"""应用配置"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os


class Settings(BaseSettings):
    """应用设置"""
    # 应用
    APP_NAME: str = "Security Toolkit"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 数据库
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/toolkit.db"
    
    # JWT
    JWT_SECRET_KEY: str = "change-this-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 小时
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # 缓存
    CACHE_TTL: int = 300  # 5 分钟
    CACHE_MAX_SIZE: int = 500
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://localhost:5173",
        "https://localhost:3000",
        "https://localhost",
        "http://localhost",
    ]
    
    # SSL/HTTPS 配置
    SSL_ENABLED: bool = False
    SSL_KEYFILE: Optional[str] = None  # SSL 私钥路径
    SSL_CERTFILE: Optional[str] = None  # SSL 证书路径
    
    # 默认 LLM 配置（可选，用户未配置时使用）
    DEFAULT_LLM_PROVIDER: Optional[str] = None  # 如: deepseek, openai, groq
    DEFAULT_LLM_API_KEY: Optional[str] = None  # 默认 API Key
    DEFAULT_LLM_BASE_URL: Optional[str] = None  # 自定义 API 地址（可选）
    DEFAULT_LLM_MODEL: Optional[str] = None  # 默认模型名称
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


settings = get_settings()
