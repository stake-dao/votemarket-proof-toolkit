"""
Retry utilities for handling transient failures.

This module provides decorators and utilities for retrying operations
with configurable backoff strategies.

Exception Handling:
- By default, retries on RetryableException and its subclasses
- NonRetryableException is never retried (propagates immediately)
- Can customize retryable_exceptions per operation
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, Union

from web3.exceptions import (
    Web3Exception,
    ContractLogicError,
    BadFunctionCallOutput,
    TransactionNotFound,
    BlockNotFound,
)

from votemarket_toolkit.shared.exceptions import RetryableException

T = TypeVar("T")

logger = logging.getLogger(__name__)

# Default retryable exceptions (network/RPC related + RetryableException hierarchy)
# Includes Web3 exceptions to ensure RPC failures are retried
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    RetryableException,  # Includes VoteMarketProofsException, APIException
    ConnectionError,
    TimeoutError,
    OSError,
    Web3Exception,  # Base class for most web3 errors
    ContractLogicError,  # Contract reverts
    BadFunctionCallOutput,  # Malformed RPC responses
    TransactionNotFound,
    BlockNotFound,
    Exception,  # Catch-all for any other RPC issues - ensures we always retry
)


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable:
    """
    Decorator for retrying async functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        exponential: Use exponential backoff (default: True)
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry with (exception, attempt)

    Returns:
        Decorated async function with retry logic

    Example:
        @with_retry(max_attempts=3, base_delay=1.0)
        async def fetch_data():
            ...
    """
    if retryable_exceptions is None:
        retryable_exceptions = DEFAULT_RETRYABLE_EXCEPTIONS

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        if exponential:
                            delay = min(base_delay * (2**attempt), max_delay)
                        else:
                            delay = base_delay

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for "
                            f"{func.__name__}: {e}. Retrying in {delay:.1f}s..."
                        )

                        if on_retry:
                            on_retry(e, attempt + 1)

                        await asyncio.sleep(delay)

            # All attempts exhausted
            if last_exception:
                raise last_exception
            raise RuntimeError(
                f"Unexpected state: no exception but all attempts exhausted"
            )

        return wrapper

    return decorator


def retry_sync(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
) -> Callable:
    """
    Decorator for retrying synchronous functions with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 30.0)
        exponential: Use exponential backoff (default: True)
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry with (exception, attempt)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_sync(max_attempts=3, base_delay=0.5)
        def call_rpc():
            ...
    """
    if retryable_exceptions is None:
        retryable_exceptions = DEFAULT_RETRYABLE_EXCEPTIONS

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        if exponential:
                            delay = min(base_delay * (2**attempt), max_delay)
                        else:
                            delay = base_delay

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for "
                            f"{func.__name__}: {e}. Retrying in {delay:.1f}s..."
                        )

                        if on_retry:
                            on_retry(e, attempt + 1)

                        time.sleep(delay)

            # All attempts exhausted
            if last_exception:
                raise last_exception
            raise RuntimeError(
                f"Unexpected state: no exception but all attempts exhausted"
            )

        return wrapper

    return decorator


async def retry_async_operation(
    operation: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    operation_name: Optional[str] = None,
    **kwargs: Any,
) -> T:
    """
    Retry an async operation with configurable backoff.

    This is a functional alternative to the decorator when you need to
    retry a specific call rather than decorating a function.

    Args:
        operation: Async function to call
        *args: Positional arguments for the operation
        max_attempts: Maximum retry attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        exponential: Use exponential backoff
        retryable_exceptions: Exception types to retry on
        operation_name: Optional name for logging
        **kwargs: Keyword arguments for the operation

    Returns:
        Result of the operation

    Example:
        result = await retry_async_operation(
            fetch_data,
            url,
            max_attempts=5,
            operation_name="fetch_data"
        )
    """
    if retryable_exceptions is None:
        retryable_exceptions = DEFAULT_RETRYABLE_EXCEPTIONS

    name = operation_name or getattr(operation, "__name__", "operation")
    last_exception: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return await operation(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt < max_attempts - 1:
                if exponential:
                    delay = min(base_delay * (2**attempt), max_delay)
                else:
                    delay = base_delay

                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed for "
                    f"{name}: {e}. Retrying in {delay:.1f}s..."
                )

                await asyncio.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError(
        "Unexpected state: no exception but all attempts exhausted"
    )


def retry_sync_operation(
    operation: Callable[..., T],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    operation_name: Optional[str] = None,
    **kwargs: Any,
) -> T:
    """
    Retry a synchronous operation with configurable backoff.

    This is a functional alternative to the decorator when you need to
    retry a specific call rather than decorating a function.

    Args:
        operation: Function to call
        *args: Positional arguments for the operation
        max_attempts: Maximum retry attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        exponential: Use exponential backoff
        retryable_exceptions: Exception types to retry on
        operation_name: Optional name for logging
        **kwargs: Keyword arguments for the operation

    Returns:
        Result of the operation
    """
    if retryable_exceptions is None:
        retryable_exceptions = DEFAULT_RETRYABLE_EXCEPTIONS

    name = operation_name or getattr(operation, "__name__", "operation")
    last_exception: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            return operation(*args, **kwargs)
        except retryable_exceptions as e:
            last_exception = e

            if attempt < max_attempts - 1:
                if exponential:
                    delay = min(base_delay * (2**attempt), max_delay)
                else:
                    delay = base_delay

                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed for "
                    f"{name}: {e}. Retrying in {delay:.1f}s..."
                )

                time.sleep(delay)

    if last_exception:
        raise last_exception
    raise RuntimeError(
        "Unexpected state: no exception but all attempts exhausted"
    )


class RetryConfig:
    """
    Configuration class for retry behavior.

    Can be used to share retry settings across multiple operations.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        exponential: bool = True,
        retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential = exponential
        self.retryable_exceptions = retryable_exceptions or DEFAULT_RETRYABLE_EXCEPTIONS

    def decorator(self) -> Callable:
        """Create a with_retry decorator using this config."""
        return with_retry(
            max_attempts=self.max_attempts,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential=self.exponential,
            retryable_exceptions=self.retryable_exceptions,
        )

    def sync_decorator(self) -> Callable:
        """Create a retry_sync decorator using this config."""
        return retry_sync(
            max_attempts=self.max_attempts,
            base_delay=self.base_delay,
            max_delay=self.max_delay,
            exponential=self.exponential,
            retryable_exceptions=self.retryable_exceptions,
        )


# Pre-configured retry configs for common use cases
RPC_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=10.0,
    exponential=True,
)

HTTP_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=5.0,
    exponential=True,
)

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=30.0,
    exponential=True,
)
