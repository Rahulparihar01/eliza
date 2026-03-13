"""TTL caching layer for frequently-read MCP data.

Caches workspace lists, knowledge-base metadata, and connector lists in
Redis with a 5-minute TTL to reduce backend load per the product spec.
Document search results, chat responses, and BI query results are
explicitly *not* cached.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_PREFIX = "mcp:cache:"
_WS_TTL = 300   # 5 minutes
_KB_TTL = 300
_CONN_TTL = 300
_TENANT_CFG_TTL = 120  # 2 minutes — shorter so admin changes propagate quickly


def _safe_key(*parts: str) -> str:
    """Build a cache key suffix from parts, hashing any that contain ':'."""
    segments = []
    for p in parts:
        s = str(p)
        if ":" in s or len(s) > 128:
            s = hashlib.sha256(s.encode()).hexdigest()[:16]
        segments.append(s)
    return ":".join(segments)


class MCPCache:
    """Redis-backed TTL cache for MCP metadata queries."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    @property
    def enabled(self) -> bool:
        return self._redis is not None

    # --- workspace list ---

    def get_workspace_list(self, customer_id: str, search: str | None) -> list[dict[str, Any]] | None:
        return self._get(_safe_key("ws", customer_id, search or ""))

    def set_workspace_list(self, customer_id: str, search: str | None, data: list[dict[str, Any]]) -> None:
        self._set(_safe_key("ws", customer_id, search or ""), data, _WS_TTL)

    # --- knowledge-base list ---

    def get_kb_list(self, workspace_id: int, user_id: int) -> list[dict[str, Any]] | None:
        return self._get(_safe_key("kb", str(workspace_id), str(user_id)))

    def set_kb_list(self, workspace_id: int, user_id: int, data: list[dict[str, Any]]) -> None:
        self._set(_safe_key("kb", str(workspace_id), str(user_id)), data, _KB_TTL)

    # --- data connection list ---

    def get_connection_list(self, customer_id: str, is_enabled: bool | None) -> list[dict[str, Any]] | None:
        return self._get(_safe_key("conn", customer_id, str(is_enabled)))

    def set_connection_list(self, customer_id: str, is_enabled: bool | None, data: list[dict[str, Any]]) -> None:
        self._set(_safe_key("conn", customer_id, str(is_enabled)), data, _CONN_TTL)

    # --- tenant config ---

    def get_tenant_config(self, customer_id: str) -> dict[str, Any] | None:
        return self._get(_safe_key("tcfg", customer_id))

    def set_tenant_config(self, customer_id: str, data: dict[str, Any] | None) -> None:
        self._set(_safe_key("tcfg", customer_id), data, _TENANT_CFG_TTL)

    def invalidate_tenant_config(self, customer_id: str) -> None:
        if not self.enabled:
            return
        try:
            self._redis.delete(_PREFIX + _safe_key("tcfg", customer_id))
        except Exception:
            pass

    # --- invalidation ---

    def invalidate_workspace_list(self, customer_id: str) -> None:
        """Drop all cached workspace lists for a tenant (all search variants)."""
        self._delete_pattern(_safe_key("ws", customer_id) + ":")

    def invalidate_kb_list(self, workspace_id: int) -> None:
        """Drop all cached KB lists for a workspace (all users)."""
        self._delete_pattern(_safe_key("kb", str(workspace_id)) + ":")

    def invalidate_connection_list(self, customer_id: str) -> None:
        """Drop all cached connection lists for a tenant."""
        self._delete_pattern(_safe_key("conn", customer_id) + ":")

    # --- internals ---

    def _get(self, suffix: str) -> Any | None:
        if not self.enabled:
            return None
        try:
            raw = self._redis.get(_PREFIX + suffix)
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return None

    def _set(self, suffix: str, data: Any, ttl: int) -> None:
        if not self.enabled:
            return
        try:
            self._redis.setex(_PREFIX + suffix, ttl, json.dumps(data, default=str))
        except Exception:
            pass

    def _delete_pattern(self, prefix: str) -> None:
        if not self.enabled:
            return
        try:
            cursor = 0
            full_prefix = _PREFIX + prefix
            while True:
                cursor, keys = self._redis.scan(cursor, match=f"{full_prefix}*", count=100)
                if keys:
                    self._redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            pass
