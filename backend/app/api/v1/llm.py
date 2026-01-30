"""LLM 配置和聊天 API"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import httpx
import json
import logging
from typing import AsyncGenerator, List, Optional, Any, Dict

logger = logging.getLogger(__name__)

from ...database import get_db
from ...config import settings
from ...models import User, UserLLMConfig, KnowledgeItem
from ...schemas.llm import (
    LLMConfigCreate, 
    LLMConfigResponse, 
    ChatRequest, 
    ChatResponse,
    LLM_PROVIDERS,
    LLM_PROVIDERS_MAP,
    LLMProvider
)
from ...schemas.knowledge import RAGChatRequest, RAGSource
from ..deps import get_current_user

# Agent Tool Calling
from ...agent import tool_registry, tool_executor

router = APIRouter(prefix="/llm", tags=["LLM"])


# ==================== HTTP 客户端连接池 ====================

_llm_http_client: Optional[httpx.AsyncClient] = None


def get_llm_http_client() -> httpx.AsyncClient:
    """获取 LLM HTTP 客户端（单例，复用连接池）"""
    global _llm_http_client
    if _llm_http_client is None or _llm_http_client.is_closed:
        _llm_http_client = httpx.AsyncClient(
            timeout=120.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )
    return _llm_http_client


async def close_llm_http_client():
    """关闭 LLM HTTP 客户端（应用关闭时调用）"""
    global _llm_http_client
    if _llm_http_client and not _llm_http_client.is_closed:
        await _llm_http_client.aclose()
        _llm_http_client = None
        logger.info("LLM HTTP 客户端已关闭")


# ==================== LLM 提供商 ====================

@router.get("/providers", response_model=list[LLMProvider])
async def get_llm_providers():
    """获取所有 LLM 提供商列表"""
    return LLM_PROVIDERS


@router.get("/default-config")
async def get_default_config():
    """获取系统默认 LLM 配置状态"""
    default_config = get_default_llm_config()
    
    if not default_config:
        return {
            "available": False,
            "provider_id": None,
            "model": None,
            "models": [],
        }
    
    # 获取提供商支持的模型列表
    provider = LLM_PROVIDERS_MAP.get(default_config.provider_id)
    models = provider.models if provider else [default_config.model]
    
    return {
        "available": True,
        "provider_id": default_config.provider_id,
        "provider_name": provider.name if provider else default_config.provider_id,
        "model": default_config.model,
        "models": models,
    }


# ==================== 用户 LLM 配置 ====================

@router.get("/config", response_model=LLMConfigResponse)
async def get_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的 LLM 配置"""
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="LLM 配置未设置")
    
    return LLMConfigResponse(
        id=config.id,
        provider_id=config.provider_id,
        api_key_set=bool(config.api_key),
        base_url=config.base_url,
        model=config.model,
        use_system_default=bool(config.use_system_default),
        created_at=config.created_at,
        updated_at=config.updated_at
    )


