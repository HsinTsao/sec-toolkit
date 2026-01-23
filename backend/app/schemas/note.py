"""笔记相关 Schema"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class CategoryCreate(BaseModel):
    """创建分类"""
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0


class CategoryResponse(BaseModel):
    """分类响应"""
    id: str
    name: str
    parent_id: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class TagCreate(BaseModel):
    """创建标签"""
    name: str = Field(..., min_length=1, max_length=50)
    color: str = "#6366f1"


class TagResponse(BaseModel):
    """标签响应"""
    id: str
    name: str
    color: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class NoteCreate(BaseModel):
    """创建笔记"""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = ""
    category_id: Optional[str] = None
    tag_ids: List[str] = []
    is_encrypted: bool = False
    is_pinned: bool = False


class NoteUpdate(BaseModel):
    """更新笔记"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = None
    category_id: Optional[str] = None
    tag_ids: Optional[List[str]] = None
    is_encrypted: Optional[bool] = None
    is_pinned: Optional[bool] = None


class NoteResponse(BaseModel):
    """笔记响应"""
    id: str
    title: str
    content: str
    category_id: Optional[str] = None
    is_encrypted: bool
    is_pinned: bool
    created_at: datetime
    updated_at: datetime
    tags: List[TagResponse] = []
    
    class Config:
        from_attributes = True

