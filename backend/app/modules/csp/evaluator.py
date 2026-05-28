"""CSP 安全评估引擎

基于 Google CSP Evaluator 的评估逻辑，检查 CSP 策略中的安全问题。
参考: https://csp-evaluator.withgoogle.com/
"""
from typing import Dict, List, Optional
from .parser import parse_csp

# ==================== 严重级别 ====================
HIGH = "high"
MEDIUM = "medium"
LOW = "low"
INFO = "info"

# ==================== 已知 CSP 绕过域名 ====================
# 参考 https://github.com/nickmatt/csp-bypass-list
JSONP_BYPASS_DOMAINS = [
    "accounts.google.com",
    "ajax.googleapis.com",
    "api.google.com",
    "clients1.google.com",
    "translate.googleapis.com",
    "maps.googleapis.com",
    "www.google.com",
    "www.googleapis.com",
    "clients6.google.com",
    "www.google-analytics.com",
    "ssl.google-analytics.com",
    "api.twitter.com",
    "cdn.syndication.twimg.com",
    "graph.facebook.com",
    "connect.facebook.net",
    "staticxx.facebook.com",
    "api.mapbox.com",
    "api.tiles.mapbox.com",
    "mc.yandex.ru",
    "api-metrika.yandex.ru",
    "suggest.yandex.ru",
    "yandex.ru",
    "an.yandex.ru",
    "api.vk.com",
    "platform.linkedin.com",
    "pagead2.googlesyndication.com",
    "tpc.googlesyndication.com",
    "partner.googleadservices.com",
    "www.googleadservices.com",
    "fast.wistia.com",
    "gist.github.com",
    "cdn.rawgit.com",
    "raw.githubusercontent.com",
]

ANGULARJS_BYPASS_DOMAINS = [
    "cdnjs.cloudflare.com",
    "cdn.jsdelivr.net",
    "ajax.googleapis.com",
    "unpkg.com",
    "cdn.bootcss.com",
    "cdn.bootcdn.net",
    "lib.baomitu.com",
    "code.jquery.com",
]

# 所有可能被用于 XSS 绕过的域名
BYPASS_DOMAINS = set(JSONP_BYPASS_DOMAINS + ANGULARJS_BYPASS_DOMAINS)

# 需要重点关注的 script 相关指令
SCRIPT_DIRECTIVES = {"script-src", "script-src-elem", "script-src-attr", "default-src"}
STYLE_DIRECTIVES = {"style-src", "style-src-elem", "style-src-attr", "default-src"}

# CSP 所有已知指令
KNOWN_DIRECTIVES = {
    "default-src", "script-src", "style-src", "img-src", "connect-src",
    "font-src", "object-src", "media-src", "frame-src", "child-src",
    "worker-src", "manifest-src", "prefetch-src", "navigate-to",
    "base-uri", "form-action", "frame-ancestors", "plugin-types",
    "report-uri", "report-to", "require-sri-for", "require-trusted-types-for",
    "trusted-types", "upgrade-insecure-requests", "block-all-mixed-content",
    "sandbox", "script-src-elem", "script-src-attr", "style-src-elem",
    "style-src-attr",
}


def evaluate_csp(raw_csp: str, csp_version: int = 3) -> dict:
    """
    评估 CSP 策略的安全性。

    Args:
        raw_csp: 原始 CSP 字符串
        csp_version: 目标 CSP 版本 (1, 2, 3)

    Returns:
        {
            "raw": "原始 CSP",
            "directives": {解析后的指令字典},
            "findings": [
                {
                    "directive": "script-src",
                    "severity": "high",
                    "description": "...",
                    "value": "'unsafe-inline'"
                },
                ...
            ],
            "summary": {
                "high": 2,
                "medium": 1,
                "low": 0,
                "info": 1,
                "score": 35,
                "rating": "C"
            }
        }
    """
    directives = parse_csp(raw_csp)
    findings: List[dict] = []

    if not directives:
        findings.append(_f(None, HIGH, "未检测到 CSP 策略", "网站没有设置 Content-Security-Policy，无法防御 XSS 等攻击"))
        return _build_result(raw_csp, directives, findings)

    # === 核心检查 ===
    _check_missing_directives(directives, findings)
    _check_unsafe_inline(directives, findings, csp_version)
    _check_unsafe_eval(directives, findings)
    _check_wildcard(directives, findings)
    _check_data_uri(directives, findings)
    _check_blob_uri(directives, findings)
    _check_http_scheme(directives, findings)
    _check_bypass_domains(directives, findings)
    _check_base_uri(directives, findings)
    _check_object_src(directives, findings)
    _check_form_action(directives, findings)
    _check_frame_ancestors(directives, findings)
    _check_nonce_and_hash(directives, findings, csp_version)
    _check_strict_dynamic(directives, findings, csp_version)
    _check_reporting(directives, findings)
    _check_unknown_directives(directives, findings)
    _check_ip_source(directives, findings)
    _check_deprecated(directives, findings)

    return _build_result(raw_csp, directives, findings)


