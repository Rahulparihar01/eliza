"""Audit logging helpers for MCP tool invocations.

Every MCP tool call is logged with user identity, tool name, parameters
(sanitized of PII), workspace context, and result status — per the Phase 1
acceptance criteria in the product spec.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = frozenset({"content_base64", "password", "token", "secret", "api_key", "credential"})


async def log_mcp_tool_call(
    *,
    tool_name: str,
    user_id: int | None,
    customer_id: str | None,
    session_key: str | None,
    workspace_id: int | None = None,
    parameters: dict[str, Any] | None = None,
    success: bool,
    error_code: str | None = None,
    duration_ms: float | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Record an MCP tool invocation in the platform audit log."""
    try:
        from src.services.audit_service import AuditAction, AuditService, AuditSeverity

        sanitized = _sanitize(parameters) if parameters else {}

        await AuditService().log_event(
            action=AuditAction.AI_QUERY_EXECUTED,
            user_id=user_id,
            resource_type="mcp_tool",
            resource_id=tool_name,
            new_values={
                "tool_name": tool_name,
                "customer_id": customer_id,
                "session_key": session_key,
                "workspace_id": workspace_id,
                "parameters": sanitized,
                "success": success,
                "error_code": error_code,
                "duration_ms": duration_ms,
                "source": "mcp_gateway",
            },
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_key,
            severity=AuditSeverity.LOW if success else AuditSeverity.MEDIUM,
        )
    except Exception as exc:
        logger.warning("Failed to log MCP audit event for tool=%s: %s", tool_name, exc)


def _sanitize(params: dict[str, Any], *, _depth: int = 0) -> dict[str, Any]:
    """Remove or mask sensitive parameter values before writing to the audit log."""
    if _depth > 5:
        return {"_truncated": True}
    out: dict[str, Any] = {}
    for key, value in params.items():
        if any(s in key.lower() for s in _SENSITIVE_KEYS):
            out[key] = "***REDACTED***"
        elif isinstance(value, dict):
            out[key] = _sanitize(value, _depth=_depth + 1)
        elif isinstance(value, list):
            out[key] = [
                _sanitize(item, _depth=_depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str) and len(value) > 500:
            out[key] = value[:500] + "...(truncated)"
        else:
            out[key] = value
    return out
