"""书签相关 Schema"""
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from typing import Optional


class BookmarkCreate(BaseModel):
    """创建书签"""
    title: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=2000)
    icon: Optional[str] = None
    category: Optional[str] = None
    sort_order: int = 0


class BookmarkUpdate(BaseModel):
    """更新书签"""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1, max_length=2000)
    icon: Optional[str] = None
    category: Optional[str] = None
    sort_order: Optional[int] = None


class BookmarkResponse(BaseModel):
    """书签响应"""
    id: str
    title: str
    url: str
    icon: Optional[str] = None
    category: Optional[str] = None
    sort_order: int
    created_at: datetime
    
    class Config:
        from_attributes = True

