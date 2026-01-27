"""网站资源连通性测试模块"""
import asyncio
import aiohttp
import re
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict, field
from enum import Enum


class ResourceType(str, Enum):
    """资源类型"""
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    SCRIPT = "script"
    STYLESHEET = "stylesheet"
    FONT = "font"
    DOCUMENT = "document"
    OTHER = "other"


# 资源类型对应的 MIME 类型前缀
RESOURCE_MIME_MAP = {
    "image": ["image/"],
    "video": ["video/", "application/x-mpegurl", "application/vnd.apple.mpegurl"],
    "audio": ["audio/"],
    "script": ["application/javascript", "text/javascript", "application/x-javascript"],
    "stylesheet": ["text/css"],
    "font": ["font/", "application/font", "application/x-font"],
    "document": ["application/pdf", "application/msword", "application/vnd.openxmlformats", "text/plain"],
}

# 文件类型的 Magic Bytes（文件头）
MAGIC_BYTES = {
    "image": {
        b'\xff\xd8\xff': "JPEG",
        b'\x89PNG\r\n\x1a\n': "PNG",
        b'GIF87a': "GIF",
        b'GIF89a': "GIF",
        b'RIFF': "WEBP",  # WEBP 以 RIFF 开头
        b'<svg': "SVG",
        b'<?xml': "SVG",  # SVG 可能以 XML 声明开头
    },
    "video": {
        b'\x00\x00\x00': "MP4/MOV",  # MP4/MOV 通常以 ftyp box 开头
        b'\x1a\x45\xdf\xa3': "WEBM/MKV",
        b'OggS': "OGG",
        b'#EXTM3U': "M3U8",
    },
    "audio": {
        b'ID3': "MP3",
        b'\xff\xfb': "MP3",
        b'\xff\xfa': "MP3",
        b'fLaC': "FLAC",
        b'OggS': "OGG",
        b'RIFF': "WAV",
    },
    "document": {
        b'%PDF': "PDF",
        b'\xd0\xcf\x11\xe0': "DOC/XLS/PPT",
        b'PK\x03\x04': "DOCX/XLSX/PPTX/ZIP",
    }
}


@dataclass
class ResourceResult:
    """资源测试结果"""
    url: str
    resource_type: str
    status_code: Optional[int] = None
    status_text: str = ""
    content_type: Optional[str] = None
    content_length: Optional[int] = None
    response_time_ms: Optional[float] = None
    error: Optional[str] = None
    accessible: bool = False
    # 增强测试结果
    enhanced_test: bool = False
    content_valid: Optional[bool] = None
    content_type_match: Optional[bool] = None
    magic_bytes_match: Optional[bool] = None
    detected_type: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


def guess_resource_type(url: str, tag_name: str = "", attr_name: str = "") -> str:
    """根据 URL 和标签猜测资源类型"""
    url_lower = url.lower()
    
    # 根据标签判断
    tag_type_map = {
        "img": ResourceType.IMAGE,
        "video": ResourceType.VIDEO,
        "audio": ResourceType.AUDIO,
        "script": ResourceType.SCRIPT,
        "link": ResourceType.STYLESHEET if attr_name == "href" else ResourceType.OTHER,
        "source": ResourceType.VIDEO,
    }
    
    if tag_name in tag_type_map:
        return tag_type_map[tag_name].value
    
    # 根据扩展名判断
    image_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp', '.avif')
    video_exts = ('.mp4', '.webm', '.ogg', '.avi', '.mov', '.mkv', '.m3u8', '.ts')
    audio_exts = ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a')
    font_exts = ('.woff', '.woff2', '.ttf', '.otf', '.eot')
    script_exts = ('.js', '.mjs')
    style_exts = ('.css',)
    doc_exts = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt')
    
    path = urlparse(url_lower).path
    
    if any(path.endswith(ext) for ext in image_exts):
        return ResourceType.IMAGE.value
    elif any(path.endswith(ext) for ext in video_exts):
        return ResourceType.VIDEO.value
    elif any(path.endswith(ext) for ext in audio_exts):
        return ResourceType.AUDIO.value
    elif any(path.endswith(ext) for ext in font_exts):
        return ResourceType.FONT.value
    elif any(path.endswith(ext) for ext in script_exts):
        return ResourceType.SCRIPT.value
    elif any(path.endswith(ext) for ext in style_exts):
        return ResourceType.STYLESHEET.value
    elif any(path.endswith(ext) for ext in doc_exts):
        return ResourceType.DOCUMENT.value
    
    return ResourceType.OTHER.value