@router.put("/config", response_model=LLMConfigResponse)
async def update_llm_config(
    config_data: LLMConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新当前用户的 LLM 配置"""
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    base_url = config_data.base_url
    if not base_url and config_data.provider_id in LLM_PROVIDERS_MAP:
        base_url = LLM_PROVIDERS_MAP[config_data.provider_id].base_url
    
    if config:
        config.provider_id = config_data.provider_id
        if config_data.api_key is not None:
            config.api_key = config_data.api_key
        config.base_url = base_url
        config.model = config_data.model
        config.use_system_default = config_data.use_system_default
    else:
        config = UserLLMConfig(
            user_id=current_user.id,
            provider_id=config_data.provider_id,
            api_key=config_data.api_key,
            base_url=base_url,
            model=config_data.model,
            use_system_default=config_data.use_system_default
        )
        db.add(config)
    
    await db.flush()
    await db.refresh(config)
    
    return LLMConfigResponse(
        id=config.id,
        provider_id=config.provider_id,
        api_key_set=bool(config.api_key),
        base_url=config.base_url,
        model=config.model,
        use_system_default=bool(config.use_system_default),
        created_at=config.created_at,
        updated_at=config.updated_at
    )


@router.delete("/config")
async def delete_llm_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除当前用户的 LLM 配置"""
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    config = result.scalar_one_or_none()
    
    if config:
        await db.delete(config)
    
    return {"message": "配置已删除"}


# ==================== 聊天 API ====================

# 基础系统提示词
BASE_SYSTEM_PROMPT = """你是一个专业的 Web 安全分析助手。

## 你的能力
- 分析 HTTP 请求/响应中的安全问题
- 识别常见漏洞（SQL注入、XSS、CSRF、SSRF等）
- 生成测试 payload
- 提供修复建议

## 回复格式
当用户提供 HTTP 请求或询问安全问题时，请按以下结构回复：

### 1. 🔍 分析
简要分析请求结构和潜在风险点

### 2. 🎯 潜在漏洞
列出可能存在的漏洞类型和风险等级

### 3. 🧪 测试建议
提供具体的测试 payload（可直接复制使用）

### 4. 🛡️ 修复建议
如果发现问题，提供修复方案

## 重要原则
- 只在用户有授权的情况下进行测试建议
- 提供可操作的具体建议
- 解释清楚漏洞原理"""

# RAG 增强系统提示词模板
RAG_SYSTEM_PROMPT_TEMPLATE = """{base_prompt}

## 用户知识库参考
以下是从用户知识库中检索到的相关内容，请优先参考这些内容来回答问题：

{knowledge_context}

---
请基于以上知识库内容和你的专业知识来回答用户的问题。如果知识库中有相关内容，请在回答中引用。"""


class DefaultLLMConfig:
    """默认 LLM 配置（用于系统默认配置）"""
    def __init__(self, provider_id: str, api_key: str, base_url: str, model: str):
        self.provider_id = provider_id
        self.api_key = api_key
        self.base_url = base_url
        self.model = model


def get_default_llm_config() -> Optional[DefaultLLMConfig]:
    """获取系统默认 LLM 配置"""
    if not settings.DEFAULT_LLM_API_KEY:
        return None
    
    provider_id = settings.DEFAULT_LLM_PROVIDER or "deepseek"
    
    # 获取 base_url：优先使用配置的，否则使用提供商默认的
    base_url = settings.DEFAULT_LLM_BASE_URL
    if not base_url and provider_id in LLM_PROVIDERS_MAP:
        base_url = LLM_PROVIDERS_MAP[provider_id].base_url
    
    # 获取 model：优先使用配置的，否则使用提供商默认的
    model = settings.DEFAULT_LLM_MODEL
    if not model and provider_id in LLM_PROVIDERS_MAP:
        model = LLM_PROVIDERS_MAP[provider_id].default_model
    
    if not base_url or not model:
        return None
    
    return DefaultLLMConfig(
        provider_id=provider_id,
        api_key=settings.DEFAULT_LLM_API_KEY,
        base_url=base_url,
        model=model
    )


async def get_user_llm_config(user_id: str, db: AsyncSession):
    """获取用户的 LLM 配置，如果用户未配置则尝试使用系统默认配置"""
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    
    # 如果用户选择使用系统默认配置
    if config and config.use_system_default:
        default_config = get_default_llm_config()
        if default_config:
            # 使用用户选择的模型，但用系统默认的 API Key
            default_config.model = config.model or default_config.model
            logger.info(f"用户 {user_id} 使用系统默认 LLM 配置 (provider={default_config.provider_id}, model={default_config.model})")
            return default_config
        else:
            raise HTTPException(
                status_code=400,
                detail="系统默认配置不可用，请联系管理员或使用自己的 API Key"
            )
    
    # 如果用户有配置且有 API Key（或者是 Ollama），使用用户配置
    if config and (config.api_key or config.provider_id == "ollama"):
        return config
    
    # 尝试使用系统默认配置（用户未配置时的 fallback）
    default_config = get_default_llm_config()
    if default_config:
        logger.info(f"用户 {user_id} 使用系统默认 LLM 配置 (provider={default_config.provider_id})")
        return default_config
    
    # 都没有配置，报错
    if not config:
        raise HTTPException(
            status_code=400, 
            detail="请先在设置中配置 LLM API Key"
        )
    
    raise HTTPException(
        status_code=400,
        detail="请先配置 API Key"
    )


async def search_knowledge_base(
    user_id: str,
    query: str,
    source_types: List[str],
    limit: int,
    db: AsyncSession
) -> List[KnowledgeItem]:
    """搜索知识库"""
    if not query.strip():
        return []
    
    # 先统计用户知识库总数（调试用）
    total_query = select(KnowledgeItem).where(
        KnowledgeItem.user_id == user_id,
        KnowledgeItem.is_enabled == True,
    )
    if source_types:
        total_query = total_query.where(KnowledgeItem.source_type.in_(source_types))
    total_result = await db.execute(total_query)
    all_items = list(total_result.scalars().all())
    print(f"📊 [RAG] 用户知识库总数: {len(all_items)} 条 (来源类型: {source_types})")
    if all_items:
        print(f"📊 [RAG] 知识库标题: {[item.title[:30] for item in all_items[:5]]}...")
    
    # 构建查询
    db_query = select(KnowledgeItem).where(
        KnowledgeItem.user_id == user_id,
        KnowledgeItem.is_enabled == True,
    )
    
    # 筛选来源类型
    if source_types:
        db_query = db_query.where(KnowledgeItem.source_type.in_(source_types))
    
    # 使用 jieba 进行中文分词
    import jieba
    import jieba.analyse
    
    # 使用 TF-IDF 提取关键词（更智能的语义分割）
    keywords = jieba.analyse.extract_tags(query, topK=8, withWeight=False)
    
    # 补充：提取英文单词（jieba 对英文处理较弱）
    import re
    eng_words = re.findall(r'[a-zA-Z]{2,}', query)
    keywords = list(dict.fromkeys(eng_words + keywords))[:10]
    
    logger.debug(f"[RAG] 分词关键词: {keywords}")
    
    if keywords:
        # 构建 OR 条件：标题或内容包含任意关键词
        conditions = []
        for keyword in keywords[:5]:  # 限制关键词数量
            pattern = f"%{keyword}%"
            conditions.append(KnowledgeItem.title.ilike(pattern))
            conditions.append(KnowledgeItem.content.ilike(pattern))
        
        db_query = db_query.where(or_(*conditions))
    
    db_query = db_query.limit(limit)
    
    result = await db.execute(db_query)
    return list(result.scalars().all())


def build_knowledge_context(items: List[KnowledgeItem]) -> tuple[str, List[RAGSource]]:
    """构建知识库上下文和来源列表（优先使用摘要）"""
    if not items:
        return "", []
    
    context_parts = []
    sources = []
    
    for i, item in enumerate(items, 1):
        # 来源类型标记
        type_emoji = {"note": "📝", "bookmark": "🔗", "file": "📄"}.get(item.source_type, "📋")
        
        # 优先使用摘要，没有摘要则使用内容预览
        if item.summary:
            # 有摘要时，使用摘要作为主要内容
            content_text = f"**摘要:** {item.summary}"
            # 如果内容不太长，也附带部分内容
            if item.content and len(item.content) <= 500:
                content_text += f"\n\n**详情:** {item.content}"
            elif item.content:
                content_text += f"\n\n**详情预览:** {item.content[:300]}..."
        else:
            # 没有摘要时，使用内容预览
            content_text = item.content[:1000] if item.content else item.title
        
        context_parts.append(f"""### {type_emoji} [{i}] {item.title}
{content_text}
""")
        
        # 构建来源（snippet 优先使用摘要）
        snippet = item.summary if item.summary else (item.content[:200] if item.content else "")
        sources.append(RAGSource(
            source_type=item.source_type,
            source_id=item.source_id,
            title=item.title,
            snippet=snippet,
            url=item.url,
        ))
    
    return "\n".join(context_parts), sources


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """聊天接口（非流式）"""
    config = await get_user_llm_config(current_user.id, db)
    
    # RAG 检索
    sources = []
    system_prompt = BASE_SYSTEM_PROMPT
    
    if request.use_rag:
        # 搜索知识库
        knowledge_items = await search_knowledge_base(
            user_id=current_user.id,
            query=request.message,
            source_types=["note", "bookmark", "file"],
            limit=5,
            db=db,
        )
        
        if knowledge_items:
            knowledge_context, sources = build_knowledge_context(knowledge_items)
            system_prompt = RAG_SYSTEM_PROMPT_TEMPLATE.format(
                base_prompt=BASE_SYSTEM_PROMPT,
                knowledge_context=knowledge_context,
            )
    
    # 构建消息
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})
    
    messages.append({"role": "user", "content": request.message})
    
    # 调用 LLM（使用连接池）
    try:
        client = get_llm_http_client()
        response = await client.post(
            f"{config.base_url}/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}"
            },
            json={
                "model": config.model,
                "messages": messages,
                "stream": False
            }
        )
        
        if response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error", {}).get("message", error_detail)
            except:
                pass
            raise HTTPException(status_code=response.status_code, detail=error_detail)
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        return ChatResponse(
            content=content, 
            sources=[s.model_dump() for s in sources]
        )
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="LLM 请求超时")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"LLM 请求失败: {str(e)}")


