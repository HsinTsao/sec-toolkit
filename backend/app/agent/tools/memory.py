"""
长期记忆工具

让 AI 可以保存和检索用户的长期记忆。
"""

from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import logging

from ..base import ToolParameter, ParameterType
from ..registry import ToolRegistry
from ..context import get_agent_context
from ...models import UserMemory, MemoryCategory

logger = logging.getLogger(__name__)


async def _get_db_session() -> Optional[AsyncSession]:
    """从上下文获取数据库会话"""
    ctx = get_agent_context()
    if ctx and ctx.db_session:
        return ctx.db_session
    return None


async def _get_user_id() -> Optional[str]:
    """从上下文获取用户 ID"""
    ctx = get_agent_context()
    if ctx and ctx.user_id:
        return ctx.user_id
    return None


async def save_memory(
    content: str,
    category: str = "general",
    source: Optional[str] = None,
) -> str:
    """
    保存一条长期记忆
    
    Args:
        content: 要记住的内容
        category: 分类（preference/fact/instruction/general）
        source: 原始对话片段（可选）
    
    Returns:
        保存结果消息
    """
    db = await _get_db_session()
    user_id = await _get_user_id()
    
    if not db or not user_id:
        return "无法保存记忆：缺少用户上下文"
    
    # 验证分类
    if category not in MemoryCategory.ALL:
        category = "general"
    
    # 检查是否已存在相同内容
    existing = await db.execute(
        select(UserMemory).where(
            UserMemory.user_id == user_id,
            UserMemory.content == content,
        )
    )
    if existing.scalar_one_or_none():
        return f"已记住该内容，无需重复保存"
    
    # 创建新记忆
    memory = UserMemory(
        user_id=user_id,
        content=content,
        category=category,
        source=source,
        importance=1.0,
    )
    
    db.add(memory)
    await db.commit()
    
    category_names = {
        "preference": "偏好",
        "fact": "事实",
        "instruction": "指令",
        "general": "信息",
    }
    
    logger.info(f"💾 保存记忆: [{category}] {content[:50]}...")
    return f"✓ 已记住（{category_names.get(category, '信息')}）：{content}"


async def recall_memories(
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 5,
) -> str:
    """
    检索相关的长期记忆
    
    Args:
        query: 搜索关键词（可选）
        category: 按分类筛选（可选）
        limit: 返回数量限制
    
    Returns:
        相关记忆列表
    """
    db = await _get_db_session()
    user_id = await _get_user_id()
    
    if not db or not user_id:
        return "无法检索记忆：缺少用户上下文"
    
    # 构建查询
    stmt = select(UserMemory).where(UserMemory.user_id == user_id)
    
    if category and category in MemoryCategory.ALL:
        stmt = stmt.where(UserMemory.category == category)
    
    if query:
        stmt = stmt.where(UserMemory.content.ilike(f"%{query}%"))
    
    stmt = stmt.order_by(UserMemory.importance.desc(), UserMemory.created_at.desc())
    stmt = stmt.limit(limit)
    
    result = await db.execute(stmt)
    memories = result.scalars().all()
    
    if not memories:
        return "没有找到相关记忆"
    
    # 更新访问时间
    for mem in memories:
        mem.last_accessed_at = datetime.utcnow()
    await db.commit()
    
    # 格式化输出
    lines = ["找到以下记忆："]
    for i, mem in enumerate(memories, 1):
        category_emoji = {
            "preference": "❤️",
            "fact": "📌",
            "instruction": "📋",
            "general": "💭",
        }.get(mem.category, "💭")
        lines.append(f"{i}. {category_emoji} {mem.content}")
    
    return "\n".join(lines)


async def list_all_memories() -> str:
    """
    列出所有长期记忆的摘要
    
    Returns:
        记忆统计和列表
    """
    db = await _get_db_session()
    user_id = await _get_user_id()
    
    if not db or not user_id:
        return "无法检索记忆：缺少用户上下文"
    
    stmt = select(UserMemory).where(UserMemory.user_id == user_id)
    stmt = stmt.order_by(UserMemory.created_at.desc())
    
    result = await db.execute(stmt)
    memories = result.scalars().all()
    
    if not memories:
        return "还没有任何记忆"
    
    # 按分类统计
    by_category = {}
    for mem in memories:
        by_category.setdefault(mem.category, []).append(mem)
    
    category_names = {
        "preference": "偏好",
        "fact": "事实",
        "instruction": "指令",
        "general": "通用",
    }
    
    lines = [f"共有 {len(memories)} 条记忆："]
    for cat, mems in by_category.items():
        lines.append(f"\n**{category_names.get(cat, cat)}** ({len(mems)} 条)")
        for mem in mems[:3]:  # 每类最多显示 3 条
            lines.append(f"  • {mem.content[:50]}{'...' if len(mem.content) > 50 else ''}")
        if len(mems) > 3:
            lines.append(f"  ...还有 {len(mems) - 3} 条")
    
    return "\n".join(lines)


def register_memory_tools(registry: ToolRegistry) -> None:
    """注册记忆工具"""
    
    # 保存记忆
    registry.register_function(
        name="save_memory",
        description="保存用户告诉你的重要信息作为长期记忆。当用户说'记住'、'以后'、'每次'等词汇时应该调用此工具。",
        func=save_memory,
        parameters=[
            ToolParameter(
                name="content",
                type=ParameterType.STRING,
                description="要记住的内容，简洁明确地描述用户的偏好、事实或指令",
            ),
            ToolParameter(
                name="category",
                type=ParameterType.STRING,
                description="分类：preference(偏好)、fact(事实)、instruction(指令)、general(通用)",
                required=False,
            ),
            ToolParameter(
                name="source",
                type=ParameterType.STRING,
                description="原始对话片段（可选）",
                required=False,
            ),
        ],
        category="memory",
    )
    
    # 检索记忆
    registry.register_function(
        name="recall_memories",
        description="检索与当前对话相关的长期记忆。用于了解用户的偏好和历史信息。",
        func=recall_memories,
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="搜索关键词",
                required=False,
            ),
            ToolParameter(
                name="category",
                type=ParameterType.STRING,
                description="按分类筛选：preference/fact/instruction/general",
                required=False,
            ),
            ToolParameter(
                name="limit",
                type=ParameterType.INTEGER,
                description="返回数量限制，默认 5",
                required=False,
            ),
        ],
        category="memory",
    )
    
    # 列出所有记忆
    registry.register_function(
        name="list_all_memories",
        description="列出用户的所有长期记忆摘要",
        func=list_all_memories,
        parameters=[],
        category="memory",
    )
