"""
财务数据模块

提供上市公司财务报表和估值数据
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_financial_summary(symbol: str) -> dict:
    """
    获取财务摘要（核心指标）
    
    Args:
        symbol: 股票代码
    
    Returns:
        财务摘要数据
    """
    import akshare as ak
    
    def _get_summary():
        try:
            result = {
                "code": symbol,
            }
            
            # 获取个股基本信息
            try:
                info_df = ak.stock_individual_info_em(symbol=symbol)
                if info_df is not None and not info_df.empty:
                    info = {}
                    for _, row in info_df.iterrows():
                        info[row["item"]] = row["value"]
                    
                    result["name"] = info.get("股票简称", "")
                    result["industry"] = info.get("行业", "")
                    result["total_market_cap"] = info.get("总市值", 0)
                    result["float_market_cap"] = info.get("流通市值", 0)
                    result["latest_price"] = info.get("最新", 0)
            except Exception as e:
                logger.warning(f"获取基本信息失败: {e}")
            
            # 获取详细财务指标（使用 stock_financial_abstract）
            try:
                fin_df = ak.stock_financial_abstract(symbol=symbol)
                if fin_df is not None and not fin_df.empty:
                    # 获取最新一期数据（第一个日期列）
                    date_cols = [c for c in fin_df.columns if c not in ('选项', '指标')]
                    if date_cols:
                        latest_date = date_cols[0]
                        result["report_date"] = latest_date
                        
                        # 提取关键指标
                        for _, row in fin_df.iterrows():
                            indicator = row["指标"]
                            value = row[latest_date]
                            
                            # 转换数值
                            try:
                                if value and value != '--':
                                    value = float(value)
                                else:
                                    value = None
                            except (ValueError, TypeError):
                                value = None
                            
                            # 映射关键指标
                            if indicator == "归母净利润":
                                result["net_profit"] = value
                            elif indicator == "营业总收入":
                                result["revenue"] = value
                            elif indicator == "基本每股收益":
                                result["eps"] = value
                            elif indicator == "每股净资产":
                                result["bps"] = value
                            elif indicator == "净资产收益率(ROE)":
                                result["roe"] = value
                            elif indicator == "毛利率":
                                result["gross_margin"] = value
                            elif indicator == "销售净利率":
                                result["net_margin"] = value
                            elif indicator == "资产负债率":
                                result["debt_ratio"] = value
                            elif indicator == "营业总收入增长率":
                                result["revenue_growth"] = value
                            elif indicator == "归属母公司净利润增长率":
                                result["profit_growth"] = value
                            elif indicator == "经营现金流量净额":
                                result["operating_cash_flow"] = value
                            elif indicator == "流动比率":
                                result["current_ratio"] = value
                            elif indicator == "速动比率":
                                result["quick_ratio"] = value
            except Exception as e:
                logger.warning(f"获取财务指标失败: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"获取财务摘要失败: {e}")
            return {"error": f"获取财务摘要失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_summary)


async def get_profit_statement(symbol: str, periods: int = 4) -> dict:
    """
    获取利润表
    
    Args:
        symbol: 股票代码
        periods: 获取期数（季报）
    
    Returns:
        利润表数据
    """
    import akshare as ak
    
    def _get_profit():
        try:
            df = ak.stock_profit_sheet_by_report_em(symbol=symbol)
            if df is None or df.empty:
                return {"error": f"未找到利润表: {symbol}"}
            
            # 取最近几期
            df = df.head(periods)
            
            reports = []
            for _, row in df.iterrows():
                report = {
                    "report_date": str(row.get("REPORT_DATE_NAME", "")),
                    "revenue": row.get("TOTAL_OPERATE_INCOME", 0),  # 营业总收入
                    "operating_profit": row.get("OPERATE_PROFIT", 0),  # 营业利润
                    "total_profit": row.get("TOTAL_PROFIT", 0),  # 利润总额
                    "net_profit": row.get("NETPROFIT", 0),  # 净利润
                    "net_profit_attr": row.get("PARENT_NETPROFIT", 0),  # 归母净利润
                    "eps": row.get("BASIC_EPS", 0),  # 基本每股收益
                }
                reports.append(report)
            
            return {
                "code": symbol,
                "type": "profit_statement",
                "periods": len(reports),
                "data": reports,
            }
            
        except Exception as e:
            logger.error(f"获取利润表失败: {e}")
            return {"error": f"获取利润表失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_profit)


async def get_balance_sheet(symbol: str, periods: int = 4) -> dict:
    """
    获取资产负债表
    
    Args:
        symbol: 股票代码
        periods: 获取期数
    
    Returns:
        资产负债表数据
    """
    import akshare as ak
    
    def _get_balance():
        try:
            df = ak.stock_balance_sheet_by_report_em(symbol=symbol)
            if df is None or df.empty:
                return {"error": f"未找到资产负债表: {symbol}"}
            
            df = df.head(periods)
            
            reports = []
            for _, row in df.iterrows():
                report = {
                    "report_date": str(row.get("REPORT_DATE_NAME", "")),
                    "total_assets": row.get("TOTAL_ASSETS", 0),  # 总资产
                    "total_liabilities": row.get("TOTAL_LIABILITIES", 0),  # 总负债
                    "total_equity": row.get("TOTAL_EQUITY", 0),  # 股东权益
                    "cash": row.get("MONETARYFUNDS", 0),  # 货币资金
                    "inventory": row.get("INVENTORY", 0),  # 存货
                    "accounts_receivable": row.get("ACCOUNTS_RECE", 0),  # 应收账款
                    "fixed_assets": row.get("FIXED_ASSET", 0),  # 固定资产
                }
                reports.append(report)
            
            return {
                "code": symbol,
                "type": "balance_sheet",
                "periods": len(reports),
                "data": reports,
            }
            
        except Exception as e:
            logger.error(f"获取资产负债表失败: {e}")
            return {"error": f"获取资产负债表失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_balance)


async def get_cash_flow(symbol: str, periods: int = 4) -> dict:
    """
    获取现金流量表
    
    Args:
        symbol: 股票代码
        periods: 获取期数
    
    Returns:
        现金流量表数据
    """
    import akshare as ak
    
    def _get_cash_flow():
        try:
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
            if df is None or df.empty:
                return {"error": f"未找到现金流量表: {symbol}"}
            
            df = df.head(periods)
            
            reports = []
            for _, row in df.iterrows():
                report = {
                    "report_date": str(row.get("REPORT_DATE_NAME", "")),
                    "operating_cash_flow": row.get("NETCASH_OPERATE", 0),  # 经营活动现金流
                    "investing_cash_flow": row.get("NETCASH_INVEST", 0),  # 投资活动现金流
                    "financing_cash_flow": row.get("NETCASH_FINANCE", 0),  # 筹资活动现金流
                    "net_cash_flow": row.get("NETCASH_CHANGE", 0),  # 现金净增加额
                    "cash_end": row.get("CCE_END", 0),  # 期末现金余额
                }
                reports.append(report)
            
            return {
                "code": symbol,
                "type": "cash_flow",
                "periods": len(reports),
                "data": reports,
            }
            
        except Exception as e:
            logger.error(f"获取现金流量表失败: {e}")
            return {"error": f"获取现金流量表失败: {str(e)}"}
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_cash_flow)
