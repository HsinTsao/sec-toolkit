"""获取目标 URL 的 CSP 头"""
import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

TIMEOUT = 10
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _normalize_url(url: str) -> str:
    """补全协议前缀"""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


async def fetch_csp(url: str) -> dict:
    """
    请求目标 URL 并提取 CSP 相关响应头。

    策略：先用 HEAD（快速拿 header），如果 header 里没有 CSP 再用 GET 检查 meta 标签。
    """
    url = _normalize_url(url)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=TIMEOUT,
            verify=False,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            # 先 HEAD，只拿响应头，不下载 body
            resp = await client.head(url)

            csp = resp.headers.get("content-security-policy", "")
            csp_ro = resp.headers.get("content-security-policy-report-only", "")

            meta_csp = None
            if not csp:
                # header 里没有 CSP，做一次 GET 检查 <meta> 标签
                try:
                    get_resp = await client.get(url)
                    csp = get_resp.headers.get("content-security-policy", "")
                    csp_ro = csp_ro or get_resp.headers.get("content-security-policy-report-only", "")
                    if not csp:
                        meta_csp = _extract_meta_csp(get_resp.text)
                    resp = get_resp
                except Exception:
                    pass

        return {
            "url": str(resp.url),
            "status_code": resp.status_code,
            "csp": csp or meta_csp or "",
            "csp_report_only": csp_ro,
            "csp_source": "header" if csp else ("meta" if meta_csp else "none"),
            "error": None,
        }
    except httpx.ConnectError as e:
        return {"url": url, "csp": "", "error": f"连接失败: {e}"}
    except httpx.TimeoutException:
        return {"url": url, "csp": "", "error": f"请求超时 ({TIMEOUT}s)"}
    except Exception as e:
        logger.exception("fetch_csp 异常")
        return {"url": url, "csp": "", "error": str(e)}


def _extract_meta_csp(html: str) -> Optional[str]:
    """从 HTML <meta> 标签中提取 CSP"""
    import re
    pattern = re.compile(
        r'<meta\s+http-equiv=["\']Content-Security-Policy["\']\s+content=["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    m = pattern.search(html)
    return m.group(1) if m else None