@router.post("/chat/stream")
async def chat_stream(
    request: RAGChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """聊天接口（流式，支持 RAG）"""
    import time
    start_time = time.time()
    
    logger.info(f"💬 [Chat] 开始处理: user={current_user.username}, message={request.message[:50]}..., use_knowledge={request.use_knowledge}")
    
    config = await get_user_llm_config(current_user.id, db)
    logger.debug(f"💬 [Chat] LLM配置: model={config.model}")
    
    # RAG 检索
    sources: List[RAGSource] = []
    system_prompt = BASE_SYSTEM_PROMPT
    
    print(f"🔍 [Chat] 用户={current_user.username}, 知识库={request.use_knowledge}, 来源类型={request.knowledge_sources}")
    
    if request.use_knowledge:
        # 搜索知识库
        knowledge_items = await search_knowledge_base(
            user_id=current_user.id,
            query=request.message,
            source_types=request.knowledge_sources,
            limit=request.max_results,
            db=db,
        )
        
        print(f"📚 [Chat] 知识库检索结果: {len(knowledge_items)} 条")
        
        if knowledge_items:
            knowledge_context, sources = build_knowledge_context(knowledge_items)
            system_prompt = RAG_SYSTEM_PROMPT_TEMPLATE.format(
                base_prompt=BASE_SYSTEM_PROMPT,
                knowledge_context=knowledge_context,
            )
            print(f"📖 [Chat] RAG 来源: {[s.title for s in sources]}")
        else:
            print("⚠️ [Chat] 知识库未检索到相关内容")
    
    # 构建消息
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in request.history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    
    messages.append({"role": "user", "content": request.message})
    
    async def generate() -> AsyncGenerator[str, None]:
        # 先发送来源信息
        if sources:
            yield f"data: {json.dumps({'sources': [s.model_dump() for s in sources]})}\n\n"
        
        try:
            client = get_llm_http_client()
            async with client.stream(
                "POST",
                f"{config.base_url}/chat/completions",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.api_key}"
                },
                json={
                    "model": config.model,
                    "messages": messages,
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield f"data: {json.dumps({'error': error_text.decode()})}\n\n"
                    return
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            break
                        try:
                            chunk = json.loads(data)
                            content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if content:
                                yield f"data: {json.dumps({'content': content})}\n\n"
                        except json.JSONDecodeError:
                            pass
                                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "Transfer-Encoding": "chunked",
        }
    )


