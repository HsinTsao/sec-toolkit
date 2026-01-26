"""
哈希计算工具

包装 modules.hash_tools 模块的功能为 Agent 可调用的工具。
"""

from ..base import ToolParameter, ParameterType
from ..registry import ToolRegistry
from ...modules.hash_tools import (
    calculate_hash,
    calculate_all_hashes,
    calculate_hmac,
    compare_hash,
)


def register_hash_tools(registry: ToolRegistry) -> None:
    """注册哈希工具"""
    
    # 计算哈希
    registry.register_function(
        name="calculate_hash",
        description="计算文本的哈希值。支持 MD5、SHA1、SHA256、SHA384、SHA512 等算法。用于数据完整性校验、密码存储分析等。",
        func=calculate_hash,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要计算哈希的文本",
            ),
            ToolParameter(
                name="algorithm",
                type=ParameterType.STRING,
                description="哈希算法",
                required=False,
                default="sha256",
                enum=["md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "sha3_512"],
            )
        ],
        category="hash",
    )
    
    # 计算所有常用哈希
    registry.register_function(
        name="calculate_all_hashes",
        description="同时计算文本的所有常用哈希值（MD5、SHA1、SHA256、SHA384、SHA512）。便于快速对比或分析。",
        func=calculate_all_hashes,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要计算哈希的文本",
            )
        ],
        category="hash",
    )
    
    # 计算 HMAC
    registry.register_function(
        name="calculate_hmac",
        description="计算 HMAC（基于哈希的消息认证码）。用于消息认证和完整性校验，需要提供密钥。",
        func=calculate_hmac,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要计算 HMAC 的消息内容",
            ),
            ToolParameter(
                name="key",
                type=ParameterType.STRING,
                description="HMAC 密钥",
            ),
            ToolParameter(
                name="algorithm",
                type=ParameterType.STRING,
                description="哈希算法",
                required=False,
                default="sha256",
                enum=["md5", "sha1", "sha256", "sha512"],
            )
        ],
        category="hash",
    )
    
    # 比较哈希
    registry.register_function(
        name="compare_hash",
        description="比较文本的哈希值是否与预期匹配。可自动检测哈希算法类型。用于验证数据完整性或密码校验。",
        func=compare_hash,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="原始文本",
            ),
            ToolParameter(
                name="expected_hash",
                type=ParameterType.STRING,
                description="预期的哈希值",
            ),
            ToolParameter(
                name="algorithm",
                type=ParameterType.STRING,
                description="哈希算法，auto 表示自动检测",
                required=False,
                default="auto",
                enum=["auto", "md5", "sha1", "sha256", "sha512"],
            )
        ],
        category="hash",
    )

