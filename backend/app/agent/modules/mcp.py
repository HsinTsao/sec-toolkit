"""
MCP (Model Context Protocol) 模块

提供与外部 MCP 服务器的集成能力：
1. 连接 MCP 服务器
2. 调用 MCP 工具
3. 获取资源

MCP 协议参考: https://modelcontextprotocol.io/
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from .base import AgentModule, AgentContext, ModuleResult

logger = logging.getLogger(__name__)


class MCPTransport(str, Enum):
    """MCP 传输类型"""
    STDIO = "stdio"
    HTTP = "http"
    WEBSOCKET = "ws"


@dataclass
class MCPServer:
    """MCP 服务器配置"""
    name: str
    transport: MCPTransport
    command: Optional[str] = None
    url: Optional[str] = None
    env: Optional[Dict[str, str]] = None
    enabled: bool = True


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    server: str


class MCPModule(AgentModule):
    """MCP 协议模块"""
    
    name = "mcp"
    description = "Model Context Protocol - 连接外部工具和数据源"
    version = "1.0.0"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._servers: Dict[str, MCPServer] = {}
        self._tools: Dict[str, MCPTool] = {}
        self._connections: Dict[str, Any] = {}
    
    async def add_server(self, server: MCPServer) -> bool:
        """添加 MCP 服务器"""
        try:
            self._servers[server.name] = server
            logger.info(f"[MCP] 添加服务器: {server.name}")
            return True
        except Exception as e:
            logger.error(f"[MCP] 添加服务器失败: {server.name}, {e}")
            return False
    
    async def list_servers(self) -> List[Dict[str, Any]]:
        """列出已配置的 MCP 服务器"""
        return [
            {
                "name": s.name,
                "transport": s.transport.value,
                "enabled": s.enabled,
                "connected": s.name in self._connections,
            }
            for s in self._servers.values()
        ]
    
    async def list_tools(self, server_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出可用的 MCP 工具"""
        tools = []
        for tool in self._tools.values():
            if server_name is None or tool.server == server_name:
                tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                    "server": tool.server,
                })
        return tools
    
    async def call_tool(
        self,
        server: str,
        tool: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """调用 MCP 工具"""
        if server not in self._connections:
            return {"error": f"服务器未连接: {server}"}
        
        logger.info(f"[MCP] 调用工具: {server}/{tool}")
        return {"error": "工具调用未实现"}
    
    async def process(self, context: AgentContext) -> ModuleResult:
        """处理 MCP 请求"""
        tools = await self.list_tools()
        
        return ModuleResult.ok(
            data={
                "available_tools": tools,
                "servers": await self.list_servers(),
            },
        )
    
    def get_config_schema(self) -> Dict[str, Any]:
        """返回配置 schema"""
        return {
            "type": "object",
            "properties": {
                "servers": {
                    "type": "array",
                    "title": "MCP 服务器",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "transport": {"type": "string"},
                            "enabled": {"type": "boolean"},
                        },
                    },
                },
            },
        }
    
    async def cleanup(self) -> None:
        """清理所有连接"""
        self._connections.clear()
