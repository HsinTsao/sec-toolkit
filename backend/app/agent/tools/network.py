"""
网络查询工具

包装 modules.network 模块的功能为 Agent 可调用的工具。
"""

from ..base import ToolParameter, ParameterType
from ..registry import ToolRegistry
from ...modules.network import (
    dns_lookup,
    whois_lookup,
    ip_info,
    reverse_dns,
    analyze_target,
)


def register_network_tools(registry: ToolRegistry) -> None:
    """注册网络工具"""
    
    # DNS 查询
    registry.register_function(
        name="dns_lookup",
        description="查询域名的 DNS 记录。支持 A、AAAA、MX、NS、TXT、CNAME 等记录类型。用于域名解析分析和信息收集。",
        func=dns_lookup,
        parameters=[
            ToolParameter(
                name="domain",
                type=ParameterType.STRING,
                description="要查询的域名",
            ),
            ToolParameter(
                name="record_type",
                type=ParameterType.STRING,
                description="DNS 记录类型",
                required=False,
                default="A",
                enum=["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "PTR", "SRV"],
            )
        ],
        category="network",
    )
    
    # WHOIS 查询
    registry.register_function(
        name="whois_lookup",
        description="查询域名的 WHOIS 信息，包括注册商、注册日期、过期日期、名称服务器等。用于域名所有权分析。",
        func=whois_lookup,
        parameters=[
            ToolParameter(
                name="domain",
                type=ParameterType.STRING,
                description="要查询的域名",
            )
        ],
        category="network",
    )
    
    # IP 信息查询
    registry.register_function(
        name="ip_info",
        description="查询 IP 地址的地理位置和网络信息，包括国家、城市、ISP、组织等。用于 IP 归属地分析。",
        func=ip_info,
        parameters=[
            ToolParameter(
                name="ip",
                type=ParameterType.STRING,
                description="要查询的 IP 地址",
            )
        ],
        category="network",
    )
    
    # 反向 DNS 查询
    registry.register_function(
        name="reverse_dns",
        description="反向 DNS 查询，根据 IP 地址查找对应的主机名。用于识别 IP 地址对应的服务。",
        func=reverse_dns,
        parameters=[
            ToolParameter(
                name="ip",
                type=ParameterType.STRING,
                description="要查询的 IP 地址",
            )
        ],
        category="network",
    )
    
    # 综合目标分析
    registry.register_function(
        name="analyze_target",
        description="综合分析目标（域名或IP），自动执行 DNS 查询、WHOIS 查询、IP 信息查询等。输入可以是域名、URL 或 IP 地址。",
        func=analyze_target,
        parameters=[
            ToolParameter(
                name="input_str",
                type=ParameterType.STRING,
                description="目标地址（域名、URL 或 IP）",
            )
        ],
        category="network",
    )

