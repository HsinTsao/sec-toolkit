"""
安全的 HTTP 客户端工具

提供带安全防护的 HTTP 请求能力，包括：
- SSRF 防护（禁止访问内网地址）
- 协议限制（只允许 http/https）
- 超时控制
- 响应大小限制
- 重定向限制
"""

import re
import socket
import ipaddress
from urllib.parse import urlparse
from typing import Optional, Dict, Any
import httpx


# ==================== 安全配置 ====================

# 禁止访问的内网 IP 段
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # localhost
    ipaddress.ip_network("10.0.0.0/8"),       # 私有网络
    ipaddress.ip_network("172.16.0.0/12"),    # 私有网络
    ipaddress.ip_network("192.168.0.0/16"),   # 私有网络
    ipaddress.ip_network("169.254.0.0/16"),   # 链路本地
    ipaddress.ip_network("::1/128"),          # IPv6 localhost
    ipaddress.ip_network("fc00::/7"),         # IPv6 私有
    ipaddress.ip_network("fe80::/10"),        # IPv6 链路本地
]

# 禁止访问的主机名
BLOCKED_HOSTNAMES = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",  # GCP 元数据服务
    "169.254.169.254",           # AWS/云厂商元数据服务
]

# 允许的协议
ALLOWED_SCHEMES = ["http", "https"]

# 默认配置
DEFAULT_TIMEOUT = 15.0
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_MAX_RESPONSE_SIZE = 5 * 1024 * 1024  # 5MB
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


# ==================== 安全检查 ====================

class SSRFError(Exception):
    """SSRF 安全错误"""
    pass


def is_ip_blocked(ip: str) -> bool:
    """检查 IP 是否在禁止列表中"""
    try:
        ip_obj = ipaddress.ip_address(ip)
        for blocked_range in BLOCKED_IP_RANGES:
            if ip_obj in blocked_range:
                return True
        return False
    except ValueError:
        return False


def validate_url(url: str) -> str:
    """
    验证 URL 安全性
    
    Args:
        url: 要验证的 URL
        
    Returns:
        清理后的 URL
        
    Raises:
        SSRFError: 如果 URL 不安全
    """
    if not url:
        raise SSRFError("URL 不能为空")
    
    # 解析 URL
    try:
        parsed = urlparse(url)
    except Exception:
        raise SSRFError("无效的 URL 格式")
    
    # 检查协议
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SSRFError(f"不允许的协议: {parsed.scheme}，仅支持 http/https")
    
    # 获取主机名
    hostname = parsed.hostname
    if not hostname:
        raise SSRFError("URL 缺少主机名")
    
    # 检查主机名黑名单
    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise SSRFError(f"禁止访问的主机: {hostname}")
    
    # 解析 IP 并检查
    try:
        # 尝试直接解析为 IP
        if is_ip_blocked(hostname):
            raise SSRFError(f"禁止访问内网地址: {hostname}")
        
        # DNS 解析检查
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, type_, proto, canonname, sockaddr in resolved_ips:
            ip = sockaddr[0]
            if is_ip_blocked(ip):
                raise SSRFError(f"域名 {hostname} 解析到禁止的内网地址: {ip}")
    except socket.gaierror:
        raise SSRFError(f"无法解析域名: {hostname}")
    except SSRFError:
        raise
    except Exception as e:
        raise SSRFError(f"URL 验证失败: {str(e)}")
    
    return url


# ==================== HTTP 客户端 ====================

async def safe_fetch(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    max_size: int = DEFAULT_MAX_RESPONSE_SIZE,
    verify_ssl: bool = True,
) -> httpx.Response:
    """
    安全的 HTTP 请求
    
    Args:
        url: 请求 URL
        method: HTTP 方法
        headers: 请求头
        timeout: 超时时间（秒）
        max_redirects: 最大重定向次数
        max_size: 最大响应大小（字节）
        verify_ssl: 是否验证 SSL 证书
        
    Returns:
        httpx.Response 对象
        
    Raises:
        SSRFError: 如果 URL 不安全
        httpx.HTTPError: HTTP 请求错误
    """
    # 安全验证
    validated_url = validate_url(url)
    
    # 默认请求头
    default_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        default_headers.update(headers)
    
    # 发起请求
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        max_redirects=max_redirects,
        verify=verify_ssl,
    ) as client:
        response = await client.request(
            method=method,
            url=validated_url,
            headers=default_headers,
        )
        
        # 检查响应大小
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            raise SSRFError(f"响应大小超限: {content_length} > {max_size}")
        
        return response


