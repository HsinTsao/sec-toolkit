"""
意图识别模块

定义用户意图分类和解析逻辑，用于双 LLM 架构的第一阶段。

架构说明:
    User Input → Intent LLM (~200 tokens) → Deterministic Router → Tool → Summary LLM

工作流程:
    1. Intent LLM 接收用户输入，输出结构化 JSON
    2. Deterministic Router 根据 JSON 调用相应工具
    3. 工具本地执行，0 token 消耗
    4. Summary LLM 将结果转换为自然语言回复
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
import re
import json
import logging

logger = logging.getLogger(__name__)


class IntentCategory(str, Enum):
    """意图分类"""
    ENCODE = "encode"          # 编码
    DECODE = "decode"          # 解码
    HASH = "hash"              # 哈希计算
    CRYPTO = "crypto"          # 加解密
    NETWORK = "network"        # 网络查询
    SEARCH = "search"          # 网络搜索（需要联网查询实时信息）
    BROWSER = "browser"        # 浏览器操作
    FINANCE = "finance"        # 股票/基金分析
    ANALYZE = "analyze"        # 安全分析（需要完整 LLM）
    CHAT = "chat"              # 普通聊天（fallback 到完整 LLM）


class ParsedIntent(BaseModel):
    """解析后的意图"""
    category: IntentCategory = Field(..., description="意图分类")
    tool: Optional[str] = Field(None, description="要调用的工具名称")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    confidence: float = Field(default=1.0, description="置信度 0-1")
    raw_input: str = Field(default="", description="原始用户输入")
    direct_response: Optional[str] = Field(None, description="模型的直接回复（无需工具时）")


# ==================== 意图识别 Prompt ====================

# Prompt 模板（工具列表动态生成）
INTENT_SYSTEM_PROMPT_TEMPLATE = """你是意图分类器。分析用户输入，返回 JSON 格式的工具调用。

## 重要规则（必须遵守）
1. 天气/气温/下雨/温度 → 必须用 weather 工具，提取城市到 location
2. 编码/解码 → 对应的 encode/decode 工具
3. 哈希/MD5/SHA → calculate_hash 工具
4. DNS/WHOIS/IP查询 → 网络工具
5. 搜索/新闻/价格 → web_search 或 news_search
6. 股票/基金/行情/股价/K线 → 股票分析工具（analyze_stock, get_stock_quote 等）
7. 只有纯聊天时才返回 chat

## 可用工具
{tools_table}

## 示例（必须严格参考）

输入: "苏州今天的天气如何？"
输出: {{"category": "search", "tool": "weather", "params": {{"location": "苏州"}}}}

输入: "北京天气怎么样"
输出: {{"category": "search", "tool": "weather", "params": {{"location": "北京"}}}}

输入: "今天会下雨吗"
输出: {{"category": "search", "tool": "weather", "params": {{}}}}

输入: "明天上海气温多少"
输出: {{"category": "search", "tool": "weather", "params": {{"location": "上海"}}}}

输入: "base64编码 hello"
输出: {{"category": "encode", "tool": "base64_encode", "params": {{"text": "hello"}}}}

输入: "查一下 google.com 的 DNS"
输出: {{"category": "network", "tool": "dns_lookup", "params": {{"target": "google.com"}}}}

输入: "最新的 AI 新闻"
输出: {{"category": "search", "tool": "news_search", "params": {{"query": "AI 新闻"}}}}

输入: "分析一下贵州茅台"
输出: {{"category": "finance", "tool": "analyze_stock", "params": {{"symbol": "600519", "market": "A"}}}}

输入: "600519 行情"
输出: {{"category": "finance", "tool": "get_stock_quote", "params": {{"symbol": "600519", "market": "A"}}}}

输入: "比亚迪的技术指标"
输出: {{"category": "finance", "tool": "get_technical_indicators", "params": {{"symbol": "002594", "market": "A"}}}}

输入: "腾讯控股最新新闻"
输出: {{"category": "finance", "tool": "get_stock_news", "params": {{"keyword": "00700"}}}}

