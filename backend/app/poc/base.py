"""PoC 基础类型和装饰器"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Awaitable
from fastapi import Request


@dataclass
class PocRequest:
    """传入 handler 的请求上下文"""
    method: str
    path: str
    query_params: dict
    headers: dict
    body: Optional[str]
    client_ip: str
    base_url: str

    @classmethod
    async def from_fastapi(cls, request: Request, name: str, sub_path: str = "") -> "PocRequest":
        client_ip = ""
        for h in ("CF-Connecting-IP", "X-Real-IP", "X-Forwarded-For"):
            val = request.headers.get(h)
            if val:
                client_ip = val.split(",")[0].strip()
                break
        if not client_ip and request.client:
            client_ip = request.client.host
        if client_ip and client_ip.startswith("::ffff:"):
            client_ip = client_ip[7:]

        try:
            raw = await request.body()
            body = raw.decode("utf-8", errors="replace") if raw else None
        except Exception:
            body = None

        scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
        host = request.headers.get("host", request.url.netloc)
        base_url = f"{scheme}://{host}/p/{name}"

        return cls(
            method=request.method,
            path=sub_path,
            query_params=dict(request.query_params),
            headers=dict(request.headers),
            body=body,
            client_ip=client_ip or "unknown",
            base_url=base_url,
        )


@dataclass
class PocResponse:
    """handler 返回的 HTTP 响应"""
    body: str = ""
    status_code: int = 200
    content_type: str = "text/html"
    headers: dict = field(default_factory=dict)
    redirect_url: Optional[str] = None


@dataclass
class PocMeta:
    """PoC 注册元信息"""
    name: str
    description: str
    category: str
    content_type: str
    record: bool
    usage: Optional[str]
    handler: Callable[[PocRequest], Awaitable[PocResponse]]
    hit_count: int = 0
    # OOB 规则模板字段（用于预填充 Callback PoC 规则表单）
    response_body: Optional[str] = None
    status_code: int = 200
    redirect_url: Optional[str] = None
    enable_variables: bool = False
    filename: Optional[str] = None


# 全局收集列表，registry 启动时读取
_registered_handlers: list[PocMeta] = []


def poc(
    *,
    name: str,
    description: str = "",
    category: str = "general",
    content_type: str = "text/html",
    record: bool = False,
    usage: Optional[str] = None,
    response_body: Optional[str] = None,
    status_code: int = 200,
    redirect_url: Optional[str] = None,
    enable_variables: bool = False,
    filename: Optional[str] = None,
) -> Callable:
    """PoC handler 注册装饰器

    用法::

        @poc(name="xss-test", description="XSS 弹窗", category="xss",
             response_body="<script>alert(1)</script>")
        async def handler(req: PocRequest) -> PocResponse:
            return PocResponse(body="<script>alert(1)</script>")

    模板字段（response_body / redirect_url 等）用于 OOB 规则表单预填充，
    动态部分用 {{callback_url}} 等 OOB 变量占位。
    """
    def decorator(func: Callable[[PocRequest], Awaitable[PocResponse]]) -> Callable:
        meta = PocMeta(
            name=name,
            description=description,
            category=category,
            content_type=content_type,
            record=record,
            usage=usage,
            handler=func,
            response_body=response_body,
            status_code=status_code,
            redirect_url=redirect_url,
            enable_variables=enable_variables,
            filename=filename,
        )
        _registered_handlers.append(meta)
        return func
    return decorator
