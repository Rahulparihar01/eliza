"""OAuth 2.1 authorization server for MCP clients (ChatGPT Enterprise, etc.).

Implements the MCP-required OAuth 2.1 flow with PKCE (S256):
 - ``/.well-known/oauth-protected-resource``  (RFC 9728)
 - ``/.well-known/oauth-authorization-server`` (RFC 8414)
 - ``GET  /authorize``          → stores OAuth params, redirects to frontend login
 - ``POST /authorize/complete`` → frontend calls after login with Bearer token
 - ``POST /token``              → exchanges code for tokens **or** refreshes

The authorize flow delegates authentication to the main Eliza frontend login
page, then the frontend completes the authorization by calling the
``/authorize/complete`` endpoint with the user's JWT.

Tokens are standard Eliza JWTs so the existing auth middleware validates
them transparently.  Authorization codes and refresh-token mappings are
stored in Redis (10-minute / 24-hour TTL respectively) with an automatic
in-memory fallback when Redis is not available.
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from base64 import urlsafe_b64encode
from typing import Any
from urllib.parse import urlencode, urlparse

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

logger = logging.getLogger(__name__)

_CODE_TTL = 600          # 10 minutes
_REFRESH_TTL = 86_400    # 24 hours
_OAUTH_SESSION_TTL = 600 # 10 minutes — pending OAuth authorizations
_CODE_PREFIX = "mcp:oauth:code:"
_REFRESH_PREFIX = "mcp:oauth:refresh:"
_OAUTH_SESSION_PREFIX = "mcp:oauth:session:"

# Trusted first-party redirect URIs that are always allowed (MCP Explorer,
# local development).  Production deployments should register client URIs
# via MCPServerConfig.oauth_redirect_uris in the database.
_BUILTIN_TRUSTED_URIS: frozenset[str] = frozenset({
    "http://localhost/callback",
    "http://localhost:3000/callback",
    "http://localhost:5001/callback",
    "http://127.0.0.1/callback",
    "http://127.0.0.1:3000/callback",
    "http://127.0.0.1:5001/callback",
})


class _TokenStore:
    """Thin key-value wrapper – Redis when available, in-memory dict otherwise.

    The in-memory fallback now stores ``(value, expires_at)`` tuples and
    enforces TTL on ``get()``, so auth-code and refresh-token lifetimes
    are honoured even without Redis.
    """

    def __init__(self, redis_client=None):
        self._redis = redis_client
        self._mem: dict[str, tuple[str, float]] = {}
        if redis_client is None:
            logger.warning(
                "OAuth token store running in-memory (no Redis). "
                "Auth codes will NOT be shared across workers."
            )

    def set(self, key: str, value: str, ttl: int) -> None:
        if self._redis:
            try:
                self._redis.setex(key, ttl, value)
                return
            except Exception:
                pass
        expires_at = time.monotonic() + ttl
        self._mem[key] = (value, expires_at)

    def get(self, key: str) -> str | None:
        if self._redis:
            try:
                return self._redis.get(key)
            except Exception:
                pass
        entry = self._mem.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            self._mem.pop(key, None)
            return None
        return value

    def delete(self, key: str) -> None:
        if self._redis:
            try:
                self._redis.delete(key)
                return
            except Exception:
                pass
        self._mem.pop(key, None)

    def cleanup_expired(self) -> None:
        """Remove all expired in-memory entries (best-effort housekeeping)."""
        now = time.monotonic()
        expired = [k for k, (_, exp) in self._mem.items() if now > exp]
        for k in expired:
            self._mem.pop(k, None)


def _s256(verifier: str) -> str:
    """Compute S256 code challenge from a PKCE verifier."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _get_configured_base_url() -> str | None:
    """Return an explicit base URL from settings, if configured."""
    try:
        from src.core.config import get_settings
        return get_settings().public_base_url or None
    except Exception:
        return None


def _get_frontend_url() -> str:
    """Return the frontend URL from settings."""
    try:
        from src.core.config import get_settings
        return get_settings().frontend_url.rstrip("/")
    except Exception:
        return "http://localhost:3000"


