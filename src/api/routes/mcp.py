"""MCP gateway routes and transport mounting.

The MCP ASGI sub-app (Streamable HTTP + SSE transports) is mounted directly
on the FastAPI ``app`` in ``src/main.py`` because ``APIRouter.mount()`` does
not properly forward requests for ASGI sub-applications.  This module only
contains FastAPI-native endpoints (status, explorer, admin CRUD).
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from src.core.config import get_settings
from src.mcp_gateway.admin import router as admin_router
from src.mcp_gateway.server import MCP_SDK_AVAILABLE

router = APIRouter(tags=["MCP Gateway"])

# Admin API for managing MCP server configurations
router.include_router(admin_router)

_settings = get_settings()
_EXPLORER_ENABLED = _settings.environment != "production"


@router.get("/v1/mcp/status")
async def get_mcp_status() -> dict:
    """Runtime status for MCP transport availability."""
    return {
        "ok": MCP_SDK_AVAILABLE,
    }


@router.get("/v1/mcp/explorer", response_class=HTMLResponse, include_in_schema=False)
async def mcp_explorer():
    """Interactive MCP Explorer UI for testing tools, OAuth, and admin API.

    Only available in non-production environments.  All actual MCP / admin
    calls made from inside the page still require a valid Bearer token.
    """
    if not _EXPLORER_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")

    from src.mcp_gateway.explorer import HTML as EXPLORER_HTML

    return HTMLResponse(EXPLORER_HTML)
