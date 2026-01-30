"""
工具执行器

负责解析和执行 LLM 的工具调用请求。
"""

from typing import Any, Dict, List, Optional, Union
from .base import BaseTool, ToolResult
from .registry import tool_registry
import json
import logging

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    工具执行器
    
    负责执行工具调用，支持：
    - 单个工具调用
    - 批量工具调用
    - 从 LLM 响应中解析并执行工具调用
    
    使用示例:
        # 直接执行
        result = await executor.execute("base64_encode", {"text": "hello"})
        
        # 从 LLM 响应执行
        results = await executor.execute_from_llm_response(llm_response)
    """
    
    def __init__(self, registry: Optional["ToolRegistry"] = None):
        self._registry = registry or tool_registry
    
    async def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        require_confirmation: bool = True,
    ) -> ToolResult:
        """
        执行单个工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            require_confirmation: 是否检查确认要求
            
        Returns:
            ToolResult: 执行结果
        """
        tool = self._registry.get(tool_name)
        
        if not tool:
            return ToolResult.fail(f"工具不存在: {tool_name}")
        
        # 检查是否需要确认
        if require_confirmation and tool.requires_confirmation:
            logger.warning(f"🔧 [ToolExecutor] 工具需要确认: {tool_name}")
            return ToolResult(
                success=False,
                error="此工具需要用户确认后才能执行",
                data={"requires_confirmation": True, "tool_name": tool_name}
            )
        
        import time
        start_time = time.time()
        logger.info(f"🔧 [ToolExecutor] 开始执行: {tool_name}({arguments})")
        
        try:
            result = await tool.execute(**arguments)
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"🔧 [ToolExecutor] 执行完成: {tool_name}, success={result.success}, 耗时={elapsed:.0f}ms")
            return result
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            logger.error(f"🔧 [ToolExecutor] 执行异常: {tool_name}, error={e}, 耗时={elapsed:.0f}ms", exc_info=True)
            return ToolResult.fail(f"执行异常: {str(e)}")
    
    async def execute_batch(
        self,
        calls: List[Dict[str, Any]],
        stop_on_error: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        批量执行工具
        
        Args:
            calls: 工具调用列表，每项包含 {tool_name, arguments, call_id?}
            stop_on_error: 遇到错误是否停止
            
        Returns:
            执行结果列表
        """
        results = []
        
        for call in calls:
            tool_name = call.get("tool_name") or call.get("name")
            arguments = call.get("arguments", {})
            call_id = call.get("call_id") or call.get("id")
            
            result = await self.execute(tool_name, arguments)
            
            results.append({
                "call_id": call_id,
                "tool_name": tool_name,
                "result": result.model_dump(),
            })
            
            if stop_on_error and not result.success:
                break
        
        return results
    
    def parse_tool_calls(self, llm_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从 LLM 响应中解析工具调用
        
        支持 OpenAI 格式的响应。
        
        Args:
            llm_response: LLM API 的响应
            
        Returns:
            工具调用列表
        """
        tool_calls = []
        
        # OpenAI 格式
        choices = llm_response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            calls = message.get("tool_calls", [])
            
            for call in calls:
                if call.get("type") == "function":
                    function = call.get("function", {})
                    tool_calls.append({
                        "call_id": call.get("id"),
                        "tool_name": function.get("name"),
                        "arguments": self._parse_arguments(function.get("arguments", "{}")),
                    })
        
        return tool_calls
    
    def _parse_arguments(self, arguments: Union[str, dict]) -> Dict[str, Any]:
        """解析参数（可能是 JSON 字符串或字典）"""
        if isinstance(arguments, dict):
            return arguments
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {}
    
    async def execute_from_llm_response(
        self,
        llm_response: Dict[str, Any],
        stop_on_error: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        从 LLM 响应中解析并执行工具调用
        
        Args:
            llm_response: LLM API 的响应
            stop_on_error: 遇到错误是否停止
            
        Returns:
            执行结果列表
        """
        tool_calls = self.parse_tool_calls(llm_response)
        
        if not tool_calls:
            return []
        
        return await self.execute_batch(tool_calls, stop_on_error)
    
    def format_tool_results_for_llm(
        self,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        将工具执行结果格式化为 LLM 可理解的消息格式
        
        Args:
            results: execute_batch 返回的结果
            
        Returns:
            可添加到 messages 的工具结果消息列表
        """
        messages = []
        
        for r in results:
            call_id = r.get("call_id")
            result = r.get("result", {})
            
            # 格式化输出内容
            if result.get("success"):
                content = json.dumps(result.get("data"), ensure_ascii=False, indent=2)
            else:
                content = f"错误: {result.get('error', '未知错误')}"
            
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": content,
            })
        
        return messages


# 全局工具执行器实例
tool_executor = ToolExecutor()

