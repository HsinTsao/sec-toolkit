"""
编码模块单元测试
"""

import pytest
from app.modules.encoding import (
    base64_encode,
    base64_decode,
    url_encode,
    url_decode,
    hex_encode,
    hex_decode,
    html_encode,
    html_decode,
)


class TestBase64:
    """Base64 编解码测试"""
    
    def test_encode_basic(self):
        """测试基本编码"""
        result = base64_encode("hello")
        assert result == "aGVsbG8="
    
    def test_decode_basic(self):
        """测试基本解码"""
        result = base64_decode("aGVsbG8=")
        assert result == "hello"
    
    def test_encode_chinese(self):
        """测试中文编码"""
        result = base64_encode("你好")
        assert result == "5L2g5aW9"
    
    def test_decode_chinese(self):
        """测试中文解码"""
        result = base64_decode("5L2g5aW9")
        assert result == "你好"
    
    def test_encode_empty(self):
        """测试空字符串"""
        result = base64_encode("")
        assert result == ""
    
    def test_decode_empty(self):
        """测试空字符串解码"""
        result = base64_decode("")
        assert result == ""
    
    def test_roundtrip(self):
        """测试编解码往返"""
        original = "Hello, World! 你好世界 123"
        encoded = base64_encode(original)
        decoded = base64_decode(encoded)
        assert decoded == original


class TestUrlEncoding:
    """URL 编解码测试"""
    
    def test_encode_basic(self):
        """测试基本编码"""
        result = url_encode("hello world")
        assert result == "hello%20world"
    
    def test_decode_basic(self):
        """测试基本解码"""
        result = url_decode("hello%20world")
        assert result == "hello world"
    
    def test_encode_special_chars(self):
        """测试特殊字符编码"""
        result = url_encode("a=1&b=2")
        assert "%26" in result or "&" in result  # 取决于实现
    
    def test_encode_chinese(self):
        """测试中文编码"""
        result = url_encode("你好")
        assert "%" in result  # 中文会被编码
    
    def test_roundtrip(self):
        """测试编解码往返"""
        original = "test=value&name=测试"
        encoded = url_encode(original)
        decoded = url_decode(encoded)
        assert decoded == original


class TestHexEncoding:
    """十六进制编解码测试"""
    
    def test_encode_basic(self):
        """测试基本编码"""
        result = hex_encode("ABC")
        assert result.lower() == "414243"
    
    def test_decode_basic(self):
        """测试基本解码"""
        result = hex_decode("414243")
        assert result == "ABC"
    
    def test_encode_empty(self):
        """测试空字符串"""
        result = hex_encode("")
        assert result == ""
    
    def test_roundtrip(self):
        """测试编解码往返"""
        original = "Hello123"
        encoded = hex_encode(original)
        decoded = hex_decode(encoded)
        assert decoded == original


class TestHtmlEncoding:
    """HTML 编解码测试"""
    
    def test_encode_basic(self):
        """测试基本编码"""
        result = html_encode("<script>alert(1)</script>")
        assert "<" not in result
        assert ">" not in result
        assert "&lt;" in result
        assert "&gt;" in result
    
    def test_decode_basic(self):
        """测试基本解码"""
        result = html_decode("&lt;div&gt;")
        assert result == "<div>"
    
    def test_encode_quotes(self):
        """测试引号编码"""
        result = html_encode('"test"')
        assert "&quot;" in result or '"' not in result
    
    def test_roundtrip(self):
        """测试编解码往返"""
        original = '<a href="test">Link</a>'
        encoded = html_encode(original)
        decoded = html_decode(encoded)
        assert decoded == original
