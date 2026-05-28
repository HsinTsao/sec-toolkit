"""Quick PoC API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...database import get_db
from ...api.deps import get_current_user
from ...models import User
from ...models.poc_log import PocAccessLog
from ...poc import poc_registry

router = APIRouter()


@router.get("/poc/list")
async def list_pocs():
    """list all pocs"""
    return {"pocs": poc_registry.to_list(), "categories": poc_registry.get_categories()}


@router.get("/poc/templates")
async def get_poc_templates():
    """compat with old template api"""
    return {"templates": poc_registry.to_templates()}


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
                "user_agent": r.user_agent,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
            for r in rows
        ]
    }
