"""
股票分析工具 - LLM Agent 可调用的股票/基金分析

提供以下工具:
- search_stock: 搜索股票/基金
- get_stock_quote: 获取实时行情
- get_stock_finance: 获取财务数据
- get_stock_news: 获取相关新闻
- get_technical_indicators: 获取技术指标
- analyze_stock: 综合分析股票
"""

from ..base import ToolParameter, ParameterType
from ..registry import ToolRegistry


async def tool_search_stock(keyword: str, market: str = "A") -> dict:
    """
    搜索股票/基金
    
    Args:
        keyword: 关键词（股票代码或名称）
        market: 市场类型 A=A股, HK=港股, FUND=基金
    """
    from ...modules.stock_analysis import search_stock
    
    results = await search_stock(keyword, market)
    
    if not results:
        return {
            "found": False,
            "message": f"未找到匹配的股票/基金: {keyword}",
            "tip": "请尝试使用股票代码或完整名称搜索",
        }
    
    return {
        "found": True,
        "count": len(results),
        "results": results,
    }


async def tool_get_stock_quote(symbol: str, market: str = "A") -> dict:
    """
    获取股票/基金实时行情
    
    Args:
        symbol: 股票代码或名称（如 600519 或 贵州茅台）
        market: 市场类型 A=A股, HK=港股, FUND=基金
    """
    from ...modules.stock_analysis import search_stock
    
    # 如果不是纯数字，先搜索股票代码
    actual_symbol = symbol
    if not symbol.isdigit() and market != "FUND":
        search_results = await search_stock(symbol, market)
        if search_results:
            actual_symbol = search_results[0]["code"]
        else:
            return {"error": f"未找到股票: {symbol}"}
    
    if market == "FUND":
        from ...modules.stock_analysis import get_fund_quote
        return await get_fund_quote(actual_symbol)
    else:
        from ...modules.stock_analysis import get_stock_quote
        return await get_stock_quote(actual_symbol, market)


async def tool_get_stock_finance(symbol: str, report_type: str = "summary") -> dict:
    """
    获取股票财务数据
    
    Args:
        symbol: 股票代码或名称
        report_type: 报表类型 summary=摘要, profit=利润表, balance=资产负债表, cash_flow=现金流量表
    """
    from ...modules.stock_analysis import (
        get_financial_summary,
        get_profit_statement,
        get_balance_sheet,
        get_cash_flow,
        search_stock,
    )
    
    # 如果不是纯数字，先搜索股票代码
    actual_symbol = symbol
    if not symbol.isdigit():
        search_results = await search_stock(symbol, "A")
        if search_results:
            actual_symbol = search_results[0]["code"]
        else:
            return {"error": f"未找到股票: {symbol}"}
    
    if report_type == "summary":
        return await get_financial_summary(actual_symbol)
    elif report_type == "profit":
        return await get_profit_statement(actual_symbol)
    elif report_type == "balance":
        return await get_balance_sheet(actual_symbol)
    elif report_type == "cash_flow":
        return await get_cash_flow(actual_symbol)
    else:
        return {"error": f"不支持的报表类型: {report_type}"}


async def tool_get_stock_news(keyword: str, max_results: int = 5) -> dict:
    """
    获取股票相关新闻
    
    Args:
        keyword: 股票代码或关键词
        max_results: 最大新闻数量
    """
    from ...modules.stock_analysis import get_stock_news, get_market_news
    
    # 判断是股票代码还是关键词
    if keyword.isdigit() and len(keyword) == 6:
        return await get_stock_news(keyword, max_results)
    else:
        # 尝试作为股票代码，如果失败则获取市场新闻
        result = await get_stock_news(keyword, max_results)
        if "error" in result:
            return await get_market_news(keyword, max_results)
        return result


