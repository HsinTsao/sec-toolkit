"""
Workflow 引擎模块

提供多步骤任务编排能力：
1. 定义工作流步骤
2. 条件分支
3. 循环执行
4. 错误处理
"""
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from .base import AgentModule, AgentContext, ModuleResult

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    """步骤类型"""
    TOOL = "tool"           # 工具调用
    LLM = "llm"             # LLM 调用
    CONDITION = "condition"  # 条件判断
    LOOP = "loop"           # 循环
    PARALLEL = "parallel"    # 并行执行


@dataclass
class WorkflowStep:
    """工作流步骤"""
    id: str
    name: str
    type: StepType
    config: Dict[str, Any] = field(default_factory=dict)
    next_step: Optional[str] = None
    on_error: Optional[str] = None


@dataclass
class Workflow:
    """工作流定义"""
    id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    start_step: str
    variables: Dict[str, Any] = field(default_factory=dict)


class WorkflowModule(AgentModule):
    """
    工作流引擎模块
    
    支持定义和执行多步骤工作流。
    """
    
    name = "workflow"
    description = "工作流引擎 - 多步骤任务编排"
    version = "1.0.0"
    
    # 预定义工作流
    BUILTIN_WORKFLOWS = {
        "security_scan": Workflow(
            id="security_scan",
            name="安全扫描",
            description="对目标进行全面安全扫描",
            steps=[
                WorkflowStep(
                    id="dns_lookup",
                    name="DNS 查询",
                    type=StepType.TOOL,
                    config={"tool": "dns_lookup"},
                    next_step="whois",
                ),
                WorkflowStep(
                    id="whois",
                    name="WHOIS 查询",
                    type=StepType.TOOL,
                    config={"tool": "whois_lookup"},
                    next_step="summary",
                ),
                WorkflowStep(
                    id="summary",
                    name="生成报告",
                    type=StepType.LLM,
                    config={"prompt": "总结安全扫描结果"},
                ),
            ],
            start_step="dns_lookup",
        ),
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._workflows: Dict[str, Workflow] = dict(self.BUILTIN_WORKFLOWS)
        self._running: Dict[str, Dict] = {}  # 运行中的工作流实例
    
    async def register_workflow(self, workflow: Workflow) -> bool:
        """注册工作流"""
        self._workflows[workflow.id] = workflow
        logger.info(f"[Workflow] 注册工作流: {workflow.name}")
        return True
    
    async def list_workflows(self) -> List[Dict[str, Any]]:
        """列出所有工作流"""
        return [
            {
                "id": w.id,
                "name": w.name,
                "description": w.description,
                "step_count": len(w.steps),
            }
            for w in self._workflows.values()
        ]
    
    async def execute(
        self,
        workflow_id: str,
        inputs: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """
        执行工作流
        
        Args:
            workflow_id: 工作流 ID
            inputs: 输入参数
            context: Agent 上下文
            
        Returns:
            执行结果
        """
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return {"error": f"工作流不存在: {workflow_id}"}
        
        # 初始化变量
        variables = {**workflow.variables, **inputs}
        results = []
        
        # 执行步骤
        current_step_id = workflow.start_step
        max_steps = 100  # 防止无限循环
        step_count = 0
        
        while current_step_id and step_count < max_steps:
            step = next(
                (s for s in workflow.steps if s.id == current_step_id),
                None
            )
            if not step:
                break
            
            logger.info(f"[Workflow] 执行步骤: {step.name}")
            
            try:
                result = await self._execute_step(step, variables, context)
                results.append({
                    "step_id": step.id,
                    "step_name": step.name,
                    "result": result,
                })
                
                # 更新变量
                if isinstance(result, dict):
                    variables.update(result)
                
                current_step_id = step.next_step
                
            except Exception as e:
                logger.error(f"[Workflow] 步骤执行失败: {step.name}, {e}")
                if step.on_error:
                    current_step_id = step.on_error
                else:
                    return {
                        "error": str(e),
                        "failed_step": step.id,
                        "results": results,
                    }
            
            step_count += 1
        
        return {
            "success": True,
            "results": results,
            "variables": variables,
        }
    
    async def _execute_step(
        self,
        step: WorkflowStep,
        variables: Dict[str, Any],
        context: AgentContext,
    ) -> Any:
        """执行单个步骤"""
        if step.type == StepType.TOOL:
            # TODO: 调用工具
            tool_name = step.config.get("tool")
            logger.info(f"[Workflow] 调用工具: {tool_name}")
            return {"tool": tool_name, "status": "executed"}
        
        elif step.type == StepType.LLM:
            # TODO: 调用 LLM
            prompt = step.config.get("prompt", "")
            logger.info(f"[Workflow] 调用 LLM: {prompt[:50]}")
            return {"llm_response": "LLM 调用未实现"}
        
        elif step.type == StepType.CONDITION:
            # TODO: 条件判断
            return {"branch": "default"}
        
        return {"status": "unknown_step_type"}
    
    async def process(self, context: AgentContext) -> ModuleResult:
        """处理请求"""
        workflows = await self.list_workflows()
        return ModuleResult.ok(data={"workflows": workflows})
    
    def get_config_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_steps": {
                    "type": "integer",
                    "title": "最大步骤数",
                    "default": 100,
                },
            },
        }
