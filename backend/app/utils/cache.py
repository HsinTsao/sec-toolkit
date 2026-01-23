"""内存缓存"""
from cachetools import TTLCache
from functools import wraps
from typing import Any, Callable
import hashlib
import json

from ..config import settings

# 全局缓存实例
cache = TTLCache(maxsize=settings.CACHE_MAX_SIZE, ttl=settings.CACHE_TTL)


def make_cache_key(*args, **kwargs) -> str:
    """生成缓存键"""
    key_data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return hashlib.md5(key_data.encode()).hexdigest()


def cached(ttl: int = None):
    """缓存装饰器
    
    Usage:
        @cached(ttl=60)
        async def get_user(user_id: str):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{func.__name__}:{make_cache_key(*args, **kwargs)}"
            
            # 尝试从缓存获取
            if cache_key in cache:
                return cache[cache_key]
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            if result is not None:
                cache[cache_key] = result
            
            return result
        return wrapper
    return decorator


def invalidate_cache(pattern: str = None):
    """清除缓存
    
    Args:
        pattern: 匹配模式，None 则清除所有
    """
    if pattern is None:
        cache.clear()
    else:
        keys_to_delete = [k for k in cache.keys() if pattern in k]
        for key in keys_to_delete:
            del cache[key]

