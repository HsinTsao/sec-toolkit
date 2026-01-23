"""工具相关 Schema"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


class FavoriteCreate(BaseModel):
    """收藏工具"""
    tool_key: str = Field(..., min_length=1, max_length=100)
    sort_order: int = 0


class FavoriteResponse(BaseModel):
    """收藏响应"""
    id: str
    tool_key: str
    sort_order: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class ToolHistoryCreate(BaseModel):
    """工具历史"""
    tool_key: str = Field(..., min_length=1, max_length=100)
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None


class ToolHistoryResponse(BaseModel):
    """历史响应"""
    id: str
    tool_key: str
    input_data: Optional[Any] = None
    output_data: Optional[Any] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

