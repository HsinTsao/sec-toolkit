"""
浏览器模块 - 无头浏览器操作

提供基于 Playwright 的无头浏览器功能，可集成到 LLM Agent 中。

功能:
- 页面访问和渲染（支持 JavaScript）
- 页面截图
- PDF 生成
- JavaScript 执行
- 元素交互（点击、输入、选择）
- 页面信息提取

使用示例:
    from app.modules.browser import BrowserManager
    
    async with BrowserManager() as browser:
        # 访问页面
        result = await browser.goto("https://example.com")
        
        # 截图
        screenshot = await browser.screenshot()
        
        # 执行 JS
        title = await browser.evaluate("document.title")
"""

import os
import logging
import base64
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# 设置 Playwright 浏览器路径
# 优先使用环境变量，其次查找常见位置
import glob
_browser_paths = glob.glob('/tmp/cursor-sandbox-cache/*/playwright') + ['/root/.cache/ms-playwright']
for _path in _browser_paths:
    if os.path.exists(_path):
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = _path
        break
else:
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'  # 使用默认位置


class BrowserError(Exception):
    """浏览器操作错误"""
    pass


class WaitUntil(str, Enum):
    """页面加载等待策略"""
    LOAD = "load"                    # 完全加载
    DOMCONTENTLOADED = "domcontentloaded"  # DOM 加载完成
    NETWORKIDLE = "networkidle"      # 网络空闲


@dataclass
class PageInfo:
    """页面信息"""
    url: str
    title: str
    html: str
    text: str = ""
    links: List[Dict[str, str]] = field(default_factory=list)
    images: List[Dict[str, str]] = field(default_factory=list)
    forms: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BrowserConfig:
    """浏览器配置"""
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    timeout: int = 30000  # 毫秒
    ignore_https_errors: bool = True
    extra_args: List[str] = field(default_factory=lambda: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage'
    ])


class BrowserManager:
    """
    浏览器管理器
    
    支持异步上下文管理器，自动管理浏览器生命周期。
    
    使用示例:
        async with BrowserManager() as browser:
            await browser.goto("https://example.com")
            html = await browser.content()
    """
    
    def __init__(self, config: Optional[BrowserConfig] = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def start(self):
        """启动浏览器"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise BrowserError("Playwright 未安装，请运行: pip install playwright && playwright install chromium")
        
        logger.info("[Browser] 启动浏览器...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.config.headless,
            args=self.config.extra_args
        )
        self._context = await self._browser.new_context(
            user_agent=self.config.user_agent,
            viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height},
            ignore_https_errors=self.config.ignore_https_errors
        )
        self._page = await self._context.new_page()
        logger.info("[Browser] 浏览器启动成功")
    
    async def close(self):
        """关闭浏览器"""
        logger.info("[Browser] 关闭浏览器...")
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
    
    @property
    def page(self):
        """获取当前页面"""
        if not self._page:
            raise BrowserError("浏览器未启动，请先调用 start() 或使用 async with")
        return self._page
    
    async def goto(
        self,
        url: str,
        wait_until: WaitUntil = WaitUntil.DOMCONTENTLOADED,
        wait_time: float = 0,
        wait_for_selector: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        访问页面
        
        Args:
            url: 目标 URL
            wait_until: 等待策略
            wait_time: 额外等待时间（秒）
            wait_for_selector: 等待特定元素出现
            
        Returns:
            包含 url, title, status 的字典
        """
        logger.info(f"[Browser] 访问: {url}")
        
        try:
            response = await self.page.goto(
                url,
                wait_until=wait_until.value,
                timeout=self.config.timeout
            )
            status = response.status if response else None
        except Exception as e:
            logger.warning(f"[Browser] 页面加载异常: {e}")
            status = None
        
        # 额外等待
        if wait_for_selector:
            try:
                await self.page.wait_for_selector(wait_for_selector, timeout=int(wait_time * 1000) or 5000)
            except Exception:
                pass
        elif wait_time > 0:
            await self.page.wait_for_timeout(int(wait_time * 1000))
        
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "status": status
        }
    
    async def content(self) -> str:
        """获取页面 HTML"""
        return await self.page.content()
    
    async def text(self) -> str:
        """获取页面纯文本"""
        return await self.page.inner_text("body")
    
    async def screenshot(
        self,
        full_page: bool = False,
        path: Optional[str] = None,
        format: str = "png"
    ) -> Union[bytes, str]:
        """
        页面截图
        
        Args:
            full_page: 是否截取整个页面
            path: 保存路径（可选）
            format: 图片格式 (png/jpeg)
            
        Returns:
            如果指定 path 则返回路径，否则返回 base64 编码的图片
        """
        logger.info(f"[Browser] 截图: full_page={full_page}")
        
        screenshot_bytes = await self.page.screenshot(
            full_page=full_page,
            type=format
        )
        
        if path:
            with open(path, "wb") as f:
                f.write(screenshot_bytes)
            return path
        
        return base64.b64encode(screenshot_bytes).decode()
    
    async def pdf(self, path: Optional[str] = None) -> Union[bytes, str]:
        """
        生成 PDF
        
        Args:
            path: 保存路径（可选）
            
        Returns:
            如果指定 path 则返回路径，否则返回 base64 编码的 PDF
        """
        logger.info("[Browser] 生成 PDF")
        
        pdf_bytes = await self.page.pdf(format="A4")
        
        if path:
            with open(path, "wb") as f:
                f.write(pdf_bytes)
            return path
        
        return base64.b64encode(pdf_bytes).decode()
    
    async def evaluate(self, script: str) -> Any:
        """
        执行 JavaScript
        
        Args:
            script: JavaScript 代码
            
        Returns:
            执行结果
        """
        logger.info(f"[Browser] 执行 JS: {script[:50]}...")
        return await self.page.evaluate(script)
    
    async def click(self, selector: str) -> bool:
        """
        点击元素
        
        Args:
            selector: CSS 选择器
            
        Returns:
            是否成功
        """
        logger.info(f"[Browser] 点击: {selector}")
        try:
            await self.page.click(selector, timeout=5000)
            return True
        except Exception as e:
            logger.warning(f"[Browser] 点击失败: {e}")
            return False
    
    async def fill(self, selector: str, value: str) -> bool:
        """
        填写输入框
        
        Args:
            selector: CSS 选择器
            value: 要填写的值
            
        Returns:
            是否成功
        """
        logger.info(f"[Browser] 填写: {selector} = {value[:20]}...")
        try:
            await self.page.fill(selector, value, timeout=5000)
            return True
        except Exception as e:
            logger.warning(f"[Browser] 填写失败: {e}")
            return False
    
    async def select(self, selector: str, value: str) -> bool:
        """
        选择下拉框选项
        
        Args:
            selector: CSS 选择器
            value: 选项值
            
        Returns:
            是否成功
        """
        logger.info(f"[Browser] 选择: {selector} = {value}")
        try:
            await self.page.select_option(selector, value, timeout=5000)
            return True
        except Exception as e:
            logger.warning(f"[Browser] 选择失败: {e}")
            return False
    
    async def scroll(self, direction: str = "down", distance: int = 500) -> None:
        """
        滚动页面
        
        Args:
            direction: 方向 (up/down)
            distance: 滚动距离（像素）
        """
        delta = distance if direction == "down" else -distance
        await self.page.mouse.wheel(0, delta)
    
    async def scroll_to_bottom(self) -> None:
        """滚动到页面底部（触发懒加载）"""
        logger.info("[Browser] 滚动到底部")
        await self.page.evaluate('''
            async () => {
                const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                for (let i = 0; i < 5; i++) {
                    window.scrollTo(0, document.body.scrollHeight);
                    await delay(300);
                }
            }
        ''')
    
    async def get_page_info(self) -> PageInfo:
        """
        获取页面详细信息
        
        Returns:
            PageInfo 对象，包含 URL、标题、HTML、链接、图片等
        """
        logger.info("[Browser] 获取页面信息")
        
        info = await self.page.evaluate('''
            () => {
                const links = Array.from(document.querySelectorAll('a[href]')).slice(0, 50).map(a => ({
                    text: a.innerText.trim().slice(0, 100),
                    href: a.href
                }));
                
                const images = Array.from(document.querySelectorAll('img[src]')).slice(0, 20).map(img => ({
                    alt: img.alt || '',
                    src: img.src
                }));
                
                const forms = Array.from(document.querySelectorAll('form')).slice(0, 10).map(form => ({
                    action: form.action,
                    method: form.method,
                    inputs: Array.from(form.querySelectorAll('input, select, textarea')).map(el => ({
                        type: el.type || el.tagName.toLowerCase(),
                        name: el.name,
                        id: el.id
                    }))
                }));
                
                return { links, images, forms };
            }
        ''')
        
        return PageInfo(
            url=self.page.url,
            title=await self.page.title(),
            html=await self.page.content(),
            text=await self.page.inner_text("body"),
            links=info.get("links", []),
            images=info.get("images", []),
            forms=info.get("forms", [])
        )
    
    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> bool:
        """
        等待元素出现
        
        Args:
            selector: CSS 选择器
            timeout: 超时时间（毫秒）
            
        Returns:
            元素是否出现
        """
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False


