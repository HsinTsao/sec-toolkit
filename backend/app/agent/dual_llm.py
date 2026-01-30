"""
双 LLM 架构 Agent

实现高效的 Token 消耗优化架构：
    User Input → Intent LLM (~200 tokens) → Router → Tool → Summary LLM (~200 tokens)

相比传统 Tool Calling 架构，Token 消耗降低 60-70%。

使用示例:
    agent = DualLLMAgent(llm_config)
    result = await agent.process("把 hello world 转成 base64")
    # result.content = "Base64 编码结果: aGVsbG8gd29ybGQ="
    # result.tokens_used ≈ 400 (vs 传统架构 ~1500)
"""

import json
import asyncio
import httpx
import logging
from typing import Any, Dict, Optional, AsyncGenerator, List
from pydantic import BaseModel, Field
from enum import Enum

from .intent import (
    IntentCategory,
    ParsedIntent,
    try_rule_match,
    parse_llm_intent_response,
    get_tool_display_name,
    get_intent_system_prompt,  # 动态获取 Prompt（备用）
    INTENT_USER_TEMPLATE,
    SUMMARY_SYSTEM_PROMPT,
    SUMMARY_USER_TEMPLATE,
    TOOL_CATEGORY_MAP,
)
from .executor import tool_executor
from .registry import tool_registry
from .base import ToolResult

logger = logging.getLogger(__name__)


class AgentMode(str, Enum):
    """Agent 运行模式"""
    FAST = "fast"        # 双 LLM 模式（省 token）
    FULL = "full"        # 完整 Tool Calling 模式（强能力）
    AUTO = "auto"        # 自动选择


class DualLLMResult(BaseModel):
    """双 LLM Agent 执行结果"""
    success: bool = Field(..., description="是否成功")
    content: str = Field(..., description="最终回复内容")
    intent: Optional[ParsedIntent] = Field(None, description="识别的意图")
    tool_result: Optional[Dict[str, Any]] = Field(None, description="工具执行结果")
    mode_used: AgentMode = Field(default=AgentMode.FAST, description="使用的模式")
    tokens_estimated: int = Field(default=0, description="估算 token 消耗")
    rule_matched: bool = Field(default=False, description="是否规则匹配（0 token）")


class LLMConfig(BaseModel):
    """LLM 配置"""
    base_url: str
    api_key: str
    model: str
    # 可选：独立的 Intent/Summary 模型（更省 token）
    intent_model: Optional[str] = None
    summary_model: Optional[str] = None


