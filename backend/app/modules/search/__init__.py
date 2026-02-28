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
import base64
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

logger = logging.getLogger(__name__)


def _decode_sogou_url(sogou_link: str) -> str:
    """
    解析搜狗跳转链接，提取真实 URL
    
    搜狗的 /link?url= 参数中包含编码后的真实 URL
    """
    try:
        if "/link?" not in sogou_link:
            return sogou_link
        
        parsed = urlparse(sogou_link)
        params = parse_qs(parsed.query)
        
        if "url" not in params:
            return sogou_link
        
        encoded_url = params["url"][0]
        
        # 尝试多种解码方式
        # 方式1: 直接 URL 解码
        try:
            decoded = unquote(encoded_url)
            if decoded.startswith("http"):
                return decoded
        except:
            pass
        
        # 方式2: Base64 解码
        try:
            # 补齐 padding
            padding = 4 - len(encoded_url) % 4
            if padding != 4:
                encoded_url_padded = encoded_url + "=" * padding
            else:
                encoded_url_padded = encoded_url
            decoded = base64.b64decode(encoded_url_padded).decode("utf-8")
            if decoded.startswith("http"):
                return decoded
        except:
            pass
        
        # 方式3: URL 安全的 Base64 解码
        try:
            padding = 4 - len(encoded_url) % 4
            if padding != 4:
                encoded_url_padded = encoded_url + "=" * padding
            else:
                encoded_url_padded = encoded_url
            decoded = base64.urlsafe_b64decode(encoded_url_padded).decode("utf-8")
            if decoded.startswith("http"):
                return decoded
        except:
            pass
        
        # 无法解码，返回原链接
        return sogou_link
        
    except Exception as e:
        logger.warning(f"[Search] 解析搜狗链接失败: {e}")
        return sogou_link


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
        # 自动选择：Bing（国内最佳）> 搜狗
        # DuckDuckGo 国内无法访问，暂时禁用
        results = await _bing_search(query, max_results)
        if results:
            return results
        return await _sogou_search(query, max_results)
    elif engine == "bing":
        return await _bing_search(query, max_results)
    elif engine == "sogou":
        return await _sogou_search(query, max_results)
    elif engine == "ddgs":
        # DuckDuckGo 国内无法访问，回退到 Bing
        logger.warning("[WebSearch] DuckDuckGo 国内无法访问，使用 Bing 替代")
        return await _bing_search(query, max_results)
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
                    # Bing 有时也返回跳转链接，尝试处理
                    if "bing.com/ck/a" in url or "/link?" in url:
                        try:
                            head_resp = await client.head(url, follow_redirects=True, timeout=5)
                            if str(head_resp.url).startswith("http"):
                                url = str(head_resp.url)
                        except:
                            pass  # 保留原链接
                    
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
                    # 处理搜狗跳转链接，解析真实 URL
                    if url.startswith("/link?"):
                        full_url = f"https://www.sogou.com{url}"
                        real_url = _decode_sogou_url(full_url)
                        # 如果解码失败（仍是跳转链接），尝试通过 HEAD 请求获取真实 URL
                        if "/link?" in real_url:
                            try:
                                head_resp = await client.head(full_url, follow_redirects=True)
                                if str(head_resp.url).startswith("http") and "/link?" not in str(head_resp.url):
                                    url = str(head_resp.url)
                                else:
                                    url = full_url  # 保留跳转链接
                            except:
                                url = full_url
                        else:
                            url = real_url
                    
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
    新闻搜索（优先 DuckDuckGo，备选 Bing 新闻站点搜索）
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数
        
    Returns:
        新闻结果列表
    """
    logger.info(f"[NewsSearch] 搜索: {query}")
    
    # DuckDuckGo 国内无法访问，暂时禁用
    # results = await _ddgs_news_search(query, max_results)
    # if results:
    #     return results
    
    # 使用 Bing 搜索
    # 构建优化的新闻查询：关键词 + 新闻/最新/资讯
    news_query = _build_news_query(query)
    results = await _bing_search(news_query, max_results * 2)  # 多搜一些，后面过滤
    
    if results:
        # 过滤出新闻网站的结果
        news_domains = [
            "news.qq.com", "news.sina.com", "news.163.com", "news.sohu.com",
            "thepaper.cn", "36kr.com", "huxiu.com", "wallstreetcn.com",
            "caixin.com", "yicai.com", "jiemian.com", "mydrivers.com",
            "ithome.com", "cnbeta.com", "ifanr.com", "geekpark.net",
            "bbc.com", "cnn.com", "reuters.com", "bloomberg.com",
        ]
        
        filtered = []
        for r in results:
            url = r.get("url", "").lower()
            # 优先包含新闻域名的结果
            is_news = any(domain in url for domain in news_domains)
            # 或者 URL 包含 news/article 等关键词
            is_news = is_news or any(kw in url for kw in ["/news/", "/article/", "/a/", "/p/"])
            
            if is_news:
                filtered.append({"title": r["title"], "url": r["url"], "snippet": r["snippet"], "source": ""})
        
        # 如果过滤后有结果，返回过滤后的；否则返回原结果
        if filtered:
            return filtered[:max_results]
        return [{"title": r["title"], "url": r["url"], "snippet": r["snippet"], "source": ""} for r in results[:max_results]]
    
    return []


def _build_news_query(query: str) -> str:
    """构建新闻搜索查询"""
    # 如果已包含"新闻"关键词，直接返回
    if "新闻" in query:
        return query
    
    # 移除可能影响搜索的词（如"最新消息"改为"最新新闻"效果更好）
    query = query.replace("最新消息", "").replace("消息", "").replace("资讯", "").strip()
    
    # 添加"最新新闻"关键词（测试表明这个组合效果最好）
    return f"{query} 最新新闻"


async def _ddgs_news_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """DuckDuckGo 新闻搜索"""
    try:
        from ddgs import DDGS
        
        logger.info(f"[NewsSearch] 使用 DuckDuckGo 新闻搜索: {query}")
        
        results = []
        ddgs = DDGS(timeout=15)
        for r in ddgs.news(query, max_results=max_results):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", r.get("link", "")),
                "snippet": r.get("body", r.get("excerpt", "")),
                "source": r.get("source", ""),
            })
        
        logger.info(f"[NewsSearch] DuckDuckGo 找到 {len(results)} 条新闻")
        return results
        
    except ImportError:
        logger.warning("[NewsSearch] ddgs 未安装")
        return []
    except Exception as e:
        logger.warning(f"[NewsSearch] DuckDuckGo 新闻搜索失败: {e}")
        return []


