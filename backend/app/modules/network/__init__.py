"""网络工具模块"""
import asyncio
import socket
import re
import dns.resolver
import whois as python_whois
import requests
from typing import Optional
from urllib.parse import urlparse


def parse_input(input_str: str) -> dict:
    """解析用户输入，识别是 URL、域名还是 IP"""
    input_str = input_str.strip()
    
    # IPv4 正则
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    # IPv6 简单正则
    ipv6_pattern = r'^([0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}$'
    
    # 检查是否是 IP
    if re.match(ipv4_pattern, input_str):
        # 验证每个数字是否在 0-255
        parts = input_str.split('.')
        if all(0 <= int(p) <= 255 for p in parts):
            return {"type": "ip", "value": input_str, "ip_version": 4}
    
    if re.match(ipv6_pattern, input_str):
        return {"type": "ip", "value": input_str, "ip_version": 6}
    
    # 检查是否是 URL
    if input_str.startswith(('http://', 'https://', '//')):
        try:
            parsed = urlparse(input_str)
            domain = parsed.netloc or parsed.path.split('/')[0]
            # 移除端口号
            domain = domain.split(':')[0]
            if domain:
                return {"type": "domain", "value": domain, "original_url": input_str}
        except:
            pass
    
    # 假设是域名
    # 简单验证域名格式
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'
    if re.match(domain_pattern, input_str):
        return {"type": "domain", "value": input_str}
    
    # 宽松匹配，可能是简单域名
    if '.' in input_str and not input_str.startswith('.') and not input_str.endswith('.'):
        return {"type": "domain", "value": input_str}
    
    return {"type": "unknown", "value": input_str, "error": "无法识别输入类型"}


async def analyze_target(input_str: str) -> dict:
    """综合分析目标，自动执行所有相关查询"""
    parsed = parse_input(input_str)
    
    result = {
        "input": input_str,
        "parsed": parsed,
        "results": {}
    }
    
    if parsed["type"] == "unknown":
        result["error"] = parsed.get("error", "无法识别输入类型")
        return result
    
    if parsed["type"] == "ip":
        # IP 地址分析
        ip = parsed["value"]
        
        # 并行执行 IP 相关查询
        ip_info_task = asyncio.create_task(ip_info(ip))
        loop = asyncio.get_event_loop()
        reverse_dns_task = loop.run_in_executor(None, reverse_dns, ip)
        
        ip_info_result, reverse_dns_result = await asyncio.gather(
            ip_info_task, reverse_dns_task, return_exceptions=True
        )
        
        if isinstance(ip_info_result, Exception):
            result["results"]["ip_info"] = {"error": str(ip_info_result)}
        else:
            result["results"]["ip_info"] = ip_info_result
        
        if isinstance(reverse_dns_result, Exception):
            result["results"]["reverse_dns"] = {"error": str(reverse_dns_result)}
        else:
            result["results"]["reverse_dns"] = reverse_dns_result
        
        # 如果反向 DNS 成功，尝试查询该域名的信息
        if "hostname" in reverse_dns_result and not reverse_dns_result.get("error"):
            hostname = reverse_dns_result["hostname"]
            result["results"]["hostname_whois"] = await whois_lookup(hostname)
    
    elif parsed["type"] == "domain":
        # 域名分析
        domain = parsed["value"]
        
        # 并行执行多种 DNS 查询
        dns_types = ["A", "AAAA", "MX", "NS", "TXT", "CNAME"]
        dns_tasks = [dns_lookup(domain, t) for t in dns_types]
        
        # WHOIS 查询
        whois_task = asyncio.create_task(whois_lookup(domain))
        
        # 等待所有 DNS 查询完成
        dns_results_list = await asyncio.gather(*dns_tasks, return_exceptions=True)
        dns_results = {}
        for record_type, result_item in zip(dns_types, dns_results_list):
            if isinstance(result_item, Exception):
                dns_results[record_type] = {"error": str(result_item)}
            else:
                dns_results[record_type] = result_item
        
        result["results"]["dns"] = dns_results
        try:
            result["results"]["whois"] = await whois_task
        except Exception as e:
            result["results"]["whois"] = {"error": str(e)}
        
        # 从 A 记录获取 IP 并查询 IP 信息
        a_records = dns_results.get("A", {})
        if "records" in a_records and a_records["records"]:
            ip = a_records["records"][0]
            result["results"]["ip_info"] = await ip_info(ip)
            loop = asyncio.get_event_loop()
            result["results"]["reverse_dns"] = await loop.run_in_executor(None, reverse_dns, ip)
    
    return result


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

