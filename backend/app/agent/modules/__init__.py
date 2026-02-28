"""
Agent 模块

提供可插拔的 AI 能力模块：
- RAG: 检索增强生成
- MCP: Model Context Protocol (TODO)
- Workflow: 工作流引擎 (TODO)
- AgentLoop: 自主循环 (TODO)
"""

from .base import AgentModule, ModuleResult, AgentContext
from .rag import RAGModule

__all__ = [
    "AgentModule",
    "ModuleResult", 
    "AgentContext",
    "RAGModule",
]