class DualLLMAgent:
    """
    双 LLM 架构 Agent
    
    工作流程:
    1. 规则优先匹配（0 token）
    2. 如果规则匹配失败，调用 Intent LLM (~200 tokens)
    3. Deterministic Router 根据意图调用工具（0 token）
    4. 简单结果直接返回（0 token），复杂结果调用 Summary LLM (~200 tokens)
    
    总消耗: 0-400 tokens（传统架构: 1000-2000 tokens）
    """
    
    def __init__(self, config: LLMConfig, use_shared_client: bool = False):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._use_shared_client = use_shared_client
        self._owns_client = False  # 标记是否拥有客户端（需要自己关闭）
    
    @property
    def client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（同步版本，用于兼容）"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
            self._owns_client = True
        return self._client
    
    async def get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端（异步版本，支持共享客户端）"""
        if self._use_shared_client:
            return await get_shared_client(self.config.base_url)
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
            self._owns_client = True
        return self._client
    
    async def close(self):
        """关闭客户端（仅关闭自己创建的客户端，不关闭共享客户端）"""
        if self._client and self._owns_client:
            await self._client.aclose()
            self._client = None
            self._owns_client = False
    
    async def process(
        self,
        user_input: str,
        mode: AgentMode = AgentMode.AUTO,
        skip_summary: bool = False,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> DualLLMResult:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入文本
            mode: 运行模式
            skip_summary: 是否跳过 Summary LLM（直接返回原始结果）
            user_context: 用户上下文（位置、时区等）
            
        Returns:
            DualLLMResult: 执行结果
        """
        user_context = user_context or {}
        tokens_used = 0
        rule_matched = False
        
        # ========== 阶段 1: 意图识别 ==========
        
        # 1.1 尝试规则匹配（0 token）
        intent = try_rule_match(user_input)
        
        if intent:
            rule_matched = True
            logger.info(f"规则匹配成功: {intent.tool}")
        else:
            # 1.2 调用 Intent LLM
            if mode == AgentMode.FULL:
                # 完整模式，直接 fallback 到聊天
                return DualLLMResult(
                    success=True,
                    content="",  # 由上层处理
                    intent=ParsedIntent(category=IntentCategory.CHAT, raw_input=user_input),
                    mode_used=AgentMode.FULL,
                    tokens_estimated=0,
                )
            
            intent = await self._call_intent_llm(user_input)
            tokens_used += 250  # 估算 Intent LLM 消耗
            logger.info(f"Intent LLM 识别: category={intent.category}, tool={intent.tool}")
        
        # ========== 阶段 2: 路由决策 ==========
        
        # 如果是聊天或分析类，始终 fallback 到完整 LLM
        # 注意：Intent LLM 的目的是识别意图，不是生成完整回复
        # 它的 max_tokens 较小，回复会被截断，所以不应该直接使用
        if intent.category in (IntentCategory.CHAT, IntentCategory.ANALYZE):
            logger.info(f"CHAT/ANALYZE 类型，需要 fallback 到完整 LLM")
            return DualLLMResult(
                success=True,
                content="",  # 标记需要 fallback
                intent=intent,
                mode_used=AgentMode.FULL,
                tokens_estimated=tokens_used,
                rule_matched=rule_matched,
            )
        
        # ========== 阶段 3: 工具执行 (0 token) ==========
        
        if not intent.tool:
            return DualLLMResult(
                success=False,
                content="无法识别要执行的工具",
                intent=intent,
                mode_used=AgentMode.FAST,
                tokens_estimated=tokens_used,
                rule_matched=rule_matched,
            )
        
        # 注入用户上下文到工具参数
        tool_params = dict(intent.params)
        if intent.tool == "weather" and user_context.get("location"):
            # 如果用户没有指定位置，使用上下文中的位置
            if not tool_params.get("location"):
                tool_params["location"] = user_context["location"]
                logger.info(f"使用用户上下文位置: {user_context['location']}")
        
        tool_result = await tool_executor.execute(
            intent.tool,
            tool_params,
            require_confirmation=False,
        )
        
        # ========== 阶段 4: 结果处理 ==========
        
        if skip_summary:
            # 直接返回原始结果
            return DualLLMResult(
                success=tool_result.success,
                content=self._format_raw_result(intent, tool_result),
                intent=intent,
                tool_result=tool_result.model_dump(),
                mode_used=AgentMode.FAST,
                tokens_estimated=tokens_used,
                rule_matched=rule_matched,
            )
        
        # 简单结果直接格式化返回（0 token）
        if tool_result.success and self._is_simple_result(tool_result.data):
            content = self._format_simple_result(intent, tool_result)
            return DualLLMResult(
                success=True,
                content=content,
                intent=intent,
                tool_result=tool_result.model_dump(),
                mode_used=AgentMode.FAST,
                tokens_estimated=tokens_used,
                rule_matched=rule_matched,
            )
        
        # 复杂结果调用 Summary LLM
        content = await self._call_summary_llm(intent, tool_result)
        tokens_used += 250  # 估算 Summary LLM 消耗
        
        return DualLLMResult(
            success=tool_result.success,
            content=content,
            intent=intent,
            tool_result=tool_result.model_dump(),
            mode_used=AgentMode.FAST,
            tokens_estimated=tokens_used,
            rule_matched=rule_matched,
        )
    
    async def process_stream(
        self,
        user_input: str,
        mode: AgentMode = AgentMode.AUTO,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式处理用户输入
        
        Yields:
            阶段性结果，包含:
            - {"stage": "intent", "data": {...}}
            - {"stage": "tool", "data": {...}}
            - {"stage": "content", "data": "..."}
            - {"stage": "done", "data": {...}}
        """
        tokens_used = 0
        rule_matched = False
        
        # 阶段 1: 意图识别
        intent = try_rule_match(user_input)
        
        if intent:
            rule_matched = True
            yield {"stage": "intent", "data": {
                "category": intent.category.value,
                "tool": intent.tool,
                "rule_matched": True,
            }}
        else:
            if mode == AgentMode.FULL:
                yield {"stage": "fallback", "data": {"reason": "full_mode"}}
                return
            
            yield {"stage": "intent", "data": {"status": "calling_llm"}}
            intent = await self._call_intent_llm(user_input)
            tokens_used += 250
            
            yield {"stage": "intent", "data": {
                "category": intent.category.value,
                "tool": intent.tool,
                "confidence": intent.confidence,
                "rule_matched": False,
            }}
        
        # 需要 fallback 到完整 LLM
        if intent.category in (IntentCategory.CHAT, IntentCategory.ANALYZE):
            yield {"stage": "fallback", "data": {
                "reason": intent.category.value,
                "tokens_used": tokens_used,
            }}
            return
        
        if not intent.tool:
            yield {"stage": "error", "data": {"message": "无法识别工具"}}
            return
        
        # 阶段 2: 工具执行
        yield {"stage": "tool", "data": {
            "name": intent.tool,
            "display_name": get_tool_display_name(intent.tool),
            "params": intent.params,
            "status": "executing",
        }}
        
        tool_result = await tool_executor.execute(
            intent.tool,
            intent.params,
            require_confirmation=False,
        )
        
        yield {"stage": "tool", "data": {
            "name": intent.tool,
            "status": "completed",
            "success": tool_result.success,
            "result": tool_result.model_dump(),
        }}
        
        # 阶段 3: 结果输出
        if tool_result.success and self._is_simple_result(tool_result.data):
            content = self._format_simple_result(intent, tool_result)
            yield {"stage": "content", "data": content}
        else:
            yield {"stage": "summary", "data": {"status": "calling_llm"}}
            content = await self._call_summary_llm(intent, tool_result)
            tokens_used += 250
            yield {"stage": "content", "data": content}
        
        # 完成
        yield {"stage": "done", "data": {
            "tokens_estimated": tokens_used,
            "rule_matched": rule_matched,
            "mode": AgentMode.FAST.value,
        }}
    
    async def _call_intent_llm(self, user_input: str) -> ParsedIntent:
        """调用 Intent LLM 识别意图（使用 Function Calling）"""
        import time
        start_time = time.time()
        model = self.config.intent_model or self.config.model
        
        logger.debug(f"🧠 [IntentLLM] 开始调用 Function Calling: model={model}, input={user_input[:50]}...")
        
        # 获取 OpenAI 格式的工具列表
        tools = tool_registry.get_openai_tools()
        
        messages = [
            {"role": "system", "content": "你是一个智能助手。根据用户的请求，选择合适的工具来完成任务。如果不需要工具，直接回复用户。"},
            {"role": "user", "content": user_input},
        ]
        
        try:
            request_body = {
                "model": model,
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.1,
            }
            
            # 如果有工具，添加 tools 参数
            if tools:
                request_body["tools"] = tools
                request_body["tool_choice"] = "auto"  # 让模型自动决定是否调用工具
            
            client = await self.get_client()
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
                json=request_body,
            )
            
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                logger.error(f"🧠 [IntentLLM] 调用失败: status={response.status_code}, body={response.text[:200]}, 耗时={elapsed:.0f}ms")
                return ParsedIntent(category=IntentCategory.CHAT, raw_input=user_input)
            
            result = response.json()
            message = result["choices"][0]["message"]
            
            # 检查是否有 tool_calls
            tool_calls = message.get("tool_calls", [])
            
            if tool_calls:
                # 模型选择了工具
                tool_call = tool_calls[0]  # 取第一个工具调用
                tool_name = tool_call["function"]["name"]
                tool_args_str = tool_call["function"]["arguments"]
                
                try:
                    tool_params = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_params = {}
                
                # 从工具名称推断分类
                category = TOOL_CATEGORY_MAP.get(tool_name, IntentCategory.CHAT)
                
                logger.info(f"🧠 [IntentLLM] Function Calling: tool={tool_name}, params={tool_params}, 耗时={elapsed:.0f}ms")
                
                return ParsedIntent(
                    category=category,
                    tool=tool_name,
                    params=tool_params,
                    confidence=0.95,  # Function Calling 置信度更高
                    raw_input=user_input,
                )
            else:
                # 模型没有选择工具，视为普通聊天
                content = message.get("content", "")
                logger.info(f"🧠 [IntentLLM] 无工具调用，fallback 到 CHAT: {content[:100]}, 耗时={elapsed:.0f}ms")
                
                return ParsedIntent(
                    category=IntentCategory.CHAT,
                    tool=None,
                    params={},
                    confidence=0.8,
                    raw_input=user_input,
                    direct_response=content if content else None,  # 保存模型的直接回复
                )
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"🧠 [IntentLLM] 调用异常: {e}, 耗时={elapsed:.0f}ms", exc_info=True)
            return ParsedIntent(category=IntentCategory.CHAT, raw_input=user_input)
    
    async def _call_summary_llm(self, intent: ParsedIntent, tool_result: ToolResult) -> str:
        """调用 Summary LLM 总结结果"""
        import time
        start_time = time.time()
        model = self.config.summary_model or self.config.model
        
        logger.debug(f"📝 [SummaryLLM] 开始调用: model={model}, tool={intent.tool}")
        
        # 格式化结果
        if tool_result.success:
            result_text = json.dumps(tool_result.data, ensure_ascii=False, indent=2)
            if len(result_text) > 1000:
                result_text = result_text[:1000] + "\n...(结果已截断)"
        else:
            result_text = f"错误: {tool_result.error}"
        
        messages = [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": SUMMARY_USER_TEMPLATE.format(
                tool_name=get_tool_display_name(intent.tool or ""),
                input_text=json.dumps(intent.params, ensure_ascii=False),
                result=result_text,
            )},
        ]
        
        try:
            client = await self.get_client()
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.config.api_key}",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 300,
                    "temperature": 0.3,
                },
            )
            
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                logger.error(f"📝 [SummaryLLM] 调用失败: status={response.status_code}, 耗时={elapsed:.0f}ms")
                return self._format_raw_result(intent, tool_result)
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            logger.info(f"📝 [SummaryLLM] 总结完成: 耗时={elapsed:.0f}ms, 长度={len(content)}")
            
            return content
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"📝 [SummaryLLM] 调用异常: {e}, 耗时={elapsed:.0f}ms", exc_info=True)
            return self._format_raw_result(intent, tool_result)
    
    def _is_simple_result(self, data: Any) -> bool:
        """判断是否是简单结果（不需要 LLM 总结）"""
        if data is None:
            return True
        if isinstance(data, str):
            return len(data) < 500
        if isinstance(data, (int, float, bool)):
            return True
        if isinstance(data, dict):
            # 简单的键值对
            return len(data) <= 3 and all(
                isinstance(v, (str, int, float, bool)) and 
                (not isinstance(v, str) or len(v) < 200)
                for v in data.values()
            )
        return False
    
    def _format_simple_result(self, intent: ParsedIntent, tool_result: ToolResult) -> str:
        """格式化简单结果（0 token）"""
        tool_name = get_tool_display_name(intent.tool or "")
        
        if not tool_result.success:
            return f"❌ {tool_name} 执行失败: {tool_result.error}"
        
        data = tool_result.data
        
        # 字符串结果
        if isinstance(data, str):
            return f"✅ **{tool_name}** 结果:\n```\n{data}\n```"
        
        # 字典结果
        if isinstance(data, dict):
            if len(data) == 1:
                key, value = list(data.items())[0]
                return f"✅ **{tool_name}** 结果:\n```\n{value}\n```"
            else:
                lines = [f"✅ **{tool_name}** 结果:"]
                for key, value in data.items():
                    lines.append(f"- **{key}**: `{value}`")
                return "\n".join(lines)
        
        # 其他类型
        return f"✅ **{tool_name}** 结果:\n```\n{data}\n```"
    
    def _format_raw_result(self, intent: ParsedIntent, tool_result: ToolResult) -> str:
        """格式化原始结果（fallback）"""
        tool_name = get_tool_display_name(intent.tool or "")
        
        if not tool_result.success:
            return f"❌ {tool_name} 执行失败: {tool_result.error}"
        
        data = tool_result.data
        if isinstance(data, str):
            return f"✅ {tool_name} 结果:\n```\n{data}\n```"
        
        return f"✅ {tool_name} 结果:\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"


# ==================== 共享 HTTP 客户端池 ====================

import weakref
from typing import Dict

# 全局共享的 HTTP 客户端（按 base_url 分组，避免重复创建）
_shared_clients: Dict[str, httpx.AsyncClient] = {}
_client_lock = asyncio.Lock()


async def get_shared_client(base_url: str) -> httpx.AsyncClient:
    """获取共享的 HTTP 客户端（避免每次请求都创建新客户端）"""
    async with _client_lock:
        if base_url not in _shared_clients or _shared_clients[base_url].is_closed:
            _shared_clients[base_url] = httpx.AsyncClient(
                timeout=60.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
            )
            logger.info(f"创建共享 HTTP 客户端: {base_url}")
        return _shared_clients[base_url]


async def cleanup_shared_clients():
    """清理所有共享客户端（应用关闭时调用）"""
    async with _client_lock:
        for url, client in _shared_clients.items():
            if not client.is_closed:
                await client.aclose()
                logger.info(f"关闭共享 HTTP 客户端: {url}")
        _shared_clients.clear()


# ==================== 共享 Agent 池 ====================

_shared_agents: Dict[str, "DualLLMAgent"] = {}
_agent_lock = asyncio.Lock()


async def get_shared_agent(config: LLMConfig) -> "DualLLMAgent":
    """
    获取共享的 DualLLMAgent（避免每次请求都创建新 Agent）
    
    使用 base_url 作为 key，因为通常同一个 API 端点使用同一个客户端
    """
    key = config.base_url
    
    async with _agent_lock:
        if key not in _shared_agents:
            agent = DualLLMAgent(config, use_shared_client=True)
            _shared_agents[key] = agent
            logger.info(f"创建共享 Agent: {key}")
        else:
            # 更新配置（API key 可能变化）
            _shared_agents[key].config = config
        return _shared_agents[key]


# ==================== 便捷函数 ====================

async def create_dual_llm_agent(
    base_url: str,
    api_key: str,
    model: str,
    intent_model: Optional[str] = None,
    summary_model: Optional[str] = None,
) -> DualLLMAgent:
    """创建双 LLM Agent"""
    config = LLMConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        intent_model=intent_model,
        summary_model=summary_model,
    )
    return DualLLMAgent(config)


async def quick_process(
    user_input: str,
    base_url: str,
    api_key: str,
    model: str,
) -> DualLLMResult:
    """快速处理单个输入"""
    agent = await create_dual_llm_agent(base_url, api_key, model)
    try:
        return await agent.process(user_input)
    finally:
        await agent.close()
