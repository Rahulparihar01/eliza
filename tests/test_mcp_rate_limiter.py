"""Tests for the MCP rate limiter.

Covers: disabled limiter passthrough, enabled detection, per-user RPM/RPH
enforcement, and sliding-window cleanup.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.mcp_gateway.rate_limiter import DEFAULT_RPH, DEFAULT_RPM, MCPRateLimiter


# ---------------------------------------------------------------------------
# Disabled limiter (no Redis)
# ---------------------------------------------------------------------------

class TestDisabledLimiter:
    def test_always_allows_when_disabled(self):
        limiter = MCPRateLimiter(redis_client=None)
        for _ in range(100):
            allowed, reason = limiter.check_and_increment(user_id=1)
            assert allowed is True
            assert reason is None

    def test_enabled_is_false(self):
        limiter = MCPRateLimiter(redis_client=None)
        assert not limiter.enabled


# ---------------------------------------------------------------------------
# Enabled detection
# ---------------------------------------------------------------------------

class TestEnabledDetection:
    def test_enabled_with_redis_client(self):
        limiter = MCPRateLimiter(redis_client=MagicMock())
        assert limiter.enabled

    def test_custom_limits_stored(self):
        limiter = MCPRateLimiter(redis_client=None, requests_per_minute=10, requests_per_hour=100)
        assert limiter._rpm == 10
        assert limiter._rph == 100

    def test_default_limits(self):
        limiter = MCPRateLimiter(redis_client=None)
        assert limiter._rpm == DEFAULT_RPM
        assert limiter._rph == DEFAULT_RPH


# ---------------------------------------------------------------------------
# Rate limiting with mocked Redis
# ---------------------------------------------------------------------------

class TestRateLimitingLogic:
    def _mock_redis(self, minute_count=0, hour_count=0):
        """Create a mock Redis client that reports specific counts."""
        mock = MagicMock()
        mock.zremrangebyscore = MagicMock()
        mock.zcard = MagicMock(side_effect=[minute_count, hour_count])
        mock.pipeline.return_value = MagicMock(
            __enter__=MagicMock(return_value=MagicMock()),
            __exit__=MagicMock(return_value=False),
            zadd=MagicMock(),
            expire=MagicMock(),
            execute=MagicMock(),
        )
        return mock

    def test_allows_when_under_limits(self):
        mock_redis = self._mock_redis(minute_count=5, hour_count=50)
        limiter = MCPRateLimiter(redis_client=mock_redis, requests_per_minute=30, requests_per_hour=500)
        allowed, reason = limiter.check_and_increment(user_id=1)
        assert allowed is True
        assert reason is None

    def test_rejects_when_minute_limit_exceeded(self):
        mock_redis = self._mock_redis(minute_count=30, hour_count=50)
        limiter = MCPRateLimiter(redis_client=mock_redis, requests_per_minute=30, requests_per_hour=500)
        allowed, reason = limiter.check_and_increment(user_id=1)
        assert allowed is False
        assert "30 requests per minute" in reason

    def test_rejects_when_hour_limit_exceeded(self):
        mock_redis = self._mock_redis(minute_count=5, hour_count=500)
        limiter = MCPRateLimiter(redis_client=mock_redis, requests_per_minute=30, requests_per_hour=500)
        allowed, reason = limiter.check_and_increment(user_id=1)
        assert allowed is False
        assert "500 requests per hour" in reason

    def test_graceful_on_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.zremrangebyscore.side_effect = ConnectionError("Redis down")
        limiter = MCPRateLimiter(redis_client=mock_redis)
        allowed, reason = limiter.check_and_increment(user_id=1)
        assert allowed is True
        assert reason is None

    def test_cleans_old_entries(self):
        mock_redis = self._mock_redis(minute_count=0, hour_count=0)
        limiter = MCPRateLimiter(redis_client=mock_redis, requests_per_minute=30, requests_per_hour=500)
        limiter.check_and_increment(user_id=42)
        assert mock_redis.zremrangebyscore.call_count == 2
