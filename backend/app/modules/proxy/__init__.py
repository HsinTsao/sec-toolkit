"""本地域名代理模块 - 绕过浏览器同源策略限制"""
import asyncio
import threading
import socket
import ssl
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse
import httpx
from aiohttp import web


@dataclass
class ProxyConfig:
    """代理配置"""
    local_port: int  # 本地监听端口
    target_url: str  # 目标 URL (如 https://target.com)
    fake_host: str   # 伪装的 Host 头 (如 trusted.com)
    enabled: bool = True
    preserve_path: bool = True  # 保留请求路径
    ssl_verify: bool = False  # 是否验证 SSL 证书
    timeout: int = 30  # 请求超时时间
    custom_headers: Dict[str, str] = field(default_factory=dict)  # 自定义请求头
    
    
@dataclass 
class ProxyLog:
    """代理请求日志"""
    timestamp: datetime
    method: str
    path: str
    target_url: str
    fake_host: str
    status_code: int
    response_time: float  # ms
    request_headers: Dict[str, str]
    response_headers: Dict[str, str]
    error: Optional[str] = None


class LocalDomainProxy:
    """本地域名代理服务器
    
    功能：
    1. 在本地端口监听 HTTP 请求
    2. 修改 Host 头后转发到目标服务器
    3. 返回目标服务器的响应
    4. 记录请求日志
    
    使用场景：
    - 绕过基于 Host 的访问控制
    - 测试同源策略相关漏洞
    - 模拟同域名请求
    """
    
    def __init__(self):
        self._configs: Dict[int, ProxyConfig] = {}  # port -> config
        self._servers: Dict[int, web.AppRunner] = {}  # port -> server runner
        self._logs: Dict[int, list] = {}  # port -> logs
        self._max_logs = 100  # 每个端口最多保留的日志数
        self._client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )

    _HOP_BY_HOP_HEADERS = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
        
    def add_proxy(self, config: ProxyConfig) -> Dict[str, Any]:
        """添加代理配置"""
        if config.local_port in self._configs:
            return {"error": f"端口 {config.local_port} 已被使用"}
        
        # 检查端口是否可用
        if not self._is_port_available(config.local_port):
            return {"error": f"端口 {config.local_port} 被占用或需要权限"}
            
        self._configs[config.local_port] = config
        self._logs[config.local_port] = []
        
        return {
            "success": True,
            "message": f"代理配置已添加，端口: {config.local_port}",
            "config": self._config_to_dict(config)
        }
    
    def remove_proxy(self, port: int) -> Dict[str, Any]:
        """移除代理配置"""
        if port not in self._configs:
            return {"error": f"端口 {port} 没有配置代理"}
        
        # 如果正在运行，先停止
        if port in self._servers:
            asyncio.create_task(self._stop_server(port))
            
        del self._configs[port]
        if port in self._logs:
            del self._logs[port]
            
        return {"success": True, "message": f"端口 {port} 代理已移除"}
    
    def update_proxy(self, port: int, **kwargs) -> Dict[str, Any]:
        """更新代理配置"""
        if port not in self._configs:
            return {"error": f"端口 {port} 没有配置代理"}
        
        config = self._configs[port]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
                
        return {
            "success": True,
            "message": "配置已更新",
            "config": self._config_to_dict(config)
        }
    
    async def start_proxy(self, port: int) -> Dict[str, Any]:
        """启动代理服务器"""
        if port not in self._configs:
            return {"error": f"端口 {port} 没有配置代理"}
        
        if port in self._servers:
            return {"error": f"端口 {port} 代理已在运行"}
        
        config = self._configs[port]
        
        try:
            # 创建 aiohttp 应用
            app = web.Application()
            app['config'] = config
            app['proxy'] = self
            
            # 添加通配路由处理所有请求
            app.router.add_route('*', '/{path:.*}', self._handle_request)
            
            # 启动服务器
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '127.0.0.1', port)
            await site.start()
            
            self._servers[port] = runner
            
            return {
                "success": True,
                "message": f"代理服务器已启动",
                "port": port,
                "local_url": f"http://127.0.0.1:{port}",
                "target": config.target_url,
                "fake_host": config.fake_host
            }
        except Exception as e:
            return {"error": f"启动失败: {str(e)}"}
    
    async def stop_proxy(self, port: int) -> Dict[str, Any]:
        """停止代理服务器"""
        if port not in self._servers:
            return {"error": f"端口 {port} 代理未运行"}
        
        await self._stop_server(port)
        return {"success": True, "message": f"端口 {port} 代理已停止"}
    
    async def _stop_server(self, port: int):
        """内部停止服务器"""
        if port in self._servers:
            await self._servers[port].cleanup()
            del self._servers[port]
    
    async def _handle_request(self, request: web.Request) -> web.Response:
        """处理代理请求"""
        config: ProxyConfig = request.app['config']
        proxy: LocalDomainProxy = request.app['proxy']
        
        start_time = datetime.now()
        
        # 构建目标 URL
        path = request.match_info.get('path', '')
        if request.query_string:
            path = f"{path}?{request.query_string}"
        
        parsed_target = urlparse(config.target_url)
        if config.preserve_path:
            target_url = f"{parsed_target.scheme}://{parsed_target.netloc}/{path}"
        else:
            target_url = config.target_url
        
        # 构建请求头
        headers = dict(request.headers)
        headers['Host'] = config.fake_host
        
        # 移除 hop-by-hop 头，避免代理层错误转发
        for key in list(headers.keys()):
            if key.lower() in self._HOP_BY_HOP_HEADERS:
                headers.pop(key, None)
        headers.pop('Content-Length', None)
        
        # 添加自定义头
        headers.update(config.custom_headers)
        
        # 读取请求体
        body = await request.read() if request.body_exists else None
        
        log_entry = ProxyLog(
            timestamp=start_time,
            method=request.method,
            path=f"/{path}",
            target_url=target_url,
            fake_host=config.fake_host,
            status_code=0,
            response_time=0,
            request_headers=dict(headers),
            response_headers={},
            error=None
        )
        
        try:
            # 发送请求到目标服务器
            response = await self._client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=False,  # 不自动跟随重定向，让客户端处理
                verify=config.ssl_verify,
                timeout=config.timeout,
            )
            
            # 计算响应时间
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds() * 1000
            
            # 更新日志
            log_entry.status_code = response.status_code
            log_entry.response_time = response_time
            log_entry.response_headers = dict(response.headers)
            
            # 构建响应头
            response_headers = dict(response.headers)
            # 移除一些不应该传递的头
            for key in list(response_headers.keys()):
                if key.lower() in self._HOP_BY_HOP_HEADERS:
                    response_headers.pop(key, None)
            response_headers.pop('content-encoding', None)
            response_headers.pop('content-length', None)
            
            # 添加 CORS 头以便浏览器能正常访问
            response_headers['Access-Control-Allow-Origin'] = '*'
            response_headers['Access-Control-Allow-Methods'] = '*'
            response_headers['Access-Control-Allow-Headers'] = '*'
            
            # 返回响应
            return web.Response(
                status=response.status_code,
                headers=response_headers,
                body=response.content
            )
            
        except httpx.TimeoutException:
            log_entry.error = "请求超时"
            log_entry.status_code = 504
            return web.Response(status=504, text="Gateway Timeout: 请求超时")
        except httpx.ConnectError as e:
            log_entry.error = f"连接失败: {str(e)}"
            log_entry.status_code = 502
            return web.Response(status=502, text=f"Bad Gateway: 连接目标服务器失败 - {str(e)}")
        except Exception as e:
            log_entry.error = str(e)
            log_entry.status_code = 500
            return web.Response(status=500, text=f"Internal Server Error: {str(e)}")
        finally:
            # 保存日志
            proxy._add_log(config.local_port, log_entry)
    
    def _add_log(self, port: int, log: ProxyLog):
        """添加日志"""
        if port not in self._logs:
            self._logs[port] = []
        
        self._logs[port].insert(0, log)
        
        # 限制日志数量
        if len(self._logs[port]) > self._max_logs:
            self._logs[port] = self._logs[port][:self._max_logs]
    
    def get_logs(self, port: int, limit: int = 50) -> list:
        """获取代理日志"""
        if port not in self._logs:
            return []
        return [self._log_to_dict(log) for log in self._logs[port][:limit]]
    
    def clear_logs(self, port: int):
        """清除日志"""
        if port in self._logs:
            self._logs[port] = []
    
    def list_proxies(self) -> list:
        """列出所有代理配置"""
        result = []
        for port, config in self._configs.items():
            info = self._config_to_dict(config)
            info['running'] = port in self._servers
            info['log_count'] = len(self._logs.get(port, []))
            result.append(info)
        return result
    
    def get_proxy_status(self, port: int) -> Dict[str, Any]:
        """获取代理状态"""
        if port not in self._configs:
            return {"error": f"端口 {port} 没有配置代理"}
        
        config = self._configs[port]
        return {
            "config": self._config_to_dict(config),
            "running": port in self._servers,
            "log_count": len(self._logs.get(port, [])),
            "local_url": f"http://127.0.0.1:{port}" if port in self._servers else None
        }
    
    def _is_port_available(self, port: int) -> bool:
        """检查端口是否可用"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return True
        except:
            return False
    
    def _config_to_dict(self, config: ProxyConfig) -> dict:
        """配置转字典"""
        return {
            "local_port": config.local_port,
            "target_url": config.target_url,
            "fake_host": config.fake_host,
            "enabled": config.enabled,
            "preserve_path": config.preserve_path,
            "ssl_verify": config.ssl_verify,
            "timeout": config.timeout,
            "custom_headers": config.custom_headers
        }
    
    def _log_to_dict(self, log: ProxyLog) -> dict:
        """日志转字典"""
        return {
            "timestamp": log.timestamp.isoformat(),
            "method": log.method,
            "path": log.path,
            "target_url": log.target_url,
            "fake_host": log.fake_host,
            "status_code": log.status_code,
            "response_time": round(log.response_time, 2),
            "request_headers": log.request_headers,
            "response_headers": log.response_headers,
            "error": log.error
        }


# 全局代理管理器实例
proxy_manager = LocalDomainProxy()

