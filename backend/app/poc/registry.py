"""PoC 注册中心 - 自动扫描 handlers/ 并管理所有 PoC"""
from __future__ import annotations

import importlib
import pkgutil
import logging
from typing import Optional

from .base import PocMeta, _registered_handlers

logger = logging.getLogger(__name__)


class PocRegistry:
    def __init__(self):
        self._pocs: dict[str, PocMeta] = {}

    def _collect(self) -> None:
        """将 _registered_handlers 中的条目注册进来"""
        for meta in _registered_handlers:
            if meta.name in self._pocs:
                logger.warning(f"PoC '{meta.name}' 重复注册，将覆盖")
            self._pocs[meta.name] = meta
            logger.info(f"注册 PoC: {meta.name} ({meta.category})")

    def auto_discover(self) -> None:
        """自动扫描 handlers/ 包下的所有模块，触发 @poc 装饰器注册"""
        from . import handlers as handlers_pkg

        _registered_handlers.clear()

        for importer, modname, ispkg in pkgutil.walk_packages(
            handlers_pkg.__path__,
            prefix=handlers_pkg.__name__ + ".",
        ):
            try:
                importlib.import_module(modname)
            except Exception:
                logger.exception(f"加载 PoC 模块失败: {modname}")

        self._collect()
        logger.info(f"共注册 {len(self._pocs)} 个 PoC handler")

    def get(self, name: str) -> Optional[PocMeta]:
        return self._pocs.get(name)

    def get_all(self) -> list[PocMeta]:
        return list(self._pocs.values())

    def get_by_category(self, category: str) -> list[PocMeta]:
        return [p for p in self._pocs.values() if p.category == category]

    def get_categories(self) -> list[str]:
        cats: list[str] = []
        for p in self._pocs.values():
            if p.category not in cats:
                cats.append(p.category)
        return cats

    def to_list(self) -> list[dict]:
        """返回前端可用的 PoC 列表"""
        return [
            {
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "content_type": p.content_type,
                "record": p.record,
                "usage": p.usage,
                "hit_count": p.hit_count,
            }
            for p in self._pocs.values()
        ]

    def to_templates(self) -> dict[str, dict]:
        """兼容旧版 POC_TEMPLATES 格式，供 OOB 模板选择器使用"""
        templates: dict[str, dict] = {}
        for p in self._pocs.values():
            key = p.name.replace("-", "_")
            templates[key] = {
                "name": p.name,
                "description": p.description,
                "category": p.category,
                "content_type": p.content_type,
                "usage": p.usage,
                "response_body": p.response_body,
                "status_code": p.status_code,
                "redirect_url": p.redirect_url,
                "enable_variables": p.enable_variables,
                "filename": p.filename,
            }
        return templates


poc_registry = PocRegistry()