async def tool_get_technical_indicators(
    symbol: str,
    market: str = "A",
    indicators: str = "MA,MACD,KDJ,RSI"
) -> dict:
    """
    获取股票技术指标
    
    Args:
        symbol: 股票代码或名称
        market: 市场类型 A=A股, HK=港股
        indicators: 指标列表，逗号分隔（MA,MACD,KDJ,RSI,BOLL）
    """
    from ...modules.stock_analysis import get_stock_with_indicators, search_stock
    
    # 如果不是纯数字，先搜索股票代码
    actual_symbol = symbol
    if not symbol.isdigit():
        search_results = await search_stock(symbol, market)
        if search_results:
            actual_symbol = search_results[0]["code"]
        else:
            return {"error": f"未找到股票: {symbol}"}
    
    # 解析指标列表
    indicator_list = [i.strip().upper() for i in indicators.split(",")]
    
    result = await get_stock_with_indicators(actual_symbol, market, days=60, indicators=indicator_list)
    
    if "error" in result:
        return result
    
    # 简化返回，只返回最新指标值和简要分析
    return {
        "code": actual_symbol,
        "market": market,
        "latest_price": result.get("history", [{}])[-1] if result.get("history") else {},
        "indicators": result.get("indicators", {}),
        "analysis": _interpret_indicators(result.get("indicators", {})),
    }


def _interpret_indicators(indicators: dict) -> list[str]:
    """解读技术指标"""
    analysis = []
    
    # MA 分析
    ma5 = indicators.get("MA5")
    ma10 = indicators.get("MA10")
    ma20 = indicators.get("MA20")
    if ma5 and ma10:
        if ma5 > ma10:
            analysis.append("短期均线在中期均线上方，短期趋势偏多")
        else:
            analysis.append("短期均线在中期均线下方，短期趋势偏空")
    
    # MACD 分析
    macd = indicators.get("MACD", {})
    if macd:
        dif = macd.get("dif", 0)
        dea = macd.get("dea", 0)
        if dif and dea:
            if dif > dea and dif > 0:
                analysis.append("MACD 金叉且在零轴上方，多头强势")
            elif dif > dea and dif < 0:
                analysis.append("MACD 金叉但在零轴下方，反弹信号")
            elif dif < dea and dif > 0:
                analysis.append("MACD 死叉但在零轴上方，回调信号")
            else:
                analysis.append("MACD 死叉且在零轴下方，空头强势")
    
    # KDJ 分析
    kdj = indicators.get("KDJ", {})
    if kdj:
        k = kdj.get("k", 50)
        j = kdj.get("j", 50)
        if j:
            if j > 80:
                analysis.append(f"KDJ J值={j:.1f}，处于超买区域，注意回调风险")
            elif j < 20:
                analysis.append(f"KDJ J值={j:.1f}，处于超卖区域，可能存在反弹机会")
    
    # RSI 分析
    rsi = indicators.get("RSI")
    if rsi:
        if rsi > 70:
            analysis.append(f"RSI={rsi:.1f}，超买状态")
        elif rsi < 30:
            analysis.append(f"RSI={rsi:.1f}，超卖状态")
        else:
            analysis.append(f"RSI={rsi:.1f}，处于中性区间")
    
    return analysis


async def tool_analyze_stock(
    symbol: str,
    market: str = "A",
    analysis_type: str = "full"
) -> dict:
    """
    综合分析股票
    
    汇总行情、财务、新闻、技术指标，生成全面分析报告。
    
    Args:
        symbol: 股票代码或名称（如 600519 或 贵州茅台）
        market: 市场类型 A=A股, HK=港股
        analysis_type: 分析类型 full=全面分析, quick=快速分析（仅行情和技术）
    """
    from ...modules.stock_analysis import analyze_stock_comprehensive, search_stock
    
    # 如果 symbol 不是纯数字，尝试搜索股票代码
    actual_symbol = symbol
    if not symbol.isdigit():
        # 用户传入的是股票名称，需要先搜索
        search_results = await search_stock(symbol, market)
        if search_results:
            actual_symbol = search_results[0]["code"]
        else:
            return {"error": f"未找到股票: {symbol}，请检查股票名称或使用股票代码"}
    
    include_news = analysis_type == "full"
    include_finance = analysis_type == "full"
    
    result = await analyze_stock_comprehensive(
        symbol=actual_symbol,
        market=market,
        include_news=include_news,
        include_finance=include_finance,
        include_technical=True,
    )
    
    return result