# ==================== 便捷函数 ====================

async def render_page(
    url: str,
    wait_time: float = 2,
    wait_for_selector: Optional[str] = None,
    screenshot: bool = False,
    full_page: bool = False
) -> Dict[str, Any]:
    """
    渲染页面并获取内容（便捷函数）
    
    Args:
        url: 目标 URL
        wait_time: 等待时间（秒）
        wait_for_selector: 等待特定元素
        screenshot: 是否截图
        full_page: 是否全页截图
        
    Returns:
        包含 html, url, title, screenshot(可选) 的字典
    """
    result = {}
    
    async with BrowserManager() as browser:
        await browser.goto(url, wait_time=wait_time, wait_for_selector=wait_for_selector)
        await browser.scroll_to_bottom()
        await browser.page.wait_for_timeout(1000)
        
        result["url"] = browser.page.url
        result["title"] = await browser.page.title()
        result["html"] = await browser.content()
        
        if screenshot:
            result["screenshot"] = await browser.screenshot(full_page=full_page)
    
    return result


async def take_screenshot(
    url: str,
    full_page: bool = True,
    wait_time: float = 2
) -> str:
    """
    截取页面截图（便捷函数）
    
    Args:
        url: 目标 URL
        full_page: 是否全页截图
        wait_time: 等待时间（秒）
        
    Returns:
        base64 编码的图片
    """
    async with BrowserManager() as browser:
        await browser.goto(url, wait_time=wait_time)
        return await browser.screenshot(full_page=full_page)


async def execute_js(url: str, script: str, wait_time: float = 2) -> Any:
    """
    在页面中执行 JavaScript（便捷函数）
    
    Args:
        url: 目标 URL
        script: JavaScript 代码
        wait_time: 等待时间（秒）
        
    Returns:
        执行结果
    """
    async with BrowserManager() as browser:
        await browser.goto(url, wait_time=wait_time)
        return await browser.evaluate(script)
