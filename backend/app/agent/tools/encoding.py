"""
编码/解码工具

包装 modules.encoding 模块的功能为 Agent 可调用的工具。
"""

from ..base import ToolParameter, ParameterType
from ..registry import ToolRegistry
from ...modules.encoding import (
    base64_encode, base64_decode,
    url_encode, url_decode,
    html_encode, html_decode,
    hex_encode, hex_decode,
    unicode_encode, unicode_decode,
    rot13,
)


def register_encoding_tools(registry: ToolRegistry) -> None:
    """注册编码工具"""
    
    # Base64 编码
    registry.register_function(
        name="base64_encode",
        description="将文本进行 Base64 编码。常用于在 HTTP 请求中传输二进制数据或隐藏明文。",
        func=base64_encode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要编码的文本内容",
            )
        ],
        category="encoding",
    )
    
    # Base64 解码
    registry.register_function(
        name="base64_decode",
        description="将 Base64 编码的字符串解码为原始文本。支持标准 Base64 和 URL 安全的 Base64。",
        func=base64_decode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要解码的 Base64 字符串",
            )
        ],
        category="encoding",
    )
    
    # URL 编码
    registry.register_function(
        name="url_encode",
        description="将文本进行 URL 编码（百分号编码）。用于在 URL 中安全传输特殊字符。",
        func=url_encode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要编码的文本",
            )
        ],
        category="encoding",
    )
    
    # URL 解码
    registry.register_function(
        name="url_decode",
        description="将 URL 编码的字符串解码为原始文本。",
        func=url_decode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要解码的 URL 编码字符串",
            )
        ],
        category="encoding",
    )
    
    # HTML 编码
    registry.register_function(
        name="html_encode",
        description="将文本中的特殊字符转换为 HTML 实体。用于防止 XSS 攻击或在 HTML 中安全显示特殊字符。",
        func=html_encode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要编码的文本",
            )
        ],
        category="encoding",
    )
    
    # HTML 解码
    registry.register_function(
        name="html_decode",
        description="将 HTML 实体解码为原始字符。",
        func=html_decode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="包含 HTML 实体的文本",
            )
        ],
        category="encoding",
    )
    
    # Hex 编码
    registry.register_function(
        name="hex_encode",
        description="将文本转换为十六进制表示。常用于分析二进制数据或绕过某些过滤器。",
        func=hex_encode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要编码的文本",
            )
        ],
        category="encoding",
    )
    
    # Hex 解码
    registry.register_function(
        name="hex_decode",
        description="将十六进制字符串解码为原始文本。支持带空格、0x 前缀等格式。",
        func=hex_decode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="十六进制字符串",
            )
        ],
        category="encoding",
    )
    
    # Unicode 编码
    registry.register_function(
        name="unicode_encode",
        description="将文本转换为 Unicode 转义序列（\\uXXXX 格式）。用于分析或构造 Unicode 字符。",
        func=unicode_encode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要编码的文本",
            )
        ],
        category="encoding",
    )
    
    # Unicode 解码
    registry.register_function(
        name="unicode_decode",
        description="将 Unicode 转义序列解码为原始文本。",
        func=unicode_decode,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="包含 Unicode 转义序列的字符串",
            )
        ],
        category="encoding",
    )
    
    # ROT13
    registry.register_function(
        name="rot13",
        description="ROT13 编码/解码。将字母表中的字母替换为其后第13个字母，编码和解码使用相同操作。",
        func=rot13,
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="要处理的文本",
            )
        ],
        category="encoding",
    )

