"""回调服务器 API - 类似 Burp Collaborator"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime
import asyncio
import re

from ...database import get_db
from ...models.callback import CallbackToken, CallbackRecord
from ...models.poc_rule import PocRule
from ...api.deps import get_current_user
from ...models import User
from ...schemas.callback import (
    TokenCreate, TokenUpdate, TokenRenew, TokenResponse,
    RecordResponse, PocRuleCreate, PocRuleUpdate, PocRuleResponse,
)
from ...services.callback_service import (
    get_callback_url,
    create_token as svc_create_token,
    list_tokens as svc_list_tokens,
    get_user_token,
    update_token as svc_update_token,
    delete_token as svc_delete_token,
    renew_token as svc_renew_token,
    get_records as svc_get_records,
    clear_records as svc_clear_records,
    poll_records as svc_poll_records,
    get_token_stats as svc_get_token_stats,
    get_all_stats as svc_get_all_stats,
    create_poc_rule as svc_create_poc_rule,
    list_poc_rules as svc_list_poc_rules,
    update_poc_rule as svc_update_poc_rule,
    delete_poc_rule as svc_delete_poc_rule,
)

router = APIRouter()


# ==================== Token 管理 API ====================

@router.post("/tokens", response_model=TokenResponse)
async def create_token(
    req: TokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的回调 Token"""
    return await svc_create_token(db, current_user.id, req)


@router.get("/tokens", response_model=List[TokenResponse])
async def list_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有 Token"""
    return await svc_list_tokens(db, current_user.id)


@router.patch("/tokens/{token_id}", response_model=TokenResponse)
async def update_token(
    token_id: str,
    req: TokenUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新 Token 配置（备注名称、自定义响应头）"""
    result = await svc_update_token(db, token_id, current_user.id, req)
    if not result:
        raise HTTPException(status_code=404, detail="Token not found")
    return result


@router.delete("/tokens/{token_id}")
async def delete_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除 Token 及其所有记录"""
    if not await svc_delete_token(db, token_id, current_user.id):
        raise HTTPException(status_code=404, detail="Token not found")
    return {"message": "Token deleted"}


@router.patch("/tokens/{token_id}/renew", response_model=TokenResponse)
async def renew_token(
    token_id: str,
    req: TokenRenew,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """续期 Token"""
    result = await svc_renew_token(db, token_id, current_user.id, req)
    if not result:
        raise HTTPException(status_code=404, detail="Token not found")
    return result


# ==================== 统计分析 API ====================

@router.get("/tokens/{token_id}/stats")
async def get_token_stats(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Token 的统计信息"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return await svc_get_token_stats(db, token_id)


@router.get("/stats/all")
async def get_all_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户所有 Token 的汇总统计"""
    return await svc_get_all_stats(db, current_user.id)


# ==================== 记录查询 API ====================

