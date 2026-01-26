#!/usr/bin/env python3
"""
Hosts 劫持代理服务器

用于配合 hosts 文件修改，实现完全的同域请求（自动携带 Cookie）

使用方法：
1. 修改 hosts 文件：127.0.0.1 target.com
2. 运行此脚本：sudo python3 hosts_proxy.py --target-ip 93.184.216.34 --domain target.com
3. 浏览器访问 http://target.com，Cookie 会自动携带
"""

import argparse
import asyncio
from aiohttp import web
import httpx
from datetime import datetime


class HostsProxy:
    def __init__(self, target_ip: str, domain: str, target_port: int = 80, 
                 use_https: bool = False, listen_port: int = 80):
        self.target_ip = target_ip
        self.domain = domain
        self.target_port = target_port
        self.use_https = use_https
        self.listen_port = listen_port
        self.logs = []
        
    def get_target_url(self, path: str) -> str:
        scheme = "https" if self.use_https else "http"
        port_str = "" if (self.target_port == 80 and not self.use_https) or \
                        (self.target_port == 443 and self.use_https) else f":{self.target_port}"
        return f"{scheme}://{self.target_ip}{port_str}{path}"
    
    async def handle_request(self, request: web.Request) -> web.Response:
        start_time = datetime.now()
        
        # 构建目标 URL
        path = request.path
        if request.query_string:
            path = f"{path}?{request.query_string}"
        target_url = self.get_target_url(path)
        
        # 复制请求头，修改 Host
        headers = dict(request.headers)
        headers['Host'] = self.domain
        
        # 移除一些代理相关的头
        for h in ['Transfer-Encoding', 'Content-Length', 'Connection']:
            headers.pop(h, None)
        
        # 读取请求体
        body = await request.read() if request.body_exists else None
        
        log_entry = {
            "time": start_time.strftime("%H:%M:%S"),
            "method": request.method,
            "path": path,
            "status": 0,
            "ms": 0,
        }
        
        try:
            async with httpx.AsyncClient(verify=False, timeout=30) as client:
                response = await client.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    content=body,
                    follow_redirects=False
                )
            
            # 计算响应时间
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            log_entry["status"] = response.status_code
            log_entry["ms"] = round(response_time)
            
            # 构建响应头
            response_headers = dict(response.headers)
            for h in ['transfer-encoding', 'content-encoding', 'content-length']:
                response_headers.pop(h, None)
            
            print(f"[{log_entry['time']}] {request.method} {path} -> {response.status_code} ({log_entry['ms']}ms)")
            
            return web.Response(
                status=response.status_code,
                headers=response_headers,
                body=response.content
            )
            
        except httpx.TimeoutException:
            log_entry["status"] = 504
            print(f"[{log_entry['time']}] {request.method} {path} -> TIMEOUT")
            return web.Response(status=504, text="Gateway Timeout")
        except Exception as e:
            log_entry["status"] = 502
            print(f"[{log_entry['time']}] {request.method} {path} -> ERROR: {e}")
            return web.Response(status=502, text=f"Bad Gateway: {e}")
        finally:
            self.logs.append(log_entry)
            if len(self.logs) > 100:
                self.logs = self.logs[-100:]
    
    async def run(self):
        app = web.Application()
        app.router.add_route('*', '/{path:.*}', self.handle_request)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, '0.0.0.0', self.listen_port)
        
        print("=" * 60)
        print("🚀 Hosts 劫持代理服务器")
        print("=" * 60)
        print(f"📍 监听端口: {self.listen_port}")
        print(f"🎯 目标 IP:  {self.target_ip}:{self.target_port}")
        print(f"🏷️  域名:    {self.domain}")
        print("=" * 60)
        print()
        print("📝 请确保已修改 hosts 文件:")
        print(f"   127.0.0.1\t{self.domain}")
        print()
        print("🌐 现在可以在浏览器中访问:")
        print(f"   http://{self.domain}/")
        print()
        print("✨ Cookie 将自动携带（包括 SameSite=Lax）")
        print()
        print("按 Ctrl+C 停止服务器")
        print("-" * 60)
        
        await site.start()
        
        # 保持运行
        while True:
            await asyncio.sleep(3600)


def main():
    parser = argparse.ArgumentParser(
        description='Hosts 劫持代理服务器 - 用于绕过 SameSite Cookie 限制',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 代理 example.com (先用 dig 或 nslookup 查询真实 IP)
  sudo python3 hosts_proxy.py --target-ip 93.184.216.34 --domain example.com
  
  # 代理 HTTPS 站点
  sudo python3 hosts_proxy.py --target-ip 93.184.216.34 --domain example.com --https
  
  # 使用自定义端口
  sudo python3 hosts_proxy.py --target-ip 93.184.216.34 --domain example.com --port 8080

注意: 监听 80/443 端口需要 root 权限 (sudo)
"""
    )
    
    parser.add_argument('--target-ip', '-t', required=True,
                        help='目标服务器的真实 IP 地址')
    parser.add_argument('--domain', '-d', required=True,
                        help='要劫持的域名 (如 example.com)')
    parser.add_argument('--port', '-p', type=int, default=80,
                        help='本地监听端口 (默认: 80)')
    parser.add_argument('--target-port', type=int, default=None,
                        help='目标服务器端口 (默认: 80 或 443)')
    parser.add_argument('--https', action='store_true',
                        help='目标使用 HTTPS')
    
    args = parser.parse_args()
    
    target_port = args.target_port
    if target_port is None:
        target_port = 443 if args.https else 80
    
    proxy = HostsProxy(
        target_ip=args.target_ip,
        domain=args.domain,
        target_port=target_port,
        use_https=args.https,
        listen_port=args.port
    )
    
    try:
        asyncio.run(proxy.run())
    except KeyboardInterrupt:
        print("\n\n👋 代理服务器已停止")
    except PermissionError:
        print(f"\n❌ 错误: 无法监听端口 {args.port}")
        print("💡 提示: 监听 80/443 端口需要 root 权限，请使用 sudo 运行")
        print(f"   sudo python3 {__file__} --target-ip {args.target_ip} --domain {args.domain}")


if __name__ == '__main__':
    main()

