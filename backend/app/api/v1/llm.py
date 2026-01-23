"""LLM 配置和聊天 API"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
import httpx
import json
import logging
from typing import AsyncGenerator, List, Optional

logger = logging.getLogger(__name__)

from ...database import get_db
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

router = APIRouter(prefix="/llm", tags=["LLM"])


# ==================== LLM 提供商 ====================

@router.get("/providers", response_model=list[LLMProvider])
async def get_llm_providers():
    """获取所有 LLM 提供商列表"""
    return LLM_PROVIDERS


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
    else:
        config = UserLLMConfig(
            user_id=current_user.id,
            provider_id=config_data.provider_id,
            api_key=config_data.api_key,
            base_url=base_url,
            model=config_data.model
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


async def get_user_llm_config(user_id: str, db: AsyncSession) -> UserLLMConfig:
    """获取用户的 LLM 配置"""
    result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=400, 
            detail="请先在设置中配置 LLM API Key"
        )
    
    if not config.api_key and config.provider_id != "ollama":
        raise HTTPException(
            status_code=400,
            detail="请先配置 API Key"
        )
    
    return config


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
    
    print(f"🔑 [RAG] jieba 分词关键词: {keywords}")
    
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
    
    # 调用 LLM
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
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
    config = await get_user_llm_config(current_user.id, db)
    
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
            async with httpx.AsyncClient(timeout=120.0) as client:
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
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
