"""本地域名代理 API"""
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict
from urllib.parse import urlparse, urljoin
import httpx
import re
from app.modules.proxy import proxy_manager, ProxyConfig

router = APIRouter()


# ==================== 请求模型 ====================

class CreateProxyRequest(BaseModel):
    """创建代理请求"""
    local_port: int = Field(..., ge=1024, le=65535, description="本地监听端口 (1024-65535)")
    target_url: str = Field(..., description="目标服务器 URL，如 https://target.com")
    fake_host: str = Field(..., description="伪装的 Host 头，如 trusted.com")
    preserve_path: bool = Field(True, description="是否保留请求路径")
    ssl_verify: bool = Field(False, description="是否验证 SSL 证书")
    timeout: int = Field(30, ge=1, le=120, description="请求超时时间（秒）")
    custom_headers: Dict[str, str] = Field(default_factory=dict, description="自定义请求头")
    auto_start: bool = Field(True, description="是否自动启动代理")


class UpdateProxyRequest(BaseModel):
    """更新代理请求"""
    target_url: Optional[str] = Field(None, description="目标服务器 URL")
    fake_host: Optional[str] = Field(None, description="伪装的 Host 头")
    preserve_path: Optional[bool] = Field(None, description="是否保留请求路径")
    ssl_verify: Optional[bool] = Field(None, description="是否验证 SSL 证书")
    timeout: Optional[int] = Field(None, ge=1, le=120, description="请求超时时间（秒）")
    custom_headers: Optional[Dict[str, str]] = Field(None, description="自定义请求头")


class IframeProxyRequest(BaseModel):
    """iframe 代理请求"""
    target_url: str = Field(..., description="目标页面 URL")
    fake_host: Optional[str] = Field(None, description="可选的伪装 Host")
    rewrite_urls: bool = Field(True, description="是否重写页面中的相对URL")
    inject_script: Optional[str] = Field(None, description="可选的注入脚本")
    cookies: Optional[str] = Field(None, description="要携带的 Cookie（手动输入目标站点的 Cookie）")
    custom_headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="自定义请求头")


# 存储 iframe 代理配置
_iframe_configs: Dict[str, dict] = {}


# ==================== 静态路由（必须在动态路由之前） ====================

@router.get("/list")
async def list_proxies():
    """列出所有代理配置"""
    return {"proxies": proxy_manager.list_proxies()}


@router.post("/create")
async def create_proxy(req: CreateProxyRequest):
    """
    创建本地域名代理
    
    用途：
    - 绕过基于 Host 的访问控制
    - 测试同源策略相关漏洞
    - 模拟同域名请求
    
    示例：
    - 本地端口: 8888
    - 目标 URL: https://api.target.com
    - 伪装 Host: trusted-origin.com
    
    访问 http://127.0.0.1:8888/path 会将请求转发到 https://api.target.com/path，
    但 Host 头会被设置为 trusted-origin.com
    """
    config = ProxyConfig(
        local_port=req.local_port,
        target_url=req.target_url.rstrip('/'),
        fake_host=req.fake_host,
        preserve_path=req.preserve_path,
        ssl_verify=req.ssl_verify,
        timeout=req.timeout,
        custom_headers=req.custom_headers
    )
    
    result = proxy_manager.add_proxy(config)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # 自动启动
    if req.auto_start:
        start_result = await proxy_manager.start_proxy(req.local_port)
        if "error" in start_result:
            return {
                **result,
                "warning": f"代理配置已添加，但启动失败: {start_result['error']}"
            }
        return {**result, **start_result}
    
    return result


@router.post("/quick-test")
async def quick_test(req: CreateProxyRequest):
    """
    快速测试代理功能
    
    创建并启动代理，返回测试 URL
    """
    config = ProxyConfig(
        local_port=req.local_port,
        target_url=req.target_url.rstrip('/'),
        fake_host=req.fake_host,
        preserve_path=req.preserve_path,
        ssl_verify=req.ssl_verify,
        timeout=req.timeout,
        custom_headers=req.custom_headers
    )
    
    # 如果端口已存在，先移除
    if req.local_port in proxy_manager._configs:
        if req.local_port in proxy_manager._servers:
            await proxy_manager.stop_proxy(req.local_port)
        proxy_manager.remove_proxy(req.local_port)
    
    result = proxy_manager.add_proxy(config)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # 启动代理
    start_result = await proxy_manager.start_proxy(req.local_port)
    if "error" in start_result:
        raise HTTPException(status_code=500, detail=start_result["error"])
    
    return {
        "success": True,
        "message": "代理已启动",
        "local_url": f"http://127.0.0.1:{req.local_port}",
        "target_url": req.target_url,
        "fake_host": req.fake_host,
        "usage": f"在浏览器中访问 http://127.0.0.1:{req.local_port}/your-path，"
                 f"请求将被转发到 {req.target_url}/your-path，Host 头为 {req.fake_host}"
    }


