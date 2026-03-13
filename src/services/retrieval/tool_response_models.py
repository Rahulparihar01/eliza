"""
Typed response envelopes for retrieval tools.

All tool responses are returned as JSON so the planner/evaluator/synthesizer
can reason about success vs failure deterministically.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class ToolError(BaseModel):
    """Structured error details for tool calls."""

    message: str
    status_code: Optional[int] = None
    url: Optional[str] = None
    retryable: bool = False
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ToolResponse(BaseModel):
    """Generic tool response envelope."""

    model_config = ConfigDict(extra="allow")

    ok: bool
    source: str
    action: str
    error: Optional[ToolError] = None

    @classmethod
    def success(cls, *, source: str, action: str, payload: Dict[str, Any]) -> "ToolResponse":
        data = {"ok": True, "source": source, "action": action, **payload}
        return cls(**data)

    @classmethod
    def failure(
        cls,
        *,
        source: str,
        action: str,
        message: str,
        status_code: Optional[int] = None,
        url: Optional[str] = None,
        retryable: bool = False,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> "ToolResponse":
        return cls(
            ok=False,
            source=source,
            action=action,
            error=ToolError(
                message=message,
                status_code=status_code,
                url=url,
                retryable=retryable,
                code=code,
                details=details,
            ),
        )

    def to_json(self) -> str:
        """Serialize as compact JSON for flow transport."""
        return json.dumps(self.model_dump(exclude_none=True))
