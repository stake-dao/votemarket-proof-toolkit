"""
Unit tests for the retry utilities module.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from votemarket_toolkit.shared.retry import (
    AGGRESSIVE_RETRY_CONFIG,
    HTTP_RETRY_CONFIG,
    RPC_RETRY_CONFIG,
    RetryConfig,
    retry_async_operation,
    retry_sync,
    retry_sync_operation,
    with_retry,
)


class TestWithRetry:
    """Tests for the with_retry async decorator."""

    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        """Test function that succeeds on first attempt."""
        mock_fn = AsyncMock(return_value="success")

        @with_retry(max_attempts=3)
        async def test_func():
            return await mock_fn()

        result = await test_func()
        assert result == "success"
        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_retry(self):
        """Test function that fails twice then succeeds."""
        mock_fn = AsyncMock(
            side_effect=[Exception("fail"), Exception("fail"), "success"]
        )

        @with_retry(max_attempts=3, base_delay=0.01)
        async def test_func():
            return await mock_fn()

        result = await test_func()
        assert result == "success"
        assert mock_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_attempts(self):
        """Test function that always fails exhausts retries."""
        mock_fn = AsyncMock(side_effect=Exception("always fail"))

        @with_retry(max_attempts=3, base_delay=0.01)
        async def test_func():
            return await mock_fn()

        with pytest.raises(Exception, match="always fail"):
            await test_func()

        assert mock_fn.call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test that exponential backoff increases delay."""
        mock_fn = AsyncMock(
            side_effect=[Exception("fail"), Exception("fail"), "success"]
        )
        sleep_times = []

        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            sleep_times.append(delay)
            await original_sleep(0.001)  # Actually wait a tiny bit

        @with_retry(max_attempts=3, base_delay=1.0, exponential=True)
        async def test_func():
            return await mock_fn()

        with patch("asyncio.sleep", mock_sleep):
            result = await test_func()

        assert result == "success"
        # First retry: base_delay * (2^0) = 1.0
        # Second retry: base_delay * (2^1) = 2.0
        assert len(sleep_times) == 2
        assert sleep_times[0] == 1.0
        assert sleep_times[1] == 2.0

    @pytest.mark.asyncio
    async def test_linear_backoff(self):
        """Test that linear backoff keeps constant delay."""
        mock_fn = AsyncMock(
            side_effect=[Exception("fail"), Exception("fail"), "success"]
        )
        sleep_times = []

        async def mock_sleep(delay):
            sleep_times.append(delay)

        @with_retry(max_attempts=3, base_delay=1.0, exponential=False)
        async def test_func():
            return await mock_fn()

        with patch("asyncio.sleep", mock_sleep):
            result = await test_func()

        assert result == "success"
        assert sleep_times == [1.0, 1.0]

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        mock_fn = AsyncMock(
            side_effect=[
                Exception("fail"),
                Exception("fail"),
                Exception("fail"),
                Exception("fail"),
                "success",
            ]
        )
        sleep_times = []

        async def mock_sleep(delay):
            sleep_times.append(delay)

        @with_retry(
            max_attempts=5, base_delay=10.0, max_delay=15.0, exponential=True
        )
        async def test_func():
            return await mock_fn()

        with patch("asyncio.sleep", mock_sleep):
            result = await test_func()

        assert result == "success"
        # Delays would be: 10, 20 (capped to 15), 40 (capped to 15), 80 (capped to 15)
        assert all(d <= 15.0 for d in sleep_times)

    @pytest.mark.asyncio
    async def test_specific_exceptions(self):
        """Test that only specified exceptions are retried."""
        mock_fn = AsyncMock(side_effect=ValueError("not retryable"))

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(TypeError,),  # Only retry TypeError
        )
        async def test_func():
            return await mock_fn()

        # ValueError should not be retried
        with pytest.raises(ValueError, match="not retryable"):
            await test_func()

        assert mock_fn.call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test that on_retry callback is called."""
        mock_fn = AsyncMock(
            side_effect=[Exception("fail1"), Exception("fail2"), "success"]
        )
        retry_calls = []

        def on_retry(exc, attempt):
            retry_calls.append((str(exc), attempt))

        @with_retry(max_attempts=3, base_delay=0.01, on_retry=on_retry)
        async def test_func():
            return await mock_fn()

        result = await test_func()
        assert result == "success"
        assert len(retry_calls) == 2
        assert retry_calls[0] == ("fail1", 1)
        assert retry_calls[1] == ("fail2", 2)


class TestRetrySyncDecorator:
    """Tests for the retry_sync synchronous decorator."""

    def test_succeeds_first_try(self):
        """Test function that succeeds on first attempt."""
        mock_fn = MagicMock(return_value="success")

        @retry_sync(max_attempts=3)
        def test_func():
            return mock_fn()

        result = test_func()
        assert result == "success"
        assert mock_fn.call_count == 1

    def test_succeeds_after_retry(self):
        """Test function that fails twice then succeeds."""
        mock_fn = MagicMock(
            side_effect=[Exception("fail"), Exception("fail"), "success"]
        )

        @retry_sync(max_attempts=3, base_delay=0.01)
        def test_func():
            return mock_fn()

        result = test_func()
        assert result == "success"
        assert mock_fn.call_count == 3

    def test_fails_after_max_attempts(self):
        """Test function that always fails exhausts retries."""
        mock_fn = MagicMock(side_effect=Exception("always fail"))

        @retry_sync(max_attempts=3, base_delay=0.01)
        def test_func():
            return mock_fn()

        with pytest.raises(Exception, match="always fail"):
            test_func()

        assert mock_fn.call_count == 3


class TestRetryAsyncOperation:
    """Tests for the retry_async_operation function."""

    @pytest.mark.asyncio
    async def test_basic_operation(self):
        """Test basic async operation retry."""

        async def failing_then_success():
            if not hasattr(failing_then_success, "call_count"):
                failing_then_success.call_count = 0
            failing_then_success.call_count += 1
            if failing_then_success.call_count < 3:
                raise Exception("fail")
            return "success"

        result = await retry_async_operation(
            failing_then_success,
            max_attempts=3,
            base_delay=0.01,
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_args(self):
        """Test async operation with arguments."""
        mock_fn = AsyncMock(return_value="result")

        result = await retry_async_operation(
            mock_fn,
            "arg1",
            "arg2",
            max_attempts=3,
            kwarg1="value1",
        )

        assert result == "result"
        mock_fn.assert_called_once_with("arg1", "arg2", kwarg1="value1")


class TestRetrySyncOperation:
    """Tests for the retry_sync_operation function."""

    def test_basic_operation(self):
        """Test basic sync operation retry."""
        call_count = [0]

        def failing_then_success():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("fail")
            return "success"

        result = retry_sync_operation(
            failing_then_success,
            max_attempts=3,
            base_delay=0.01,
        )
        assert result == "success"
        assert call_count[0] == 3

    def test_with_args(self):
        """Test sync operation with arguments."""
        mock_fn = MagicMock(return_value="result")

        result = retry_sync_operation(
            mock_fn,
            "arg1",
            "arg2",
            max_attempts=3,
            kwarg1="value1",
        )

        assert result == "result"
        mock_fn.assert_called_once_with("arg1", "arg2", kwarg1="value1")


class TestRetryConfig:
    """Tests for RetryConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 30.0
        assert config.exponential is True
        assert config.retryable_exceptions == (Exception,)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=10.0,
            exponential=False,
            retryable_exceptions=(ValueError, TypeError),
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 10.0
        assert config.exponential is False
        assert config.retryable_exceptions == (ValueError, TypeError)

    @pytest.mark.asyncio
    async def test_decorator_from_config(self):
        """Test creating decorator from config."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        mock_fn = AsyncMock(side_effect=[Exception("fail"), "success"])

        @config.decorator()
        async def test_func():
            return await mock_fn()

        result = await test_func()
        assert result == "success"
        assert mock_fn.call_count == 2

    def test_sync_decorator_from_config(self):
        """Test creating sync decorator from config."""
        config = RetryConfig(max_attempts=2, base_delay=0.01)
        mock_fn = MagicMock(side_effect=[Exception("fail"), "success"])

        @config.sync_decorator()
        def test_func():
            return mock_fn()

        result = test_func()
        assert result == "success"
        assert mock_fn.call_count == 2


class TestPreConfiguredConfigs:
    """Tests for pre-configured retry configs."""

    def test_rpc_retry_config(self):
        """Test RPC retry configuration."""
        assert RPC_RETRY_CONFIG.max_attempts == 3
        assert RPC_RETRY_CONFIG.base_delay == 1.0
        assert RPC_RETRY_CONFIG.max_delay == 10.0

    def test_http_retry_config(self):
        """Test HTTP retry configuration."""
        assert HTTP_RETRY_CONFIG.max_attempts == 3
        assert HTTP_RETRY_CONFIG.base_delay == 0.5
        assert HTTP_RETRY_CONFIG.max_delay == 5.0

    def test_aggressive_retry_config(self):
        """Test aggressive retry configuration."""
        assert AGGRESSIVE_RETRY_CONFIG.max_attempts == 5
        assert AGGRESSIVE_RETRY_CONFIG.base_delay == 0.5
        assert AGGRESSIVE_RETRY_CONFIG.max_delay == 30.0
