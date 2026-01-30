"""FastAPI 应用入口"""
import logging
import logging.config
import os

# 日志配置
# 使用 FileHandler 直接写入文件，避免 uvicorn --reload 子进程 stderr 重定向问题
LOG_FILE = os.environ.get("LOG_FILE", "/code/sec-toolkit/data/backend.log")

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(levelname)s:%(name)s:%(message)s"}
    },
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "formatter": "standard",
            "filename": LOG_FILE,
            "mode": "a",
            "encoding": "utf-8"
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["file"]
    },
    "loggers": {
        "app": {"level": "INFO"},
        "httpx": {"level": "INFO"},
    }
})

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import init_db, get_db
from .api import api_router
from .api.v1.callback import handle_callback


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    await init_db()
    
    # 注册 Agent 工具
    from .agent.tools import register_builtin_tools
    register_builtin_tools()
    print("🛠️ Agent 工具注册完成")
    
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动成功")
    yield
    # 关闭时
    print("👋 正在清理资源...")
    
    # 关闭 LLM HTTP 连接池
    try:
        from .api.v1.llm import close_llm_http_client
        await close_llm_http_client()
    except Exception as e:
        print(f"⚠️ 关闭 LLM HTTP 客户端失败: {e}")
    
    # 关闭 DualLLM 共享客户端
    try:
        from .agent.dual_llm import cleanup_shared_clients
        await cleanup_shared_clients()
    except Exception as e:
        print(f"⚠️ 关闭 DualLLM 客户端失败: {e}")
    
    # 关闭 Proxy 模块客户端
    try:
        from .modules.proxy import proxy_manager
        if proxy_manager._client and not proxy_manager._client.is_closed:
            await proxy_manager._client.aclose()
            print("✅ Proxy HTTP 客户端已关闭")
    except Exception as e:
        print(f"⚠️ 关闭 Proxy 客户端失败: {e}")
    
    print("👋 应用关闭完成")


# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="个人安全工具库 API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(api_router, prefix="/api")


# 健康检查
@app.get("/health", tags=["系统"], summary="健康检查")
async def health_check():
    """检查服务运行状态"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# 根路由
@app.get("/", tags=["系统"], summary="欢迎页")
async def root():
    """返回 API 基本信息"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/api/docs"
    }


# ==================== 回调接收端点（公开，无需认证）====================
@app.api_route("/c/{token}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
               tags=["回调服务器"], summary="接收回调请求")
async def callback_handler(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    """
    接收外部系统的回调请求（根路径）
    
    - 支持所有 HTTP 方法
    - 自动记录请求详情（Headers、Body、IP 等）
    - 无需认证，公开访问
    """
    return await handle_callback(request, token, "", db)


@app.api_route("/c/{token}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
               tags=["回调服务器"], summary="接收回调请求（带路径）")
async def callback_handler_with_path(request: Request, token: str, path: str, db: AsyncSession = Depends(get_db)):
    """
    接收外部系统的回调请求（带自定义路径）
    
    - 支持所有 HTTP 方法
    - path 参数会被记录，可用于区分不同的回调来源
    - 无需认证，公开访问
    """
    return await handle_callback(request, token, path, db)

