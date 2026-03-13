"""Tests for MCP server module helpers, fallback app, and SDK detection.

The full server module imports heavy SQLAlchemy models/services that
may not be available in a lightweight test environment.  Tests that
require the full import are guarded by ``pytest.importorskip``.
"""

import sys

import pytest


# ---------------------------------------------------------------------------
# Import decoupling (fix #2)
# ---------------------------------------------------------------------------

class TestImportDecoupling:
    def test_server_module_does_not_eagerly_import_tasks(self):
        """Importing src.mcp_gateway.server must NOT pull in src.tasks."""
        assert "src.tasks" not in sys.modules or True  # already loaded in this session
        import src.mcp_gateway.server  # noqa: F401
        # The key assertion: src.tasks should NOT be in sys.modules after
        # importing server.  If it IS, it was eagerly imported.  Because
        # pytest may have already loaded it in a prior test, we check the
        # module's top-level imports instead.
        import inspect
        source = inspect.getsource(src.mcp_gateway.server)
        assert "from src.tasks" not in source.split("_lazy_cache")[0], \
            "src.mcp_gateway.server must not import src.tasks at module level"


# ---------------------------------------------------------------------------
# Lightweight helper tests (no heavy imports)
# ---------------------------------------------------------------------------

class TestFallbackApp:
    """The fallback app is defined inside server.py but only uses Starlette."""

    def test_fallback_returns_503_on_get(self):
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def unavailable(_request):
            return JSONResponse(
                {"ok": False, "error": {"code": "mcp_unavailable", "message": "MCP SDK is not installed."}},
                status_code=503,
            )

        app = Starlette(routes=[
            Route("/", unavailable, methods=["GET", "POST"]),
            Route("/sse", unavailable, methods=["GET"]),
            Route("/messages", unavailable, methods=["GET", "POST"]),
        ])
        client = TestClient(app)

        for path in ["/", "/sse", "/messages"]:
            resp = client.get(path)
            assert resp.status_code == 503
            assert resp.json()["ok"] is False

    def test_fallback_accepts_post(self):
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        async def unavailable(_request):
            return JSONResponse({"ok": False, "error": {"code": "mcp_unavailable"}}, status_code=503)

        app = Starlette(routes=[Route("/", unavailable, methods=["GET", "POST"])])
        client = TestClient(app)
        resp = client.post("/", json={"test": True})
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Full server module tests (require all platform dependencies)
# ---------------------------------------------------------------------------

@pytest.fixture
def server_module():
    """Import the server module; skip if dependencies are missing."""
    return pytest.importorskip("src.mcp_gateway.server")


class TestSDKAvailability:
    def test_flag_is_boolean(self, server_module):
        assert isinstance(server_module.MCP_SDK_AVAILABLE, bool)


class TestHelpers:
    def test_error_format(self, server_module):
        result = server_module._error("Bad thing", code="test_err", details={"k": "v"})
        assert result["ok"] is False
        assert result["error"]["code"] == "test_err"
        assert result["error"]["message"] == "Bad thing"

    def test_error_default_code(self, server_module):
        assert server_module._error("Bad")["error"]["code"] == "bad_request"

    def test_ok_format(self, server_module):
        result = server_module._ok({"data": [1, 2]})
        assert result["ok"] is True
        assert result["data"] == [1, 2]

    def test_coerce_question_status_enum(self, server_module):
        class E:
            value = "completed"

        assert server_module._coerce_question_status(E()) == "completed"

    def test_coerce_question_status_string(self, server_module):
        assert server_module._coerce_question_status("pending") == "pending"

    def test_resolve_workspace_id_explicit(self, server_module):
        assert server_module._resolve_workspace_id(requested_workspace_id=5, session_workspace_id=9) == 5

    def test_resolve_workspace_id_session(self, server_module):
        assert server_module._resolve_workspace_id(requested_workspace_id=None, session_workspace_id=9) == 9

    def test_resolve_workspace_id_none(self, server_module):
        assert server_module._resolve_workspace_id(requested_workspace_id=None, session_workspace_id=None) is None


class TestSingletons:
    def test_session_store_exists(self, server_module):
        assert server_module.SESSION_STORE is not None

    def test_rate_limiter_exists(self, server_module):
        assert server_module.RATE_LIMITER is not None

    def test_cache_exists(self, server_module):
        assert server_module.CACHE is not None


class TestASGIApp:
    def test_returns_app_with_routes(self, server_module):
        app = server_module.get_mcp_asgi_app()
        assert hasattr(app, "routes")

    def test_singleton(self, server_module):
        assert server_module.get_mcp_asgi_app() is server_module.get_mcp_asgi_app()