def _base_url(request: Request) -> str:
    """Derive the public base URL.

    Prefers an explicit ``public_base_url`` from settings (immune to header
    spoofing).  Falls back to ``X-Forwarded-*`` headers which are safe when
    the app sits behind a trusted reverse proxy.
    """
    configured = _get_configured_base_url()
    if configured:
        return configured.rstrip("/")
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{scheme}://{host}"


def _normalize_uri(uri: str) -> str:
    """Normalize a redirect URI for safe comparison (scheme + host + path)."""
    parsed = urlparse(uri.strip())
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _load_registered_uris(client_id: str) -> set[str]:
    """Load redirect URIs registered for *client_id* from the DB.

    Returns an empty set on any failure (missing DB, missing config, etc.)
    so the caller can still fall back to the built-in trusted list.
    """
    try:
        from src.models import database
        from src.models.mcp_config import MCPServerConfig

        if database.SessionLocal is None:
            database.init_database()
        db = database.SessionLocal()
        try:
            config = (
                db.query(MCPServerConfig)
                .filter(MCPServerConfig.oauth_client_id == client_id, MCPServerConfig.is_enabled.is_(True))
                .first()
            )
            if config and config.oauth_redirect_uris:
                return {_normalize_uri(u) for u in config.oauth_redirect_uris}
        finally:
            db.close()
    except Exception as exc:
        logger.debug("Could not load OAuth redirect URIs from DB: %s", exc)
    return set()


def _is_redirect_uri_allowed(client_id: str, redirect_uri: str) -> bool:
    """Check *redirect_uri* against built-in trusted URIs and DB allowlist.

    Default-deny: if no DB allowlist exists for the ``client_id``, only
    built-in trusted (localhost/dev) URIs are accepted.
    """
    normalised = _normalize_uri(redirect_uri)

    if normalised in {_normalize_uri(u) for u in _BUILTIN_TRUSTED_URIS}:
        return True

    registered = _load_registered_uris(client_id)
    if registered and normalised in registered:
        return True

    if not registered:
        logger.warning(
            "No registered redirect URIs for client_id=%s and URI %s is not "
            "in the built-in trusted list — rejecting. Register URIs in "
            "MCPServerConfig.oauth_redirect_uris to allow this callback.",
            client_id,
            redirect_uri,
        )

    return False



async def protected_resource_metadata(request: Request) -> JSONResponse:
    """RFC 9728 — ``/.well-known/oauth-protected-resource``."""
    base = _base_url(request)
    return JSONResponse(
        {
            "resource": f"{base}/mcp",
            "authorization_servers": [f"{base}/mcp/oauth"],
            "bearer_methods_supported": ["header"],
            "scopes_supported": [
                "workspaces:read",
                "documents:read",
                "documents:write",
                "bi:read",
                "connections:read",
                "connections:write",
            ],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )


async def authorization_server_metadata(request: Request) -> JSONResponse:
    """RFC 8414 — ``/.well-known/oauth-authorization-server``."""
    base = _base_url(request)
    oauth_base = f"{base}/mcp/oauth"
    return JSONResponse(
        {
            "issuer": oauth_base,
            "authorization_endpoint": f"{oauth_base}/authorize",
            "token_endpoint": f"{oauth_base}/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post"],
            "scopes_supported": [
                "workspaces:read",
                "documents:read",
                "documents:write",
                "bi:read",
                "connections:read",
                "connections:write",
            ],
        },
        headers={"Cache-Control": "public, max-age=3600"},
    )


