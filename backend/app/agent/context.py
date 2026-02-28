"""
Agent 执行上下文

使用 contextvars 存储当前请求的上下文信息，
让工具可以访问用户 ID、数据库会话等。
"""

from contextvars import ContextVar
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    user_id: Optional[str] = None
    db_session: Optional[Any] = None  # AsyncSession
    extra: dict = None
    
    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


# 上下文变量
_agent_context: ContextVar[Optional[AgentContext]] = ContextVar("agent_context", default=None)


def get_agent_context() -> Optional[AgentContext]:
    """获取当前 Agent 上下文"""
    return _agent_context.get()


def set_agent_context(ctx: AgentContext) -> None:
    """设置 Agent 上下文"""
    _agent_context.set(ctx)


def clear_agent_context() -> None:
    """清除 Agent 上下文"""
    _agent_context.set(None)


class AgentContextManager:
    """Agent 上下文管理器，用于 with 语句"""
    
    def __init__(self, user_id: str = None, db_session: Any = None, **extra):
        self.ctx = AgentContext(user_id=user_id, db_session=db_session, extra=extra)
        self._token = None
    
    def __enter__(self):
        self._token = _agent_context.set(self.ctx)
        return self.ctx
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        _agent_context.reset(self._token)
        return False
    
    async def __aenter__(self):
        self._token = _agent_context.set(self.ctx)
        return self.ctx
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        _agent_context.reset(self._token)
        return False
