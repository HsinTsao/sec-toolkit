"""回调服务 Schemas"""
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime


# ==================== Token ====================

class TokenCreate(BaseModel):
    name: Optional[str] = None
    expires_hours: Optional[int] = 24
    # 默认回调端点返回时附加的自定义响应头
    response_headers: Optional[Dict[str, str]] = None


class TokenUpdate(BaseModel):
    name: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None


class TokenRenew(BaseModel):
    expires_hours: int = 24


class TokenResponse(BaseModel):
    id: str
    token: str
    name: Optional[str]
    url: str
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    record_count: int = 0
    response_headers: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True


# ==================== Record ====================

class RecordResponse(BaseModel):
    id: str
    token: str
    timestamp: datetime
    client_ip: Optional[str]
    method: Optional[str]
    path: Optional[str]
    query_string: Optional[str]
    headers: Optional[dict]
    body: Optional[str]
    user_agent: Optional[str]
    protocol: str
    raw_request: Optional[str] = None
    is_poc_hit: bool = False
    poc_rule_name: Optional[str] = None
    is_data_exfil: bool = False
    exfil_data: Optional[str] = None
    exfil_type: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== PoC 规则 ====================

class PocRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status_code: int = 200
    content_type: str = 'text/html'
    response_body: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None
    redirect_url: Optional[str] = None
    delay_ms: int = 0
    enable_variables: bool = False
    filename: Optional[str] = None


class PocRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    response_body: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None
    redirect_url: Optional[str] = None
    delay_ms: Optional[int] = None
    enable_variables: Optional[bool] = None
    is_active: Optional[bool] = None
    filename: Optional[str] = None


class PocRuleResponse(BaseModel):
    id: str
    token_id: str
    name: str
    description: Optional[str]
    status_code: int
    content_type: str
    response_body: Optional[str]
    response_headers: Optional[Dict[str, str]]
    redirect_url: Optional[str]
    delay_ms: int
    enable_variables: bool
    is_active: bool
    hit_count: int
    url: str
    filename: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
