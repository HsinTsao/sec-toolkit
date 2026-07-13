"""Quick PoC API"""
from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...database import get_db
from ...api.deps import get_current_user
from ...models import User
from ...models.poc_log import PocAccessLog
from ...poc import poc_registry
from ...poc.base import PocRequest

router = APIRouter()


@router.get("/poc/list")
async def list_pocs():
    """list all pocs"""
    return {"pocs": poc_registry.to_list(), "categories": poc_registry.get_categories()}


@router.get("/poc/templates")
async def get_poc_templates():
    """compat with old template api"""
    return {"templates": poc_registry.to_templates()}


@router.get("/poc/{name}/preview")
async def preview_poc(
    name: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """preview poc response without depending on public /p route"""
    meta = poc_registry.get(name)
    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PoC 不存在")

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    preview_req = PocRequest(
        method="GET",
        path="",
        query_params={},
        headers={"x-quick-poc-preview": "1"},
        body=None,
        client_ip=request.client.host if request.client else "preview",
        base_url=f"{scheme}://{host}/p/{name}",
    )

    try:
        result = await meta.handler(preview_req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"预览生成失败: {exc}") from exc

    body = result.body
    content_type = result.content_type or meta.content_type

    if isinstance(body, bytes):
        if content_type.startswith("text/") or content_type in {"application/json", "application/xml"}:
            preview_body = body.decode("utf-8", errors="replace")
        else:
            preview_body = f"[binary response: {len(body)} bytes, content-type={content_type}]"
    else:
        preview_body = body

    return {
        "name": meta.name,
        "content_type": content_type,
        "status_code": result.status_code,
        "redirect_url": result.redirect_url,
        "body": preview_body,
    }


@router.get("/poc/{name}/logs")
async def get_poc_logs(
    name: str,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """get poc access logs"""
    result = await db.execute(
        select(PocAccessLog)
        .where(PocAccessLog.poc_name == name)
        .order_by(PocAccessLog.timestamp.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return {
        "logs": [
            {
                "id": r.id,
                "poc_name": r.poc_name,
                "client_ip": r.client_ip,
                "method": r.method,
                "path": r.path,
                "query_string": r.query_string,
                "headers": r.headers,
                "body": r.body,
                "user_agent": r.user_agent,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]
    }
