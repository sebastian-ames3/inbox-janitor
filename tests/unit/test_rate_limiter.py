"""
Unit tests for RateLimiter.

Tests Redis-backed sliding window rate limiting:
- Rate limit checking (within/exceeded)
- Sliding window algorithm
- Increment operations
- Wait with exponential backoff
- Usage monitoring
- Reset functionality

Run tests:
    pytest tests/unit/test_rate_limiter.py -v
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import asyncio

from app.modules.ingest.rate_limiter import (
    RateLimiter,
    RateLimitExceeded,
)


# Test fixtures

@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="0")
    redis.incrby = AsyncMock()
    redis.expire = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def rate_limiter(mock_redis):
    """Create a RateLimiter with mocked Redis."""
    limiter = RateLimiter(emails_per_minute=10)
    limiter._redis = mock_redis
    return limiter


# Test initialization

class TestRateLimiterInit:
    """Test RateLimiter initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        limiter = RateLimiter()
        assert limiter.emails_per_minute == 10
        assert limiter.quota_units_per_minute == 50  # 10 emails * 5 units

    def test_init_with_custom_emails_per_minute(self):
        """Test initialization with custom emails_per_minute."""
        limiter = RateLimiter(emails_per_minute=20)
        assert limiter.emails_per_minute == 20
        assert limiter.quota_units_per_minute == 100  # 20 emails * 5 units

    def test_window_key_format(self):
        """Test Redis key format for time windows."""
        limiter = RateLimiter()
        window_start = datetime(2024, 11, 5, 14, 30, 0)
        key = limiter._get_window_key("user-123", window_start)
        assert key == "rate_limit:user-123:2024-11-05T14:30:00"


# Test check_rate_limit

class TestCheckRateLimit:
    """Test check_rate_limit method."""

    @pytest.mark.asyncio
    async def test_within_limit_returns_true(self, rate_limiter, mock_redis):
        """Test check_rate_limit returns True when within limit."""
        # Setup - no usage in current or previous window
        mock_redis.get.return_value = "0"

        # Execute
        result = await rate_limiter.check_rate_limit(
            user_id="user-123",
            quota_units=5
        )

        # Verify
        assert result is True

    @pytest.mark.asyncio
    async def test_at_limit_returns_false(self, rate_limiter, mock_redis):
        """Test check_rate_limit returns False when at limit."""
        # Setup - current window at limit (50 quota units)
        mock_redis.get.return_value = "50"

        # Execute
        result = await rate_limiter.check_rate_limit(
            user_id="user-123",
            quota_units=5
        )

        # Verify
        assert result is False

    @pytest.mark.asyncio
    async def test_sliding_window_calculation(self, rate_limiter, mock_redis):
        """Test sliding window combines current and previous windows."""
        # Setup - previous window has 30 units, current has 10
        mock_redis.get.side_effect = ["10", "30"]  # current, previous

        # Execute (at 30 seconds into minute, weight = 0.5)
        # weighted_count = (30 * 0.5) + 10 = 25
        # Adding 5 more = 30, which is under limit (50)
        result = await rate_limiter.check_rate_limit(
            user_id="user-123",
            quota_units=5
        )

        # Verify
        assert result is True

    @pytest.mark.asyncio
    async def test_sliding_window_exceeds_limit(self, rate_limiter, mock_redis):
        """Test sliding window detects limit exceeded."""
        # Setup - Use high values that exceed limit regardless of weight
        # At any second: weighted_count = (previous * (1 - weight)) + current
        # Worst case (weight=1): (0 * 0) + 50 = 50, adding 5 = 55 > 50 ✓
        # Best case (weight=0): (50 * 1) + 50 = 100, adding 5 = 105 > 50 ✓
        mock_redis.get.side_effect = ["50", "50"]

        # Execute - Should exceed limit regardless of current second
        result = await rate_limiter.check_rate_limit(
            user_id="user-123",
            quota_units=5
        )

        # Verify
        assert result is False


# Test increment