def extract_resources_from_html(html: str, base_url: str) -> List[Dict[str, str]]:
    """从 HTML 中提取所有资源链接"""
    soup = BeautifulSoup(html, 'html.parser')
    resources = []
    seen_urls = set()
    
    def add_resource(url: str, tag_name: str, attr_name: str, force_type: str = None):
        """添加资源到列表"""
        if not url:
            return
        
        # 处理相对 URL
        absolute_url = urljoin(base_url, url.strip())
        
        # 过滤无效 URL
        if not absolute_url.startswith(('http://', 'https://')):
            return
        
        # 过滤 data: URL 和 blob: URL
        if absolute_url.startswith(('data:', 'blob:', 'javascript:')):
            return
        
        # 去重
        if absolute_url in seen_urls:
            return
        seen_urls.add(absolute_url)
        
        resource_type = force_type or guess_resource_type(absolute_url, tag_name, attr_name)
        resources.append({
            'url': absolute_url,
            'resource_type': resource_type,
            'tag': tag_name,
            'attr': attr_name
        })
    
    # ==================== 图片提取 ====================
    # 常见的图片懒加载属性
    img_lazy_attrs = [
        'src', 'data-src', 'data-original', 'data-lazy-src', 'data-lazy',
        'data-echo', 'data-srcset', 'data-original-src', 'data-url',
        'data-img', 'data-image', 'data-hi-res', 'lazy-src', 'real-src',
        'data-actualsrc', 'data-thumb', 'data-full', 'data-zoom-src'
    ]
    
    for img in soup.find_all('img'):
        for attr in img_lazy_attrs:
            url = img.get(attr)
            if url:
                add_resource(url, 'img', attr, 'image')
        
        # 处理 srcset（响应式图片）
        srcset = img.get('srcset') or img.get('data-srcset')
        if srcset:
            # srcset 格式: "url1 1x, url2 2x" 或 "url1 100w, url2 200w"
            for part in srcset.split(','):
                part = part.strip()
                if part:
                    url = part.split()[0] if part.split() else part
                    add_resource(url, 'img', 'srcset', 'image')
    
    # <picture> 标签中的 <source>
    for picture in soup.find_all('picture'):
        for source in picture.find_all('source'):
            url = source.get('srcset') or source.get('src')
            if url:
                # srcset 可能包含多个 URL
                for part in url.split(','):
                    part = part.strip()
                    if part:
                        src = part.split()[0] if part.split() else part
                        add_resource(src, 'picture>source', 'srcset', 'image')
    
    # ==================== 视频/音频提取 ====================
    for video in soup.find_all('video'):
        for attr in ['src', 'data-src', 'poster', 'data-poster']:
            url = video.get(attr)
            if url:
                rtype = 'image' if 'poster' in attr else 'video'
                add_resource(url, 'video', attr, rtype)
    
    for audio in soup.find_all('audio'):
        for attr in ['src', 'data-src']:
            url = audio.get(attr)
            if url:
                add_resource(url, 'audio', attr, 'audio')
    
    # <source> 标签（视频/音频源）
    for source in soup.find_all('source'):
        url = source.get('src') or source.get('data-src')
        if url:
            # 尝试判断是视频还是音频
            parent = source.parent
            if parent and parent.name == 'video':
                add_resource(url, 'source', 'src', 'video')
            elif parent and parent.name == 'audio':
                add_resource(url, 'source', 'src', 'audio')
            else:
                add_resource(url, 'source', 'src')
    
    # ==================== 脚本和样式 ====================
    for script in soup.find_all('script'):
        url = script.get('src')
        if url:
            add_resource(url, 'script', 'src', 'script')
    
    for link in soup.find_all('link'):
        url = link.get('href')
        if url:
            rel = link.get('rel', [])
            if isinstance(rel, list):
                rel = ' '.join(rel).lower()
            else:
                rel = rel.lower()
            
            if 'stylesheet' in rel:
                add_resource(url, 'link', 'href', 'stylesheet')
            elif 'icon' in rel or 'apple-touch-icon' in rel:
                add_resource(url, 'link', 'href', 'image')
            elif 'preload' in rel:
                # preload 资源
                as_type = link.get('as', '').lower()
                if as_type == 'image':
                    add_resource(url, 'link', 'href', 'image')
                elif as_type == 'font':
                    add_resource(url, 'link', 'href', 'font')
                elif as_type in ('script', 'style'):
                    add_resource(url, 'link', 'href', as_type if as_type == 'script' else 'stylesheet')
    
    # ==================== 其他媒体标签 ====================
    for iframe in soup.find_all('iframe'):
        url = iframe.get('src') or iframe.get('data-src')
        if url:
            add_resource(url, 'iframe', 'src')
    
    for embed in soup.find_all('embed'):
        url = embed.get('src')
        if url:
            add_resource(url, 'embed', 'src')
    
    for obj in soup.find_all('object'):
        url = obj.get('data')
        if url:
            add_resource(url, 'object', 'data')
    
    # ==================== 文件链接（<a>标签） ====================
    # 排除的页面扩展名（这些是网页，不是文件）
    page_exts = ('.html', '.htm', '.php', '.asp', '.aspx', '.jsp', '.do', '.action', '.shtml')
    
    # 文件相关的路径关键词（宽松匹配）
    file_keywords = (
        '/file', '/download', '/attach', '/upload',
        '/blob', '/object', '/storage', '/media',
        '/resource/file', '/assets/', '/static/',
        '/cdn/', '/oss/', '/cos/', '/eos/',
        'helpcenter', 'software', 'package', 'release',
    )
    
    # 检测文件名模式：路径末尾包含扩展名
    # 匹配：xxx.tar.gz, xxx.rpm, xxx-1.0.zip, file.iso 等
    # 更宽松：只要末尾有 .xxx 格式就认为可能是文件
    filename_pattern = re.compile(r'/[^/]+\.[a-z0-9]{1,12}$', re.I)
    
    # 检测文件 ID 模式
    file_id_pattern = re.compile(r'[a-f0-9]{24,}/?$|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/?$', re.I)
    
    for a in soup.find_all('a'):
        url = a.get('href')
        if url:
            # 跳过 javascript:、mailto:、tel:、#锚点 等
            if url.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                continue
            
            path = urlparse(url).path.lower()
            full_url_lower = url.lower()
            
            # 跳过明显的页面链接（以页面扩展名结尾）
            if any(path.endswith(ext) for ext in page_exts):
                continue
            
            # 1. 检查是否包含文件关键词
            has_file_keyword = any(kw in full_url_lower for kw in file_keywords)
            
            # 2. 检查 URL 末尾是否像文件名（包含扩展名）
            looks_like_file = filename_pattern.search(path) is not None
            
            # 3. 检查是否是文件 ID
            has_file_id = file_id_pattern.search(path) is not None
            
            # 满足以下任一条件则认为是文件链接：
            # - 路径末尾看起来像文件名（有扩展名）
            # - 有文件关键词
            # - 有文件 ID 且包含资源相关路径
            if looks_like_file or has_file_keyword or (has_file_id and any(kw in full_url_lower for kw in ('/file', '/resource', '/blob', '/object'))):
                add_resource(url, 'a', 'href')
    
    # ==================== CSS 中的资源 ====================
    # 内联 <style> 标签
    for style in soup.find_all('style'):
        if style.string:
            urls = re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', style.string)
            for url in urls:
                add_resource(url, 'style', 'url()')
    
    # 内联 style 属性
    for tag in soup.find_all(style=True):
        style_value = tag.get('style', '')
        urls = re.findall(r'url\(["\']?([^"\'()]+)["\']?\)', style_value)
        for url in urls:
            add_resource(url, tag.name, 'style')
    
    # ==================== 通用 data-* 属性扫描 ====================
    # 扫描所有标签的 data-* 属性，查找可能的资源 URL
    url_pattern = re.compile(r'^https?://|^/[^/]')
    media_exts = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.bmp',
                  '.mp4', '.webm', '.ogg', '.mp3', '.wav', '.m3u8')
    
    for tag in soup.find_all(True):
        for attr, value in tag.attrs.items():
            if attr.startswith('data-') and isinstance(value, str):
                # 跳过已处理的常见属性
                if attr in img_lazy_attrs:
                    continue
                # 检查是否像 URL
                if url_pattern.match(value) or any(ext in value.lower() for ext in media_exts):
                    add_resource(value, tag.name, attr)
    
    # ==================== JSON-LD 中的图片 ====================
    for script in soup.find_all('script', type='application/ld+json'):
        if script.string:
            try:
                import json
                data = json.loads(script.string)
                # 递归查找 image 字段
                def find_images(obj):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if key.lower() in ('image', 'thumbnail', 'logo', 'photo', 'contenturl'):
                                if isinstance(value, str):
                                    add_resource(value, 'json-ld', key, 'image')
                                elif isinstance(value, list):
                                    for item in value:
                                        if isinstance(item, str):
                                            add_resource(item, 'json-ld', key, 'image')
                            else:
                                find_images(value)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_images(item)
                find_images(data)
            except:
                pass
    
    # ==================== Open Graph 和 Twitter Cards ====================
    for meta in soup.find_all('meta'):
        prop = meta.get('property', '') or meta.get('name', '')
        content = meta.get('content', '')
        
        if content and prop.lower() in ('og:image', 'og:image:url', 'og:video', 'og:audio',
                                         'twitter:image', 'twitter:image:src', 'twitter:player'):
            rtype = 'image'
            if 'video' in prop.lower():
                rtype = 'video'
            elif 'audio' in prop.lower():
                rtype = 'audio'
            add_resource(content, 'meta', prop, rtype)
    
    return resources


