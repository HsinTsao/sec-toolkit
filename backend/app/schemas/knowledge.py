"""知识库相关 Schema"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


# ==================== 文件上传 ====================

class FileUploadResponse(BaseModel):
    """文件上传响应"""
    id: str
    filename: str
    original_name: str
    file_type: str
    file_size: int
    content_preview: Optional[str] = None  # 内容预览（前500字符）
    created_at: datetime
    
    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """文件列表响应"""
    id: str
    original_name: str
    file_type: str
    file_size: int
    note_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class FileToNoteRequest(BaseModel):
    """文件转存为笔记请求"""
    title: Optional[str] = None  # 不传则使用文件名
    category_id: Optional[str] = None


# ==================== 知识库条目 ====================

class KnowledgeItemCreate(BaseModel):
    """创建知识条目"""
    source_type: Literal["note", "bookmark", "file"]
    source_id: str


class KnowledgeItemResponse(BaseModel):
    """知识条目响应"""
    id: str
    source_type: str
    source_id: str
    title: str
    summary: Optional[str] = None  # 摘要
    content_preview: Optional[str] = None  # 内容预览
    url: Optional[str] = None
    is_enabled: bool
    has_summary: bool = False
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class KnowledgeItemUpdate(BaseModel):
    """更新知识条目"""
    is_enabled: Optional[bool] = None
    summary: Optional[str] = None  # 用户可编辑摘要


class GenerateSummaryRequest(BaseModel):
    """生成摘要请求"""
    item_ids: List[str] = Field(..., description="要生成摘要的知识条目ID列表")


class GenerateSummaryResponse(BaseModel):
    """生成摘要响应"""
    success: int
    failed: int
    results: List[dict]


class KnowledgeSyncRequest(BaseModel):
    """同步知识库请求"""
    sync_notes: bool = True
    sync_bookmarks: bool = True
    sync_files: bool = True


class KnowledgeSyncResponse(BaseModel):
    """同步知识库响应"""
    added: int
    updated: int
    removed: int


# ==================== 知识库搜索 ====================

class KnowledgeSearchResult(BaseModel):
    """知识库搜索结果"""
    id: str
    source_type: str
    source_id: str
    title: str
    content_snippet: str  # 匹配的内容片段
    url: Optional[str] = None
    relevance: float = 1.0  # 相关性分数
    
    class Config:
        from_attributes = True


# ==================== RAG 聊天增强 ====================

class RAGChatRequest(BaseModel):
    """RAG 增强聊天请求"""
    message: str = Field(..., description="用户消息")
    history: List[dict] = Field(default=[], description="对话历史")
    use_knowledge: bool = Field(default=True, description="是否使用知识库")
    knowledge_sources: List[Literal["note", "bookmark", "file"]] = Field(
        default=["note", "bookmark", "file"],
        description="知识来源类型"
    )
    max_results: int = Field(default=5, description="最大检索结果数")


class RAGSource(BaseModel):
    """RAG 引用来源"""
    source_type: str
    source_id: str
    title: str
    snippet: str
    url: Optional[str] = None


class RAGChatResponse(BaseModel):
    """RAG 增强聊天响应"""
    content: str
    sources: List[RAGSource] = []

