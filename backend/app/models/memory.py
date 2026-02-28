"""用户长期记忆模型"""
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..database import Base


class UserMemory(Base):
    """用户长期记忆表
    
    存储 AI 从对话中提取的用户偏好、事实等信息
    """
    __tablename__ = "user_memories"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 记忆内容
    content = Column(Text, nullable=False)  # 记忆的具体内容
    category = Column(String(50), default="general")  # 分类：preference/fact/instruction/general
    
    # 元数据
    source = Column(Text, nullable=True)  # 原始对话片段（用于追溯）
    importance = Column(Float, default=1.0)  # 重要性评分 0-1
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)  # 最后被检索/使用的时间
    
    # 关系
    user = relationship("User", backref="memories")
    
    # 索引
    __table_args__ = (
        Index("idx_memory_user_category", "user_id", "category"),
        Index("idx_memory_created", "created_at"),
    )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "source": self.source,
            "importance": self.importance,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_accessed_at": self.last_accessed_at.isoformat() if self.last_accessed_at else None,
        }
    
    def __repr__(self):
        return f"<UserMemory {self.id[:8]}... [{self.category}]: {self.content[:30]}...>"


# 记忆分类常量
class MemoryCategory:
    PREFERENCE = "preference"  # 用户偏好，如"喜欢简洁回复"
    FACT = "fact"              # 用户相关事实，如"从事量化交易"
    INSTRUCTION = "instruction"  # 用户指令，如"以后回复用英文"
    GENERAL = "general"        # 通用记忆
    
    ALL = [PREFERENCE, FACT, INSTRUCTION, GENERAL]
