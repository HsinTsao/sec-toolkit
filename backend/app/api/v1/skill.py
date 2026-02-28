"""
Skill API 端点

提供 Skill 的查询、创建、更新、删除功能。
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ...database import get_db
from ...models.user import User
from ...models.skill import UserSkill
from ...schemas.skill import (
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    SkillListItem,
    SkillListResponse,
)
from ...agent.skill import skill_registry, Skill
from ..deps import get_current_user, get_optional_user

router = APIRouter(prefix="/skills", tags=["Skill"])


@router.get("", response_model=SkillListResponse)
async def list_skills(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    获取所有可用的 Skill
    
    返回预置 Skill 和用户自定义 Skill 列表
    """
    # 获取预置 Skill
    builtin_skills = [
        SkillListItem(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            icon=skill.icon,
            category=skill.category.value if hasattr(skill.category, 'value') else skill.category,
            is_builtin=True,
            enabled=skill.enabled,
            tools_count=len(skill.tools),
        )
        for skill in skill_registry.get_all_builtin()
        if skill.enabled
    ]
    
    # 获取用户自定义 Skill
    custom_skills = []
    if current_user:
        stmt = select(UserSkill).where(UserSkill.user_id == current_user.id)
        result = await db.execute(stmt)
        user_skills = result.scalars().all()
        custom_skills = [
            SkillListItem(
                id=skill.id,
                name=skill.name,
                description=skill.description or "",
                icon=skill.icon or "🔧",
                category=skill.category or "custom",
                is_builtin=False,
                enabled=skill.enabled,
                tools_count=len(skill.tools or []),
            )
            for skill in user_skills
        ]
    
    return SkillListResponse(builtin=builtin_skills, custom=custom_skills)


@router.get("/{skill_id}", response_model=SkillResponse)
async def get_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    获取 Skill 详情
    """
    # 检查是否是预置 Skill
    if skill_id.startswith("builtin_"):
        builtin = skill_registry.get_builtin(skill_id)
        if builtin:
            return SkillResponse(
                id=builtin.id,
                name=builtin.name,
                description=builtin.description,
                icon=builtin.icon,
                category=builtin.category.value if hasattr(builtin.category, 'value') else builtin.category,
                system_prompt=builtin.system_prompt,
                tools=builtin.tools,
                welcome_message=builtin.welcome_message,
                example_prompts=builtin.example_prompts,
                max_tool_calls=builtin.max_tool_calls,
                is_builtin=True,
                enabled=builtin.enabled,
            )
        raise HTTPException(status_code=404, detail="预置 Skill 不存在")
    
    # 用户自定义 Skill
    if not current_user:
        raise HTTPException(status_code=401, detail="需要登录")
    
    stmt = select(UserSkill).where(
        UserSkill.id == skill_id,
        UserSkill.user_id == current_user.id
    )
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    return SkillResponse(**skill.to_dict())


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    data: SkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建自定义 Skill
    """
    skill = UserSkill(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        icon=data.icon,
        category=data.category,
        system_prompt=data.system_prompt,
        tools=data.tools,
        welcome_message=data.welcome_message,
        example_prompts=data.example_prompts,
        max_tool_calls=data.max_tool_calls,
    )
    
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    
    return SkillResponse(**skill.to_dict())


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: str,
    data: SkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新自定义 Skill
    """
    # 预置 Skill 不可修改
    if skill_id.startswith("builtin_"):
        raise HTTPException(status_code=403, detail="预置 Skill 不可修改")
    
    stmt = select(UserSkill).where(
        UserSkill.id == skill_id,
        UserSkill.user_id == current_user.id
    )
    result = await db.execute(stmt)
    skill = result.scalar_one_or_none()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(skill, field, value)
    
    await db.commit()
    await db.refresh(skill)
    
    return SkillResponse(**skill.to_dict())


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除自定义 Skill
    """
    # 预置 Skill 不可删除
    if skill_id.startswith("builtin_"):
        raise HTTPException(status_code=403, detail="预置 Skill 不可删除")
    
    stmt = delete(UserSkill).where(
        UserSkill.id == skill_id,
        UserSkill.user_id == current_user.id
    )
    result = await db.execute(stmt)
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    await db.commit()


@router.get("/{skill_id}/tools")
async def get_skill_tools(
    skill_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    获取 Skill 可用的工具列表
    """
    from ...agent import tool_registry
    
    # 获取 Skill
    skill: Optional[Skill] = None
    
    if skill_id.startswith("builtin_"):
        skill = skill_registry.get_builtin(skill_id)
    elif current_user:
        stmt = select(UserSkill).where(
            UserSkill.id == skill_id,
            UserSkill.user_id == current_user.id
        )
        result = await db.execute(stmt)
        user_skill = result.scalar_one_or_none()
        if user_skill:
            skill = user_skill.to_skill()
    
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    # 获取工具列表
    all_tools = tool_registry.get_tools_info()
    
    if skill.tools:
        # 有白名单，只返回白名单中的工具
        return [t for t in all_tools if t["name"] in skill.tools]
    else:
        # 无白名单，返回所有工具
        return all_tools
