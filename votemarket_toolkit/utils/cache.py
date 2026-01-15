"""
TTL (Time-To-Live) file-based caching utilities for performance optimization.

This module provides:
1. A TTL cache decorator for async functions
2. A cache manager for manual cache control
3. File-based persistent caching with automatic expiration

Configuration:
- VM_CACHE_TTL: Default TTL in seconds (default: 3600 = 1 hour)

Cache files are stored in .cache directory and excluded from git.
"""

import asyncio
import fnmatch
import hashlib
import json
import os
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from votemarket_toolkit.shared.logging import get_logger

_logger = get_logger(__name__)

# Cache configuration from environment
DEFAULT_CACHE_TTL = int(os.environ.get("VM_CACHE_TTL", "3600"))

# Cache directory path (created lazily)
CACHE_DIR = Path(".cache")

# Track whether cache directory has been initialized
_cache_initialized = False


def _ensure_cache_dir() -> None:
    """
    Lazily initialize the cache directory and update .gitignore if needed.

    This is called on first cache access rather than at import time to avoid
    side effects during module import.
    """
    global _cache_initialized
    if _cache_initialized:
        return

    # Create cache directory
    CACHE_DIR.mkdir(exist_ok=True)

    # Ensure cache directory is gitignored
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        try:
            with open(gitignore_path, "r") as f:
                gitignore_content = f.read()
            if (
                ".cache/" not in gitignore_content
                and ".cache" not in gitignore_content
            ):
                with open(gitignore_path, "a") as f:
                    f.write("\n# VoteMarket cache files\n.cache/\n")
        except (OSError, IOError) as e:
            _logger.debug("Could not update .gitignore: %s", e)

    _cache_initialized = True


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

    def __init__(self, default_ttl: Optional[int] = None):
        """
        Initialize TTL cache.

        Args:
            default_ttl: Default time-to-live in seconds.
                         If not provided, uses VM_CACHE_TTL env var (default: 3600)
        """
        self._lock = asyncio.Lock()
        self.default_ttl = default_ttl if default_ttl is not None else DEFAULT_CACHE_TTL
        self._cleanup_task: Optional[asyncio.Task] = None
        self._namespace = "global"
        # Key index maps hash -> original key for pattern matching
        self._key_index_path = CACHE_DIR / "_key_index.json"
        self._key_index: Dict[str, str] = self._load_key_index()

    def _load_key_index(self) -> Dict[str, str]:
        """Load the key index from disk."""
        if self._key_index_path.exists():
            try:
                with open(self._key_index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception):
                return {}
        return {}

    def _save_key_index(self) -> None:
        """Save the key index to disk."""
        try:
            with open(self._key_index_path, "w", encoding="utf-8") as f:
                json.dump(self._key_index, f)
        except Exception as e:
            _logger.debug("Failed to save key index: %s", e)

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        # Create safe filename from key
        safe_key = hashlib.sha256(
            f"{self._namespace}:{key}".encode()
        ).hexdigest()
        return CACHE_DIR / f"{safe_key}.cache"

    def _get_hash_for_key(self, key: str) -> str:
        """Get the hash for a cache key."""
        return hashlib.sha256(
            f"{self._namespace}:{key}".encode()
        ).hexdigest()

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
        _ensure_cache_dir()

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
                # Store key in index for pattern matching
                key_hash = self._get_hash_for_key(key)
                self._key_index[key_hash] = key
                self._save_key_index()
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
                except Exception as e:
                    _logger.warning("Failed to remove cache file %s: %s", cache_file, e)
            # Clear key index
            self._key_index.clear()
            self._save_key_index()

    async def delete(self, key: str) -> None:
        """Delete a specific cache entry."""
        async with self._lock:
            cache_path = self._get_cache_path(key)
            if cache_path.exists():
                try:
                    cache_path.unlink()
                    # Remove from key index
                    key_hash = self._get_hash_for_key(key)
                    self._key_index.pop(key_hash, None)
                    self._save_key_index()
                except Exception as e:
                    _logger.warning("Failed to delete cache entry %s: %s", key, e)

    async def invalidate(self, key: str) -> bool:
        """
        Invalidate a specific cache entry by key.

        Args:
            key: The exact cache key to invalidate

        Returns:
            True if entry was found and deleted, False otherwise
        """
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            await self.delete(key)
            return True
        return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a glob pattern.

        Args:
            pattern: Glob pattern to match (e.g., "campaigns:*", "*.ethereum.*")

        Returns:
            Number of entries invalidated
        """
        async with self._lock:
            invalidated = 0
            keys_to_remove = []

            # Find all keys matching the pattern
            for key_hash, original_key in self._key_index.items():
                if fnmatch.fnmatch(original_key, pattern):
                    cache_path = CACHE_DIR / f"{key_hash}.cache"
                    if cache_path.exists():
                        try:
                            cache_path.unlink()
                            invalidated += 1
                        except Exception as e:
                            _logger.warning(
                                "Failed to invalidate cache entry %s: %s",
                                original_key, e
                            )
                    keys_to_remove.append(key_hash)

            # Update key index
            for key_hash in keys_to_remove:
                self._key_index.pop(key_hash, None)
            if keys_to_remove:
                self._save_key_index()

            return invalidated

    def get_keys(self, pattern: Optional[str] = None) -> List[str]:
        """
        Get all cached keys, optionally filtered by pattern.

        Args:
            pattern: Optional glob pattern to filter keys

        Returns:
            List of cache keys
        """
        keys = list(self._key_index.values())
        if pattern:
            keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]
        return keys

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
                    except Exception as e:
                        _logger.warning("Failed to remove corrupted cache file %s: %s", cache_file, e)

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


# Global cache instance (uses VM_CACHE_TTL env var, defaults to 3600)
_global_cache = TTLCache()


def ttl_cache(ttl: Optional[int] = None, key_prefix: Optional[str] = None):
    """
    Decorator for caching async function results with TTL.

    Args:
        ttl: Time-to-live in seconds (default: VM_CACHE_TTL env var or 3600)
        key_prefix: Optional prefix for cache keys (useful for namespacing)

    Example:
        @ttl_cache(ttl=3600)  # Cache for 1 hour
        async def expensive_operation(param1, param2):
            # ... expensive computation ...
            return result
    """
    effective_ttl = ttl if ttl is not None else DEFAULT_CACHE_TTL

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
            await _global_cache.set(cache_key, result, effective_ttl)

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
            except Exception as e:
                _logger.warning("Failed to clear cache file %s: %s", cache_file, e)


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


async def invalidate_cache(key: str) -> bool:
    """
    Invalidate a specific cache entry.

    Args:
        key: The exact cache key to invalidate

    Returns:
        True if entry was found and deleted, False otherwise
    """
    return await _global_cache.invalidate(key)


async def invalidate_cache_pattern(pattern: str) -> int:
    """
    Invalidate all cache entries matching a glob pattern.

    Args:
        pattern: Glob pattern to match (e.g., "campaigns:*", "*:42161:*")

    Returns:
        Number of entries invalidated

    Example:
        >>> await invalidate_cache_pattern("campaigns:*")  # Clear all campaign caches
        >>> await invalidate_cache_pattern("*:42161:*")  # Clear all Arbitrum caches
    """
    return await _global_cache.invalidate_pattern(pattern)


def get_cache_keys(pattern: Optional[str] = None) -> List[str]:
    """
    Get all cached keys, optionally filtered by pattern.

    Args:
        pattern: Optional glob pattern to filter keys

    Returns:
        List of cache keys
    """
    return _global_cache.get_keys(pattern)


def get_default_cache_ttl() -> int:
    """Get the default cache TTL in seconds."""
    return DEFAULT_CACHE_TTL


# Manual cache management
class CacheManager:
    """Manual cache management for complex caching scenarios."""

    def __init__(self, namespace: str, ttl: Optional[int] = None):
        """
        Initialize cache manager with namespace.

        Args:
            namespace: Namespace for cache keys
            ttl: Default TTL in seconds (default: VM_CACHE_TTL env var or 3600)
        """
        self.namespace = namespace
        self.ttl = ttl if ttl is not None else DEFAULT_CACHE_TTL

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
        # Use pattern-based invalidation for this namespace
        await _global_cache.invalidate_pattern(f"{self.namespace}:*")

    async def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry in this namespace."""
        full_key = f"{self.namespace}:{key}"
        return await _global_cache.invalidate(full_key)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern within this namespace."""
        full_pattern = f"{self.namespace}:{pattern}"
        return await _global_cache.invalidate_pattern(full_pattern)


class SyncCacheManager:
    """Synchronous cache manager for use in non-async contexts.

    Uses the same file-based storage as TTLCache but with sync operations.
    Suitable for services that need sync cache access (e.g., CampaignService).
    """

    def __init__(self, namespace: str, ttl: Optional[int] = None):
        """
        Initialize sync cache manager with namespace.

        Args:
            namespace: Namespace for cache keys (e.g., "campaigns", "analytics")
            ttl: Default TTL in seconds (default: VM_CACHE_TTL env var or 3600)
        """
        self.namespace = namespace
        self.ttl = ttl if ttl is not None else DEFAULT_CACHE_TTL
        self._key_index_path = CACHE_DIR / "_key_index.json"

    def _get_cache_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        safe_key = hashlib.sha256(
            f"{self.namespace}:{key}".encode()
        ).hexdigest()
        return CACHE_DIR / f"{safe_key}.cache"

    def _get_hash_for_key(self, key: str) -> str:
        """Get the hash for a cache key."""
        return hashlib.sha256(
            f"{self.namespace}:{key}".encode()
        ).hexdigest()

    def _load_key_index(self) -> Dict[str, str]:
        """Load the key index from disk."""
        if self._key_index_path.exists():
            try:
                with open(self._key_index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception):
                return {}
        return {}

    def _save_key_index(self, index: Dict[str, str]) -> None:
        """Save the key index to disk."""
        try:
            with open(self._key_index_path, "w", encoding="utf-8") as f:
                json.dump(index, f)
        except Exception as e:
            _logger.debug("Failed to save key index: %s", e)

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        cache_path = self._get_cache_path(key)

        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                if time.time() < data.get("expiry_time", 0):
                    return data["value"]
                else:
                    # Remove expired file
                    cache_path.unlink(missing_ok=True)
            except (json.JSONDecodeError, KeyError, Exception):
                # If file is corrupted, remove it
                if cache_path.exists():
                    cache_path.unlink(missing_ok=True)

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        _ensure_cache_dir()

        if ttl is None:
            ttl = self.ttl

        cache_path = self._get_cache_path(key)
        expiry_time = time.time() + ttl

        try:
            data = {"value": value, "expiry_time": expiry_time}
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f)

            # Store key in index for pattern matching
            full_key = f"{self.namespace}:{key}"
            key_hash = self._get_hash_for_key(key)
            index = self._load_key_index()
            index[key_hash] = full_key
            self._save_key_index(index)
        except (TypeError, Exception):
            # If write fails, try to clean up
            if cache_path.exists():
                cache_path.unlink(missing_ok=True)

    def delete(self, key: str) -> None:
        """Delete a specific cache entry."""
        cache_path = self._get_cache_path(key)
        if cache_path.exists():
            try:
                cache_path.unlink()
                # Remove from key index
                key_hash = self._get_hash_for_key(key)
                index = self._load_key_index()
                index.pop(key_hash, None)
                self._save_key_index(index)
            except Exception as e:
                _logger.warning("Failed to delete cache entry %s: %s", key, e)

    def clear(self) -> int:
        """Clear all entries in this namespace.

        Returns:
            Number of entries cleared
        """
        cleared = 0
        index = self._load_key_index()
        keys_to_remove = []

        # Find all keys in this namespace
        for key_hash, full_key in index.items():
            if full_key.startswith(f"{self.namespace}:"):
                cache_path = CACHE_DIR / f"{key_hash}.cache"
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                        cleared += 1
                    except Exception as e:
                        _logger.warning(
                            "Failed to clear cache entry %s: %s",
                            full_key, e
                        )
                keys_to_remove.append(key_hash)

        # Update key index
        for key_hash in keys_to_remove:
            index.pop(key_hash, None)
        if keys_to_remove:
            self._save_key_index(index)

        return cleared

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all cache entries matching a glob pattern within namespace.

        Args:
            pattern: Glob pattern to match (e.g., "*:42161:*")

        Returns:
            Number of entries invalidated
        """
        full_pattern = f"{self.namespace}:{pattern}"
        invalidated = 0
        index = self._load_key_index()
        keys_to_remove = []

        for key_hash, full_key in index.items():
            if fnmatch.fnmatch(full_key, full_pattern):
                cache_path = CACHE_DIR / f"{key_hash}.cache"
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                        invalidated += 1
                    except Exception as e:
                        _logger.warning(
                            "Failed to invalidate cache entry %s: %s",
                            full_key, e
                        )
                keys_to_remove.append(key_hash)

        # Update key index
        for key_hash in keys_to_remove:
            index.pop(key_hash, None)
        if keys_to_remove:
            self._save_key_index(index)

        return invalidated