输入: "搜索平安银行"
输出: {{"category": "finance", "tool": "search_stock", "params": {{"keyword": "平安银行", "market": "A"}}}}

输入: "你好"
输出: {{"category": "chat", "tool": null, "params": {{}}}}

只输出 JSON，不要解释。"""


def build_intent_system_prompt() -> str:
    """
    动态构建 Intent System Prompt
    
    从 tool_registry 获取实际注册的工具，生成工具列表
    重要工具（weather, web_search 等）放在前面
    """
    from .registry import tool_registry
    
    # 获取所有工具（返回 List[BaseTool]）
    tools = tool_registry.get_all()
    
    if not tools:
        return INTENT_SYSTEM_PROMPT_TEMPLATE.format(
            tools_table="（工具正在加载中...）"
        )
    
    # 工具优先级排序（重要的放前面）
    priority_order = [
        "weather",      # 天气查询最常用
        "web_search",   # 网络搜索
        "news_search",  # 新闻搜索
        # 股票分析工具
        "analyze_stock",  # 综合分析（最常用）
        "get_stock_quote",  # 实时行情
        "search_stock",  # 搜索股票
        "get_technical_indicators",  # 技术指标
        "get_stock_finance",  # 财务数据
        "get_stock_news",  # 股票新闻
        # 编码/哈希/网络
        "base64_encode", "base64_decode",
        "url_encode", "url_decode",
        "calculate_hash",
        "dns_lookup", "whois_lookup", "ip_info",
        "browser_goto",
    ]
    
    def sort_key(tool):
        try:
            return priority_order.index(tool.name)
        except ValueError:
            return 100  # 不在列表中的放后面
    
    tools_sorted = sorted(tools, key=sort_key)
    
    # 构建工具表格（只包含常用工具，避免太长）
    lines = ["| 工具 | 用途 | 参数 |", "|------|------|------|"]
    
    # 只显示前 15 个最常用的工具，避免 Prompt 太长
    for tool in tools_sorted[:15]:
        name = tool.name
        desc = tool.description[:35] + "..." if len(tool.description) > 35 else tool.description
        
        params = []
        for p in tool.parameters:
            param_str = p.name
            if not p.required:
                param_str += "(可选)"
            params.append(param_str)
        params_str = ", ".join(params) if params else "-"
        
        lines.append(f"| {name} | {desc} | {params_str} |")
    
    tools_table = "\n".join(lines)
    
    return INTENT_SYSTEM_PROMPT_TEMPLATE.format(tools_table=tools_table)


# 兼容旧代码：提供静态变量（首次访问时动态生成）
_cached_prompt = None

def get_intent_system_prompt() -> str:
    """获取 Intent System Prompt（带缓存）"""
    global _cached_prompt
    if _cached_prompt is None:
        _cached_prompt = build_intent_system_prompt()
    return _cached_prompt


def refresh_intent_prompt():
    """刷新 Prompt 缓存（添加新工具后调用）"""
    global _cached_prompt
    _cached_prompt = None


# 为了向后兼容，保留 INTENT_SYSTEM_PROMPT 变量名
# 但实际使用时应调用 get_intent_system_prompt()
INTENT_SYSTEM_PROMPT = None  # 将在首次使用时动态设置

INTENT_USER_TEMPLATE = "用户输入: {user_input}"


# 结果总结 Prompt
SUMMARY_SYSTEM_PROMPT = """你是数据展示助手。将工具结果转为用户友好的格式。

规则：
1. 股票分析：数据已预格式化，直接美化输出，用Markdown加粗关键数据，保持结构
2. 搜索/新闻：列出要点
3. 编码/哈希：简洁展示
4. 中文回复，不要重复输入内容"""

SUMMARY_USER_TEMPLATE = """工具: {tool_name}
参数: {input_text}
数据:
{result}