# ==================== Agent Tool Calling API ====================

@router.get("/agent/tools")
async def get_agent_tools(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """获取可用的 Agent 工具列表"""
    categories = [category] if category else None
    tools = tool_registry.get_tools_info(categories=categories)
    return {
        "tools": tools,
        "categories": tool_registry.get_categories(),
    }


@router.get("/agent/tools/openai-format")
async def get_agent_tools_openai_format(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """获取 OpenAI Function Calling 格式的工具定义"""
    categories = [category] if category else None
    return tool_registry.get_openai_tools(categories=categories)


@router.post("/agent/execute")
async def execute_agent_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """
    执行单个 Agent 工具
    
    用于手动测试工具或前端直接调用工具。
    """
    result = await tool_executor.execute(tool_name, arguments, require_confirmation=False)
    return result.model_dump()


# Agent 增强系统提示词
AGENT_SYSTEM_PROMPT = """你是一个专业的 Web 安全分析助手，具有使用工具的能力。

## 你的能力
- 分析 HTTP 请求/响应中的安全问题
- 识别常见漏洞（SQL注入、XSS、CSRF、SSRF等）
- 使用工具进行编码/解码、哈希计算、网络查询等操作
- 生成测试 payload
- 提供修复建议

## 工具使用原则
- 当需要进行编码、解码、哈希计算等操作时，使用对应的工具
- 当需要查询域名、IP 信息时，使用网络查询工具
- 工具执行结果会返回给你，请基于结果继续分析

## 回复格式
当你使用工具时，请说明你要做什么以及为什么。
当你得到工具结果后，请对结果进行分析和解释。

## 重要原则
- 只在用户有授权的情况下进行测试建议
- 提供可操作的具体建议
- 解释清楚漏洞原理"""


from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    message: str = Field(..., description="用户消息")
    history: List[Dict[str, Any]] = Field(default=[], description="对话历史")
    use_tools: bool = Field(default=True, description="是否启用工具调用")
    tool_categories: Optional[List[str]] = Field(default=None, description="启用的工具分类")
    use_knowledge: bool = Field(default=False, description="是否使用知识库")
    knowledge_sources: List[str] = Field(default=["note", "bookmark"], description="知识库来源类型")
    max_tool_iterations: int = Field(default=5, description="最大工具调用轮次")


@router.post("/agent/chat")
async def agent_chat_stream(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Agent 聊天接口（流式，支持 Tool Calling）
    
    支持 LLM 自动调用工具完成任务，工具执行结果会自动反馈给 LLM 继续处理。
    """
    logger.info(f"🤖 [AgentChat] 开始处理: user={current_user.username}, message={request.message[:50]}..., use_tools={request.use_tools}")
    
    config = await get_user_llm_config(current_user.id, db)
    logger.debug(f"🤖 [AgentChat] LLM配置: model={config.model}")
    
    # 构建系统提示词
    system_prompt = AGENT_SYSTEM_PROMPT
    sources: List[RAGSource] = []
    
    # RAG 检索
    if request.use_knowledge:
        knowledge_items = await search_knowledge_base(
            user_id=current_user.id,
            query=request.message,
            source_types=request.knowledge_sources,
            limit=5,
            db=db,
        )
        
        if knowledge_items:
            knowledge_context, sources = build_knowledge_context(knowledge_items)
            system_prompt = f"""{AGENT_SYSTEM_PROMPT}

## 用户知识库参考
以下是从用户知识库中检索到的相关内容：

{knowledge_context}

---
请基于以上知识库内容和你的专业知识来回答用户的问题。"""
    
    # 构建消息
    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in request.history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    
    messages.append({"role": "user", "content": request.message})
    
    # 获取工具定义
    tools = []
    if request.use_tools:
        tools = tool_registry.get_openai_tools(categories=request.tool_categories)
    
    async def generate() -> AsyncGenerator[str, None]:
        nonlocal messages
        
        try:
            
            # 发送知识库来源
            if sources:
                yield f"data: {json.dumps({'sources': [s.model_dump() for s in sources]})}\n\n"
            
            # 发送可用工具信息
            if tools:
                tool_names = [t["function"]["name"] for t in tools]
                yield f"data: {json.dumps({'available_tools': tool_names})}\n\n"
            
            iteration = 0
            max_iterations = request.max_tool_iterations
            
            while iteration < max_iterations:
                iteration += 1
                
                try:
                    client = get_llm_http_client()
                    # 构建请求体
                    request_body = {
                        "model": config.model,
                        "messages": messages,
                        "stream": True,
                    }
                    
                    # 添加工具（如果有）
                    if tools:
                        request_body["tools"] = tools
                        request_body["tool_choice"] = "auto"
                    
                    async with client.stream(
                        "POST",
                        f"{config.base_url}/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {config.api_key}"
                        },
                        json=request_body
                    ) as response:
                            if response.status_code != 200:
                                error_text = await response.aread()
                                error_msg = error_text.decode()
                                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                                return
                            
                            # 收集完整响应
                            full_content = ""
                            tool_calls_data: Dict[int, Dict] = {}
                            finish_reason = None
                            
                            async for line in response.aiter_lines():
                                if not line.startswith("data: "):
                                    continue
                                
                                data = line[6:]
                                if data == "[DONE]":
                                    break
                                
                                try:
                                    chunk = json.loads(data)
                                    choice = chunk.get("choices", [{}])[0]
                                    delta = choice.get("delta", {})
                                    finish_reason = choice.get("finish_reason") or finish_reason
                                    
                                    # 处理文本内容
                                    content = delta.get("content", "")
                                    if content:
                                        full_content += content
                                        yield f"data: {json.dumps({'content': content})}\n\n"
                                    
                                    # 处理工具调用
                                    if "tool_calls" in delta:
                                        for tc in delta["tool_calls"]:
                                            idx = tc.get("index", 0)
                                            if idx not in tool_calls_data:
                                                tool_calls_data[idx] = {
                                                    "id": tc.get("id", ""),
                                                    "type": "function",
                                                    "function": {"name": "", "arguments": ""}
                                                }
                                            
                                            if tc.get("id"):
                                                tool_calls_data[idx]["id"] = tc["id"]
                                            
                                            func = tc.get("function", {})
                                            if func.get("name"):
                                                tool_calls_data[idx]["function"]["name"] = func["name"]
                                            if func.get("arguments"):
                                                tool_calls_data[idx]["function"]["arguments"] += func["arguments"]
                                    
                                except json.JSONDecodeError:
                                    pass
                            
                            # 检查是否有工具调用
                            has_tool_calls = finish_reason == "tool_calls" and bool(tool_calls_data)
                            if has_tool_calls:
                                tool_calls = list(tool_calls_data.values())
                                
                                # 将 assistant 消息（包含工具调用）添加到历史
                                assistant_message = {"role": "assistant", "content": full_content or None}
                                if tool_calls:
                                    assistant_message["tool_calls"] = tool_calls
                                messages.append(assistant_message)
                                
                                # 执行工具调用
                                for tc in tool_calls:
                                    tool_name = tc["function"]["name"]
                                    tool_call_id = tc["id"]
                                    
                                    try:
                                        arguments = json.loads(tc["function"]["arguments"])
                                    except json.JSONDecodeError:
                                        arguments = {}
                                    
                                    # 通知前端工具调用开始
                                    yield f"data: {json.dumps({'tool_call': {'name': tool_name, 'arguments': arguments, 'status': 'executing'}})}\n\n"
                                    
                                    # 执行工具
                                    result = await tool_executor.execute(tool_name, arguments, require_confirmation=False)
                                    
                                    # 格式化结果
                                    if result.success:
                                        result_content = json.dumps(result.data, ensure_ascii=False, indent=2)
                                    else:
                                        result_content = f"错误: {result.error}"
                                    
                                    # 通知前端工具执行完成
                                    yield f"data: {json.dumps({'tool_call': {'name': tool_name, 'result': result.model_dump(), 'status': 'completed'}})}\n\n"
                                    
                                    # 将工具结果添加到消息
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": tool_call_id,
                                        "content": result_content,
                                    })
                                
                                # 继续下一轮对话
                                continue
                            
                            # 没有工具调用或正常结束，退出循环
                            yield f"data: {json.dumps({'done': True})}\n\n"
                            return
                            
                except Exception as e:
                    error_msg = str(e)
                    logger.exception("Agent chat error")
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    return
            
            # 达到最大迭代次数
            yield f"data: {json.dumps({'warning': '达到最大工具调用次数限制', 'done': True})}\n\n"
            
        except Exception as e:
            logger.exception("Agent generate error")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "Transfer-Encoding": "chunked",
        }
    )


# ==================== 双 LLM 架构 API (省 Token 模式) ====================

from ...agent.dual_llm import DualLLMAgent, LLMConfig, AgentMode, DualLLMResult, get_shared_agent
from ...agent.intent import IntentCategory


class UserContext(BaseModel):
    """用户上下文信息"""
    location: Optional[str] = Field(default=None, description="用户位置（城市名）")
    timezone: Optional[str] = Field(default=None, description="用户时区")
    language: Optional[str] = Field(default="zh-CN", description="用户语言")


class FastChatRequest(BaseModel):
    """快速聊天请求（双 LLM 模式）"""
    message: str = Field(..., description="用户消息")
    mode: str = Field(default="auto", description="模式: auto/fast/full")
    skip_summary: bool = Field(default=False, description="跳过 Summary LLM")
    context: Optional[UserContext] = Field(default=None, description="用户上下文信息")


class FastChatResponse(BaseModel):
    """快速聊天响应"""
    content: str = Field(..., description="回复内容")
    mode_used: str = Field(..., description="实际使用的模式")
    tokens_estimated: int = Field(default=0, description="估算 token 消耗")
    rule_matched: bool = Field(default=False, description="是否规则匹配")
    tool_used: Optional[str] = Field(None, description="使用的工具")
    fallback_needed: bool = Field(default=False, description="是否需要 fallback 到完整模式")


@router.post("/fast/chat", response_model=FastChatResponse)
async def fast_chat(
    request: FastChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    快速聊天接口（双 LLM 架构，省 Token）
    
    工作流程:
    1. 规则匹配 → 工具执行 → 格式化返回 (0 token)
    2. Intent LLM → 工具执行 → Summary LLM (~400 tokens)
    3. 复杂问题 fallback 到完整 LLM
    
    相比传统 Tool Calling，Token 消耗降低 60-70%
    """
    import time
    start_time = time.time()
    logger.info(f"⚡ [FastChat] 开始处理: user={current_user.username}, msg={request.message[:50]}...")
    
    config = await get_user_llm_config(current_user.id, db)
    
    # 使用共享 Agent（避免每次请求都创建新的 HTTP 客户端）
    agent_config = LLMConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        intent_model=getattr(settings, 'INTENT_LLM_MODEL', None),
        summary_model=getattr(settings, 'SUMMARY_LLM_MODEL', None),
    )
    
    # 使用共享 Agent 而不是每次创建新的
    agent = await get_shared_agent(agent_config)
    
    try:
        # 解析模式
        mode_map = {
            "auto": AgentMode.AUTO,
            "fast": AgentMode.FAST,
            "full": AgentMode.FULL,
        }
        mode = mode_map.get(request.mode, AgentMode.AUTO)
        
        # 构建用户上下文
        user_context = {}
        if request.context:
            if request.context.location:
                user_context["location"] = request.context.location
            if request.context.timezone:
                user_context["timezone"] = request.context.timezone
        
        # 处理请求
        result = await agent.process(
            request.message,
            mode=mode,
            skip_summary=request.skip_summary,
            user_context=user_context,
        )
        
        # 检查是否需要 fallback
        fallback_needed = (
            result.intent and 
            result.intent.category in (IntentCategory.CHAT, IntentCategory.ANALYZE) and
            not result.content
        )
        
        elapsed = (time.time() - start_time) * 1000
        logger.info(f"✅ [FastChat] 完成: tool={result.intent.tool if result.intent else None}, tokens={result.tokens_estimated}, rule={result.rule_matched}, fallback={fallback_needed}, {elapsed:.0f}ms")
        
        return FastChatResponse(
            content=result.content,
            mode_used=result.mode_used.value,
            tokens_estimated=result.tokens_estimated,
            rule_matched=result.rule_matched,
            tool_used=result.intent.tool if result.intent else None,
            fallback_needed=fallback_needed,
        )
    except Exception as e:
        elapsed = (time.time() - start_time) * 1000
        logger.error(f"❌ [FastChat] 错误: {e}, {elapsed:.0f}ms", exc_info=True)
        raise
    # 注意：不再需要 finally 中关闭 agent，因为使用的是共享 Agent


@router.post("/fast/chat/stream")
async def fast_chat_stream(
    request: FastChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    快速聊天流式接口（双 LLM 架构）
    
    返回 SSE 流，包含各阶段状态:
    - intent: 意图识别结果
    - tool: 工具执行状态
    - content: 最终内容
    - fallback: 需要切换到完整模式
    - done: 完成
    """
    config = await get_user_llm_config(current_user.id, db)
    
    agent_config = LLMConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        intent_model=getattr(settings, 'INTENT_LLM_MODEL', None),
        summary_model=getattr(settings, 'SUMMARY_LLM_MODEL', None),
    )
    
    agent = DualLLMAgent(agent_config)
    
    mode_map = {
        "auto": AgentMode.AUTO,
        "fast": AgentMode.FAST,
        "full": AgentMode.FULL,
    }
    mode = mode_map.get(request.mode, AgentMode.AUTO)
    
    async def generate() -> AsyncGenerator[str, None]:
        try:
            async for event in agent.process_stream(request.message, mode=mode):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception("Fast chat stream error")
            yield f"data: {json.dumps({'stage': 'error', 'data': str(e)})}\n\n"
        finally:
            await agent.close()
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            "Transfer-Encoding": "chunked",
        }
    )


@router.get("/fast/info")
async def get_fast_mode_info(
    current_user: User = Depends(get_current_user),
):
    """
    获取快速模式信息
    
    返回支持的工具分类和预估 token 消耗对比
    """
    return {
        "enabled": getattr(settings, 'DUAL_LLM_ENABLED', True),
        "supported_categories": [
            {"id": "encode", "name": "编码", "examples": ["base64", "url", "html", "hex"]},
            {"id": "decode", "name": "解码", "examples": ["base64", "url", "html", "hex"]},
            {"id": "hash", "name": "哈希", "examples": ["md5", "sha256", "hmac"]},
            {"id": "network", "name": "网络", "examples": ["dns", "whois", "ip"]},
        ],
        "fallback_categories": [
            {"id": "analyze", "name": "安全分析", "reason": "需要完整 LLM 能力"},
            {"id": "chat", "name": "普通对话", "reason": "开放式问答"},
        ],
        "token_comparison": {
            "traditional": {"per_request": "1000-2000", "description": "传统 Tool Calling"},
            "fast_mode": {"per_request": "0-400", "description": "双 LLM 架构"},
            "savings": "60-70%",
        },
        "models": {
            "intent": getattr(settings, 'INTENT_LLM_MODEL', None) or "使用默认模型",
            "summary": getattr(settings, 'SUMMARY_LLM_MODEL', None) or "使用默认模型",
        }
    }
