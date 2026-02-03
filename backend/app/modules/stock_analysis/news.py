"""
新闻舆情模块

提供股票相关新闻和市场资讯
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_stock_news(symbol: str, max_count: int = 10) -> dict:
    """
    获取个股新闻
    
    Args:
        symbol: 股票代码
        max_count: 最大新闻数量
    
    Returns:
        新闻列表
    """
    import akshare as ak
    
    def _get_news():
        try:
            df = ak.stock_news_em(symbol=symbol)
            if df is None or df.empty:
                return {"error": f"未找到相关新闻: {symbol}"}
            
            # 取最新的几条
            df = df.head(max_count)
            
            news_list = []
            for _, row in df.iterrows():
                news = {
                    "title": row.get("新闻标题", ""),
                    "content": row.get("新闻内容", "")[:500] if row.get("新闻内容") else "",  # 截取前500字
                    "source": row.get("新闻来源", ""),
                    "time": str(row.get("发布时间", "")),
                    "url": row.get("新闻链接", ""),
                }
                news_list.append(news)
            
            return {
                "code": symbol,
                "count": len(news_list),
                "news": news_list,
            }
            
        except Exception as e:
            logger.error(f"获取个股新闻失败: {e}")
            return {"error": f"获取个股新闻失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_news)


async def get_market_news(category: str = "财经", max_count: int = 10) -> dict:
    """
    获取市场新闻资讯
    
    Args:
        category: 新闻类别（财经、股票、基金等）
        max_count: 最大新闻数量
    
    Returns:
        新闻列表
    """
    import akshare as ak
    
    def _get_market_news():
        try:
            # 获取财经新闻
            df = ak.stock_info_global_em()
            if df is None or df.empty:
                # 备选：使用东方财富快讯
                try:
                    df = ak.stock_info_global_cls()
                except Exception:
                    return {"error": "获取市场新闻失败"}
            
            if df is None or df.empty:
                return {"error": "暂无市场新闻"}
            
            df = df.head(max_count)
            
            news_list = []
            for _, row in df.iterrows():
                # 根据不同数据源处理字段
                title = row.get("标题", "") or row.get("title", "")
                content = row.get("内容", "") or row.get("content", "")
                time_str = str(row.get("发布时间", "") or row.get("time", ""))
                
                news = {
                    "title": title,
                    "content": content[:300] if content else "",
                    "time": time_str,
                }
                news_list.append(news)
            
            return {
                "category": category,
                "count": len(news_list),
                "news": news_list,
            }
            
        except Exception as e:
            logger.error(f"获取市场新闻失败: {e}")
            return {"error": f"获取市场新闻失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_market_news)


async def get_research_reports(symbol: str, max_count: int = 5) -> dict:
    """
    获取研究报告
    
    Args:
        symbol: 股票代码
        max_count: 最大数量
    
    Returns:
        研报列表
    """
    import akshare as ak
    
    def _get_reports():
        try:
            df = ak.stock_research_report_em(symbol=symbol)
            if df is None or df.empty:
                return {"error": f"未找到研报: {symbol}"}
            
            df = df.head(max_count)
            
            reports = []
            for _, row in df.iterrows():
                report = {
                    "title": row.get("报告名称", ""),
                    "org": row.get("机构名称", ""),
                    "author": row.get("作者", ""),
                    "date": str(row.get("日期", "")),
                    "rating": row.get("评级", ""),
                }
                reports.append(report)
            
            return {
                "code": symbol,
                "count": len(reports),
                "reports": reports,
            }
            
        except Exception as e:
            logger.error(f"获取研报失败: {e}")
            # 研报接口可能不可用，返回空结果而非错误
            return {
                "code": symbol,
                "count": 0,
                "reports": [],
                "note": "暂无研报数据",
            }
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_reports)
