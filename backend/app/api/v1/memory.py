"""用户长期记忆 API"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import Optional
from datetime import datetime

from ...database import get_db
from ...models import User, UserMemory, MemoryCategory
from ...schemas.memory import (
    MemoryCreate, 
    MemoryUpdate, 
    MemoryResponse, 
    MemoryListResponse,
    MemoryStats,
)
from ..deps import get_current_user

router = APIRouter(prefix="/memories", tags=["Memory"])


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    category: Optional[str] = Query(None, description="按分类筛选"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取用户的记忆列表"""
    query = select(UserMemory).where(UserMemory.user_id == user.id)
    
    # 分类筛选
    if category and category in MemoryCategory.ALL:
        query = query.where(UserMemory.category == category)
    
    # 关键词搜索
    if search:
        query = query.where(UserMemory.content.ilike(f"%{search}%"))
    
    # 按创建时间倒序
    query = query.order_by(UserMemory.created_at.desc())
    
    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    
    # 分页
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    memories = result.scalars().all()
    
    return MemoryListResponse(
        memories=[MemoryResponse.model_validate(m) for m in memories],
        total=total,
    )


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取记忆统计信息"""
    # 总数
    total_query = select(func.count()).where(UserMemory.user_id == user.id)
    total = (await db.execute(total_query)).scalar() or 0
    
    # 按分类统计
    category_query = (
        select(UserMemory.category, func.count())
        .where(UserMemory.user_id == user.id)
        .group_by(UserMemory.category)
    )
    result = await db.execute(category_query)
    by_category = {row[0]: row[1] for row in result.all()}
    
    return MemoryStats(total=total, by_category=by_category)


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取单条记忆详情"""
    result = await db.execute(
        select(UserMemory).where(
            UserMemory.id == memory_id,
            UserMemory.user_id == user.id,
        )
    )
    memory = result.scalar_one_or_none()
    
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    
    # 更新访问时间
    memory.last_accessed_at = datetime.utcnow()
    await db.commit()
    
    return MemoryResponse.model_validate(memory)


@router.post("", response_model=MemoryResponse)
async def create_memory(
    data: MemoryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建新记忆"""
    # 检查是否已存在相同内容
    existing = await db.execute(
        select(UserMemory).where(
            UserMemory.user_id == user.id,
            UserMemory.content == data.content,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="已存在相同内容的记忆")
    
    memory = UserMemory(
        user_id=user.id,
        content=data.content,
        category=data.category if data.category in MemoryCategory.ALL else "general",
        source=data.source,
        importance=data.importance,
    )
    
    db.add(memory)
    await db.commit()
    await db.refresh(memory)
    
    return MemoryResponse.model_validate(memory)


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    data: MemoryUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新记忆"""
    result = await db.execute(
        select(UserMemory).where(
            UserMemory.id == memory_id,
            UserMemory.user_id == user.id,
        )
    )
    memory = result.scalar_one_or_none()
    
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    
    # 更新字段
    if data.content is not None:
        memory.content = data.content
    if data.category is not None and data.category in MemoryCategory.ALL:
        memory.category = data.category
    if data.importance is not None:
        memory.importance = data.importance
    
    await db.commit()
    await db.refresh(memory)
    
    return MemoryResponse.model_validate(memory)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除记忆"""
    result = await db.execute(
        select(UserMemory).where(
            UserMemory.id == memory_id,
            UserMemory.user_id == user.id,
        )
    )
    memory = result.scalar_one_or_none()
    
    if not memory:
        raise HTTPException(status_code=404, detail="记忆不存在")
    
    await db.delete(memory)
    await db.commit()
    
    return {"message": "删除成功"}


@router.delete("")
async def clear_memories(
    category: Optional[str] = Query(None, description="只清除特定分类"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """清空记忆"""
    query = delete(UserMemory).where(UserMemory.user_id == user.id)
    
    if category and category in MemoryCategory.ALL:
        query = query.where(UserMemory.category == category)
    
    result = await db.execute(query)
    await db.commit()
    
    return {"message": f"已清除 {result.rowcount} 条记忆"}
