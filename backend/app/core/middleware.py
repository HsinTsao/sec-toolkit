"""
中间件模块

提供：
1. 全局异常处理
2. 请求日志记录
3. 请求 ID 追踪
"""

import time
import uuid
import logging
import traceback
from typing import Callable
from contextvars import ContextVar

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import ValidationError as PydanticValidationError

from .exceptions import AppException

# 请求 ID 上下文变量，用于日志追踪
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

logger = logging.getLogger("app.middleware")


def get_request_id() -> str:
    """获取当前请求 ID"""
    return request_id_var.get()


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    请求上下文中间件
    
    为每个请求生成唯一 ID，记录请求日志
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 生成请求 ID（优先使用客户端传递的）
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        request_id_var.set(request_id)
        
        # 记录请求开始
        start_time = time.time()
        method = request.method
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""
        client_ip = request.client.host if request.client else "unknown"
        
        # 从代理头获取真实 IP
        if forwarded := request.headers.get("X-Forwarded-For"):
            client_ip = forwarded.split(",")[0].strip()
        elif real_ip := request.headers.get("X-Real-IP"):
            client_ip = real_ip
        
        logger.info(
            f"[{request_id}] --> {method} {path}"
            f"{'?' + query if query else ''} | IP: {client_ip}"
        )
        
        # 处理请求
        try:
            response = await call_next(request)
        except Exception as e:
            # 未捕获的异常
            logger.error(
                f"[{request_id}] 未捕获异常: {type(e).__name__}: {str(e)}\n"
                f"{traceback.format_exc()}"
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": True,
                    "code": "INTERNAL_ERROR",
                    "message": "服务器内部错误",
                    "request_id": request_id,
                }
            )
        
        # 计算耗时
        duration_ms = (time.time() - start_time) * 1000
        
        # 添加响应头
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
        
        # 记录响应
        status_code = response.status_code
        log_level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR
        logger.log(
            log_level,
            f"[{request_id}] <-- {status_code} | {duration_ms:.2f}ms"
        )
        
        return response


def setup_exception_handlers(app: FastAPI) -> None:
    """
    设置全局异常处理器
    
    处理：
    1. AppException - 业务异常
    2. RequestValidationError - 请求参数验证错误
    3. Exception - 未知异常
    """
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """处理业务异常"""
        request_id = get_request_id()
        
        logger.warning(
            f"[{request_id}] 业务异常: {exc.error_code} - {exc.message}"
            f"{f' | detail: {exc.detail}' if exc.detail else ''}"
        )
        
        content = exc.to_dict()
        content["request_id"] = request_id
        
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理请求参数验证错误"""
        request_id = get_request_id()
        
        # 格式化错误信息
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
                "type": error["type"],
            })
        
        logger.warning(f"[{request_id}] 参数验证失败: {errors}")
        
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "code": "VALIDATION_ERROR",
                "message": "请求参数验证失败",
                "detail": {"errors": errors},
                "request_id": request_id,
            },
        )
    
    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(
        request: Request, exc: PydanticValidationError
    ) -> JSONResponse:
        """处理 Pydantic 验证错误"""
        request_id = get_request_id()
        
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
            })
        
        logger.warning(f"[{request_id}] Pydantic 验证失败: {errors}")
        
        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "code": "VALIDATION_ERROR",
                "message": "数据验证失败",
                "detail": {"errors": errors},
                "request_id": request_id,
            },
        )
    
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """处理未知异常"""
        request_id = get_request_id()
        
        logger.error(
            f"[{request_id}] 未知异常: {type(exc).__name__}: {str(exc)}\n"
            f"{traceback.format_exc()}"
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误",
                "request_id": request_id,
            },
        )
