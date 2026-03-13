"""Tests for the MCP session store (in-memory fallback path).

Covers: session creation, workspace binding, conversation tracking,
session expiry, serialization, and the acceptance criteria for
"workspace selection persists across tool calls within a session".
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.mcp_gateway.session_store import MCPSessionState, MCPSessionStore, _deserialize, _serialize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(**kw) -> MCPSessionStore:
    """Create a store forced into in-memory fallback mode."""
    store = MCPSessionStore(ttl_seconds=kw.get("ttl_seconds", 3600))
    store._redis = None          # force in-memory path regardless of env
    store._fallback.clear()
    return store


# ---------------------------------------------------------------------------
# Session creation & retrieval
# ---------------------------------------------------------------------------

class TestSessionCreation:
    def test_new_session_has_no_workspace(self):
        store = _make_store()
        state = store.get_or_create("sess-1")
        assert isinstance(state, MCPSessionState)
        assert state.workspace_id is None
        assert state.conversation_id is None
        assert state.last_question_id is None

    def test_same_key_returns_same_state(self):
        store = _make_store()
        first = store.get_or_create("sess-a")
        second = store.get_or_create("sess-a")
        assert first.workspace_id == second.workspace_id

    def test_different_keys_are_independent(self):
        store = _make_store()
        store.update_workspace("sess-a", 10)
        store.update_workspace("sess-b", 20)
        assert store.get_or_create("sess-a").workspace_id == 10
        assert store.get_or_create("sess-b").workspace_id == 20

    def test_touch_updates_timestamp(self):
        store = _make_store()
        state = store.get_or_create("sess-t")
        assert state.updated_at is not None
        old_ts = state.updated_at
        state.touch()
        assert state.updated_at >= old_ts


# ---------------------------------------------------------------------------
# Workspace binding (US-013: session remembers workspace)
# ---------------------------------------------------------------------------

class TestWorkspaceBinding:
    def test_update_workspace_persists(self):
        store = _make_store()
        store.update_workspace("sess-w", 42)
        assert store.get_or_create("sess-w").workspace_id == 42

    def test_switching_workspace_clears_conversation(self):
        store = _make_store()
        store.update_workspace("sess-w", 10)
        store.update_conversation("sess-w", 101)
        store.update_workspace("sess-w", 20)
        state = store.get_or_create("sess-w")
        assert state.workspace_id == 20
        assert state.conversation_id is None

    def test_same_workspace_keeps_conversation(self):
        store = _make_store()
        store.update_workspace("sess-w", 10)
        store.update_conversation("sess-w", 101)
        store.update_workspace("sess-w", 10)
        state = store.get_or_create("sess-w")
        assert state.workspace_id == 10
        assert state.conversation_id == 101


# ---------------------------------------------------------------------------
# Conversation tracking (US-012: MCP conversations persisted)
# ---------------------------------------------------------------------------

class TestConversationTracking:
    def test_update_conversation(self):
        store = _make_store()
        store.update_conversation("sess-c", 55)
        assert store.get_or_create("sess-c").conversation_id == 55

    def test_update_last_question(self):
        store = _make_store()
        store.update_last_question("sess-q", "q-abc")
        assert store.get_or_create("sess-q").last_question_id == "q-abc"


# ---------------------------------------------------------------------------
# Session expiry & cleanup
# ---------------------------------------------------------------------------

class TestExpiry:
    def test_expired_sessions_cleaned_on_access(self):
        store = _make_store(ttl_seconds=60)
        state = store.get_or_create("old-sess")
        state.updated_at = datetime.now(UTC) - timedelta(seconds=120)

        store.get_or_create("new-sess")

        assert "old-sess" not in store._fallback
        assert "new-sess" in store._fallback

    def test_clear_removes_session(self):
        store = _make_store()
        store.get_or_create("sess-del")
        store.clear("sess-del")
        assert "sess-del" not in store._fallback

    def test_clear_nonexistent_is_safe(self):
        store = _make_store()
        store.clear("never-existed")


# ---------------------------------------------------------------------------
# Serialization round-trip (needed for Redis path)
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_roundtrip_preserves_all_fields(self):
        state = MCPSessionState(
            workspace_id=42,
            conversation_id=7,
            last_question_id="q-1",
            metadata={"source": "mcp"},
        )
        state.updated_at = datetime.now(UTC)

        raw = _serialize(state)
        restored = _deserialize(raw)

        assert restored.workspace_id == 42
        assert restored.conversation_id == 7
        assert restored.last_question_id == "q-1"
        assert restored.metadata == {"source": "mcp"}
        assert restored.updated_at is not None

    def test_roundtrip_with_none_fields(self):
        state = MCPSessionState()
        state.touch()
        raw = _serialize(state)
        restored = _deserialize(raw)
        assert restored.workspace_id is None
        assert restored.conversation_id is None

    def test_deserialize_ignores_unknown_keys(self):
        raw = '{"workspace_id": 1, "unknown_future_field": true, "updated_at": null}'
        restored = _deserialize(raw)
        assert restored.workspace_id == 1


# ---------------------------------------------------------------------------
# Redis fallback detection
# ---------------------------------------------------------------------------

class TestRedisDetection:
    def test_in_memory_store_reports_no_redis(self):
        store = _make_store()
        assert not store.using_redis

    def test_redis_client_is_none_for_fallback(self):
        store = _make_store()
        assert store.redis_client is None

    def test_required_redis_raises_when_unavailable(self):
        fake_settings = SimpleNamespace(
            redis_host_url="redis://redis:6379/0",
            mcp_redis_db=2,
            mcp_redis_required=True,
        )

        class FakeRedisClient:
            def ping(self):
                raise RuntimeError("redis down")

        class FakeRedisModule:
            class Redis:
                @staticmethod
                def from_url(*args, **kwargs):
                    return FakeRedisClient()

        with patch("src.core.config.get_settings", return_value=fake_settings):
            with patch.dict("sys.modules", {"redis": FakeRedisModule}):
                with pytest.raises(RuntimeError, match="MCP Redis is required"):
                    MCPSessionStore(ttl_seconds=3600)
