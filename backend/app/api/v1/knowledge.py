"""知识库管理 API"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_, func
from typing import List, Optional
import os
import uuid
import aiofiles
from datetime import datetime
import httpx

from ...database import get_db
from ...models import User, Note, Bookmark, UploadedFile, KnowledgeItem
from ...schemas.knowledge import (
    FileUploadResponse,
    FileListResponse,
    FileToNoteRequest,
    KnowledgeItemCreate,
    KnowledgeItemResponse,
    KnowledgeItemUpdate,
    KnowledgeSyncRequest,
    KnowledgeSyncResponse,
    KnowledgeSearchResult,
    GenerateSummaryRequest,
    GenerateSummaryResponse,
)
from ...models import UserLLMConfig
from ...utils import fetch_webpage_meta, build_summary_from_meta, SSRFError
from ..deps import get_current_user

router = APIRouter(prefix="/knowledge", tags=["知识库"])

# 文件上传目录
UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# 支持的文件类型
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


# ==================== 文件解析工具 ====================

async def parse_file_content(file_path: str, file_type: str) -> str:
    """解析文件内容为纯文本"""
    content = ""
    
    try:
        if file_type in ["txt", "md"]:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
        
        elif file_type == "pdf":
            # 使用 PyMuPDF 解析 PDF
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(file_path)
                for page in doc:
                    content += page.get_text()
                doc.close()
            except ImportError:
                content = "[PDF 解析需要安装 PyMuPDF: pip install PyMuPDF]"
        
        elif file_type == "docx":
            # 使用 python-docx 解析 Word
            try:
                from docx import Document
                doc = Document(file_path)
                content = "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                content = "[DOCX 解析需要安装 python-docx: pip install python-docx]"
    
    except Exception as e:
        content = f"[文件解析失败: {str(e)}]"
    
    return content


# ==================== 文件上传 API ====================

@router.post("/files/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    auto_add_knowledge: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传文件"""
    # 检查文件扩展名
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型。支持: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # 检查文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件过大，最大支持 {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
    
    # 生成唯一文件名
    file_id = str(uuid.uuid4())
    filename = f"{file_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # 保存文件
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)
    
    # 解析文件内容
    file_type = ext[1:]  # 去掉点号
    content_text = await parse_file_content(file_path, file_type)
    
    # 创建数据库记录
    uploaded_file = UploadedFile(
        id=file_id,
        user_id=current_user.id,
        filename=filename,
        original_name=file.filename,
        file_type=file_type,
        file_size=len(content),
        file_path=file_path,
        content_text=content_text,
    )
    db.add(uploaded_file)
    await db.flush()
    
    # 自动添加到知识库
    if auto_add_knowledge and content_text:
        knowledge_item = KnowledgeItem(
            user_id=current_user.id,
            source_type="file",
            source_id=file_id,
            title=file.filename,
            content=content_text,
        )
        db.add(knowledge_item)
    
    return FileUploadResponse(
        id=uploaded_file.id,
        filename=uploaded_file.filename,
        original_name=uploaded_file.original_name,
        file_type=uploaded_file.file_type,
        file_size=uploaded_file.file_size,
        content_preview=content_text[:500] if content_text else None,
        created_at=uploaded_file.created_at,
    )


