"""编码/解码工具模块"""
import base64
import urllib.parse
import html
import codecs
import binascii


def base64_encode(text: str) -> str:
    """Base64 编码"""
    try:
        return base64.b64encode(text.encode('utf-8')).decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def base64_decode(text: str) -> str:
    """Base64 解码"""
    try:
        # 处理 URL 安全的 Base64
        text = text.replace('-', '+').replace('_', '/')
        # 补全 padding
        padding = 4 - len(text) % 4
        if padding != 4:
            text += '=' * padding
        return base64.b64decode(text).decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def url_encode(text: str) -> str:
    """URL 编码"""
    try:
        return urllib.parse.quote(text, safe='')
    except Exception as e:
        return f"错误: {str(e)}"


def url_decode(text: str) -> str:
    """URL 解码"""
    try:
        return urllib.parse.unquote(text)
    except Exception as e:
        return f"错误: {str(e)}"


def html_encode(text: str) -> str:
    """HTML 实体编码"""
    try:
        return html.escape(text)
    except Exception as e:
        return f"错误: {str(e)}"


def html_decode(text: str) -> str:
    """HTML 实体解码"""
    try:
        return html.unescape(text)
    except Exception as e:
        return f"错误: {str(e)}"


def hex_encode(text: str) -> str:
    """Hex 编码"""
    try:
        return text.encode('utf-8').hex()
    except Exception as e:
        return f"错误: {str(e)}"


def hex_decode(text: str) -> str:
    """Hex 解码"""
    try:
        # 移除可能的空格和 0x 前缀
        text = text.replace(' ', '').replace('0x', '').replace('\\x', '')
        return bytes.fromhex(text).decode('utf-8')
    except Exception as e:
        return f"错误: {str(e)}"


def unicode_encode(text: str) -> str:
    """Unicode 编码 (\\uXXXX 格式)"""
    try:
        return ''.join(f'\\u{ord(c):04x}' for c in text)
    except Exception as e:
        return f"错误: {str(e)}"


def unicode_decode(text: str) -> str:
    """Unicode 解码"""
    try:
        return codecs.decode(text, 'unicode_escape')
    except Exception as e:
        return f"错误: {str(e)}"


def ascii_to_binary(text: str) -> str:
    """ASCII 转二进制"""
    try:
        return ' '.join(format(ord(c), '08b') for c in text)
    except Exception as e:
        return f"错误: {str(e)}"


def binary_to_ascii(text: str) -> str:
    """二进制转 ASCII"""
    try:
        binary_values = text.split()
        return ''.join(chr(int(b, 2)) for b in binary_values)
    except Exception as e:
        return f"错误: {str(e)}"


def rot13(text: str) -> str:
    """ROT13 编码/解码"""
    try:
        return codecs.encode(text, 'rot_13')
    except Exception as e:
        return f"错误: {str(e)}"


def morse_encode(text: str) -> str:
    """摩尔斯电码编码"""
    MORSE_CODE = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
        'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
        'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
        'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
        'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---',
        '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...',
        '8': '---..', '9': '----.', ' ': '/', '.': '.-.-.-', ',': '--..--',
        '?': '..--..', "'": '.----.', '!': '-.-.--', '/': '-..-.', '(': '-.--.',
        ')': '-.--.-', '&': '.-...', ':': '---...', ';': '-.-.-.', '=': '-...-',
        '+': '.-.-.', '-': '-....-', '_': '..--.-', '"': '.-..-.', '$': '...-..-',
        '@': '.--.-.'
    }
    try:
        return ' '.join(MORSE_CODE.get(c.upper(), c) for c in text)
    except Exception as e:
        return f"错误: {str(e)}"


def morse_decode(text: str) -> str:
    """摩尔斯电码解码"""
    MORSE_CODE_REVERSED = {
        '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E', '..-.': 'F',
        '--.': 'G', '....': 'H', '..': 'I', '.---': 'J', '-.-': 'K', '.-..': 'L',
        '--': 'M', '-.': 'N', '---': 'O', '.--.': 'P', '--.-': 'Q', '.-.': 'R',
        '...': 'S', '-': 'T', '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X',
        '-.--': 'Y', '--..': 'Z', '-----': '0', '.----': '1', '..---': '2',
        '...--': '3', '....-': '4', '.....': '5', '-....': '6', '--...': '7',
        '---..': '8', '----.': '9', '/': ' ', '.-.-.-': '.', '--..--': ',',
        '..--..': '?', '.----.': "'", '-.-.--': '!', '-..-.': '/', '-.--.': '(',
        '-.--.-': ')', '.-...': '&', '---...': ':', '-.-.-.': ';', '-...-': '=',
        '.-.-.': '+', '-....-': '-', '..--.-': '_', '.-..-.': '"', '...-..-': '$',
        '.--.-.': '@'
    }
    try:
        return ''.join(MORSE_CODE_REVERSED.get(code, code) for code in text.split())
    except Exception as e:
        return f"错误: {str(e)}"

