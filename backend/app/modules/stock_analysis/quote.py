"""
行情数据模块

提供股票、基金的实时和历史行情数据

注意：使用稳定的个股信息接口，避免使用容易被限流的全量行情接口
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 股票代码列表缓存（避免重复请求）
_stock_list_cache = None
_stock_list_cache_time = None
_CACHE_TTL = 3600  # 缓存1小时


def _get_stock_list():
    """获取 A股 股票代码列表（带缓存）"""
    import akshare as ak
    global _stock_list_cache, _stock_list_cache_time
    
    now = datetime.now()
    if _stock_list_cache is not None and _stock_list_cache_time:
        if (now - _stock_list_cache_time).seconds < _CACHE_TTL:
            return _stock_list_cache
    
    try:
        df = ak.stock_info_a_code_name()
        if df is not None and not df.empty:
            _stock_list_cache = df
            _stock_list_cache_time = now
            return df
    except Exception as e:
        logger.warning(f"获取股票列表失败: {e}")
    
    return _stock_list_cache  # 返回旧缓存（如果有）


async def search_stock(keyword: str, market: str = "A") -> list[dict]:
    """
    搜索股票/基金
    
    Args:
        keyword: 关键词（股票代码或名称）
        market: 市场类型 A=A股, HK=港股, FUND=基金
    
    Returns:
        匹配的股票/基金列表
    """
    import akshare as ak
    
    def _search():
        results = []
        try:
            if market == "A":
                # A股搜索 - 使用股票代码列表（更稳定）
                df = _get_stock_list()
                if df is not None and not df.empty:
                    # 按代码或名称过滤
                    mask = (
                        df["code"].astype(str).str.contains(keyword, case=False, na=False) |
                        df["name"].str.contains(keyword, case=False, na=False)
                    )
                    filtered = df[mask].head(10)
                    for _, row in filtered.iterrows():
                        results.append({
                            "code": str(row["code"]),
                            "name": row["name"],
                            "market": "A",
                        })
            
            elif market == "HK":
                # 港股搜索 - 使用港股列表
                try:
                    df = ak.stock_hk_spot_em()
                    if df is not None and not df.empty:
                        mask = (
                            df["代码"].str.contains(keyword, case=False, na=False) |
                            df["名称"].str.contains(keyword, case=False, na=False)
                        )
                        filtered = df[mask].head(10)
                        for _, row in filtered.iterrows():
                            results.append({
                                "code": row["代码"],
                                "name": row["名称"],
                                "market": "HK",
                                "price": float(row["最新价"]) if row["最新价"] else 0,
                                "change_percent": float(row["涨跌幅"]) if row["涨跌幅"] else 0,
                            })
                except Exception as e:
                    logger.warning(f"港股搜索失败: {e}")
            
            elif market == "FUND":
                # 基金搜索
                try:
                    df = ak.fund_etf_spot_em()
                    if df is not None and not df.empty:
                        mask = (
                            df["代码"].str.contains(keyword, case=False, na=False) |
                            df["名称"].str.contains(keyword, case=False, na=False)
                        )
                        filtered = df[mask].head(10)
                        for _, row in filtered.iterrows():
                            results.append({
                                "code": row["代码"],
                                "name": row["名称"],
                                "market": "FUND",
                                "price": float(row["最新价"]) if row["最新价"] else 0,
                                "change_percent": float(row["涨跌幅"]) if row["涨跌幅"] else 0,
                            })
                except Exception as e:
                    logger.warning(f"基金搜索失败: {e}")
                        
        except Exception as e:
            logger.error(f"搜索股票失败: {e}")
        
        return results
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _search)


async def get_stock_quote(symbol: str, market: str = "A") -> dict:
    """
    获取股票实时行情
    
    使用个股信息接口 + 最新历史数据，更稳定
    
    Args:
        symbol: 股票代码（如 600519）
        market: 市场类型 A=A股, HK=港股
    
    Returns:
        实时行情数据
    """
    import akshare as ak
    
    def _get_quote():
        try:
            if market == "A":
                # 获取个股基本信息
                try:
                    info_df = ak.stock_individual_info_em(symbol=symbol)
                except Exception as e:
                    logger.warning(f"获取个股信息失败: {e}")
                    info_df = None
                
                # 获取最新历史数据（包含价格）
                try:
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
                    hist_df = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period="daily",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq"
                    )
                except Exception as e:
                    logger.warning(f"获取历史数据失败: {e}")
                    hist_df = None
                
                if info_df is None and hist_df is None:
                    return {"error": f"未找到股票: {symbol}"}
                
                # 构建结果
                result = {
                    "code": symbol,
                    "market": "A",
                    "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                
                # 从个股信息获取基本数据
                if info_df is not None and not info_df.empty:
                    info = {}
                    for _, row in info_df.iterrows():
                        info[row["item"]] = row["value"]
                    
                    result["name"] = info.get("股票简称", "")
                    result["industry"] = info.get("行业", "")
                    result["total_market_cap"] = info.get("总市值", 0)
                    result["float_market_cap"] = info.get("流通市值", 0)
                    result["pe_ratio"] = info.get("市盈率(动态)", None)
                    result["pb_ratio"] = info.get("市净率", None)
                
                # 从历史数据获取最新价格
                if hist_df is not None and not hist_df.empty:
                    latest = hist_df.iloc[-1]
                    prev = hist_df.iloc[-2] if len(hist_df) > 1 else latest
                    
                    result["price"] = float(latest["收盘"])
                    result["open"] = float(latest["开盘"])
                    result["high"] = float(latest["最高"])
                    result["low"] = float(latest["最低"])
                    result["volume"] = float(latest["成交量"])
                    result["amount"] = float(latest["成交额"])
                    result["change_percent"] = float(latest["涨跌幅"]) if "涨跌幅" in latest else 0
                    result["change"] = result["price"] - float(prev["收盘"])
                    result["date"] = str(latest["日期"])
                
                return result
            
            elif market == "HK":
                # 港股 - 使用历史数据接口
                try:
                    end_date = datetime.now().strftime("%Y%m%d")
                    start_date = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
                    hist_df = ak.stock_hk_hist(
                        symbol=symbol,
                        period="daily",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq"
                    )
                    
                    if hist_df is None or hist_df.empty:
                        return {"error": f"未找到港股: {symbol}"}
                    
                    latest = hist_df.iloc[-1]
                    prev = hist_df.iloc[-2] if len(hist_df) > 1 else latest
                    
                    return {
                        "code": symbol,
                        "market": "HK",
                        "price": float(latest["收盘"]),
                        "open": float(latest["开盘"]),
                        "high": float(latest["最高"]),
                        "low": float(latest["最低"]),
                        "volume": float(latest["成交量"]),
                        "amount": float(latest["成交额"]),
                        "change_percent": float(latest["涨跌幅"]) if "涨跌幅" in latest else 0,
                        "change": float(latest["收盘"]) - float(prev["收盘"]),
                        "date": str(latest["日期"]),
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                except Exception as e:
                    logger.error(f"获取港股行情失败: {e}")
                    return {"error": f"获取港股行情失败: {str(e)}"}
            
            return {"error": f"未找到股票: {symbol}"}
            
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            return {"error": f"获取行情失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_quote)


async def get_stock_history(
    symbol: str,
    market: str = "A",
    period: str = "daily",
    days: int = 30
) -> dict:
    """
    获取股票历史行情
    
    Args:
        symbol: 股票代码
        market: 市场类型 A=A股, HK=港股
        period: 周期 daily=日线, weekly=周线, monthly=月线
        days: 获取天数
    
    Returns:
        历史行情数据
    """
    import akshare as ak
    
    def _get_history():
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
            
            if market == "A":
                df = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"  # 前复权
                )
            elif market == "HK":
                df = ak.stock_hk_hist(
                    symbol=symbol,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
            else:
                return {"error": f"不支持的市场类型: {market}"}
            
            if df is None or df.empty:
                return {"error": f"未找到历史数据: {symbol}"}
            
            # 取最近 N 条
            df = df.tail(days)
            
            history = []
            for _, row in df.iterrows():
                history.append({
                    "date": str(row["日期"]),
                    "open": float(row["开盘"]),
                    "close": float(row["收盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "volume": float(row["成交量"]),
                    "amount": float(row["成交额"]),
                    "change_percent": float(row["涨跌幅"]) if "涨跌幅" in row else 0,
                })
            
            return {
                "code": symbol,
                "market": market,
                "period": period,
                "count": len(history),
                "data": history,
            }
            
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}")
            return {"error": f"获取历史数据失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_history)


async def get_fund_quote(symbol: str) -> dict:
    """
    获取基金实时行情
    
    Args:
        symbol: 基金代码
    
    Returns:
        基金实时行情
    """
    import akshare as ak
    
    def _get_fund():
        try:
            # ETF 基金
            df = ak.fund_etf_spot_em()
            if df is not None and not df.empty:
                row = df[df["代码"] == symbol]
                if not row.empty:
                    row = row.iloc[0]
                    return {
                        "code": row["代码"],
                        "name": row["名称"],
                        "type": "ETF",
                        "price": float(row["最新价"]) if row["最新价"] else 0,
                        "change_percent": float(row["涨跌幅"]) if row["涨跌幅"] else 0,
                        "volume": float(row["成交量"]) if row["成交量"] else 0,
                        "amount": float(row["成交额"]) if row["成交额"] else 0,
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
            
            # 场外基金净值
            try:
                df = ak.fund_open_fund_info_em(symbol=symbol, indicator="单位净值走势")
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    return {
                        "code": symbol,
                        "type": "开放式基金",
                        "nav": float(latest["单位净值"]) if "单位净值" in latest else 0,
                        "date": str(latest["净值日期"]) if "净值日期" in latest else "",
                        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
            except Exception:
                pass
            
            return {"error": f"未找到基金: {symbol}"}
            
        except Exception as e:
            logger.error(f"获取基金行情失败: {e}")
            return {"error": f"获取基金行情失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_fund)
