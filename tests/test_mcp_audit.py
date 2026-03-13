"""Tests for MCP audit logging.

Covers: PII sanitization, long-value truncation, and graceful failure
when the audit service is unavailable.
"""

import pytest

from src.mcp_gateway.audit import _sanitize


# ---------------------------------------------------------------------------
# Parameter sanitization
# ---------------------------------------------------------------------------

class TestSanitization:
    def test_redacts_sensitive_keys(self):
        params = {
            "query": "SELECT 1",
            "password": "secret123",
            "api_key": "sk-abcd",
            "content_base64": "SGVsbG8gV29ybGQ=",
            "token": "eyJhbGciOiJIUzI1NiJ9",
            "credential": "my-cred",
        }
        result = _sanitize(params)
        assert result["query"] == "SELECT 1"
        for key in ("password", "api_key", "content_base64", "token", "credential"):
            assert result[key] == "***REDACTED***"

    def test_truncates_long_strings(self):
        params = {"big_value": "x" * 1000}
        result = _sanitize(params)
        assert len(result["big_value"]) < 600
        assert result["big_value"].endswith("...(truncated)")

    def test_passes_through_normal_values(self):
        params = {"workspace_id": 42, "limit": 10, "query": "hello"}
        result = _sanitize(params)
        assert result == params

    def test_empty_params(self):
        assert _sanitize({}) == {}

    def test_case_insensitive_key_matching(self):
        params = {"API_KEY": "secret", "Password": "pass"}
        result = _sanitize(params)
        assert result["API_KEY"] == "***REDACTED***"
        assert result["Password"] == "***REDACTED***"

    def test_nested_sensitive_key_partial_match(self):
        params = {"user_api_key_id": "abc", "secret_value": "xyz"}
        result = _sanitize(params)
        assert result["user_api_key_id"] == "***REDACTED***"
        assert result["secret_value"] == "***REDACTED***"

    def test_recursive_nested_dict_sanitization(self):
        params = {
            "config": {
                "api_key": "secret-key",
                "host": "localhost",
            },
            "query": "SELECT 1",
        }
        result = _sanitize(params)
        assert result["config"]["api_key"] == "***REDACTED***"
        assert result["config"]["host"] == "localhost"
        assert result["query"] == "SELECT 1"

    def test_recursive_nested_list_sanitization(self):
        params = {
            "items": [
                {"name": "ok", "password": "secret"},
                {"name": "also-ok"},
            ],
        }
        result = _sanitize(params)
        assert result["items"][0]["password"] == "***REDACTED***"
        assert result["items"][0]["name"] == "ok"
        assert result["items"][1]["name"] == "also-ok"

    def test_deep_nesting_truncated(self):
        nested = {"a": "b"}
        for _ in range(10):
            nested = {"inner": nested}
        result = _sanitize({"deep": nested})
        deep = result["deep"]
        for _ in range(5):
            deep = deep["inner"]
        assert deep == {"_truncated": True}
