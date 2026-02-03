"""
技术指标模块

提供常用技术分析指标计算
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _calculate_ma(prices: list, period: int) -> list:
    """计算移动平均线"""
    ma = []
    for i in range(len(prices)):
        if i < period - 1:
            ma.append(None)
        else:
            ma.append(sum(prices[i-period+1:i+1]) / period)
    return ma


def _calculate_ema(prices: list, period: int) -> list:
    """计算指数移动平均"""
    ema = []
    multiplier = 2 / (period + 1)
    
    for i, price in enumerate(prices):
        if i == 0:
            ema.append(price)
        else:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
    
    return ema


def _calculate_macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """计算 MACD 指标"""
    ema_fast = _calculate_ema(prices, fast)
    ema_slow = _calculate_ema(prices, slow)
    
    # DIF = 快线 - 慢线
    dif = [f - s if f and s else None for f, s in zip(ema_fast, ema_slow)]
    
    # DEA = DIF 的 EMA
    dif_valid = [d for d in dif if d is not None]
    dea_valid = _calculate_ema(dif_valid, signal)
    
    # 补充 None
    dea = [None] * (len(dif) - len(dea_valid)) + dea_valid
    
    # MACD 柱 = (DIF - DEA) * 2
    macd_bar = []
    for d, e in zip(dif, dea):
        if d is not None and e is not None:
            macd_bar.append((d - e) * 2)
        else:
            macd_bar.append(None)
    
    return {
        "dif": dif,
        "dea": dea,
        "macd": macd_bar,
    }


def _calculate_kdj(highs: list, lows: list, closes: list, period: int = 9) -> dict:
    """计算 KDJ 指标"""
    k_values = []
    d_values = []
    j_values = []
    
    for i in range(len(closes)):
        if i < period - 1:
            k_values.append(50)
            d_values.append(50)
            j_values.append(50)
            continue
        
        # RSV = (收盘价 - N日最低) / (N日最高 - N日最低) * 100
        period_high = max(highs[i-period+1:i+1])
        period_low = min(lows[i-period+1:i+1])
        
        if period_high == period_low:
            rsv = 50
        else:
            rsv = (closes[i] - period_low) / (period_high - period_low) * 100
        
        # K = 2/3 * 前K + 1/3 * RSV
        k = 2/3 * k_values[-1] + 1/3 * rsv
        # D = 2/3 * 前D + 1/3 * K
        d = 2/3 * d_values[-1] + 1/3 * k
        # J = 3K - 2D
        j = 3 * k - 2 * d
        
        k_values.append(k)
        d_values.append(d)
        j_values.append(j)
    
    return {
        "k": k_values,
        "d": d_values,
        "j": j_values,
    }


def _calculate_rsi(prices: list, period: int = 14) -> list:
    """计算 RSI 相对强弱指标"""
    rsi = []
    gains = []
    losses = []
    
    for i in range(len(prices)):
        if i == 0:
            rsi.append(50)
            continue
        
        change = prices[i] - prices[i-1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
        
        if i < period:
            rsi.append(50)
            continue
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))
    
    return rsi


def _calculate_boll(prices: list, period: int = 20, std_dev: int = 2) -> dict:
    """计算布林带"""
    import math
    
    upper = []
    middle = []
    lower = []
    
    for i in range(len(prices)):
        if i < period - 1:
            upper.append(None)
            middle.append(None)
            lower.append(None)
            continue
        
        # 中轨 = MA
        ma = sum(prices[i-period+1:i+1]) / period
        
        # 标准差
        variance = sum((p - ma) ** 2 for p in prices[i-period+1:i+1]) / period
        std = math.sqrt(variance)
        
        middle.append(ma)
        upper.append(ma + std_dev * std)
        lower.append(ma - std_dev * std)
    
    return {
        "upper": upper,
        "middle": middle,
        "lower": lower,
    }


async def calculate_indicators(
    prices: list[dict],
    indicators: list[str] = None
) -> dict:
    """
    计算技术指标
    
    Args:
        prices: 价格数据列表 [{"close": x, "high": y, "low": z}, ...]
        indicators: 需要计算的指标列表 ["MA", "MACD", "KDJ", "RSI", "BOLL"]
    
    Returns:
        技术指标数据
    """
    if not prices:
        return {"error": "价格数据为空"}
    
    if indicators is None:
        indicators = ["MA", "MACD", "KDJ", "RSI"]
    
    closes = [p["close"] for p in prices]
    highs = [p["high"] for p in prices]
    lows = [p["low"] for p in prices]
    
    result = {
        "count": len(prices),
        "indicators": {},
    }
    
    for ind in indicators:
        ind_upper = ind.upper()
        
        if ind_upper == "MA":
            result["indicators"]["MA5"] = _calculate_ma(closes, 5)
            result["indicators"]["MA10"] = _calculate_ma(closes, 10)
            result["indicators"]["MA20"] = _calculate_ma(closes, 20)
            result["indicators"]["MA60"] = _calculate_ma(closes, 60)
        
        elif ind_upper == "MACD":
            result["indicators"]["MACD"] = _calculate_macd(closes)
        
        elif ind_upper == "KDJ":
            result["indicators"]["KDJ"] = _calculate_kdj(highs, lows, closes)
        
        elif ind_upper == "RSI":
            result["indicators"]["RSI"] = _calculate_rsi(closes)
        
        elif ind_upper == "BOLL":
            result["indicators"]["BOLL"] = _calculate_boll(closes)
    
    # 返回最近一天的指标值（用于展示）
    latest = {}
    for key, value in result["indicators"].items():
        if isinstance(value, dict):
            # 复合指标如 MACD、KDJ
            latest[key] = {}
            for sub_key, sub_value in value.items():
                if sub_value and sub_value[-1] is not None:
                    latest[key][sub_key] = round(sub_value[-1], 2)
        elif isinstance(value, list) and value and value[-1] is not None:
            latest[key] = round(value[-1], 2)
    
    result["latest"] = latest
    
    return result


async def get_stock_with_indicators(
    symbol: str,
    market: str = "A",
    days: int = 60,
    indicators: list[str] = None
) -> dict:
    """
    获取股票数据并计算技术指标
    
    Args:
        symbol: 股票代码
        market: 市场类型
        days: 历史天数
        indicators: 指标列表
    
    Returns:
        带技术指标的股票数据
    """
    from .quote import get_stock_history
    
    # 获取历史数据
    history = await get_stock_history(symbol, market, "daily", days)
    
    if "error" in history:
        return history
    
    # 转换数据格式
    prices = []
    for item in history["data"]:
        prices.append({
            "close": item["close"],
            "high": item["high"],
            "low": item["low"],
        })
    
    # 计算指标
    indicators_result = await calculate_indicators(prices, indicators)
    
    return {
        "code": symbol,
        "market": market,
        "history": history["data"],
        "indicators": indicators_result.get("latest", {}),
        "full_indicators": indicators_result.get("indicators", {}),
    }
