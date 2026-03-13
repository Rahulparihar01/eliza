"""MCP gateway for exposing workspace chat and data tools."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
import time
import threading
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from src.mcp_gateway.audit import log_mcp_tool_call
from src.mcp_gateway.cache import MCPCache
from src.mcp_gateway.rate_limiter import MCPRateLimiter
from src.mcp_gateway.session_store import MCPSessionStore

logger = logging.getLogger(__name__)

# Heavy platform imports are deferred to function scope so that importing
# this module does not trigger the entire model/service/task graph (which
# pulls in spaCy, document processing, etc.).  The helpers below provide
# lazy access with module-level caching.

if TYPE_CHECKING:
    from src.middleware.authorization import auth_middleware as _auth_mw_type  # noqa: F401

if TYPE_CHECKING:
    from src.core.auth_context import CurrentUserContext

try:
    from mcp.server.fastmcp import Context, FastMCP

    MCP_SDK_AVAILABLE = True
except Exception:  # pragma: no cover - exercised by runtime fallback
    Context = Any  # type: ignore[assignment]
    FastMCP = Any  # type: ignore[assignment]
    MCP_SDK_AVAILABLE = False


# ---------- singletons (initialised once, shared across requests) ----------

SESSION_STORE = MCPSessionStore()
RATE_LIMITER = MCPRateLimiter(redis_client=SESSION_STORE.redis_client)
CACHE = MCPCache(redis_client=SESSION_STORE.redis_client)


# ---------- lazy imports (keeps module import lightweight) ----------

_lazy_cache: dict[str, Any] = {}
_lazy_lock = threading.Lock()


def _lazy(name: str):
    """Return a lazily-imported platform symbol.  Cached after first access."""
    if name in _lazy_cache:
        return _lazy_cache[name]

    with _lazy_lock:
        if name in _lazy_cache:
            return _lazy_cache[name]

        if name == "database":
            from src.models import database as mod
        elif name == "auth_middleware":
            from src.middleware.authorization import auth_middleware as mod  # type: ignore[assignment]
        elif name == "BIQuestion":
            from src.models.business_intelligence import BIQuestion as mod  # type: ignore[assignment]
        elif name == "QuestionStatus":
            from src.models.business_intelligence import QuestionStatus as mod  # type: ignore[assignment]
        elif name == "Document":
            from src.models.document import Document as mod  # type: ignore[assignment]
        elif name == "DocumentChunk":
            from src.models.document import DocumentChunk as mod  # type: ignore[assignment]
        elif name == "RAGFlowDomain":
            from src.models.ragflow_domain import RAGFlowDomain as mod  # type: ignore[assignment]
        elif name == "KnowledgeBase":
            from src.models.workspace import KnowledgeBase as mod  # type: ignore[assignment]
        elif name == "KnowledgeBasePermissionType":
            from src.models.workspace import KnowledgeBasePermissionType as mod  # type: ignore[assignment]
        elif name == "BusinessIntelligenceService":
            from src.services.business_intelligence_service import BusinessIntelligenceService as mod  # type: ignore[assignment]
        elif name == "ConnectorService":
            from src.services.ingestion.connector_service import ConnectorService as mod  # type: ignore[assignment]
        elif name == "KnowledgeBaseAccessService":
            from src.services.knowledge_base_access_service import KnowledgeBaseAccessService as mod  # type: ignore[assignment]
        elif name == "NativeRAGService":
            from src.services.native_rag_service import NativeRAGService as mod  # type: ignore[assignment]
        elif name == "SettingsService":
            from src.services.settings_service import SettingsService as mod  # type: ignore[assignment]
        elif name == "process_bi_question":
            from src.tasks.business_intelligence_tasks import process_bi_question as mod  # type: ignore[assignment]
        else:
            raise ImportError(f"Unknown lazy import: {name}")

        _lazy_cache[name] = mod
        return mod


# ---------- helpers ----------


def _error(message: str, code: str = "bad_request", details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, **payload}


def _ensure_db_session():
    database = _lazy("database")
    if database.SessionLocal is None:
        database.init_database()
    return database.SessionLocal()


def _has_permission(user: CurrentUserContext, permission: str) -> bool:
    return user.is_superuser or user.has_permission(permission)


def _coerce_question_status(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


_SESSION_KEY_RE = re.compile(r"[^a-zA-Z0-9_\-.]")
_MAX_SESSION_KEY_LEN = 128


def _safe_session_segment(raw: str) -> str:
    """Strip non-alphanumeric characters and cap length to prevent key injection."""
    return _SESSION_KEY_RE.sub("", raw.strip())[:_MAX_SESSION_KEY_LEN]


def _resolve_session_key(
    *,
    user: CurrentUserContext,
    ctx: Context,
    request: Any,
    explicit_session_id: str | None,
) -> str:
    if explicit_session_id:
        cleaned = _safe_session_segment(explicit_session_id)
        if cleaned:
            return f"user:{user.user_id}:session:{cleaned}"

    header_session = request.headers.get("x-eliza-mcp-session")
    if header_session:
        cleaned = _safe_session_segment(header_session)
        if cleaned:
            return f"user:{user.user_id}:header:{cleaned}"

    client_id = getattr(ctx, "client_id", None)
    if client_id:
        return f"user:{user.user_id}:client:{_safe_session_segment(str(client_id))}"

    return f"user:{user.user_id}:default"


async def _authenticate_ctx(ctx: Context) -> tuple[CurrentUserContext, Any] | tuple[None, None]:
    try:
        request_context = ctx.request_context
    except Exception:
        return None, None

    request = getattr(request_context, "request", None)
    if request is None:
        return None, None

    auth_header = request.headers.get("authorization", "").strip()
    if not auth_header.lower().startswith("bearer "):
        return None, None

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None, None

    try:
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await _lazy("auth_middleware").get_current_user(request=request, credentials=credentials)
        return user, request
    except Exception:
        logger.debug("MCP authentication failed", exc_info=True)
        return None, None


def _resolve_workspace_id(
    *,
    requested_workspace_id: int | None,
    session_workspace_id: int | None,
) -> int | None:
    if requested_workspace_id is not None:
        return requested_workspace_id
    return session_workspace_id


def _serialize_question(question) -> dict[str, Any]:
    status = _coerce_question_status(question.status)
    payload: dict[str, Any] = {
        "question_id": question.question_id,
        "status": status,
        "original_question": question.original_question,
        "error_message": question.error_message,
    }
    if question.result is not None:
        payload["result"] = {
            "answer": question.result.analysis_text,
            "executive_summary": question.result.executive_summary,
            "key_findings": question.result.key_findings or [],
            "recommendations": question.result.recommendations or [],
            "confidence_score": question.result.confidence_score,
            "data_sources_used": question.result.data_sources_used or [],
            "visualizations": question.result.visualizations or {},
        }
    return payload


def _client_ip(request: Any) -> str | None:
    try:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else None
    except Exception:
        return None


def _client_ua(request: Any) -> str | None:
    try:
        return request.headers.get("user-agent")
    except Exception:
        return None


# ---------- tenant config enforcement ----------


def _load_tenant_config(customer_id: str) -> dict[str, Any] | None:
    """Load the active MCPServerConfig for a tenant, with caching.

    Returns a dict with ``allowed_workspace_ids`` and ``allowed_tool_names``
    (both may be empty lists meaning "no restriction"), or ``None`` when no
    config row exists (which also means "no restriction").

    When Redis is unavailable caching is a no-op and every call hits the DB.
    This is consistent with the other MCPCache methods and acceptable at MCP
    request volume.
    """
    cached = CACHE.get_tenant_config(customer_id)
    if cached is not None:
        return cached if cached != {} else None

    db = _ensure_db_session()
    try:
        from src.models.mcp_config import MCPServerConfig

        config = (
            db.query(MCPServerConfig)
            .filter(
                MCPServerConfig.customer_id == customer_id,
                MCPServerConfig.is_enabled.is_(True),
            )
            .order_by(MCPServerConfig.created_at.desc())
            .first()
        )
        if config is None:
            CACHE.set_tenant_config(customer_id, {})
            return None

        result: dict[str, Any] = {
            "allowed_workspace_ids": config.allowed_workspace_ids or [],
            "allowed_tool_names": config.allowed_tool_names or [],
        }
        CACHE.set_tenant_config(customer_id, result)
        return result
    except Exception:
        logger.debug("Failed to load tenant MCP config for %s", customer_id, exc_info=True)
        return None
    finally:
        db.close()


def _check_tool_allowed(
    cfg: dict[str, Any] | None,
    tool_name: str,
) -> tuple[bool, str | None]:
    """Check whether *tool_name* is permitted by a pre-loaded tenant config.

    An empty ``allowed_tool_names`` list (or no config) means all tools are
    allowed.
    """
    if cfg is None:
        return True, None
    allowed = cfg.get("allowed_tool_names") or []
    if not allowed:
        return True, None
    if tool_name in allowed:
        return True, None
    return False, f"Tool '{tool_name}' is not enabled for your organisation."


def _check_workspace_allowed(
    cfg: dict[str, Any] | None,
    workspace_id: int,
) -> tuple[bool, str | None]:
    """Check whether *workspace_id* is permitted by a pre-loaded tenant config.

    An empty ``allowed_workspace_ids`` list (or no config) means all
    workspaces are allowed.  The error message is intentionally generic to
    avoid confirming workspace existence to restricted callers.
    """
    if cfg is None:
        return True, None
    allowed = cfg.get("allowed_workspace_ids") or []
    if not allowed:
        return True, None
    if workspace_id in allowed:
        return True, None
    return False, "Access denied for the requested workspace."


def _apply_workspace_filter(
    cfg: dict[str, Any] | None,
    workspaces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter a workspace list to only those permitted by a pre-loaded config."""
    if cfg is None:
        return workspaces
    allowed = cfg.get("allowed_workspace_ids") or []
    if not allowed:
        return workspaces
    allowed_set = set(allowed)
    return [ws for ws in workspaces if ws.get("id") in allowed_set]


