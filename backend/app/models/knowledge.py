"""知识库相关模型"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..database import Base


class UploadedFile(Base):
    """上传文件表"""
    __tablename__ = "uploaded_files"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 文件信息
    filename = Column(String(255), nullable=False)  # 存储的文件名
    original_name = Column(String(255), nullable=False)  # 原始文件名
    file_type = Column(String(50), nullable=False)  # pdf, txt, md, docx
    file_size = Column(Integer, nullable=False)  # 文件大小（字节）
    file_path = Column(String(500), nullable=False)  # 存储路径
    
    # 解析后的内容
    content_text = Column(Text, nullable=True)  # 解析后的文本内容
    
    # 关联笔记（如果转存为笔记）
    note_id = Column(String(36), ForeignKey("notes.id", ondelete="SET NULL"), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", backref="uploaded_files")
    note = relationship("Note", backref="source_file")


class KnowledgeItem(Base):
    """知识库条目表 - 统一索引笔记/书签/文件"""
    __tablename__ = "knowledge_items"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 来源信息
    source_type = Column(String(20), nullable=False)  # note, bookmark, file
    source_id = Column(String(36), nullable=False)  # 对应的笔记/书签/文件ID
    
    # 内容信息
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)  # AI 生成或用户编辑的摘要
    content = Column(Text, nullable=True)  # 完整内容（用于全文搜索）
    url = Column(String(2000), nullable=True)  # 书签的 URL
    
    # 状态
    is_enabled = Column(Boolean, default=True)  # 是否启用
    has_summary = Column(Boolean, default=False)  # 是否有摘要
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", backref="knowledge_items")

