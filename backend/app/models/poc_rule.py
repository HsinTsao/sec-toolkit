"""PoC 规则模型"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func
import uuid

from ..database import Base


class PocRule(Base):
    """PoC 响应规则"""
    __tablename__ = "poc_rules"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_id = Column(String(36), nullable=False, index=True)  # 关联的 OOB Token
    name = Column(String(50), nullable=False)  # 规则名称（URL 路径）
    description = Column(String(200), nullable=True)  # 描述
    
    # 响应配置
    status_code = Column(Integer, default=200)  # HTTP 状态码
    content_type = Column(String(100), default='text/html')  # Content-Type
    response_body = Column(Text, nullable=True)  # 响应体
    response_headers = Column(JSON, default=dict)  # 额外响应头
    
    # 高级功能
    redirect_url = Column(String(500), nullable=True)  # 重定向 URL（优先于 response_body）
    delay_ms = Column(Integer, default=0)  # 延迟响应（毫秒）
    enable_variables = Column(Integer, default=0)  # 是否启用变量替换
    
    # 元数据
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    hit_count = Column(Integer, default=0)  # 命中次数

