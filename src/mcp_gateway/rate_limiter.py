"""Redis-based sliding-window rate limiter for MCP tool invocations.

Enforces per-user limits: requests-per-minute and requests-per-hour.
When Redis is unavailable the limiter is permissive (always allows).
"""

from __future__ import annotations

import logging
import secrets
import time

logger = logging.getLogger(__name__)

_REDIS_PREFIX = "mcp:rl:"
DEFAULT_RPM = 30
DEFAULT_RPH = 500


class MCPRateLimiter:
    """Per-user sliding-window rate limiter backed by Redis sorted sets."""

    def __init__(
        self,
        redis_client=None,
        requests_per_minute: int = DEFAULT_RPM,
        requests_per_hour: int = DEFAULT_RPH,
    ):
        self._redis = redis_client
        self._rpm = requests_per_minute
        self._rph = requests_per_hour

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    def check_and_increment(self, user_id: int) -> tuple[bool, str | None]:
        """Check rate limits and record the request if allowed.

        Returns ``(allowed, rejection_reason)``.
        """
        if not self.enabled:
            return True, None

        now = time.time()
        member = f"{now}:{secrets.token_hex(4)}"
        try:
            minute_key = f"{_REDIS_PREFIX}{user_id}:min"
            self._redis.zremrangebyscore(minute_key, 0, now - 60)
            if self._redis.zcard(minute_key) >= self._rpm:
                return False, f"Rate limit exceeded: {self._rpm} requests per minute"

            hour_key = f"{_REDIS_PREFIX}{user_id}:hr"
            self._redis.zremrangebyscore(hour_key, 0, now - 3600)
            if self._redis.zcard(hour_key) >= self._rph:
                return False, f"Rate limit exceeded: {self._rph} requests per hour"

            pipe = self._redis.pipeline()
            pipe.zadd(minute_key, {member: now})
            pipe.expire(minute_key, 120)
            pipe.zadd(hour_key, {member: now})
            pipe.expire(hour_key, 7200)
            pipe.execute()

            return True, None
        except Exception as exc:
            logger.warning("Rate limiter Redis error, allowing request: %s", exc)
            return True, None