@router.get("/tokens/{token_id}/records", response_model=List[RecordResponse])
async def get_records(
    token_id: str,
    limit: int = 100,
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Token 的回调记录，支持关键字搜索"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return await svc_get_records(db, token_id, limit, keyword=keyword)


@router.delete("/tokens/{token_id}/records")
async def clear_records(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清空 Token 的所有记录"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    deleted = await svc_clear_records(db, token_id)
    return {"deleted": deleted}


@router.get("/tokens/{token_id}/poll")
async def poll_records(
    token_id: str,
    since: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """轮询新记录"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    records = await svc_poll_records(db, token_id, since)
    return {"count": len(records), "records": records}


# ==================== PoC 规则 API ====================


@router.post("/tokens/{token_id}/rules", response_model=PocRuleResponse)
async def create_poc_rule(
    token_id: str,
    req: PocRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建 PoC 规则"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    result = await svc_create_poc_rule(db, token, req)
    if not result:
        raise HTTPException(status_code=400, detail="Rule name already exists")
    return result


@router.get("/tokens/{token_id}/rules", response_model=List[PocRuleResponse])
async def list_poc_rules(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 PoC 规则列表"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    return await svc_list_poc_rules(db, token)


@router.patch("/tokens/{token_id}/rules/{rule_id}", response_model=PocRuleResponse)
async def update_poc_rule(
    token_id: str, rule_id: str, req: PocRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新 PoC 规则"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    result = await svc_update_poc_rule(db, token, rule_id, req)
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.delete("/tokens/{token_id}/rules/{rule_id}")
async def delete_poc_rule(
    token_id: str, rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除 PoC 规则"""
    token = await get_user_token(db, token_id, current_user.id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    if not await svc_delete_poc_rule(db, token_id, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": "Rule deleted"}


# ==================== 回调接收端点（公开，无需认证）====================

def replace_variables(content: str, request: Request, client_ip: str, token: str) -> str:
    """替换响应内容中的变量"""
    if not content:
        return content

    query_params = dict(request.query_params)
    replacements = {
        '{{client_ip}}': client_ip or 'unknown',
        '{{timestamp}}': datetime.utcnow().isoformat(),
        '{{method}}': request.method,
        '{{path}}': str(request.url.path),
        '{{host}}': request.headers.get('host', 'unknown'),
        '{{user_agent}}': request.headers.get('user-agent', 'unknown'),
        '{{callback_url}}': get_callback_url(f"/c/{token}"),
        '{{attacker_ip}}': 'ATTACKER_IP',
        '{{attacker_port}}': '4444',
    }

    for var, value in replacements.items():
        content = content.replace(var, value)

    param_pattern = r'\{\{param\.(\w+)\}\}'
    for match in re.finditer(param_pattern, content):
        param_name = match.group(1)
        param_value = query_params.get(param_name, '')
        content = content.replace(match.group(0), param_value)

    return content


def _normalize_ip(ip: str) -> str:
    if ip and ip.startswith('::ffff:'):
        return ip[7:]
    return ip or ''


def get_client_ip(request: Request) -> str:
    """从请求中获取真实客户端 IP"""
    proxy_headers = [
        'CF-Connecting-IP',
        'X-Real-IP',
        'True-Client-IP',
        'X-Client-IP',
    ]

    for header in proxy_headers:
        value = request.headers.get(header)
        if value:
            ip = value.split(',')[0].strip()
            if ip:
                return _normalize_ip(ip)

    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
        if ip:
            return _normalize_ip(ip)

    if request.client and request.client.host:
        return _normalize_ip(request.client.host)

    return 'unknown'


async def handle_callback(request: Request, token: str, path: str, db: AsyncSession):
    """处理回调请求 - 始终记录所有请求"""
    result = await db.execute(
        select(CallbackToken).where(CallbackToken.token == token)
    )
    db_token = result.scalar_one_or_none()

    if not db_token:
        return PlainTextResponse("Not Found", status_code=404)

    is_expired = db_token.expires_at and db_token.expires_at < datetime.utcnow()
    client_ip = get_client_ip(request)

    try:
        body = (await request.body()).decode('utf-8', errors='replace')
    except Exception:
        body = None

    headers_dict = dict(request.headers)

    raw_lines = [
        f"{request.method} {request.url.path}{'?' + str(request.url.query) if request.url.query else ''} HTTP/1.1",
        f"Host: {request.headers.get('host', 'unknown')}"
    ]
    for k, v in headers_dict.items():
        if k.lower() != 'host':
            raw_lines.append(f"{k}: {v}")
    raw_lines.append("")
    if body:
        raw_lines.append(body)
    raw_request = "\r\n".join(raw_lines)

    query_params = dict(request.query_params)
    is_data_exfil = query_params.get('_exfil') == '1'
    exfil_type = query_params.get('_type') if is_data_exfil else None
    exfil_data = query_params.get('_data') if is_data_exfil else None

    if is_data_exfil and not exfil_data:
        for key in ['data', 'd', 'c', 'cookie', 'file', 'cmd', 'result']:
            if key in query_params:
                exfil_data = query_params[key]
                break
        if not exfil_data and body:
            exfil_data = body[:2000]

    is_poc_hit = path.startswith("p/")
    poc_rule_name = path[2:].split("/")[0] if is_poc_hit else None

    record = CallbackRecord(
        token_id=db_token.id, token=token,
        client_ip=client_ip, method=request.method,
        path=f"/{path}" if path else "/",
        query_string=str(request.url.query) if request.url.query else None,
        headers=headers_dict, body=body if body else None,
        user_agent=request.headers.get("user-agent"),
        protocol="HTTP", raw_request=raw_request,
        is_poc_hit=1 if is_poc_hit else 0,
        poc_rule_name=poc_rule_name,
        is_data_exfil=1 if is_data_exfil else 0,
        exfil_data=exfil_data, exfil_type=exfil_type,
    )
    db.add(record)
    await db.flush()

    if path.startswith("p/"):
        rule_name = path[2:].split("/")[0]
        rule_result = await db.execute(
            select(PocRule).where(
                PocRule.token_id == db_token.id,
                PocRule.name == rule_name,
                PocRule.is_active == 1
            )
        )
        rule = rule_result.scalar_one_or_none()

        if rule:
            rule.hit_count += 1
            await db.flush()

            if rule.delay_ms > 0:
                await asyncio.sleep(rule.delay_ms / 1000)

            if rule.redirect_url:
                redirect_url = rule.redirect_url
                if rule.enable_variables:
                    redirect_url = replace_variables(redirect_url, request, client_ip, token)
                return Response(
                    content="",
                    status_code=rule.status_code or 302,
                    headers={"Location": redirect_url, "Referrer-Policy": "unsafe-url"}
                )

            response_body = rule.response_body or ""
            if rule.enable_variables:
                response_body = replace_variables(response_body, request, client_ip, token)

            response_headers = dict(rule.response_headers or {})
            response_headers["Referrer-Policy"] = "unsafe-url"
            ct = rule.content_type or "text/plain"
            if ct.startswith("text/") and "charset" not in ct:
                ct = f"{ct}; charset=utf-8"
            response_headers["Content-Type"] = ct
            if rule.filename:
                response_headers["Content-Disposition"] = f'inline; filename="{rule.filename}"'

            return Response(
                content=response_body,
                status_code=rule.status_code,
                headers=response_headers
            )
        else:
            return PlainTextResponse(f"PoC Rule '{rule_name}' not found", status_code=404)

    base_headers = {"Referrer-Policy": "unsafe-url"}
    # 附加用户为该 Token 配置的自定义响应头（如 Access-Control-Allow-Origin）
    custom_headers = db_token.response_headers or {}
    for k, v in custom_headers.items():
        if k and v is not None:
            base_headers[str(k)] = str(v)

    if is_expired:
        return PlainTextResponse("Token Expired (but recorded)", status_code=410, headers=base_headers)
    return PlainTextResponse("OK", status_code=200, headers=base_headers)
