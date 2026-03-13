"""
Connector Permissions API Tests

Tests that connector permissions are correctly enforced via the API.
These tests use the API exactly as the frontend would - no direct database access.

Required permissions for connector endpoints:
- connections:read   - GET /api/connectors/types, GET /api/connectors/configurations
- connections:create - POST /api/connectors/configurations
- connections:update - PUT /api/connectors/configurations/{id}
- connections:delete - DELETE /api/connectors/configurations/{id}
- connections:test   - POST /api/connectors/test-connection, POST /api/connectors/greenhouse/test-connection
- connections:sync   - POST /api/connectors/configurations/{id}/sync

Run with:
    cd docs/specs/testing
    pytest test_connector_permissions.py -v

Prerequisites:
    - Local environment running (docker compose up)
    - Test users created with different roles
"""

import pytest
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass


# ============================================================================
# Configuration
# ============================================================================

BASE_URL = "http://localhost:5001"
FRONTEND_URL = "http://localhost:3000"

# Test user credentials - these should exist in your local database
# with the appropriate roles assigned
TEST_USERS = {
    "platform_admin": {
        "email": "scott@eliza.com",
        "password": "admin123",  # Update with actual password
        "expected_access": {
            "connections:read": True,
            "connections:create": True,
            "connections:update": True,
            "connections:delete": True,
            "connections:test": True,
            "connections:sync": True,
        }
    },
    "tenant_admin": {
        "email": "admin@test-tenant.com",
        "password": "admin123",  # Update with actual password
        "expected_access": {
            "connections:read": True,
            "connections:create": True,
            "connections:update": True,
            "connections:delete": True,
            "connections:test": True,
            "connections:sync": True,
        }
    },
    "tenant_editor": {
        "email": "editor@test-tenant.com",
        "password": "editor123",  # Update with actual password
        "expected_access": {
            "connections:read": False,  # Editors should NOT have connection access
            "connections:create": False,
            "connections:update": False,
            "connections:delete": False,
            "connections:test": False,
            "connections:sync": False,
        }
    },
    "tenant_viewer": {
        "email": "viewer@test-tenant.com",
        "password": "viewer123",  # Update with actual password
        "expected_access": {
            "connections:read": False,  # Viewers should NOT have connection access
            "connections:create": False,
            "connections:update": False,
            "connections:delete": False,
            "connections:test": False,
            "connections:sync": False,
        }
    },
}


# ============================================================================
# Helper Classes
# ============================================================================