# ==================== iframe 同域代理（静态路由在前） ====================

@router.get("/iframe/list")
async def list_iframe_proxies():
    """列出所有 iframe 代理配置"""
    return {
        "configs": [
            {"proxy_id": pid, **cfg}
            for pid, cfg in _iframe_configs.items()
        ]
    }


@router.post("/iframe/create")
async def create_iframe_proxy(req: IframeProxyRequest):
    """
    创建 iframe 同域代理配置
    
    返回一个代理 ID，可用于在 iframe 中加载：
    <iframe src="/api/proxy/iframe/{proxy_id}"></iframe>
    
    这样 iframe 内容与主页面同域，可以实现：
    - 跨 iframe 的 DOM 操作
    - postMessage 通信无限制
    - 读取 iframe 内的 cookie（如果同域）
    """
    import uuid
    proxy_id = str(uuid.uuid4())[:8]
    
    parsed = urlparse(req.target_url)
    
    _iframe_configs[proxy_id] = {
        "target_url": req.target_url,
        "base_url": f"{parsed.scheme}://{parsed.netloc}",
        "fake_host": req.fake_host or parsed.netloc,
        "rewrite_urls": req.rewrite_urls,
        "inject_script": req.inject_script,
        "cookies": req.cookies,
        "custom_headers": req.custom_headers or {},
    }
    
    return {
        "success": True,
        "proxy_id": proxy_id,
        "iframe_src": f"/api/proxy/iframe/{proxy_id}",
        "usage": f'<iframe src="/api/proxy/iframe/{proxy_id}"></iframe>',
        "note": "iframe 将与主页面同域，可进行 DOM 操作和 JS 通信"
    }


@router.get("/iframe/{proxy_id}")
async def iframe_proxy_get(proxy_id: str, request: Request):
    """通过代理加载 iframe 内容（GET）"""
    return await _handle_iframe_proxy(proxy_id, request, "GET")


@router.post("/iframe/{proxy_id}")
async def iframe_proxy_post(proxy_id: str, request: Request):
    """通过代理加载 iframe 内容（POST）"""
    return await _handle_iframe_proxy(proxy_id, request, "POST")


@router.delete("/iframe/{proxy_id}")
async def delete_iframe_proxy(proxy_id: str):
    """删除 iframe 代理配置"""
    if proxy_id not in _iframe_configs:
        raise HTTPException(status_code=404, detail="代理配置不存在")
    
    del _iframe_configs[proxy_id]
    return {"success": True, "message": "已删除"}


@router.get("/iframe/{proxy_id}/{path:path}")
async def iframe_proxy_path_get(proxy_id: str, path: str, request: Request):
    """通过代理加载 iframe 子路径内容（GET）"""
    return await _handle_iframe_proxy(proxy_id, request, "GET", path)


@router.post("/iframe/{proxy_id}/{path:path}")
async def iframe_proxy_path_post(proxy_id: str, path: str, request: Request):
    """通过代理加载 iframe 子路径内容（POST）"""
    return await _handle_iframe_proxy(proxy_id, request, "POST", path)


# ==================== 端口代理管理（动态路由） ====================

@router.post("/{port}/start")
async def start_proxy(port: int):
    """启动指定端口的代理服务器"""
    result = await proxy_manager.start_proxy(port)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.post("/{port}/stop")
async def stop_proxy(port: int):
    """停止指定端口的代理服务器"""
    result = await proxy_manager.stop_proxy(port)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result


@router.get("/{port}/status")
async def get_proxy_status(port: int):
    """获取代理状态"""
    result = proxy_manager.get_proxy_status(port)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.get("/{port}/logs")
async def get_proxy_logs(port: int, limit: int = 50):
    """获取代理请求日志"""
    logs = proxy_manager.get_logs(port, limit)
    return {"logs": logs, "count": len(logs)}


@router.delete("/{port}/logs")
async def clear_proxy_logs(port: int):
    """清除代理日志"""
    proxy_manager.clear_logs(port)
    return {"success": True, "message": f"端口 {port} 的日志已清除"}


@router.put("/{port}")
async def update_proxy(port: int, req: UpdateProxyRequest):
    """更新代理配置（需要重启代理才能生效）"""
    update_data = req.model_dump(exclude_none=True)
    
    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")
    
    result = proxy_manager.update_proxy(port, **update_data)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@router.delete("/{port}")
async def delete_proxy(port: int):
    """删除代理配置"""
    result = proxy_manager.remove_proxy(port)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


# ==================== 辅助函数 ====================

