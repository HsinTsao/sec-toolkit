"""
Agent Tool Calling 中间架构

提供标准化的工具定义、注册和执行机制，支持 LLM Function Calling。

## 传统模式
    from app.agent import tool_registry, tool_executor
    
    # 获取所有工具定义（用于传递给 LLM）
    tools = tool_registry.get_openai_tools()
    
    # 执行工具调用
    result = await tool_executor.execute("base64_encode", {"text": "hello"})

## 双 LLM 模式（省 Token）
    from app.agent import DualLLMAgent, LLMConfig
    
    agent = DualLLMAgent(LLMConfig(base_url=..., api_key=..., model=...))
    result = await agent.process("把 hello 转成 base64")
    # Token 消耗降低 60-70%
"""

from .registry import tool_registry
from .executor import tool_executor
from .base import BaseTool, ToolParameter, ToolResult, ParameterType
from .dual_llm import DualLLMAgent, LLMConfig, AgentMode, DualLLMResult
from .intent import IntentCategory, ParsedIntent

__all__ = [
    # 传统模式
    "tool_registry",
    "tool_executor", 
    "BaseTool",
    "ToolParameter",
    "ToolResult",
    "ParameterType",
    # 双 LLM 模式
    "DualLLMAgent",
    "LLMConfig",
    "AgentMode",
    "DualLLMResult",
    "IntentCategory",
    "ParsedIntent",
]

