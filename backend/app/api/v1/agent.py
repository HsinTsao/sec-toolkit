"""
Agent 配置 API

提供 Agent 配置管理功能：
- System Prompt 配置
- 模块启用/禁用
- Agent 参数调整
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

from ...database import get_db
from ...models import User, AgentConfig, DEFAULT_SYSTEM_PROMPT
from ..deps import get_current_user

router = APIRouter(prefix="/agent", tags=["Agent 配置"])
logger = logging.getLogger(__name__)


# ==================== Schemas ====================

class AgentConfigResponse(BaseModel):
    """Agent 配置响应"""
    system_prompt: Optional[str] = None
    system_prompt_enabled: bool = False
    modules_config: Dict[str, Any] = Field(default_factory=dict)
    temperature: str = "0.7"
    max_tokens: str = "2048"
    default_system_prompt: str = DEFAULT_SYSTEM_PROMPT


class SystemPromptUpdate(BaseModel):
    """System Prompt 更新请求"""
    system_prompt: Optional[str] = None
    enabled: bool = False


class ModulesConfigUpdate(BaseModel):
    """模块配置更新请求"""
    modules_config: Dict[str, Any]


class AgentParamsUpdate(BaseModel):
    """Agent 参数更新请求"""
    temperature: Optional[str] = None
    max_tokens: Optional[str] = None


# ==================== Helper Functions ====================

async def get_or_create_agent_config(user_id: str, db: AsyncSession) -> AgentConfig:
    """获取或创建用户的 Agent 配置"""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.user_id == user_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        config = AgentConfig(user_id=user_id)
        db.add(config)
        await db.commit()
        await db.refresh(config)
    
    return config


# ==================== API Endpoints ====================

@router.get("/config", response_model=AgentConfigResponse)
async def get_agent_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的 Agent 配置
    """
    config = await get_or_create_agent_config(current_user.id, db)
    
    return AgentConfigResponse(
        system_prompt=config.system_prompt,
        system_prompt_enabled=config.system_prompt_enabled,
        modules_config=config.modules_config or {},
        temperature=config.temperature or "0.7",
        max_tokens=config.max_tokens or "2048",
        default_system_prompt=DEFAULT_SYSTEM_PROMPT,
    )


@router.put("/system-prompt")
async def update_system_prompt(
    request: SystemPromptUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新 System Prompt 配置
    """
    config = await get_or_create_agent_config(current_user.id, db)
    
    config.system_prompt = request.system_prompt
    config.system_prompt_enabled = request.enabled
    
    await db.commit()
    await db.refresh(config)
    
    logger.info(f"用户 {current_user.username} 更新了 System Prompt, enabled={request.enabled}")
    
    return {
        "message": "System Prompt 已更新",
        "system_prompt": config.system_prompt,
        "enabled": config.system_prompt_enabled,
    }


@router.put("/modules")
async def update_modules_config(
    request: ModulesConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新模块配置
    
    格式示例：
    {
        "rag": {"enabled": true, "top_k": 5},
        "mcp": {"enabled": false},
        "workflow": {"enabled": false}
    }
    """
    config = await get_or_create_agent_config(current_user.id, db)
    
    # 合并配置
    current_modules = config.modules_config or {}
    current_modules.update(request.modules_config)
    config.modules_config = current_modules
    
    await db.commit()
    await db.refresh(config)
    
    logger.info(f"用户 {current_user.username} 更新了模块配置")
    
    return {
        "message": "模块配置已更新",
        "modules_config": config.modules_config,
    }


@router.put("/params")
async def update_agent_params(
    request: AgentParamsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新 Agent 参数
    """
    config = await get_or_create_agent_config(current_user.id, db)
    
    if request.temperature is not None:
        # 验证温度值
        try:
            temp = float(request.temperature)
            if not 0 <= temp <= 2:
                raise ValueError("温度值应在 0-2 之间")
            config.temperature = request.temperature
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    if request.max_tokens is not None:
        # 验证 max_tokens
        try:
            tokens = int(request.max_tokens)
            if not 1 <= tokens <= 32000:
                raise ValueError("max_tokens 应在 1-32000 之间")
            config.max_tokens = request.max_tokens
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    await db.commit()
    await db.refresh(config)
    
    logger.info(f"用户 {current_user.username} 更新了 Agent 参数")
    
    return {
        "message": "Agent 参数已更新",
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
    }


@router.post("/reset")
async def reset_agent_config(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    重置 Agent 配置为默认值
    """
    config = await get_or_create_agent_config(current_user.id, db)
    
    config.system_prompt = None
    config.system_prompt_enabled = False
    config.modules_config = {}
    config.temperature = "0.7"
    config.max_tokens = "2048"
    
    await db.commit()
    
    logger.info(f"用户 {current_user.username} 重置了 Agent 配置")
    
    return {"message": "Agent 配置已重置"}
