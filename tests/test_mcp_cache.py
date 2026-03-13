"""Tests for the MCP caching layer.

Covers: disabled cache behaviour, cache set/get round-trips with mocked
Redis, TTL enforcement, and the spec requirement that workspace lists,
KB metadata, and connector lists are cached at 5-minute TTL.
"""

import json
from unittest.mock import MagicMock, call

import pytest

from src.mcp_gateway.cache import MCPCache, _CONN_TTL, _KB_TTL, _PREFIX, _WS_TTL, _safe_key


# ---------------------------------------------------------------------------
# Disabled cache (no Redis)
# ---------------------------------------------------------------------------

class TestDisabledCache:
    def test_get_returns_none(self):
        cache = MCPCache(redis_client=None)
        assert cache.get_workspace_list("t1", None) is None
        assert cache.get_kb_list(1, 1) is None
        assert cache.get_connection_list("t1", True) is None

    def test_set_is_noop(self):
        cache = MCPCache(redis_client=None)
        cache.set_workspace_list("t1", None, [{"id": 1}])
        assert cache.get_workspace_list("t1", None) is None

    def test_enabled_is_false(self):
        cache = MCPCache(redis_client=None)
        assert not cache.enabled


# ---------------------------------------------------------------------------
# Cache with mocked Redis
# ---------------------------------------------------------------------------

class TestCacheWithRedis:
    def _mock_redis(self, stored=None):
        mock = MagicMock()
        mock.get = MagicMock(return_value=json.dumps(stored) if stored else None)
        mock.setex = MagicMock()
        return mock

    def test_workspace_list_roundtrip(self):
        data = [{"id": 1, "name": "WS1"}, {"id": 2, "name": "WS2"}]
        redis = self._mock_redis(stored=data)
        cache = MCPCache(redis_client=redis)

        cache.set_workspace_list("tenant1", "search", data)
        redis.setex.assert_called_once()
        args = redis.setex.call_args
        assert args[0][1] == _WS_TTL

        result = cache.get_workspace_list("tenant1", "search")
        assert result == data

    def test_kb_list_roundtrip(self):
        data = [{"id": 10, "name": "KB1"}]
        redis = self._mock_redis(stored=data)
        cache = MCPCache(redis_client=redis)

        cache.set_kb_list(42, 1, data)
        args = redis.setex.call_args
        assert args[0][1] == _KB_TTL

        result = cache.get_kb_list(42, 1)
        assert result == data

    def test_connection_list_roundtrip(self):
        data = [{"connector_id": "c1", "type": "postgres"}]
        redis = self._mock_redis(stored=data)
        cache = MCPCache(redis_client=redis)

        cache.set_connection_list("tenant1", True, data)
        args = redis.setex.call_args
        assert args[0][1] == _CONN_TTL

        result = cache.get_connection_list("tenant1", True)
        assert result == data

    def test_cache_miss_returns_none(self):
        redis = self._mock_redis(stored=None)
        cache = MCPCache(redis_client=redis)
        assert cache.get_workspace_list("t1", None) is None

    def test_ttls_are_five_minutes(self):
        assert _WS_TTL == 300
        assert _KB_TTL == 300
        assert _CONN_TTL == 300

    def test_graceful_on_redis_error(self):
        redis = MagicMock()
        redis.get.side_effect = ConnectionError("Redis down")
        redis.setex.side_effect = ConnectionError("Redis down")
        cache = MCPCache(redis_client=redis)

        cache.set_workspace_list("t1", None, [{"id": 1}])
        result = cache.get_workspace_list("t1", None)
        assert result is None


# ---------------------------------------------------------------------------
# Safe key escaping
# ---------------------------------------------------------------------------

class TestSafeKey:
    def test_normal_values_unchanged(self):
        key = _safe_key("ws", "tenant1", "search")
        assert key == "ws:tenant1:search"

    def test_colon_in_part_is_hashed(self):
        key = _safe_key("ws", "tenant:with:colons", "")
        parts = key.split(":")
        assert parts[0] == "ws"
        assert parts[1] != "tenant:with:colons"
        assert len(parts[1]) == 16

    def test_long_value_is_hashed(self):
        long_val = "x" * 200
        key = _safe_key("kb", long_val, "1")
        parts = key.split(":")
        assert len(parts[1]) == 16

    def test_integer_parts_pass_through(self):
        key = _safe_key("kb", "42", "7")
        assert key == "kb:42:7"