async def _handle_iframe_proxy(proxy_id: str, request: Request, method: str, path: str = ""):
    """处理 iframe 代理请求"""
    if proxy_id not in _iframe_configs:
        raise HTTPException(status_code=404, detail="代理配置不存在或已过期")
    
    config = _iframe_configs[proxy_id]
    
    # 构建目标 URL
    if path:
        target_url = urljoin(config["base_url"] + "/", path)
    else:
        target_url = config["target_url"]
    
    # 添加查询参数
    if request.query_params:
        target_url += ("&" if "?" in target_url else "?") + str(request.query_params)
    
    # 构建请求头
    headers = {
        "Host": config["fake_host"],
        "User-Agent": request.headers.get("User-Agent", "Mozilla/5.0"),
        "Accept": request.headers.get("Accept", "*/*"),
        "Accept-Language": request.headers.get("Accept-Language", "en-US,en;q=0.9"),
    }
    
    # 使用配置中的 Cookie（手动设置的目标站点 Cookie）
    if config.get("cookies"):
        headers["Cookie"] = config["cookies"]
    
    # 添加自定义请求头
    if config.get("custom_headers"):
        headers.update(config["custom_headers"])
    
    # 复制一些原始请求头（如果配置中没有设置的话）
    for h in ["Authorization", "Content-Type"]:
        if h in request.headers and h not in headers:
            headers[h] = request.headers[h]
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as client:
            if method == "GET":
                response = await client.get(target_url, headers=headers)
            else:
                body = await request.body()
                response = await client.post(target_url, headers=headers, content=body)
        
        content_type = response.headers.get("content-type", "")
        content = response.content
        
        # 如果是 HTML，进行处理
        if "text/html" in content_type:
            content = _process_html_content(
                content.decode("utf-8", errors="ignore"),
                proxy_id,
                config
            )
            content = content.encode("utf-8")
        
        # 构建响应头，移除阻止 iframe 的头
        response_headers = {}
        for key, value in response.headers.items():
            key_lower = key.lower()
            # 跳过这些阻止 iframe 嵌入的头
            if key_lower in ["x-frame-options", "content-security-policy", 
                            "content-security-policy-report-only", "transfer-encoding",
                            "content-encoding", "content-length"]:
                continue
            response_headers[key] = value
        
        # 添加允许 iframe 的头
        response_headers["X-Frame-Options"] = "ALLOWALL"
        response_headers["Access-Control-Allow-Origin"] = "*"
        
        return Response(
            content=content,
            status_code=response.status_code,
            headers=response_headers,
            media_type=content_type.split(";")[0] if content_type else None
        )
        
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="请求目标服务器超时")
    except httpx.ConnectError as e:
        raise HTTPException(status_code=502, detail=f"无法连接目标服务器: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"代理错误: {str(e)}")


def _process_html_content(html: str, proxy_id: str, config: dict) -> str:
    """处理 HTML 内容，重写 URL 并注入脚本"""
    
    if config.get("rewrite_urls"):
        proxy_base = f"/api/proxy/iframe/{proxy_id}"
        
        # 重写绝对 URL（同域）
        # href="/path" -> href="/api/proxy/iframe/{id}/path"
        html = re.sub(
            r'(href|src|action)=(["\'])\/(?!\/)',
            rf'\1=\2{proxy_base}/',
            html
        )
        
        # 添加 <base> 标签来处理相对 URL（如果没有的话）
        if "<base" not in html.lower():
            base_tag = f'<base href="{proxy_base}/" target="_self">'
            if "<head>" in html:
                html = html.replace("<head>", f"<head>\n{base_tag}", 1)
            elif "<HEAD>" in html:
                html = html.replace("<HEAD>", f"<HEAD>\n{base_tag}", 1)
            else:
                html = base_tag + html
    
    # 注入自定义脚本
    if config.get("inject_script"):
        script_tag = f'<script>{config["inject_script"]}</script>'
        if "</body>" in html:
            html = html.replace("</body>", f"{script_tag}\n</body>")
        elif "</BODY>" in html:
            html = html.replace("</BODY>", f"{script_tag}\n</BODY>")
        else:
            html += script_tag
    
    # 注入通信桥接脚本
    bridge_script = """
<script>
// iframe 同域通信桥接
window.__PROXY_BRIDGE__ = {
    proxyId: '""" + proxy_id + """',
    sendToParent: function(type, data) {
        if (window.parent !== window) {
            window.parent.postMessage({
                from: 'iframe-proxy',
                proxyId: this.proxyId,
                type: type,
                data: data
            }, '*');
        }
    },
    ready: function() {
        this.sendToParent('ready', { url: location.href, title: document.title });
    }
};
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        window.__PROXY_BRIDGE__.ready();
    });
} else {
    window.__PROXY_BRIDGE__.ready();
}
</script>
"""
    if "</head>" in html:
        html = html.replace("</head>", f"{bridge_script}</head>")
    elif "</HEAD>" in html:
        html = html.replace("</HEAD>", f"{bridge_script}</HEAD>")
    
    return html
