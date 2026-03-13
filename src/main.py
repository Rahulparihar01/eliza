"""
AI Enablement Platform - Main FastAPI Application

This is the main entry point for the AI Enablement Platform API.
Provides enterprise AI enablement analysis and recommendations.
"""

import os
import sys
import time
import importlib
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.dirname(__file__))

from core.config import get_settings
from core.exceptions import AIEnablementException
from core.logging import LogCategory, get_logger, setup_logging
from middleware.logging import PerformanceLoggingMiddleware, RequestLoggingMiddleware
from middleware.tenant_context import TenantContextMiddleware
from services.database_service import DatabaseService
from src.applets.registry import get_enabled_route_keys

# Import all models in correct order BEFORE importing routes/services
# This ensures SQLAlchemy metadata is built correctly with proper foreign key references
from src.models.database import init_async_database, init_database

# Initialize settings and logging
settings = get_settings()
setup_logging(settings)  # Pass full settings object for enhanced logging
logger = get_logger(__name__, component="main")

# Resolve route modularity once so startup hooks and router inclusion use
# the same enabled/disabled view of the deployment.
enabled_route_keys = get_enabled_route_keys(os.getenv("APPLETS"))


def _is_route_enabled(route_key: str) -> bool:
    return enabled_route_keys is None or route_key in enabled_route_keys


