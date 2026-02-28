"""
用户自定义 Skill 模型
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, JSON, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class UserSkill(Base):
    """用户自定义 Skill"""
    __tablename__ = "user_skills"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 基本信息
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    icon = Column(String(10), default="🔧")
    category = Column(String(50), default="custom")
    
    # 核心配置
    system_prompt = Column(Text, nullable=False)
    tools = Column(JSON, default=list)  # 工具白名单，空列表=全部工具可用
    
    # 用户体验
    welcome_message = Column(Text, default="")
    example_prompts = Column(JSON, default=list)  # 示例提问
    
    # 限制
    max_tool_calls = Column(Integer, default=10)
    
    # 状态
    enabled = Column(Boolean, default=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", backref="skills")
    
    def to_skill(self):
        """转换为 Skill 对象"""
        from ..agent.skill import Skill, SkillCategory
        
        try:
            category = SkillCategory(self.category)
        except ValueError:
            category = SkillCategory.CUSTOM
        
        return Skill(
            id=self.id,
            name=self.name,
            description=self.description or "",
            icon=self.icon or "🔧",
            category=category,
            system_prompt=self.system_prompt,
            tools=self.tools or [],
            welcome_message=self.welcome_message or "",
            example_prompts=self.example_prompts or [],
            max_tool_calls=self.max_tool_calls or 10,
            is_builtin=False,
            enabled=self.enabled,
        )
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category,
            "system_prompt": self.system_prompt,
            "tools": self.tools or [],
            "welcome_message": self.welcome_message,
            "example_prompts": self.example_prompts or [],
            "max_tool_calls": self.max_tool_calls,
            "enabled": self.enabled,
            "is_builtin": False,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