def _f(directive: Optional[str], severity: str, title: str, description: str, value: str = "") -> dict:
    return {
        "directive": directive,
        "severity": severity,
        "title": title,
        "description": description,
        "value": value,
    }


def _build_result(raw: str, directives: dict, findings: list) -> dict:
    counts = {HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    score = _calculate_score(counts, directives)
    rating = _score_to_rating(score)

    return {
        "raw": raw,
        "directives": directives,
        "findings": findings,
        "summary": {
            **counts,
            "score": score,
            "rating": rating,
        },
    }


def _calculate_score(counts: dict, directives: dict) -> int:
    """0~100 分，100 最安全"""
    if not directives:
        return 0
    score = 100
    score -= counts[HIGH] * 20
    score -= counts[MEDIUM] * 10
    score -= counts[LOW] * 5
    return max(0, min(100, score))


def _score_to_rating(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 50:
        return "C"
    if score >= 25:
        return "D"
    return "F"


def _get_effective_values(directives: dict, directive: str) -> List[str]:
    """获取指令的有效值，考虑 default-src 回退"""
    if directive in directives:
        return directives[directive]
    if "default-src" in directives:
        return directives["default-src"]
    return []


# ==================== 各项检查规则 ====================

def _check_missing_directives(directives: dict, findings: list):
    """检查关键指令是否缺失"""
    if "default-src" not in directives:
        findings.append(_f(
            "default-src", MEDIUM,
            "缺少 default-src 指令",
            "default-src 是其他未明确指定的指令的回退策略。缺少它意味着未覆盖的资源类型没有限制。"
        ))

    if "script-src" not in directives and "default-src" not in directives:
        findings.append(_f(
            "script-src", HIGH,
            "缺少 script-src 指令",
            "没有 script-src 也没有 default-src，浏览器将允许加载任意来源的脚本。"
        ))


def _check_unsafe_inline(directives: dict, findings: list, csp_version: int):
    """检查 'unsafe-inline'"""
    for d in ["script-src", "script-src-elem", "script-src-attr", "default-src"]:
        values = directives.get(d, [])
        if "'unsafe-inline'" in values:
            has_nonce = any(v.startswith("'nonce-") for v in values)
            has_hash = any(v.startswith("'sha256-") or v.startswith("'sha384-") or v.startswith("'sha512-") for v in values)

            if csp_version >= 2 and (has_nonce or has_hash):
                findings.append(_f(
                    d, INFO,
                    f"'{d}' 包含 'unsafe-inline'（被 nonce/hash 覆盖）",
                    f"在 CSP Level 2+ 中，如果同时设置了 nonce 或 hash，'unsafe-inline' 会被自动忽略，这里保留是为了向下兼容。",
                    "'unsafe-inline'"
                ))
            else:
                findings.append(_f(
                    d, HIGH,
                    f"'{d}' 允许 'unsafe-inline'",
                    "'unsafe-inline' 允许执行内联脚本，攻击者可以通过 XSS 注入内联代码执行。这是 CSP 最常见的绕过方式。",
                    "'unsafe-inline'"
                ))

    for d in ["style-src", "style-src-elem", "style-src-attr", "default-src"]:
        values = directives.get(d, [])
        if "'unsafe-inline'" in values and d not in ["default-src"]:
            findings.append(_f(
                d, LOW,
                f"'{d}' 允许内联样式",
                "'unsafe-inline' 在样式指令中风险较低，但仍可能被利用进行 CSS 注入攻击（如数据窃取）。",
                "'unsafe-inline'"
            ))


def _check_unsafe_eval(directives: dict, findings: list):
    """检查 'unsafe-eval'"""
    for d in ["script-src", "script-src-elem", "default-src"]:
        values = directives.get(d, [])
        if "'unsafe-eval'" in values:
            findings.append(_f(
                d, MEDIUM,
                f"'{d}' 允许 'unsafe-eval'",
                "'unsafe-eval' 允许使用 eval()、Function()、setTimeout(string) 等动态代码执行方法，增加了 XSS 利用面。",
                "'unsafe-eval'"
            ))


def _check_wildcard(directives: dict, findings: list):
    """检查通配符"""
    for d, values in directives.items():
        if d in ("report-uri", "report-to", "sandbox", "upgrade-insecure-requests",
                 "block-all-mixed-content", "require-trusted-types-for", "trusted-types"):
            continue
        if "*" in values:
            severity = HIGH if d in SCRIPT_DIRECTIVES else MEDIUM
            findings.append(_f(
                d, severity,
                f"'{d}' 使用了通配符 *",
                "通配符 '*' 允许从任何来源加载资源，这基本上等于没有 CSP 限制。",
                "*"
            ))
        for v in values:
            if v.startswith("*.") and v != "*":
                severity = MEDIUM if d in SCRIPT_DIRECTIVES else LOW
                findings.append(_f(
                    d, severity,
                    f"'{d}' 使用了过于宽泛的通配符域名",
                    f"'{v}' 允许该域名的所有子域，如果任何子域存在安全问题（如 JSONP 端点、文件上传），可能被利用绕过 CSP。",
                    v
                ))


def _check_data_uri(directives: dict, findings: list):
    """检查 data: URI"""
    for d in ["script-src", "script-src-elem", "default-src"]:
        values = directives.get(d, [])
        if "data:" in values:
            findings.append(_f(
                d, HIGH,
                f"'{d}' 允许 data: URI",
                "data: URI 允许通过 <script src='data:text/javascript,...'> 注入并执行任意 JavaScript 代码。",
                "data:"
            ))

    for d in ["img-src", "media-src", "font-src"]:
        values = _get_effective_values(directives, d)
        if "data:" in values:
            findings.append(_f(
                d, LOW,
                f"'{d}' 允许 data: URI",
                "data: URI 在此指令中风险较低，但可能被用于 CSP 数据泄露（如通过 CSS 选择器配合 background-image 窃取数据）。",
                "data:"
            ))


def _check_blob_uri(directives: dict, findings: list):
    """检查 blob: URI"""
    for d in ["script-src", "script-src-elem", "default-src", "worker-src"]:
        values = directives.get(d, [])
        if "blob:" in values:
            findings.append(_f(
                d, MEDIUM,
                f"'{d}' 允许 blob: URI",
                "blob: URI 可以创建动态内容，在某些场景下可被用于绕过 CSP 限制执行脚本。",
                "blob:"
            ))


def _check_http_scheme(directives: dict, findings: list):
    """检查是否允许 HTTP 明文"""
    for d, values in directives.items():
        if d in ("report-uri", "report-to", "sandbox", "upgrade-insecure-requests",
                 "block-all-mixed-content"):
            continue
        if "http:" in values:
            severity = MEDIUM if d in SCRIPT_DIRECTIVES else LOW
            findings.append(_f(
                d, severity,
                f"'{d}' 允许 HTTP 明文协议",
                "允许通过 http: 加载资源，可能遭受中间人攻击（MITM）注入恶意内容。建议使用 https: 或移除协议限定。",
                "http:"
            ))
        for v in values:
            if v.startswith("http://"):
                severity = MEDIUM if d in SCRIPT_DIRECTIVES else LOW
                findings.append(_f(
                    d, severity,
                    f"'{d}' 中包含 HTTP 明文源",
                    f"'{v}' 使用了 HTTP 明文协议，可能遭受中间人攻击。",
                    v
                ))


def _check_bypass_domains(directives: dict, findings: list):
    """检查已知的 CSP 绕过域名"""
    for d in ["script-src", "script-src-elem", "default-src"]:
        values = directives.get(d, [])
        for v in values:
            domain = _extract_domain(v)
            if not domain:
                continue
            if domain in JSONP_BYPASS_DOMAINS:
                findings.append(_f(
                    d, HIGH,
                    f"'{d}' 白名单中包含已知 JSONP 绕过域名",
                    f"'{domain}' 提供 JSONP 端点，攻击者可以利用它执行任意 JavaScript。"
                    f"例如: <script src='//{domain}/path?callback=alert(1)'></script>",
                    v
                ))
            elif domain in ANGULARJS_BYPASS_DOMAINS:
                findings.append(_f(
                    d, HIGH,
                    f"'{d}' 白名单中包含可托管任意 JS 的 CDN",
                    f"'{domain}' 是公共 CDN，攻击者可以通过该 CDN 加载 AngularJS 等库来绕过 CSP。"
                    f"例如：加载 AngularJS 后利用模板注入执行代码。",
                    v
                ))


def _check_base_uri(directives: dict, findings: list):
    """检查 base-uri 是否受限"""
    if "base-uri" not in directives:
        findings.append(_f(
            "base-uri", MEDIUM,
            "缺少 base-uri 指令",
            "未设置 base-uri 限制，攻击者可以通过注入 <base> 标签改变页面中所有相对 URL 的基准地址，"
            "从而劫持脚本加载路径。建议设置 base-uri 'self' 或 'none'。"
        ))
    else:
        values = directives["base-uri"]
        if "*" in values or not values:
            findings.append(_f(
                "base-uri", MEDIUM,
                "base-uri 设置过于宽松",
                "base-uri 的值允许任意来源，无法有效防止 <base> 标签注入攻击。",
                " ".join(values)
            ))


def _check_object_src(directives: dict, findings: list):
    """检查 object-src 是否受限"""
    values = _get_effective_values(directives, "object-src")
    if "object-src" not in directives and "default-src" not in directives:
        findings.append(_f(
            "object-src", MEDIUM,
            "缺少 object-src 指令",
            "未限制 <object>/<embed>/<applet> 标签的来源，攻击者可能利用这些标签执行恶意插件代码。"
            "建议设置 object-src 'none'。"
        ))
    elif values and "'none'" not in values and "'self'" not in values:
        has_risky = "*" in values or any(v.startswith("http") for v in values)
        if has_risky:
            findings.append(_f(
                "object-src", MEDIUM,
                "object-src 设置过于宽松",
                "允许从外部来源加载插件对象，建议设置为 'none' 禁用。",
                " ".join(values)
            ))


def _check_form_action(directives: dict, findings: list):
    """检查 form-action"""
    if "form-action" not in directives:
        findings.append(_f(
            "form-action", LOW,
            "缺少 form-action 指令",
            "未限制表单提交的目标地址，攻击者可能通过注入表单将用户数据提交到恶意服务器。"
            "注意: form-action 不受 default-src 回退。"
        ))


def _check_frame_ancestors(directives: dict, findings: list):
    """检查 frame-ancestors（防点击劫持）"""
    if "frame-ancestors" not in directives:
        findings.append(_f(
            "frame-ancestors", LOW,
            "缺少 frame-ancestors 指令",
            "未设置 frame-ancestors，页面可能被嵌入到恶意网站的 iframe 中实施点击劫持攻击。"
            "建议设置 frame-ancestors 'self' 或 'none'。注意: X-Frame-Options 头也可以提供类似保护。"
        ))


def _check_nonce_and_hash(directives: dict, findings: list, csp_version: int):
    """检查 nonce / hash 使用情况"""
    if csp_version < 2:
        return

    for d in ["script-src", "script-src-elem", "default-src"]:
        values = directives.get(d, [])
        for v in values:
            if v.startswith("'nonce-"):
                nonce_val = v[7:-1] if v.endswith("'") else v[7:]
                if len(nonce_val) < 8:
                    findings.append(_f(
                        d, HIGH,
                        f"Nonce 值过短",
                        f"Nonce '{v}' 长度不足，容易被猜测。建议使用至少 128 位（16 字节）的随机值。",
                        v
                    ))
                if nonce_val in ("test", "debug", "example", "abc123", "123456"):
                    findings.append(_f(
                        d, HIGH,
                        f"Nonce 使用了固定/可预测的值",
                        f"Nonce 必须每次请求都随机生成，使用固定值等于没有 nonce 保护。",
                        v
                    ))


def _check_strict_dynamic(directives: dict, findings: list, csp_version: int):
    """检查 'strict-dynamic' 使用"""
    if csp_version < 3:
        return

    for d in ["script-src", "default-src"]:
        values = directives.get(d, [])
        if "'strict-dynamic'" in values:
            has_nonce = any(v.startswith("'nonce-") for v in values)
            has_hash = any(v.startswith(("'sha256-", "'sha384-", "'sha512-")) for v in values)
            if not has_nonce and not has_hash:
                findings.append(_f(
                    d, HIGH,
                    f"'strict-dynamic' 没有配合 nonce/hash 使用",
                    "'strict-dynamic' 需要与 nonce 或 hash 一起使用才有意义。"
                    "它会忽略白名单域名，仅信任通过 nonce/hash 加载的脚本及其动态创建的子脚本。",
                    "'strict-dynamic'"
                ))
            else:
                findings.append(_f(
                    d, INFO,
                    f"使用了 'strict-dynamic'（推荐方式）",
                    "'strict-dynamic' 配合 nonce/hash 是 CSP Level 3 推荐的最佳实践，"
                    "可以在保持安全性的同时支持动态脚本加载。",
                    "'strict-dynamic'"
                ))
            # strict-dynamic 下白名单域名和 'self' 会被忽略
            has_whitelist = any(not v.startswith("'") and v not in ("data:", "blob:", "http:", "https:", "*") for v in values)
            if has_whitelist:
                findings.append(_f(
                    d, INFO,
                    "strict-dynamic 模式下白名单域名被忽略",
                    "在启用 'strict-dynamic' 时，显式的域名白名单会被浏览器忽略。"
                    "保留它们是为了向下兼容不支持 CSP3 的浏览器。",
                ))


def _check_reporting(directives: dict, findings: list):
    """检查是否配置了违规上报"""
    has_report = "report-uri" in directives or "report-to" in directives
    if not has_report:
        findings.append(_f(
            "report-uri", INFO,
            "未配置 CSP 违规上报",
            "建议配置 report-uri 或 report-to 指令，以便收集 CSP 违规报告，及时发现潜在攻击或策略问题。"
        ))


def _check_unknown_directives(directives: dict, findings: list):
    """检查未知/拼写错误的指令"""
    for d in directives:
        if d not in KNOWN_DIRECTIVES:
            findings.append(_f(
                d, LOW,
                f"未知的指令 '{d}'",
                f"'{d}' 不是标准 CSP 指令，可能是拼写错误。浏览器会忽略未知指令。"
            ))


def _check_ip_source(directives: dict, findings: list):
    """检查是否有 IP 地址作为源"""
    import re
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')

    for d, values in directives.items():
        if d in ("report-uri", "report-to"):
            continue
        for v in values:
            clean = v.replace("http://", "").replace("https://", "").split(":")[0]
            if ip_pattern.match(clean):
                findings.append(_f(
                    d, LOW,
                    f"'{d}' 中使用了 IP 地址",
                    f"使用 IP 地址 '{v}' 作为源不如域名可读且不够灵活。如果 IP 对应服务器被控制，可能导致安全问题。",
                    v
                ))


def _check_deprecated(directives: dict, findings: list):
    """检查已废弃的指令"""
    deprecated = {
        "plugin-types": "plugin-types 已在 CSP Level 3 中废弃，现代浏览器不再支持。请使用 object-src 'none' 代替。",
        "referrer": "referrer 指令已废弃，请改用 Referrer-Policy HTTP 头。",
        "prefetch-src": "prefetch-src 从未被浏览器广泛支持，已从规范中移除。",
    }
    for d, msg in deprecated.items():
        if d in directives:
            findings.append(_f(d, LOW, f"使用了已废弃的指令 '{d}'", msg))

    if "block-all-mixed-content" in directives:
        findings.append(_f(
            "block-all-mixed-content", INFO,
            "block-all-mixed-content 已被 upgrade-insecure-requests 取代",
            "建议改用 upgrade-insecure-requests，它可以自动将 HTTP 请求升级为 HTTPS，而不是直接阻断。"
        ))


def _extract_domain(value: str) -> Optional[str]:
    """从 CSP 源值中提取纯域名"""
    v = value.lower().strip()
    if v.startswith(("'", "data:", "blob:", "http:", "https:", "mediastream:", "filesystem:")):
        # 提取 http(s)://domain 的情况
        if v.startswith(("http://", "https://")):
            v = v.split("://", 1)[1]
        else:
            return None
    v = v.split("/")[0]  # 去掉路径
    v = v.split(":")[0]  # 去掉端口
    v = v.lstrip("*.")   # 去掉通配符前缀
    return v if v else None
