"""API 路由"""
from fastapi import APIRouter
from .v1 import auth, notes, tools, bookmarks, users, bypass, callback, llm, knowledge

api_router = APIRouter()

# 注册路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(notes.router, prefix="/notes", tags=["笔记"])
api_router.include_router(tools.router, prefix="/tools", tags=["工具"])
api_router.include_router(bookmarks.router, prefix="/bookmarks", tags=["书签"])
api_router.include_router(bypass.router, prefix="/bypass", tags=["绕过"])
api_router.include_router(callback.router, prefix="/callback", tags=["回调服务器"])
api_router.include_router(llm.router, tags=["LLM"])
api_router.include_router(knowledge.router, tags=["知识库"])

