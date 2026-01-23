"""书签路由"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
import requests
import re
import socket
import ipaddress
from urllib.parse import urljoin, urlparse

from ...database import get_db
from ...models import User, Bookmark
from ...schemas import BookmarkCreate, BookmarkUpdate, BookmarkResponse
from ...api.deps import get_current_user

router = APIRouter()


# ==================== SSRF 防护 ====================

# 禁止访问的私有/内部 IP 范围
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),       # Loopback
    ipaddress.ip_network('10.0.0.0/8'),        # Private A
    ipaddress.ip_network('172.16.0.0/12'),     # Private B
    ipaddress.ip_network('192.168.0.0/16'),    # Private C
    ipaddress.ip_network('169.254.0.0/16'),    # Link-local
    ipaddress.ip_network('0.0.0.0/8'),         # Current network
    ipaddress.ip_network('100.64.0.0/10'),     # Carrier-grade NAT
    ipaddress.ip_network('192.0.0.0/24'),      # IETF Protocol
    ipaddress.ip_network('192.0.2.0/24'),      # TEST-NET-1
    ipaddress.ip_network('198.51.100.0/24'),   # TEST-NET-2
    ipaddress.ip_network('203.0.113.0/24'),    # TEST-NET-3
    ipaddress.ip_network('224.0.0.0/4'),       # Multicast
    ipaddress.ip_network('240.0.0.0/4'),       # Reserved
    ipaddress.ip_network('255.255.255.255/32'), # Broadcast
    # IPv6
    ipaddress.ip_network('::1/128'),           # Loopback
    ipaddress.ip_network('fc00::/7'),          # Unique local
    ipaddress.ip_network('fe80::/10'),         # Link-local
    ipaddress.ip_network('ff00::/8'),          # Multicast
]

# 禁止的主机名
BLOCKED_HOSTNAMES = [
    'localhost',
    'localhost.localdomain',
    '127.0.0.1',
    '::1',
    '0.0.0.0',
    'metadata.google.internal',      # GCP metadata
    'metadata.google.com',
    '169.254.169.254',               # AWS/Azure/GCP metadata
]

# 允许的协议
ALLOWED_SCHEMES = ['http', 'https']


def is_ip_blocked(ip_str: str) -> bool:
    """检查 IP 是否在禁止范围内"""
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in BLOCKED_IP_RANGES:
            if ip in network:
                return True
        return False
    except ValueError:
        return False


def is_safe_url(url: str) -> tuple[bool, str]:
    """
    检查 URL 是否安全（防止 SSRF）
    返回: (is_safe, error_message)
    """
    try:
        parsed = urlparse(url)
        
        # 检查协议
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, f"不允许的协议: {parsed.scheme}"
        
        hostname = parsed.hostname
        if not hostname:
            return False, "无效的 URL"
        
        hostname_lower = hostname.lower()
        
        # 检查禁止的主机名
        if hostname_lower in BLOCKED_HOSTNAMES:
            return False, "禁止访问的地址"
        
        # 检查是否以禁止的主机名结尾（如 evil.localhost）
        for blocked in BLOCKED_HOSTNAMES:
            if hostname_lower.endswith('.' + blocked):
                return False, "禁止访问的地址"
        
        # 解析主机名获取 IP 地址
        try:
            # 获取所有 IP 地址（包括 IPv4 和 IPv6）
            addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
            for info in addr_info:
                ip_str = info[4][0]
                if is_ip_blocked(ip_str):
                    return False, "禁止访问内部网络地址"
        except socket.gaierror:
            # DNS 解析失败，可能是无效域名
            return False, "无法解析域名"
        
        # 检查端口（可选：只允许标准端口）
        port = parsed.port
        if port and port not in [80, 443, 8080, 8443]:
            # 允许一些常见端口，但禁止敏感端口
            sensitive_ports = [22, 23, 25, 3306, 5432, 6379, 27017, 11211]
            if port in sensitive_ports:
                return False, f"禁止访问的端口: {port}"
        
        return True, ""
        
    except Exception as e:
        return False, f"URL 解析错误: {str(e)}"


class SafeRedirectSession(requests.Session):
    """安全的 HTTP Session，检查重定向目标"""
    
    def __init__(self, max_redirects: int = 5):
        super().__init__()
        self.max_redirects = max_redirects
        self._redirect_count = 0
    
    def get_redirect_target(self, resp):
        """获取重定向目标并验证"""
        target = super().get_redirect_target(resp)
        if target:
            self._redirect_count += 1
            if self._redirect_count > self.max_redirects:
                raise requests.TooManyRedirects(f"超过最大重定向次数: {self.max_redirects}")
            
            # 检查重定向目标是否安全
            is_safe, error = is_safe_url(target)
            if not is_safe:
                raise requests.exceptions.InvalidURL(f"重定向目标不安全: {error}")
        
        return target


class UrlMetaRequest(BaseModel):
    """URL Meta 请求"""
    url: str


class UrlMetaResponse(BaseModel):
    """URL Meta 响应"""
    title: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    url: str


def extract_meta_from_html(html: str, base_url: str) -> dict:
    """从 HTML 中提取 meta 信息"""
    result = {
        'title': None,
        'description': None,
        'icon': None
    }
    
    # 提取 title
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
    if title_match:
        result['title'] = title_match.group(1).strip()
    
    # 提取 og:title（优先级更高）
    og_title_match = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not og_title_match:
        og_title_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html, re.IGNORECASE)
    if og_title_match:
        result['title'] = og_title_match.group(1).strip()
    
    # 提取 description
    desc_match = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not desc_match:
        desc_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']', html, re.IGNORECASE)
    if desc_match:
        result['description'] = desc_match.group(1).strip()
    
    # 提取 og:description（优先级更高）
    og_desc_match = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not og_desc_match:
        og_desc_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']', html, re.IGNORECASE)
    if og_desc_match:
        result['description'] = og_desc_match.group(1).strip()
    
    # 提取 favicon
    # 尝试多种 favicon 标签格式
    icon_patterns = [
        r'<link[^>]+rel=["\'](?:shortcut )?icon["\'][^>]+href=["\']([^"\']+)["\']',
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'](?:shortcut )?icon["\']',
        r'<link[^>]+rel=["\']apple-touch-icon["\'][^>]+href=["\']([^"\']+)["\']',
    ]
    
    for pattern in icon_patterns:
        icon_match = re.search(pattern, html, re.IGNORECASE)
        if icon_match:
            icon_url = icon_match.group(1)
            # 转换为绝对 URL
            if not icon_url.startswith(('http://', 'https://', '//')):
                icon_url = urljoin(base_url, icon_url)
            elif icon_url.startswith('//'):
                icon_url = 'https:' + icon_url
            result['icon'] = icon_url
            break
    
    # 如果没有找到 favicon，使用默认路径
    if not result['icon']:
        parsed = urlparse(base_url)
        result['icon'] = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
    
    return result


@router.post("/meta", response_model=UrlMetaResponse)
async def get_url_meta(
    request: UrlMetaRequest,
    current_user: User = Depends(get_current_user)
):
    """获取 URL 的 meta 信息（标题、描述、图标）- 带 SSRF 防护"""
    url = request.url.strip()
    
    # 确保 URL 有协议
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # ===== SSRF 安全检查 =====
    is_safe, error_msg = is_safe_url(url)
    if not is_safe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"URL 安全检查失败: {error_msg}"
        )
    
    try:
        # 使用安全的 Session（检查重定向）
        session = SafeRedirectSession(max_redirects=5)
        
        # 请求网页
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        
        response = session.get(
            url, 
            headers=headers, 
            timeout=10, 
            allow_redirects=True,
            verify=True  # 验证 SSL 证书
        )
        response.raise_for_status()
        
        # 尝试正确解码
        content = response.content
        encoding = response.encoding
        
        # 尝试从 content-type 或 meta 标签获取编码
        if 'charset' in response.headers.get('content-type', '').lower():
            pass  # 使用 response.encoding
        else:
            # 尝试从 HTML 中检测编码
            charset_match = re.search(rb'charset=["\']?([^"\'>\s]+)', content[:1024])
            if charset_match:
                encoding = charset_match.group(1).decode('ascii', errors='ignore')
        
        try:
            html = content.decode(encoding or 'utf-8', errors='ignore')
        except:
            html = content.decode('utf-8', errors='ignore')
        
        # 提取 meta 信息
        meta = extract_meta_from_html(html, url)
        
        # 如果没有获取到标题，使用域名
        if not meta['title']:
            parsed = urlparse(url)
            meta['title'] = parsed.netloc.replace('www.', '')
        
        return UrlMetaResponse(
            title=meta['title'],
            description=meta['description'],
            icon=meta['icon'],
            url=url
        )
        
    except requests.exceptions.TooManyRedirects:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="重定向次数过多"
        )
    except requests.exceptions.InvalidURL as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except requests.exceptions.Timeout:
        # 超时时返回域名作为标题
        parsed = urlparse(url)
        return UrlMetaResponse(
            title=parsed.netloc.replace('www.', ''),
            url=url
        )
    except requests.exceptions.SSLError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSL 证书验证失败"
        )
    except requests.exceptions.ConnectionError:
        # 连接失败，返回域名
        parsed = urlparse(url)
        return UrlMetaResponse(
            title=parsed.netloc.replace('www.', ''),
            url=url
        )
    except HTTPException:
        # 重新抛出 HTTP 异常
        raise
    except Exception as e:
        # 其他错误返回域名，但记录日志
        print(f"[WARN] URL meta fetch error: {url} - {str(e)}")
        parsed = urlparse(url)
        return UrlMetaResponse(
            title=parsed.netloc.replace('www.', ''),
            url=url
        )


@router.get("", response_model=List[BookmarkResponse])
async def get_bookmarks(
    category: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取书签列表"""
    query = select(Bookmark).where(Bookmark.user_id == current_user.id)
    
    if category:
        query = query.where(Bookmark.category == category)
    
    query = query.order_by(Bookmark.sort_order, Bookmark.created_at.desc())
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=BookmarkResponse, status_code=status.HTTP_201_CREATED)
async def create_bookmark(
    bookmark_in: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建书签"""
    bookmark = Bookmark(
        user_id=current_user.id,
        title=bookmark_in.title,
        url=bookmark_in.url,
        icon=bookmark_in.icon,
        category=bookmark_in.category,
        sort_order=bookmark_in.sort_order
    )
    db.add(bookmark)
    await db.flush()
    await db.refresh(bookmark)
    return bookmark


@router.patch("/{bookmark_id}", response_model=BookmarkResponse)
async def update_bookmark(
    bookmark_id: str,
    bookmark_in: BookmarkUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新书签"""
    result = await db.execute(
        select(Bookmark).where(
            Bookmark.id == bookmark_id,
            Bookmark.user_id == current_user.id
        )
    )
    bookmark = result.scalar_one_or_none()
    
    if not bookmark:
        raise HTTPException(status_code=404, detail="书签不存在")
    
    if bookmark_in.title is not None:
        bookmark.title = bookmark_in.title
    if bookmark_in.url is not None:
        bookmark.url = bookmark_in.url
    if bookmark_in.icon is not None:
        bookmark.icon = bookmark_in.icon
    if bookmark_in.category is not None:
        bookmark.category = bookmark_in.category
    if bookmark_in.sort_order is not None:
        bookmark.sort_order = bookmark_in.sort_order
    
    await db.flush()
    await db.refresh(bookmark)
    return bookmark


@router.delete("/{bookmark_id}")
async def delete_bookmark(
    bookmark_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除书签"""
    result = await db.execute(
        select(Bookmark).where(
            Bookmark.id == bookmark_id,
            Bookmark.user_id == current_user.id
        )
    )
    bookmark = result.scalar_one_or_none()
    
    if not bookmark:
        raise HTTPException(status_code=404, detail="书签不存在")
    
    await db.delete(bookmark)
    return {"message": "删除成功"}

