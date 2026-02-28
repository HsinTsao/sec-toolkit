"""
统一异常定义

提供应用级别的异常类，用于替代直接抛出 HTTPException。
优点：
1. 更清晰的业务语义
2. 统一的错误响应格式
3. 便于日志记录和错误追踪
4. 支持国际化错误消息

使用示例:
    from app.core import NotFoundError, ValidationError
    
    # 抛出 404 错误
    raise NotFoundError("用户不存在", detail={"user_id": user_id})
    
    # 抛出验证错误
    raise ValidationError("邮箱格式不正确")
"""

from typing import Any, Optional, Dict


class AppException(Exception):
    """
    应用基础异常类
    
    所有业务异常都应该继承此类
    """
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "服务器内部错误"
    
    def __init__(
        self,
        message: Optional[str] = None,
        *,
        detail: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        self.message = message or self.__class__.message
        self.detail = detail or {}
        if error_code:
            self.error_code = error_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为响应字典"""
        result = {
            "error": True,
            "code": self.error_code,
            "message": self.message,
        }
        if self.detail:
            result["detail"] = self.detail
        return result


class BadRequestError(AppException):
    """400 错误请求"""
    status_code = 400
    error_code = "BAD_REQUEST"
    message = "请求参数错误"


class UnauthorizedError(AppException):
    """401 未授权"""
    status_code = 401
    error_code = "UNAUTHORIZED"
    message = "未授权访问"


class ForbiddenError(AppException):
    """403 禁止访问"""
    status_code = 403
    error_code = "FORBIDDEN"
    message = "禁止访问"


class NotFoundError(AppException):
    """404 资源不存在"""
    status_code = 404
    error_code = "NOT_FOUND"
    message = "资源不存在"


class ConflictError(AppException):
    """409 资源冲突"""
    status_code = 409
    error_code = "CONFLICT"
    message = "资源冲突"


class ValidationError(AppException):
    """422 验证错误"""
    status_code = 422
    error_code = "VALIDATION_ERROR"
    message = "数据验证失败"


class InternalServerError(AppException):
    """500 服务器内部错误"""
    status_code = 500
    error_code = "INTERNAL_ERROR"
    message = "服务器内部错误"


class RateLimitError(AppException):
    """429 请求过于频繁"""
    status_code = 429
    error_code = "RATE_LIMIT"
    message = "请求过于频繁，请稍后再试"


class ServiceUnavailableError(AppException):
    """503 服务不可用"""
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"
    message = "服务暂时不可用"
