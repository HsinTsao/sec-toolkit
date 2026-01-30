"""
搜索工具 - LLM Agent 可调用的网络搜索

提供以下工具:
- web_search: 网络搜索
- news_search: 新闻搜索
"""

import re
from ..base import ToolParameter, ParameterType
from ..registry import ToolRegistry


def _optimize_query(query: str) -> str:
    """
    优化搜索查询
    
    对特定类型的查询进行智能处理，提高搜索结果相关性
    """
    query = query.strip()
    
    # 天气查询优化：添加 "天气预报" 关键词
    weather_keywords = ["天气", "气温", "温度", "下雨", "下雪", "刮风", "晴天", "阴天"]
    is_weather_query = any(kw in query for kw in weather_keywords)
    
    if is_weather_query and "天气预报" not in query:
        # 清理多余词汇
        query = re.sub(r"(怎么样|如何|会不会|是否|吗|呢)$", "", query).strip()
        query = f"{query} 天气预报"
    
    # 价格查询优化
    if re.search(r"(?:价格|股价|汇率|行情)$", query):
        query = f"{query} 最新"
    
    return query


async def tool_web_search(query: str, max_results: int = 5) -> dict:
    """网络搜索"""
    from ...modules.search import web_search
    
    # 优化查询
    optimized_query = _optimize_query(query)
    
    results = await web_search(query=optimized_query, max_results=max_results)
    return {
        "original_query": query,
        "optimized_query": optimized_query,
        "count": len(results),
        "results": results
    }


async def tool_news_search(query: str, max_results: int = 5) -> dict:
    """新闻搜索"""
    from ...modules.search import news_search
    
    results = await news_search(query=query, max_results=max_results)
    return {
        "query": query,
        "count": len(results),
        "results": results
    }


async def tool_weather(location: str = "") -> dict:
    """
    获取天气信息
    
    使用 wttr.in 免费天气 API
    """
    import httpx
    import logging
    
    logger = logging.getLogger(__name__)
    
    # 默认城市
    if not location:
        location = "Shanghai"  # 默认上海
    
    try:
        # wttr.in 支持中文城市名
        url = f"https://wttr.in/{location}?format=j1"
        logger.info(f"[Weather] 请求: {url}")
        
        async with httpx.AsyncClient(timeout=30) as client:  # 增加超时到 30 秒
            response = await client.get(url, headers={"Accept-Language": "zh-CN"})
            
            logger.info(f"[Weather] 响应: status={response.status_code}")
            
            if response.status_code != 200:
                logger.warning(f"[Weather] 请求失败: HTTP {response.status_code}")
                return {"error": f"获取天气失败: HTTP {response.status_code}"}
            
            data = response.json()
            
            # 解析天气数据
            current = data.get("current_condition", [{}])[0]
            weather_desc = current.get("lang_zh", [{}])
            if weather_desc:
                weather_desc = weather_desc[0].get("value", current.get("weatherDesc", [{}])[0].get("value", ""))
            else:
                weather_desc = current.get("weatherDesc", [{}])[0].get("value", "")
            
            result = {
                "location": location,
                "temperature": f"{current.get('temp_C', 'N/A')}°C",
                "feels_like": f"{current.get('FeelsLikeC', 'N/A')}°C",
                "weather": weather_desc,
                "humidity": f"{current.get('humidity', 'N/A')}%",
                "wind": f"{current.get('windspeedKmph', 'N/A')} km/h",
                "visibility": f"{current.get('visibility', 'N/A')} km",
            }
            
            # 添加未来天气
            forecast = data.get("weather", [])
            if forecast:
                result["forecast"] = []
                for day in forecast[:3]:
                    result["forecast"].append({
                        "date": day.get("date", ""),
                        "max_temp": f"{day.get('maxtempC', 'N/A')}°C",
                        "min_temp": f"{day.get('mintempC', 'N/A')}°C",
                    })
            
            return result
            
    except Exception as e:
        logger.error(f"[Weather] 异常: {type(e).__name__}: {e}")
        return {"error": f"获取天气失败: {str(e)}"}


def register_search_tools(registry: ToolRegistry) -> None:
    """注册搜索工具"""
    
    registry.register_function(
        name="web_search",
        description="搜索互联网获取最新信息。当需要查找实时信息、新闻、技术文档、或任何需要联网查询的内容时使用。",
        func=tool_web_search,
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="搜索关键词"
            ),
            ToolParameter(
                name="max_results",
                type=ParameterType.INTEGER,
                description="返回结果数量（1-10）",
                required=False
            ),
        ],
        category="search",
    )
    
    registry.register_function(
        name="news_search",
        description="搜索最新新闻和资讯。当需要查找近期新闻、行业动态、时事热点时使用。",
        func=tool_news_search,
        parameters=[
            ToolParameter(
                name="query",
                type=ParameterType.STRING,
                description="新闻搜索关键词"
            ),
            ToolParameter(
                name="max_results",
                type=ParameterType.INTEGER,
                description="返回结果数量（1-10）",
                required=False
            ),
        ],
        category="search",
    )
    
    registry.register_function(
        name="weather",
        description="获取指定城市的实时天气信息，包括温度、湿度、风速等。查询天气、气温、是否下雨等问题时使用。",
        func=tool_weather,
        parameters=[
            ToolParameter(
                name="location",
                type=ParameterType.STRING,
                description="城市名称（如：北京、上海、广州）",
                required=False
            ),
        ],
        category="search",
    )
