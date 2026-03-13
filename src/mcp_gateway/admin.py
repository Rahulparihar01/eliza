"""Admin API for managing MCP server configurations.

Provides CRUD endpoints for tenant admins to:
 - List / create / update / delete MCP server configs
 - Enable/disable MCP per workspace
 - Set rate limits and white-label branding
 - Platform admin toggle per tenant

Mounted under ``/v1/mcp/admin`` by the MCP route module.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.middleware.authorization import require_permission
from src.models import database
from src.models.mcp_config import MCPServerConfig

logger = logging.getLogger(__name__)

KNOWN_MCP_TOOLS: frozenset[str] = frozenset({
    "list_workspaces",
    "select_workspace",
    "list_knowledge_bases",
    "search_documents",
    "chat",
    "ask_question",
    "list_data_connections",
    "get_document",
    "upload_document",
    "trigger_sync",
})
_CLIENT_ID_SAFE_RE = re.compile(r"[^a-z0-9-]+")

router = APIRouter(prefix="/v1/mcp/admin", tags=["MCP Admin"])


def _invalidate_tenant_cache(customer_id: str) -> None:
    """Best-effort cache bust so config changes take effect immediately."""
    try:
        from src.mcp_gateway.server import CACHE as _server_cache
        _server_cache.invalidate_tenant_config(customer_id)
    except Exception:
        pass


def _get_db():
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic schemas ---


def _validate_http_url(v: str | None) -> str | None:
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if not v.startswith(("https://", "http://")):
        raise ValueError("icon_url must use http:// or https:// scheme")
    return v


def _validate_tool_names(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    unknown = set(v) - KNOWN_MCP_TOOLS
    if unknown:
        sorted_unknown = ", ".join(sorted(unknown))
        sorted_known = ", ".join(sorted(KNOWN_MCP_TOOLS))
        raise ValueError(
            f"Unknown tool name(s): {sorted_unknown}. "
            f"Valid tools: {sorted_known}"
        )
    return v


def _validate_redirect_uris(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v

    cleaned: list[str] = []
    seen: set[str] = set()
    for uri in v:
        value = uri.strip()
        if not value:
            continue
        if not value.startswith(("https://", "http://")):
            raise ValueError("oauth_redirect_uris must use http:// or https:// scheme")
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _public_base_url(request: Request) -> str:
    configured = get_settings().public_base_url
    if configured:
        return configured.rstrip("/")

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{scheme}://{host}"


def _generate_oauth_client_id(config: MCPServerConfig) -> str:
    raw = f"mcp-{config.customer_id}-{config.server_name}-{config.id}".lower()
    collapsed = _CLIENT_ID_SAFE_RE.sub("-", raw)
    collapsed = re.sub(r"-{2,}", "-", collapsed).strip("-")
    return collapsed[:255] or f"mcp-config-{config.id}"


def _ensure_oauth_client_id(config: MCPServerConfig, db: Session) -> None:
    if config.oauth_client_id:
        return

    config.oauth_client_id = _generate_oauth_client_id(config)
    db.commit()
    db.refresh(config)


def _serialize_config(config: MCPServerConfig, request: Request) -> "MCPServerConfigResponse":
    base = _public_base_url(request)
    return MCPServerConfigResponse(
        id=config.id,
        customer_id=config.customer_id,
        server_type=config.server_type,
        server_name=config.server_name,
        display_name=config.display_name,
        description=config.description,
        icon_url=config.icon_url,
        is_enabled=config.is_enabled,
        allowed_workspace_ids=config.allowed_workspace_ids,
        allowed_tool_names=config.allowed_tool_names,
        enabled_widgets=config.enabled_widgets,
        rate_limit_rpm=config.rate_limit_rpm,
        rate_limit_rph=config.rate_limit_rph,
        max_concurrent_sessions=config.max_concurrent_sessions,
        max_async_operations=config.max_async_operations,
        oauth_client_id=config.oauth_client_id,
        oauth_redirect_uris=config.oauth_redirect_uris or [],
        server_url=f"{base}/mcp",
        authorization_url=f"{base}/mcp/oauth/authorize",
        token_url=f"{base}/mcp/oauth/token",
        oauth_token_endpoint_auth_method="none",
    )


class MCPServerConfigCreate(BaseModel):
    server_type: Literal["chat", "applet"] = Field(default="chat", description="chat or applet")
    server_name: str = Field(default="eliza-chat", min_length=1, max_length=100)
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    icon_url: str | None = Field(default=None, max_length=500)
    is_enabled: bool = False
    allowed_workspace_ids: list[int] = Field(default_factory=list)
    allowed_tool_names: list[str] = Field(default_factory=list)
    enabled_widgets: list[str] = Field(default_factory=list)
    rate_limit_rpm: int = Field(default=30, ge=1, le=10000)
    rate_limit_rph: int = Field(default=500, ge=1, le=100000)
    max_concurrent_sessions: int = Field(default=50, ge=1, le=10000)
    max_async_operations: int = Field(default=5, ge=1, le=1000)
    oauth_client_id: str | None = Field(default=None, max_length=255)
    oauth_redirect_uris: list[str] = Field(default_factory=list)

    _validate_icon_url = field_validator("icon_url", mode="before")(_validate_http_url)
    _validate_tool_names = field_validator("allowed_tool_names", mode="before")(_validate_tool_names)
    _validate_redirect_uris = field_validator("oauth_redirect_uris", mode="before")(_validate_redirect_uris)


class MCPServerConfigUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    icon_url: str | None = Field(default=None, max_length=500)
    is_enabled: bool | None = None
    allowed_workspace_ids: list[int] | None = None
    allowed_tool_names: list[str] | None = None
    enabled_widgets: list[str] | None = None
    rate_limit_rpm: int | None = Field(default=None, ge=1, le=10000)
    rate_limit_rph: int | None = Field(default=None, ge=1, le=100000)
    max_concurrent_sessions: int | None = Field(default=None, ge=1, le=10000)
    max_async_operations: int | None = Field(default=None, ge=1, le=1000)
    oauth_client_id: str | None = Field(default=None, max_length=255)
    oauth_redirect_uris: list[str] | None = None

    _validate_icon_url = field_validator("icon_url", mode="before")(_validate_http_url)
    _validate_tool_names = field_validator("allowed_tool_names", mode="before")(_validate_tool_names)
    _validate_redirect_uris = field_validator("oauth_redirect_uris", mode="before")(_validate_redirect_uris)


class MCPServerConfigResponse(BaseModel):
    id: int
    customer_id: str
    server_type: str
    server_name: str
    display_name: str | None
    description: str | None
    icon_url: str | None
    is_enabled: bool
    allowed_workspace_ids: list[int] | None
    allowed_tool_names: list[str] | None
    enabled_widgets: list[str] | None
    rate_limit_rpm: int
    rate_limit_rph: int
    max_concurrent_sessions: int
    max_async_operations: int
    oauth_client_id: str | None
    oauth_redirect_uris: list[str]
    server_url: str
    authorization_url: str
    token_url: str
    oauth_token_endpoint_auth_method: str

    model_config = {"from_attributes": True}


# --- Endpoints ---


@router.get("/configs", response_model=list[MCPServerConfigResponse])
async def list_mcp_configs(
    request: Request,
    current_user=Depends(require_permission(["admin:settings:read"])),
    db: Session = Depends(_get_db),
):
    """List all MCP server configurations for the current tenant."""
    configs = (
        db.query(MCPServerConfig)
        .filter(MCPServerConfig.customer_id == current_user.customer_id)
        .order_by(MCPServerConfig.created_at.desc())
        .all()
    )
    for config in configs:
        _ensure_oauth_client_id(config, db)
    return [_serialize_config(config, request) for config in configs]


@router.post("/configs", response_model=MCPServerConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_config(
    body: MCPServerConfigCreate,
    request: Request,
    current_user=Depends(require_permission(["admin:settings:write"])),
    db: Session = Depends(_get_db),
):
    """Create a new MCP server configuration for the current tenant."""
    config = MCPServerConfig(
        customer_id=current_user.customer_id,
        **body.model_dump(),
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    _ensure_oauth_client_id(config, db)
    _invalidate_tenant_cache(current_user.customer_id)
    return _serialize_config(config, request)


@router.get("/configs/{config_id}", response_model=MCPServerConfigResponse)
async def get_mcp_config(
    config_id: int,
    request: Request,
    current_user=Depends(require_permission(["admin:settings:read"])),
    db: Session = Depends(_get_db),
):
    """Get a single MCP server configuration."""
    config = (
        db.query(MCPServerConfig)
        .filter(
            MCPServerConfig.id == config_id,
            MCPServerConfig.customer_id == current_user.customer_id,
        )
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="MCP server config not found")
    _ensure_oauth_client_id(config, db)
    return _serialize_config(config, request)


@router.patch("/configs/{config_id}", response_model=MCPServerConfigResponse)
async def update_mcp_config(
    config_id: int,
    body: MCPServerConfigUpdate,
    request: Request,
    current_user=Depends(require_permission(["admin:settings:write"])),
    db: Session = Depends(_get_db),
):
    """Update an existing MCP server configuration."""
    config = (
        db.query(MCPServerConfig)
        .filter(
            MCPServerConfig.id == config_id,
            MCPServerConfig.customer_id == current_user.customer_id,
        )
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(config, field_name, value)

    db.commit()
    db.refresh(config)
    _ensure_oauth_client_id(config, db)
    _invalidate_tenant_cache(current_user.customer_id)
    return _serialize_config(config, request)


@router.delete("/configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp_config(
    config_id: int,
    current_user=Depends(require_permission(["admin:settings:write"])),
    db: Session = Depends(_get_db),
):
    """Delete an MCP server configuration."""
    config = (
        db.query(MCPServerConfig)
        .filter(
            MCPServerConfig.id == config_id,
            MCPServerConfig.customer_id == current_user.customer_id,
        )
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    db.delete(config)
    db.commit()
    _invalidate_tenant_cache(current_user.customer_id)


@router.post("/configs/{config_id}/toggle", response_model=MCPServerConfigResponse)
async def toggle_mcp_config(
    config_id: int,
    request: Request,
    current_user=Depends(require_permission(["admin:settings:write"])),
    db: Session = Depends(_get_db),
):
    """Toggle the enabled state of an MCP server configuration."""
    config = (
        db.query(MCPServerConfig)
        .filter(
            MCPServerConfig.id == config_id,
            MCPServerConfig.customer_id == current_user.customer_id,
        )
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="MCP server config not found")

    config.is_enabled = not config.is_enabled
    db.commit()
    db.refresh(config)
    _ensure_oauth_client_id(config, db)
    _invalidate_tenant_cache(current_user.customer_id)
    return _serialize_config(config, request)