@router.get("/files", response_model=List[FileListResponse])
async def list_files(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文件列表"""
    result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.user_id == current_user.id)
        .order_by(UploadedFile.created_at.desc())
    )
    files = result.scalars().all()
    return files


@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取文件详情"""
    result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.id == file_id, UploadedFile.user_id == current_user.id)
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return {
        "id": file.id,
        "original_name": file.original_name,
        "file_type": file.file_type,
        "file_size": file.file_size,
        "content_text": file.content_text,
        "note_id": file.note_id,
        "created_at": file.created_at,
    }


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除文件"""
    result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.id == file_id, UploadedFile.user_id == current_user.id)
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 删除物理文件
    if os.path.exists(file.file_path):
        os.remove(file.file_path)
    
    # 删除知识库条目
    await db.execute(
        delete(KnowledgeItem)
        .where(KnowledgeItem.source_type == "file", KnowledgeItem.source_id == file_id)
    )
    
    # 删除数据库记录
    await db.delete(file)
    
    return {"message": "文件已删除"}


@router.post("/files/{file_id}/to-note")
async def file_to_note(
    file_id: str,
    request: FileToNoteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """将文件转存为笔记"""
    result = await db.execute(
        select(UploadedFile)
        .where(UploadedFile.id == file_id, UploadedFile.user_id == current_user.id)
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if not file.content_text:
        raise HTTPException(status_code=400, detail="文件内容为空，无法转存")
    
    # 创建笔记
    title = request.title or os.path.splitext(file.original_name)[0]
    note = Note(
        user_id=current_user.id,
        category_id=request.category_id,
        title=title,
        content=file.content_text,
    )
    db.add(note)
    await db.flush()
    
    # 关联文件
    file.note_id = note.id
    
    # 更新知识库条目
    ki_result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.source_type == "file", KnowledgeItem.source_id == file_id)
    )
    knowledge_item = ki_result.scalar_one_or_none()
    if knowledge_item:
        # 将来源改为笔记
        knowledge_item.source_type = "note"
        knowledge_item.source_id = note.id
        knowledge_item.title = title
    
    return {
        "message": "已转存为笔记",
        "note_id": note.id,
        "title": title,
    }


# ==================== 知识库管理 API ====================

@router.get("/items", response_model=List[KnowledgeItemResponse])
async def list_knowledge_items(
    source_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取知识库条目列表"""
    query = select(KnowledgeItem).where(KnowledgeItem.user_id == current_user.id)
    
    if source_type:
        query = query.where(KnowledgeItem.source_type == source_type)
    
    query = query.order_by(KnowledgeItem.updated_at.desc())
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    # 添加内容预览
    response = []
    for item in items:
        response.append(KnowledgeItemResponse(
            id=item.id,
            source_type=item.source_type,
            source_id=item.source_id,
            title=item.title,
            summary=item.summary,
            content_preview=item.content[:200] + "..." if item.content and len(item.content) > 200 else item.content,
            url=item.url,
            is_enabled=item.is_enabled,
            has_summary=item.has_summary or False,
            created_at=item.created_at,
            updated_at=item.updated_at,
        ))
    
    return response


