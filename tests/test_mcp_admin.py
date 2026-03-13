"""Tests for MCP admin API Pydantic schemas.

Covers: model validation, default values, partial updates, and
serialization.  Imports the Pydantic schemas directly — they are
defined before the router decorators in admin.py, so we isolate them
by stubbing the heavy middleware/model dependencies at import time
and cleaning up afterwards.
"""

import importlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixture: import the admin module with stubs, clean up after
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def admin_schemas():
    """Import admin Pydantic schemas while stubbing heavy deps."""
    stubs_to_add = {}
    originals = {}

    deps = [
        "bcrypt",
        "jwt",
        "src.middleware",
        "src.middleware.authorization",
        "src.models",
        "src.models.auth",
        "src.models.database",
        "src.models.mcp_config",
        "src.services",
        "src.services.auth_service",
    ]
    for mod_name in deps:
        originals[mod_name] = sys.modules.get(mod_name)
        if mod_name not in sys.modules:
            stubs_to_add[mod_name] = MagicMock()
            sys.modules[mod_name] = stubs_to_add[mod_name]

    # Force (re-)import of the admin module with stubs active
    if "src.mcp_gateway.admin" in sys.modules:
        mod = importlib.reload(sys.modules["src.mcp_gateway.admin"])
    else:
        mod = importlib.import_module("src.mcp_gateway.admin")

    yield mod

    # Cleanup: remove stubs we added, restore originals
    for mod_name in stubs_to_add:
        if originals[mod_name] is None:
            sys.modules.pop(mod_name, None)
        else:
            sys.modules[mod_name] = originals[mod_name]


# ---------------------------------------------------------------------------
# Create schema
# ---------------------------------------------------------------------------

class TestConfigCreateSchema:
    def test_defaults(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate()
        assert config.server_type == "chat"
        assert config.server_name == "eliza-chat"
        assert config.is_enabled is False
        assert config.rate_limit_rpm == 30
        assert config.rate_limit_rph == 500
        assert config.max_concurrent_sessions == 50
        assert config.max_async_operations == 5
        assert config.allowed_workspace_ids == []
        assert config.allowed_tool_names == []
        assert config.enabled_widgets == []
        assert config.oauth_client_id is None
        assert config.oauth_redirect_uris == []

    def test_custom_values(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate(
            server_type="applet",
            server_name="eliza-recruiter",
            display_name="AI Recruiter",
            description="Talent tools",
            is_enabled=True,
            rate_limit_rpm=60,
            rate_limit_rph=1000,
            allowed_workspace_ids=[1, 2, 3],
            oauth_client_id="tenant-recruiter",
            oauth_redirect_uris=["https://chatgpt.com/callback"],
        )
        assert config.server_type == "applet"
        assert config.display_name == "AI Recruiter"
        assert config.is_enabled is True
        assert config.rate_limit_rpm == 60
        assert config.allowed_workspace_ids == [1, 2, 3]
        assert config.oauth_client_id == "tenant-recruiter"
        assert config.oauth_redirect_uris == ["https://chatgpt.com/callback"]

    def test_model_dump(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate(display_name="Test")
        data = config.model_dump()
        assert "server_type" in data
        assert "server_name" in data
        assert "rate_limit_rpm" in data
        assert "oauth_client_id" in data
        assert "oauth_redirect_uris" in data


# ---------------------------------------------------------------------------
# Update schema
# ---------------------------------------------------------------------------

class TestConfigUpdateSchema:
    def test_all_fields_optional(self, admin_schemas):
        config = admin_schemas.MCPServerConfigUpdate()
        data = config.model_dump(exclude_unset=True)
        assert data == {}

    def test_partial_update(self, admin_schemas):
        config = admin_schemas.MCPServerConfigUpdate(display_name="New Name", is_enabled=True)
        data = config.model_dump(exclude_unset=True)
        assert data == {"display_name": "New Name", "is_enabled": True}

    def test_rate_limits_updatable(self, admin_schemas):
        config = admin_schemas.MCPServerConfigUpdate(rate_limit_rpm=100, rate_limit_rph=2000)
        data = config.model_dump(exclude_unset=True)
        assert data["rate_limit_rpm"] == 100
        assert data["rate_limit_rph"] == 2000

    def test_oauth_fields_updatable(self, admin_schemas):
        config = admin_schemas.MCPServerConfigUpdate(
            oauth_client_id="tenant-workspaces",
            oauth_redirect_uris=["https://claude.ai/api/mcp/auth_callback"],
        )
        data = config.model_dump(exclude_unset=True)
        assert data["oauth_client_id"] == "tenant-workspaces"
        assert data["oauth_redirect_uris"] == ["https://claude.ai/api/mcp/auth_callback"]


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class TestConfigResponseSchema:
    def test_from_attributes_enabled(self, admin_schemas):
        assert admin_schemas.MCPServerConfigResponse.model_config.get("from_attributes") is True

    def test_required_fields(self, admin_schemas):
        fields = admin_schemas.MCPServerConfigResponse.model_fields
        required_names = {"id", "customer_id", "server_type", "server_name",
                         "is_enabled", "rate_limit_rpm", "rate_limit_rph",
                         "max_concurrent_sessions", "max_async_operations",
                         "server_url", "authorization_url", "token_url"}
        for name in required_names:
            assert name in fields, f"Missing required field: {name}"


# ---------------------------------------------------------------------------
# Validation rules
# ---------------------------------------------------------------------------

class TestValidation:
    def test_icon_url_rejects_javascript(self, admin_schemas):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="icon_url"):
            admin_schemas.MCPServerConfigCreate(icon_url="javascript:alert(1)")

    def test_icon_url_rejects_data_uri(self, admin_schemas):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="icon_url"):
            admin_schemas.MCPServerConfigCreate(icon_url="data:text/html,<h1>hi</h1>")

    def test_icon_url_accepts_https(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate(icon_url="https://cdn.example.com/icon.png")
        assert config.icon_url == "https://cdn.example.com/icon.png"

    def test_icon_url_accepts_http(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate(icon_url="http://localhost/icon.png")
        assert config.icon_url == "http://localhost/icon.png"

    def test_icon_url_accepts_none(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate(icon_url=None)
        assert config.icon_url is None

    def test_description_max_length(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate(description="x" * 5000)
        assert len(config.description) == 5000

    def test_description_exceeds_max_length_rejected(self, admin_schemas):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            admin_schemas.MCPServerConfigCreate(description="x" * 5001)

    def test_redirect_uris_are_trimmed_and_deduplicated(self, admin_schemas):
        config = admin_schemas.MCPServerConfigCreate(
            oauth_redirect_uris=[
                " https://chatgpt.com/callback ",
                "https://chatgpt.com/callback",
                "http://localhost/callback",
            ]
        )
        assert config.oauth_redirect_uris == [
            "https://chatgpt.com/callback",
            "http://localhost/callback",
        ]

    def test_redirect_uris_reject_non_http_schemes(self, admin_schemas):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="oauth_redirect_uris"):
            admin_schemas.MCPServerConfigCreate(
                oauth_redirect_uris=["javascript:alert(1)"]
            )