async def fetch_webpage(url: str, timeout: float = DEFAULT_TIMEOUT) -> Optional[str]:
    """
    获取网页内容
    
    Args:
        url: 网页 URL
        timeout: 超时时间
        
    Returns:
        网页 HTML 内容，失败返回 None
    """
    try:
        response = await safe_fetch(url, timeout=timeout)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"获取网页失败: {url}, 错误: {e}")
    return None


# ==================== 网页信息提取 ====================

def extract_meta_info(html: str) -> Dict[str, str]:
    """
    从 HTML 中提取 meta 信息
    
    Args:
        html: HTML 内容
        
    Returns:
        包含 meta 信息的字典
    """
    meta_info = {
        "title": "",
        "description": "",
        "keywords": "",
        "og_title": "",
        "og_description": "",
        "og_site_name": "",
        "og_image": "",
    }
    
    if not html:
        return meta_info
    
    # 提取 title
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        meta_info["title"] = title_match.group(1).strip()
    
    # 提取 meta description
    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', 
        html, re.IGNORECASE
    )
    if not desc_match:
        desc_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', 
            html, re.IGNORECASE
        )
    if desc_match:
        meta_info["description"] = desc_match.group(1).strip()
    
    # 提取 meta keywords
    kw_match = re.search(
        r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']+)["\']', 
        html, re.IGNORECASE
    )
    if not kw_match:
        kw_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']keywords["\']', 
            html, re.IGNORECASE
        )
    if kw_match:
        meta_info["keywords"] = kw_match.group(1).strip()
    
    # 提取 og:title
    og_title_match = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', 
        html, re.IGNORECASE
    )
    if not og_title_match:
        og_title_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', 
            html, re.IGNORECASE
        )
    if og_title_match:
        meta_info["og_title"] = og_title_match.group(1).strip()
    
    # 提取 og:description
    og_desc_match = re.search(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', 
        html, re.IGNORECASE
    )
    if not og_desc_match:
        og_desc_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']', 
            html, re.IGNORECASE
        )
    if og_desc_match:
        meta_info["og_description"] = og_desc_match.group(1).strip()
    
    # 提取 og:site_name
    og_site_match = re.search(
        r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']', 
        html, re.IGNORECASE
    )
    if not og_site_match:
        og_site_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name["\']', 
            html, re.IGNORECASE
        )
    if og_site_match:
        meta_info["og_site_name"] = og_site_match.group(1).strip()
    
    # 提取 og:image
    og_image_match = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', 
        html, re.IGNORECASE
    )
    if not og_image_match:
        og_image_match = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', 
            html, re.IGNORECASE
        )
    if og_image_match:
        meta_info["og_image"] = og_image_match.group(1).strip()
    
    return meta_info


async def fetch_webpage_meta(url: str) -> Dict[str, str]:
    """
    获取网页的 meta 信息（带安全防护）
    
    Args:
        url: 网页 URL
        
    Returns:
        包含 meta 信息的字典
    """
    html = await fetch_webpage(url)
    return extract_meta_info(html) if html else {}


def build_summary_from_meta(title: str, url: str, meta: Dict[str, str]) -> str:
    """
    根据 meta 信息构建摘要
    
    Args:
        title: 标题
        url: URL
        meta: meta 信息字典
        
    Returns:
        构建的摘要文本
    """
    parts = []
    
    # 优先使用 og:description 或 description
    description = meta.get("og_description") or meta.get("description") or ""
    if description:
        parts.append(description)
    
    # 添加关键词信息
    keywords = meta.get("keywords", "")
    if keywords and len(keywords) < 200:
        parts.append(f"关键词: {keywords}")
    
    # 添加站点信息
    site_name = meta.get("og_site_name", "")
    if site_name:
        parts.append(f"来源: {site_name}")
    
    return "\n".join(parts) if parts else ""

