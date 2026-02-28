"""记忆相关的 Pydantic Schema"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class MemoryCreate(BaseModel):
    """创建记忆的请求"""
    content: str = Field(..., min_length=1, max_length=2000, description="记忆内容")
    category: str = Field(default="general", description="分类: preference/fact/instruction/general")
    source: Optional[str] = Field(default=None, description="原始对话片段")
    importance: float = Field(default=1.0, ge=0, le=1, description="重要性 0-1")


class MemoryUpdate(BaseModel):
    """更新记忆的请求"""
    content: Optional[str] = Field(None, min_length=1, max_length=2000)
    category: Optional[str] = None
    importance: Optional[float] = Field(None, ge=0, le=1)


class MemoryResponse(BaseModel):
    """单条记忆的响应"""
    id: str
    content: str
    category: str
    source: Optional[str]
    importance: float
    created_at: datetime
    last_accessed_at: datetime
    
    class Config:
        from_attributes = True


class MemoryListResponse(BaseModel):
    """记忆列表响应"""
    memories: List[MemoryResponse]
    total: int
    
    
class MemoryStats(BaseModel):
    """记忆统计信息"""
    total: int
    by_category: dict  # {"preference": 5, "fact": 3, ...}
