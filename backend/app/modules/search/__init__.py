"""
搜索模块 - 网络搜索功能

提供网络搜索能力，自动选择可用的搜索引擎：
- 国内环境优先级：Bing 中国 > 搜狗 > 百度（反爬严格）
- 国外环境：DuckDuckGo (ddgs)

使用示例:
    from app.modules.search import web_search
    
    results = await web_search("Python 教程", max_results=5)
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)


async def web_search(
    query: str,
    max_results: int = 5,
    engine: str = "auto",
) -> List[Dict[str, str]]:
    """
    网络搜索
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数（1-10）
        engine: 搜索引擎 (auto/sogou/ddgs)
        
    Returns:
        搜索结果列表，每项包含 title, url, snippet
    """
    logger.info(f"[WebSearch] 搜索: {query}, engine={engine}, max={max_results}")
    
    max_results = min(max(1, max_results), 10)
    
    if engine == "auto":
        # 自动选择：Bing（国内最佳）> 搜狗 > ddgs
        results = await _bing_search(query, max_results)
        if results:
            return results
        results = await _sogou_search(query, max_results)
        if results:
            return results
        return await _ddgs_search(query, max_results)
    elif engine == "bing":
        return await _bing_search(query, max_results)
    elif engine == "sogou":
        return await _sogou_search(query, max_results)
    elif engine == "ddgs":
        return await _ddgs_search(query, max_results)
    else:
        return await _bing_search(query, max_results)


async def _bing_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Bing 中国搜索（国内首选）"""
    import httpx
    
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("[WebSearch] BeautifulSoup 未安装")
        return []
    
    try:
        # 使用 Bing 中国版
        search_url = f"https://cn.bing.com/search?q={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        logger.info(f"[WebSearch] 使用 Bing 搜索: {query}")
        
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"[WebSearch] Bing 返回状态码: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            results = []
            # Bing 搜索结果选择器
            items = soup.select(".b_algo")
            
            for item in items[:max_results]:
                # 标题和链接
                title_el = item.select_one("h2 a")
                if not title_el:
                    continue
                    
                title = title_el.get_text().strip()
                url = title_el.get("href", "")
                
                # 摘要
                snippet_el = item.select_one(".b_caption p, .b_lineclamp2, .b_paractl")
                snippet = snippet_el.get_text().strip() if snippet_el else ""
                
                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet[:200] if snippet else "",
                    })
            
            logger.info(f"[WebSearch] Bing 找到 {len(results)} 条结果")
            return results
            
    except Exception as e:
        logger.error(f"[WebSearch] Bing 搜索失败: {e}")
        return []


async def _ddgs_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """DuckDuckGo 搜索（国外环境）"""
    try:
        from ddgs import DDGS
        
        results = []
        ddgs = DDGS(timeout=10)
        for r in ddgs.text(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", r.get("link", "")),
                "snippet": r.get("body", r.get("snippet", "")),
            })
        
        logger.info(f"[WebSearch] ddgs 找到 {len(results)} 条结果")
        return results
        
    except Exception as e:
        logger.warning(f"[WebSearch] ddgs 搜索失败: {e}")
        return []


async def _sogou_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """搜狗搜索（国内环境）"""
    import httpx
    
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("[WebSearch] BeautifulSoup 未安装")
        return []
    
    try:
        search_url = f"https://www.sogou.com/web?query={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        
        logger.info(f"[WebSearch] 使用搜狗搜索: {query}")
        
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            
            if response.status_code != 200:
                logger.warning(f"[WebSearch] 搜狗返回状态码: {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            results = []
            # 搜狗搜索结果选择器
            items = soup.select(".vrwrap, .rb, .results .result")
            
            for item in items[:max_results]:
                # 标题和链接
                title_el = item.select_one("h3 a, .vr-title a, .pt a")
                if not title_el:
                    continue
                    
                title = title_el.get_text().strip()
                url = title_el.get("href", "")
                
                # 摘要
                snippet_el = item.select_one(".str_time, .space-txt, .str-text, .text-layout")
                snippet = snippet_el.get_text().strip() if snippet_el else ""
                
                if title and url:
                    # 处理相对 URL
                    if url.startswith("/link?"):
                        url = f"https://www.sogou.com{url}"
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet[:200] if snippet else "",
                    })
            
            logger.info(f"[WebSearch] 搜狗找到 {len(results)} 条结果")
            return results
            
    except Exception as e:
        logger.error(f"[WebSearch] 搜狗搜索失败: {e}")
        return []


async def news_search(
    query: str,
    max_results: int = 5,
) -> List[Dict[str, str]]:
    """
    新闻搜索（使用搜狗新闻）
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数
        
    Returns:
        新闻结果列表
    """
    import httpx
    
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("[NewsSearch] BeautifulSoup 未安装")
        return []
    
    logger.info(f"[NewsSearch] 搜索: {query}")
    
    try:
        search_url = f"https://news.sogou.com/news?query={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
        }
        
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(search_url, headers=headers)
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            results = []
            items = soup.select(".news-list li, .vrwrap")
            
            for item in items[:max_results]:
                title_el = item.select_one("h3 a, .news-title a")
                if not title_el:
                    continue
                    
                title = title_el.get_text().strip()
                url = title_el.get("href", "")
                
                snippet_el = item.select_one(".news-txt, .txt-info")
                snippet = snippet_el.get_text().strip() if snippet_el else ""
                
                source_el = item.select_one(".news-from, .news-source")
                source = source_el.get_text().strip() if source_el else ""
                
                if title and url:
                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet[:200] if snippet else "",
                        "source": source,
                    })
            
            logger.info(f"[NewsSearch] 找到 {len(results)} 条新闻")
            return results
            
    except Exception as e:
        logger.error(f"[NewsSearch] 失败: {e}")
        return []
