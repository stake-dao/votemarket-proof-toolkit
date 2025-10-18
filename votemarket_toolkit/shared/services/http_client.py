"""
Shared HTTP client utilities for sync and async operations.

Centralizes httpx client creation with sensible defaults, connection pooling,
timeouts, and a consistent User-Agent. Use these helpers instead of creating
ad-hoc clients across the codebase.
"""

from __future__ import annotations

import os
from typing import Optional

import httpx

DEFAULT_TIMEOUT = float(os.getenv("VM_HTTP_TIMEOUT", "15"))
DEFAULT_CONNECT_TIMEOUT = float(os.getenv("VM_HTTP_CONNECT_TIMEOUT", "5"))
USER_AGENT = os.getenv("VM_HTTP_UA", "votemarket-toolkit/1.x")

_sync_client: Optional[httpx.Client] = None
_async_client: Optional[httpx.AsyncClient] = None


def _build_limits() -> httpx.Limits:
    return httpx.Limits(max_keepalive_connections=20, max_connections=100)


def _build_timeout() -> httpx.Timeout:
    return httpx.Timeout(DEFAULT_TIMEOUT, connect=DEFAULT_CONNECT_TIMEOUT)


def _default_headers() -> dict:
    return {"User-Agent": USER_AGENT}


def get_client() -> httpx.Client:
    """Get a shared synchronous httpx client."""
    global _sync_client
    if _sync_client is None:
        _sync_client = httpx.Client(
            timeout=_build_timeout(),
            limits=_build_limits(),
            headers=_default_headers(),
        )
    return _sync_client


def get_async_client() -> httpx.AsyncClient:
    """Get a shared asynchronous httpx client."""
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(
            timeout=_build_timeout(),
            limits=_build_limits(),
            headers=_default_headers(),
        )
    return _async_client


async def aclose_async_client() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None


def close_client() -> None:
    global _sync_client
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None

