"""
Pytest 配置和 Fixtures

提供测试所需的通用配置和 fixtures
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, AsyncMock

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 设置测试环境变量
import os
os.environ["LOG_FILE"] = "/tmp/test.log"
os.environ["LOG_LEVEL"] = "DEBUG"

from app.main import app
from app.database import Base, get_db
from app.config import settings


# 测试数据库 URL（使用内存数据库）
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    创建测试数据库会话
    
    每个测试函数使用独立的内存数据库
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture(scope="function")
async def client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    创建测试 HTTP 客户端
    
    自动注入测试数据库
    """
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user() -> dict:
    """模拟用户数据"""
    return {
        "id": "test-user-id",
        "username": "testuser",
        "email": "test@example.com",
    }


@pytest.fixture
def mock_token() -> str:
    """模拟 JWT Token"""
    return "test-jwt-token"


@pytest.fixture
def auth_headers(mock_token: str) -> dict:
    """带认证的请求头"""
    return {"Authorization": f"Bearer {mock_token}"}
