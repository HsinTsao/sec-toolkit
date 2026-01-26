"""
Agent 审计日志服务

记录 AI Agent 的每一步操作，包括：
- 用户消息
- LLM 请求/响应
- 工具调用/结果
- RAG 检索
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid
import time
import logging
import json

from ..models.audit_log import AgentSession, AuditLog, AuditEventType

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Agent 审计日志记录器
    
    使用示例:
        async with AuditLogger(db, user_id) as audit:
            # 开始会话
            await audit.start_session(message="用户问题", model="gpt-4")
            
            # 记录用户消息
            await audit.log_user_message("你好")
            
            # 记录 LLM 响应
            await audit.log_llm_response("你好！有什么可以帮助你的？")
            
            # 记录工具调用
            await audit.log_tool_call("base64_encode", {"text": "hello"})
            await audit.log_tool_result("base64_encode", {"success": True, "data": "aGVsbG8="})
    """
    
    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id
        self.session: Optional[AgentSession] = None
        self.event_order = 0
        self._start_time: Optional[float] = None
    
    async def __aenter__(self) -> "AuditLogger":
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type:
                await self.end_session(status="error", error=str(exc_val))
            else:
                await self.end_session(status="completed")
    
    async def start_session(
        self,
        message: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        use_tools: bool = True,
        use_knowledge: bool = False,
    ) -> str:
        """
        开始一个新的 Agent 会话
        
        Returns:
            session_id: 会话 ID
        """
        self.session = AgentSession(
            user_id=self.user_id,
            initial_message=message[:500] if message else None,  # 截断过长的消息
            model=model,
            provider=provider,
            use_tools=1 if use_tools else 0,
            use_knowledge=1 if use_knowledge else 0,
            status="active",
        )
        self.db.add(self.session)
        await self.db.flush()
        
        # 记录会话开始事件
        await self._log(
            event_type=AuditEventType.SESSION_START,
            content=message,
            extra_data={
                "model": model,
                "provider": provider,
                "use_tools": use_tools,
                "use_knowledge": use_knowledge,
            }
        )
        
        logger.info(f"🎬 [Audit] 会话开始: {self.session.id}")
        return self.session.id
    
    async def end_session(
        self,
        status: str = "completed",
        error: Optional[str] = None,
    ):
        """结束会话"""
        if not self.session:
            return
        
        self.session.status = status
        self.session.ended_at = datetime.utcnow()
        if error:
            self.session.error_message = error[:1000]
        
        await self._log(
            event_type=AuditEventType.SESSION_END,
            extra_data={
                "status": status,
                "message_count": self.session.message_count,
                "tool_call_count": self.session.tool_call_count,
            },
            success=status == "completed",
            error_message=error,
        )
        
        await self.db.flush()
        logger.info(f"🎬 [Audit] 会话结束: {self.session.id}, 状态: {status}")
    
    async def log_user_message(self, message: str) -> str:
        """记录用户消息"""
        if self.session:
            self.session.message_count += 1
        
        log = await self._log(
            event_type=AuditEventType.USER_MESSAGE,
            content=message,
        )
        
        logger.debug(f"📝 [Audit] 用户消息: {message[:100]}...")
        return log.id
    
    async def log_llm_request(
        self,
        messages: List[Dict],
        tools: Optional[List] = None,
    ) -> str:
        """记录 LLM 请求"""
        self._start_time = time.time()
        
        log = await self._log(
            event_type=AuditEventType.LLM_REQUEST,
            content=json.dumps(messages[-1], ensure_ascii=False) if messages else None,
            extra_data={
                "message_count": len(messages),
                "has_tools": bool(tools),
                "tool_count": len(tools) if tools else 0,
            }
        )
        
        return log.id
    
    async def log_llm_response(
        self,
        content: str,
        tokens_used: Optional[int] = None,
        has_tool_calls: bool = False,
    ) -> str:
        """记录 LLM 响应"""
        duration_ms = None
        if self._start_time:
            duration_ms = int((time.time() - self._start_time) * 1000)
            self._start_time = None
        
        if self.session and tokens_used:
            self.session.total_tokens += tokens_used
        
        log = await self._log(
            event_type=AuditEventType.LLM_RESPONSE,
            content=content[:5000] if content else None,  # 截断过长的响应
            extra_data={
                "has_tool_calls": has_tool_calls,
            },
            duration_ms=duration_ms,
            tokens_used=tokens_used,
        )
        
        logger.debug(f"🤖 [Audit] LLM 响应: {content[:100] if content else '(empty)'}...")
        return log.id
    
    async def log_llm_error(self, error: str) -> str:
        """记录 LLM 错误"""
        duration_ms = None
        if self._start_time:
            duration_ms = int((time.time() - self._start_time) * 1000)
            self._start_time = None
        
        log = await self._log(
            event_type=AuditEventType.LLM_ERROR,
            error_message=error,
            success=False,
            duration_ms=duration_ms,
        )
        
        logger.warning(f"❌ [Audit] LLM 错误: {error}")
        return log.id
    
    async def log_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        call_id: Optional[str] = None,
    ) -> str:
        """记录工具调用"""
        if self.session:
            self.session.tool_call_count += 1
        
        self._start_time = time.time()
        
        log = await self._log(
            event_type=AuditEventType.TOOL_CALL,
            tool_name=tool_name,
            tool_arguments=arguments,
            extra_data={"call_id": call_id},
        )
        
        logger.info(f"🔧 [Audit] 工具调用: {tool_name}({arguments})")
        return log.id
    
    async def log_tool_result(
        self,
        tool_name: str,
        result: Dict[str, Any],
        success: bool = True,
    ) -> str:
        """记录工具执行结果"""
        duration_ms = None
        if self._start_time:
            duration_ms = int((time.time() - self._start_time) * 1000)
            self._start_time = None
        
        # 截断过大的结果
        result_str = json.dumps(result, ensure_ascii=False)
        if len(result_str) > 10000:
            result = {"truncated": True, "preview": result_str[:1000]}
        
        log = await self._log(
            event_type=AuditEventType.TOOL_RESULT if success else AuditEventType.TOOL_ERROR,
            tool_name=tool_name,
            tool_result=result,
            success=success,
            duration_ms=duration_ms,
        )
        
        status = "✅" if success else "❌"
        logger.info(f"{status} [Audit] 工具结果: {tool_name} -> success={success}")
        return log.id
    
    async def log_rag_search(
        self,
        query: str,
        source_types: List[str],
    ) -> str:
        """记录 RAG 检索"""
        self._start_time = time.time()
        
        log = await self._log(
            event_type=AuditEventType.RAG_SEARCH,
            content=query,
            extra_data={"source_types": source_types},
        )
        
        logger.debug(f"🔍 [Audit] RAG 检索: {query[:100]}...")
        return log.id
    
    async def log_rag_result(
        self,
        results: List[Dict],
        sources: List[str],
    ) -> str:
        """记录 RAG 检索结果"""
        duration_ms = None
        if self._start_time:
            duration_ms = int((time.time() - self._start_time) * 1000)
            self._start_time = None
        
        log = await self._log(
            event_type=AuditEventType.RAG_RESULT,
            extra_data={
                "result_count": len(results),
                "sources": sources,
            },
            duration_ms=duration_ms,
        )
        
        logger.debug(f"📚 [Audit] RAG 结果: {len(results)} 条")
        return log.id
    
    async def _log(
        self,
        event_type: AuditEventType,
        content: Optional[str] = None,
        extra_data: Optional[Dict] = None,
        tool_name: Optional[str] = None,
        tool_arguments: Optional[Dict] = None,
        tool_result: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AuditLog:
        """内部日志记录方法"""
        self.event_order += 1
        
        log = AuditLog(
            session_id=self.session.id if self.session else str(uuid.uuid4()),
            user_id=self.user_id,
            event_type=event_type.value,
            event_order=self.event_order,
            content=content,
            extra_data=extra_data,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            tool_result=tool_result,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            success=1 if success else 0,
            error_message=error_message,
        )
        
        self.db.add(log)
        await self.db.flush()
        
        return log


# ==================== 查询函数 ====================

async def get_user_sessions(
    db: AsyncSession,
    user_id: str,
    limit: int = 50,
    offset: int = 0,
) -> List[AgentSession]:
    """获取用户的会话列表"""
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.user_id == user_id)
        .order_by(desc(AgentSession.started_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_session_logs(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> List[AuditLog]:
    """获取会话的所有日志"""
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.session_id == session_id,
            AuditLog.user_id == user_id,
        )
        .order_by(AuditLog.event_order)
    )
    return list(result.scalars().all())


async def get_session_detail(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> Optional[AgentSession]:
    """获取会话详情"""
    result = await db.execute(
        select(AgentSession)
        .where(
            AgentSession.id == session_id,
            AgentSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_user_stats(
    db: AsyncSession,
    user_id: str,
) -> Dict[str, Any]:
    """获取用户的 Agent 使用统计"""
    from sqlalchemy import func
    
    # 会话统计
    session_result = await db.execute(
        select(
            func.count(AgentSession.id).label("total_sessions"),
            func.sum(AgentSession.message_count).label("total_messages"),
            func.sum(AgentSession.tool_call_count).label("total_tool_calls"),
            func.sum(AgentSession.total_tokens).label("total_tokens"),
        )
        .where(AgentSession.user_id == user_id)
    )
    session_stats = session_result.first()
    
    # 工具使用统计
    tool_result = await db.execute(
        select(
            AuditLog.tool_name,
            func.count().label("count")
        )
        .where(
            AuditLog.user_id == user_id,
            AuditLog.event_type == AuditEventType.TOOL_CALL.value,
            AuditLog.tool_name.isnot(None),
        )
        .group_by(AuditLog.tool_name)
        .order_by(desc(func.count()))
        .limit(10)
    )
    tool_stats = [{"tool": row[0], "count": row[1]} for row in tool_result.all()]
    
    return {
        "total_sessions": session_stats[0] or 0,
        "total_messages": session_stats[1] or 0,
        "total_tool_calls": session_stats[2] or 0,
        "total_tokens": session_stats[3] or 0,
        "top_tools": tool_stats,
    }