def check_content_type_match(resource_type: str, content_type: str) -> bool:
    """检查 Content-Type 是否与资源类型匹配"""
    if not content_type:
        return False
    
    content_type_lower = content_type.lower()
    expected_prefixes = RESOURCE_MIME_MAP.get(resource_type, [])
    
    for prefix in expected_prefixes:
        if prefix in content_type_lower:
            return True
    
    # 对于 other 类型，不做严格检查
    if resource_type == "other":
        return True
    
    return False


def check_magic_bytes(resource_type: str, content: bytes) -> tuple[bool, Optional[str]]:
    """检查文件头是否匹配资源类型"""
    if not content or len(content) < 4:
        return False, None
    
    magic_map = MAGIC_BYTES.get(resource_type, {})
    
    for magic, file_type in magic_map.items():
        if content.startswith(magic):
            return True, file_type
    
    # 特殊处理：检查是否是 HTML 错误页面
    content_start = content[:100].lower()
    if b'<!doctype html' in content_start or b'<html' in content_start:
        return False, "HTML"
    
    # 对于 other 类型，不做严格检查
    if resource_type == "other":
        return True, None
    
    return False, None


async def test_resource_accessibility(
    session: aiohttp.ClientSession,
    url: str,
    resource_type: str,
    timeout: int = 10,
    method: str = "HEAD",
    enhanced: bool = False
) -> ResourceResult:
    """测试单个资源的可访问性
    
    Args:
        session: aiohttp 会话
        url: 资源 URL
        resource_type: 资源类型
        timeout: 超时时间（秒）
        method: 请求方法
        enhanced: 是否启用增强测试（会下载部分内容验证）
    """
    import time
    
    result = ResourceResult(url=url, resource_type=resource_type)
    result.enhanced_test = enhanced
    result.warnings = []
    
    try:
        start_time = time.time()
        
        # 增强测试需要使用 GET 请求来获取内容
        actual_method = "GET" if enhanced else method
        
        async with session.request(
            actual_method,
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            allow_redirects=True,
            ssl=False  # 忽略 SSL 证书验证
        ) as response:
            end_time = time.time()
            
            result.status_code = response.status
            result.status_text = response.reason or ""
            result.content_type = response.headers.get('Content-Type', '')
            
            # 尝试获取内容长度
            content_length = response.headers.get('Content-Length')
            if content_length:
                try:
                    result.content_length = int(content_length)
                except ValueError:
                    pass
            
            result.response_time_ms = round((end_time - start_time) * 1000, 2)
            
            # 基本可访问性检查
            basic_accessible = 200 <= response.status < 400
            result.accessible = basic_accessible
            
            # 增强测试
            if enhanced and basic_accessible:
                # 1. 检查 Content-Type 是否匹配
                result.content_type_match = check_content_type_match(resource_type, result.content_type or "")
                if not result.content_type_match:
                    result.warnings.append(f"Content-Type 不匹配: 期望 {resource_type}，实际 {result.content_type}")
                
                # 2. 检查 Content-Length
                if result.content_length == 0:
                    result.warnings.append("内容长度为 0")
                    result.content_valid = False
                elif result.content_length is not None:
                    # 对于图片、视频等，检查最小大小
                    min_sizes = {
                        "image": 100,  # 图片至少 100 字节
                        "video": 1000,  # 视频至少 1KB
                        "audio": 1000,  # 音频至少 1KB
                        "document": 100,  # 文档至少 100 字节
                    }
                    min_size = min_sizes.get(resource_type, 0)
                    if result.content_length < min_size:
                        result.warnings.append(f"内容大小异常: {result.content_length} 字节（期望至少 {min_size} 字节）")
                
                # 3. 读取部分内容检查文件头
                try:
                    # 只读取前 1KB 来检查文件头
                    content = await response.content.read(1024)
                    if content:
                        magic_match, detected = check_magic_bytes(resource_type, content)
                        result.magic_bytes_match = magic_match
                        result.detected_type = detected
                        
                        if not magic_match:
                            if detected == "HTML":
                                result.warnings.append("实际返回的是 HTML 页面，可能是错误页或防盗链页面")
                            else:
                                result.warnings.append(f"文件头不匹配预期的 {resource_type} 类型")
                        
                        # 检查是否包含常见错误关键词
                        content_str = content.decode('utf-8', errors='ignore').lower()
                        error_keywords = ['not found', '404', 'error', '禁止访问', '文件不存在', 'access denied', 'forbidden']
                        for keyword in error_keywords:
                            if keyword in content_str:
                                result.warnings.append(f"内容包含错误关键词: {keyword}")
                                break
                    else:
                        result.content_valid = False
                        result.warnings.append("无法读取内容")
                except Exception as e:
                    result.warnings.append(f"读取内容失败: {str(e)}")
                
                # 综合判断增强测试结果
                if result.warnings:
                    # 有警告时，根据严重程度判断
                    critical_warnings = [w for w in result.warnings if 
                                        '内容长度为 0' in w or 
                                        'HTML 页面' in w or 
                                        '错误关键词' in w]
                    if critical_warnings:
                        result.accessible = False
                        result.content_valid = False
                    else:
                        result.content_valid = True  # 有轻微警告但可能仍可用
                else:
                    result.content_valid = True
            
    except aiohttp.ClientResponseError as e:
        result.status_code = e.status
        result.status_text = str(e.message)
        result.error = str(e)
        result.accessible = False
        
    except asyncio.TimeoutError:
        result.error = "请求超时"
        result.accessible = False
        
    except aiohttp.ClientError as e:
        result.error = f"连接错误: {str(e)}"
        result.accessible = False
        
    except Exception as e:
        result.error = f"未知错误: {str(e)}"
        result.accessible = False
    
    # 如果 HEAD 请求返回 405，尝试 GET 请求（非增强模式）
    if result.status_code == 405 and method == "HEAD" and not enhanced:
        return await test_resource_accessibility(session, url, resource_type, timeout, "GET", enhanced)
    
    return result


