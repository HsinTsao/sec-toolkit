"""
Trace 事件系统

提供 Agent 执行过程的可观测性，支持：
- 结构化事件记录
- 嵌套事件追踪
- 实时事件推送
- 执行时间统计

使用示例:
    tracer = Tracer()
    
    with tracer.span("intent", "Intent Recognition") as span:
        span.set_data({"input": user_input})
        result = await intent_llm(user_input)
        span.set_data({"result": result})
    
    events = tracer.get_events()
"""

import time
import uuid
import asyncio
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, field
from contextlib import contextmanager, asynccontextmanager

logger = logging.getLogger(__name__)


class TraceType(str, Enum):
    """事件类型"""
    INTENT = "intent"              # 意图识别
    TOOL_CALL = "tool_call"        # 工具调用
    LLM_CALL = "llm_call"          # LLM 调用
    RAG_QUERY = "rag_query"        # RAG 检索
    MCP_REQUEST = "mcp_request"    # MCP 请求
    WORKFLOW_STEP = "workflow_step"  # 工作流步骤
    AGENT_LOOP = "agent_loop"      # Agent 循环
    RULE_MATCH = "rule_match"      # 规则匹配
    SUMMARY = "summary"            # 摘要生成
    ERROR = "error"                # 错误


class TraceStage(str, Enum):
    """事件阶段"""
    START = "start"
    END = "end"
    ERROR = "error"


@dataclass
class TraceEvent:
    """追踪事件"""
    id: str                              # 事件 ID
    type: TraceType                      # 事件类型
    name: str                            # 显示名称
    stage: TraceStage                    # 阶段
    timestamp: float                     # 时间戳（毫秒）
    parent_id: Optional[str] = None      # 父事件 ID
    duration_ms: Optional[float] = None  # 耗时（毫秒）
    data: Dict[str, Any] = field(default_factory=dict)      # 事件数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "id": self.id,
            "type": self.type.value if isinstance(self.type, Enum) else self.type,
            "name": self.name,
            "stage": self.stage.value if isinstance(self.stage, Enum) else self.stage,
            "timestamp": self.timestamp,
            "parent_id": self.parent_id,
            "duration_ms": self.duration_ms,
            "data": self.data,
            "metadata": self.metadata,
        }
        return result


class TraceSpan:
    """
    追踪跨度
    
    表示一个可测量的操作，支持嵌套。
    """
    
    def __init__(
        self,
        tracer: "Tracer",
        event_type: TraceType,
        name: str,
        parent_id: Optional[str] = None,
    ):
        self.tracer = tracer
        self.id = str(uuid.uuid4())[:8]
        self.type = event_type
        self.name = name
        self.parent_id = parent_id
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.data: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self._children: List[str] = []
    
    def set_data(self, data: Dict[str, Any]) -> "TraceSpan":
        """设置事件数据"""
        self.data.update(data)
        return self
    
    def set_metadata(self, metadata: Dict[str, Any]) -> "TraceSpan":
        """设置元数据"""
        self.metadata.update(metadata)
        return self
    
    def add_child(self, child_id: str) -> None:
        """添加子事件"""
        self._children.append(child_id)
    
    def start(self) -> "TraceSpan":
        """开始计时"""
        self.start_time = time.time() * 1000  # 毫秒
        
        # 发送开始事件
        event = TraceEvent(
            id=self.id,
            type=self.type,
            name=self.name,
            stage=TraceStage.START,
            timestamp=self.start_time,
            parent_id=self.parent_id,
            data=self.data.copy(),
            metadata=self.metadata.copy(),
        )
        self.tracer._add_event(event)
        
        return self
    
    def end(self, error: Optional[str] = None) -> "TraceSpan":
        """结束计时"""
        self.end_time = time.time() * 1000  # 毫秒
        duration = self.end_time - (self.start_time or self.end_time)
        
        # 发送结束事件
        event = TraceEvent(
            id=self.id,
            type=self.type,
            name=self.name,
            stage=TraceStage.ERROR if error else TraceStage.END,
            timestamp=self.end_time,
            parent_id=self.parent_id,
            duration_ms=round(duration, 2),
            data=self.data.copy(),
            metadata=self.metadata.copy(),
        )
        
        if error:
            event.data["error"] = error
        
        self.tracer._add_event(event)
        
        return self
    
    def __enter__(self) -> "TraceSpan":
        return self.start()
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_val:
            self.end(error=str(exc_val))
        else:
            self.end()