@dataclass
class AuthenticatedSession:
    """Holds session info for an authenticated user."""
    email: str
    access_token: str
    session: requests.Session
    
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated GET request."""
        return self.session.get(
            f"{BASE_URL}{endpoint}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            **kwargs
        )
    
    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated POST request."""
        return self.session.post(
            f"{BASE_URL}{endpoint}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            **kwargs
        )
    
    def put(self, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated PUT request."""
        return self.session.put(
            f"{BASE_URL}{endpoint}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            **kwargs
        )
    
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated DELETE request."""
        return self.session.delete(
            f"{BASE_URL}{endpoint}",
            headers={"Authorization": f"Bearer {self.access_token}"},
            **kwargs
        )


# ============================================================================
# Authentication Helpers
# ============================================================================

def login(email: str, password: str) -> Optional[AuthenticatedSession]:
    """
    Login via API and return authenticated session.
    
    Uses the same login flow as the frontend.
    """
    session = requests.Session()
    
    try:
        response = session.post(
            f"{BASE_URL}/v1/auth/login",
            json={"email": email, "password": password}
        )
        
        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            if access_token:
                return AuthenticatedSession(
                    email=email,
                    access_token=access_token,
                    session=session
                )
        
        print(f"Login failed for {email}: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        print(f"Login error for {email}: {e}")
        return None


def get_authenticated_user(user_type: str) -> Optional[AuthenticatedSession]:
    """Get authenticated session for a specific user type."""
    if user_type not in TEST_USERS:
        raise ValueError(f"Unknown user type: {user_type}")
    
    user_config = TEST_USERS[user_type]
    return login(user_config["email"], user_config["password"])


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def platform_admin_session():
    """Get authenticated session for platform admin."""
    session = get_authenticated_user("platform_admin")
    if not session:
        pytest.skip("Could not authenticate platform_admin user")
    return session


@pytest.fixture(scope="module")
def tenant_admin_session():
    """Get authenticated session for tenant admin."""
    session = get_authenticated_user("tenant_admin")
    if not session:
        pytest.skip("Could not authenticate tenant_admin user")
    return session


@pytest.fixture(scope="module")
def tenant_editor_session():
    """Get authenticated session for tenant editor."""
    session = get_authenticated_user("tenant_editor")
    if not session:
        pytest.skip("Could not authenticate tenant_editor user")
    return session


@pytest.fixture(scope="module")
def tenant_viewer_session():
    """Get authenticated session for tenant viewer."""
    session = get_authenticated_user("tenant_viewer")
    if not session:
        pytest.skip("Could not authenticate tenant_viewer user")
    return session


# ============================================================================
# Test: connections:read Permission
# ============================================================================

class TestConnectionsReadPermission:
    """Tests for connections:read permission on GET endpoints."""
    
    def test_platform_admin_can_get_connector_types(self, platform_admin_session):
        """Platform admin should be able to get connector types."""
        response = platform_admin_session.get("/api/connectors/types")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "connector_types" in data, "Response should contain connector_types"
    
    def test_platform_admin_can_get_configurations(self, platform_admin_session):
        """Platform admin should be able to get connector configurations."""
        response = platform_admin_session.get("/api/connectors/configurations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_tenant_admin_can_get_connector_types(self, tenant_admin_session):
        """Tenant admin should be able to get connector types."""
        response = tenant_admin_session.get("/api/connectors/types")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_tenant_admin_can_get_configurations(self, tenant_admin_session):
        """Tenant admin should be able to get connector configurations."""
        response = tenant_admin_session.get("/api/connectors/configurations")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_tenant_editor_cannot_get_connector_types(self, tenant_editor_session):
        """Tenant editor should NOT be able to get connector types (connections are admin-only)."""
        response = tenant_editor_session.get("/api/connectors/types")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    
    def test_tenant_editor_cannot_get_configurations(self, tenant_editor_session):
        """Tenant editor should NOT be able to get connector configurations."""
        response = tenant_editor_session.get("/api/connectors/configurations")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    
    def test_tenant_viewer_cannot_get_connector_types(self, tenant_viewer_session):
        """Tenant viewer should NOT be able to get connector types."""
        response = tenant_viewer_session.get("/api/connectors/types")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    
    def test_tenant_viewer_cannot_get_configurations(self, tenant_viewer_session):
        """Tenant viewer should NOT be able to get connector configurations."""
        response = tenant_viewer_session.get("/api/connectors/configurations")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    
    def test_unauthenticated_cannot_get_connector_types(self):
        """Unauthenticated users should get 401."""
        response = requests.get(f"{BASE_URL}/api/connectors/types")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    
    def test_unauthenticated_cannot_get_configurations(self):
        """Unauthenticated users should get 401."""
        response = requests.get(f"{BASE_URL}/api/connectors/configurations")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


# ============================================================================
# Test: connections:create Permission
# ============================================================================

class TestConnectionsCreatePermission:
    """Tests for connections:create permission on POST endpoints."""
    
    # Sample connector configuration for testing
    SAMPLE_CONFIG = {
        "connector_type": "greenhouse",
        "connector_name": "Test Greenhouse Connection",
        "description": "Test connection for permission tests",
        "tags": ["test"],
        "credentials": {
            "api_key": "test_api_key_12345"
        },
        "sync_config": {
            "max_candidates": 100
        },
        "sync_mode": "full_refresh"
    }
    
    def test_platform_admin_can_create_configuration(self, platform_admin_session):
        """Platform admin should be able to create connector configuration."""
        response = platform_admin_session.post(
            "/api/connectors/configurations",
            json=self.SAMPLE_CONFIG
        )
        # May fail due to invalid API key, but should NOT be 403
        assert response.status_code != 403, f"Got 403 Forbidden - permission denied"
        # Could be 201 (success), 400 (validation), or 500 (connection test failed)
        assert response.status_code in [201, 400, 500], f"Unexpected status: {response.status_code}: {response.text}"
    
    def test_tenant_admin_can_create_configuration(self, tenant_admin_session):
        """Tenant admin should be able to create connector configuration."""
        config = self.SAMPLE_CONFIG.copy()
        config["connector_name"] = "Tenant Admin Test Connection"
        
        response = tenant_admin_session.post(
            "/api/connectors/configurations",
            json=config
        )
        # May fail due to invalid API key, but should NOT be 403
        assert response.status_code != 403, f"Got 403 Forbidden - permission denied"
    
    def test_tenant_editor_cannot_create_configuration(self, tenant_editor_session):
        """Tenant editor should NOT be able to create connector configuration."""
        response = tenant_editor_session.post(
            "/api/connectors/configurations",
            json=self.SAMPLE_CONFIG
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    
    def test_tenant_viewer_cannot_create_configuration(self, tenant_viewer_session):
        """Tenant viewer should NOT be able to create connector configuration."""
        response = tenant_viewer_session.post(
            "/api/connectors/configurations",
            json=self.SAMPLE_CONFIG
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    
    def test_unauthenticated_cannot_create_configuration(self):
        """Unauthenticated users should get 401."""
        response = requests.post(
            f"{BASE_URL}/api/connectors/configurations",
            json=self.SAMPLE_CONFIG
        )
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


# ============================================================================
# Test: connections:test Permission
# ============================================================================

class TestConnectionsTestPermission:
    """Tests for connections:test permission on test connection endpoints."""
    
    TEST_CONNECTION_PAYLOAD = {
        "connector_type": "greenhouse",
        "credentials": {
            "api_key": "test_api_key_12345"
        },
        "sync_config": {}
    }
    
    def test_platform_admin_can_test_connection(self, platform_admin_session):
        """Platform admin should be able to test connections."""
        response = platform_admin_session.post(
            "/api/connectors/test-connection",
            json=self.TEST_CONNECTION_PAYLOAD
        )
        # Should not be 403 - connection may fail but permission should be granted
        assert response.status_code != 403, f"Got 403 Forbidden - permission denied"
    
    def test_platform_admin_can_test_greenhouse_connection(self, platform_admin_session):
        """Platform admin should be able to test Greenhouse connection specifically."""
        response = platform_admin_session.post(
            "/api/connectors/greenhouse/test-connection",
            json={
                "credentials": {"api_key": "test_api_key"},
                "sync_config": {}
            }
        )
        # Should not be 403
        assert response.status_code != 403, f"Got 403 Forbidden - permission denied"
    
    def test_tenant_admin_can_test_connection(self, tenant_admin_session):
        """Tenant admin should be able to test connections."""
        response = tenant_admin_session.post(
            "/api/connectors/test-connection",
            json=self.TEST_CONNECTION_PAYLOAD
        )
        assert response.status_code != 403, f"Got 403 Forbidden - permission denied"
    
    def test_tenant_editor_cannot_test_connection(self, tenant_editor_session):
        """Tenant editor should NOT be able to test connections."""
        response = tenant_editor_session.post(
            "/api/connectors/test-connection",
            json=self.TEST_CONNECTION_PAYLOAD
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_tenant_viewer_cannot_test_connection(self, tenant_viewer_session):
        """Tenant viewer should NOT be able to test connections."""
        response = tenant_viewer_session.post(
            "/api/connectors/test-connection",
            json=self.TEST_CONNECTION_PAYLOAD
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"


# ============================================================================
# Test: Validate Config Permission (uses connections:read)
# ============================================================================

class TestValidateConfigPermission:
    """Tests for validate-config endpoint which requires connections:read."""
    
    VALIDATE_PAYLOAD = {
        "connector_type": "greenhouse",
        "sync_config": {
            "max_candidates": 100
        }
    }
    
    def test_platform_admin_can_validate_config(self, platform_admin_session):
        """Platform admin should be able to validate connector config."""
        response = platform_admin_session.post(
            "/api/connectors/validate-config",
            json=self.VALIDATE_PAYLOAD
        )
        assert response.status_code != 403, f"Got 403 Forbidden - permission denied"
    
    def test_tenant_admin_can_validate_config(self, tenant_admin_session):
        """Tenant admin should be able to validate connector config."""
        response = tenant_admin_session.post(
            "/api/connectors/validate-config",
            json=self.VALIDATE_PAYLOAD
        )
        assert response.status_code != 403, f"Got 403 Forbidden - permission denied"
    
    def test_tenant_editor_cannot_validate_config(self, tenant_editor_session):
        """Tenant editor should NOT be able to validate connector config."""
        response = tenant_editor_session.post(
            "/api/connectors/validate-config",
            json=self.VALIDATE_PAYLOAD
        )
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"


# ============================================================================
# Test: Sync Runs Permission (uses connections:read)
# ============================================================================

class TestSyncRunsPermission:
    """Tests for sync runs endpoint which requires connections:read."""
    
    def test_platform_admin_can_get_sync_runs(self, platform_admin_session):
        """Platform admin should be able to get sync runs."""
        response = platform_admin_session.get("/api/connectors/sync-runs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_tenant_admin_can_get_sync_runs(self, tenant_admin_session):
        """Tenant admin should be able to get sync runs."""
        response = tenant_admin_session.get("/api/connectors/sync-runs")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_tenant_editor_cannot_get_sync_runs(self, tenant_editor_session):
        """Tenant editor should NOT be able to get sync runs."""
        response = tenant_editor_session.get("/api/connectors/sync-runs")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
    
    def test_tenant_viewer_cannot_get_sync_runs(self, tenant_viewer_session):
        """Tenant viewer should NOT be able to get sync runs."""
        response = tenant_viewer_session.get("/api/connectors/sync-runs")
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"


# ============================================================================
# Quick Smoke Test (Can run without all users set up)
# ============================================================================

class TestConnectorPermissionsSmoke:
    """
    Quick smoke test that can run with just the platform admin user.
    
    Run this first to verify basic connectivity and permissions.
    """
    
    def test_api_is_reachable(self):
        """Verify API is reachable."""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, "API health check failed"
    
    def test_login_works(self):
        """Verify login endpoint works."""
        # Try to login - even if it fails, the endpoint should respond
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": "test@test.com", "password": "wrong"}
        )
        # Should get 401 (invalid credentials), not 500 or connection error
        assert response.status_code in [401, 400], f"Login endpoint issue: {response.status_code}"
    
    def test_platform_admin_full_connector_access(self, platform_admin_session):
        """
        Comprehensive test that platform admin has full connector access.
        
        This is the most important test - if platform admin can't access
        connectors, something is fundamentally broken.
        """
        # 1. Can get types
        response = platform_admin_session.get("/api/connectors/types")
        assert response.status_code == 200, f"Cannot get connector types: {response.status_code}"
        
        # 2. Can get configurations
        response = platform_admin_session.get("/api/connectors/configurations")
        assert response.status_code == 200, f"Cannot get configurations: {response.status_code}"
        
        # 3. Can get sync runs
        response = platform_admin_session.get("/api/connectors/sync-runs")
        assert response.status_code == 200, f"Cannot get sync runs: {response.status_code}"
        
        # 4. Can attempt to test connection (will fail but shouldn't be 403)
        response = platform_admin_session.post(
            "/api/connectors/test-connection",
            json={
                "connector_type": "greenhouse",
                "credentials": {"api_key": "test"},
                "sync_config": {}
            }
        )
        assert response.status_code != 403, f"Test connection returned 403: {response.text}"
        
        print("✅ Platform admin has full connector access!")


# ============================================================================
# Main entry point for running tests directly
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Connector Permissions Test Suite")
    print("=" * 60)
    print()
    print("This test suite verifies that connector permissions are correctly")
    print("enforced via the API.")
    print()
    print("Prerequisites:")
    print("  1. Local environment running (docker compose up)")
    print("  2. Platform admin user exists (scott@eliza.com)")
    print("  3. Test tenant with admin/editor/viewer users (optional)")
    print()
    print("Run with: pytest test_connector_permissions.py -v")
    print()
    print("Quick smoke test: pytest test_connector_permissions.py -v -k 'smoke'")
    print("=" * 60)
    
    # Run quick connectivity check
    print("\nRunning quick connectivity check...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ API is reachable at {BASE_URL}")
        else:
            print(f"⚠️ API returned status {response.status_code}")
    except Exception as e:
        print(f"❌ Cannot reach API at {BASE_URL}: {e}")
        print("   Make sure docker compose is running!")