async def fetch_page_with_browser(
    url: str,
    wait_time: int = 3,
    wait_for_selector: Optional[str] = None
) -> Dict[str, Any]:
    """
    使用浏览器渲染页面，获取动态加载的内容
    
    Args:
        url: 目标 URL
        wait_time: 等待时间（秒），等待 JavaScript 执行
        wait_for_selector: 等待特定元素出现
    
    Returns:
        包含 html 和 final_url 的字典，或包含 error 的字典
    """
    import os
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 设置 Playwright 使用本地安装的浏览器（在 venv 内）
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'
    
    try:
        from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    except ImportError:
        return {'error': 'Playwright 未安装，请运行: pip install playwright && playwright install chromium'}
    
    result = {}
    logger.info(f"[浏览器渲染] 开始访问: {url}")
    
    try:
        async with async_playwright() as p:
            # 启动浏览器
            logger.info("[浏览器渲染] 启动浏览器...")
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            
            try:
                # 创建页面
                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    ignore_https_errors=True
                )
                page = await context.new_page()
                
                # 访问页面 - 使用 domcontentloaded 而不是 networkidle，避免某些网站永远无法完成
                logger.info("[浏览器渲染] 访问页面...")
                try:
                    response = await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                except PlaywrightTimeout:
                    logger.warning("[浏览器渲染] 页面加载超时，继续尝试获取内容...")
                    response = None
                
                if response and response.status >= 400:
                    result['error'] = f"页面返回错误状态码: {response.status}"
                    return result
                
                # 等待页面加载
                logger.info(f"[浏览器渲染] 等待 {wait_time} 秒让 JS 执行...")
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(wait_for_selector, timeout=wait_time * 1000)
                    except PlaywrightTimeout:
                        pass  # 超时也继续
                else:
                    # 等待指定时间让 JS 执行
                    await page.wait_for_timeout(wait_time * 1000)
                
                # 滚动页面以触发懒加载
                logger.info("[浏览器渲染] 滚动页面触发懒加载...")
                try:
                    await page.evaluate('''
                        async () => {
                            const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                            for (let i = 0; i < 3; i++) {
                                window.scrollTo(0, document.body.scrollHeight * (i + 1) / 3);
                                await delay(300);
                            }
                            window.scrollTo(0, 0);
                        }
                    ''')
                except Exception as scroll_err:
                    logger.warning(f"[浏览器渲染] 滚动失败: {scroll_err}")
                
                # 再等待一下让懒加载完成
                await page.wait_for_timeout(1000)
                
                # 获取渲染后的 HTML
                logger.info("[浏览器渲染] 获取页面内容...")
                html = await page.content()
                final_url = page.url
                
                result['html'] = html
                result['final_url'] = final_url
                logger.info(f"[浏览器渲染] 完成，HTML 长度: {len(html)}")
                
            finally:
                logger.info("[浏览器渲染] 关闭浏览器...")
                await browser.close()
                
    except PlaywrightTimeout as e:
        logger.error(f"[浏览器渲染] 超时: {str(e)}")
        result['error'] = f"浏览器渲染超时: 页面加载时间过长"
    except Exception as e:
        logger.error(f"[浏览器渲染] 失败: {str(e)}")
        result['error'] = f"浏览器渲染失败: {str(e)}"
    
    return result


