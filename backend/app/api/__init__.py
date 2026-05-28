"""API 路由"""
from fastapi import APIRouter
from .v1 import auth, notes, tools, bookmarks, users, bypass, callback, llm, knowledge, proxy, agent, skill, memory, revshell, poc

api_router = APIRouter()

# 注册路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(users.router, prefix="/users", tags=["用户"])
api_router.include_router(notes.router, prefix="/notes", tags=["笔记"])
api_router.include_router(tools.router, prefix="/tools", tags=["工具"])
api_router.include_router(bookmarks.router, prefix="/bookmarks", tags=["书签"])
api_router.include_router(bypass.router, prefix="/bypass", tags=["绕过"])
api_router.include_router(callback.router, prefix="/callback", tags=["回调服务器"])
api_router.include_router(proxy.router, prefix="/proxy", tags=["本地代理"])
api_router.include_router(revshell.router, prefix="/revshell", tags=["反弹 Shell"])
api_router.include_router(llm.router, tags=["LLM"])
api_router.include_router(knowledge.router, tags=["知识库"])
api_router.include_router(agent.router, tags=["Agent 配置"])
api_router.include_router(skill.router, tags=["Skill"])
api_router.include_router(memory.router, tags=["记忆"])

api_router.include_router(poc.router, tags=["Quick PoC"])
