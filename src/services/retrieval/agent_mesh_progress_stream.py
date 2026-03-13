"""
In-memory progress event store for Agent Mesh live chat updates.

This powers SSE progress streaming keyed by a client-provided request_id.
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


TERMINAL_EVENT_TYPES = {"completed", "failed"}


class AgentMeshProgressStreamStore:
    """Thread-safe in-memory event buffer for Agent Mesh runs."""

    def __init__(self, *, ttl_seconds: int = 900, max_events: int = 400) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_events = max_events
        self._lock = threading.Lock()
        self._streams: Dict[str, Dict[str, Any]] = {}

    def initialize(self, request_id: str) -> None:
        """Ensure a request stream exists."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup_locked(now)
            stream = self._streams.get(request_id)
            if stream is None:
                self._streams[request_id] = {
                    "events": [],
                    "sequence": 0,
                    "terminal": False,
                    "updated_at": now,
                    "created_at": now,
                }
                return
            stream["updated_at"] = now

    def publish(
        self,
        request_id: str,
        *,
        event_type: str,
        message: str,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Append an event for the request and return the event payload."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup_locked(now)
            stream = self._streams.get(request_id)
            if stream is None:
                stream = {
                    "events": [],
                    "sequence": 0,
                    "terminal": False,
                    "updated_at": now,
                    "created_at": now,
                }
                self._streams[request_id] = stream

            stream["sequence"] += 1
            event = {
                "event_id": f"agent-mesh-{uuid.uuid4().hex}",
                "sequence": stream["sequence"],
                "event_type": event_type,
                "message": message,
                "metadata": metadata or {},
                "timestamp": now.isoformat(),
            }
            stream["events"].append(event)
            if len(stream["events"]) > self._max_events:
                # Keep only the latest bounded window.
                stream["events"] = stream["events"][-self._max_events :]

            if event_type in TERMINAL_EVENT_TYPES:
                stream["terminal"] = True
            stream["updated_at"] = now
            return event

    def get_events(self, request_id: str, *, after_sequence: int) -> List[Dict[str, Any]]:
        """Return events with sequence > after_sequence for a request."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup_locked(now)
            stream = self._streams.get(request_id)
            if not stream:
                return []
            stream["updated_at"] = now
            return [
                event
                for event in stream["events"]
                if int(event.get("sequence", 0)) > after_sequence
            ]

    def is_terminal(self, request_id: str) -> bool:
        """Return True if a terminal event was published for request_id."""
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup_locked(now)
            stream = self._streams.get(request_id)
            if not stream:
                return False
            return bool(stream.get("terminal"))

    def _cleanup_locked(self, now: datetime) -> None:
        """Drop expired streams to avoid unbounded memory growth."""
        expiry_cutoff = now - timedelta(seconds=self._ttl_seconds)
        to_delete = [
            request_id
            for request_id, stream in self._streams.items()
            if stream.get("updated_at", now) < expiry_cutoff
        ]
        for request_id in to_delete:
            self._streams.pop(request_id, None)


_STORE = AgentMeshProgressStreamStore()


def get_agent_mesh_progress_store() -> AgentMeshProgressStreamStore:
    """Singleton accessor for Agent Mesh progress store."""
    return _STORE