async def fetch_resource_size(
    session: aiohttp.ClientSession,
    url: str,
    timeout: int = 10
) -> Dict[str, Any]:
    """
    获取单个资源的文件大小
    
    Args:
        session: aiohttp 会话
        url: 资源 URL
        timeout: 超时时间（秒）
    
    Returns:
        包含 size、content_type 等信息的字典
    """
    result = {
        'url': url,
        'size': None,
        'size_formatted': None,
        'content_type': None,
        'error': None
    }
    
    try:
        async with session.head(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            allow_redirects=True,
            ssl=False
        ) as response:
            if response.status == 200:
                content_length = response.headers.get('Content-Length')
                if content_length:
                    size = int(content_length)
                    result['size'] = size
                    result['size_formatted'] = format_file_size(size)
                result['content_type'] = response.headers.get('Content-Type', '')
            elif response.status == 405:
                # HEAD 不支持，尝试 GET 只获取头
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    allow_redirects=True,
                    ssl=False
                ) as get_response:
                    if get_response.status == 200:
                        content_length = get_response.headers.get('Content-Length')
                        if content_length:
                            size = int(content_length)
                            result['size'] = size
                            result['size_formatted'] = format_file_size(size)
                        result['content_type'] = get_response.headers.get('Content-Type', '')
            else:
                result['error'] = f"HTTP {response.status}"
    except asyncio.TimeoutError:
        result['error'] = "超时"
    except Exception as e:
        result['error'] = str(e)[:50]
    
    return result


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小为人类可读的格式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