class TestIncrement:
    """Test increment method."""

    @pytest.mark.asyncio
    async def test_increment_calls_redis_incrby(self, rate_limiter, mock_redis):
        """Test increment increases Redis counter."""
        # Execute
        await rate_limiter.increment(
            user_id="user-123",
            quota_units=5
        )

        # Verify
        mock_redis.incrby.assert_called_once()
        # Check that increment was called with quota_units
        call_args = mock_redis.incrby.call_args
        assert call_args[0][1] == 5  # Second argument is quota_units

    @pytest.mark.asyncio
    async def test_increment_sets_expiry(self, rate_limiter, mock_redis):
        """Test increment sets 2-minute expiry on Redis key."""
        # Execute
        await rate_limiter.increment(
            user_id="user-123",
            quota_units=5
        )

        # Verify
        mock_redis.expire.assert_called_once()
        call_args = mock_redis.expire.call_args
        assert call_args[0][1] == 120  # 2 minutes


# Test check_and_increment

class TestCheckAndIncrement:
    """Test check_and_increment method."""

    @pytest.mark.asyncio
    async def test_check_and_increment_within_limit(self, rate_limiter, mock_redis):
        """Test check_and_increment succeeds when within limit."""
        # Setup
        mock_redis.get.return_value = "0"

        # Execute
        await rate_limiter.check_and_increment(
            user_id="user-123",
            quota_units=5
        )

        # Verify - should increment
        mock_redis.incrby.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_and_increment_exceeds_limit_raises_error(self, rate_limiter, mock_redis):
        """Test check_and_increment raises RateLimitExceeded when over limit."""
        # Setup - at limit
        mock_redis.get.return_value = "50"

        # Execute & Verify
        with pytest.raises(RateLimitExceeded, match="Rate limit exceeded"):
            await rate_limiter.check_and_increment(
                user_id="user-123",
                quota_units=5
            )

        # Should not increment if limit exceeded
        mock_redis.incrby.assert_not_called()


# Test wait_for_rate_limit

class TestWaitForRateLimit:
    """Test wait_for_rate_limit method."""

    @pytest.mark.asyncio
    async def test_wait_immediate_success(self, rate_limiter, mock_redis):
        """Test wait_for_rate_limit succeeds immediately when within limit."""
        # Setup
        mock_redis.get.return_value = "0"

        # Execute
        await rate_limiter.wait_for_rate_limit(
            user_id="user-123",
            quota_units=5,
            max_wait_seconds=10
        )

        # Verify - should increment
        mock_redis.incrby.assert_called_once()

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_wait_retries_with_exponential_backoff(self, mock_sleep, rate_limiter, mock_redis):
        """Test wait_for_rate_limit retries with exponential backoff."""
        # Setup - first check fails, second succeeds
        mock_redis.get.side_effect = ["50", "50", "0", "0"]  # Need 4 calls for 2 attempts

        # Execute
        await rate_limiter.wait_for_rate_limit(
            user_id="user-123",
            quota_units=5,
            max_wait_seconds=10
        )

        # Verify - should have slept once with 1 second
        mock_sleep.assert_called()
        assert mock_sleep.call_count >= 1

    @pytest.mark.asyncio
    @patch("asyncio.sleep", new_callable=AsyncMock)
    @patch("time.time")
    async def test_wait_max_timeout_raises_error(self, mock_time, mock_sleep, rate_limiter, mock_redis):
        """Test wait_for_rate_limit raises error after max wait time."""
        # Setup - always at limit
        mock_redis.get.return_value = "50"

        # Mock time to simulate timeout
        mock_time.side_effect = [0, 0, 61]  # Start at 0, then exceed 60s max_wait

        # Execute & Verify
        with pytest.raises(RateLimitExceeded, match="wait timeout"):
            await rate_limiter.wait_for_rate_limit(
                user_id="user-123",
                quota_units=5,
                max_wait_seconds=60
            )


# Test get_current_usage

