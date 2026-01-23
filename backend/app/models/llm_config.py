"""用户 LLM 配置模型"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..database import Base


class UserLLMConfig(Base):
    """用户 LLM 配置表"""
    __tablename__ = "user_llm_configs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    
    # LLM 配置
    provider_id = Column(String(50), nullable=False, default="deepseek")  # openai, groq, deepseek, etc.
    api_key = Column(Text, nullable=True)  # 加密存储
    base_url = Column(String(500), nullable=True)  # 自定义 API 地址
    model = Column(String(100), nullable=False, default="deepseek-chat")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", backref="llm_config")

