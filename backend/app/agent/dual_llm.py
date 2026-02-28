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
    get_tool_display_name,
    SUMMARY_SYSTEM_PROMPT,
    SUMMARY_USER_TEMPLATE,
    TOOL_CATEGORY_MAP,
)
from .executor import tool_executor
from .registry import tool_registry
from .base import ToolResult
from .trace import Tracer, TraceType, TracerFactory

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
    trace_events: List[Dict[str, Any]] = Field(default_factory=list, description="追踪事件列表")
    trace_id: Optional[str] = Field(None, description="追踪 ID")


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
        self._active_skill: Optional["Skill"] = None  # 当前选中的 Skill（两阶段模式）
        self._active_skills: List["Skill"] = []  # 激活的 Skills 列表（宽松模式）
        self._user_memories: List[str] = []  # 召回的用户长期记忆
    
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
    
    def set_skill(self, skill: "Skill") -> None:
        """
        设置激活的 Skill
        
        激活 Skill 后：
        - 使用 Skill 的 system_prompt 替代默认 prompt
        - 只使用 Skill 白名单中的工具（如果设置了白名单）
        """
        self._active_skill = skill
        logger.info(f"激活 Skill: {skill.name} ({skill.id})")
    
    def clear_skill(self) -> None:
        """清除当前选中的 Skill"""
        if self._active_skill:
            logger.info(f"取消激活 Skill: {self._active_skill.name}")
        self._active_skill = None
    
    @property
    def active_skill(self) -> Optional["Skill"]:
        """获取当前激活的 Skill"""
        return self._active_skill
    
    def set_active_skills(self, skills: List["Skill"]) -> None:
        """设置多个激活的 Skill（宽松模式）"""
        self._active_skills = skills
        if skills:
            logger.info(f"激活 Skills（宽松模式）: {[s.name for s in skills]}")
    
    def clear_active_skills(self) -> None:
        """清除所有激活的 Skill"""
        self._active_skills = []
    
    @property
    def active_skills(self) -> List["Skill"]:
        """获取所有激活的 Skill"""
        return self._active_skills
    
    def _get_skills_prompt_section(self) -> str:
        """生成激活 Skill 的 Prompt 段落供 Intent LLM 判断"""
        if not self._active_skills:
            return ""
        lines = ["\n## 当前激活的 Skill（优先考虑）"]
        for skill in self._active_skills:
            tools_info = f"工具: {', '.join(skill.tools)}" if skill.tools else "全部工具"
            lines.append(f"- **{skill.name}** (id: {skill.id}): {skill.description} [{tools_info}]")
        lines.append("\n如果请求匹配某个 Skill，在输出中添加 \"skill_id\": \"xxx\"。")
        return "\n".join(lines)
    
    def _get_available_tools(self) -> list:
        """
        获取可用的 OpenAI 格式工具列表
        
        两阶段模式：
        - 如果有选中的 Skill（_active_skill），优先使用其工具（但不限制其他工具）
        - 否则返回所有工具
        """
        all_tools = tool_registry.get_openai_tools()
        
        # 如果有选中的 Skill 且有工具白名单，将这些工具排在前面（优先推荐）
        if self._active_skill and self._active_skill.tools:
            whitelist = set(self._active_skill.tools)
            priority_tools = [t for t in all_tools if t["function"]["name"] in whitelist]
            other_tools = [t for t in all_tools if t["function"]["name"] not in whitelist]
            return priority_tools + other_tools
        
        return all_tools
    
    async def _recall_user_memories(self, user_input: str, limit: int = 5) -> List[str]:
        """
        自动召回用户的长期记忆
        
        Args:
            user_input: 用户输入（用于关键词匹配）
            limit: 返回数量限制
        
        Returns:
            记忆内容列表
        """
        from sqlalchemy import select
        from .context import get_agent_context
        from ..models import UserMemory
        
        ctx = get_agent_context()
        if not ctx or not ctx.db_session or not ctx.user_id:
            logger.warning(f"🧠 [Memory] 无法召回记忆: ctx={ctx is not None}, db={ctx.db_session is not None if ctx else None}, user_id={ctx.user_id if ctx else None}")
            return []
        
        db = ctx.db_session
        user_id = ctx.user_id
        
        logger.info(f"🧠 [Memory] 开始召回记忆: user_id={user_id[:8]}...")
        
        try:
            # 优先召回重要的记忆（preference 和 instruction）
            stmt = select(UserMemory).where(
                UserMemory.user_id == user_id
            ).order_by(
                # 按分类优先级排序：instruction > preference > fact > general
                UserMemory.category.desc(),
                UserMemory.importance.desc(),
                UserMemory.last_accessed_at.desc()
            ).limit(limit)
            
            result = await db.execute(stmt)
            memories = result.scalars().all()
            
            if not memories:
                logger.debug(f"🧠 [Memory] 数据库中无记忆 (user_id={user_id})")
                return []
            
            # 更新访问时间
            from datetime import datetime
            for mem in memories:
                mem.last_accessed_at = datetime.utcnow()
            await db.commit()
            
            # 返回记忆内容
            return [mem.content for mem in memories]
            
        except Exception as e:
            logger.warning(f"召回记忆失败: {e}")
            return []
    
    def _get_system_prompt(self) -> str:
        """
        获取 system prompt
        
        两阶段模式：
        - 如果有选中的 Skill（_active_skill），使用其专属 Prompt
        - 否则使用默认 Prompt
        """
        base_prompt = ""
        
        # 如果有选中的 Skill，使用其专属 Prompt
        if self._active_skill and self._active_skill.system_prompt:
            base_prompt = self._active_skill.system_prompt
        else:
            # 默认 Prompt - 包含记忆功能的重要指导
            base_prompt = """你是一个智能助手。根据用户的请求，选择合适的工具来完成任务。

## 重要规则
1. **记忆优先**：当用户要求你"记住"某事、说"以后"怎样、给你取名字、介绍自己（如"我叫xxx"）时，必须调用 save_memory 工具保存信息
2. 其他请求：选择合适的工具，或直接回复

## 记忆触发词示例
- "记住..." → save_memory
- "以后..." → save_memory  
- "你叫xxx" → save_memory（保存AI名字）
- "我叫xxx" → save_memory（保存用户名字）
- "我的邮箱是..." → save_memory"""
        
        # 注入长期记忆
        if self._user_memories:
            memory_section = "\n\n## 用户长期记忆（必须遵守）\n以下是用户之前告诉你的重要信息，你必须在回复时使用这些信息：\n"
            for i, mem in enumerate(self._user_memories, 1):
                memory_section += f"- {mem}\n"
            memory_section += "\n**重要**：如果用户问你的名字，必须使用上面记忆中的名字回答。"
            base_prompt += memory_section
            logger.info(f"🧠 [SystemPrompt] 已注入 {len(self._user_memories)} 条记忆到 prompt")
        else:
            logger.info(f"🧠 [SystemPrompt] 无记忆注入, _user_memories={getattr(self, '_user_memories', 'NOT_SET')}")
        
        return base_prompt
    
    async def process(
        self,
        user_input: str,
        mode: AgentMode = AgentMode.AUTO,
        skip_summary: bool = False,
        user_context: Optional[Dict[str, Any]] = None,
        tracer: Optional[Tracer] = None,
        skill_ids: Optional[List[str]] = None,
    ) -> DualLLMResult:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入文本
            mode: 运行模式
            skip_summary: 是否跳过 Summary LLM（直接返回原始结果）
            user_context: 用户上下文（位置、时区等）
            tracer: 可选的追踪器，用于记录执行过程
            skill_id: 激活的 Skill ID（可选）
            
        Returns:
            DualLLMResult: 执行结果
        """
        user_context = user_context or {}
        tokens_used = 0
        rule_matched = False
        
        # 如果指定了 skill_ids，加载并设置激活的 Skills（宽松模式）
        if skill_ids:
            from .skill import skill_registry
            loaded_skills = []
            for sid in skill_ids:
                skill = skill_registry.get_builtin(sid)
                if skill:
                    loaded_skills.append(skill)
                else:
                    logger.warning(f"Skill 不存在: {sid}")
            if loaded_skills:
                self.set_active_skills(loaded_skills)
        
        # 创建或使用传入的 Tracer
        _tracer = tracer or TracerFactory.create()
        
        # ========== 阶段 1: 意图识别 ==========
        
        # 1.1 尝试规则匹配（0 token）
        async with _tracer.trace_async(TraceType.RULE_MATCH, "规则匹配") as span:
            span.set_data({"input": user_input[:100]})
            intent = try_rule_match(user_input)
            
            if intent:
                rule_matched = True
                span.set_data({
                    "matched": True,
                    "tool": intent.tool,
                    "category": intent.category.value,
                })
                logger.info(f"规则匹配成功: {intent.tool}")
            else:
                span.set_data({"matched": False})
        
        if not intent:
            # 1.2 调用 Intent LLM
            if mode == AgentMode.FULL:
                # 完整模式，直接 fallback 到聊天
                return DualLLMResult(
                    success=True,
                    content="",  # 由上层处理
                    intent=ParsedIntent(category=IntentCategory.CHAT, raw_input=user_input),
                    mode_used=AgentMode.FULL,
                    tokens_estimated=0,
                    trace_events=_tracer.get_events(),
                    trace_id=_tracer.trace_id,
                )
            
            async with _tracer.trace_async(TraceType.INTENT, "意图识别") as span:
                model = self.config.intent_model or self.config.model
                span.set_metadata({"model": model})
                span.set_data({"input": user_input[:100]})
                
                intent = await self._call_intent_llm(user_input)
                tokens_used += 250  # 估算 Intent LLM 消耗
                
                span.set_data({
                    "category": intent.category.value,
                    "tool": intent.tool,
                    "params": intent.params,
                    "confidence": intent.confidence,
                })
                span.set_metadata({"tokens": 250})
                
            logger.info(f"Intent LLM 识别: category={intent.category}, tool={intent.tool}")
        
        # ========== 阶段 2: 路由决策 ==========
        
        # 如果是聊天或分析类，始终 fallback 到完整 LLM
        if intent.category in (IntentCategory.CHAT, IntentCategory.ANALYZE):
            logger.info(f"CHAT/ANALYZE 类型，需要 fallback 到完整 LLM")
            return DualLLMResult(
                success=True,
                content="",  # 标记需要 fallback
                intent=intent,
                mode_used=AgentMode.FULL,
                tokens_estimated=tokens_used,
                rule_matched=rule_matched,
                trace_events=_tracer.get_events(),
                trace_id=_tracer.trace_id,
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
                trace_events=_tracer.get_events(),
                trace_id=_tracer.trace_id,
            )
        
        # 注入用户上下文到工具参数
        tool_params = dict(intent.params)
        if intent.tool == "weather" and user_context.get("location"):
            if not tool_params.get("location"):
                tool_params["location"] = user_context["location"]
                logger.info(f"使用用户上下文位置: {user_context['location']}")
        
        async with _tracer.trace_async(TraceType.TOOL_CALL, f"工具: {intent.tool}") as span:
            span.set_data({
                "tool": intent.tool,
                "display_name": get_tool_display_name(intent.tool),
                "params": tool_params,
            })
            
            tool_result = await tool_executor.execute(
                intent.tool,
                tool_params,
                require_confirmation=False,
            )
            
            span.set_data({
                "tool": intent.tool,
                "params": tool_params,
                "success": tool_result.success,
                "result": tool_result.data if tool_result.success else tool_result.error,
            })
        
        # ========== 阶段 4: 结果处理 ==========
        
        if skip_summary:
            return DualLLMResult(
                success=tool_result.success,
                content=self._format_raw_result(intent, tool_result),
                intent=intent,
                tool_result=tool_result.model_dump(),
                mode_used=AgentMode.FAST,
                tokens_estimated=tokens_used,
                rule_matched=rule_matched,
                trace_events=_tracer.get_events(),
                trace_id=_tracer.trace_id,
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
                trace_events=_tracer.get_events(),
                trace_id=_tracer.trace_id,
            )
        
        # 复杂结果调用 Summary LLM
        async with _tracer.trace_async(TraceType.SUMMARY, "摘要生成") as span:
            model = self.config.summary_model or self.config.model
            span.set_metadata({"model": model})
            
            content = await self._call_summary_llm(intent, tool_result)
            tokens_used += 250  # 估算 Summary LLM 消耗
            
            span.set_data({"output": content[:200] if content else ""})
            span.set_metadata({"tokens": 250})
        
        return DualLLMResult(
            success=tool_result.success,
            content=content,
            intent=intent,
            tool_result=tool_result.model_dump(),
            mode_used=AgentMode.FAST,
            tokens_estimated=tokens_used,
            rule_matched=rule_matched,
            trace_events=_tracer.get_events(),
            trace_id=_tracer.trace_id,
        )
    
    async def process_stream(
        self,
        user_input: str,
        mode: AgentMode = AgentMode.AUTO,
        tracer: Optional[Tracer] = None,
        skill_ids: Optional[List[str]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式处理用户输入
        
        Args:
            user_input: 用户输入
            mode: 处理模式
            tracer: 追踪器
            skill_ids: 激活的 Skill ID 列表
            history: 对话历史 [{"role": "user/assistant", "content": "..."}]
        
        Yields:
            阶段性结果，包含:
            - {"stage": "trace", "data": {...}}  # 追踪事件
            - {"stage": "skill", "data": {...}}  # Skill 激活信息
            - {"stage": "intent", "data": {...}}
            - {"stage": "tool", "data": {...}}
            - {"stage": "content", "data": "..."}
            - {"stage": "done", "data": {...}}
        """
        import time
        tokens_used = 0
        rule_matched = False
        
        # 保存对话历史供 LLM 调用使用（短期记忆）
        self._history = history or []
        
        # 发送对话历史 trace 事件
        if self._history:
            logger.info(f"📝 [History] 携带 {len(self._history)} 条对话历史")
            yield {
                "stage": "trace",
                "data": {
                    "type": "conversation_history",
                    "data": {
                        "count": len(self._history),
                        "messages": [
                            {"role": msg.get("role"), "content": msg.get("content", "")[:50] + "..." if len(msg.get("content", "")) > 50 else msg.get("content", "")}
                            for msg in self._history[-6:]  # 只显示最近 6 条
                        ],
                    }
                }
            }
        
        # 自动召回用户长期记忆
        self._user_memories = await self._recall_user_memories(user_input, limit=5)
        if self._user_memories:
            logger.info(f"🧠 [Memory] 召回 {len(self._user_memories)} 条长期记忆")
            # 发送记忆召回 trace 事件
            yield {
                "stage": "trace",
                "data": {
                    "type": "memory_recall",
                    "data": {
                        "count": len(self._user_memories),
                        "memories": self._user_memories,
                    }
                }
            }
        else:
            logger.info("🧠 [Memory] 无长期记忆")
        
        # 如果指定了 skill_ids，加载并设置激活的 Skills（宽松模式）
        if skill_ids:
            from .skill import skill_registry
            loaded_skills = []
            for sid in skill_ids:
                skill = skill_registry.get_builtin(sid)
                if skill:
                    loaded_skills.append(skill)
                else:
                    logger.warning(f"Skill 不存在: {sid}")
            if loaded_skills:
                self.set_active_skills(loaded_skills)
        
        # 创建或使用传入的 Tracer
        _tracer = tracer or TracerFactory.create()
        
        # 发送 trace_id
        yield {"stage": "trace_start", "data": {"trace_id": _tracer.trace_id}}
        
        # 如果有激活的 Skills（宽松模式），发送 Skills 信息
        if self._active_skills:
            skills_info = [{
                "id": s.id,
                "name": s.name,
                "icon": s.icon,
                "tools_count": len(s.tools) if s.tools else "all",
            } for s in self._active_skills]
            yield {"stage": "skill", "data": {"skills": skills_info, "mode": "loose"}}
            
            # 发送 Skills 激活的 trace 事件
            skill_names = ", ".join(s.name for s in self._active_skills)
            yield {"stage": "trace", "data": {
                "id": f"skill_{_tracer.trace_id[:4]}",
                "type": "skill",
                "name": f"Skills: {skill_names}",
                "stage": "end",
                "timestamp": time.time() * 1000,
                "duration_ms": 0,
                "data": {
                    "input": f"激活 Skills: {skill_names}",
                    "output": f"宽松模式，AI 智能选择",
                    "skills": skills_info,
                    "mode": "loose",
                },
                "metadata": {"count": len(self._active_skills)},
            }}
        
        # 阶段 1: 意图识别 - 规则匹配
        rule_start = time.time() * 1000
        intent = try_rule_match(user_input)
        rule_duration = time.time() * 1000 - rule_start
        
        # 发送规则匹配的 trace 事件
        yield {"stage": "trace", "data": {
            "id": f"rule_{_tracer.trace_id[:4]}",
            "type": "rule_match",
            "name": "规则匹配",
            "stage": "end",
            "timestamp": time.time() * 1000,
            "duration_ms": round(rule_duration, 2),
            "data": {
                "input": user_input[:100],
                "output": f"匹配工具: {intent.tool}" if intent else "未匹配，需调用 Intent LLM",
                "matched": intent is not None,
                "tool": intent.tool if intent else None,
                "params": intent.params if intent else None,
            },
        }}
        
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
            
            # ========== 阶段 1.5: Skill 选择（如果有激活的 Skills）==========
            selected_skill = None
            if self._active_skills:
                skill_select_start = time.time() * 1000
                model = self.config.intent_model or self.config.model
                
                yield {"stage": "trace", "data": {
                    "id": f"skill_select_{_tracer.trace_id[:4]}",
                    "type": "skill_select",
                    "name": "Skill 选择",
                    "stage": "start",
                    "timestamp": skill_select_start,
                    "data": {
                        "input": user_input[:100],
                        "candidates": [{"id": s.id, "name": s.name} for s in self._active_skills],
                    },
                    "metadata": {"model": model},
                }}
                
                select_result = await self._select_skill_llm(user_input)
                selected_skill_id = select_result.get("skill_id")
                tokens_used += 50  # Skill 选择消耗较少 token
                
                skill_select_duration = time.time() * 1000 - skill_select_start
                
                if selected_skill_id:
                    # 找到选中的 Skill 并激活
                    for skill in self._active_skills:
                        if skill.id == selected_skill_id:
                            selected_skill = skill
                            self.set_skill(skill)  # 激活该 Skill，后续使用其 Prompt 和工具
                            break
                
                yield {"stage": "trace", "data": {
                    "id": f"skill_select_{_tracer.trace_id[:4]}",
                    "type": "skill_select",
                    "name": "Skill 选择",
                    "stage": "end",
                    "timestamp": time.time() * 1000,
                    "duration_ms": round(skill_select_duration, 2),
                    "data": {
                        "input": select_result.get("prompt", user_input[:200]),
                        "output": select_result.get("raw_output", "none"),
                        "selected_skill_id": selected_skill_id,
                        "selected_skill_name": selected_skill.name if selected_skill else None,
                        "candidates": select_result.get("candidates", []),
                    },
                    "metadata": {
                        "model": select_result.get("model"),
                        "tokens": 50,
                    },
                }}
                
                # 发送 Skill 选择结果
                yield {"stage": "skill_selected", "data": {
                    "skill_id": selected_skill_id,
                    "skill_name": selected_skill.name if selected_skill else None,
                    "skill_icon": selected_skill.icon if selected_skill else None,
                }}
            
            yield {"stage": "intent", "data": {"status": "calling_llm"}}
            
            # 发送 Intent LLM 开始事件
            intent_start = time.time() * 1000
            model = self.config.intent_model or self.config.model
            yield {"stage": "trace", "data": {
                "id": f"intent_{_tracer.trace_id[:4]}",
                "type": "intent",
                "name": "意图识别",
                "stage": "start",
                "timestamp": intent_start,
                "data": {"input": user_input[:100]},
                "metadata": {"model": model},
            }}
            
            intent = await self._call_intent_llm(user_input)
            tokens_used += 250
            
            intent_duration = time.time() * 1000 - intent_start
            
            # 发送 Intent LLM 结束事件
            yield {"stage": "trace", "data": {
                "id": f"intent_{_tracer.trace_id[:4]}",
                "type": "intent",
                "name": "意图识别",
                "stage": "end",
                "timestamp": time.time() * 1000,
                "duration_ms": round(intent_duration, 2),
                "data": {
                    "input": user_input[:200],
                    "output": f"类别: {intent.category.value}, 工具: {intent.tool or '无'}, 置信度: {intent.confidence}",
                    "category": intent.category.value,
                    "tool": intent.tool,
                    "params": intent.params,
                    "confidence": intent.confidence,
                },
                "metadata": {"model": model, "tokens": 250},
            }}
            
            yield {"stage": "intent", "data": {
                "category": intent.category.value,
                "tool": intent.tool,
                "confidence": intent.confidence,
                "rule_matched": False,
            }}
        
        # 需要 fallback 到完整 LLM
        if intent.category in (IntentCategory.CHAT, IntentCategory.ANALYZE):
            # 如果 Intent LLM 已经生成了回复（包含记忆），直接使用它
            if intent.direct_response:
                logger.info(f"🧠 [DirectResponse] 使用 Intent LLM 的直接回复（已包含记忆）")
                
                yield {"stage": "trace", "data": {
                    "id": f"direct_{_tracer.trace_id[:4]}",
                    "type": "llm_call",
                    "name": "直接回复",
                    "stage": "end",
                    "timestamp": time.time() * 1000,
                    "duration_ms": 0,
                    "data": {
                        "input": user_input[:100],
                        "output": intent.direct_response[:200],
                        "has_memory": len(self._user_memories) > 0,
                        "memories": self._user_memories if self._user_memories else None,
                    },
                    "metadata": {"source": "intent_llm_direct"},
                }}
                
                # 直接返回 Intent LLM 的回复（使用 content 事件，前端会识别）
                yield {"stage": "content", "data": intent.direct_response}
                yield {"stage": "done", "data": {
                    "tokens_used": tokens_used,
                    "tokens_estimated": tokens_used,
                    "tool_used": None,
                    "rule_matched": False,
                    "has_memory": len(self._user_memories) > 0,
                }}
                return
            
            # 没有直接回复，需要 fallback 到完整 LLM
            yield {"stage": "trace", "data": {
                "id": f"fallback_{_tracer.trace_id[:4]}",
                "type": "llm_call",
                "name": "切换完整模式",
                "stage": "end",
                "timestamp": time.time() * 1000,
                "duration_ms": 0,
                "data": {
                    "input": f"意图类别: {intent.category.value}",
                    "output": "切换到完整 LLM 模式处理",
                    "reason": intent.category.value,
                    "message": "需要完整 LLM 处理复杂问题",
                },
                "metadata": {"note": "后续由完整模式处理"},
            }}
            
            yield {"stage": "fallback", "data": {
                "reason": intent.category.value,
                "tokens_used": tokens_used,
            }}
            return
        
        if not intent.tool:
            yield {"stage": "error", "data": {"message": "无法识别工具"}}
            return
        
        # 阶段 2: 工具执行
        tool_start = time.time() * 1000
        
        yield {"stage": "trace", "data": {
            "id": f"tool_{_tracer.trace_id[:4]}",
            "type": "tool_call",
            "name": f"工具: {get_tool_display_name(intent.tool)}",
            "stage": "start",
            "timestamp": tool_start,
            "data": {
                "input": f"调用 {intent.tool}，参数: {str(intent.params)[:100]}",
                "tool": intent.tool,
                "display_name": get_tool_display_name(intent.tool),
                "params": intent.params,
            },
        }}
        
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
        
        tool_duration = time.time() * 1000 - tool_start
        
        # 格式化工具输出
        tool_output_str = ""
        if tool_result.success:
            if isinstance(tool_result.data, dict):
                # 提取关键信息
                result_data = tool_result.data.get("result", tool_result.data)
                tool_output_str = str(result_data)[:200]
            else:
                tool_output_str = str(tool_result.data)[:200]
        else:
            tool_output_str = f"错误: {tool_result.error}"
        
        yield {"stage": "trace", "data": {
            "id": f"tool_{_tracer.trace_id[:4]}",
            "type": "tool_call",
            "name": f"工具: {get_tool_display_name(intent.tool)}",
            "stage": "end",
            "timestamp": time.time() * 1000,
            "duration_ms": round(tool_duration, 2),
            "data": {
                "input": f"调用 {intent.tool}，参数: {str(intent.params)[:100]}",
                "output": tool_output_str,
                "tool": intent.tool,
                "params": intent.params,
                "success": tool_result.success,
                "result": tool_result.data if tool_result.success else tool_result.error,
            },
        }}
        
        yield {"stage": "tool", "data": {
            "name": intent.tool,
            "status": "completed",
            "success": tool_result.success,
            "result": tool_result.model_dump(),
        }}
        
        # 如果是记忆存储工具，发送专门的 trace 事件
        if intent.tool == "save_memory" and tool_result.success:
            yield {
                "stage": "trace",
                "data": {
                    "type": "memory_save",
                    "data": {
                        "content": intent.params.get("content", ""),
                        "category": intent.params.get("category", "general"),
                        "result": tool_result.data,
                    }
                }
            }
        
        # 阶段 3: 结果输出
        if tool_result.success and self._is_simple_result(tool_result.data):
            # 简单结果：直接格式化（0 token）
            format_start = time.time() * 1000
            
            yield {"stage": "trace", "data": {
                "id": f"format_{_tracer.trace_id[:4]}",
                "type": "llm_call",
                "name": "结果格式化",
                "stage": "start",
                "timestamp": format_start,
                "data": {
                    "input": f"工具结果: {tool_output_str[:100]}",
                    "type": "simple_format",
                },
                "metadata": {"tokens": 0},
            }}
            
            content = self._format_simple_result(intent, tool_result)
            
            format_duration = time.time() * 1000 - format_start
            
            yield {"stage": "trace", "data": {
                "id": f"format_{_tracer.trace_id[:4]}",
                "type": "llm_call",
                "name": "结果格式化",
                "stage": "end",
                "timestamp": time.time() * 1000,
                "duration_ms": round(format_duration, 2),
                "data": {
                    "input": f"工具结果: {tool_output_str[:100]}",
                    "output": content[:300] if content else "",
                    "type": "simple_format",
                },
                "metadata": {"tokens": 0, "note": "简单结果，无需 LLM"},
            }}
            
            yield {"stage": "content", "data": content}
        else:
            yield {"stage": "summary", "data": {"status": "calling_llm"}}
            
            summary_start = time.time() * 1000
            model = self.config.summary_model or self.config.model
            
            # 准备输入摘要
            summary_input = f"工具: {intent.tool}, 结果: {tool_output_str[:100]}"
            
            yield {"stage": "trace", "data": {
                "id": f"summary_{_tracer.trace_id[:4]}",
                "type": "summary",
                "name": "摘要生成",
                "stage": "start",
                "timestamp": summary_start,
                "data": {"input": summary_input},
                "metadata": {"model": model},
            }}
            
            content = await self._call_summary_llm(intent, tool_result)
            tokens_used += 250
            
            summary_duration = time.time() * 1000 - summary_start
            
            yield {"stage": "trace", "data": {
                "id": f"summary_{_tracer.trace_id[:4]}",
                "type": "summary",
                "name": "摘要生成",
                "stage": "end",
                "timestamp": time.time() * 1000,
                "duration_ms": round(summary_duration, 2),
                "data": {
                    "input": summary_input,
                    "output": content[:300] if content else "",
                },
                "metadata": {"model": model, "tokens": 250},
            }}
            
            yield {"stage": "content", "data": content}
        
        # 完成
        yield {"stage": "done", "data": {
            "tokens_estimated": tokens_used,
            "rule_matched": rule_matched,
            "mode": AgentMode.FAST.value,
            "trace_id": _tracer.trace_id,
        }}
    

    async def _select_skill_llm(self, user_input: str) -> Dict[str, Any]:
        """
        第一阶段：Skill 选择 LLM
        
        根据用户输入判断应该使用哪个激活的 Skill
        返回包含选择结果和详细信息的字典
        """
        result = {
            "skill_id": None,
            "model": None,
            "prompt": None,
            "raw_output": None,
            "candidates": [],
        }
        
        if not self._active_skills:
            return result
        
        import time
        start_time = time.time()
        model = self.config.intent_model or self.config.model
        result["model"] = model
        result["candidates"] = [{"id": s.id, "name": s.name} for s in self._active_skills]
        
        # 构建 Skill 选择 Prompt
        skills_desc = []
        for skill in self._active_skills:
            tools_info = f"专属工具: {', '.join(skill.tools)}" if skill.tools else "可用所有工具"
            skills_desc.append(f"- {skill.id}: {skill.name} - {skill.description} ({tools_info})")
        
        system_prompt = f"""你是一个意图分类器。根据用户的输入，判断应该使用哪个 Skill 来处理。

当前激活的 Skills:
{chr(10).join(skills_desc)}

规则：
1. 如果用户的请求明显属于某个 Skill 的领域，返回该 Skill 的 id
2. 如果不确定或不属于任何 Skill，返回 "none"
3. 只返回 skill_id 或 "none"，不要返回其他内容"""

        user_prompt = f"用户输入: {user_input}\n\n请返回应该使用的 skill_id 或 \"none\":"
        result["prompt"] = f"[System]\n{system_prompt}\n\n[User]\n{user_prompt}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
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
                    "max_tokens": 50,
                    "temperature": 0.1,
                },
            )
            
            elapsed = (time.time() - start_time) * 1000
            
            if response.status_code != 200:
                logger.warning(f"🎯 [SkillSelect] 调用失败: {response.status_code}, 耗时={elapsed:.0f}ms")
                return result
            
            resp_json = response.json()
            raw_output = resp_json["choices"][0]["message"]["content"].strip()
            result["raw_output"] = raw_output
            
            skill_id = raw_output.strip('"').strip("'")
            
            # 验证返回的 skill_id 是否有效
            if skill_id == "none" or not skill_id:
                logger.info(f"🎯 [SkillSelect] 未匹配任何 Skill, 耗时={elapsed:.0f}ms")
                return result
            
            # 检查是否是有效的 skill_id
            valid_ids = [s.id for s in self._active_skills]
            if skill_id in valid_ids:
                logger.info(f"🎯 [SkillSelect] 选择 Skill: {skill_id}, 耗时={elapsed:.0f}ms")
                result["skill_id"] = skill_id
                return result
            else:
                logger.warning(f"🎯 [SkillSelect] 返回了无效的 skill_id: {skill_id}, 耗时={elapsed:.0f}ms")
                return result
                
        except Exception as e:
            logger.error(f"🎯 [SkillSelect] 异常: {e}", exc_info=True)
            return result

    def _detect_memory_intent(self, user_input: str) -> Optional[ParsedIntent]:
        """
        检测是否是记忆相关的请求（规则优先于 LLM）
        
        某些 LLM 对 Function Calling 的支持不够好，会忽略记忆相关请求。
        这里使用规则检测来确保记忆功能正常工作。
        """
        import re
        text = user_input.strip()
        
        # 记忆触发模式: (pattern, category, content_transform)
        # content_transform: 如果是函数，用于将匹配结果转换为更清晰的记忆内容
        # 注意：更具体的模式要放在前面，通用模式放在后面
        memory_patterns = [
            # 给 AI 取名 - 需要特殊处理，保存更明确的内容（多种表达方式）
            (r"(?:你)?以后叫(.{1,15})", "instruction", lambda m: f"AI 助手的名字是: {m.group(1).strip()}"),
            (r"以后(?:你)?叫(.{1,15})", "instruction", lambda m: f"AI 助手的名字是: {m.group(1).strip()}"),
            (r"(?:以后)?(?:你|叫你)叫(.{1,15})", "instruction", lambda m: f"AI 助手的名字是: {m.group(1).strip()}"),
            (r"你的名字(?:以后)?(?:是|叫)(.{1,15})", "instruction", lambda m: f"AI 助手的名字是: {m.group(1).strip()}"),
            (r"称呼你(?:为)?(.{1,15})", "instruction", lambda m: f"AI 助手的名字是: {m.group(1).strip()}"),
            (r"叫你(.{1,15})", "instruction", lambda m: f"AI 助手的名字是: {m.group(1).strip()}"),
            # 用户自我介绍
            (r"我叫(.{1,15})", "fact", lambda m: f"用户的名字是: {m.group(1).strip()}"),
            (r"我的名字是(.{1,15})", "fact", lambda m: f"用户的名字是: {m.group(1).strip()}"),
            (r"我的邮箱是(.+)", "fact", lambda m: f"用户的邮箱: {m.group(1).strip()}"),
            (r"我的电话是(.+)", "fact", lambda m: f"用户的电话: {m.group(1).strip()}"),
            (r"我在(.{2,20})工作", "fact", lambda m: f"用户在 {m.group(1).strip()} 工作"),
            (r"我从事(.{2,20})", "fact", lambda m: f"用户从事 {m.group(1).strip()}"),
            (r"我是(.{2,30})", "fact", lambda m: f"用户是: {m.group(1).strip()}"),
            # 偏好
            (r"我喜欢(.{2,})", "preference", lambda m: f"用户喜欢: {m.group(1).strip()}"),
            (r"我不喜欢(.{2,})", "preference", lambda m: f"用户不喜欢: {m.group(1).strip()}"),
            (r"我偏好(.{2,})", "preference", lambda m: f"用户偏好: {m.group(1).strip()}"),
            # 通用记忆请求（保留原始内容）
            (r"记住(.{2,})", "general", lambda m: m.group(1).strip()),
            (r"记得(.{2,})", "general", lambda m: m.group(1).strip()),
            # 指令类（保留原始内容）
            (r"以后(.{2,})", "instruction", None),  # None 表示使用原始输入
            (r"今后(.{2,})", "instruction", None),
            (r"下次(.{2,})", "instruction", None),
            (r"每次(.{2,})", "instruction", None),
            (r"永远(.{2,})", "instruction", None),
            (r"始终(.{2,})", "instruction", None),
        ]
        
        for pattern, category, transform in memory_patterns:
            match = re.search(pattern, text)
            if match:
                # 转换内容为更清晰的格式
                if transform:
                    content = transform(match)
                else:
                    content = text
                    
                logger.info(f"🧠 [Memory] 规则检测命中: pattern={pattern}, content={content}")
                return ParsedIntent(
                    category=IntentCategory.MEMORY,
                    tool="save_memory",
                    params={
                        "content": content,
                        "category": category,
                    },
                    confidence=1.0,
                    raw_input=user_input,
                )
        
        return None

    async def _call_intent_llm(self, user_input: str) -> ParsedIntent:
        """调用 Intent LLM 识别意图（使用 Function Calling）"""
        import time
        start_time = time.time()
        model = self.config.intent_model or self.config.model
        
        # 先用规则检测记忆意图（规则优先于 LLM）
        memory_intent = self._detect_memory_intent(user_input)
        if memory_intent:
            return memory_intent
        
        logger.debug(f"🧠 [IntentLLM] 开始调用 Function Calling: model={model}, input={user_input[:50]}...")
        
        # 获取可用工具列表（如果有激活的 Skill，会过滤工具）
        tools = self._get_available_tools()
        
        # 获取 system prompt（如果有激活的 Skill，使用 Skill 的 prompt）
        system_prompt = self._get_system_prompt()
        
        # 调试：检查 system prompt 是否包含记忆
        has_memory_in_prompt = "用户长期记忆" in system_prompt
        mem_count = len(self._user_memories) if hasattr(self, '_user_memories') else 0
        logger.info(f"🧠 [IntentLLM] system_prompt 包含记忆: {has_memory_in_prompt}, _user_memories 数量: {mem_count}")
        if has_memory_in_prompt:
            logger.info(f"🧠 [IntentLLM] 记忆内容: {self._user_memories}")
        
        # 构建 messages，包含对话历史
        messages = [{"role": "system", "content": system_prompt}]
        
        # 添加对话历史（限制最近 10 轮，避免超出 token 限制）
        if hasattr(self, '_history') and self._history:
            history_limit = 10  # 最近 10 条消息（约 5 轮对话）
            recent_history = self._history[-history_limit:]
            for msg in recent_history:
                if msg.get("role") in ("user", "assistant") and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})
        
        # 添加当前用户输入
        messages.append({"role": "user", "content": user_input})
        
        # 调试：打印 messages 结构
        logger.debug(f"🧠 [IntentLLM] Messages 结构: {len(messages)} 条, roles={[m['role'] for m in messages]}")
        
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
            
            # 调试：打印工具列表中是否有 save_memory
            tool_names = [t["function"]["name"] for t in tools] if tools else []
            logger.info(f"🧠 [IntentLLM] 可用工具数: {len(tool_names)}, 包含save_memory: {'save_memory' in tool_names}")
            
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
            
            # 调试：打印完整响应
            logger.debug(f"🧠 [IntentLLM] 完整响应: {message}")
            
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
    
    def _format_stock_analysis(self, data: dict) -> str:
        """将股票分析数据格式化为精简文本（节省 token）"""
        lines = []
        
        # 行情
        quote = data.get("quote", {})
        if quote and "error" not in quote:
            lines.append(f"## {quote.get('name', '')}({quote.get('code', '')})")
            lines.append(f"价格:{quote.get('price', 0)}元 涨跌:{quote.get('change_percent', 0):+.2f}%")
            if quote.get('industry'):
                lines.append(f"行业:{quote.get('industry')}")
        
        # 财务（精简格式）
        finance = data.get("finance", {})
        if finance and "error" not in finance:
            items = []
            if finance.get("roe"): items.append(f"ROE:{finance['roe']:.1f}%")
            if finance.get("gross_margin"): items.append(f"毛利率:{finance['gross_margin']:.1f}%")
            if finance.get("net_margin"): items.append(f"净利率:{finance['net_margin']:.1f}%")
            if finance.get("profit_growth"): items.append(f"利润增长:{finance['profit_growth']:+.1f}%")
            if finance.get("debt_ratio"): items.append(f"负债率:{finance['debt_ratio']:.1f}%")
            if items:
                lines.append(f"财务: {' | '.join(items)}")
        
        # 技术指标（精简格式）
        tech = data.get("technical", {})
        indicators = tech.get("indicators", {})
        if indicators:
            items = []
            if indicators.get("MA5"): items.append(f"MA5:{indicators['MA5']:.1f}")
            if indicators.get("MA20"): items.append(f"MA20:{indicators['MA20']:.1f}")
            macd = indicators.get("MACD", {})
            if macd: items.append(f"MACD:{'金叉' if macd.get('dif',0) > macd.get('dea',0) else '死叉'}")
            kdj = indicators.get("KDJ", {})
            if kdj and kdj.get("j"): items.append(f"KDJ-J:{kdj['j']:.0f}")
            if indicators.get("RSI"): items.append(f"RSI:{indicators['RSI']:.0f}")
            if items:
                lines.append(f"技术: {' | '.join(items)}")
        
        # 趋势
        trend = tech.get("trend", {})
        if trend:
            trend_items = []
            if trend.get("macd_signal"): trend_items.append(trend["macd_signal"])
            if trend.get("kdj_signal"): trend_items.append(trend["kdj_signal"])
            if trend.get("rsi_signal"): trend_items.append(trend["rsi_signal"])
            if trend_items:
                lines.append(f"信号: {', '.join(trend_items)}")
        
        # 投资建议
        suggestion = data.get("suggestion", {})
        if suggestion:
            lines.append(f"建议: {suggestion.get('overall', '观望')} (技术:{suggestion.get('technical_score', 50)}分 基本面:{suggestion.get('fundamental_score', 50)}分)")
            if suggestion.get("reasons"):
                lines.append(f"利好: {'; '.join(suggestion['reasons'][:3])}")
            if suggestion.get("risks"):
                lines.append(f"风险: {'; '.join(suggestion['risks'][:3])}")
        
        # 新闻（只取标题）
        news = data.get("news", {})
        news_list = news.get("news", [])
        if news_list:
            lines.append("新闻:")
            for n in news_list[:3]:
                title = n.get("title", "")[:40]
                lines.append(f"- {title}...")
        
        # 免责声明
        lines.append("\n⚠️ 以上分析仅供参考，不构成投资建议。")
        
        return "\n".join(lines)
    
    async def _call_summary_llm(self, intent: ParsedIntent, tool_result: ToolResult) -> str:
        """调用 Summary LLM 总结结果"""
        import time
        start_time = time.time()
        model = self.config.summary_model or self.config.model
        
        logger.debug(f"📝 [SummaryLLM] 开始调用: model={model}, tool={intent.tool}")
        
        max_result_len = 2000
        max_tokens = 600
        
        # 股票分析类工具：使用专门的格式化函数
        if intent.tool == "analyze_stock" and tool_result.success:
            result_text = self._format_stock_analysis(tool_result.data)
            max_tokens = 800
        elif intent.tool in ("get_stock_finance", "get_technical_indicators") and tool_result.success:
            result_text = json.dumps(tool_result.data, ensure_ascii=False, indent=1)
            if len(result_text) > 2500:
                result_text = result_text[:2500] + "..."
            max_tokens = 700
        elif tool_result.success:
            result_text = json.dumps(tool_result.data, ensure_ascii=False, indent=1)
            if len(result_text) > max_result_len:
                result_text = result_text[:max_result_len] + "..."
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
                    "max_tokens": max_tokens,
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