def build_oauth_app(*, redis_client=None) -> Starlette:
    """Return a Starlette sub-application that serves the OAuth 2.1 endpoints."""

    store = _TokenStore(redis_client)

    # ------------------------------------------------------------------
    # GET /authorize — validate params, store session, redirect to login
    # ------------------------------------------------------------------
    async def authorize_get(request: Request) -> RedirectResponse | JSONResponse:
        params = request.query_params
        client_id = params.get("client_id", "").strip()
        redirect_uri = params.get("redirect_uri", "").strip()
        code_challenge = params.get("code_challenge", "").strip()
        code_challenge_method = params.get("code_challenge_method", "S256")
        state = params.get("state", "")
        scope = params.get("scope", "")

        if not client_id:
            return JSONResponse({"error": "invalid_request", "error_description": "Missing client_id."}, status_code=400)
        if code_challenge_method != "S256":
            return JSONResponse({"error": "invalid_request", "error_description": "Only S256 code challenge method is supported."}, status_code=400)
        if not code_challenge:
            return JSONResponse({"error": "invalid_request", "error_description": "Missing code_challenge. PKCE (S256) is required."}, status_code=400)
        if not redirect_uri:
            return JSONResponse({"error": "invalid_request", "error_description": "Missing redirect_uri."}, status_code=400)
        if not _is_redirect_uri_allowed(client_id, redirect_uri):
            return JSONResponse({"error": "invalid_request", "error_description": "redirect_uri is not registered for this client."}, status_code=400)

        session_key = secrets.token_urlsafe(32)
        store.set(
            _OAUTH_SESSION_PREFIX + session_key,
            json.dumps({
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                "state": state,
                "scope": scope,
            }),
            _OAUTH_SESSION_TTL,
        )

        frontend_url = _get_frontend_url()
        login_url = f"{frontend_url}/login?{urlencode({'mcp_oauth_session': session_key})}"
        return RedirectResponse(login_url, status_code=302)

    # ------------------------------------------------------------------
    # POST /authorize/complete — called by frontend after login to finish
    # the OAuth flow.  Expects JSON ``{"session": "…"}`` with a Bearer
    # token in the Authorization header.
    # ------------------------------------------------------------------
    async def authorize_complete(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"error": "invalid_request", "error_description": "Invalid JSON body."}, status_code=400)

        session_key = body.get("session", "").strip()
        if not session_key:
            return JSONResponse({"error": "invalid_request", "error_description": "Missing session."}, status_code=400)

        raw = store.get(_OAUTH_SESSION_PREFIX + session_key)
        if not raw:
            return JSONResponse({"error": "invalid_request", "error_description": "OAuth session expired or invalid. Please restart the authorization flow."}, status_code=400)
        store.delete(_OAUTH_SESSION_PREFIX + session_key)
        session_data = json.loads(raw)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse({"error": "unauthorized", "error_description": "Missing Bearer token."}, status_code=401)
        access_token = auth_header[7:]

        try:
            from src.services.auth_service import auth_service
            payload = await auth_service.verify_token(access_token)
            user_id = int(payload.get("sub"))
            user = await auth_service.get_user_by_id(user_id)
            if not user:
                return JSONResponse({"error": "unauthorized", "error_description": "User not found or inactive."}, status_code=401)
        except Exception as exc:
            logger.warning("OAuth authorize/complete: token validation failed: %s", exc)
            return JSONResponse({"error": "unauthorized", "error_description": "Invalid or expired token."}, status_code=401)

        code = secrets.token_urlsafe(48)
        store.set(
            _CODE_PREFIX + code,
            json.dumps({
                "user_id": user.id,
                "client_id": session_data["client_id"],
                "code_challenge": session_data["code_challenge"],
                "redirect_uri": session_data["redirect_uri"],
                "scope": session_data.get("scope", ""),
            }),
            _CODE_TTL,
        )

        redirect_uri = session_data["redirect_uri"]
        redirect_params: dict[str, str] = {"code": code}
        if session_data.get("state"):
            redirect_params["state"] = session_data["state"]
        sep = "&" if "?" in redirect_uri else "?"
        target = f"{redirect_uri}{sep}{urlencode(redirect_params)}"

        return JSONResponse({"redirect_url": target})

    # ------------------------------------------------------------------
    # POST /token — code exchange or refresh
    # ------------------------------------------------------------------
    async def token_endpoint(request: Request) -> JSONResponse:
        store.cleanup_expired()
        try:
            body: dict[str, Any]
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                body = await request.json()
            else:
                form = await request.form()
                body = dict(form)

            grant_type = body.get("grant_type")

            if grant_type == "authorization_code":
                return await _handle_code_exchange(body, store)
            if grant_type == "refresh_token":
                return await _handle_refresh(body, store)

            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
        except Exception as exc:
            logger.exception("OAuth token endpoint error")
            return JSONResponse({"error": "server_error", "error_description": "An internal error occurred."}, status_code=500)

    return Starlette(
        routes=[
            Route("/.well-known/oauth-protected-resource", protected_resource_metadata),
            Route("/.well-known/oauth-authorization-server", authorization_server_metadata),
            Route("/authorize", authorize_get, methods=["GET", "HEAD"]),
            Route("/authorize/complete", authorize_complete, methods=["POST"]),
            Route("/token", token_endpoint, methods=["POST"]),
        ]
    )


