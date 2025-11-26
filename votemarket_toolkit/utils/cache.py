"""
TTL (Time-To-Live) file-based caching utilities for performance optimization.

This module provides:
1. A TTL cache decorator for async functions
2. A cache manager for manual cache control
3. File-based persistent caching with automatic expiration

Default TTL is 1 hour (3600 seconds) for all caches.
Cache files are stored in .cache directory and excluded from git.
"""

import asyncio
import hashlib
import json
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

# Cache directory configuration
CACHE_DIR = Path(".cache")
CACHE_DIR.mkdir(exist_ok=True)

# Ensure cache directory is gitignored
gitignore_path = Path(".gitignore")
if gitignore_path.exists():
    with open(gitignore_path, "r") as f:
        gitignore_content = f.read()
    if (
        ".cache/" not in gitignore_content
        and ".cache" not in gitignore_content
    ):
        with open(gitignore_path, "a") as f:
            f.write("\n# VoteMarket cache files\n.cache/\n")


class CacheEntry:
    """A cache entry with expiration time."""

    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expiry_time = time.time() + ttl

    def is_expired(self) -> bool:
        """Check if this cache entry has expired."""
        return time.time() > self.expiry_time


class TTLCache:
    """File-based persistent TTL cache implementation."""

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize TTL cache.

        Args:
            default_ttl: Default time-to-live in seconds (default: 3600 = 1 hour)
        """
        self._lock = asyncio.Lock()
        self.default_ttl = default_ttl
        self._cleanup_task: Optional[asyncio.Task] = None
        self._namespace = "global"

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        # Create safe filename from key
        safe_key = hashlib.sha256(
            f"{self._namespace}:{key}".encode()
        ).hexdigest()
        return CACHE_DIR / f"{safe_key}.cache"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        async with self._lock:
            cache_path = self._get_cache_path(key)

            if cache_path.exists():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Reconstruct CacheEntry from JSON data
                    entry = CacheEntry(data["value"], 0)
                    entry.expiry_time = data["expiry_time"]

                    if not entry.is_expired():
                        return entry.value
                    else:
                        # Remove expired file
                        cache_path.unlink()
                except (json.JSONDecodeError, KeyError, Exception):
                    # If file is corrupted, remove it
                    if cache_path.exists():
                        cache_path.unlink()

        return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Set value in cache with TTL."""
        if ttl is None:
            ttl = self.default_ttl

        async with self._lock:
            cache_path = self._get_cache_path(key)
            entry = CacheEntry(value, ttl)

            try:
                # Create JSON-serializable representation
                data = {"value": entry.value, "expiry_time": entry.expiry_time}
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
            except (TypeError, json.JSONEncodeError, Exception):
                # If write fails, try to clean up
                if cache_path.exists():
                    cache_path.unlink()

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            # Remove all cache files
            for cache_file in CACHE_DIR.glob("*.cache"):
                try:
                    cache_file.unlink()
                except Exception:
                    pass

    async def delete(self, key: str) -> None:
        """Delete a specific cache entry."""
        async with self._lock:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                except Exception:
                    pass

    async def cleanup_expired(self) -> None:
        """Remove all expired entries."""
        async with self._lock:
            # Check all cache files
            for cache_file in CACHE_DIR.glob("*.cache"):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    # Check if expired
                    if time.time() > data.get("expiry_time", 0):
                        cache_file.unlink()
                except (json.JSONDecodeError, KeyError, Exception):
                    # If file is corrupted or can't be read, remove it
                    try:
                        cache_file.unlink()
                    except Exception:
                        pass

    def start_cleanup_task(self, interval: int = 60) -> None:
        """Start periodic cleanup of expired entries."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(
                self._periodic_cleanup(interval)
            )

    async def _periodic_cleanup(self, interval: int) -> None:
        """Periodically clean up expired entries."""
        while True:
            await asyncio.sleep(interval)
            await self.cleanup_expired()

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total_entries = 0
        active_entries = 0
        expired_entries = 0

        for cache_file in CACHE_DIR.glob("*.cache"):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                total_entries += 1
                # Check if expired
                if time.time() > data.get("expiry_time", 0):
                    expired_entries += 1
                else:
                    active_entries += 1
            except (json.JSONDecodeError, KeyError, Exception):
                pass

        return {
            "total_entries": total_entries,
            "active_entries": active_entries,
            "expired_entries": expired_entries,
        }


# Global cache instance
_global_cache = TTLCache(default_ttl=3600)  # 1 hour default


def ttl_cache(ttl: int = 3600, key_prefix: Optional[str] = None):
    """
    Decorator for caching async function results with TTL.

    Args:
        ttl: Time-to-live in seconds (default: 3600 = 1 hour)
        key_prefix: Optional prefix for cache keys (useful for namespacing)

    Example:
        @ttl_cache(ttl=3600)  # Cache for 1 hour
        async def expensive_operation(param1, param2):
            # ... expensive computation ...
            return result
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = _generate_cache_key(
                func.__name__, args, kwargs, key_prefix
            )

            # Try to get from cache
            cached_value = await _global_cache.get(cache_key)
            if cached_value is not None:
                return cached_value

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await _global_cache.set(cache_key, result, ttl)

            return result

        # Add cache control methods using setattr to avoid type errors
        setattr(
            wrapper,
            "clear_cache",
            lambda: _clear_function_cache(func.__name__, key_prefix),
        )
        setattr(wrapper, "cache", _global_cache)

        return wrapper

    return decorator


