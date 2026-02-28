"""
RAG (Retrieval-Augmented Generation) 模块

提供检索增强生成能力：
1. 从知识库检索相关内容
2. 生成向量嵌入
3. 计算相似度并排序
4. 将检索结果注入到 LLM 上下文

使用通义千问的 text-embedding-v2 API 生成向量。
"""
import json
import hashlib
import logging
import httpx
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .base import AgentModule, AgentContext, ModuleResult
from ...config import settings

logger = logging.getLogger(__name__)


class RAGModule(AgentModule):
    """
    RAG 模块
    
    支持从多种知识源检索：
    - 笔记 (note)
    - 书签 (bookmark)  
    - 上传文件 (file)
    """
    
    name = "rag"
    description = "检索增强生成 - 从知识库检索相关内容"
    version = "1.0.0"
    
    # 默认配置
    DEFAULT_CONFIG = {
        "top_k": 5,              # 返回前 K 个结果
        "min_score": 0.3,        # 最小相似度阈值
        "max_context_length": 4000,  # 最大上下文长度
        "sources": ["note", "bookmark", "file"],  # 启用的知识源
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._embedding_cache: Dict[str, List[float]] = {}  # 简单缓存
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本的向量嵌入
        
        使用通义千问的 text-embedding-v2 API
        """
        # 检查缓存
        cache_key = hashlib.md5(text.encode()).hexdigest()
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        try:
            api_key = getattr(settings, 'DEFAULT_LLM_API_KEY', None)
            if not api_key:
                logger.warning("未配置 DEFAULT_LLM_API_KEY，无法生成向量")
                return None
            
            client = await self._get_client()
            response = await client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "text-embedding-v2",
                    "input": {
                        "texts": [text[:2048]]  # 限制长度
                    },
                    "parameters": {
                        "text_type": "query"
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                embeddings = result.get("output", {}).get("embeddings", [])
                if embeddings:
                    embedding = embeddings[0].get("embedding", [])
                    # 缓存结果
                    self._embedding_cache[cache_key] = embedding
                    return embedding
            else:
                logger.error(f"Embedding API 错误: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            logger.error(f"获取 Embedding 失败: {e}")
        
        return None
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def _search_knowledge(
        self, 
        query: str, 
        db: AsyncSession,
        user_id: str,
        sources: List[str],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """
        搜索知识库
        
        1. 获取查询的向量嵌入
        2. 获取知识库条目
        3. 计算相似度并排序
        4. 返回 top_k 个结果
        """
        from ...models import KnowledgeItem
        
        # 获取查询向量
        query_embedding = await self._get_embedding(query)
        
        # 查询知识库条目
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.user_id == user_id,
            KnowledgeItem.is_enabled == True,
            KnowledgeItem.source_type.in_(sources),
        )
        result = await db.execute(stmt)
        items = result.scalars().all()
        
        if not items:
            return []
        
        # 计算相似度
        scored_items: List[Tuple[float, Dict[str, Any]]] = []
        
        for item in items:
            # 使用标题和内容计算相似度
            text = f"{item.title} {item.summary or ''} {(item.content or '')[:500]}"
            
            if query_embedding:
                # 使用向量相似度
                item_embedding = await self._get_embedding(text[:500])
                if item_embedding:
                    score = self._cosine_similarity(query_embedding, item_embedding)
                else:
                    # 回退到关键词匹配
                    score = self._keyword_score(query, text)
            else:
                # 回退到关键词匹配
                score = self._keyword_score(query, text)
            
            if score >= self.config["min_score"]:
                scored_items.append((score, {
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "title": item.title,
                    "content": item.content or item.summary or "",
                    "url": item.url,
                    "score": score,
                }))
        
        # 按相似度排序
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        return [item for _, item in scored_items[:top_k]]
    
    def _keyword_score(self, query: str, text: str) -> float:
        """简单的关键词匹配评分"""
        query_words = set(query.lower().split())
        text_lower = text.lower()
        
        if not query_words:
            return 0.0
        
        matches = sum(1 for word in query_words if word in text_lower)
        return matches / len(query_words)
    
    def _format_context(self, results: List[Dict[str, Any]], max_length: int) -> str:
        """格式化检索结果为上下文"""
        if not results:
            return ""
        
        context_parts = ["以下是与问题相关的参考资料：\n"]
        current_length = len(context_parts[0])
        
        for i, item in enumerate(results, 1):
            content = item.get("content", "")
            # 截断过长的内容
            if len(content) > 500:
                content = content[:500] + "..."
            
            entry = f"\n[{i}] {item['title']}\n{content}\n"
            
            if current_length + len(entry) > max_length:
                break
            
            context_parts.append(entry)
            current_length += len(entry)
        
        return "".join(context_parts)
    
    async def process(
        self, 
        context: AgentContext,
        db: Optional[AsyncSession] = None,
    ) -> ModuleResult:
        """
        处理 RAG 检索请求
        
        Args:
            context: Agent 执行上下文
            db: 数据库会话
            
        Returns:
            ModuleResult: 包含检索到的上下文和来源
        """
        if not db:
            return ModuleResult.fail("数据库会话未提供")
        
        try:
            # 执行检索
            results = await self._search_knowledge(
                query=context.user_input,
                db=db,
                user_id=context.user_id,
                sources=self.config["sources"],
                top_k=self.config["top_k"],
            )
            
            if not results:
                logger.info(f"[RAG] 未找到相关内容: query={context.user_input[:50]}")
                return ModuleResult.ok(
                    data={"found": False},
                    context="",
                    sources=[],
                )
            
            # 格式化上下文
            formatted_context = self._format_context(
                results, 
                self.config["max_context_length"]
            )
            
            # 提取来源信息
            sources = [
                {
                    "source_type": r["source_type"],
                    "source_id": r["source_id"],
                    "title": r["title"],
                    "snippet": r["content"][:200] if r["content"] else "",
                    "url": r.get("url"),
                    "score": round(r["score"], 3),
                }
                for r in results
            ]
            
            logger.info(f"[RAG] 检索完成: query={context.user_input[:50]}, found={len(results)}")
            
            return ModuleResult.ok(
                data={"found": True, "count": len(results)},
                context=formatted_context,
                sources=sources,
            )
            
        except Exception as e:
            logger.exception(f"[RAG] 检索失败: {e}")
            return ModuleResult.fail(str(e))
    
    def get_config_schema(self) -> Dict[str, Any]:
        """返回配置 schema"""
        return {
            "type": "object",
            "properties": {
                "top_k": {
                    "type": "integer",
                    "title": "返回结果数",
                    "description": "返回前 K 个最相关的结果",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "min_score": {
                    "type": "number",
                    "title": "最小相似度",
                    "description": "低于此阈值的结果将被过滤",
                    "default": 0.3,
                    "minimum": 0,
                    "maximum": 1,
                },
                "max_context_length": {
                    "type": "integer",
                    "title": "最大上下文长度",
                    "description": "注入到 LLM 的上下文最大字符数",
                    "default": 4000,
                },
                "sources": {
                    "type": "array",
                    "title": "知识源",
                    "description": "启用的知识源类型",
                    "items": {
                        "type": "string",
                        "enum": ["note", "bookmark", "file"],
                    },
                    "default": ["note", "bookmark", "file"],
                },
            },
        }
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._embedding_cache.clear()
