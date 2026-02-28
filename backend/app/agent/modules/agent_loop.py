"""
Agent Loop 模块 - 自主循环执行

实现类似 ReAct 的思考-行动-观察循环：
1. 思考：分析当前状态，规划下一步
2. 行动：执行工具或生成回复
3. 观察：获取结果，更新状态
4. 循环直到任务完成
"""
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from .base import AgentModule, AgentContext, ModuleResult

logger = logging.getLogger(__name__)


class LoopState(str, Enum):
    """循环状态"""
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class LoopStep:
    """循环步骤记录"""
    iteration: int
    state: LoopState
    thought: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Dict] = None
    observation: Optional[str] = None


@dataclass
class LoopContext:
    """循环执行上下文"""
    task: str
    max_iterations: int = 10
    current_iteration: int = 0
    steps: List[LoopStep] = field(default_factory=list)
    final_answer: Optional[str] = None


class AgentLoopModule(AgentModule):
    """
    Agent Loop 模块
    
    支持自主循环执行任务，直到获得最终答案。
    """
    
    name = "agent_loop"
    description = "自主循环执行 - ReAct 风格"
    version = "1.0.0"
    
    DEFAULT_CONFIG = {
        "max_iterations": 10,
        "think_prompt": "分析当前情况，决定下一步行动",
        "stop_phrases": ["FINAL ANSWER:", "任务完成"],
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
    
    async def run_loop(
        self,
        task: str,
        context: AgentContext,
        available_tools: List[str],
    ) -> LoopContext:
        """
        运行 Agent 循环
        
        Args:
            task: 任务描述
            context: Agent 上下文
            available_tools: 可用工具列表
            
        Returns:
            循环执行上下文
        """
        loop_ctx = LoopContext(
            task=task,
            max_iterations=self.config["max_iterations"],
        )
        
        while loop_ctx.current_iteration < loop_ctx.max_iterations:
            loop_ctx.current_iteration += 1
            step = LoopStep(iteration=loop_ctx.current_iteration, state=LoopState.THINKING)
            
            # 1. 思考
            step.thought = await self._think(task, loop_ctx, context)
            logger.info(f"[AgentLoop] 迭代 {loop_ctx.current_iteration} 思考: {step.thought[:100] if step.thought else ''}")
            
            # 检查是否完成
            if self._check_completion(step.thought):
                step.state = LoopState.COMPLETED
                loop_ctx.final_answer = self._extract_answer(step.thought)
                loop_ctx.steps.append(step)
                break
            
            # 2. 行动
            step.state = LoopState.ACTING
            action, action_input = await self._decide_action(step.thought, available_tools)
            step.action = action
            step.action_input = action_input
            
            if not action:
                step.state = LoopState.FAILED
                loop_ctx.steps.append(step)
                break
            
            # 3. 观察
            step.state = LoopState.OBSERVING
            step.observation = await self._execute_action(action, action_input, context)
            
            loop_ctx.steps.append(step)
            logger.info(f"[AgentLoop] 迭代 {loop_ctx.current_iteration} 行动: {action}, 观察: {step.observation[:100] if step.observation else ''}")
        
        if not loop_ctx.final_answer:
            loop_ctx.final_answer = "达到最大迭代次数，任务未完成"
        
        return loop_ctx
    
    async def _think(
        self,
        task: str,
        loop_ctx: LoopContext,
        context: AgentContext,
    ) -> str:
        """思考下一步"""
        # TODO: 调用 LLM 进行思考
        # 这里返回模拟结果
        if loop_ctx.current_iteration == 1:
            return f"我需要分析任务: {task}"
        return "FINAL ANSWER: 任务分析完成"
    
    async def _decide_action(
        self,
        thought: str,
        available_tools: List[str],
    ) -> tuple:
        """决定行动"""
        # TODO: 从思考中提取行动
        return ("search", {"query": "test"})
    
    async def _execute_action(
        self,
        action: str,
        action_input: Dict,
        context: AgentContext,
    ) -> str:
        """执行行动"""
        # TODO: 调用实际工具
        return f"执行 {action} 的结果"
    
    def _check_completion(self, thought: str) -> bool:
        """检查是否完成"""
        if not thought:
            return False
        for phrase in self.config["stop_phrases"]:
            if phrase in thought:
                return True
        return False
    
    def _extract_answer(self, thought: str) -> str:
        """提取最终答案"""
        for phrase in self.config["stop_phrases"]:
            if phrase in thought:
                return thought.split(phrase)[-1].strip()
        return thought
    
    async def process(self, context: AgentContext) -> ModuleResult:
        """处理请求"""
        loop_ctx = await self.run_loop(
            task=context.user_input,
            context=context,
            available_tools=["search", "calculate"],
        )
        
        return ModuleResult.ok(
            data={
                "iterations": loop_ctx.current_iteration,
                "final_answer": loop_ctx.final_answer,
                "steps": [
                    {
                        "iteration": s.iteration,
                        "state": s.state.value,
                        "thought": s.thought,
                        "action": s.action,
                    }
                    for s in loop_ctx.steps
                ],
            },
        )
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_iterations": {
                    "type": "integer",
                    "title": "最大迭代次数",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
        }
