"""
内置工具集合

提供安全测试相关的内置工具，包括：
- 编码/解码工具
- 哈希计算工具
- 网络查询工具

使用示例:
    from app.agent.tools import register_builtin_tools
    
    # 注册所有内置工具
    register_builtin_tools()
"""

from ..registry import tool_registry
from .encoding import register_encoding_tools
from .hash import register_hash_tools
from .network import register_network_tools


def register_builtin_tools() -> None:
    """注册所有内置工具"""
    register_encoding_tools(tool_registry)
    register_hash_tools(tool_registry)
    register_network_tools(tool_registry)


__all__ = ["register_builtin_tools"]