@router.post("/items", response_model=KnowledgeItemResponse)
async def add_knowledge_item(
    request: KnowledgeItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """手动添加知识条目"""
    # 检查是否已存在
    existing = await db.execute(
        select(KnowledgeItem)
        .where(
            KnowledgeItem.user_id == current_user.id,
            KnowledgeItem.source_type == request.source_type,
            KnowledgeItem.source_id == request.source_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该条目已在知识库中")
    
    # 获取源数据
    title = ""
    content = ""
    url = None
    
    if request.source_type == "note":
        result = await db.execute(
            select(Note).where(Note.id == request.source_id, Note.user_id == current_user.id)
        )
        note = result.scalar_one_or_none()
        if not note:
            raise HTTPException(status_code=404, detail="笔记不存在")
        title = note.title
        content = note.content
    
    elif request.source_type == "bookmark":
        result = await db.execute(
            select(Bookmark).where(Bookmark.id == request.source_id, Bookmark.user_id == current_user.id)
        )
        bookmark = result.scalar_one_or_none()
        if not bookmark:
            raise HTTPException(status_code=404, detail="书签不存在")
        title = bookmark.title
        url = bookmark.url
        # 书签暂时只存标题和URL，后续可以抓取网页内容
    
    elif request.source_type == "file":
        result = await db.execute(
            select(UploadedFile).where(UploadedFile.id == request.source_id, UploadedFile.user_id == current_user.id)
        )
        file = result.scalar_one_or_none()
        if not file:
            raise HTTPException(status_code=404, detail="文件不存在")
        title = file.original_name
        content = file.content_text
    
    else:
        raise HTTPException(status_code=400, detail="不支持的来源类型")
    
    # 创建知识条目
    item = KnowledgeItem(
        user_id=current_user.id,
        source_type=request.source_type,
        source_id=request.source_id,
        title=title,
        content=content,
        url=url,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)
    
    return KnowledgeItemResponse(
        id=item.id,
        source_type=item.source_type,
        source_id=item.source_id,
        title=item.title,
        content_preview=item.content[:200] + "..." if item.content and len(item.content) > 200 else item.content,
        url=item.url,
        is_enabled=item.is_enabled,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.patch("/items/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    item_id: str,
    request: KnowledgeItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新知识条目（启用/禁用、编辑摘要）"""
    result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id, KnowledgeItem.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    
    if request.is_enabled is not None:
        item.is_enabled = request.is_enabled
    
    if request.summary is not None:
        item.summary = request.summary
        item.has_summary = bool(request.summary.strip())
    
    await db.flush()
    await db.refresh(item)
    
    return KnowledgeItemResponse(
        id=item.id,
        source_type=item.source_type,
        source_id=item.source_id,
        title=item.title,
        summary=item.summary,
        content_preview=item.content[:200] + "..." if item.content and len(item.content) > 200 else item.content,
        url=item.url,
        is_enabled=item.is_enabled,
        has_summary=item.has_summary or False,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.delete("/items/{item_id}")
async def delete_knowledge_item(
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除知识条目"""
    result = await db.execute(
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id, KnowledgeItem.user_id == current_user.id)
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="知识条目不存在")
    
    await db.delete(item)
    
    return {"message": "知识条目已删除"}


# ==================== Summary 生成 ====================

SUMMARY_PROMPT = """请为以下内容生成一个专业的摘要，参考学术论文摘要的写作风格。

要求：
1. 概述文章主题：说明这篇内容主要讨论/介绍了什么
2. 核心内容：提炼文章的关键观点、方法、技术或结论
3. 价值说明：简要说明该内容的实用价值或适用场景
4. 字数控制在 100-200 字
5. 使用客观、专业的语言风格

标题：{title}

正文：
{content}

请直接输出摘要内容，不要添加"摘要："等前缀。"""


async def generate_summary_with_llm(
    title: str,
    content: str,
    api_key: str,
    base_url: str,
    model: str
) -> str:
    """使用 LLM 生成摘要"""
    # 限制内容长度，避免 token 超限
    max_content_len = 4000
    if len(content) > max_content_len:
        content = content[:max_content_len] + "...[内容过长已截断]"
    
    prompt = SUMMARY_PROMPT.format(title=title, content=content)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            },
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"LLM API 错误: {response.text}"
            )
        
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()


@router.post("/items/generate-summary", response_model=GenerateSummaryResponse)
async def generate_summary(
    request: GenerateSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """为知识条目生成 AI 摘要"""
    # 获取用户的 LLM 配置
    config_result = await db.execute(
        select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
    )
    llm_config = config_result.scalar_one_or_none()
    
    if not llm_config or not llm_config.api_key:
        raise HTTPException(status_code=400, detail="请先配置 LLM API Key")
    
    success = 0
    failed = 0
    results = []
    
    for item_id in request.item_ids:
        try:
            # 获取知识条目
            result = await db.execute(
                select(KnowledgeItem)
                .where(KnowledgeItem.id == item_id, KnowledgeItem.user_id == current_user.id)
            )
            item = result.scalar_one_or_none()
            
            if not item:
                results.append({"id": item_id, "success": False, "error": "条目不存在"})
                failed += 1
                continue
            
            summary = ""
            
            # 书签类型：抓取网页 meta 信息
            if item.source_type == "bookmark" and item.url:
                meta = await fetch_webpage_meta(item.url)
                summary = build_summary_from_meta(item.title, item.url, meta)
                
                # 如果 meta 信息足够丰富，直接使用；否则尝试用 AI 生成
                if not summary and llm_config:
                    # 用 meta 信息让 AI 生成摘要
                    meta_content = f"""
网站标题: {meta.get('title') or item.title}
URL: {item.url}
描述: {meta.get('description') or meta.get('og_description') or '无'}
关键词: {meta.get('keywords') or '无'}
"""
                    summary = await generate_summary_with_llm(
                        title=item.title,
                        content=meta_content,
                        api_key=llm_config.api_key,
                        base_url=llm_config.base_url,
                        model=llm_config.model,
                    )
            
            # 笔记/文件类型：使用内容生成摘要
            elif item.content:
                summary = await generate_summary_with_llm(
                    title=item.title,
                    content=item.content,
                    api_key=llm_config.api_key,
                    base_url=llm_config.base_url,
                    model=llm_config.model,
                )
            else:
                results.append({"id": item_id, "success": False, "error": "内容为空且无法抓取"})
                failed += 1
                continue
            
            if not summary:
                results.append({"id": item_id, "success": False, "error": "无法生成摘要"})
                failed += 1
                continue
            
            # 保存摘要
            item.summary = summary
            item.has_summary = True
            item.updated_at = datetime.utcnow()
            
            results.append({
                "id": item_id, 
                "success": True, 
                "summary": summary[:100] + "..." if len(summary) > 100 else summary
            })
            success += 1
            
        except Exception as e:
            results.append({"id": item_id, "success": False, "error": str(e)})
            failed += 1
    
    await db.commit()
    
    return GenerateSummaryResponse(success=success, failed=failed, results=results)


@router.post("/sync", response_model=KnowledgeSyncResponse)
async def sync_knowledge(
    request: KnowledgeSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """同步笔记/书签/文件到知识库"""
    added = 0
    updated = 0
    removed = 0
    
    # 获取现有知识条目
    existing_result = await db.execute(
        select(KnowledgeItem).where(KnowledgeItem.user_id == current_user.id)
    )
    existing_items = {(item.source_type, item.source_id): item for item in existing_result.scalars().all()}
    
    # 同步笔记
    if request.sync_notes:
        notes_result = await db.execute(
            select(Note).where(Note.user_id == current_user.id)
        )
        for note in notes_result.scalars().all():
            key = ("note", note.id)
            if key in existing_items:
                # 更新
                item = existing_items[key]
                if item.title != note.title or item.content != note.content:
                    item.title = note.title
                    item.content = note.content
                    item.updated_at = datetime.utcnow()
                    updated += 1
                del existing_items[key]
            else:
                # 新增
                item = KnowledgeItem(
                    user_id=current_user.id,
                    source_type="note",
                    source_id=note.id,
                    title=note.title,
                    content=note.content,
                )
                db.add(item)
                added += 1
    
    # 同步书签
    if request.sync_bookmarks:
        bookmarks_result = await db.execute(
            select(Bookmark).where(Bookmark.user_id == current_user.id)
        )
        for bookmark in bookmarks_result.scalars().all():
            key = ("bookmark", bookmark.id)
            if key in existing_items:
                # 更新
                item = existing_items[key]
                if item.title != bookmark.title or item.url != bookmark.url:
                    item.title = bookmark.title
                    item.url = bookmark.url
                    item.updated_at = datetime.utcnow()
                    updated += 1
                del existing_items[key]
            else:
                # 新增
                item = KnowledgeItem(
                    user_id=current_user.id,
                    source_type="bookmark",
                    source_id=bookmark.id,
                    title=bookmark.title,
                    url=bookmark.url,
                )
                db.add(item)
                added += 1
    
    # 同步文件
    if request.sync_files:
        files_result = await db.execute(
            select(UploadedFile).where(UploadedFile.user_id == current_user.id)
        )
        for file in files_result.scalars().all():
            key = ("file", file.id)
            if key in existing_items:
                del existing_items[key]
            else:
                # 新增
                item = KnowledgeItem(
                    user_id=current_user.id,
                    source_type="file",
                    source_id=file.id,
                    title=file.original_name,
                    content=file.content_text,
                )
                db.add(item)
                added += 1
    
    # 删除不再存在的条目
    for key, item in existing_items.items():
        source_type = key[0]
        if (source_type == "note" and request.sync_notes) or \
           (source_type == "bookmark" and request.sync_bookmarks) or \
           (source_type == "file" and request.sync_files):
            await db.delete(item)
            removed += 1
    
    return KnowledgeSyncResponse(added=added, updated=updated, removed=removed)


# ==================== 知识库搜索 API ====================

@router.get("/search", response_model=List[KnowledgeSearchResult])
async def search_knowledge(
    q: str,
    source_types: Optional[str] = None,  # 逗号分隔: note,bookmark,file
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """搜索知识库（全文搜索，优先匹配标题和摘要）"""
    if not q.strip():
        return []
    
    # 构建查询
    query = select(KnowledgeItem).where(
        KnowledgeItem.user_id == current_user.id,
        KnowledgeItem.is_enabled == True,
    )
    
    # 筛选来源类型
    if source_types:
        types = [t.strip() for t in source_types.split(",")]
        query = query.where(KnowledgeItem.source_type.in_(types))
    
    # 搜索标题、摘要和内容
    search_pattern = f"%{q}%"
    query = query.where(
        or_(
            KnowledgeItem.title.ilike(search_pattern),
            KnowledgeItem.summary.ilike(search_pattern),
            KnowledgeItem.content.ilike(search_pattern),
        )
    )
    
    query = query.limit(limit * 2)  # 多取一些，后面排序
    
    result = await db.execute(query)
    items = result.scalars().all()
    
    # 计算相关性分数（标题 > 摘要 > 内容）
    q_lower = q.lower()
    scored_items = []
    for item in items:
        score = 0.0
        # 标题匹配得分最高
        if item.title and q_lower in item.title.lower():
            score += 3.0
        # 摘要匹配得分次高
        if item.summary and q_lower in item.summary.lower():
            score += 2.0
        # 内容匹配得分最低
        if item.content and q_lower in item.content.lower():
            score += 1.0
        scored_items.append((item, score))
    
    # 按相关性排序
    scored_items.sort(key=lambda x: x[1], reverse=True)
    scored_items = scored_items[:limit]
    
    # 构建结果，优先使用摘要作为片段
    results = []
    for item, score in scored_items:
        # 优先使用摘要作为片段，如果没有摘要则从内容中提取
        if item.summary:
            snippet = item.summary
        elif item.content:
            content_lower = item.content.lower()
            pos = content_lower.find(q_lower)
            if pos >= 0:
                start = max(0, pos - 50)
                end = min(len(item.content), pos + len(q) + 100)
                snippet = ("..." if start > 0 else "") + item.content[start:end] + ("..." if end < len(item.content) else "")
            else:
                snippet = item.content[:150] + "..." if len(item.content) > 150 else item.content
        else:
            snippet = item.title
        
        results.append(KnowledgeSearchResult(
            id=item.id,
            source_type=item.source_type,
            source_id=item.source_id,
            title=item.title,
            content_snippet=snippet,
            url=item.url,
            relevance=score / 6.0 if score > 0 else 0.5,  # 归一化分数
        ))
    
    return results

