"""
工具注册中心

管理所有可用工具的注册、查询和配置。
"""

from typing import Dict, List, Optional, Type, Callable
from .base import BaseTool, FunctionTool, ToolParameter, ParameterType
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册中心
    
    负责管理所有注册的工具，提供工具的注册、查询、分类等功能。
    
    使用示例:
        # 注册工具类
        registry.register(MyTool)
        
        # 使用装饰器注册函数
        @registry.tool(name="my_func", description="我的函数")
        def my_func(text: str) -> str:
            return text
        
        # 获取工具
        tool = registry.get("my_func")
        
        # 获取 OpenAI 格式的工具列表
        tools = registry.get_openai_tools()
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Dict[str, List[str]] = {}  # category -> [tool_names]
    
    def register(self, tool_class: Type[BaseTool]) -> None:
        """
        注册工具类
        
        Args:
            tool_class: 工具类（继承自 BaseTool）
        """
        tool = tool_class()
        self._register_instance(tool)
    
    def register_instance(self, tool: BaseTool) -> None:
        """
        注册工具实例
        
        Args:
            tool: 工具实例
        """
        self._register_instance(tool)
    
    def _register_instance(self, tool: BaseTool) -> None:
        """内部注册方法"""
        if not tool.name:
            raise ValueError(f"工具必须有名称: {tool.__class__.__name__}")
        
        if tool.name in self._tools:
            logger.warning(f"工具 {tool.name} 已存在，将被覆盖")
        
        self._tools[tool.name] = tool
        
        # 更新分类索引
        category = tool.category
        if category not in self._categories:
            self._categories[category] = []
        if tool.name not in self._categories[category]:
            self._categories[category].append(tool.name)
        
        logger.info(f"注册工具: {tool.name} (分类: {category})")
    
    def register_function(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: List[ToolParameter],
        category: str = "general",
        requires_confirmation: bool = False,
    ) -> None:
        """
        注册函数为工具
        
        Args:
            name: 工具名称
            description: 工具描述
            func: 要包装的函数
            parameters: 参数定义列表
            category: 分类
            requires_confirmation: 是否需要确认
        """
        tool = FunctionTool(
            name=name,
            description=description,
            func=func,
            parameters=parameters,
            category=category,
            requires_confirmation=requires_confirmation,
        )
        self._register_instance(tool)
    
    def tool(
        self,
        name: str,
        description: str,
        parameters: List[ToolParameter],
        category: str = "general",
        requires_confirmation: bool = False,
    ) -> Callable:
        """
        工具注册装饰器
        
        示例:
            @registry.tool(
                name="uppercase",
                description="转换为大写",
                parameters=[ToolParameter(name="text", description="输入文本")]
            )
            def uppercase(text: str) -> str:
                return text.upper()
        """
        def decorator(func: Callable) -> Callable:
            self.register_function(
                name=name,
                description=description,
                func=func,
                parameters=parameters,
                category=category,
                requires_confirmation=requires_confirmation,
            )
            return func
        return decorator
    
    def get(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)
    
    def get_all(self) -> List[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())
    
    def get_by_category(self, category: str) -> List[BaseTool]:
        """按分类获取工具"""
        tool_names = self._categories.get(category, [])
        return [self._tools[name] for name in tool_names if name in self._tools]
    
    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return list(self._categories.keys())
    
    def get_openai_tools(self, categories: Optional[List[str]] = None) -> List[dict]:
        """
        获取 OpenAI Function Calling 格式的工具列表
        
        Args:
            categories: 可选，只返回指定分类的工具
            
        Returns:
            OpenAI tools 格式的列表
        """
        tools = []
        for tool in self._tools.values():
            if categories is None or tool.category in categories:
                tools.append(tool.to_openai_function())
        return tools
    
    def get_tools_info(self, categories: Optional[List[str]] = None) -> List[dict]:
        """
        获取工具信息列表（用于 API 响应）
        
        Args:
            categories: 可选，只返回指定分类的工具
        """
        tools = []
        for tool in self._tools.values():
            if categories is None or tool.category in categories:
                tools.append(tool.to_dict())
        return tools
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            tool = self._tools.pop(name)
            # 从分类中移除
            if tool.category in self._categories:
                self._categories[tool.category] = [
                    n for n in self._categories[tool.category] if n != name
                ]
            logger.info(f"注销工具: {name}")
            return True
        return False
    
    def clear(self) -> None:
        """清空所有工具"""
        self._tools.clear()
        self._categories.clear()


# 全局工具注册中心实例
tool_registry = ToolRegistry()