class TestGetCurrentUsage:
    """Test get_current_usage method."""

    @pytest.mark.asyncio
    async def test_get_current_usage_no_usage(self, rate_limiter, mock_redis):
        """Test get_current_usage with no usage."""
        # Setup
        mock_redis.get.return_value = "0"

        # Execute
        usage = await rate_limiter.get_current_usage(user_id="user-123")

        # Verify
        assert usage["current_count"] == 0
        assert usage["limit"] == 50
        assert usage["percentage"] == 0.0
        assert usage["remaining"] == 50

    @pytest.mark.asyncio
    async def test_get_current_usage_partial(self, rate_limiter, mock_redis):
        """Test get_current_usage with partial usage."""
        # Setup - 25 units used in current window, 0 in previous
        mock_redis.get.side_effect = ["25", "0"]

        # Execute
        usage = await rate_limiter.get_current_usage(user_id="user-123")

        # Verify
        assert usage["current_count"] == 25
        assert usage["limit"] == 50
        assert usage["percentage"] == 50.0
        assert usage["remaining"] == 25

    @pytest.mark.asyncio
    async def test_get_current_usage_at_limit(self, rate_limiter, mock_redis):
        """Test get_current_usage at limit."""
        # Setup - at limit
        mock_redis.get.side_effect = ["50", "0"]

        # Execute
        usage = await rate_limiter.get_current_usage(user_id="user-123")

        # Verify
        assert usage["current_count"] == 50
        assert usage["percentage"] == 100.0
        assert usage["remaining"] == 0


# Test reset_user_limit

class TestResetUserLimit:
    """Test reset_user_limit method."""

    @pytest.mark.asyncio
    async def test_reset_user_limit_deletes_keys(self, rate_limiter, mock_redis):
        """Test reset_user_limit deletes Redis keys."""
        # Execute
        await rate_limiter.reset_user_limit(user_id="user-123")

        # Verify - should delete both current and previous window keys
        mock_redis.delete.assert_called_once()
        call_args = mock_redis.delete.call_args[0]
        assert len(call_args) == 2  # Should delete 2 keys


# Test close

class TestClose:
    """Test close method."""

    @pytest.mark.asyncio
    async def test_close_closes_redis_connection(self, rate_limiter, mock_redis):
        """Test close closes Redis connection."""
        # Execute
        await rate_limiter.close()

        # Verify
        mock_redis.close.assert_called_once()


# Integration tests with multiple operations

class TestRateLimiterIntegration:
    """Integration tests combining multiple operations."""

    @pytest.mark.asyncio
    async def test_sequential_requests_within_limit(self, rate_limiter, mock_redis):
        """Test multiple sequential requests within limit."""
        # Setup - start with no usage
        mock_redis.get.return_value = "0"

        # Execute - make 5 requests (5 units each = 25 total)
        for i in range(5):
            await rate_limiter.check_and_increment(
                user_id="user-123",
                quota_units=5
            )

        # Verify - should increment 5 times
        assert mock_redis.incrby.call_count == 5

    @pytest.mark.asyncio
    async def test_exceed_limit_on_sixth_request(self, rate_limiter, mock_redis):
        """Test 11th request exceeds limit (10 requests * 5 units = 50, limit is 50)."""
        # Setup - simulate increasing usage
        # Note: check_rate_limit calls get() twice (current + previous window)
        # So we need pairs: (current_window_count, previous_window_count)
        usage_values = [
            "0", "0",   # Request 1: current=0, prev=0, total=0
            "5", "0",   # Request 2: current=5, prev=0, total=5
            "10", "0",  # Request 3: current=10, prev=0, total=10
            "15", "0",  # Request 4: current=15, prev=0, total=15
            "20", "0",  # Request 5: current=20, prev=0, total=20
            "25", "0",  # Request 6: current=25, prev=0, total=25
            "30", "0",  # Request 7: current=30, prev=0, total=30
            "35", "0",  # Request 8: current=35, prev=0, total=35
            "40", "0",  # Request 9: current=40, prev=0, total=40
            "45", "0",  # Request 10: current=45, prev=0, total=45
            "50", "0",  # Request 11: current=50, prev=0, total=50 (SHOULD FAIL)
        ]
        mock_redis.get.side_effect = usage_values + ["0"] * 100  # Add padding

        # Execute - make requests until limit exceeded
        request_count = 0
        for i in range(12):  # Try 12 requests
            try:
                await rate_limiter.check_and_increment(
                    user_id="user-123",
                    quota_units=5
                )
                request_count += 1
            except RateLimitExceeded:
                break

        # Verify - should succeed on first 10 requests, fail on 11th (10 * 5 = 50 = limit)
        assert request_count == 10
