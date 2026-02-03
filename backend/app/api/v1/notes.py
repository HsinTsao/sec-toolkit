"""笔记路由"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional

from ...database import get_db
from ...models import User, Note, Category, Tag, NoteTag
from ...schemas import (
    NoteCreate, NoteUpdate, NoteResponse,
    CategoryCreate, CategoryResponse,
    TagCreate, TagResponse
)
from ...api.deps import get_current_user

router = APIRouter()


# ==================== 分类 ====================

@router.get("/categories", response_model=List[CategoryResponse])
async def get_categories(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取分类列表"""
    result = await db.execute(
        select(Category)
        .where(Category.user_id == current_user.id)
        .order_by(Category.sort_order)
    )
    return result.scalars().all()


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    category_in: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建分类"""
    category = Category(
        user_id=current_user.id,
        name=category_in.name,
        parent_id=category_in.parent_id,
        icon=category_in.icon,
        sort_order=category_in.sort_order
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除分类"""
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == current_user.id
        )
    )
    category = result.scalar_one_or_none()
    
    if not category:
        raise HTTPException(status_code=404, detail="分类不存在")
    
    await db.delete(category)
    return {"message": "删除成功"}


# ==================== 标签 ====================

@router.get("/tags", response_model=List[TagResponse])
async def get_tags(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取标签列表"""
    result = await db.execute(
        select(Tag).where(Tag.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    tag_in: TagCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建标签"""
    tag = Tag(
        user_id=current_user.id,
        name=tag_in.name,
        color=tag_in.color
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}")
async def delete_tag(
    tag_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除标签"""
    result = await db.execute(
        select(Tag).where(Tag.id == tag_id, Tag.user_id == current_user.id)
    )
    tag = result.scalar_one_or_none()
    
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")
    
    await db.delete(tag)
    return {"message": "删除成功"}


# ==================== 笔记 ====================

@router.get("", response_model=List[NoteResponse])
async def get_notes(
    category_id: Optional[str] = None,
    tag_id: Optional[str] = None,
    search: Optional[str] = None,
    pinned_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取笔记列表"""
    query = select(Note).where(Note.user_id == current_user.id)
    
    # 分类筛选
    if category_id:
        query = query.where(Note.category_id == category_id)
    
    # 置顶筛选
    if pinned_only:
        query = query.where(Note.is_pinned == True)
    
    # 搜索
    if search:
        query = query.where(
            or_(
                Note.title.ilike(f"%{search}%"),
                Note.content.ilike(f"%{search}%")
            )
        )
    
    # 标签筛选
    if tag_id:
        query = query.join(NoteTag).where(NoteTag.tag_id == tag_id)
    
    # 排序和分页
    query = query.order_by(Note.is_pinned.desc(), Note.updated_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await db.execute(query.options(selectinload(Note.tags).selectinload(NoteTag.tag)))
    notes = result.scalars().all()
    
    # 转换响应格式
    response = []
    for note in notes:
        note_dict = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "category_id": note.category_id,
            "is_encrypted": note.is_encrypted,
            "is_pinned": note.is_pinned,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
            "tags": [
                TagResponse(
                    id=nt.tag.id,
                    name=nt.tag.name,
                    color=nt.tag.color,
                    created_at=nt.tag.created_at
                )
                for nt in note.tags
            ]
        }
        response.append(NoteResponse(**note_dict))
    
    return response


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取单个笔记"""
    result = await db.execute(
        select(Note)
        .where(Note.id == note_id, Note.user_id == current_user.id)
        .options(selectinload(Note.tags).selectinload(NoteTag.tag))
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    note_dict = {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "category_id": note.category_id,
        "is_encrypted": note.is_encrypted,
        "is_pinned": note.is_pinned,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "tags": [
            TagResponse(
                id=nt.tag.id,
                name=nt.tag.name,
                color=nt.tag.color,
                created_at=nt.tag.created_at
            )
            for nt in note.tags
        ]
    }
    return NoteResponse(**note_dict)


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    note_in: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建笔记"""
    note = Note(
        user_id=current_user.id,
        title=note_in.title,
        content=note_in.content,
        category_id=note_in.category_id,
        is_encrypted=note_in.is_encrypted,
        is_pinned=note_in.is_pinned
    )
    db.add(note)
    await db.flush()
    
    # 添加标签
    for tag_id in note_in.tag_ids:
        note_tag = NoteTag(note_id=note.id, tag_id=tag_id)
        db.add(note_tag)
    
    await db.flush()
    await db.refresh(note)
    
    # 重新查询以获取标签
    result = await db.execute(
        select(Note)
        .where(Note.id == note.id)
        .options(selectinload(Note.tags).selectinload(NoteTag.tag))
    )
    note = result.scalar_one()
    
    note_dict = {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "category_id": note.category_id,
        "is_encrypted": note.is_encrypted,
        "is_pinned": note.is_pinned,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "tags": [
            TagResponse(
                id=nt.tag.id,
                name=nt.tag.name,
                color=nt.tag.color,
                created_at=nt.tag.created_at
            )
            for nt in note.tags
        ]
    }
    return NoteResponse(**note_dict)


@router.patch("/{note_id}", response_model=NoteResponse)
@router.post("/{note_id}/update", response_model=NoteResponse)  # POST 别名，兼容某些网络环境
async def update_note(
    note_id: str,
    note_in: NoteUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新笔记"""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == current_user.id)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    # 更新字段
    if note_in.title is not None:
        note.title = note_in.title
    if note_in.content is not None:
        note.content = note_in.content
    if note_in.category_id is not None:
        note.category_id = note_in.category_id
    if note_in.is_encrypted is not None:
        note.is_encrypted = note_in.is_encrypted
    if note_in.is_pinned is not None:
        note.is_pinned = note_in.is_pinned
    
    # 更新标签
    if note_in.tag_ids is not None:
        # 删除旧标签
        await db.execute(
            NoteTag.__table__.delete().where(NoteTag.note_id == note_id)
        )
        # 添加新标签
        for tag_id in note_in.tag_ids:
            note_tag = NoteTag(note_id=note.id, tag_id=tag_id)
            db.add(note_tag)
    
    await db.flush()
    
    # 重新查询
    result = await db.execute(
        select(Note)
        .where(Note.id == note.id)
        .options(selectinload(Note.tags).selectinload(NoteTag.tag))
    )
    note = result.scalar_one()
    
    note_dict = {
        "id": note.id,
        "title": note.title,
        "content": note.content,
        "category_id": note.category_id,
        "is_encrypted": note.is_encrypted,
        "is_pinned": note.is_pinned,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "tags": [
            TagResponse(
                id=nt.tag.id,
                name=nt.tag.name,
                color=nt.tag.color,
                created_at=nt.tag.created_at
            )
            for nt in note.tags
        ]
    }
    return NoteResponse(**note_dict)


@router.delete("/{note_id}")
async def delete_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除笔记"""
    result = await db.execute(
        select(Note).where(Note.id == note_id, Note.user_id == current_user.id)
    )
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    
    await db.delete(note)
    return {"message": "删除成功"}

