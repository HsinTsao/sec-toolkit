"""格式处理工具模块"""
import json
import re
import uuid as uuid_lib
import difflib
from datetime import datetime
from xml.dom import minidom
import xml.etree.ElementTree as ET


def format_json(text: str, indent: int = 2) -> str:
    """JSON 格式化"""
    try:
        data = json.loads(text)
        return json.dumps(data, indent=indent, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return f"JSON 解析错误: {str(e)}"
    except Exception as e:
        return f"错误: {str(e)}"


def minify_json(text: str) -> str:
    """JSON 压缩"""
    try:
        data = json.loads(text)
        return json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    except json.JSONDecodeError as e:
        return f"JSON 解析错误: {str(e)}"
    except Exception as e:
        return f"错误: {str(e)}"


def format_xml(text: str) -> str:
    """XML 格式化"""
    try:
        dom = minidom.parseString(text)
        return dom.toprettyxml(indent="  ")
    except Exception as e:
        return f"XML 解析错误: {str(e)}"


def json_to_yaml(text: str) -> str:
    """JSON 转 YAML"""
    try:
        import yaml
        data = json.loads(text)
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)
    except ImportError:
        return "需要安装 PyYAML: pip install pyyaml"
    except Exception as e:
        return f"错误: {str(e)}"


def convert_format(text: str, from_format: str, to_format: str) -> str:
    """格式转换"""
    try:
        # 解析源格式
        if from_format.lower() == "json":
            data = json.loads(text)
        elif from_format.lower() == "xml":
            root = ET.fromstring(text)
            data = _xml_to_dict(root)
        else:
            return f"不支持的源格式: {from_format}"
        
        # 转换为目标格式
        if to_format.lower() == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif to_format.lower() == "xml":
            return _dict_to_xml(data)
        else:
            return f"不支持的目标格式: {to_format}"
    except Exception as e:
        return f"错误: {str(e)}"


def _xml_to_dict(element) -> dict:
    """XML 元素转字典"""
    result = {}
    for child in element:
        if len(child) == 0:
            result[child.tag] = child.text
        else:
            result[child.tag] = _xml_to_dict(child)
    return result


def _dict_to_xml(data: dict, root_name: str = "root") -> str:
    """字典转 XML"""
    root = ET.Element(root_name)
    _dict_to_xml_element(data, root)
    return ET.tostring(root, encoding='unicode')


def _dict_to_xml_element(data, parent):
    """递归将字典转为 XML 元素"""
    if isinstance(data, dict):
        for key, value in data.items():
            child = ET.SubElement(parent, key)
            _dict_to_xml_element(value, child)
    elif isinstance(data, list):
        for item in data:
            child = ET.SubElement(parent, "item")
            _dict_to_xml_element(item, child)
    else:
        parent.text = str(data) if data is not None else ""


def test_regex(pattern: str, text: str, flags: str = "") -> dict:
    """正则表达式测试"""
    try:
        # 解析 flags
        flag_value = 0
        if 'i' in flags:
            flag_value |= re.IGNORECASE
        if 'm' in flags:
            flag_value |= re.MULTILINE
        if 's' in flags:
            flag_value |= re.DOTALL
        
        regex = re.compile(pattern, flag_value)
        
        # 查找所有匹配
        matches = []
        for match in regex.finditer(text):
            match_info = {
                "match": match.group(),
                "start": match.start(),
                "end": match.end(),
                "groups": match.groups() if match.groups() else None
            }
            matches.append(match_info)
        
        return {
            "pattern": pattern,
            "flags": flags,
            "match_count": len(matches),
            "matches": matches
        }
    except re.error as e:
        return {"error": f"正则表达式错误: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}


def text_diff(text1: str, text2: str) -> list:
    """文本对比"""
    try:
        diff = difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile='text1',
            tofile='text2'
        )
        return list(diff)
    except Exception as e:
        return [f"错误: {str(e)}"]


def convert_timestamp(
    timestamp: int = None,
    datetime_str: str = None,
    format: str = "%Y-%m-%d %H:%M:%S"
) -> dict:
    """时间戳转换"""
    try:
        result = {}
        
        if timestamp is not None:
            # 时间戳转日期
            if timestamp > 10000000000:
                # 毫秒时间戳
                dt = datetime.fromtimestamp(timestamp / 1000)
                result['is_milliseconds'] = True
            else:
                # 秒时间戳
                dt = datetime.fromtimestamp(timestamp)
                result['is_milliseconds'] = False
            
            result['timestamp'] = timestamp
            result['datetime'] = dt.strftime(format)
            result['iso'] = dt.isoformat()
            result['utc'] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        elif datetime_str is not None:
            # 日期转时间戳
            dt = datetime.strptime(datetime_str, format)
            result['datetime'] = datetime_str
            result['timestamp'] = int(dt.timestamp())
            result['timestamp_ms'] = int(dt.timestamp() * 1000)
            result['iso'] = dt.isoformat()
        
        else:
            # 返回当前时间
            now = datetime.now()
            result['datetime'] = now.strftime(format)
            result['timestamp'] = int(now.timestamp())
            result['timestamp_ms'] = int(now.timestamp() * 1000)
            result['iso'] = now.isoformat()
        
        return result
    except Exception as e:
        return {"error": str(e)}


def base_convert(value: str, from_base: int, to_base: int) -> str:
    """进制转换"""
    try:
        if from_base < 2 or from_base > 36 or to_base < 2 or to_base > 36:
            return "进制范围: 2-36"
        
        # 转为十进制
        decimal_value = int(value, from_base)
        
        # 转为目标进制
        if to_base == 10:
            return str(decimal_value)
        
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        result = ""
        
        if decimal_value == 0:
            return "0"
        
        negative = decimal_value < 0
        decimal_value = abs(decimal_value)
        
        while decimal_value:
            result = digits[decimal_value % to_base] + result
            decimal_value //= to_base
        
        return ("-" + result) if negative else result
    except ValueError:
        return f"无效的 {from_base} 进制数"
    except Exception as e:
        return f"错误: {str(e)}"


def generate_uuid() -> dict:
    """生成 UUID"""
    uuid1 = str(uuid_lib.uuid1())
    uuid4 = str(uuid_lib.uuid4())
    
    return {
        "uuid1": uuid1,
        "uuid4": uuid4,
        "uuid1_no_dash": uuid1.replace("-", ""),
        "uuid4_no_dash": uuid4.replace("-", "")
    }

