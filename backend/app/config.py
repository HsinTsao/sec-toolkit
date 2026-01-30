"""应用配置"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from pathlib import Path
import os

# 确定项目根目录（支持本地开发和 Docker 部署）
# 本地开发: backend/app/config.py -> 项目根目录是 ../../
# Docker: /app/app/config.py -> 数据目录是 /app/data
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent  # backend 目录
_project_root = _backend_dir.parent  # 项目根目录

# 检测运行环境
if os.path.exists("/app/data"):
    # Docker 环境
    _data_dir = Path("/app/data")
    _env_file = Path("/app/.env") if Path("/app/.env").exists() else None
else:
    # 本地开发环境
    _data_dir = _project_root / "data"
    _env_file = _project_root / ".env" if (_project_root / ".env").exists() else None


class Settings(BaseSettings):
    """应用设置"""
    # 应用
    APP_NAME: str = "Security Toolkit"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 数据库（默认使用项目根目录的 data 文件夹）
    DATABASE_URL: str = f"sqlite+aiosqlite:///{_data_dir}/toolkit.db"
    
    # JWT
    JWT_SECRET_KEY: str = "change-this-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 缓存
    CACHE_TTL: int = 300  # 5 分钟
    CACHE_MAX_SIZE: int = 500
    
    # CORS（支持默认 80/443 端口和开发端口）
    CORS_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:5173",
        "https://localhost",
        "https://localhost:443",
        "https://localhost:5173",
    ]
    
    # SSL/HTTPS 配置
    SSL_ENABLED: bool = False
    SSL_KEYFILE: Optional[str] = None  # SSL 私钥路径
    SSL_CERTFILE: Optional[str] = None  # SSL 证书路径
    
    # 默认 LLM 配置（可选，用户未配置时使用）
    DEFAULT_LLM_PROVIDER: Optional[str] = None  # 如: qwen, deepseek, openai, groq
    DEFAULT_LLM_API_KEY: Optional[str] = None  # 默认 API Key
    DEFAULT_LLM_BASE_URL: Optional[str] = None  # 自定义 API 地址（可选）
    DEFAULT_LLM_MODEL: Optional[str] = None  # 默认模型名称
    
    # 双 LLM 架构配置（省 Token 模式）
    # 如果不配置，则使用默认模型
    INTENT_LLM_MODEL: Optional[str] = None  # Intent LLM 模型（推荐用小模型如 qwen-turbo）
    SUMMARY_LLM_MODEL: Optional[str] = None  # Summary LLM 模型
    DUAL_LLM_ENABLED: bool = True  # 是否启用双 LLM 模式
    
    class Config:
        env_file = str(_env_file) if _env_file else ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
