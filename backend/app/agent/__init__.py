"""
Agent Tool Calling 中间架构

提供标准化的工具定义、注册和执行机制，支持 LLM Function Calling。

使用示例:
    from app.agent import tool_registry, tool_executor
    
    # 获取所有工具定义（用于传递给 LLM）
    tools = tool_registry.get_openai_tools()
    
    # 执行工具调用
    result = await tool_executor.execute("base64_encode", {"text": "hello"})
"""

from .registry import tool_registry
from .executor import tool_executor
from .base import BaseTool, ToolParameter, ToolResult

__all__ = [
    "tool_registry",
    "tool_executor", 
    "BaseTool",
    "ToolParameter",
    "ToolResult",
]

