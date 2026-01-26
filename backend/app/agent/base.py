"""
工具基类定义

遵循 OpenAI Function Calling 标准格式，兼容大多数 LLM。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable, Union
from pydantic import BaseModel, Field
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class ParameterType(str, Enum):
    """参数类型"""
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str = Field(..., description="参数名称")
    type: ParameterType = Field(default=ParameterType.STRING, description="参数类型")
    description: str = Field(..., description="参数描述")
    required: bool = Field(default=True, description="是否必需")
    default: Optional[Any] = Field(default=None, description="默认值")
    enum: Optional[List[str]] = Field(default=None, description="可选值列表")


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool = Field(..., description="是否成功")
    data: Any = Field(default=None, description="返回数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    
    @classmethod
    def ok(cls, data: Any) -> "ToolResult":
        """创建成功结果"""
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        """创建失败结果"""
        return cls(success=False, error=error)


class BaseTool(ABC):
    """
    工具基类
    
    所有工具都需要继承此类并实现 execute 方法。
    
    示例:
        class MyTool(BaseTool):
            name = "my_tool"
            description = "我的工具"
            parameters = [
                ToolParameter(name="input", type=ParameterType.STRING, description="输入内容")
            ]
            
            async def execute(self, input: str) -> ToolResult:
                return ToolResult.ok(f"处理结果: {input}")
    """
    
    # 工具名称（唯一标识）
    name: str = ""
    
    # 工具描述（用于 LLM 理解工具用途）
    description: str = ""
    
    # 工具分类
    category: str = "general"
    
    # 参数定义
    parameters: List[ToolParameter] = []
    
    # 是否需要确认执行（用于危险操作）
    requires_confirmation: bool = False
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具
        
        Args:
            **kwargs: 根据 parameters 定义的参数
            
        Returns:
            ToolResult: 执行结果
        """
        pass
    
    def to_openai_function(self) -> Dict[str, Any]:
        """
        转换为 OpenAI Function Calling 格式
        
        Returns:
            符合 OpenAI API 规范的工具定义
        """
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type.value,
                "description": param.description,
            }
            
            if param.enum:
                prop["enum"] = param.enum
                
            if param.default is not None:
                prop["default"] = param.default
                
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            }
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 API 响应）"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": [p.model_dump() for p in self.parameters],
            "requires_confirmation": self.requires_confirmation,
        }


class FunctionTool(BaseTool):
    """
    函数包装工具
    
    将普通函数包装为工具，便于快速创建工具。
    
    示例:
        def my_func(text: str) -> str:
            return text.upper()
        
        tool = FunctionTool(
            name="uppercase",
            description="转换为大写",
            func=my_func,
            parameters=[
                ToolParameter(name="text", description="输入文本")
            ]
        )
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: List[ToolParameter],
        category: str = "general",
        requires_confirmation: bool = False,
    ):
        self.name = name
        self.description = description
        self._func = func
        self.parameters = parameters
        self.category = category
        self.requires_confirmation = requires_confirmation
    
    async def execute(self, **kwargs) -> ToolResult:
        """执行包装的函数"""
        try:
            # 检查是否是异步函数
            if asyncio.iscoroutinefunction(self._func):
                result = await self._func(**kwargs)
            else:
                # 在线程池中运行同步函数
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: self._func(**kwargs))
            
            # 处理返回值
            if isinstance(result, ToolResult):
                return result
            elif isinstance(result, str) and result.strip().startswith("错误:"):
                # 兼容现有工具函数返回错误字符串的情况
                error_msg = result.split("错误:", 1)[1].strip()
                return ToolResult.fail(error_msg or result)
            elif isinstance(result, dict) and "error" in result:
                return ToolResult.fail(result["error"])
            else:
                return ToolResult.ok(result)
                
        except Exception as e:
            logger.exception(f"工具 {self.name} 执行失败")
            return ToolResult.fail(str(e))

