"""
综合分析器模块

汇总各类数据，生成综合分析报告供 LLM 分析
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# 免责声明
DISCLAIMER = """
⚠️ 免责声明：以上分析仅供参考，不构成投资建议。股市有风险，投资需谨慎。
本分析基于公开数据和技术指标，不保证准确性和完整性。
投资决策请结合自身情况，咨询专业投资顾问。
"""


async def analyze_stock_comprehensive(
    symbol: str,
    market: str = "A",
    include_news: bool = True,
    include_finance: bool = True,
    include_technical: bool = True,
) -> dict:
    """
    综合分析股票
    
    汇总行情、财务、新闻、技术指标等数据，
    生成结构化分析报告供 LLM 进行解读。
    
    Args:
        symbol: 股票代码
        market: 市场类型 A=A股, HK=港股
        include_news: 是否包含新闻
        include_finance: 是否包含财务数据
        include_technical: 是否包含技术指标
    
    Returns:
        综合分析数据
    """
    from .quote import get_stock_quote, get_stock_history
    from .finance import get_financial_summary
    from .news import get_stock_news
    from .technical import calculate_indicators
    
    result = {
        "code": symbol,
        "market": market,
        "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "disclaimer": DISCLAIMER,
    }
    
    # 并发获取数据
    tasks = [get_stock_quote(symbol, market)]
    
    if include_technical:
        tasks.append(get_stock_history(symbol, market, "daily", 60))
    
    if include_finance and market == "A":
        tasks.append(get_financial_summary(symbol))
    
    if include_news and market == "A":
        tasks.append(get_stock_news(symbol, max_count=5))
    
    # 执行所有任务
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理行情数据
    quote_result = results[0]
    if isinstance(quote_result, Exception):
        result["quote"] = {"error": str(quote_result)}
    elif "error" in quote_result:
        result["quote"] = quote_result
    else:
        result["quote"] = quote_result
        result["name"] = quote_result.get("name", "")
    
    task_idx = 1
    
    # 处理技术指标
    if include_technical:
        history_result = results[task_idx]
        task_idx += 1
        
        if isinstance(history_result, Exception):
            result["technical"] = {"error": str(history_result)}
        elif "error" in history_result:
            result["technical"] = history_result
        else:
            # 计算技术指标
            prices = [
                {"close": d["close"], "high": d["high"], "low": d["low"]}
                for d in history_result.get("data", [])
            ]
            if prices:
                indicators = await calculate_indicators(prices, ["MA", "MACD", "KDJ", "RSI", "BOLL"])
                result["technical"] = {
                    "latest_prices": history_result["data"][-5:] if history_result.get("data") else [],
                    "indicators": indicators.get("latest", {}),
                    "trend": _analyze_trend(history_result.get("data", []), indicators),
                }
    
    # 处理财务数据
    if include_finance and market == "A":
        finance_result = results[task_idx]
        task_idx += 1
        
        if isinstance(finance_result, Exception):
            result["finance"] = {"error": str(finance_result)}
        else:
            result["finance"] = finance_result
    
    # 处理新闻数据
    if include_news and market == "A":
        news_result = results[task_idx]
        task_idx += 1
        
        if isinstance(news_result, Exception):
            result["news"] = {"error": str(news_result)}
        else:
            result["news"] = news_result
    
    # 生成分析摘要
    result["summary"] = _generate_summary(result)
    
    # 生成投资建议
    result["suggestion"] = _generate_investment_suggestion(result)
    
    return result


def _analyze_trend(history: list, indicators: dict) -> dict:
    """分析趋势"""
    if not history or len(history) < 5:
        return {"status": "数据不足"}
    
    trend = {}
    
    # 最近 5 日涨跌
    recent_5 = history[-5:]
    trend["recent_5_days"] = {
        "start_price": recent_5[0]["close"],
        "end_price": recent_5[-1]["close"],
        "change_percent": round((recent_5[-1]["close"] - recent_5[0]["close"]) / recent_5[0]["close"] * 100, 2),
    }
    
    # 最近 20 日涨跌
    if len(history) >= 20:
        recent_20 = history[-20:]
        trend["recent_20_days"] = {
            "start_price": recent_20[0]["close"],
            "end_price": recent_20[-1]["close"],
            "change_percent": round((recent_20[-1]["close"] - recent_20[0]["close"]) / recent_20[0]["close"] * 100, 2),
        }
    
    # 均线趋势分析
    latest = indicators.get("latest", {})
    current_price = history[-1]["close"]
    
    ma_analysis = []
    for ma_name in ["MA5", "MA10", "MA20", "MA60"]:
        ma_value = latest.get(ma_name)
        if ma_value:
            position = "上方" if current_price > ma_value else "下方"
            ma_analysis.append(f"股价在{ma_name}{position}")
    
    trend["ma_analysis"] = ma_analysis
    
    # MACD 分析
    macd = latest.get("MACD", {})
    if macd:
        dif = macd.get("dif", 0)
        dea = macd.get("dea", 0)
        if dif and dea:
            if dif > dea:
                trend["macd_signal"] = "金叉（多头）"
            else:
                trend["macd_signal"] = "死叉（空头）"
    
    # KDJ 分析
    kdj = latest.get("KDJ", {})
    if kdj:
        k = kdj.get("k", 50)
        d = kdj.get("d", 50)
        j = kdj.get("j", 50)
        if k and d and j:
            if j > 80:
                trend["kdj_signal"] = "超买区域"
            elif j < 20:
                trend["kdj_signal"] = "超卖区域"
            elif k > d:
                trend["kdj_signal"] = "金叉（偏多）"
            else:
                trend["kdj_signal"] = "死叉（偏空）"
    
    # RSI 分析
    rsi = latest.get("RSI")
    if rsi:
        if rsi > 70:
            trend["rsi_signal"] = f"RSI={rsi:.1f}，超买"
        elif rsi < 30:
            trend["rsi_signal"] = f"RSI={rsi:.1f}，超卖"
        else:
            trend["rsi_signal"] = f"RSI={rsi:.1f}，中性"
    
    return trend


def _generate_summary(data: dict) -> str:
    """生成分析摘要"""
    parts = []
    
    # 基本信息
    quote = data.get("quote", {})
    if quote and "error" not in quote:
        name = quote.get("name", data.get("code", ""))
        price = quote.get("price", 0)
        change = quote.get("change_percent", 0)
        direction = "↑" if change > 0 else "↓" if change < 0 else "→"
        parts.append(f"【{name}】当前价格 {price} 元，涨跌幅 {change:+.2f}% {direction}")
    
    # 技术面
    technical = data.get("technical", {})
    trend = technical.get("trend", {})
    if trend:
        signals = []
        if "macd_signal" in trend:
            signals.append(f"MACD {trend['macd_signal']}")
        if "kdj_signal" in trend:
            signals.append(f"KDJ {trend['kdj_signal']}")
        if "rsi_signal" in trend:
            signals.append(trend["rsi_signal"])
        if signals:
            parts.append(f"技术信号：{', '.join(signals)}")
    
    # 财务面
    finance = data.get("finance", {})
    if finance and "error" not in finance:
        finance_items = []
        if finance.get("roe"):
            finance_items.append(f"ROE {finance['roe']:.2f}%")
        if finance.get("gross_margin"):
            finance_items.append(f"毛利率 {finance['gross_margin']:.2f}%")
        if finance.get("profit_growth"):
            finance_items.append(f"利润增长 {finance['profit_growth']:+.2f}%")
        if finance_items:
            parts.append(f"财务指标：{', '.join(finance_items)}")
    
    # 新闻概要
    news = data.get("news", {})
    news_list = news.get("news", [])
    if news_list:
        parts.append(f"近期新闻 {len(news_list)} 条")
    
    return "\n".join(parts) if parts else "数据获取中..."


def _generate_investment_suggestion(data: dict) -> dict:
    """
    生成投资建议（仅供参考）
    
    基于技术指标和财务数据进行综合判断
    """
    suggestion = {
        "overall": "观望",  # 默认观望
        "technical_score": 50,  # 技术面得分 0-100
        "fundamental_score": 50,  # 基本面得分 0-100
        "risk_level": "中",  # 风险等级
        "reasons": [],  # 判断理由
        "risks": [],  # 风险提示
    }
    
    # === 技术面分析 ===
    technical = data.get("technical", {})
    trend = technical.get("trend", {})
    indicators = technical.get("indicators", {})
    
    tech_score = 50
    
    # MACD 信号
    macd = indicators.get("MACD", {})
    if macd:
        dif = macd.get("dif", 0)
        dea = macd.get("dea", 0)
        if dif and dea:
            if dif > dea and dif > 0:
                tech_score += 15
                suggestion["reasons"].append("MACD 金叉且在零轴上方，多头强势")
            elif dif > dea and dif < 0:
                tech_score += 5
                suggestion["reasons"].append("MACD 金叉但在零轴下方，反弹信号")
            elif dif < dea and dif > 0:
                tech_score -= 5
                suggestion["reasons"].append("MACD 死叉但在零轴上方，注意回调")
            else:
                tech_score -= 15
                suggestion["reasons"].append("MACD 死叉且在零轴下方，空头强势")
    
    # KDJ 信号
    kdj = indicators.get("KDJ", {})
    if kdj:
        j = kdj.get("j", 50)
        if j:
            if j > 80:
                tech_score -= 10
                suggestion["risks"].append("KDJ 超买，短期可能回调")
            elif j < 20:
                tech_score += 10
                suggestion["reasons"].append("KDJ 超卖，可能存在反弹机会")
    
    # RSI 信号
    rsi = indicators.get("RSI")
    if rsi:
        if rsi > 70:
            tech_score -= 10
            suggestion["risks"].append(f"RSI={rsi:.1f} 超买区域")
        elif rsi < 30:
            tech_score += 10
            suggestion["reasons"].append(f"RSI={rsi:.1f} 超卖区域")
    
    # 均线趋势
    if trend.get("recent_5_days"):
        change = trend["recent_5_days"].get("change_percent", 0)
        if change > 5:
            tech_score += 5
            suggestion["reasons"].append(f"近5日上涨 {change:.2f}%")
        elif change < -5:
            tech_score -= 5
            suggestion["risks"].append(f"近5日下跌 {abs(change):.2f}%")
    
    suggestion["technical_score"] = max(0, min(100, tech_score))
    
    # === 基本面分析 ===
    finance = data.get("finance", {})
    fund_score = 50
    
    if finance and "error" not in finance:
        # ROE（净资产收益率）
        roe = finance.get("roe")
        if roe:
            if roe > 20:
                fund_score += 15
                suggestion["reasons"].append(f"ROE {roe:.2f}% 优秀（>20%）")
            elif roe > 10:
                fund_score += 5
                suggestion["reasons"].append(f"ROE {roe:.2f}% 良好（>10%）")
            elif roe < 5:
                fund_score -= 10
                suggestion["risks"].append(f"ROE {roe:.2f}% 偏低（<5%）")
        
        # 毛利率
        gross_margin = finance.get("gross_margin")
        if gross_margin:
            if gross_margin > 50:
                fund_score += 10
                suggestion["reasons"].append(f"毛利率 {gross_margin:.2f}% 较高")
            elif gross_margin < 20:
                fund_score -= 5
                suggestion["risks"].append(f"毛利率 {gross_margin:.2f}% 偏低")
        
        # 利润增长
        profit_growth = finance.get("profit_growth")
        if profit_growth:
            if profit_growth > 20:
                fund_score += 10
                suggestion["reasons"].append(f"利润增长 {profit_growth:.2f}% 强劲")
            elif profit_growth < -10:
                fund_score -= 10
                suggestion["risks"].append(f"利润下滑 {abs(profit_growth):.2f}%")
        
        # 负债率
        debt_ratio = finance.get("debt_ratio")
        if debt_ratio:
            if debt_ratio > 70:
                fund_score -= 10
                suggestion["risks"].append(f"负债率 {debt_ratio:.2f}% 较高")
    
    suggestion["fundamental_score"] = max(0, min(100, fund_score))
    
    # === 综合评估 ===
    total_score = (suggestion["technical_score"] + suggestion["fundamental_score"]) / 2
    
    if total_score >= 70:
        suggestion["overall"] = "偏多"
        suggestion["risk_level"] = "低"
    elif total_score >= 55:
        suggestion["overall"] = "中性偏多"
        suggestion["risk_level"] = "中"
    elif total_score >= 45:
        suggestion["overall"] = "观望"
        suggestion["risk_level"] = "中"
    elif total_score >= 30:
        suggestion["overall"] = "谨慎"
        suggestion["risk_level"] = "高"
    else:
        suggestion["overall"] = "偏空"
        suggestion["risk_level"] = "高"
    
    return suggestion
