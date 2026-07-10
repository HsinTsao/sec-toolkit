"""FastAPI 应用入口"""
import logging
import logging.config
import os

# 日志配置
LOG_FILE = os.environ.get("LOG_FILE", "/code/sec-toolkit/data/backend.log")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "detailed": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        }
    },
    "handlers": {
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "standard",
            "filename": LOG_FILE,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "encoding": "utf-8"
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "detailed",
            "filename": LOG_FILE.replace(".log", ".error.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "level": "ERROR"
        }
    },
    "root": {
        "level": LOG_LEVEL,
        "handlers": ["file", "error_file"]
    },
    "loggers": {
        "app": {"level": LOG_LEVEL},
        "app.middleware": {"level": LOG_LEVEL},
        "uvicorn": {"level": "WARNING"},
        "httpx": {"level": "WARNING"},
        "sqlalchemy": {"level": "WARNING"},
    }
})

logger = logging.getLogger("app")

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import init_db, get_db
from .api import api_router
from .api.v1.callback import handle_callback
from .core.middleware import RequestContextMiddleware, setup_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("正在初始化数据库...")
    await init_db()
    
    # 注册 Agent 工具
    from .agent.tools import register_builtin_tools
    register_builtin_tools()
    logger.info("Agent 工具注册完成")
    
    # 注册预置 Skill
    from .agent.skill import register_builtin_skills
    register_builtin_skills()
    logger.info("预置 Skill 注册完成")

    # 注册 PoC handlers
    from .poc import poc_registry
    poc_registry.auto_discover()
    logger.info("PoC handler 注册完成")
    
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 启动成功")
    yield
    # 关闭时
    logger.info("正在清理资源...")
    
    # 关闭 LLM HTTP 连接池
    try:
        from .api.v1.llm import close_llm_http_client
        await close_llm_http_client()
        logger.info("LLM HTTP 客户端已关闭")
    except Exception as e:
        logger.warning(f"关闭 LLM HTTP 客户端失败: {e}")
    
    # 关闭 DualLLM 共享客户端
    try:
        from .agent.dual_llm import cleanup_shared_clients
        await cleanup_shared_clients()
        logger.info("DualLLM 客户端已关闭")
    except Exception as e:
        logger.warning(f"关闭 DualLLM 客户端失败: {e}")
    
    # 关闭 Proxy 模块客户端
    try:
        from .modules.proxy import proxy_manager
        if proxy_manager._client and not proxy_manager._client.is_closed:
            await proxy_manager._client.aclose()
            logger.info("Proxy HTTP 客户端已关闭")
    except Exception as e:
        logger.warning(f"关闭 Proxy 客户端失败: {e}")
    
    # 关闭反弹 Shell 监听和会话
    try:
        from .modules.revshell import RevShellManager
        manager = RevShellManager.get_instance()
        await manager.cleanup()
        logger.info("反弹 Shell 资源已清理")
    except Exception as e:
        logger.warning(f"清理反弹 Shell 资源失败: {e}")
    
    logger.info("应用关闭完成")


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

# 中间件配置（注意顺序：后添加的先执行）
# 1. 请求上下文中间件（请求 ID、日志）
app.add_middleware(RequestContextMiddleware)

# 2. CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Response-Time"],
)

# 设置全局异常处理器
setup_exception_handlers(app)

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


# ==================== Quick PoC 公开端点 ====================
from .poc import poc_registry
from .poc.base import PocRequest as PocReq
from .models.poc_log import PocAccessLog
from fastapi.responses import PlainTextResponse, Response, RedirectResponse


async def _handle_poc(request: Request, name: str, sub_path: str, db: AsyncSession):
    """处理 PoC 请求"""
    meta = poc_registry.get(name)
    if not meta:
        return PlainTextResponse("PoC Not Found", status_code=404)

    is_preview = request.headers.get("x-quick-poc-preview") == "1"

    if not is_preview:
        meta.hit_count += 1
    poc_req = await PocReq.from_fastapi(request, name, sub_path)

    if meta.record and not is_preview:
        log = PocAccessLog(
            poc_name=name,
            client_ip=poc_req.client_ip,
            method=poc_req.method,
            path=sub_path or "/",
            query_string=str(request.url.query) if request.url.query else None,
            headers=dict(request.headers),
            body=poc_req.body,
            user_agent=request.headers.get("user-agent"),
        )
        db.add(log)

    try:
        result = await meta.handler(poc_req)
    except Exception as e:
        return PlainTextResponse(f"Handler Error: {e}", status_code=500)

    if result.redirect_url:
        return RedirectResponse(url=result.redirect_url, status_code=result.status_code or 302)

    ct = result.content_type or "text/plain"
    if ct.startswith("text/") and "charset" not in ct:
        ct = f"{ct}; charset=utf-8"

    headers = dict(result.headers) if result.headers else {}
    headers["Content-Type"] = ct

    return Response(content=result.body, status_code=result.status_code, headers=headers)


@app.api_route("/p/{name}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
               tags=["Quick PoC"], summary="PoC 端点")
async def poc_handler(request: Request, name: str, db: AsyncSession = Depends(get_db)):
    return await _handle_poc(request, name, "", db)


@app.api_route("/p/{name}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
               tags=["Quick PoC"], summary="PoC 端点（带子路径）")
async def poc_handler_with_path(request: Request, name: str, path: str, db: AsyncSession = Depends(get_db)):
    return await _handle_poc(request, name, path, db)