def register_stock_tools(registry: ToolRegistry) -> None:
    """注册股票分析工具"""
    
    registry.register_function(
        name="search_stock",
        description="搜索股票或基金。根据代码或名称关键词查找，返回匹配的股票/基金列表。",
        func=tool_search_stock,
        parameters=[
            ToolParameter(
                name="keyword",
                type=ParameterType.STRING,
                description="搜索关键词（股票代码如 600519，或名称如 茅台）"
            ),
            ToolParameter(
                name="market",
                type=ParameterType.STRING,
                description="市场类型：A=A股, HK=港股, FUND=基金",
                required=False,
                enum=["A", "HK", "FUND"],
            ),
        ],
        category="finance",
    )
    
    registry.register_function(
        name="get_stock_quote",
        description="获取股票或基金的实时行情数据，包括价格、涨跌幅、成交量、市盈率等。",
        func=tool_get_stock_quote,
        parameters=[
            ToolParameter(
                name="symbol",
                type=ParameterType.STRING,
                description="股票/基金代码（如 600519、00700、510300）"
            ),
            ToolParameter(
                name="market",
                type=ParameterType.STRING,
                description="市场类型：A=A股, HK=港股, FUND=基金",
                required=False,
                enum=["A", "HK", "FUND"],
            ),
        ],
        category="finance",
    )
    
    registry.register_function(
        name="get_stock_finance",
        description="获取上市公司财务数据，包括利润表、资产负债表、现金流量表等。用于基本面分析。",
        func=tool_get_stock_finance,
        parameters=[
            ToolParameter(
                name="symbol",
                type=ParameterType.STRING,
                description="股票代码（如 600519）"
            ),
            ToolParameter(
                name="report_type",
                type=ParameterType.STRING,
                description="报表类型：summary=财务摘要, profit=利润表, balance=资产负债表, cash_flow=现金流量表",
                required=False,
                enum=["summary", "profit", "balance", "cash_flow"],
            ),
        ],
        category="finance",
    )
    
    registry.register_function(
        name="get_stock_news",
        description="获取股票相关的新闻资讯。用于了解公司动态和市场舆情。",
        func=tool_get_stock_news,
        parameters=[
            ToolParameter(
                name="keyword",
                type=ParameterType.STRING,
                description="股票代码或关键词"
            ),
            ToolParameter(
                name="max_results",
                type=ParameterType.INTEGER,
                description="返回新闻数量（1-20）",
                required=False,
            ),
        ],
        category="finance",
    )
    
    registry.register_function(
        name="get_technical_indicators",
        description="获取股票技术分析指标，如均线(MA)、MACD、KDJ、RSI、布林带(BOLL)等。用于技术面分析。",
        func=tool_get_technical_indicators,
        parameters=[
            ToolParameter(
                name="symbol",
                type=ParameterType.STRING,
                description="股票代码"
            ),
            ToolParameter(
                name="market",
                type=ParameterType.STRING,
                description="市场类型：A=A股, HK=港股",
                required=False,
                enum=["A", "HK"],
            ),
            ToolParameter(
                name="indicators",
                type=ParameterType.STRING,
                description="需要的指标，逗号分隔（如 MA,MACD,KDJ,RSI,BOLL）",
                required=False,
            ),
        ],
        category="finance",
    )
    
    registry.register_function(
        name="analyze_stock",
        description="综合分析股票，汇总实时行情、财务数据、新闻舆情、技术指标，生成全面分析报告。适合快速了解一只股票的整体情况。",
        func=tool_analyze_stock,
        parameters=[
            ToolParameter(
                name="symbol",
                type=ParameterType.STRING,
                description="股票代码（如 600519）"
            ),
            ToolParameter(
                name="market",
                type=ParameterType.STRING,
                description="市场类型：A=A股, HK=港股",
                required=False,
                enum=["A", "HK"],
            ),
            ToolParameter(
                name="analysis_type",
                type=ParameterType.STRING,
                description="分析类型：full=全面分析（含新闻财务）, quick=快速分析（仅行情技术）",
                required=False,
                enum=["full", "quick"],
            ),
        ],
        category="finance",
    )
