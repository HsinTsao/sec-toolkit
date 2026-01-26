"""Agent 审计日志模型"""
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from ..database import Base


class AuditEventType(str, enum.Enum):
    """审计事件类型"""
    # 会话事件
    SESSION_START = "session_start"      # 会话开始
    SESSION_END = "session_end"          # 会话结束
    
    # 用户事件
    USER_MESSAGE = "user_message"        # 用户消息
    
    # LLM 事件
    LLM_REQUEST = "llm_request"          # LLM 请求
    LLM_RESPONSE = "llm_response"        # LLM 响应（文本）
    LLM_ERROR = "llm_error"              # LLM 错误
    
    # 工具事件
    TOOL_CALL = "tool_call"              # 工具调用请求
    TOOL_RESULT = "tool_result"          # 工具执行结果
    TOOL_ERROR = "tool_error"            # 工具执行错误
    
    # RAG 事件
    RAG_SEARCH = "rag_search"            # RAG 知识库检索
    RAG_RESULT = "rag_result"            # RAG 检索结果


class AgentSession(Base):
    """Agent 会话表"""
    __tablename__ = "agent_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 会话信息
    initial_message = Column(Text, nullable=True)  # 初始消息摘要
    model = Column(String(100), nullable=True)     # 使用的模型
    provider = Column(String(50), nullable=True)   # 提供商
    
    # 统计信息
    message_count = Column(Integer, default=0)     # 消息数
    tool_call_count = Column(Integer, default=0)   # 工具调用数
    total_tokens = Column(Integer, default=0)      # 总 token 数（如果有）
    
    # 配置
    use_tools = Column(Integer, default=1)         # 是否启用工具
    use_knowledge = Column(Integer, default=0)     # 是否使用知识库
    
    # 状态
    status = Column(String(20), default="active")  # active, completed, error
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    
    # 关系
    user = relationship("User", backref="agent_sessions")
    logs = relationship("AuditLog", back_populates="session", cascade="all, delete-orphan")


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 事件信息
    event_type = Column(String(50), nullable=False)  # AuditEventType
    event_order = Column(Integer, nullable=False)    # 事件顺序（在会话中的序号）
    
    # 事件详情
    content = Column(Text, nullable=True)            # 主要内容（消息/结果等）
    extra_data = Column(JSON, nullable=True)         # 额外元数据
    
    # 工具相关（仅工具事件）
    tool_name = Column(String(100), nullable=True)
    tool_arguments = Column(JSON, nullable=True)
    tool_result = Column(JSON, nullable=True)
    
    # 性能指标
    duration_ms = Column(Integer, nullable=True)     # 执行耗时（毫秒）
    tokens_used = Column(Integer, nullable=True)     # token 使用量
    
    # 状态
    success = Column(Integer, default=1)             # 1=成功, 0=失败
    error_message = Column(Text, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    session = relationship("AgentSession", back_populates="logs")
    user = relationship("User", backref="audit_logs")

