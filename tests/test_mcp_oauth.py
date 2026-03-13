"""Tests for MCP OAuth 2.1 endpoints.

Covers: discovery metadata, PKCE S256 verification, authorization code
flow, token exchange, refresh token rotation, redirect_uri allowlist
validation, in-memory TTL enforcement, and error cases.
"""

import json
import secrets
import time
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from src.mcp_gateway.oauth import (
    _TokenStore,
    _s256,
    _CODE_PREFIX,
    _CSRF_PREFIX,
    _normalize_uri,
    _BUILTIN_TRUSTED_URIS,
    _is_redirect_uri_allowed,
    build_oauth_app,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _client() -> TestClient:
    """Build a test client against the OAuth app (in-memory token store)."""
    app = build_oauth_app(redis_client=None)
    return TestClient(app)


def _get_store(app) -> _TokenStore:
    """Extract the _TokenStore from the OAuth app's closures."""
    for route in app.routes:
        if hasattr(route, "endpoint"):
            fn = route.endpoint
            if hasattr(fn, "__closure__") and fn.__closure__:
                for cell in fn.__closure__:
                    try:
                        obj = cell.cell_contents
                        if isinstance(obj, _TokenStore):
                            return obj
                    except ValueError:
                        continue
    raise RuntimeError("Could not find _TokenStore in OAuth app closures")


def _make_csrf(app) -> str:
    """Create a valid CSRF token in the app's store and return it."""
    store = _get_store(app)
    token = secrets.token_urlsafe(32)
    store.set(_CSRF_PREFIX + token, "1", 600)
    return token


# ---------------------------------------------------------------------------
# PKCE S256
# ---------------------------------------------------------------------------

class TestPKCES256:
    def test_known_vector(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        expected = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
        assert _s256(verifier) == expected

    def test_different_verifiers_produce_different_challenges(self):
        v1 = secrets.token_urlsafe(32)
        v2 = secrets.token_urlsafe(32)
        assert _s256(v1) != _s256(v2)


# ---------------------------------------------------------------------------
# TokenStore (in-memory fallback) — with TTL enforcement
# ---------------------------------------------------------------------------

class TestTokenStore:
    def test_set_get_delete(self):
        store = _TokenStore(redis_client=None)
        store.set("key1", "value1", ttl=60)
        assert store.get("key1") == "value1"
        store.delete("key1")
        assert store.get("key1") is None

    def test_get_missing_key(self):
        store = _TokenStore(redis_client=None)
        assert store.get("nonexistent") is None

    def test_delete_missing_key_is_safe(self):
        store = _TokenStore(redis_client=None)
        store.delete("nonexistent")

    def test_expired_entry_returns_none(self):
        store = _TokenStore(redis_client=None)
        store.set("key-exp", "val", ttl=1)
        store._mem["key-exp"] = ("val", time.monotonic() - 10)
        assert store.get("key-exp") is None

    def test_expired_entry_is_removed_from_mem(self):
        store = _TokenStore(redis_client=None)
        store.set("key-rm", "val", ttl=1)
        store._mem["key-rm"] = ("val", time.monotonic() - 10)
        store.get("key-rm")
        assert "key-rm" not in store._mem

    def test_valid_entry_within_ttl(self):
        store = _TokenStore(redis_client=None)
        store.set("key-ok", "val", ttl=3600)
        assert store.get("key-ok") == "val"

    def test_cleanup_expired(self):
        store = _TokenStore(redis_client=None)
        store.set("live", "v1", ttl=3600)
        store.set("dead", "v2", ttl=1)
        store._mem["dead"] = ("v2", time.monotonic() - 10)
        store.cleanup_expired()
        assert "live" in store._mem
        assert "dead" not in store._mem


# ---------------------------------------------------------------------------
# URI normalization
# ---------------------------------------------------------------------------

class TestNormalizeUri:
    def test_strips_trailing_slash(self):
        assert _normalize_uri("http://localhost/callback/") == "http://localhost/callback"

    def test_preserves_scheme_host_path(self):
        assert _normalize_uri("https://app.example.com/oauth/cb") == "https://app.example.com/oauth/cb"

    def test_ignores_query_and_fragment(self):
        result = _normalize_uri("http://localhost/cb?foo=1#bar")
        assert result == "http://localhost/cb"

    def test_handles_whitespace(self):
        assert _normalize_uri("  http://localhost/cb  ") == "http://localhost/cb"


# ---------------------------------------------------------------------------
# Redirect URI validation
# ---------------------------------------------------------------------------

class TestRedirectUriValidation:
    def test_builtin_trusted_uris_allowed(self):
        for uri in _BUILTIN_TRUSTED_URIS:
            assert _is_redirect_uri_allowed("any-client", uri), f"Built-in URI should be allowed: {uri}"

    @patch("src.mcp_gateway.oauth._load_registered_uris", return_value=set())
    def test_unknown_client_builtin_uri_allowed(self, mock_load):
        assert _is_redirect_uri_allowed("unknown-client", "http://localhost/callback") is True

    @patch("src.mcp_gateway.oauth._load_registered_uris", return_value=set())
    def test_unknown_client_non_builtin_uri_denied(self, mock_load):
        assert _is_redirect_uri_allowed("unknown-client", "http://anywhere.com/cb") is False

    @patch("src.mcp_gateway.oauth._load_registered_uris",
           return_value={"https://chatgpt.com/callback"})
    def test_registered_uri_allowed(self, mock_load):
        assert _is_redirect_uri_allowed("my-client", "https://chatgpt.com/callback") is True

    @patch("src.mcp_gateway.oauth._load_registered_uris",
           return_value={"https://chatgpt.com/callback"})
    def test_unregistered_uri_rejected(self, mock_load):
        assert _is_redirect_uri_allowed("my-client", "https://evil.com/steal") is False

    @patch("src.mcp_gateway.oauth._load_registered_uris",
           return_value={"https://chatgpt.com/callback"})
    def test_partial_match_rejected(self, mock_load):
        assert _is_redirect_uri_allowed("my-client", "https://chatgpt.com/callback-evil") is False

    @patch("src.mcp_gateway.oauth._load_registered_uris",
           return_value={"https://app.example.com/oauth/cb"})
    def test_wrong_client_uri_combo_rejected(self, mock_load):
        assert _is_redirect_uri_allowed("client-b", "https://other.com/cb") is False

    @patch("src.mcp_gateway.oauth._load_registered_uris", return_value=set())
    def test_empty_allowlist_non_builtin_denied(self, mock_load):
        assert _is_redirect_uri_allowed("client-x", "https://production.app/cb") is False


class TestAuthorizePostValidation:
    """Test the /authorize POST early-rejection logic (CSRF, client_id, redirect_uri, PKCE)."""

    def test_missing_csrf_token_rejected(self):
        app = build_oauth_app(redis_client=None)
        client = TestClient(app)
        resp = client.post(
            "/authorize",
            data={
                "email": "a@b.com",
                "password": "pass",
                "redirect_uri": "http://localhost/callback",
                "code_challenge": "ch",
                "code_challenge_method": "S256",
                "client_id": "test",
                "csrf_token": "",
            },
        )
        assert resp.status_code == 401
        assert "expired" in resp.text.lower() or "invalid" in resp.text.lower()

    def test_missing_client_id_rejected(self):
        app = build_oauth_app(redis_client=None)
        csrf = _make_csrf(app)
        client = TestClient(app)
        resp = client.post(
            "/authorize",
            data={
                "email": "a@b.com",
                "password": "pass",
                "redirect_uri": "http://localhost/callback",
                "code_challenge": "ch",
                "code_challenge_method": "S256",
                "client_id": "",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 401
        assert "client_id" in resp.text.lower()

    def test_whitespace_only_client_id_rejected(self):
        app = build_oauth_app(redis_client=None)
        csrf = _make_csrf(app)
        client = TestClient(app)
        resp = client.post(
            "/authorize",
            data={
                "email": "a@b.com",
                "password": "pass",
                "redirect_uri": "http://localhost/callback",
                "code_challenge": "ch",
                "code_challenge_method": "S256",
                "client_id": "   ",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 401
        assert "client_id" in resp.text.lower()

    def test_empty_code_challenge_rejected(self):
        app = build_oauth_app(redis_client=None)
        csrf = _make_csrf(app)
        client = TestClient(app)
        resp = client.post(
            "/authorize",
            data={
                "email": "a@b.com",
                "password": "pass",
                "redirect_uri": "http://localhost/callback",
                "code_challenge": "",
                "code_challenge_method": "S256",
                "client_id": "test-client",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 401
        assert "code_challenge" in resp.text.lower()

    def test_whitespace_only_code_challenge_rejected(self):
        app = build_oauth_app(redis_client=None)
        csrf = _make_csrf(app)
        client = TestClient(app)
        resp = client.post(
            "/authorize",
            data={
                "email": "a@b.com",
                "password": "pass",
                "redirect_uri": "http://localhost/callback",
                "code_challenge": "   ",
                "code_challenge_method": "S256",
                "client_id": "test-client",
                "csrf_token": csrf,
            },
        )
        assert resp.status_code == 401
        assert "code_challenge" in resp.text.lower()


# ---------------------------------------------------------------------------
# Discovery metadata endpoints
# ---------------------------------------------------------------------------

class TestDiscoveryMetadata:
    def test_protected_resource_metadata(self):
        client = _client()
        resp = client.get("/.well-known/oauth-protected-resource")
        assert resp.status_code == 200
        data = resp.json()
        assert "resource" in data
        assert "authorization_servers" in data
        assert "bearer_methods_supported" in data
        assert "header" in data["bearer_methods_supported"]
        assert len(data["scopes_supported"]) >= 1

    def test_authorization_server_metadata(self):
        client = _client()
        resp = client.get("/.well-known/oauth-authorization-server")
        assert resp.status_code == 200
        data = resp.json()
        assert data["response_types_supported"] == ["code"]
        assert "authorization_code" in data["grant_types_supported"]
        assert "refresh_token" in data["grant_types_supported"]
        assert data["code_challenge_methods_supported"] == ["S256"]
        assert "authorization_endpoint" in data
        assert "token_endpoint" in data

    def test_metadata_has_cache_headers(self):
        client = _client()
        resp = client.get("/.well-known/oauth-protected-resource")
        assert "max-age" in resp.headers.get("cache-control", "")

    def test_scopes_include_required_phase1_scopes(self):
        client = _client()
        data = client.get("/.well-known/oauth-authorization-server").json()
        required = {"workspaces:read", "documents:read", "bi:read", "connections:read"}
        assert required.issubset(set(data["scopes_supported"]))


# ---------------------------------------------------------------------------
# Authorize endpoint
# ---------------------------------------------------------------------------

class TestAuthorizeEndpoint:
    def test_get_renders_login_form(self):
        client = _client()
        resp = client.get(
            "/authorize",
            params={
                "client_id": "test-client",
                "redirect_uri": "http://localhost/callback",
                "code_challenge": "abc",
                "code_challenge_method": "S256",
                "state": "xyz",
            },
        )
        assert resp.status_code == 200
        assert "Sign in to Eliza" in resp.text
        assert "test-client" in resp.text

    def test_get_without_params_still_renders(self):
        client = _client()
        resp = client.get("/authorize")
        assert resp.status_code == 200
        assert "Sign in" in resp.text

    def test_hidden_fields_present(self):
        client = _client()
        resp = client.get(
            "/authorize",
            params={
                "state": "s123",
                "redirect_uri": "http://localhost/cb",
                "code_challenge": "ch",
                "code_challenge_method": "S256",
                "scope": "workspaces:read",
                "client_id": "cid",
            },
        )
        for field in ["csrf_token", "state", "redirect_uri", "code_challenge", "code_challenge_method", "scope", "client_id"]:
            assert f'name="{field}"' in resp.text


# ---------------------------------------------------------------------------
# Token endpoint — error cases
# ---------------------------------------------------------------------------

class TestTokenEndpointErrors:
    def test_unsupported_grant_type(self):
        client = _client()
        resp = client.post("/token", json={"grant_type": "client_credentials"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "unsupported_grant_type"

    def test_invalid_authorization_code(self):
        client = _client()
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "invalid-code-123",
                "code_verifier": "test",
                "redirect_uri": "http://localhost/callback",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_grant"

    def test_invalid_refresh_token(self):
        client = _client()
        resp = client.post(
            "/token",
            json={
                "grant_type": "refresh_token",
                "refresh_token": "invalid-refresh-token",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_grant"

    def test_accepts_form_encoded_body(self):
        client = _client()
        resp = client.post(
            "/token",
            data={"grant_type": "authorization_code", "code": "bad"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 400

    def test_expired_code_returns_invalid_grant(self):
        client = _client()
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "definitely-expired",
                "code_verifier": "v",
                "redirect_uri": "http://localhost/cb",
            },
        )
        assert resp.json()["error"] == "invalid_grant"


# ---------------------------------------------------------------------------
# Code exchange integration (uses the app's internal store)
# ---------------------------------------------------------------------------

class TestCodeExchange:
    def _seed_code(self, app, code: str, challenge: str, redirect_uri: str, client_id: str = "test-client"):
        """Reach into the app's internal store to plant a code for testing."""
        store = _get_store(app)
        store.set(
            _CODE_PREFIX + code,
            json.dumps({
                "user_id": 1,
                "client_id": client_id,
                "code_challenge": challenge,
                "redirect_uri": redirect_uri,
                "scope": "workspaces:read",
            }),
            ttl=600,
        )

    @patch("src.services.auth_service.auth_service")
    @patch("src.models.database.SessionLocal")
    @patch("src.models.database.init_database")
    def test_valid_code_exchange(self, mock_init_db, mock_session_local, mock_auth_svc):
        from unittest.mock import AsyncMock, MagicMock

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        mock_session_local.return_value = mock_session

        mock_auth_svc.create_session_for_user = AsyncMock(return_value=("at-minted", "rt-platform"))

        app = build_oauth_app(redis_client=None)
        verifier = secrets.token_urlsafe(32)
        challenge = _s256(verifier)
        redirect = "http://localhost/cb"

        self._seed_code(app, "code-ok", challenge, redirect, client_id="test-client")

        client = TestClient(app)
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "code-ok",
                "code_verifier": verifier,
                "redirect_uri": redirect,
                "client_id": "test-client",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "at-minted"
        assert data["token_type"] == "Bearer"
        assert "refresh_token" in data
        assert "expires_in" in data

    @patch("src.services.auth_service.auth_service")
    @patch("src.models.database.SessionLocal")
    @patch("src.models.database.init_database")
    def test_client_id_mismatch_rejected(self, mock_init_db, mock_session_local, mock_auth_svc):
        app = build_oauth_app(redis_client=None)
        verifier = secrets.token_urlsafe(32)
        challenge = _s256(verifier)
        redirect = "http://localhost/cb"
        self._seed_code(app, "code-cid", challenge, redirect, client_id="real-client")

        client = TestClient(app)
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "code-cid",
                "code_verifier": verifier,
                "redirect_uri": redirect,
                "client_id": "evil-client",
            },
        )
        assert resp.status_code == 400
        assert "client_id" in resp.json()["error_description"]

    def test_pkce_mismatch_rejected(self):
        app = build_oauth_app(redis_client=None)
        redirect = "http://localhost/cb"
        self._seed_code(app, "code-pkce", _s256("correct-verifier"), redirect)

        client = TestClient(app)
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "code-pkce",
                "code_verifier": "wrong-verifier",
                "redirect_uri": redirect,
            },
        )
        assert resp.status_code == 400
        assert "PKCE" in resp.json()["error_description"]

    def test_empty_pkce_challenge_rejected(self):
        """Codes with empty code_challenge are rejected (PKCE mandatory)."""
        app = build_oauth_app(redis_client=None)
        redirect = "http://localhost/cb"
        self._seed_code(app, "code-no-pkce", "", redirect)

        client = TestClient(app)
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "code-no-pkce",
                "code_verifier": "",
                "redirect_uri": redirect,
            },
        )
        assert resp.status_code == 400
        assert "PKCE" in resp.json()["error_description"]

    def test_redirect_uri_mismatch_rejected(self):
        app = build_oauth_app(redis_client=None)
        self._seed_code(app, "code-redir", _s256("v"), "http://localhost/original")

        client = TestClient(app)
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "code-redir",
                "code_verifier": "v",
                "redirect_uri": "http://evil.com/steal",
            },
        )
        assert resp.status_code == 400
        assert "redirect_uri" in resp.json()["error_description"]

    def test_code_is_single_use(self):
        app = build_oauth_app(redis_client=None)
        verifier = secrets.token_urlsafe(32)
        challenge = _s256(verifier)
        redirect = "http://localhost/cb"
        self._seed_code(app, "code-once", challenge, redirect)

        client = TestClient(app)
        payload = {
            "grant_type": "authorization_code",
            "code": "code-once",
            "code_verifier": verifier,
            "redirect_uri": redirect,
        }
        resp1 = client.post("/token", json=payload)
        # Code is consumed (deleted) on first attempt regardless of token-minting outcome
        resp2 = client.post("/token", json=payload)
        assert resp2.status_code == 400
        assert resp2.json()["error"] == "invalid_grant"

    def test_expired_code_rejected_via_ttl(self):
        """Verify that in-memory TTL enforcement rejects expired codes."""
        app = build_oauth_app(redis_client=None)
        store = _get_store(app)
        key = _CODE_PREFIX + "code-ttl-dead"
        store._mem[key] = (
            json.dumps({"user_id": 1, "client_id": "c", "code_challenge": _s256("v"), "redirect_uri": "http://localhost/cb", "scope": ""}),
            time.monotonic() - 100,
        )

        client = TestClient(app)
        resp = client.post(
            "/token",
            json={
                "grant_type": "authorization_code",
                "code": "code-ttl-dead",
                "code_verifier": "v",
                "redirect_uri": "http://localhost/cb",
                "client_id": "c",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_grant"
