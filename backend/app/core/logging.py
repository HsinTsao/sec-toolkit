"""
日志工具模块

提供便捷的日志记录功能，支持请求 ID 追踪
"""

import logging
from typing import Optional
from functools import wraps
import time

from .middleware import get_request_id


class AppLogger:
    """
    应用日志记录器
    
    自动附加请求 ID，便于追踪
    
    使用示例:
        from app.core.logging import get_logger
        
        logger = get_logger(__name__)
        logger.info("用户登录成功", user_id=123)
        logger.error("数据库查询失败", error=str(e))
    """
    
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
    
    def _format_message(self, message: str, **kwargs) -> str:
        """格式化日志消息，附加请求 ID 和额外参数"""
        request_id = get_request_id()
        prefix = f"[{request_id}] " if request_id else ""
        
        if kwargs:
            extras = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{prefix}{message} | {extras}"
        return f"{prefix}{message}"
    
    def debug(self, message: str, **kwargs) -> None:
        self._logger.debug(self._format_message(message, **kwargs))
    
    def info(self, message: str, **kwargs) -> None:
        self._logger.info(self._format_message(message, **kwargs))
    
    def warning(self, message: str, **kwargs) -> None:
        self._logger.warning(self._format_message(message, **kwargs))
    
    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        self._logger.error(self._format_message(message, **kwargs), exc_info=exc_info)
    
    def critical(self, message: str, exc_info: bool = True, **kwargs) -> None:
        self._logger.critical(self._format_message(message, **kwargs), exc_info=exc_info)
    
    def exception(self, message: str, **kwargs) -> None:
        """记录异常信息（自动包含堆栈）"""
        self._logger.exception(self._format_message(message, **kwargs))


def get_logger(name: str) -> AppLogger:
    """获取日志记录器"""
    return AppLogger(name)


def log_execution_time(logger: Optional[AppLogger] = None, level: str = "info"):
    """
    装饰器：记录函数执行时间
    
    使用示例:
        @log_execution_time()
        async def slow_function():
            ...
    """
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                getattr(logger, level)(
                    f"{func.__name__} 执行完成",
                    duration_ms=f"{duration:.2f}"
                )
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(
                    f"{func.__name__} 执行失败",
                    duration_ms=f"{duration:.2f}",
                    error=str(e)
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                getattr(logger, level)(
                    f"{func.__name__} 执行完成",
                    duration_ms=f"{duration:.2f}"
                )
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(
                    f"{func.__name__} 执行失败",
                    duration_ms=f"{duration:.2f}",
                    error=str(e)
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
