"""内存缓存"""
from cachetools import TTLCache
from functools import wraps
from typing import Any, Callable
import hashlib
import json

from ..config import settings

_default_cache = TTLCache(maxsize=settings.CACHE_MAX_SIZE, ttl=settings.CACHE_TTL)
_ttl_caches: dict[int, TTLCache] = {}

# 向后兼容：外部直接引用 cache 的场景
cache = _default_cache


def _get_cache(ttl: int | None) -> TTLCache:
    """获取指定 TTL 的缓存实例，None 则返回默认"""
    if ttl is None:
        return _default_cache
    if ttl not in _ttl_caches:
        _ttl_caches[ttl] = TTLCache(maxsize=settings.CACHE_MAX_SIZE, ttl=ttl)
    return _ttl_caches[ttl]


def make_cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl: int = None):
    """缓存装饰器

    Args:
        ttl: 缓存过期时间（秒），None 使用全局 CACHE_TTL

    Usage:
        @cached(ttl=60)
        async def get_user(user_id: str):
            ...
    """
    def decorator(func: Callable):
        target_cache = _get_cache(ttl)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{make_cache_key(*args, **kwargs)}"

            if cache_key in target_cache:
                return target_cache[cache_key]

            result = await func(*args, **kwargs)

            if result is not None:
                target_cache[cache_key] = result

            return result
        return wrapper
    return decorator


def invalidate_cache(pattern: str = None):
    """清除缓存

    Args:
        pattern: 匹配模式，None 则清除所有
    """
    all_caches = [_default_cache] + list(_ttl_caches.values())
    for c in all_caches:
        if pattern is None:
            c.clear()
        else:
            keys_to_delete = [k for k in c.keys() if pattern in k]
            for key in keys_to_delete:
                del c[key]

