"""
股票/基金分析模块

提供 A股、港股、基金的数据获取和分析功能：
- 行情数据（实时/历史）
- 财务数据（财报/估值）
- 新闻舆情
- 技术指标（MA/MACD/KDJ 等）
- 综合分析

数据源：AKShare（开源免费）
"""

from .quote import (
    get_stock_quote,
    get_stock_history,
    get_fund_quote,
    search_stock,
)
from .finance import (
    get_financial_summary,
    get_profit_statement,
    get_balance_sheet,
    get_cash_flow,
)
from .news import (
    get_stock_news,
    get_market_news,
)
from .technical import (
    calculate_indicators,
    get_stock_with_indicators,
)
from .analyzer import (
    analyze_stock_comprehensive,
)

__all__ = [
    # 行情
    "get_stock_quote",
    "get_stock_history",
    "get_fund_quote",
    "search_stock",
    # 财务
    "get_financial_summary",
    "get_profit_statement",
    "get_balance_sheet",
    "get_cash_flow",
    # 新闻
    "get_stock_news",
    "get_market_news",
    # 技术指标
    "calculate_indicators",
    "get_stock_with_indicators",
    # 综合分析
    "analyze_stock_comprehensive",
]