async def batch_fetch_resource_sizes(
    resources: List[Dict],
    custom_headers: Optional[Dict[str, str]] = None,
    concurrency: int = 10,
    timeout: int = 10
) -> List[Dict]:
    """
    批量获取资源的文件大小
    
    Args:
        resources: 资源列表，每个资源需要包含 url 字段
        custom_headers: 自定义请求头
        concurrency: 并发数
        timeout: 单个请求超时时间
    
    Returns:
        更新后的资源列表，包含 size、size_formatted 字段
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
    }
    if custom_headers:
        headers.update(custom_headers)
    
    connector = aiohttp.TCPConnector(ssl=False, limit=concurrency)
    
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        semaphore = asyncio.Semaphore(concurrency)
        
        async def fetch_with_semaphore(resource: Dict) -> Dict:
            async with semaphore:
                size_info = await fetch_resource_size(session, resource['url'], timeout)
                # 合并信息到资源字典
                resource['size'] = size_info['size']
                resource['size_formatted'] = size_info['size_formatted']
                resource['content_type'] = size_info.get('content_type')
                if size_info['error']:
                    resource['size_error'] = size_info['error']
                return resource
        
        tasks = [fetch_with_semaphore(r) for r in resources]
        results = await asyncio.gather(*tasks)
    
    return list(results)


async def extract_resources_only(
    target_url: str,
    include_types: Optional[List[str]] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    use_browser: bool = False,
    browser_wait_time: int = 3,
    fetch_size: bool = False,
    size_concurrency: int = 10
) -> Dict[str, Any]:
    """
    只提取网页资源，不进行测试
    
    Args:
        target_url: 目标网页 URL
        include_types: 只包含特定类型的资源
        custom_headers: 自定义请求头
        use_browser: 是否使用浏览器渲染（用于动态页面）
        browser_wait_time: 浏览器等待时间（秒）
        fetch_size: 是否获取文件大小
        size_concurrency: 获取文件大小的并发数
    
    Returns:
        提取结果字典
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    if custom_headers:
        headers.update(custom_headers)
    
    result = {
        'target_url': target_url,
        'total_resources': 0,
        'resources': [],
        'summary_by_type': {},
        'render_mode': 'browser' if use_browser else 'static',
        'error': None
    }
    
    try:
        if use_browser:
            # 使用浏览器渲染
            browser_result = await fetch_page_with_browser(target_url, browser_wait_time)
            
            if 'error' in browser_result:
                result['error'] = browser_result['error']
                return result
            
            html = browser_result['html']
            final_url = browser_result['final_url']
        else:
            # 静态请求
            connector = aiohttp.TCPConnector(ssl=False)
            
            async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
                try:
                    async with session.get(
                        target_url,
                        timeout=aiohttp.ClientTimeout(total=30),
                        allow_redirects=True
                    ) as response:
                        if response.status != 200:
                            result['error'] = f"无法获取目标页面: HTTP {response.status}"
                            return result
                        
                        html = await response.text()
                        final_url = str(response.url)
                        
                except Exception as e:
                    result['error'] = f"获取目标页面失败: {str(e)}"
                    return result
        
        # 提取资源
        resources = extract_resources_from_html(html, final_url)
        
        # 根据类型过滤
        if include_types:
            resources = [r for r in resources if r['resource_type'] in include_types]
        
        # 获取文件大小（可选）
        if fetch_size and resources:
            resources = await batch_fetch_resource_sizes(
                resources,
                custom_headers=custom_headers,
                concurrency=size_concurrency
            )
            # 计算总大小
            total_size = sum(r.get('size', 0) or 0 for r in resources)
            result['total_size'] = total_size
            result['total_size_formatted'] = format_file_size(total_size)
            
            # 按文件大小从大到小排序（None 和 0 排在最后）
            resources = sorted(resources, key=lambda r: r.get('size') or 0, reverse=True)
        
        result['total_resources'] = len(resources)
        result['resources'] = resources
        
        # 按类型统计
        for r in resources:
            rtype = r['resource_type']
            if rtype not in result['summary_by_type']:
                result['summary_by_type'][rtype] = 0
            result['summary_by_type'][rtype] += 1
    
    except Exception as e:
        result['error'] = f"提取过程出错: {str(e)}"
    
    return result


async def batch_extract_resources(
    target_urls: List[str],
    include_types: Optional[List[str]] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    use_browser: bool = False,
    browser_wait_time: int = 3,
    fetch_size: bool = False,
    size_concurrency: int = 10
) -> Dict[str, Any]:
    """
    批量提取多个网页的资源，不进行测试
    
    Args:
        target_urls: 目标 URL 列表
        include_types: 只包含特定类型的资源
        custom_headers: 自定义请求头
        use_browser: 是否使用浏览器渲染（用于动态页面）
        fetch_size: 是否获取文件大小
        browser_wait_time: 浏览器等待时间（秒）
    """
    # URL 去重（保持顺序）
    seen_urls = set()
    unique_urls = []
    for url in target_urls:
        url_normalized = url.strip().rstrip('/')
        if url_normalized and url_normalized not in seen_urls:
            seen_urls.add(url_normalized)
            unique_urls.append(url.strip())
    
    result = {
        'total_sites': len(unique_urls),
        'input_urls': len(target_urls),  # 原始输入数量
        'deduplicated': len(target_urls) - len(unique_urls),  # 去重数量
        'success_sites': 0,
        'failed_sites': 0,
        'total_resources': 0,
        'sites': [],
        'all_resources': [],
        'summary_by_type': {},
        'render_mode': 'browser' if use_browser else 'static',
        'error': None
    }
    
    total_size = 0
    
    for target_url in unique_urls:
        site_result = await extract_resources_only(
            target_url=target_url,
            use_browser=use_browser,
            browser_wait_time=browser_wait_time,
            include_types=include_types,
            custom_headers=custom_headers,
            fetch_size=fetch_size,
            size_concurrency=size_concurrency
        )
        
        # 添加来源 URL 到每个资源
        for r in site_result.get('resources', []):
            r['source_url'] = target_url
        
        result['sites'].append(site_result)
        
        if site_result.get('error'):
            result['failed_sites'] += 1
        else:
            result['success_sites'] += 1
            result['total_resources'] += site_result.get('total_resources', 0)
            result['all_resources'].extend(site_result.get('resources', []))
            
            # 汇总文件大小
            if fetch_size:
                total_size += site_result.get('total_size', 0) or 0
            
            # 汇总按类型统计
            for rtype, count in site_result.get('summary_by_type', {}).items():
                if rtype not in result['summary_by_type']:
                    result['summary_by_type'][rtype] = 0
                result['summary_by_type'][rtype] += count
    
    # 添加总大小信息，并对 all_resources 按大小排序
    if fetch_size:
        result['total_size'] = total_size
        result['total_size_formatted'] = format_file_size(total_size)
        # 按文件大小从大到小排序
        result['all_resources'] = sorted(
            result['all_resources'], 
            key=lambda r: r.get('size') or 0, 
            reverse=True
        )
    
    return result


