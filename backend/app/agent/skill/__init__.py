"""
Skill 模块

提供可配置的 Skill 系统，支持：
- 预置 Skill（股票分析师、安全专家、编码助手等）
- 用户自定义 Skill
- 显式激活模式
"""

from .base import Skill, SkillCategory, SkillContext
from .registry import SkillRegistry, skill_registry, register_builtin_skills

__all__ = [
    "Skill",
    "SkillCategory",
    "SkillContext",
    "SkillRegistry",
    "skill_registry",
    "register_builtin_skills",
]
