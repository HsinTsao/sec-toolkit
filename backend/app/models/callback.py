"""回调记录模型"""
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func
import uuid

from ..database import Base


class CallbackToken(Base):
    """回调 Token"""
    __tablename__ = "callback_tokens"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token = Column(String(32), unique=True, index=True, nullable=False)  # 短 token，用于 URL
    name = Column(String(100), nullable=True)  # 用户备注名称
    user_id = Column(String(36), nullable=False, index=True)  # 所属用户
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # 过期时间
    is_active = Column(Integer, default=1)  # 是否激活


class CallbackRecord(Base):
    """回调记录"""
    __tablename__ = "callback_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_id = Column(String(36), nullable=False, index=True)  # 关联的 token
    token = Column(String(32), nullable=False, index=True)  # 冗余存储 token
    
    # 请求信息
    timestamp = Column(DateTime, server_default=func.now())
    client_ip = Column(String(45), nullable=True)  # 支持 IPv6
    method = Column(String(10), nullable=True)
    path = Column(String(500), nullable=True)  # 完整请求路径
    query_string = Column(Text, nullable=True)  # 查询参数
    
    # 请求头和请求体
    headers = Column(JSON, nullable=True)
    body = Column(Text, nullable=True)
    
    # User-Agent 单独存储便于查询
    user_agent = Column(String(500), nullable=True)
    
    # 额外信息
    protocol = Column(String(10), default='HTTP')  # HTTP/HTTPS/DNS 等
    raw_request = Column(Text, nullable=True)  # 原始请求
    
    # PoC 相关字段
    is_poc_hit = Column(Integer, default=0)  # 是否命中 PoC 规则路径
    poc_rule_name = Column(String(50), nullable=True)  # 命中的 PoC 规则名
    is_data_exfil = Column(Integer, default=0)  # 是否有数据外带（证明攻击成功）
    exfil_data = Column(Text, nullable=True)  # 外带的数据内容
    exfil_type = Column(String(50), nullable=True)  # 外带数据类型（cookie/file/cmd/custom）