# ---------- constants ----------

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_MAX_FILENAME_LEN = 255
_SAFE_FILENAME_RE = re.compile(r"^[\w\-. ()\[\]]+$")

# ---------- fallback when MCP SDK is missing ----------


def _build_fallback_app() -> Starlette:
    async def unavailable(_request):
        return JSONResponse(
            {
                "ok": False,
                "error": {
                    "code": "mcp_unavailable",
                    "message": "MCP SDK is not installed in this deployment image.",
                },
            },
            status_code=503,
        )

    return Starlette(routes=[
        Route("/", unavailable, methods=["GET", "POST"]),
        Route("/sse", unavailable, methods=["GET"]),
        Route("/messages", unavailable, methods=["GET", "POST"]),
    ])


# ---------- MCP server builder ----------


def _build_mcp_server() -> FastMCP:
    mcp = FastMCP(
        name="eliza-chat",
        instructions=(
            "Eliza workspace tools. Select a workspace before chat/search actions when needed."
        ),
        streamable_http_path="/",
        sse_path="/sse",
        message_path="/messages",
    )

    # ======================================================================
    # list_workspaces
    # ======================================================================

    @mcp.tool(name="list_workspaces", structured_output=True)
    async def list_workspaces(
        ctx: Context,
        search: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "list_workspaces")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "assistant:access"):
                _audit_ok, _audit_err = False, "access_denied"
                return _error("You do not have access to workspaces.", code="access_denied")

            cached = CACHE.get_workspace_list(user.customer_id, search)
            if cached is not None:
                session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)
                state = SESSION_STORE.get_or_create(session_key)
                filtered = _apply_workspace_filter(tenant_cfg, cached)
                return _ok({"session_id": session_key, "active_workspace_id": state.workspace_id, "workspaces": filtered})

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)
            session_state = SESSION_STORE.get_or_create(session_key)

            db = _ensure_db_session()
            try:
                _RFD = _lazy("RAGFlowDomain")
                query = (
                    db.query(_RFD)
                    .options(joinedload(_RFD.template))
                    .filter(_RFD.customer_id == user.customer_id, _RFD.is_active)
                )
                if search:
                    search_term = f"%{search.strip()}%"
                    query = query.filter(
                        or_(
                            _RFD.name.ilike(search_term),
                            _RFD.display_name.ilike(search_term),
                        )
                    )
                workspaces = query.order_by(_RFD.display_name).all()
                ws_list = [
                    {
                        "id": ws.id,
                        "name": ws.name,
                        "display_name": ws.display_name,
                        "description": ws.description,
                        "status": ws.status.value if hasattr(ws.status, "value") else str(ws.status),
                        "template_name": ws.template.name if ws.template else None,
                        "template_display_name": ws.template.display_name if ws.template else None,
                        "document_count": ws.document_count,
                        "knowledge_base_count": len(ws.knowledge_bases or []),
                    }
                    for ws in workspaces
                ]
                CACHE.set_workspace_list(user.customer_id, search, ws_list)
                filtered = _apply_workspace_filter(tenant_cfg, ws_list)
                return _ok({"session_id": session_key, "active_workspace_id": session_state.workspace_id, "workspaces": filtered})
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("list_workspaces failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="list_workspaces", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                parameters={"search": search}, success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # select_workspace
    # ======================================================================

    @mcp.tool(name="select_workspace", structured_output=True)
    async def select_workspace(
        workspace_id: int,
        ctx: Context,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "select_workspace")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            ws_ok, ws_reason = _check_workspace_allowed(tenant_cfg, workspace_id)
            if not ws_ok:
                _audit_ok, _audit_err = False, "workspace_not_allowed"
                return _error(ws_reason, code="workspace_not_allowed")

            if not _has_permission(user, "assistant:access"):
                return _error("You do not have access to workspaces.", code="access_denied")

            db = _ensure_db_session()
            try:
                _RFD = _lazy("RAGFlowDomain")
                workspace = (
                    db.query(_RFD)
                    .filter(
                        _RFD.id == workspace_id,
                        _RFD.customer_id == user.customer_id,
                        _RFD.is_active,
                    )
                    .first()
                )
                if workspace is None:
                    return _error("Workspace not found.", code="not_found")

                session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)
                SESSION_STORE.update_workspace(session_key, workspace_id)
                return _ok({
                    "session_id": session_key,
                    "workspace": {
                        "id": workspace.id,
                        "name": workspace.name,
                        "display_name": workspace.display_name,
                    },
                })
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("select_workspace failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="select_workspace", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                workspace_id=workspace_id, parameters={"workspace_id": workspace_id},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # list_knowledge_bases
    # ======================================================================

    @mcp.tool(name="list_knowledge_bases", structured_output=True)
    async def list_knowledge_bases(
        ctx: Context,
        workspace_id: int | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "list_knowledge_bases")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "assistant:access"):
                return _error("You do not have access to knowledge bases.", code="access_denied")

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)
            state = SESSION_STORE.get_or_create(session_key)
            active_workspace_id = _resolve_workspace_id(requested_workspace_id=workspace_id, session_workspace_id=state.workspace_id)
            if active_workspace_id is None:
                return _error("No active workspace. Call select_workspace first.", code="workspace_required")

            ws_ok, ws_reason = _check_workspace_allowed(tenant_cfg, active_workspace_id)
            if not ws_ok:
                _audit_ok, _audit_err = False, "workspace_not_allowed"
                return _error(ws_reason, code="workspace_not_allowed")

            cached = CACHE.get_kb_list(active_workspace_id, user.user_id)
            if cached is not None:
                return _ok({"session_id": session_key, "workspace_id": active_workspace_id, "knowledge_bases": cached})

            db = _ensure_db_session()
            try:
                _RFD = _lazy("RAGFlowDomain")
                workspace = (
                    db.query(_RFD)
                    .filter(_RFD.id == active_workspace_id, _RFD.customer_id == user.customer_id, _RFD.is_active)
                    .first()
                )
                if workspace is None:
                    return _error("Workspace not found.", code="not_found")

                access_service = _lazy("KnowledgeBaseAccessService")(db)
                kb_ids = access_service.resolve_accessible_kb_ids(workspace_id=workspace.id, user=user, required_permission=_lazy("KnowledgeBasePermissionType").READ)
                if not kb_ids:
                    return _ok({"session_id": session_key, "workspace_id": workspace.id, "knowledge_bases": []})

                _KB = _lazy("KnowledgeBase")
                knowledge_bases = (
                    db.query(_KB)
                    .filter(_KB.workspace_id == workspace.id, _KB.id.in_(kb_ids), _KB.is_active)
                    .order_by(_KB.created_at.desc())
                    .all()
                )
                kb_list = [
                    {
                        "id": kb.id,
                        "name": kb.name,
                        "description": kb.description,
                        "status": kb.status,
                        "document_count": kb.document_count,
                        "chunk_count": kb.chunk_count,
                    }
                    for kb in knowledge_bases
                ]
                CACHE.set_kb_list(active_workspace_id, user.user_id, kb_list)
                return _ok({"session_id": session_key, "workspace_id": workspace.id, "knowledge_bases": kb_list})
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("list_knowledge_bases failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="list_knowledge_bases", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                workspace_id=workspace_id, parameters={"workspace_id": workspace_id},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # search_documents
    # ======================================================================

    @mcp.tool(name="search_documents", structured_output=True)
    async def search_documents(
        query: str,
        ctx: Context,
        workspace_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        limit: int = 10,
        similarity_threshold: float | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "search_documents")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "assistant:access"):
                return _error("You do not have access to document search.", code="access_denied")

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)
            state = SESSION_STORE.get_or_create(session_key)
            active_workspace_id = _resolve_workspace_id(requested_workspace_id=workspace_id, session_workspace_id=state.workspace_id)
            if active_workspace_id is None:
                return _error("No active workspace. Call select_workspace first.", code="workspace_required")

            ws_ok, ws_reason = _check_workspace_allowed(tenant_cfg, active_workspace_id)
            if not ws_ok:
                _audit_ok, _audit_err = False, "workspace_not_allowed"
                return _error(ws_reason, code="workspace_not_allowed")

            db = _ensure_db_session()
            try:
                rag_service = _lazy("NativeRAGService")(db)
                workspace = await rag_service.get_domain(active_workspace_id, user.customer_id)
                if workspace is None:
                    return _error("Workspace not found.", code="not_found")

                access_service = _lazy("KnowledgeBaseAccessService")(db)
                try:
                    kb_scope = access_service.resolve_effective_kb_scope(
                        workspace_id=workspace.id, user=user,
                        requested_kb_ids=knowledge_base_ids,
                        required_permission=_lazy("KnowledgeBasePermissionType").READ,
                    )
                except PermissionError as exc:
                    return _error(str(exc), code="access_denied")
                except ValueError as exc:
                    return _error(str(exc), code="bad_request")

                effective_threshold = similarity_threshold
                if effective_threshold is None:
                    effective_threshold = float((workspace.similarity_threshold or 0) / 100.0)

                chunks = await rag_service.retrieve(
                    domain_id=workspace.id, customer_id=user.customer_id,
                    query=query, top_k=max(1, min(limit, 100)),
                    min_score=effective_threshold, knowledge_base_ids=kb_scope,
                )
                return _ok({
                    "session_id": session_key,
                    "workspace_id": workspace.id,
                    "query": query,
                    "results": [
                        {
                            "content": item.get("text", ""),
                            "document_name": item.get("document_name"),
                            "document_id": item.get("document_id"),
                            "similarity": item.get("score"),
                            "metadata": item.get("metadata") or {},
                        }
                        for item in chunks
                    ],
                })
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("search_documents failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="search_documents", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                workspace_id=workspace_id,
                parameters={"query": query, "limit": limit},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # chat
    # ======================================================================

    @mcp.tool(name="chat", structured_output=True)
    async def chat(
        message: str,
        ctx: Context,
        workspace_id: int | None = None,
        conversation_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        top_k: int = 5,
        similarity_threshold: float | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "chat")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "assistant:access"):
                return _error("You do not have access to chat.", code="access_denied")

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)
            state = SESSION_STORE.get_or_create(session_key)
            active_workspace_id = _resolve_workspace_id(requested_workspace_id=workspace_id, session_workspace_id=state.workspace_id)
            if active_workspace_id is None:
                return _error("No active workspace. Call select_workspace first.", code="workspace_required")

            ws_ok, ws_reason = _check_workspace_allowed(tenant_cfg, active_workspace_id)
            if not ws_ok:
                _audit_ok, _audit_err = False, "workspace_not_allowed"
                return _error(ws_reason, code="workspace_not_allowed")

            db = _ensure_db_session()
            try:
                rag_service = _lazy("NativeRAGService")(db)
                workspace = await rag_service.get_domain(active_workspace_id, user.customer_id)
                if workspace is None:
                    return _error("Workspace not found.", code="not_found")

                access_service = _lazy("KnowledgeBaseAccessService")(db)
                try:
                    kb_scope = access_service.resolve_effective_kb_scope(
                        workspace_id=workspace.id, user=user,
                        requested_kb_ids=knowledge_base_ids,
                        required_permission=_lazy("KnowledgeBasePermissionType").READ,
                    )
                except PermissionError as exc:
                    return _error(str(exc), code="access_denied")
                except ValueError as exc:
                    return _error(str(exc), code="bad_request")

                active_conversation_id = conversation_id or state.conversation_id
                if active_conversation_id is not None:
                    existing = await rag_service.get_conversation(active_conversation_id, user.customer_id)
                    if existing is None or existing.domain_id != workspace.id or existing.user_id != user.user_id:
                        active_conversation_id = None

                if active_conversation_id is None:
                    conversation = await rag_service.create_conversation(
                        domain_id=workspace.id,
                        customer_id=user.customer_id,
                        user_id=user.user_id,
                        title=message[:120],
                        source="mcp",
                    )
                    active_conversation_id = conversation.id

                effective_threshold = similarity_threshold
                if effective_threshold is None:
                    effective_threshold = float((workspace.similarity_threshold or 0) / 100.0)

                response = await rag_service.chat(
                    domain_id=workspace.id, customer_id=user.customer_id,
                    question=message, conversation_id=active_conversation_id,
                    user_id=user.user_id, top_k=max(1, min(top_k, 100)),
                    min_score=effective_threshold, knowledge_base_ids=kb_scope,
                )
                SESSION_STORE.update_workspace(session_key, workspace.id)
                SESSION_STORE.update_conversation(session_key, active_conversation_id)

                assistant_message = {
                    "id": response.get("assistant_message_id"),
                    "role": "assistant",
                    "content": response.get("answer", ""),
                    "chunks": response.get("chunks", []),
                    "created_at": response.get("assistant_message_created_at"),
                }
                user_message = {
                    "id": response.get("user_message_id"),
                    "role": "user",
                    "content": message,
                    "created_at": response.get("user_message_created_at"),
                }
                return _ok({
                    "session_id": session_key,
                    "workspace_id": workspace.id,
                    "conversation_id": active_conversation_id,
                    "assistant_message": assistant_message,
                    "user_message": user_message,
                })
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("chat failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="chat", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                workspace_id=workspace_id,
                parameters={"message_length": len(message), "top_k": top_k},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # ask_question
    # ======================================================================

    @mcp.tool(name="ask_question", structured_output=True)
    async def ask_question(
        question: str,
        ctx: Context,
        company_hr_dataset: str | None = None,
        wait_for_result: bool = False,
        timeout_seconds: int = 120,
        poll_interval_seconds: float = 2.0,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "ask_question")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "assistant:questions:ask"):
                return _error("You do not have access to ask questions.", code="access_denied")

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)

            db = _ensure_db_session()
            try:
                target_company = company_hr_dataset
                if not target_company:
                    target_company = _lazy("SettingsService")(db).get_default_company_hr_dataset()

                if target_company and not _lazy("auth_middleware").check_company_access(user, target_company):
                    return _error(f"You do not have permission to access data from '{target_company}'.", code="access_denied")

                bi_service = _lazy("BusinessIntelligenceService")(db)
                created = bi_service.create_question(
                    user_id=user.user_id, customer_id=user.customer_id,
                    company_hr_dataset=target_company, question=question,
                    session_id=session_key, metadata={"source": "mcp_gateway"},
                )
                _lazy("process_bi_question").delay(
                    question_id=created.question_id, user_id=user.user_id,
                    customer_id=user.customer_id, company_hr_dataset=target_company,
                )
                SESSION_STORE.update_last_question(session_key, created.question_id)
                created_question_id = created.question_id
                created_status = created.status
            finally:
                db.close()

            if not wait_for_result:
                return _ok({
                    "session_id": session_key,
                    "question_id": created_question_id,
                    "status": _coerce_question_status(created_status),
                    "message": "Question submitted for asynchronous processing.",
                })

            timeout = max(10, min(timeout_seconds, 600))
            poll_interval = min(max(poll_interval_seconds, 0.5), 5.0)
            deadline = time.monotonic() + timeout
            _BIQ = _lazy("BIQuestion")
            _QS = _lazy("QuestionStatus")
            terminal_statuses = {_QS.COMPLETED.value, _QS.FAILED.value}
            last_serialized: dict[str, Any] | None = None
            last_status: str | None = None
            found = False
            while time.monotonic() < deadline:
                poll_db = _ensure_db_session()
                try:
                    current = (
                        poll_db.query(_BIQ)
                        .options(joinedload(_BIQ.result))
                        .filter(_BIQ.question_id == created_question_id)
                        .first()
                    )
                    if current is not None:
                        found = True
                        last_status = _coerce_question_status(current.status)
                        if last_status in terminal_statuses:
                            last_serialized = _serialize_question(current)
                finally:
                    poll_db.close()
                if last_serialized is not None:
                    break
                await asyncio.sleep(poll_interval)

            if not found:
                return _error("Question could not be reloaded.", code="internal_error")

            if last_serialized is not None:
                return _ok(last_serialized)

            return _ok({
                "question_id": created_question_id,
                "status": last_status or _coerce_question_status(created_status),
                "message": "Question is still processing.",
            })
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("ask_question failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="ask_question", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                parameters={"question_length": len(question), "wait_for_result": wait_for_result},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # list_data_connections
    # ======================================================================

    @mcp.tool(name="list_data_connections", structured_output=True)
    async def list_data_connections(
        ctx: Context,
        is_enabled: bool | None = True,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "list_data_connections")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "connections:read"):
                return _error("You do not have access to data connections.", code="access_denied")

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)

            cached = CACHE.get_connection_list(user.customer_id, is_enabled)
            if cached is not None:
                return _ok({"session_id": session_key, "connections": cached})

            db = _ensure_db_session()
            try:
                connector_service = _lazy("ConnectorService")(db)
                connectors = connector_service.list_configurations(customer_id=user.customer_id, is_enabled=is_enabled)
                conn_list = [
                    {
                        "connector_id": item.connector_id,
                        "name": item.connector_name,
                        "type": item.connector_type,
                        "is_enabled": item.is_enabled,
                        "is_healthy": item.is_healthy,
                        "sync_mode": item.sync_mode,
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                    }
                    for item in connectors
                ]
                CACHE.set_connection_list(user.customer_id, is_enabled, conn_list)
                return _ok({"session_id": session_key, "connections": conn_list})
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("list_data_connections failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="list_data_connections", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                parameters={"is_enabled": is_enabled}, success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # get_document
    # ======================================================================

    @mcp.tool(name="get_document", structured_output=True)
    async def get_document(
        document_id: int,
        ctx: Context,
        include_chunks: bool = True,
        chunk_limit: int = 20,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "get_document")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "assistant:documents:read"):
                return _error("You do not have access to documents.", code="access_denied")

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)

            db = _ensure_db_session()
            try:
                _Doc = _lazy("Document")
                document = (
                    db.query(_Doc)
                    .filter(_Doc.id == document_id, _Doc.customer_id == user.customer_id)
                    .first()
                )
                if document is None:
                    return _error("Document not found.", code="not_found")

                payload: dict[str, Any] = {
                    "session_id": session_key,
                    "document": {
                        "id": document.id,
                        "filename": document.filename,
                        "original_filename": document.original_filename,
                        "status": document.status,
                        "mime_type": document.mime_type,
                        "file_size": document.file_size,
                        "total_chunks": document.total_chunks,
                        "created_at": document.created_at.isoformat() if document.created_at else None,
                        "processing_completed_at": document.processing_completed_at.isoformat() if document.processing_completed_at else None,
                        "metadata": document.document_metadata or {},
                    },
                }

                if include_chunks:
                    safe_limit = max(1, min(chunk_limit, 100))
                    _DC = _lazy("DocumentChunk")
                    chunks = (
                        db.query(_DC)
                        .filter(_DC.document_id == document.id)
                        .order_by(_DC.chunk_index.asc())
                        .limit(safe_limit)
                        .all()
                    )
                    payload["chunks"] = [
                        {
                            "chunk_id": chunk.chunk_id,
                            "chunk_index": chunk.chunk_index,
                            "text": chunk.text,
                            "token_count": chunk.token_count,
                            "section_title": chunk.section_title,
                        }
                        for chunk in chunks
                    ]
                return _ok(payload)
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("get_document failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="get_document", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                parameters={"document_id": document_id, "include_chunks": include_chunks},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # upload_document
    # ======================================================================

    @mcp.tool(name="upload_document", structured_output=True)
    async def upload_document(
        filename: str,
        content_base64: str,
        ctx: Context,
        workspace_id: int | None = None,
        knowledge_base_id: int | None = None,
        mime_type: str = "application/octet-stream",
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "upload_document")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "assistant:documents:upload"):
                return _error("You do not have access to upload documents.", code="access_denied")

            safe_name = os.path.basename(filename).strip()
            if not safe_name or len(safe_name) > _MAX_FILENAME_LEN or not _SAFE_FILENAME_RE.match(safe_name):
                return _error(
                    "Invalid filename. Use alphanumeric characters, hyphens, underscores, "
                    "dots, spaces, and parentheses only (max 255 chars).",
                    code="bad_request",
                )
            filename = safe_name

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)
            state = SESSION_STORE.get_or_create(session_key)
            active_workspace_id = _resolve_workspace_id(requested_workspace_id=workspace_id, session_workspace_id=state.workspace_id)
            if active_workspace_id is None:
                return _error("No active workspace. Call select_workspace first.", code="workspace_required")

            ws_ok, ws_reason = _check_workspace_allowed(tenant_cfg, active_workspace_id)
            if not ws_ok:
                _audit_ok, _audit_err = False, "workspace_not_allowed"
                return _error(ws_reason, code="workspace_not_allowed")

            try:
                file_content = base64.b64decode(content_base64, validate=True)
            except Exception:
                return _error("Invalid base64 content payload.", code="bad_request")

            if not file_content:
                return _error("Decoded file content is empty.", code="bad_request")

            if len(file_content) > _MAX_UPLOAD_BYTES:
                return _error(
                    f"File exceeds maximum upload size ({_MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
                    code="bad_request",
                )

            db = _ensure_db_session()
            try:
                rag_service = _lazy("NativeRAGService")(db)
                workspace = await rag_service.get_domain(active_workspace_id, user.customer_id)
                if workspace is None:
                    return _error("Workspace not found.", code="not_found")

                access_service = _lazy("KnowledgeBaseAccessService")(db)
                writable_scope = access_service.resolve_accessible_kb_ids(workspace_id=workspace.id, user=user, required_permission=_lazy("KnowledgeBasePermissionType").WRITE)
                selected_kb_id = knowledge_base_id
                if selected_kb_id is not None and selected_kb_id not in writable_scope:
                    return _error(f"Access denied for knowledge base(s): [{selected_kb_id}]", code="access_denied")
                if selected_kb_id is None and writable_scope:
                    selected_kb_id = writable_scope[0]

                uploaded = await rag_service.upload_domain_document(
                    domain_id=workspace.id, customer_id=user.customer_id,
                    file_content=file_content, filename=filename,
                    mime_type=mime_type, user_id=user.user_id,
                    knowledge_base_id=selected_kb_id,
                )
                CACHE.invalidate_kb_list(workspace.id)
                SESSION_STORE.update_workspace(session_key, workspace.id)
                return _ok({
                    "session_id": session_key,
                    "workspace_id": workspace.id,
                    "knowledge_base_id": selected_kb_id,
                    "document": {
                        "id": uploaded.id,
                        "original_filename": uploaded.original_filename,
                        "status": uploaded.status.value if hasattr(uploaded.status, "value") else str(uploaded.status),
                        "chunk_count": uploaded.chunk_count,
                        "progress": uploaded.progress,
                    },
                })
            finally:
                db.close()
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("upload_document failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="upload_document", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                workspace_id=workspace_id,
                parameters={"filename": filename, "mime_type": mime_type},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    # ======================================================================
    # trigger_sync
    # ======================================================================

    @mcp.tool(name="trigger_sync", structured_output=True)
    async def trigger_sync(
        connector_id: str,
        ctx: Context,
        manual_trigger: bool = True,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        user, request = await _authenticate_ctx(ctx)
        if user is None or request is None:
            return _error("Authentication required (Bearer token).", code="unauthorized")

        allowed, reason = RATE_LIMITER.check_and_increment(user.user_id)
        if not allowed:
            return _error(reason or "Rate limit exceeded.", code="rate_limited")

        t0 = time.monotonic()
        _audit_ok, _audit_err = True, None
        try:
            tenant_cfg = _load_tenant_config(user.customer_id)
            tool_ok, tool_reason = _check_tool_allowed(tenant_cfg, "trigger_sync")
            if not tool_ok:
                _audit_ok, _audit_err = False, "tool_not_allowed"
                return _error(tool_reason, code="tool_not_allowed")

            if not _has_permission(user, "connections:sync"):
                return _error("You do not have access to trigger sync.", code="access_denied")

            session_key = _resolve_session_key(user=user, ctx=ctx, request=request, explicit_session_id=session_id)

            db = _ensure_db_session()
            try:
                connector_service = _lazy("ConnectorService")(db)
                sync_run = connector_service.trigger_sync(
                    connector_id=connector_id, customer_id=user.customer_id, manual_trigger=manual_trigger,
                )
                CACHE.invalidate_connection_list(user.customer_id)
                return _ok({
                    "session_id": session_key,
                    "sync": {
                        "sync_id": sync_run.sync_id,
                        "status": sync_run.status,
                        "connector_id": connector_id,
                        "triggered_by": sync_run.triggered_by,
                        "started_at": sync_run.started_at.isoformat() if sync_run.started_at else None,
                    },
                })
            finally:
                db.close()
        except ValueError as exc:
            _audit_ok, _audit_err = False, "bad_request"
            return _error(str(exc), code="bad_request")
        except HTTPException as exc:
            _audit_ok, _audit_err = False, "http_error"
            return _error(str(exc.detail), code="http_error")
        except Exception:
            logger.exception("trigger_sync failed")
            _audit_ok, _audit_err = False, "internal_error"
            return _error("An internal error occurred.", code="internal_error")
        finally:
            await log_mcp_tool_call(
                tool_name="trigger_sync", user_id=user.user_id,
                customer_id=user.customer_id, session_key=session_id,
                parameters={"connector_id": connector_id, "manual_trigger": manual_trigger},
                success=_audit_ok,
                error_code=_audit_err,
                duration_ms=round((time.monotonic() - t0) * 1000, 1),
                ip_address=_client_ip(request), user_agent=_client_ua(request),
            )

    return mcp


# ---------- ASGI application assembly ----------

_MCP_ASGI_APP: Starlette | None = None


def get_mcp_asgi_app() -> Starlette:
    """Return MCP ASGI app exposing both streamable HTTP and SSE transports."""
    global _MCP_ASGI_APP
    if _MCP_ASGI_APP is not None:
        return _MCP_ASGI_APP

    if not MCP_SDK_AVAILABLE:
        _MCP_ASGI_APP = _build_fallback_app()
        return _MCP_ASGI_APP

    mcp_server = _build_mcp_server()
    streamable = mcp_server.streamable_http_app()
    sse = mcp_server.sse_app()

    from src.mcp_gateway.oauth import (
        build_oauth_app,
        authorization_server_metadata,
        protected_resource_metadata,
    )

    oauth_app = build_oauth_app(redis_client=SESSION_STORE.redis_client)

    # Build a composite Starlette app that preserves the streamable app's
    # lifespan_context (required to initialise the MCP task group).
    # Well-known discovery routes are duplicated at the MCP root so that
    # standard MCP clients (which probe /{mcp}/.well-known/…) can find them
    # in addition to the canonical /oauth/.well-known/… paths.
    _MCP_ASGI_APP = Starlette(
        routes=[
            Route("/.well-known/oauth-protected-resource", protected_resource_metadata),
            Route("/.well-known/oauth-authorization-server", authorization_server_metadata),
            Mount("/oauth", app=oauth_app),
            *streamable.routes,
            *sse.routes,
        ],
        lifespan=streamable.router.lifespan_context,
    )
    return _MCP_ASGI_APP
