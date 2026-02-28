"""
哈希模块单元测试
"""

import pytest
from app.modules.hash_tools import (
    calculate_hash,
    calculate_all_hashes,
    calculate_hmac,
    compare_hash,
)


class TestCalculateHash:
    """calculate_hash 函数测试"""
    
    def test_md5_basic(self):
        """测试 MD5 哈希"""
        result = calculate_hash("hello", "md5")
        assert result == "5d41402abc4b2a76b9719d911017c592"
    
    def test_sha1_basic(self):
        """测试 SHA1 哈希"""
        result = calculate_hash("hello", "sha1")
        assert result == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
    
    def test_sha256_basic(self):
        """测试 SHA256 哈希"""
        result = calculate_hash("hello", "sha256")
        assert result == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    
    def test_sha512_basic(self):
        """测试 SHA512 哈希"""
        result = calculate_hash("hello", "sha512")
        assert result.startswith("9b71d224bd62f3785d96d46ad3ea3d73")
    
    def test_empty_string(self):
        """测试空字符串"""
        result = calculate_hash("", "md5")
        assert result == "d41d8cd98f00b204e9800998ecf8427e"
    
    def test_chinese(self):
        """测试中文"""
        result = calculate_hash("你好", "md5")
        assert len(result) == 32  # MD5 长度固定为 32 位
    
    def test_case_insensitive_algorithm(self):
        """测试算法名称不区分大小写"""
        result1 = calculate_hash("test", "MD5")
        result2 = calculate_hash("test", "md5")
        assert result1 == result2
    
    def test_unsupported_algorithm(self):
        """测试不支持的算法"""
        result = calculate_hash("test", "unknown")
        assert "错误" in result


class TestCalculateAllHashes:
    """calculate_all_hashes 函数测试"""
    
    def test_returns_all_algorithms(self):
        """测试返回所有算法"""
        result = calculate_all_hashes("test")
        
        assert "md5" in result
        assert "sha1" in result
        assert "sha256" in result
        assert "sha512" in result
    
    def test_values_are_correct(self):
        """测试值正确性"""
        result = calculate_all_hashes("hello")
        
        assert result["md5"] == "5d41402abc4b2a76b9719d911017c592"
        assert result["sha1"] == "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"


class TestCalculateHmac:
    """calculate_hmac 函数测试"""
    
    def test_basic(self):
        """测试基本 HMAC"""
        result = calculate_hmac("hello", "secret", "sha256")
        assert len(result) == 64  # SHA256 HMAC 长度
    
    def test_different_keys(self):
        """测试不同密钥产生不同结果"""
        result1 = calculate_hmac("hello", "key1", "sha256")
        result2 = calculate_hmac("hello", "key2", "sha256")
        assert result1 != result2
    
    def test_unsupported_algorithm(self):
        """测试不支持的算法"""
        result = calculate_hmac("hello", "key", "unknown")
        assert "错误" in result


class TestCompareHash:
    """compare_hash 函数测试"""
    
    def test_match(self):
        """测试匹配"""
        expected = "5d41402abc4b2a76b9719d911017c592"  # MD5 of "hello"
        result = compare_hash("hello", expected)
        
        assert result["match"] is True
        assert result["algorithm"] == "md5"
    
    def test_no_match(self):
        """测试不匹配"""
        result = compare_hash("hello", "wronghash123456789012345678901234")
        assert result["match"] is False
    
    def test_auto_detect_sha256(self):
        """测试自动检测 SHA256"""
        expected = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        result = compare_hash("hello", expected)
        
        assert result["match"] is True
        assert result["algorithm"] == "sha256"
    
    def test_case_insensitive_comparison(self):
        """测试大小写不敏感比较"""
        expected = "5D41402ABC4B2A76B9719D911017C592"  # 大写
        result = compare_hash("hello", expected)
        assert result["match"] is True
