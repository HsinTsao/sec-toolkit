"""
异常类单元测试
"""

import pytest
from app.core.exceptions import (
    AppException,
    BadRequestError,
    UnauthorizedError,
    ForbiddenError,
    NotFoundError,
    ConflictError,
    ValidationError,
    InternalServerError,
)


class TestAppException:
    """AppException 基类测试"""
    
    def test_default_values(self):
        """测试默认值"""
        exc = AppException()
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"
        assert exc.message == "服务器内部错误"
        assert exc.detail == {}
    
    def test_custom_message(self):
        """测试自定义消息"""
        exc = AppException("自定义错误消息")
        assert exc.message == "自定义错误消息"
    
    def test_custom_detail(self):
        """测试自定义详情"""
        exc = AppException("错误", detail={"field": "value"})
        assert exc.detail == {"field": "value"}
    
    def test_custom_error_code(self):
        """测试自定义错误码"""
        exc = AppException("错误", error_code="CUSTOM_ERROR")
        assert exc.error_code == "CUSTOM_ERROR"
    
    def test_to_dict(self):
        """测试转换为字典"""
        exc = AppException("测试错误", detail={"key": "value"})
        result = exc.to_dict()
        
        assert result["error"] is True
        assert result["code"] == "INTERNAL_ERROR"
        assert result["message"] == "测试错误"
        assert result["detail"] == {"key": "value"}
    
    def test_to_dict_without_detail(self):
        """测试转换为字典（无详情）"""
        exc = AppException("测试错误")
        result = exc.to_dict()
        
        assert "detail" not in result


class TestBadRequestError:
    """BadRequestError 测试"""
    
    def test_default_values(self):
        exc = BadRequestError()
        assert exc.status_code == 400
        assert exc.error_code == "BAD_REQUEST"
        assert exc.message == "请求参数错误"


class TestUnauthorizedError:
    """UnauthorizedError 测试"""
    
    def test_default_values(self):
        exc = UnauthorizedError()
        assert exc.status_code == 401
        assert exc.error_code == "UNAUTHORIZED"


class TestForbiddenError:
    """ForbiddenError 测试"""
    
    def test_default_values(self):
        exc = ForbiddenError()
        assert exc.status_code == 403
        assert exc.error_code == "FORBIDDEN"


class TestNotFoundError:
    """NotFoundError 测试"""
    
    def test_default_values(self):
        exc = NotFoundError()
        assert exc.status_code == 404
        assert exc.error_code == "NOT_FOUND"
    
    def test_with_resource_info(self):
        """测试带资源信息"""
        exc = NotFoundError("用户不存在", detail={"user_id": 123})
        assert exc.message == "用户不存在"
        assert exc.detail["user_id"] == 123


class TestConflictError:
    """ConflictError 测试"""
    
    def test_default_values(self):
        exc = ConflictError()
        assert exc.status_code == 409
        assert exc.error_code == "CONFLICT"


class TestValidationError:
    """ValidationError 测试"""
    
    def test_default_values(self):
        exc = ValidationError()
        assert exc.status_code == 422
        assert exc.error_code == "VALIDATION_ERROR"


class TestInternalServerError:
    """InternalServerError 测试"""
    
    def test_default_values(self):
        exc = InternalServerError()
        assert exc.status_code == 500
        assert exc.error_code == "INTERNAL_ERROR"