def _generate_cache_key(
    func_name: str, args: Tuple, kwargs: Dict, prefix: Optional[str] = None
) -> str:
    """Generate a unique cache key from function name and arguments."""
    # Create a dictionary of all arguments
    key_data = {"func": func_name, "args": args, "kwargs": kwargs}

    # Convert to JSON and hash it
    key_json = json.dumps(key_data, sort_keys=True, default=str)
    key_hash = hashlib.sha256(key_json.encode()).hexdigest()[:16]

    # Add prefix if provided
    if prefix:
        return f"{prefix}:{func_name}:{key_hash}"
    return f"{func_name}:{key_hash}"


async def _clear_function_cache(
    func_name: str, prefix: Optional[str] = None
) -> None:
    """Clear all cache entries for a specific function."""
    # With file-based cache and hashed keys, we clear all cache entries
    async with _global_cache._lock:
        # Since we hash the keys, we can't directly match patterns
        # So we'll clear all cache for now (limitation of file-based cache)
        for cache_file in CACHE_DIR.glob("*.cache"):
            try:
                cache_file.unlink()
            except Exception:
                pass


# Convenience functions
async def clear_all_cache() -> None:
    """Clear all cached data."""
    await _global_cache.clear()


async def get_cache_stats() -> Dict[str, int]:
    """Get global cache statistics."""
    return _global_cache.get_stats()


def start_cache_cleanup(interval: int = 60) -> None:
    """
    Start periodic cleanup of expired cache entries.

    Args:
        interval: Cleanup interval in seconds (default: 60)
    """
    _global_cache.start_cleanup_task(interval)


# Manual cache management
class CacheManager:
    """Manual cache management for complex caching scenarios."""

    def __init__(self, namespace: str, ttl: int = 3600):
        """
        Initialize cache manager with namespace.

        Args:
            namespace: Namespace for cache keys
            ttl: Default TTL in seconds
        """
        self.namespace = namespace
        self.ttl = ttl

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        full_key = f"{self.namespace}:{key}"
        return await _global_cache.get(full_key)

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None
    ) -> None:
        """Set value in cache."""
        full_key = f"{self.namespace}:{key}"
        if ttl is None:
            ttl = self.ttl
        await _global_cache.set(full_key, value, ttl)

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        full_key = f"{self.namespace}:{key}"
        await _global_cache.delete(full_key)

    async def clear(self) -> None:
        """Clear all entries in this namespace."""
        async with _global_cache._lock:
            # Clear all cache files for this namespace
            # Since keys are hashed, we can't match namespace directly
            # This is a limitation of file-based cache
            await _global_cache.clear()
