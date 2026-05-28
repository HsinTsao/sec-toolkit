"""CSP 字符串解析器"""
from typing import Dict, List


def parse_csp(raw: str) -> Dict[str, List[str]]:
    """
    将 CSP 字符串解析为 {指令名: [值列表]} 的字典。

    示例:
        "default-src 'self'; script-src 'self' cdn.example.com"
        ->
        {"default-src": ["'self'"], "script-src": ["'self'", "cdn.example.com"]}
    """
    directives: Dict[str, List[str]] = {}
    if not raw or not raw.strip():
        return directives

    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if not tokens:
            continue
        name = tokens[0].lower()
        values = tokens[1:]
        directives[name] = values

    return directives
