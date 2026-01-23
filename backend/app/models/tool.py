"""工具相关模型"""
from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..database import Base


class Favorite(Base):
    """收藏工具表"""
    __tablename__ = "favorites"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tool_key = Column(String(100), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="favorites")
    
    # 联合唯一约束
    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class ToolHistory(Base):
    """工具使用历史表"""
    __tablename__ = "tool_history"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tool_key = Column(String(100), nullable=False)
    input_data = Column(Text, nullable=True)  # JSON 字符串
    output_data = Column(Text, nullable=True)  # JSON 字符串
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="tool_history")

