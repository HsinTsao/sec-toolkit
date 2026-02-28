"""
Skill 相关的 Pydantic Schema
"""

from typing import Optional
from pydantic import BaseModel, Field


class SkillBase(BaseModel):
    """Skill 基础字段"""
    name: str = Field(..., min_length=1, max_length=100, description="Skill 名称")
    description: str = Field(default="", max_length=500, description="描述")
    icon: str = Field(default="🔧", max_length=10, description="图标（emoji）")
    category: str = Field(default="custom", description="分类")
    system_prompt: str = Field(..., min_length=1, description="System Prompt")
    tools: list[str] = Field(default=[], description="工具白名单（空=全部可用）")
    welcome_message: str = Field(default="", max_length=500, description="欢迎语")
    example_prompts: list[str] = Field(default=[], description="示例提问")
    max_tool_calls: int = Field(default=10, ge=1, le=50, description="单次最大工具调用")


class SkillCreate(SkillBase):
    """创建 Skill"""
    pass


class SkillUpdate(BaseModel):
    """更新 Skill"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    icon: Optional[str] = Field(None, max_length=10)
    category: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    tools: Optional[list[str]] = None
    welcome_message: Optional[str] = Field(None, max_length=500)
    example_prompts: Optional[list[str]] = None
    max_tool_calls: Optional[int] = Field(None, ge=1, le=50)
    enabled: Optional[bool] = None


class SkillResponse(SkillBase):
    """Skill 响应"""
    id: str
    is_builtin: bool = False
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class SkillListItem(BaseModel):
    """Skill 列表项"""
    id: str
    name: str
    description: str
    icon: str
    category: str
    is_builtin: bool
    enabled: bool
    tools_count: int


class SkillListResponse(BaseModel):
    """Skill 列表响应"""
    builtin: list[SkillListItem]
    custom: list[SkillListItem]
