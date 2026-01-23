"""网络工具模块"""
import asyncio
import socket
import dns.resolver
import whois as python_whois
import requests
from typing import Optional


async def dns_lookup(domain: str, record_type: str = "A") -> dict:
    """DNS 查询"""
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = 5
        resolver.lifetime = 5
        
        # 在线程池中运行同步 DNS 查询
        loop = asyncio.get_event_loop()
        answers = await loop.run_in_executor(
            None, 
            lambda: resolver.resolve(domain, record_type)
        )
        
        records = []
        for rdata in answers:
            records.append(str(rdata))
        
        return {
            "domain": domain,
            "record_type": record_type,
            "records": records,
            "ttl": answers.rrset.ttl if answers.rrset else None
        }
    except dns.resolver.NXDOMAIN:
        return {"error": "域名不存在"}
    except dns.resolver.NoAnswer:
        return {"error": f"没有 {record_type} 记录"}
    except dns.resolver.Timeout:
        return {"error": "查询超时"}
    except Exception as e:
        return {"error": str(e)}


async def whois_lookup(domain: str) -> dict:
    """WHOIS 查询"""
    try:
        loop = asyncio.get_event_loop()
        w = await loop.run_in_executor(None, python_whois.whois, domain)
        
        # 转换为可序列化的字典
        result = {
            "domain_name": w.domain_name,
            "registrar": w.registrar,
            "whois_server": w.whois_server,
            "creation_date": str(w.creation_date) if w.creation_date else None,
            "expiration_date": str(w.expiration_date) if w.expiration_date else None,
            "updated_date": str(w.updated_date) if w.updated_date else None,
            "name_servers": w.name_servers,
            "status": w.status,
            "emails": w.emails,
            "registrant": w.registrant,
            "country": w.country,
        }
        
        # 清理 None 值
        result = {k: v for k, v in result.items() if v is not None}
        
        return result
    except Exception as e:
        return {"error": str(e)}


async def ip_info(ip: str) -> dict:
    """IP 信息查询"""
    try:
        loop = asyncio.get_event_loop()
        
        # 使用免费的 IP 查询 API
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                return {
                    "ip": ip,
                    "country": data.get("country"),
                    "country_code": data.get("countryCode"),
                    "region": data.get("regionName"),
                    "city": data.get("city"),
                    "zip": data.get("zip"),
                    "lat": data.get("lat"),
                    "lon": data.get("lon"),
                    "timezone": data.get("timezone"),
                    "isp": data.get("isp"),
                    "org": data.get("org"),
                    "as": data.get("as"),
                }
            else:
                return {"error": data.get("message", "查询失败")}
        else:
            return {"error": f"HTTP 错误: {response.status_code}"}
    except requests.Timeout:
        return {"error": "查询超时"}
    except Exception as e:
        return {"error": str(e)}


def reverse_dns(ip: str) -> dict:
    """反向 DNS 查询"""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return {
            "ip": ip,
            "hostname": hostname
        }
    except socket.herror:
        return {"error": "没有找到对应的主机名"}
    except Exception as e:
        return {"error": str(e)}


def get_dns_record_types() -> list:
    """获取支持的 DNS 记录类型"""
    return [
        {"type": "A", "description": "IPv4 地址"},
        {"type": "AAAA", "description": "IPv6 地址"},
        {"type": "CNAME", "description": "规范名称"},
        {"type": "MX", "description": "邮件交换"},
        {"type": "TXT", "description": "文本记录"},
        {"type": "NS", "description": "名称服务器"},
        {"type": "SOA", "description": "起始授权"},
        {"type": "PTR", "description": "指针记录"},
        {"type": "SRV", "description": "服务记录"},
    ]

