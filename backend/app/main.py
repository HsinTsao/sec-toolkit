"""FastAPI 应用入口"""
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
    print("👋 应用关闭")


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
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# 根路由
@app.get("/")
async def root():
    """根路由"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/api/docs"
    }


# ==================== 回调接收端点（公开，无需认证）====================
@app.api_route("/c/{token}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def callback_handler(request: Request, token: str, db: AsyncSession = Depends(get_db)):
    """接收回调请求 - 根路径"""
    return await handle_callback(request, token, "", db)


@app.api_route("/c/{token}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def callback_handler_with_path(request: Request, token: str, path: str, db: AsyncSession = Depends(get_db)):
    """接收回调请求 - 带路径"""
    return await handle_callback(request, token, path, db)

