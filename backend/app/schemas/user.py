"""用户相关 Schema"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, Any
import json


class UserCreate(BaseModel):
    """用户注册"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    """用户登录"""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """用户更新"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    avatar: Optional[str] = None
    settings: Optional[dict] = None


class UserResponse(BaseModel):
    """用户响应"""
    id: str
    email: str
    username: str
    avatar: Optional[str] = None
    is_active: bool
    settings: dict = {}
    created_at: datetime
    
    @field_validator('settings', mode='before')
    @classmethod
    def parse_settings(cls, v: Any) -> dict:
        """将 JSON 字符串转换为字典"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        if v is None:
            return {}
        return v
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """Token 响应"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求"""
    refresh_token: str


class TokenPayload(BaseModel):
    """Token 载荷"""
    sub: str  # user_id
    exp: datetime
    type: str  # access 或 refresh