async def test_selected_resources(
    resources: List[Dict[str, str]],
    timeout: int = 10,
    concurrency: int = 10,
    enhanced: bool = False,
    custom_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    测试选定的资源列表
    
    Args:
        resources: 资源列表，每个资源需要包含 url 和 resource_type
        timeout: 单个请求超时时间（秒）
        concurrency: 并发请求数
        enhanced: 是否启用增强测试
        custom_headers: 自定义请求头
    
    Returns:
        测试结果字典
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    if custom_headers:
        headers.update(custom_headers)
    
    result = {
        'total': len(resources),
        'accessible_count': 0,
        'inaccessible_count': 0,
        'warning_count': 0,
        'enhanced_mode': enhanced,
        'results': [],
        'summary_by_type': {},
        'error': None
    }
    
    try:
        connector = aiohttp.TCPConnector(limit=concurrency, ssl=False)
        
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            semaphore = asyncio.Semaphore(concurrency)
            
            async def test_with_semaphore(resource: Dict) -> ResourceResult:
                async with semaphore:
                    res = await test_resource_accessibility(
                        session,
                        resource['url'],
                        resource.get('resource_type', 'other'),
                        timeout,
                        enhanced=enhanced
                    )
                    # 保留来源 URL
                    if 'source_url' in resource:
                        res_dict = asdict(res)
                        res_dict['source_url'] = resource['source_url']
                        return res_dict
                    return asdict(res)
            
            tasks = [test_with_semaphore(r) for r in resources]
            test_results = await asyncio.gather(*tasks)
            
            for r in test_results:
                result['results'].append(r)
                
                if r['accessible']:
                    result['accessible_count'] += 1
                else:
                    result['inaccessible_count'] += 1
                
                if r.get('warnings'):
                    result['warning_count'] += 1
                
                # 按类型统计
                rtype = r['resource_type']
                if rtype not in result['summary_by_type']:
                    result['summary_by_type'][rtype] = {
                        'total': 0,
                        'accessible': 0,
                        'inaccessible': 0,
                        'with_warnings': 0
                    }
                result['summary_by_type'][rtype]['total'] += 1
                if r['accessible']:
                    result['summary_by_type'][rtype]['accessible'] += 1
                else:
                    result['summary_by_type'][rtype]['inaccessible'] += 1
                if r.get('warnings'):
                    result['summary_by_type'][rtype]['with_warnings'] += 1
    
    except Exception as e:
        result['error'] = f"测试过程出错: {str(e)}"
    
    return result


async def crawl_and_test_resources(
    target_url: str,
    filter_ids: Optional[List[str]] = None,
    timeout: int = 10,
    concurrency: int = 10,
    include_types: Optional[List[str]] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    enhanced: bool = False
) -> Dict[str, Any]:
    """
    爬取并测试网站资源连通性
    
    Args:
        target_url: 目标网页 URL
        filter_ids: 过滤 ID 列表，只返回 URL 中包含这些 ID 的资源
        timeout: 单个请求超时时间（秒）
        concurrency: 并发请求数
        include_types: 只包含特定类型的资源
        custom_headers: 自定义请求头
    
    Returns:
        测试结果字典
    """
    # 默认请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }
    
    if custom_headers:
        headers.update(custom_headers)
    
    result = {
        'target_url': target_url,
        'total_resources': 0,
        'tested_resources': 0,
        'accessible_count': 0,
        'inaccessible_count': 0,
        'resources': [],
        'filtered_resources': [],
        'summary_by_type': {},
        'error': None
    }
    
    try:
        # 创建连接器
        connector = aiohttp.TCPConnector(limit=concurrency, ssl=False)
        
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            # 1. 获取目标页面
            try:
                async with session.get(
                    target_url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    allow_redirects=True
                ) as response:
                    if response.status != 200:
                        result['error'] = f"无法获取目标页面: HTTP {response.status}"
                        return result
                    
                    html = await response.text()
                    final_url = str(response.url)
                    
            except Exception as e:
                result['error'] = f"获取目标页面失败: {str(e)}"
                return result
            
            # 2. 提取资源
            resources = extract_resources_from_html(html, final_url)
            result['total_resources'] = len(resources)
            
            # 3. 根据类型过滤
            if include_types:
                resources = [r for r in resources if r['resource_type'] in include_types]
            
            # 4. 并发测试资源
            semaphore = asyncio.Semaphore(concurrency)
            
            async def test_with_semaphore(resource: Dict) -> ResourceResult:
                async with semaphore:
                    return await test_resource_accessibility(
                        session,
                        resource['url'],
                        resource['resource_type'],
                        timeout,
                        enhanced=enhanced
                    )
            
            # 执行测试
            tasks = [test_with_semaphore(r) for r in resources]
            test_results = await asyncio.gather(*tasks)
            
            # 5. 整理结果
            all_results = [asdict(r) for r in test_results]
            result['resources'] = all_results
            result['tested_resources'] = len(all_results)
            
            # 统计
            for r in all_results:
                if r['accessible']:
                    result['accessible_count'] += 1
                else:
                    result['inaccessible_count'] += 1
                
                # 按类型统计
                rtype = r['resource_type']
                if rtype not in result['summary_by_type']:
                    result['summary_by_type'][rtype] = {
                        'total': 0,
                        'accessible': 0,
                        'inaccessible': 0
                    }
                result['summary_by_type'][rtype]['total'] += 1
                if r['accessible']:
                    result['summary_by_type'][rtype]['accessible'] += 1
                else:
                    result['summary_by_type'][rtype]['inaccessible'] += 1
            
            # 6. 根据 ID 过滤
            if filter_ids:
                filtered = []
                for r in all_results:
                    url = r['url']
                    for filter_id in filter_ids:
                        if filter_id in url:
                            r['matched_id'] = filter_id
                            filtered.append(r)
                            break
                result['filtered_resources'] = filtered
    
    except Exception as e:
        result['error'] = f"测试过程出错: {str(e)}"
    
    return result


async def test_single_resource(
    url: str,
    timeout: int = 10,
    custom_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """测试单个资源的可访问性"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    if custom_headers:
        headers.update(custom_headers)
    
    resource_type = guess_resource_type(url)
    
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        result = await test_resource_accessibility(session, url, resource_type, timeout)
        return asdict(result)


async def batch_test_urls(
    urls: List[str],
    timeout: int = 10,
    concurrency: int = 10,
    custom_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """批量测试 URL 列表的可访问性"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    if custom_headers:
        headers.update(custom_headers)
    
    result = {
        'total': len(urls),
        'accessible_count': 0,
        'inaccessible_count': 0,
        'results': []
    }
    
    connector = aiohttp.TCPConnector(limit=concurrency, ssl=False)
    async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
        semaphore = asyncio.Semaphore(concurrency)
        
        async def test_with_semaphore(url: str) -> ResourceResult:
            async with semaphore:
                resource_type = guess_resource_type(url)
                return await test_resource_accessibility(session, url, resource_type, timeout)
        
        tasks = [test_with_semaphore(url) for url in urls]
        test_results = await asyncio.gather(*tasks)
        
        for r in test_results:
            r_dict = asdict(r)
            result['results'].append(r_dict)
            if r.accessible:
                result['accessible_count'] += 1
            else:
                result['inaccessible_count'] += 1
    
    return result


async def batch_crawl_and_test(
    target_urls: List[str],
    filter_ids: Optional[List[str]] = None,
    timeout: int = 10,
    concurrency: int = 10,
    include_types: Optional[List[str]] = None,
    custom_headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    批量爬取多个网站并测试资源连通性
    
    Args:
        target_urls: 目标网页 URL 列表
        filter_ids: 过滤 ID 列表，用于筛选资源
        timeout: 单个请求超时时间（秒）
        concurrency: 并发请求数
        include_types: 只包含特定类型的资源
        custom_headers: 自定义请求头
    
    Returns:
        测试结果字典
    """
    result = {
        'total_sites': len(target_urls),
        'success_sites': 0,
        'failed_sites': 0,
        'total_resources': 0,
        'tested_resources': 0,
        'accessible_count': 0,
        'inaccessible_count': 0,
        'sites': [],  # 每个网站的详细结果
        'all_resources': [],  # 所有资源汇总
        'filtered_resources': [],  # ID 过滤后的资源
        'filter_summary': {},  # ID 过滤统计
        'summary_by_type': {},
        'error': None
    }
    
    # 初始化 ID 过滤统计
    if filter_ids:
        for fid in filter_ids:
            result['filter_summary'][fid] = {
                'found': False,
                'count': 0,
                'accessible': 0,
                'inaccessible': 0,
                'resources': []
            }
    
    # 逐个处理网站
    for target_url in target_urls:
        site_result = await crawl_and_test_resources(
            target_url=target_url,
            filter_ids=filter_ids,
            timeout=timeout,
            concurrency=concurrency,
            include_types=include_types,
            custom_headers=custom_headers
        )
        
        # 添加来源 URL 到每个资源
        for r in site_result.get('resources', []):
            r['source_url'] = target_url
        for r in site_result.get('filtered_resources', []):
            r['source_url'] = target_url
        
        result['sites'].append(site_result)
        
        if site_result.get('error'):
            result['failed_sites'] += 1
        else:
            result['success_sites'] += 1
            result['total_resources'] += site_result.get('total_resources', 0)
            result['tested_resources'] += site_result.get('tested_resources', 0)
            result['accessible_count'] += site_result.get('accessible_count', 0)
            result['inaccessible_count'] += site_result.get('inaccessible_count', 0)
            
            # 汇总所有资源
            result['all_resources'].extend(site_result.get('resources', []))
            
            # 汇总按类型统计
            for rtype, stats in site_result.get('summary_by_type', {}).items():
                if rtype not in result['summary_by_type']:
                    result['summary_by_type'][rtype] = {
                        'total': 0,
                        'accessible': 0,
                        'inaccessible': 0
                    }
                result['summary_by_type'][rtype]['total'] += stats['total']
                result['summary_by_type'][rtype]['accessible'] += stats['accessible']
                result['summary_by_type'][rtype]['inaccessible'] += stats['inaccessible']
            
            # 汇总过滤资源并更新 ID 统计
            for r in site_result.get('filtered_resources', []):
                result['filtered_resources'].append(r)
                matched_id = r.get('matched_id')
                if matched_id and matched_id in result['filter_summary']:
                    result['filter_summary'][matched_id]['found'] = True
                    result['filter_summary'][matched_id]['count'] += 1
                    result['filter_summary'][matched_id]['resources'].append(r)
                    if r.get('accessible'):
                        result['filter_summary'][matched_id]['accessible'] += 1
                    else:
                        result['filter_summary'][matched_id]['inaccessible'] += 1
    
    return result
