"""反弹 Shell 监听 API"""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from typing import Optional
import asyncio
import logging

from ...api.deps import get_current_user
from ...models import User
from ...utils.security import decode_token
from ...modules.revshell import (
    RevShellManager,
    PAYLOAD_TEMPLATES,
    UPGRADE_COMMANDS,
    generate_payload,
    generate_all_payloads,
    get_listener_commands,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== Schemas ====================

class ListenerCreate(BaseModel):
    port: int


class PayloadGenerate(BaseModel):
    template_id: str
    ip: str
    port: int
    shell: str = "/bin/bash"


class PayloadGenerateAll(BaseModel):
    ip: str
    port: int


# ==================== 监听管理 ====================

@router.post("/listeners")
async def start_listener(
    req: ListenerCreate,
    current_user: User = Depends(get_current_user),
):
    """启动反弹 Shell 监听"""
    manager = RevShellManager.get_instance()
    try:
        listener = await manager.start_listener(req.port)
        return {"message": f"监听已启动: 0.0.0.0:{req.port}", "listener": listener.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/listeners/{port}")
async def stop_listener(
    port: int,
    current_user: User = Depends(get_current_user),
):
    """停止监听"""
    manager = RevShellManager.get_instance()
    try:
        await manager.stop_listener(port)
        return {"message": f"监听已停止: 端口 {port}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/listeners")
async def list_listeners(
    current_user: User = Depends(get_current_user),
):
    """获取所有监听"""
    manager = RevShellManager.get_instance()
    return {"listeners": manager.get_listeners()}


# ==================== 会话管理 ====================

@router.get("/sessions")
async def list_sessions(
    port: Optional[int] = None,
    current_user: User = Depends(get_current_user),
):
    """获取所有反弹 Shell 会话"""
    manager = RevShellManager.get_instance()
    return {"sessions": manager.get_sessions(port)}


@router.delete("/sessions/{session_id}")
async def kill_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """断开指定会话"""
    manager = RevShellManager.get_instance()
    try:
        await manager.kill_session(session_id)
        return {"message": f"会话 {session_id} 已断开"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ==================== WebSocket 终端 ====================

@router.websocket("/sessions/{session_id}/terminal")
async def terminal_ws(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
):
    """WebSocket 终端交互，通过 query 参数传递 JWT token 鉴权"""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001, reason="认证失败")
        return

    manager = RevShellManager.get_instance()
    session = manager.sessions.get(session_id)
    if not session:
        await websocket.close(code=4004, reason="会话不存在")
        return

    await websocket.accept()

    session._websockets.add(websocket)

    history = session.get_output_history()
    if history:
        try:
            await websocket.send_bytes(history)
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_bytes()
            await session.write(data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
    finally:
        session._websockets.discard(websocket)


# ==================== Payload 生成 ====================

@router.get("/payloads")
async def get_payload_templates(
    current_user: User = Depends(get_current_user),
):
    """获取所有 Payload 模板"""
    templates = []
    for tid, t in PAYLOAD_TEMPLATES.items():
        templates.append({
            "id": tid,
            "name": t["name"],
            "platform": t["platform"],
            "command_template": t["command"],
        })
    return {"templates": templates}


@router.post("/payloads/generate")
async def generate_single_payload(
    req: PayloadGenerate,
    current_user: User = Depends(get_current_user),
):
    """生成指定 Payload"""
    result = generate_payload(req.template_id, req.ip, req.port, req.shell)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/payloads/generate-all")
async def generate_all(
    req: PayloadGenerateAll,
    current_user: User = Depends(get_current_user),
):
    """批量生成所有 Payload"""
    return {"payloads": generate_all_payloads(req.ip, req.port)}


@router.get("/payloads/listener-commands")
async def get_listener_cmds(
    port: int = Query(...),
    current_user: User = Depends(get_current_user),
):
    """获取本地监听命令"""
    return {"commands": get_listener_commands(port)}


@router.get("/payloads/upgrade-commands")
async def get_upgrade_cmds(
    current_user: User = Depends(get_current_user),
):
    """获取 Shell 升级命令"""
    return {"commands": UPGRADE_COMMANDS}