美化输出（保持数据完整）:"""


# ==================== 极简规则匹配（只用于 100% 确定的场景）====================
#
# 设计原则：
# 1. 规则匹配只处理"显式命令"，如 "base64编码 xxx"
# 2. 自然语言表达（如"苏州天气怎么样"）交给 Intent LLM
# 3. 规则是优化，不是必需品

# 极简规则：只匹配显式的工具调用命令
EXPLICIT_COMMAND_PATTERNS = [
    # Base64 显式命令
    (r"^base64\s*(?:编码|encode)\s+(.+)$", "base64_encode", {"text": 1}),
    (r"^base64\s*(?:解码|decode)\s+(.+)$", "base64_decode", {"text": 1}),
    # URL 显式命令
    (r"^url\s*(?:编码|encode)\s+(.+)$", "url_encode", {"text": 1}),
    (r"^url\s*(?:解码|decode)\s+(.+)$", "url_decode", {"text": 1}),
    # 哈希显式命令
    (r"^(md5|sha1|sha256|sha512)\s+(.+)$", "calculate_hash", {"algorithm": 1, "text": 2}),
    # DNS 显式命令
    (r"^dns\s+([a-zA-Z0-9][-a-zA-Z0-9.]+)$", "dns_lookup", {"target": 1}),
    # WHOIS 显式命令
    (r"^whois\s+([a-zA-Z0-9][-a-zA-Z0-9.]+)$", "whois_lookup", {"target": 1}),
]


def try_rule_match(user_input: str) -> Optional[ParsedIntent]:
    """
    极简规则匹配 - 只处理显式命令（0 token 消耗）
    
    设计原则：
    - 只匹配"显式命令"格式，如 "base64编码 xxx"、"md5 xxx"
    - 自然语言表达（如"帮我把xxx转成base64"）交给 Intent LLM
    - 规则匹配是性能优化，不是必需品
    
    Returns:
        ParsedIntent 如果匹配成功，否则 None（交给 LLM）
    """
    text = user_input.strip()
    
    # 只匹配显式命令
    for pattern, tool, param_map in EXPLICIT_COMMAND_PATTERNS:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            # 构建参数
            params = {}
            for param_name, group_index in param_map.items():
                value = match.group(group_index).strip()
                if param_name == "algorithm":
                    value = value.lower()
                params[param_name] = value
            
            # 确定分类
            category = TOOL_CATEGORY_MAP.get(tool, IntentCategory.CHAT)
            
            logger.info(f"[Intent] 显式命令匹配: {tool}, params={params}")
            return ParsedIntent(
                category=category,
                tool=tool,
                params=params,
                confidence=0.99,  # 显式命令，高置信度
                raw_input=user_input,
            )
    
    # 其他所有情况交给 Intent LLM（更智能的处理）
    return None


def parse_llm_intent_response(response: str, user_input: str) -> ParsedIntent:
    """
    解析 Intent LLM 的响应
    
    Args:
        response: LLM 返回的 JSON 字符串
        user_input: 原始用户输入
        
    Returns:
        ParsedIntent 对象
    """
    try:
        # 尝试直接解析（LLM 通常直接返回 JSON）
        response_clean = response.strip()
        
        # 找到最外层的 JSON 对象
        start_idx = response_clean.find('{')
        if start_idx == -1:
            raise ValueError("未找到 JSON 对象")
        
        # 找到匹配的结束括号（处理嵌套）
        depth = 0
        end_idx = start_idx
        for i, char in enumerate(response_clean[start_idx:], start_idx):
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        
        json_str = response_clean[start_idx:end_idx + 1]
        data = json.loads(json_str)
        
        # 验证并构建 Intent
        category = data.get("category", "chat")
        if category not in [e.value for e in IntentCategory]:
            logger.warning(f"未知 category: {category}, 使用 chat")
            category = "chat"
        
        logger.debug(f"解析成功: category={category}, tool={data.get('tool')}, params={data.get('params')}")
        
        return ParsedIntent(
            category=IntentCategory(category),
            tool=data.get("tool"),
            params=data.get("params", {}),
            confidence=float(data.get("confidence", 0.8)),
            raw_input=user_input,
        )
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"解析 Intent 响应失败: {e}, response={response[:200]}")
    
    # 解析失败，fallback 到聊天
    return ParsedIntent(
        category=IntentCategory.CHAT,
        tool=None,
        params={},
        confidence=0.5,
        raw_input=user_input,
    )


# ==================== 工具名称映射 ====================

TOOL_CATEGORY_MAP = {
    # 编码
    "base64_encode": IntentCategory.ENCODE,
    "url_encode": IntentCategory.ENCODE,
    "html_encode": IntentCategory.ENCODE,
    "hex_encode": IntentCategory.ENCODE,
    "unicode_encode": IntentCategory.ENCODE,
    "rot13": IntentCategory.ENCODE,
    # 解码
    "base64_decode": IntentCategory.DECODE,
    "url_decode": IntentCategory.DECODE,
    "html_decode": IntentCategory.DECODE,
    "hex_decode": IntentCategory.DECODE,
    "unicode_decode": IntentCategory.DECODE,
    # 哈希
    "calculate_hash": IntentCategory.HASH,
    "calculate_all_hashes": IntentCategory.HASH,
    "calculate_hmac": IntentCategory.HASH,
    "compare_hash": IntentCategory.HASH,
    # 网络
    "dns_lookup": IntentCategory.NETWORK,
    "whois_lookup": IntentCategory.NETWORK,
    "ip_info": IntentCategory.NETWORK,
    "reverse_dns": IntentCategory.NETWORK,
    "analyze_target": IntentCategory.NETWORK,
    # 搜索
    "web_search": IntentCategory.SEARCH,
    "news_search": IntentCategory.SEARCH,
    "weather": IntentCategory.SEARCH,
    # 浏览器
    "browser_goto": IntentCategory.BROWSER,
    "browser_screenshot": IntentCategory.BROWSER,
    "browser_get_content": IntentCategory.BROWSER,
    "browser_execute_js": IntentCategory.BROWSER,
    # 股票/基金分析
    "search_stock": IntentCategory.FINANCE,
    "get_stock_quote": IntentCategory.FINANCE,
    "get_stock_finance": IntentCategory.FINANCE,
    "get_stock_news": IntentCategory.FINANCE,
    "get_technical_indicators": IntentCategory.FINANCE,
    "analyze_stock": IntentCategory.FINANCE,
}


def get_tool_display_name(tool_name: str) -> str:
    """获取工具的显示名称"""
    TOOL_NAMES = {
        "base64_encode": "Base64 编码",
        "base64_decode": "Base64 解码",
        "url_encode": "URL 编码",
        "url_decode": "URL 解码",
        "html_encode": "HTML 编码",
        "html_decode": "HTML 解码",
        "hex_encode": "Hex 编码",
        "hex_decode": "Hex 解码",
        "unicode_encode": "Unicode 编码",
        "unicode_decode": "Unicode 解码",
        "rot13": "ROT13",
        "calculate_hash": "哈希计算",
        "calculate_all_hashes": "全部哈希",
        "calculate_hmac": "HMAC 计算",
        "dns_lookup": "DNS 查询",
        "whois_lookup": "WHOIS 查询",
        "ip_info": "IP 信息查询",
        "reverse_dns": "反向 DNS",
        # 搜索
        "web_search": "网络搜索",
        "news_search": "新闻搜索",
        "weather": "天气查询",
        # 浏览器
        "browser_goto": "访问网页",
        "browser_screenshot": "网页截图",
        "browser_get_content": "获取网页内容",
        "browser_execute_js": "执行 JavaScript",
        # 股票/基金分析
        "search_stock": "搜索股票",
        "get_stock_quote": "股票行情",
        "get_stock_finance": "财务数据",
        "get_stock_news": "股票新闻",
        "get_technical_indicators": "技术指标",
        "analyze_stock": "综合分析",
    }
    return TOOL_NAMES.get(tool_name, tool_name)
