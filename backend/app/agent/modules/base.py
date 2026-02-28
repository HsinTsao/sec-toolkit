"""
Agent 模块基类

定义所有 Agent 模块的通用接口。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from dataclasses import dataclass


@dataclass
class AgentContext:
    """
    Agent 执行上下文
    
    包含当前请求的所有上下文信息。
    """
    user_id: str                          # 用户 ID
    user_input: str                       # 用户输入
    history: List[Dict[str, str]] = None  # 对话历史
    metadata: Dict[str, Any] = None       # 元数据
    
    def __post_init__(self):
        if self.history is None:
            self.history = []
        if self.metadata is None:
            self.metadata = {}


class ModuleResult(BaseModel):
    """
    模块执行结果
    """
    success: bool = Field(..., description="是否成功")
    data: Optional[Dict[str, Any]] = Field(None, description="结果数据")
    error: Optional[str] = Field(None, description="错误信息")
    
    # RAG 特有字段
    context: Optional[str] = Field(None, description="注入的上下文")
    sources: Optional[List[Dict[str, Any]]] = Field(None, description="来源列表")
    
    @classmethod
    def ok(cls, data: Optional[Dict[str, Any]] = None, **kwargs) -> "ModuleResult":
        return cls(success=True, data=data, **kwargs)
    
    @classmethod
    def fail(cls, error: str) -> "ModuleResult":
        return cls(success=False, error=error)


class AgentModule(ABC):
    """
    Agent 模块基类
    
    所有模块都需要继承此类并实现 process 方法。
    """
    
    # 模块元信息
    name: str = "base"
    description: str = "Base module"
    version: str = "1.0.0"
    
    # 模块状态
    enabled: bool = True
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
    
    @abstractmethod
    async def process(self, context: AgentContext) -> ModuleResult:
        """
        处理请求
        
        Args:
            context: Agent 执行上下文
            
        Returns:
            ModuleResult: 模块执行结果
        """
        pass
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        返回配置 schema（用于前端配置面板）
        
        Returns:
            JSON Schema 格式的配置定义
        """
        return {}
    
    async def initialize(self) -> None:
        """
        模块初始化
        
        在模块首次使用时调用。
        """
        pass
    
    async def cleanup(self) -> None:
        """
        模块清理
        
        在模块不再使用时调用。
        """
        pass
