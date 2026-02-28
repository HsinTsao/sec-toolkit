"""
Skill 基础定义

Skill 是一组工具 + 专属 Prompt 的组合，用于处理特定领域的任务。
采用显式激活模式：用户手动选择激活某个 Skill，激活后该 Skill 的配置生效。
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class SkillCategory(str, Enum):
    """Skill 分类"""
    FINANCE = "finance"      # 金融分析
    SECURITY = "security"    # 安全检测
    ENCODING = "encoding"    # 编码解码
    SEARCH = "search"        # 搜索查询
    CUSTOM = "custom"        # 用户自定义


@dataclass
class Skill:
    """
    Skill 定义
    
    一个 Skill 包含：
    - 基本信息（id, name, description, icon）
    - 专属 System Prompt（角色设定）
    - 可用工具列表（白名单，空=全部可用）
    - 用户体验配置（欢迎语、示例提问）
    """
    # 基本信息
    id: str                             # 唯一标识（预置用 builtin_ 前缀）
    name: str                           # 显示名称
    description: str                    # 描述（显示给用户）
    icon: str = "🔧"                    # 图标 (emoji)
    category: SkillCategory = SkillCategory.CUSTOM
    
    # 核心配置
    system_prompt: str = ""             # 专属 System Prompt（角色设定）
    tools: list[str] = field(default_factory=list)  # 可用工具白名单（空=全部可用）
    
    # 用户体验
    welcome_message: str = ""           # 激活时的欢迎语
    example_prompts: list[str] = field(default_factory=list)  # 示例提问
    
    # 限制
    max_tool_calls: int = 10            # 单次最大工具调用次数
    
    # 元数据
    is_builtin: bool = False            # 是否预置
    enabled: bool = True                # 是否启用
    
    def to_dict(self) -> dict:
        """转换为字典（用于 API 返回）"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "category": self.category.value if isinstance(self.category, SkillCategory) else self.category,
            "system_prompt": self.system_prompt,
            "tools": self.tools,
            "welcome_message": self.welcome_message,
            "example_prompts": self.example_prompts,
            "max_tool_calls": self.max_tool_calls,
            "is_builtin": self.is_builtin,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Skill":
        """从字典创建 Skill"""
        category = data.get("category", "custom")
        if isinstance(category, str):
            try:
                category = SkillCategory(category)
            except ValueError:
                category = SkillCategory.CUSTOM
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            icon=data.get("icon", "🔧"),
            category=category,
            system_prompt=data.get("system_prompt", ""),
            tools=data.get("tools", []),
            welcome_message=data.get("welcome_message", ""),
            example_prompts=data.get("example_prompts", []),
            max_tool_calls=data.get("max_tool_calls", 10),
            is_builtin=data.get("is_builtin", False),
            enabled=data.get("enabled", True),
        )


@dataclass
class SkillContext:
    """Skill 执行上下文"""
    skill: Skill
    user_id: str
    user_input: str
    history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