def _env_flag(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


seed_data_enabled = _env_flag("SEED_DATA", True)
seed_default_workspaces_enabled = _env_flag("SEED_DEFAULT_WORKSPACES", False)


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    logger.info(
        "Starting AI Enablement Platform API",
        category=LogCategory.SYSTEM,
        operation="startup",
        user_message="🚀 AI Platform starting...",
        metadata={
            "environment": settings.environment,
            "customer_id": settings.customer_id,
            "log_level": settings.log_level,
        },
    )

    # Initialize services
    try:
        # Initialize database service (both sync and async)
        db_service = DatabaseService()
        db_initialized = await db_service.initialize()
        if not db_initialized:
            raise Exception("Database initialization failed")

        # Initialize sync database for sync operations (tools, scripts, etc.)
        init_database()
        logger.info("✅ Sync database initialized")

        # Initialize async database for admin and other async operations
        init_async_database()
        logger.info("✅ Async database initialized for admin portal")

        # Set up development data if in development mode
        if settings.environment == "development":
            await db_service.setup_development_data()

        # Store database service in app state
        app.state.db_service = db_service

        # Optional startup seeding with applet-aware guards.
        try:
            from src.models.database import SessionLocal
        except Exception as session_import_error:
            logger.warning(f"⚠️ Could not import SessionLocal for startup seeding: {session_import_error}")
            SessionLocal = None

        if not seed_data_enabled:
            logger.info("Skipping startup data seeding (SEED_DATA=false).")
        elif SessionLocal is None:
            logger.warning("⚠️ SessionLocal unavailable; skipping startup data seeding.")
        else:
            db_session = SessionLocal()
            try:
                if _is_route_enabled("rag_eval"):
                    try:
                        from src.services.eval_set_service import EvalSetService

                        eval_set_service = EvalSetService(db_session)
                        count = eval_set_service.ensure_static_sets_exist()
                        if count > 0:
                            logger.info(f"✅ Static eval sets seeded/verified ({count} sets)")
                    except Exception as seed_error:
                        # Non-fatal: if seeding fails, admin can seed manually.
                        logger.warning(f"⚠️ Could not seed static eval sets: {seed_error}")
                else:
                    logger.info("Skipping eval set seeding (ai_console routes not enabled).")

                if seed_default_workspaces_enabled and _is_route_enabled("workspace"):
                    try:
                        from src.services.workspace_seed_service import WorkspaceSeedService

                        workspace_seed_service = WorkspaceSeedService(db_session)
                        ws_count = workspace_seed_service.ensure_default_workspaces_exist()
                        if ws_count > 0:
                            logger.info(f"✅ Default workspaces seeded ({ws_count} workspaces)")
                    except Exception as ws_seed_error:
                        # Non-fatal: if seeding fails, admin can seed manually.
                        logger.warning(f"⚠️ Could not seed default workspaces: {ws_seed_error}")
                elif not seed_default_workspaces_enabled:
                    logger.info("Skipping default workspace seeding (SEED_DEFAULT_WORKSPACES=false).")
                else:
                    logger.info("Skipping default workspace seeding (workspace routes not enabled).")
            finally:
                db_session.close()

        # TODO: Initialize model providers
        # TODO: Initialize vector stores
        from src.services.langfuse_service import get_langfuse_service

        app.state.langfuse_service = get_langfuse_service()
        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize services: {e}")
        raise

    yield

    # Shutdown
    try:
        if hasattr(app.state, "langfuse_service") and app.state.langfuse_service:
            app.state.langfuse_service.shutdown()
    except Exception:
        pass
    logger.info("Shutting down AI Enablement Platform API")
    # TODO: Cleanup resources


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Combined lifespan: app services + MCP session manager."""
    if _is_route_enabled("mcp"):
        from src.mcp_gateway.server import get_mcp_asgi_app

        mcp_app = get_mcp_asgi_app()
        mcp_lifespan = mcp_app.router.lifespan_context
        async with _app_lifespan(app):
            async with mcp_lifespan(app):
                yield
    else:
        async with _app_lifespan(app):
            yield


# Create FastAPI application
app = FastAPI(
    title="AI Enablement Platform",
    description="Enterprise AI enablement analysis and recommendations platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add middleware
# Parse allowed_origins if it's a string (e.g., from env var)
allowed_origins = settings.allowed_origins
if isinstance(allowed_origins, str):
    allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]

# When allow_credentials=True, we cannot use ["*"] - must specify exact origins
# If "*" is provided, replace with common development origins
if allowed_origins == ["*"] or (isinstance(allowed_origins, list) and "*" in allowed_origins):
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    # Add production origins if needed
    if settings.environment == "production":
        # In production, you should set ALLOWED_ORIGINS env var explicitly
        logger.warning(
            "Using default CORS origins in production. Set ALLOWED_ORIGINS env var for production.",
            category=LogCategory.SYSTEM,
        )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],  # Allow frontend to see all headers
)

# Parse allowed_hosts if it's a string
allowed_hosts = settings.allowed_hosts
if isinstance(allowed_hosts, str):
    allowed_hosts = [host.strip() for host in allowed_hosts.split(",")]

# If wildcard is present, keep it to allow all hosts
# Otherwise use the configured list plus common internal hostnames
if "*" in allowed_hosts:
    # Wildcard allows all hosts - no middleware restriction
    allowed_hosts = ["*"]
else:
    # Add common internal hostnames for health checks
    internal_hosts = ["localhost", "127.0.0.1", "app"]
    allowed_hosts = list(set(allowed_hosts + internal_hosts))

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to all responses."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Add new logging middleware (replaces old log_requests)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(PerformanceLoggingMiddleware, slow_request_threshold_ms=1000.0)

# Add tenant context middleware for Row Level Security
# This middleware sets the PostgreSQL session variable for RLS policies
app.add_middleware(TenantContextMiddleware)


# Exception handlers
@app.exception_handler(AIEnablementException)
async def ai_enablement_exception_handler(_request: Request, exc: AIEnablementException):
    """Handle custom AI Enablement exceptions."""
    logger.error(
        f"AI Enablement error: {exc.detail}",
        category=LogCategory.SYSTEM,
        error_code=exc.error_code,
        metadata={"error_code": exc.error_code, "status_code": exc.status_code},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": exc.detail, "timestamp": time.time()},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(
        f"HTTP error: {exc.detail}",
        category=LogCategory.API,
        metadata={"status_code": exc.status_code},
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": "http_error", "message": exc.detail, "timestamp": time.time()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(
        f"Unexpected error: {exc!s}",
        exception=exc,
        category=LogCategory.SYSTEM,
        metadata={"path": request.url.path, "method": request.method},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "timestamp": time.time(),
        },
    )


# Include routers (optionally filtered by APPLETS manifest selection)
if enabled_route_keys is None:
    logger.info(
        "Route modularity disabled (APPLETS=all). Including all routers.",
        category=LogCategory.SYSTEM,
    )
else:
    logger.info(
        "Route modularity enabled. Including subset of routers.",
        category=LogCategory.SYSTEM,
        metadata={"enabled_route_count": len(enabled_route_keys)},
    )


def _include_router_if_enabled(
    route_key: str,
    module_path: str,
    router_attr: str = "router",
    prefix: str | None = None,
    tags: list[str] | None = None,
) -> None:
    if enabled_route_keys is not None and route_key not in enabled_route_keys:
        return

    module = importlib.import_module(module_path)
    router = getattr(module, router_attr)

    kwargs: dict[str, Any] = {}
    if prefix is not None:
        kwargs["prefix"] = prefix
    if tags is not None:
        kwargs["tags"] = tags
    app.include_router(router, **kwargs)


_include_router_if_enabled("health", "api.routes.health", prefix="/health", tags=["Health"])
_include_router_if_enabled("auth", "api.routes.auth", prefix="/v1/auth", tags=["Authentication"])
_include_router_if_enabled("models", "api.routes.models", prefix="/v1/models", tags=["Models"])
_include_router_if_enabled("config", "api.routes.config", prefix="/v1/config", tags=["Configuration"])
_include_router_if_enabled("mcp", "src.api.routes.mcp", tags=["MCP Gateway"])

# Mount MCP ASGI sub-app (Streamable HTTP + SSE transports) directly on the
# FastAPI app.  APIRouter.mount() does not forward requests correctly for
# ASGI sub-applications, so this must live here rather than in the router.
if _is_route_enabled("mcp"):
    from src.mcp_gateway.server import get_mcp_asgi_app

    # RFC 8414 path-based discovery: MCP clients construct the well-known URL
    # as ``{origin}/.well-known/{suffix}{issuer_path}``, which lands outside
    # the /mcp mount.  We expose these at the FastAPI root so clients that
    # follow the strict RFC 8414 algorithm can discover the OAuth metadata.
    from starlette.requests import Request as _Request
    from src.mcp_gateway.oauth import (
        authorization_server_metadata as _as_meta,
        protected_resource_metadata as _pr_meta,
    )

    @app.get("/.well-known/oauth-authorization-server/mcp/oauth", include_in_schema=False)
    async def _rfc8414_as_metadata(request: _Request):
        return await _as_meta(request)

    @app.get("/.well-known/oauth-protected-resource/mcp", include_in_schema=False)
    async def _rfc8414_pr_metadata(request: _Request):
        return await _pr_meta(request)

    app.mount("/mcp", get_mcp_asgi_app())
_include_router_if_enabled("documents", "api.routes.documents", tags=["Documents"])

# Import and include API Keys router
# TODO: api_keys route module needs to be created - temporarily commented out
# _include_router_if_enabled("api_keys", "src.api.routes.api_keys", tags=["API Keys"])

_include_router_if_enabled("audit", "src.api.routes.audit", prefix="/v1/audit", tags=["Audit"])
_include_router_if_enabled(
    "permissions",
    "src.api.routes.permissions",
    prefix="/v1/permissions",
    tags=["Permissions"],
)
_include_router_if_enabled("mfa", "src.api.routes.mfa", prefix="/v1/mfa", tags=["MFA"])
_include_router_if_enabled("hr", "src.api.routes.hr", tags=["HR"])
_include_router_if_enabled("admin", "src.api.routes.admin", tags=["Admin"])
_include_router_if_enabled(
    "business_intelligence",
    "src.api.routes.business_intelligence",
    tags=["Business Intelligence"],
)
_include_router_if_enabled("settings", "api.routes.settings", tags=["Settings"])
_include_router_if_enabled("companies", "api.routes.companies", tags=["Companies"])
_include_router_if_enabled("bedrock", "src.api.routes.bedrock", tags=["AWS Bedrock"])
_include_router_if_enabled("providers", "src.api.routes.providers", tags=["AI Providers"])
_include_router_if_enabled("agents", "src.api.routes.agents", tags=["Agent Configuration"])
_include_router_if_enabled("connectors", "src.api.routes.connectors", tags=["Data Connectors"])
_include_router_if_enabled("search", "src.api.routes.search", prefix="/v1", tags=["Search"])
_include_router_if_enabled("talent", "src.api.routes.talent", tags=["Talent Intelligence"])
_include_router_if_enabled(
    "talent_matching",
    "src.api.routes.talent_matching",
    prefix="/api",
    tags=["Talent Matching"],
)
_include_router_if_enabled(
    "ml_talent",
    "src.api.routes.ml_talent",
    prefix="/api",
    tags=["ML Talent Intelligence"],
)
_include_router_if_enabled(
    "talent_feedback",
    "src.api.routes.talent_feedback",
    prefix="",
    tags=["Talent Feedback"],
)
_include_router_if_enabled(
    "linkedin_enrichment",
    "src.api.routes.linkedin_enrichment",
    prefix="",
    tags=["LinkedIn Enrichment"],
)
_include_router_if_enabled(
    "document_parsing",
    "api.routes.document_parsing",
    prefix="/api",
    tags=["Document Parsing"],
)
_include_router_if_enabled("outreach", "api.routes.outreach", tags=["Candidate Outreach"])
_include_router_if_enabled("data_analyst", "src.api.routes.data_analyst", tags=["Data Analyst"])
_include_router_if_enabled(
    "email_templates",
    "src.api.routes.email_templates",
    tags=["Email Templates"],
)
_include_router_if_enabled(
    "tenant_admin",
    "src.api.routes.tenant_admin",
    prefix="/api/v1",
    tags=["Tenant Admin"],
)
_include_router_if_enabled(
    "platform_admin",
    "src.api.routes.platform_admin",
    prefix="/api/v1",
    tags=["Platform Admin"],
)
_include_router_if_enabled(
    "talent_config",
    "src.api.routes.talent_config",
    prefix="/api/v1",
    tags=["Talent Configuration"],
)
_include_router_if_enabled(
    "analysis_config",
    "src.api.routes.analysis_config",
    prefix="/api/v1",
    tags=["Analysis Configuration"],
)
_include_router_if_enabled(
    "candidate_feedback",
    "src.api.routes.candidate_feedback",
    tags=["Candidate Feedback"],
)
_include_router_if_enabled(
    "reference_checks",
    "src.api.routes.reference_checks",
    prefix="/api/v1",
    tags=["Reference Checks"],
)
_include_router_if_enabled(
    "reference_check_webhooks",
    "src.api.routes.reference_check_webhooks",
    prefix="/api/v1/webhooks",
    tags=["Reference Check Webhooks"],
)
_include_router_if_enabled("compliance", "src.api.routes.compliance", tags=["Compliance & Audit"])
_include_router_if_enabled("adoption", "src.api.routes.adoption", tags=["Adoption Dashboard"])
_include_router_if_enabled(
    "rag_eval",
    "src.api.routes.rag_eval",
    prefix="/api/v1",
    tags=["RAG Evaluation"],
)
_include_router_if_enabled(
    "gepa_optimizer",
    "src.api.routes.gepa_optimizer",
    prefix="/api/v1",
    tags=["GEPA Optimizer"],
)
_include_router_if_enabled(
    "prompt_management",
    "src.api.routes.prompt_management",
    prefix="/api/v1",
    tags=["Prompt Management"],
)
_include_router_if_enabled("ragflow", "src.api.routes.ragflow", tags=["RAGFlow - RAG Chat Service"])
_include_router_if_enabled("workspace", "src.api.routes.workspace", tags=["Workspaces"])
_include_router_if_enabled(
    "workspace_templates",
    "src.api.routes.workspace",
    router_attr="template_router",
    tags=["Workspace Templates"],
)
_include_router_if_enabled(
    "workspace_chat",
    "src.api.routes.workspace",
    router_attr="chat_router",
    tags=["Chat"],
)
_include_router_if_enabled("sow", "src.api.routes.sow", tags=["SOW Generation"])
_include_router_if_enabled("retrieval", "src.api.routes.retrieval", tags=["Retrieval"])
_include_router_if_enabled("oauth", "src.api.routes.oauth", tags=["OAuth"])
_include_router_if_enabled(
    "tenant_settings",
    "src.api.routes.tenant_settings",
    prefix="/api",
    tags=["Tenant Settings"],
)
_include_router_if_enabled("content_writer", "src.api.routes.content_writer", tags=["Content Writer"])
_include_router_if_enabled(
    "content_research",
    "src.api.routes.content_research",
    tags=["Content Research"],
)
_include_router_if_enabled(
    "tiny_model_studio",
    "src.api.routes.tiny_model_studio",
    tags=["Tiny Model Studio"],
)


@app.get("/", response_model=dict[str, Any])
async def root():
    """Root endpoint with basic platform information."""
    return {
        "name": "AI Enablement Platform",
        "version": "1.0.0",
        "description": "Enterprise AI enablement analysis and recommendations",
        "customer_id": settings.customer_id,
        "environment": settings.environment,
        "docs_url": "/docs",
        "health_url": "/health",
        "timestamp": time.time(),
    }


if __name__ == "__main__":
    # Run with uvicorn for development
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=5001,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
        access_log=True,
    )

