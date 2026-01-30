"""
浏览器工具 - LLM Agent 可调用的浏览器操作

提供以下工具:
- browser_goto: 访问网页
- browser_screenshot: 页面截图
- browser_get_content: 获取页面内容
- browser_execute_js: 执行 JavaScript
"""

from ..base import ToolParameter, ParameterType
from ..registry import ToolRegistry


async def browser_goto(url: str, wait_time: float = 2) -> dict:
    """使用无头浏览器访问网页"""
    from ...modules.browser import BrowserManager
    
    async with BrowserManager() as browser:
        result = await browser.goto(url, wait_time=wait_time)
        await browser.scroll_to_bottom()
        text = await browser.text()
        return {
            "url": result["url"],
            "title": result["title"],
            "text_preview": text[:500] + "..." if len(text) > 500 else text
        }


async def browser_screenshot(url: str, full_page: bool = False) -> dict:
    """对网页进行截图"""
    from ...modules.browser import take_screenshot
    
    screenshot = await take_screenshot(url=url, full_page=full_page)
    return {
        "url": url,
        "format": "png",
        "size_bytes": len(screenshot),
        "base64_data": screenshot
    }


async def browser_get_content(url: str) -> dict:
    """获取网页详细内容"""
    from ...modules.browser import BrowserManager
    
    async with BrowserManager() as browser:
        await browser.goto(url, wait_time=2)
        await browser.scroll_to_bottom()
        info = await browser.get_page_info()
        return {
            "url": info.url,
            "title": info.title,
            "text": info.text[:2000] if len(info.text) > 2000 else info.text,
            "links": info.links[:10],
            "images": info.images[:5],
            "forms": info.forms
        }


async def browser_execute_js(url: str, script: str) -> dict:
    """在网页中执行 JavaScript"""
    from ...modules.browser import execute_js
    
    result = await execute_js(url=url, script=script)
    return {"url": url, "result": result}


def register_browser_tools(registry: ToolRegistry) -> None:
    """注册浏览器工具"""
    
    registry.register_function(
        name="browser_goto",
        description="使用无头浏览器访问网页，支持 JavaScript 渲染。适用于需要 JS 渲染的动态页面。",
        func=browser_goto,
        parameters=[
            ToolParameter(name="url", type=ParameterType.STRING, description="要访问的网页 URL"),
            ToolParameter(name="wait_time", type=ParameterType.NUMBER, description="等待时间（秒）", required=False),
        ],
        category="browser",
    )
    
    registry.register_function(
        name="browser_screenshot",
        description="对网页进行截图，返回 base64 编码的 PNG 图片。",
        func=browser_screenshot,
        parameters=[
            ToolParameter(name="url", type=ParameterType.STRING, description="要截图的网页 URL"),
            ToolParameter(name="full_page", type=ParameterType.BOOLEAN, description="是否全页截图", required=False),
        ],
        category="browser",
    )
    
    registry.register_function(
        name="browser_get_content",
        description="获取网页详细内容，包括文本、链接、图片、表单等信息。",
        func=browser_get_content,
        parameters=[
            ToolParameter(name="url", type=ParameterType.STRING, description="要获取内容的网页 URL"),
        ],
        category="browser",
    )
    
    registry.register_function(
        name="browser_execute_js",
        description="在网页中执行 JavaScript 代码并返回结果。",
        func=browser_execute_js,
        parameters=[
            ToolParameter(name="url", type=ParameterType.STRING, description="网页 URL"),
            ToolParameter(name="script", type=ParameterType.STRING, description="JavaScript 代码"),
        ],
        category="browser",
    )