class Tracer:
    """
    追踪器
    
    管理一次请求的所有追踪事件。
    """
    
    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())[:8]
        self._events: List[TraceEvent] = []
        self._current_span: Optional[TraceSpan] = None
        self._span_stack: List[TraceSpan] = []
        self._listeners: List[Callable[[TraceEvent], None]] = []
        self._async_listeners: List[Callable[[TraceEvent], Any]] = []
        self._start_time = time.time() * 1000
    
    def span(
        self,
        event_type: TraceType,
        name: str,
    ) -> TraceSpan:
        """
        创建一个追踪跨度
        
        Args:
            event_type: 事件类型
            name: 显示名称
            
        Returns:
            TraceSpan 实例，可用作上下文管理器
        """
        parent_id = self._span_stack[-1].id if self._span_stack else None
        span = TraceSpan(self, event_type, name, parent_id)
        
        if parent_id:
            self._span_stack[-1].add_child(span.id)
        
        return span
    
    @contextmanager
    def trace(self, event_type: TraceType, name: str):
        """同步追踪上下文管理器"""
        span = self.span(event_type, name)
        self._span_stack.append(span)
        try:
            span.start()
            yield span
            span.end()
        except Exception as e:
            span.end(error=str(e))
            raise
        finally:
            self._span_stack.pop()
    
    @asynccontextmanager
    async def trace_async(self, event_type: TraceType, name: str):
        """异步追踪上下文管理器"""
        span = self.span(event_type, name)
        self._span_stack.append(span)
        try:
            span.start()
            yield span
            span.end()
        except Exception as e:
            span.end(error=str(e))
            raise
        finally:
            self._span_stack.pop()
    
    def _add_event(self, event: TraceEvent) -> None:
        """添加事件"""
        self._events.append(event)
        
        # 通知监听器
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.warning(f"Trace listener error: {e}")
        
        # 异步监听器
        for listener in self._async_listeners:
            try:
                result = listener(event)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                logger.warning(f"Async trace listener error: {e}")
    
    def add_listener(self, listener: Callable[[TraceEvent], None]) -> None:
        """添加事件监听器"""
        self._listeners.append(listener)
    
    def add_async_listener(self, listener: Callable[[TraceEvent], Any]) -> None:
        """添加异步事件监听器"""
        self._async_listeners.append(listener)
    
    def get_events(self) -> List[Dict[str, Any]]:
        """获取所有事件"""
        return [e.to_dict() for e in self._events]
    
    def get_summary(self) -> Dict[str, Any]:
        """获取追踪摘要"""
        total_time = time.time() * 1000 - self._start_time
        
        # 统计各类型事件
        type_stats = {}
        for event in self._events:
            if event.stage == TraceStage.END:
                event_type = event.type.value if isinstance(event.type, Enum) else event.type
                if event_type not in type_stats:
                    type_stats[event_type] = {"count": 0, "total_ms": 0}
                type_stats[event_type]["count"] += 1
                type_stats[event_type]["total_ms"] += event.duration_ms or 0
        
        # 计算总 tokens（从 metadata 中提取）
        total_tokens = 0
        for event in self._events:
            if "tokens" in event.metadata:
                total_tokens += event.metadata["tokens"]
        
        return {
            "trace_id": self.trace_id,
            "total_time_ms": round(total_time, 2),
            "event_count": len(self._events),
            "type_stats": type_stats,
            "total_tokens": total_tokens,
        }
    
    def clear(self) -> None:
        """清空事件"""
        self._events.clear()
        self._span_stack.clear()


# 全局 Tracer 工厂
class TracerFactory:
    """Tracer 工厂，用于管理请求级别的 Tracer"""
    
    _tracers: Dict[str, Tracer] = {}
    
    @classmethod
    def create(cls, trace_id: Optional[str] = None) -> Tracer:
        """创建新的 Tracer"""
        tracer = Tracer(trace_id)
        cls._tracers[tracer.trace_id] = tracer
        return tracer
    
    @classmethod
    def get(cls, trace_id: str) -> Optional[Tracer]:
        """获取已存在的 Tracer"""
        return cls._tracers.get(trace_id)
    
    @classmethod
    def remove(cls, trace_id: str) -> None:
        """移除 Tracer"""
        cls._tracers.pop(trace_id, None)
    
    @classmethod
    def clear_all(cls) -> None:
        """清空所有 Tracer"""
        cls._tracers.clear()
