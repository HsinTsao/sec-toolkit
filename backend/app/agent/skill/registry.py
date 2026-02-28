"""
Skill 注册中心

管理所有 Skill（预置 + 用户自定义），提供查询和获取功能。
"""

import logging
from typing import Optional
from .base import Skill, SkillCategory

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Skill 注册中心
    
    管理预置 Skill，用户 Skill 从数据库动态加载。
    """
    
    def __init__(self):
        self._builtin_skills: dict[str, Skill] = {}
    
    def register(self, skill: Skill) -> None:
        """注册预置 Skill"""
        if not skill.id.startswith("builtin_"):
            skill.id = f"builtin_{skill.id}"
        skill.is_builtin = True
        self._builtin_skills[skill.id] = skill
        logger.info(f"注册预置 Skill: {skill.name} ({skill.id})")
    
    def get_builtin(self, skill_id: str) -> Optional[Skill]:
        """获取预置 Skill"""
        return self._builtin_skills.get(skill_id)
    
    def get_all_builtin(self) -> list[Skill]:
        """获取所有预置 Skill"""
        return list(self._builtin_skills.values())
    
    def get_builtin_by_category(self, category: SkillCategory) -> list[Skill]:
        """按分类获取预置 Skill"""
        return [s for s in self._builtin_skills.values() if s.category == category]
    
    def list_builtin_info(self) -> list[dict]:
        """获取预置 Skill 简要信息列表"""
        return [
            {
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "icon": skill.icon,
                "category": skill.category.value if isinstance(skill.category, SkillCategory) else skill.category,
                "is_builtin": True,
                "tools_count": len(skill.tools),
            }
            for skill in self._builtin_skills.values()
            if skill.enabled
        ]


# 全局 Skill 注册中心
skill_registry = SkillRegistry()


def register_builtin_skills():
    """注册所有预置 Skill"""
    from .builtin import get_builtin_skills
    
    for skill in get_builtin_skills():
        skill_registry.register(skill)
    
    logger.info(f"预置 Skill 注册完成，共 {len(skill_registry._builtin_skills)} 个")