async def _handle_code_exchange(body: dict[str, Any], store: _TokenStore) -> JSONResponse:
    code = body.get("code", "")
    verifier = body.get("code_verifier", "")
    redirect_uri = body.get("redirect_uri", "")
    client_id = body.get("client_id", "")

    raw = store.get(_CODE_PREFIX + code)
    if not raw:
        return JSONResponse({"error": "invalid_grant", "error_description": "Authorization code expired or invalid."}, status_code=400)

    store.delete(_CODE_PREFIX + code)

    data = json.loads(raw)

    if data.get("client_id") and data["client_id"] != client_id:
        return JSONResponse({"error": "invalid_grant", "error_description": "client_id mismatch."}, status_code=400)

    if data.get("redirect_uri") != redirect_uri:
        return JSONResponse({"error": "invalid_grant", "error_description": "redirect_uri mismatch."}, status_code=400)

    expected_challenge = data.get("code_challenge", "")
    if not expected_challenge or _s256(verifier) != expected_challenge:
        return JSONResponse({"error": "invalid_grant", "error_description": "PKCE verification failed."}, status_code=400)

    try:
        from src.services.auth_service import auth_service
        from src.models.auth import User
        from src.models import database

        if database.SessionLocal is None:
            database.init_database()
        db = database.SessionLocal()
        try:
            user = db.query(User).filter(User.id == data["user_id"], User.is_active.is_(True)).first()
            if not user:
                return JSONResponse({"error": "invalid_grant", "error_description": "User not found or inactive."}, status_code=400)
            access_token, _platform_refresh = await auth_service.create_session_for_user(user)
        finally:
            db.close()
    except Exception as exc:
        logger.exception("OAuth code exchange: failed to mint token")
        return JSONResponse({"error": "server_error", "error_description": "An internal error occurred."}, status_code=500)

    mcp_refresh = secrets.token_urlsafe(48)
    store.set(
        _REFRESH_PREFIX + mcp_refresh,
        json.dumps({
            "user_id": data["user_id"],
            "client_id": data.get("client_id", ""),
            "scope": data.get("scope", ""),
        }),
        _REFRESH_TTL,
    )

    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 28800,
        "refresh_token": mcp_refresh,
        "scope": data.get("scope", ""),
    })


async def _handle_refresh(body: dict[str, Any], store: _TokenStore) -> JSONResponse:
    old_token = body.get("refresh_token", "")
    client_id = body.get("client_id", "")

    raw = store.get(_REFRESH_PREFIX + old_token)
    if not raw:
        return JSONResponse({"error": "invalid_grant", "error_description": "Refresh token expired or invalid."}, status_code=400)

    data = json.loads(raw)
    store.delete(_REFRESH_PREFIX + old_token)

    if data.get("client_id") and data["client_id"] != client_id:
        return JSONResponse({"error": "invalid_grant", "error_description": "client_id mismatch."}, status_code=400)

    try:
        from src.services.auth_service import auth_service
        from src.models.auth import User
        from src.models import database

        if database.SessionLocal is None:
            database.init_database()
        db = database.SessionLocal()
        try:
            user = db.query(User).filter(User.id == data["user_id"], User.is_active.is_(True)).first()
            if not user:
                return JSONResponse({"error": "invalid_grant", "error_description": "User not found or inactive."}, status_code=400)

            access_token, _platform_refresh = await auth_service.create_session_for_user(user)
        finally:
            db.close()
    except Exception as exc:
        logger.exception("OAuth refresh failed")
        return JSONResponse({"error": "server_error", "error_description": "An internal error occurred."}, status_code=500)

    new_refresh = secrets.token_urlsafe(48)
    store.set(
        _REFRESH_PREFIX + new_refresh,
        json.dumps({
            "user_id": data["user_id"],
            "client_id": data.get("client_id", ""),
            "scope": data.get("scope", ""),
        }),
        _REFRESH_TTL,
    )

    return JSONResponse({
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 28800,
        "refresh_token": new_refresh,
        "scope": data.get("scope", ""),
    })
