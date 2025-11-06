"""
Rate limiter for Gmail API calls using Redis sliding window.

Prevents quota exhaustion by enforcing:
- 10 emails/minute per user (configurable)
- Sliding window algorithm for smooth rate limiting
- Exponential backoff for quota exceeded errors

Gmail API quotas:
- messages.list() = 5 quota units
- messages.get() = 5 quota units
- messages.modify() = 5 quota units
- Daily quota: 1 billion units per day (effectively unlimited for our use case)
- Per-user quota: 250 units per second (we stay well below this)
"""

import logging
import time
from typing import Optional
from datetime import datetime, timedelta
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """
    Redis-backed sliding window rate limiter.

    Usage:
        limiter = RateLimiter()
        await limiter.check_and_increment(user_id='user-123', quota_units=5)
        # If rate limit exceeded, raises RateLimitExceeded
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        emails_per_minute: Optional[int] = None
    ):
        """
        Initialize rate limiter.

        Args:
            redis_url: Redis connection URL (defaults to settings.REDIS_URL)
            emails_per_minute: Max emails per minute per user (defaults to settings.RATE_LIMIT_EMAILS_PER_MIN)
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.emails_per_minute = emails_per_minute or settings.RATE_LIMIT_EMAILS_PER_MIN
        self._redis: Optional[redis.Redis] = None

        # Convert emails/min to quota units/min
        # Each email fetch/modify = 5 quota units
        self.quota_units_per_minute = self.emails_per_minute * 5

    async def _get_redis(self) -> redis.Redis:
        """Get Redis client (lazy initialization)."""
        if not self._redis:
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis

    def _get_window_key(self, user_id: str, window_start: datetime) -> str:
        """
        Get Redis key for a time window.

        Args:
            user_id: User UUID
            window_start: Start of time window

        Returns:
            Redis key string

        Example:
            rate_limit:user-123:2024-11-05T14:30:00
        """
        # Round to minute
        window_str = window_start.strftime("%Y-%m-%dT%H:%M:00")
        return f"rate_limit:{user_id}:{window_str}"

    async def check_rate_limit(
        self,
        user_id: str,
        quota_units: int = 5
    ) -> bool:
        """
        Check if user has exceeded rate limit (non-blocking).

        Args:
            user_id: User UUID
            quota_units: Number of quota units to check (default 5 = 1 email operation)

        Returns:
            True if within limit, False if exceeded

        Usage:
            if await limiter.check_rate_limit(user_id='user-123', quota_units=5):
                # Proceed with API call
            else:
                # Rate limit exceeded, wait or raise error
        """
        redis_client = await self._get_redis()
        now = datetime.utcnow()

        # Get current minute window
        current_window = now.replace(second=0, microsecond=0)
        current_key = self._get_window_key(user_id, current_window)

        # Get previous minute window (for sliding window)
        previous_window = current_window - timedelta(minutes=1)
        previous_key = self._get_window_key(user_id, previous_window)

        # Get counts for both windows
        current_count = int(await redis_client.get(current_key) or 0)
        previous_count = int(await redis_client.get(previous_key) or 0)

        # Calculate weighted count (sliding window)
        seconds_into_minute = now.second
        weight = seconds_into_minute / 60.0  # 0.0 at start of minute, 1.0 at end

        # Sliding window formula:
        # count = (previous_minute * (1 - weight)) + (current_minute)
        weighted_count = (previous_count * (1 - weight)) + current_count

        # Check if adding quota_units would exceed limit
        if weighted_count + quota_units > self.quota_units_per_minute:
            logger.warning(
                f"Rate limit check failed for user {user_id}",
                extra={
                    "user_id": user_id,
                    "current_count": weighted_count,
                    "quota_units": quota_units,
                    "limit": self.quota_units_per_minute
                }
            )
            return False

        return True

    async def increment(
        self,
        user_id: str,
        quota_units: int = 5
    ):
        """
        Increment rate limit counter (call after successful API request).

        Args:
            user_id: User UUID
            quota_units: Number of quota units consumed (default 5)

        Usage:
            # After successful API call
            await limiter.increment(user_id='user-123', quota_units=5)
        """
        redis_client = await self._get_redis()
        now = datetime.utcnow()

        # Get current minute window
        current_window = now.replace(second=0, microsecond=0)
        current_key = self._get_window_key(user_id, current_window)

        # Increment counter
        await redis_client.incrby(current_key, quota_units)

        # Set expiry (2 minutes to cover sliding window)
        await redis_client.expire(current_key, 120)

    async def check_and_increment(
        self,
        user_id: str,
        quota_units: int = 5
    ):
        """
        Check rate limit and increment if allowed (atomic operation).

        Args:
            user_id: User UUID
            quota_units: Number of quota units to consume (default 5)

        Raises:
            RateLimitExceeded: If rate limit exceeded

        Usage:
            await limiter.check_and_increment(user_id='user-123', quota_units=5)
            # Proceed with API call
        """
        # Check rate limit
        if not await self.check_rate_limit(user_id, quota_units):
            raise RateLimitExceeded(
                f"Rate limit exceeded for user {user_id}. "
                f"Limit: {self.emails_per_minute} emails/min"
            )

        # Increment counter
        await self.increment(user_id, quota_units)

    async def wait_for_rate_limit(
        self,
        user_id: str,
        quota_units: int = 5,
        max_wait_seconds: int = 60
    ):
        """
        Wait until rate limit allows request (blocking with exponential backoff).

        Args:
            user_id: User UUID
            quota_units: Number of quota units needed
            max_wait_seconds: Maximum time to wait (default 60 seconds)

        Raises:
            RateLimitExceeded: If max wait time exceeded

        Usage:
            await limiter.wait_for_rate_limit(user_id='user-123', quota_units=5)
            # Rate limit cleared, proceed with API call
        """
        start_time = time.time()
        wait_time = 1  # Start with 1 second

        while True:
            # Check if within limit
            if await self.check_rate_limit(user_id, quota_units):
                # Increment and return
                await self.increment(user_id, quota_units)
                return

            # Check if max wait time exceeded
            elapsed = time.time() - start_time
            if elapsed >= max_wait_seconds:
                raise RateLimitExceeded(
                    f"Rate limit wait timeout for user {user_id} after {max_wait_seconds}s"
                )

            # Log wait
            logger.info(
                f"Rate limit hit for user {user_id}, waiting {wait_time}s",
                extra={
                    "user_id": user_id,
                    "wait_time": wait_time,
                    "elapsed": elapsed
                }
            )

            # Wait with exponential backoff
            await asyncio.sleep(wait_time)
            wait_time = min(wait_time * 2, 16)  # Max 16 seconds between retries

    async def get_current_usage(self, user_id: str) -> dict:
        """
        Get current rate limit usage for user.

        Args:
            user_id: User UUID

        Returns:
            Dict with:
                - current_count: Current quota units used
                - limit: Quota units limit per minute
                - percentage: Usage percentage (0-100)
                - remaining: Quota units remaining

        Usage:
            usage = await limiter.get_current_usage(user_id='user-123')
            print(f"Used: {usage['percentage']}%")
        """
        redis_client = await self._get_redis()
        now = datetime.utcnow()

        # Get current minute window
        current_window = now.replace(second=0, microsecond=0)
        current_key = self._get_window_key(user_id, current_window)

        # Get previous minute window
        previous_window = current_window - timedelta(minutes=1)
        previous_key = self._get_window_key(user_id, previous_window)

        # Get counts
        current_count = int(await redis_client.get(current_key) or 0)
        previous_count = int(await redis_client.get(previous_key) or 0)

        # Calculate weighted count
        seconds_into_minute = now.second
        weight = seconds_into_minute / 60.0
        weighted_count = (previous_count * (1 - weight)) + current_count

        # Calculate percentage and remaining
        percentage = (weighted_count / self.quota_units_per_minute) * 100
        remaining = max(0, self.quota_units_per_minute - weighted_count)

        return {
            "current_count": int(weighted_count),
            "limit": self.quota_units_per_minute,
            "percentage": round(percentage, 2),
            "remaining": int(remaining)
        }

    async def reset_user_limit(self, user_id: str):
        """
        Reset rate limit for user (emergency use only).

        Args:
            user_id: User UUID

        Usage:
            await limiter.reset_user_limit(user_id='user-123')
        """
        redis_client = await self._get_redis()
        now = datetime.utcnow()

        # Delete current and previous minute windows
        current_window = now.replace(second=0, microsecond=0)
        previous_window = current_window - timedelta(minutes=1)

        current_key = self._get_window_key(user_id, current_window)
        previous_key = self._get_window_key(user_id, previous_window)

        await redis_client.delete(current_key, previous_key)

        logger.warning(
            f"Rate limit reset for user {user_id}",
            extra={"user_id": user_id}
        )

    async def close(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global rate limiter instance
_global_limiter: Optional[RateLimiter] = None


async def get_rate_limiter() -> RateLimiter:
    """
    Get global rate limiter instance (singleton).

    Usage:
        limiter = await get_rate_limiter()
        await limiter.check_and_increment(user_id='user-123')
    """
    global _global_limiter
    if not _global_limiter:
        _global_limiter = RateLimiter()
    return _global_limiter


# Import asyncio for sleep function
import asyncio
