"""Redis-backed MCP session state for workspace-scoped tool execution.

Falls back to in-memory storage when Redis is unavailable unless
``MCP_REDIS_REQUIRED=true`` is configured, in which case MCP startup fails
fast instead.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, fields
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_REDIS_PREFIX = "mcp:session:"
_DEFAULT_TTL = 60 * 60 * 8  # 8 hours
_DEFAULT_REDIS_DB = 2


@dataclass
class MCPSessionState:
    """Mutable state for a single MCP client session."""

    workspace_id: int | None = None
    conversation_id: int | None = None
    last_question_id: str | None = None
    metadata: dict[str, Any] | None = None
    updated_at: datetime | None = None

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)


def _serialize(state: MCPSessionState) -> str:
    return json.dumps(
        {
            "workspace_id": state.workspace_id,
            "conversation_id": state.conversation_id,
            "last_question_id": state.last_question_id,
            "metadata": state.metadata,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
        }
    )


def _deserialize(raw: str | bytes) -> MCPSessionState:
    data = json.loads(raw)
    updated_at = data.get("updated_at")
    if updated_at:
        updated_at = datetime.fromisoformat(updated_at)
    field_names = {f.name for f in fields(MCPSessionState)}
    return MCPSessionState(**{k: v for k, v in {**data, "updated_at": updated_at}.items() if k in field_names})


class MCPSessionStore:
    """Redis-backed session store with automatic in-memory fallback and TTL cleanup."""

    def __init__(self, ttl_seconds: int = _DEFAULT_TTL, redis_url: str | None = None, redis_db: int | None = None):
        self._ttl = max(60, ttl_seconds)
        self._redis = None
        self._fallback: dict[str, MCPSessionState] = {}
        self._lock = Lock()

        self._init_redis(redis_url, redis_db)

    def _init_redis(self, redis_url: str | None, redis_db: int | None) -> None:
        url = redis_url
        db_num = redis_db
        redis_required = False
        if not url:
            try:
                from src.core.config import get_settings

                settings = get_settings()
                url = settings.redis_host_url
                redis_required = bool(getattr(settings, "mcp_redis_required", False))
                if db_num is None:
                    db_num = getattr(settings, "mcp_redis_db", None)
            except Exception:
                url = None
        if db_num is None:
            db_num = _DEFAULT_REDIS_DB

        if url:
            try:
                import redis as _redis

                self._redis = _redis.Redis.from_url(url, decode_responses=True, db=db_num)
                self._redis.ping()
                logger.info("MCP session store using Redis (db=%s)", db_num)
            except Exception as exc:
                if redis_required:
                    raise RuntimeError(
                        "MCP Redis is required but unavailable. "
                        "Check REDIS_URL/REDIS_HOST and set MCP_REDIS_REQUIRED=false "
                        "only for local development."
                    ) from exc
                logger.warning("Redis unavailable for MCP sessions (%s); using in-memory fallback", exc)
                self._redis = None
        elif redis_required:
            raise RuntimeError(
                "MCP Redis is required but no Redis URL could be resolved. "
                "Set REDIS_URL or REDIS_HOST/REDIS_PORT."
            )
        if self._redis is None:
            logger.warning(
                "MCP session store running in-memory. "
                "Sessions will NOT be shared across workers."
            )

    @property
    def using_redis(self) -> bool:
        return self._redis is not None

    @property
    def redis_client(self):
        """Expose the underlying Redis client for shared use by rate limiter / cache."""
        return self._redis

    # --- public API (unchanged contract) ---

    def get_or_create(self, session_key: str) -> MCPSessionState:
        if self.using_redis:
            return self._redis_get_or_create(session_key)
        return self._memory_get_or_create(session_key)

    def update_workspace(self, session_key: str, workspace_id: int | None) -> MCPSessionState:
        state = self.get_or_create(session_key)
        if state.workspace_id != workspace_id:
            state.conversation_id = None
        state.workspace_id = workspace_id
        state.touch()
        self._persist(session_key, state)
        return state

    def update_conversation(self, session_key: str, conversation_id: int | None) -> MCPSessionState:
        state = self.get_or_create(session_key)
        state.conversation_id = conversation_id
        state.touch()
        self._persist(session_key, state)
        return state

    def update_last_question(self, session_key: str, question_id: str | None) -> MCPSessionState:
        state = self.get_or_create(session_key)
        state.last_question_id = question_id
        state.touch()
        self._persist(session_key, state)
        return state

    def clear(self, session_key: str) -> None:
        if self.using_redis:
            try:
                self._redis.delete(_REDIS_PREFIX + session_key)
            except Exception:
                pass
        with self._lock:
            self._fallback.pop(session_key, None)

    # --- Redis backend ---

    def _redis_get_or_create(self, session_key: str) -> MCPSessionState:
        rkey = _REDIS_PREFIX + session_key
        try:
            raw = self._redis.get(rkey)
            if raw:
                state = _deserialize(raw)
                state.touch()
                self._redis.expire(rkey, self._ttl)
                return state
        except Exception:
            pass
        state = MCPSessionState()
        state.touch()
        try:
            self._redis.setex(rkey, self._ttl, _serialize(state))
        except Exception:
            pass
        return state

    def _persist(self, session_key: str, state: MCPSessionState) -> None:
        if self.using_redis:
            try:
                self._redis.setex(_REDIS_PREFIX + session_key, self._ttl, _serialize(state))
                return
            except Exception:
                pass
        with self._lock:
            self._fallback[session_key] = state

    # --- In-memory fallback ---

    def _memory_get_or_create(self, session_key: str) -> MCPSessionState:
        now = datetime.now(UTC)
        with self._lock:
            self._cleanup_expired_locked(now)
            state = self._fallback.get(session_key)
            if state is None:
                state = MCPSessionState()
                self._fallback[session_key] = state
            state.touch()
            return state

    def _cleanup_expired_locked(self, now: datetime) -> None:
        threshold = now - timedelta(seconds=self._ttl)
        expired = [
            k
            for k, v in self._fallback.items()
            if v.updated_at is not None and v.updated_at < threshold
        ]
        for k in expired:
            self._fallback.pop(k, None)
