"""回调服务 - 数据库操作层"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_

from ..models.callback import CallbackToken, CallbackRecord
from ..models.poc_rule import PocRule
from ..schemas.callback import (
    TokenCreate, TokenUpdate, TokenRenew, TokenResponse,
    RecordResponse, PocRuleCreate, PocRuleUpdate, PocRuleResponse,
)
from ..config import settings


def get_callback_url(path: str) -> str:
    if settings.CALLBACK_BASE_URL:
        base = settings.CALLBACK_BASE_URL.rstrip('/')
        return f"{base}{path}"
    return path


def _build_token_response(t: CallbackToken, record_count: int = 0) -> TokenResponse:
    return TokenResponse(
        id=t.id, token=t.token, name=t.name,
        url=get_callback_url(f"/c/{t.token}"),
        created_at=t.created_at, expires_at=t.expires_at,
        is_active=bool(t.is_active), record_count=record_count,
        response_headers=t.response_headers or {},
    )


def _build_record_response(r: CallbackRecord) -> RecordResponse:
    return RecordResponse(
        id=r.id, token=r.token, timestamp=r.timestamp,
        client_ip=r.client_ip, method=r.method, path=r.path,
        query_string=r.query_string, headers=r.headers, body=r.body,
        user_agent=r.user_agent, protocol=r.protocol,
        raw_request=r.raw_request,
        is_poc_hit=bool(r.is_poc_hit), poc_rule_name=r.poc_rule_name,
        is_data_exfil=bool(r.is_data_exfil),
        exfil_data=r.exfil_data, exfil_type=r.exfil_type,
    )


def _build_rule_response(rule: PocRule, token_str: str) -> PocRuleResponse:
    return PocRuleResponse(
        id=rule.id, token_id=rule.token_id, name=rule.name,
        description=rule.description, status_code=rule.status_code,
        content_type=rule.content_type, response_body=rule.response_body,
        response_headers=rule.response_headers, redirect_url=rule.redirect_url,
        delay_ms=rule.delay_ms, enable_variables=bool(rule.enable_variables),
        is_active=bool(rule.is_active), hit_count=rule.hit_count,
        url=get_callback_url(f"/c/{token_str}/p/{rule.name}"),
        filename=rule.filename, created_at=rule.created_at,
    )


# ==================== Token CRUD ====================

async def create_token(
    db: AsyncSession, user_id: str, req: TokenCreate
) -> TokenResponse:
    token = secrets.token_urlsafe(9)[:12]
    result = await db.execute(select(CallbackToken).where(CallbackToken.token == token))
    while result.scalar_one_or_none():
        token = secrets.token_urlsafe(9)[:12]
        result = await db.execute(select(CallbackToken).where(CallbackToken.token == token))

    expires_at = None
    if req.expires_hours:
        expires_at = datetime.utcnow() + timedelta(hours=req.expires_hours)

    db_token = CallbackToken(
        token=token, name=req.name, user_id=user_id, expires_at=expires_at,
        response_headers=req.response_headers or {},
    )
    db.add(db_token)
    await db.flush()
    await db.refresh(db_token)
    return _build_token_response(db_token, 0)


async def update_token(
    db: AsyncSession, token_id: str, user_id: str, req: TokenUpdate
) -> Optional[TokenResponse]:
    """更新 Token 配置（备注名称、自定义响应头）"""
    token = await get_user_token(db, token_id, user_id)
    if not token:
        return None

    update_data = req.model_dump(exclude_unset=True)
    if 'name' in update_data:
        token.name = update_data['name']
    if 'response_headers' in update_data:
        token.response_headers = update_data['response_headers'] or {}

    await db.flush()
    await db.refresh(token)

    count_result = await db.execute(
        select(func.count()).select_from(CallbackRecord)
        .where(CallbackRecord.token_id == token.id)
    )
    count = count_result.scalar() or 0
    return _build_token_response(token, count)


async def list_tokens(db: AsyncSession, user_id: str) -> list[TokenResponse]:
    result = await db.execute(
        select(CallbackToken)
        .where(CallbackToken.user_id == user_id)
        .order_by(CallbackToken.created_at.desc())
    )
    tokens = result.scalars().all()

    token_ids = [t.id for t in tokens]
    count_map: dict[str, int] = {}
    if token_ids:
        count_result = await db.execute(
            select(CallbackRecord.token_id, func.count().label('cnt'))
            .where(CallbackRecord.token_id.in_(token_ids))
            .group_by(CallbackRecord.token_id)
        )
        count_map = {row[0]: row[1] for row in count_result.all()}

    return [_build_token_response(t, count_map.get(t.id, 0)) for t in tokens]


async def get_user_token(
    db: AsyncSession, token_id: str, user_id: str
) -> Optional[CallbackToken]:
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id, CallbackToken.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def delete_token(db: AsyncSession, token_id: str, user_id: str) -> bool:
    token = await get_user_token(db, token_id, user_id)
    if not token:
        return False
    await db.execute(delete(CallbackRecord).where(CallbackRecord.token_id == token_id))
    await db.delete(token)
    return True


async def renew_token(
    db: AsyncSession, token_id: str, user_id: str, req: TokenRenew
) -> Optional[TokenResponse]:
    token = await get_user_token(db, token_id, user_id)
    if not token:
        return None

    if req.expires_hours > 0:
        token.expires_at = datetime.utcnow() + timedelta(hours=req.expires_hours)
    else:
        token.expires_at = None
    token.is_active = 1

    await db.flush()
    await db.refresh(token)

    count_result = await db.execute(
        select(func.count()).select_from(CallbackRecord)
        .where(CallbackRecord.token_id == token.id)
    )
    count = count_result.scalar() or 0
    return _build_token_response(token, count)


# ==================== 记录查询 ====================

async def get_records(
    db: AsyncSession, token_id: str, limit: int = 100,
    keyword: Optional[str] = None,
) -> list[RecordResponse]:
    query = (
        select(CallbackRecord)
        .where(CallbackRecord.token_id == token_id)
    )
    if keyword:
        like_pattern = f"%{keyword}%"
        query = query.where(or_(
            CallbackRecord.raw_request.like(like_pattern),
            CallbackRecord.client_ip.like(like_pattern),
            CallbackRecord.exfil_data.like(like_pattern),
        ))
    result = await db.execute(
        query.order_by(CallbackRecord.timestamp.desc()).limit(limit)
    )
    return [_build_record_response(r) for r in result.scalars().all()]


async def clear_records(db: AsyncSession, token_id: str) -> int:
    result = await db.execute(
        delete(CallbackRecord).where(CallbackRecord.token_id == token_id)
    )
    return result.rowcount


async def poll_records(
    db: AsyncSession, token_id: str, since: Optional[str] = None
) -> list[RecordResponse]:
    query = select(CallbackRecord).where(CallbackRecord.token_id == token_id)
    if since:
        try:
            since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.where(CallbackRecord.timestamp > since_time)
        except Exception:
            pass
    result = await db.execute(
        query.order_by(CallbackRecord.timestamp.desc()).limit(50)
    )
    return [_build_record_response(r) for r in result.scalars().all()]


# ==================== 统计 ====================

async def get_token_stats(db: AsyncSession, token_id: str) -> dict:
    total_result = await db.execute(
        select(func.count()).select_from(CallbackRecord)
        .where(CallbackRecord.token_id == token_id)
    )
    total_count = total_result.scalar() or 0

    ip_result = await db.execute(
        select(CallbackRecord.client_ip, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.client_ip)
        .order_by(func.count().desc()).limit(10)
    )
    ip_stats = [{"ip": row[0] or "Unknown", "count": row[1]} for row in ip_result.all()]

    method_result = await db.execute(
        select(CallbackRecord.method, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.method)
    )
    method_stats = [{"method": row[0] or "Unknown", "count": row[1]} for row in method_result.all()]

    path_result = await db.execute(
        select(CallbackRecord.path, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.path)
        .order_by(func.count().desc()).limit(10)
    )
    path_stats = [{"path": row[0] or "/", "count": row[1]} for row in path_result.all()]

    ua_result = await db.execute(
        select(CallbackRecord.user_agent, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.user_agent)
        .order_by(func.count().desc()).limit(10)
    )
    ua_stats = [{"user_agent": row[0] or "Unknown", "count": row[1]} for row in ua_result.all()]

    return {
        "total": total_count,
        "by_ip": ip_stats,
        "by_method": method_stats,
        "by_path": path_stats,
        "by_user_agent": ua_stats,
    }


async def get_all_stats(db: AsyncSession, user_id: str) -> dict:
    tokens_result = await db.execute(
        select(CallbackToken).where(CallbackToken.user_id == user_id)
    )
    tokens = tokens_result.scalars().all()
    token_ids = [t.id for t in tokens]

    if not token_ids:
        return {"total_tokens": 0, "total_requests": 0, "by_token": []}

    count_result = await db.execute(
        select(CallbackRecord.token_id, func.count().label('cnt'))
        .where(CallbackRecord.token_id.in_(token_ids))
        .group_by(CallbackRecord.token_id)
    )
    count_map = {row[0]: row[1] for row in count_result.all()}
    total_requests = sum(count_map.values())

    token_stats = sorted(
        [
            {
                "token_id": t.id, "token": t.token, "name": t.name,
                "count": count_map.get(t.id, 0),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tokens
        ],
        key=lambda x: x["count"], reverse=True,
    )

    return {
        "total_tokens": len(tokens),
        "total_requests": total_requests,
        "by_token": token_stats,
    }


# ==================== PoC 规则 CRUD ====================

async def create_poc_rule(
    db: AsyncSession, token: CallbackToken, req: PocRuleCreate
) -> Optional[PocRuleResponse]:
    existing = await db.execute(
        select(PocRule).where(PocRule.token_id == token.id, PocRule.name == req.name)
    )
    if existing.scalar_one_or_none():
        return None  # 名称已存在

    rule = PocRule(
        token_id=token.id, name=req.name, description=req.description,
        status_code=req.status_code, content_type=req.content_type,
        response_body=req.response_body,
        response_headers=req.response_headers or {},
        redirect_url=req.redirect_url, delay_ms=req.delay_ms,
        enable_variables=1 if req.enable_variables else 0,
        filename=req.filename,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return _build_rule_response(rule, token.token)


async def list_poc_rules(
    db: AsyncSession, token: CallbackToken
) -> list[PocRuleResponse]:
    result = await db.execute(
        select(PocRule).where(PocRule.token_id == token.id)
        .order_by(PocRule.created_at.desc())
    )
    return [_build_rule_response(r, token.token) for r in result.scalars().all()]


async def update_poc_rule(
    db: AsyncSession, token: CallbackToken, rule_id: str, req: PocRuleUpdate
) -> Optional[PocRuleResponse]:
    result = await db.execute(
        select(PocRule).where(PocRule.id == rule_id, PocRule.token_id == token.id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return None

    update_data = req.model_dump(exclude_unset=True)
    if 'enable_variables' in update_data:
        update_data['enable_variables'] = 1 if update_data['enable_variables'] else 0
    if 'is_active' in update_data:
        update_data['is_active'] = 1 if update_data['is_active'] else 0

    for key, value in update_data.items():
        setattr(rule, key, value)

    await db.flush()
    await db.refresh(rule)
    return _build_rule_response(rule, token.token)


async def delete_poc_rule(
    db: AsyncSession, token_id: str, rule_id: str
) -> bool:
    result = await db.execute(
        delete(PocRule).where(PocRule.id == rule_id, PocRule.token_id == token_id)
    )
    return result.rowcount > 0
