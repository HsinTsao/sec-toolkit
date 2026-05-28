"""PoC 访问日志模型"""
import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON
from sqlalchemy.sql import func

from ..database import Base


class PocAccessLog(Base):
    __tablename__ = "poc_access_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    poc_name = Column(String(100), nullable=False, index=True)
    client_ip = Column(String(50))
    method = Column(String(10))
    path = Column(String(500))
    query_string = Column(Text)
    headers = Column(JSON)
    body = Column(Text)
    user_agent = Column(String(500))
    timestamp = Column(DateTime, server_default=func.now(), index=True)
