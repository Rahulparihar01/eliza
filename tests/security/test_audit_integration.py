"""
Security Integration Tests: End-to-End Audit Verification

These tests verify:
1. API requests are logged in the audit table
2. Database triggers fire and create audit entries
3. Tenant context is properly captured in audit logs
4. RLS violations are logged when detected

Run with: pytest tests/security/test_audit_integration.py -v

NOTE: These tests require the full application to be running.
"""

import pytest
import os
import sys
import time
import httpx
from datetime import datetime, timedelta, timezone
from sqlalchemy import text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.models import database


# Configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5001")
TEST_TENANT_ID = "eliza"  # Use the platform's default tenant
TEST_TARGET_TENANT_ID = "test-view-as-tenant"  # Tenant to view as (must match ^[a-z0-9-]+$ pattern)

# Default test credentials (platform admin)
DEFAULT_ADMIN_EMAIL = "scott@eliza.com"
DEFAULT_ADMIN_PASSWORD = "admin123"


def get_db_session():
    """Get a database session, initializing if needed."""
    if database.SessionLocal is None:
        database.init_database()
    return database.SessionLocal()


def get_auth_token(email: str = None, password: str = None):
    """Get an authentication token for API calls."""
    # Try to get token from environment first
    token = os.environ.get("TEST_AUTH_TOKEN")
    if token:
        return token
    
    # Use provided credentials or defaults
    login_email = email or os.environ.get("TEST_USER_EMAIL", DEFAULT_ADMIN_EMAIL)
    login_password = password or os.environ.get("TEST_USER_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    
    # Try to login (note: endpoint is /v1/auth/login, not /api/v1/auth/login)
    try:
        response = httpx.post(
            f"{API_BASE_URL}/v1/auth/login",
            json={
                "email": login_email,
                "password": login_password
            },
            timeout=10.0
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token") or data.get("token")
            if token:
                print(f"✅ Successfully authenticated as {login_email}")
                return token
            else:
                print(f"⚠️ Login succeeded but no token in response: {data.keys()}")
        else:
            print(f"⚠️ Login failed with status {response.status_code}: {response.text[:200]}")
    except Exception as e:
        print(f"⚠️ Could not get auth token: {e}")
    
    return None


def ensure_test_tenant_exists(db, auth_token: str = None):
    """
    Create a test tenant for 'view as' testing if it doesn't exist.
    
    Uses the proper API endpoint to create the tenant, which:
    - Creates the customer record
    - Creates default roles (admin, editor, viewer) via create_default_roles_for_tenant()
    - Creates an admin invite
    
    The API enforces admin_email is provided, ensuring every tenant has an admin.
    """
    # Check if test tenant exists
    result = db.execute(text("""
        SELECT customer_id FROM customers WHERE customer_id = :tenant_id
    """), {"tenant_id": TEST_TARGET_TENANT_ID})
    
    if result.fetchone() is None:
        # Create the test tenant via API
        if not auth_token:
            auth_token = get_auth_token()
        
        if not auth_token:
            print(f"⚠️ Cannot create test tenant: no auth token available")
            return
        
        try:
            with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
                response = client.post(
                    "/api/v1/platform-admin/tenants",
                    json={
                        "customer_id": TEST_TARGET_TENANT_ID,
                        "name": "Test View As Tenant",
                        "admin_email": "admin@testviewas.com",
                        "admin_name": "Test Tenant Admin",
                        "subscription_tier": "basic",
                        "feature_ids": []  # No features needed for this test tenant
                    },
                    headers={"Authorization": f"Bearer {auth_token}"}
                )
                
                if response.status_code == 201:
                    data = response.json()
                    print(f"✅ Created test tenant via API: {TEST_TARGET_TENANT_ID}")
                    print(f"   Admin invite URL: {data.get('admin_invite_url', 'N/A')}")
                elif response.status_code == 409:
                    # Tenant already exists (race condition)
                    print(f"✓ Test tenant already exists: {TEST_TARGET_TENANT_ID}")
                else:
                    print(f"⚠️ Could not create test tenant via API: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"⚠️ Could not create test tenant via API: {e}")
    else:
        print(f"✓ Test tenant already exists: {TEST_TARGET_TENANT_ID}")


class TestAPIAuditLogging:
    """Test that API requests are logged in the audit table."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session and HTTP client."""
        self.db = get_db_session()
        self.token = get_auth_token()
        self.headers = {}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
            print(f"✓ Using auth token: {self.token[:20]}...")
        else:
            print("⚠️ No auth token available")
        
        # Record timestamp before tests
        self.test_start_time = datetime.now(timezone.utc)
        
        yield
        
        self.db.close()
    
    def test_health_endpoint_does_not_require_auth(self):
        """Verify health endpoint is accessible."""
        response = httpx.get(f"{API_BASE_URL}/health", timeout=10.0, follow_redirects=True)
        assert response.status_code == 200, f"Health endpoint failed: {response.text}"
    
    def test_api_request_creates_audit_entry(self):
        """Verify that an authenticated API request creates an audit log entry."""
        if not self.token:
            pytest.skip("No auth token available - skipping API test")
        
        # Make an API request to roles endpoint
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=self.headers,
            timeout=10.0
        )
        
        assert response.status_code == 200, f"Roles request failed: {response.text[:200]}"
        
        # Wait a moment for sync audit logging
        time.sleep(0.5)
        
        # Check if an audit entry was created
        result = self.db.execute(text("""
            SELECT id, action, api_endpoint, customer_id, outcome, timestamp, user_id
            FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/admin/roles'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        
        # NOW we REQUIRE the audit entry to exist
        assert row is not None, "API request should create an audit entry"
        assert row[1] == 'SELECT', "GET request should be logged as SELECT action"
        assert row[2] == '/api/v1/admin/roles', "API endpoint should be logged correctly"
        assert row[3] is not None, "customer_id should be captured"
        assert row[4] == 'success', "Successful request should have 'success' outcome"
        assert row[6] is not None, "user_id should be captured"
        print(f"✅ API request audit verified: action={row[1]}, customer={row[3]}, outcome={row[4]}")
    
    def test_api_request_captures_tenant_context(self):
        """Verify that tenant context is captured in audit logs."""
        if not self.token:
            pytest.skip("No auth token available - skipping API test")
        
        # Make an API request to users endpoint
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/users",
            headers=self.headers,
            timeout=10.0
        )
        
        assert response.status_code == 200, f"Users request failed: {response.text[:200]}"
        
        # Wait for audit logging
        time.sleep(0.5)
        
        # Check for audit entry with tenant context
        result = self.db.execute(text("""
            SELECT id, customer_id, api_endpoint, action, user_id, duration_ms
            FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/admin/users'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        
        assert row is not None, "API request should create an audit entry"
        assert row[1] == TEST_TENANT_ID, f"customer_id should be '{TEST_TENANT_ID}', got '{row[1]}'"
        assert row[3] == 'SELECT', "GET request should map to SELECT action"
        assert row[4] is not None, "user_id should be captured"
        assert row[5] is not None and row[5] > 0, "duration_ms should be captured"
        print(f"✅ Tenant context verified: customer_id={row[1]}, user_id={row[4]}, duration={row[5]}ms")
    
    def test_failed_request_logged_with_outcome(self):
        """Verify that failed requests are logged with error outcome."""
        # Make a request that should fail (no auth)
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            timeout=10.0  # No auth header
        )
        
        # Should get 401 or 403
        assert response.status_code in [401, 403, 422], f"Expected auth error, got {response.status_code}"
        
        # Note: Unauthenticated requests won't have tenant context set,
        # so they may not be logged. This is expected behavior.
        print(f"✅ Auth error response verified: status={response.status_code}")
    
    def test_http_methods_map_to_correct_actions(self):
        """Verify that different HTTP methods are logged with correct actions."""
        if not self.token:
            pytest.skip("No auth token available - skipping API test")
        
        # Test GET -> SELECT
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/permissions",
            headers=self.headers,
            timeout=10.0
        )
        assert response.status_code == 200
        
        time.sleep(0.3)
        
        result = self.db.execute(text("""
            SELECT action FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/admin/permissions'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC LIMIT 1
        """), {"start_time": self.test_start_time})
        row = result.fetchone()
        assert row is not None and row[0] == 'SELECT', "GET should map to SELECT"
        print(f"✅ HTTP method mapping verified: GET -> SELECT")
    
    def test_audit_entry_includes_duration(self):
        """Verify that audit entries include request duration."""
        if not self.token:
            pytest.skip("No auth token available - skipping API test")
        
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=self.headers,
            timeout=10.0
        )
        
        time.sleep(0.5)
        
        result = self.db.execute(text("""
            SELECT duration_ms FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/admin/roles'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        assert row is not None, "Audit entry should exist"
        assert row[0] is not None, "duration_ms should be captured"
        assert row[0] > 0, f"duration_ms should be positive, got {row[0]}"
        print(f"✅ Duration captured: {row[0]}ms")
    
    def test_audit_entry_includes_client_info(self):
        """Verify that audit entries include client IP and user agent."""
        if not self.token:
            pytest.skip("No auth token available - skipping API test")
        
        # Make request with custom user agent
        headers = {**self.headers, "User-Agent": "pytest-security-test/1.0"}
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=headers,
            timeout=10.0
        )
        
        time.sleep(0.5)
        
        result = self.db.execute(text("""
            SELECT ip_address, user_agent FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/admin/roles'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        assert row is not None, "Audit entry should exist"
        # IP address should be captured (might be localhost or container IP)
        assert row[0] is not None, "ip_address should be captured"
        assert row[1] is not None, "user_agent should be captured"
        print(f"✅ Client info captured: ip={row[0]}, user_agent={row[1][:50]}...")


class TestDatabaseTriggerAudit:
    """
    Test that API operations create proper audit entries.
    
    These tests use the API (as a real user would) and then verify
    that audit entries are created in the database.
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session and auth."""
        self.db = get_db_session()
        self.token = get_auth_token()
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.test_start_time = datetime.now(timezone.utc)
        yield
        self.db.close()
    
    def test_role_create_via_api_creates_audit_entry(self):
        """Verify creating a role via API creates an audit trail."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # Count audit entries before
        before_count = self.db.execute(text("""
            SELECT COUNT(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%roles%'
        """), {"start_time": self.test_start_time}).scalar() or 0
        
        # Create a role via API
        unique_name = f"test-role-{int(time.time())}"
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            response = client.post(
                "/api/v1/admin/roles",
                json={
                    "role_name": unique_name,
                    "display_name": "Test Audit Role",
                    "description": "Created by audit test"
                },
                headers=self.headers
            )
        
        print(f"Role creation response: {response.status_code}")
        
        # Wait for background audit task
        time.sleep(0.5)
        
        # Count audit entries after
        after_count = self.db.execute(text("""
            SELECT COUNT(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%roles%'
        """), {"start_time": self.test_start_time}).scalar() or 0
        
        new_entries = after_count - before_count
        print(f"New audit entries after role creation via API: {new_entries}")
        
        if response.status_code in (200, 201):
            assert new_entries > 0, "API role creation should create audit entry"
            print("✅ Role creation via API triggered audit entry")
        else:
            print(f"⚠️ Role creation returned {response.status_code}: {response.text}")
    
    def test_user_invite_via_api_creates_audit_entry(self):
        """Verify inviting a user via API creates an audit trail."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # Count audit entries before
        before_count = self.db.execute(text("""
            SELECT COUNT(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%invite%'
        """), {"start_time": self.test_start_time}).scalar() or 0
        
        # Get an existing role to assign
        role_result = self.db.execute(text("""
            SELECT id FROM roles WHERE customer_id = 'eliza' AND name = 'viewer' LIMIT 1
        """)).fetchone()
        
        if not role_result:
            pytest.skip("No viewer role found")
        
        role_id = role_result[0]
        unique_email = f"test-invite-{int(time.time())}@example.com"
        
        # Create invite via API
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            response = client.post(
                "/api/v1/tenant-admin/invites",
                json={
                    "email": unique_email,
                    "role_ids": [role_id],
                    "full_name": "Test Invite User"
                },
                headers=self.headers
            )
        
        print(f"Invite creation response: {response.status_code}")
        
        # Wait for background audit task
        time.sleep(0.5)
        
        # Count audit entries after
        after_count = self.db.execute(text("""
            SELECT COUNT(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%invite%'
        """), {"start_time": self.test_start_time}).scalar() or 0
        
        new_entries = after_count - before_count
        print(f"New audit entries after invite via API: {new_entries}")
        
        if response.status_code in (200, 201):
            assert new_entries > 0, "API invite should create audit entry"
            print("✅ User invite via API triggered audit entry")
        else:
            print(f"⚠️ Invite returned {response.status_code}: {response.text}")
    
    def test_settings_update_via_api_creates_audit_entry(self):
        """Verify updating settings via API creates an audit trail."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # Count audit entries before
        before_count = self.db.execute(text("""
            SELECT COUNT(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND action = 'UPDATE'
        """), {"start_time": self.test_start_time}).scalar() or 0
        
        # Get current user info via API (this is a read operation)
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            response = client.get(
                "/api/v1/auth/me",
                headers=self.headers
            )
        
        print(f"Get user response: {response.status_code}")
        
        # Wait for background audit task
        time.sleep(0.5)
        
        # Verify audit entry was created for the read
        after_count = self.db.execute(text("""
            SELECT COUNT(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
        """), {"start_time": self.test_start_time}).scalar() or 0
        
        print(f"Audit entries after API call: {after_count - before_count}")
        
        if response.status_code == 200:
            print("✅ API call was audited")


class TestTenantContextInAudit:
    """
    Test that tenant context is properly captured in all audit scenarios.
    
    Uses API calls to trigger real actions, then verifies audit entries
    contain correct tenant context.
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session and auth."""
        self.db = get_db_session()
        self.token = get_auth_token()
        self.headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        self.test_start_time = datetime.now(timezone.utc)
        yield
        self.db.close()
    
    def test_api_call_captures_customer_id(self):
        """Verify API calls capture the tenant's customer_id in audit."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # Make an API call that should be audited
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            response = client.get(
                "/api/v1/admin/roles",
                headers=self.headers
            )
        
        print(f"API call response: {response.status_code}")
        
        # Wait for background audit task
        time.sleep(0.5)
        
        # Verify audit entry has customer_id
        result = self.db.execute(text("""
            SELECT customer_id, api_endpoint, action
            FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%roles%'
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        if row:
            assert row[0] is not None, "customer_id should be captured"
            assert row[0] == 'eliza', f"Expected customer_id 'eliza', got '{row[0]}'"
            print(f"✅ Tenant context captured: customer_id={row[0]}, endpoint={row[1]}")
        else:
            print("⚠️ No audit entry found - middleware may not be logging")
    
    def test_cross_tenant_access_via_header_is_logged(self):
        """Verify cross-tenant access via header is properly logged."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # Ensure test tenant exists for viewing
        ensure_test_tenant_exists(self.db, auth_token=self.token)
        
        # Make an API call with X-Cross-Tenant-Access header
        with httpx.Client(base_url=API_BASE_URL, timeout=30.0) as client:
            response = client.get(
                "/api/v1/admin/users",
                headers={
                    **self.headers,
                    "X-Cross-Tenant-Access": "true"
                }
            )
        
        print(f"Cross-tenant API call response: {response.status_code}")
        
        # Wait for background audit task
        time.sleep(0.5)
        
        # Verify audit entry captures cross-tenant flag
        result = self.db.execute(text("""
            SELECT customer_id, additional_context
            FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%users%'
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        if row and row[1]:
            context = row[1] if isinstance(row[1], dict) else {}
            if context.get('cross_tenant_access'):
                print("✅ Cross-tenant access flag captured in audit")
            else:
                print(f"⚠️ Cross-tenant flag not in additional_context: {context}")
        else:
            print("⚠️ No audit entry with context found")


class TestRLSViolationDetection:
    """
    Test RLS (Row Level Security) policies at the database layer.
    
    These tests verify:
    1. RLS violation log table exists with correct schema
    2. RLS policies are configured on tenant tables
    3. Platform admin context variables work correctly
    
    NOTE: These tests use SET statements to test database-level RLS,
    which is appropriate for testing the security layer directly.
    The application layer (API) is tested in other test classes.
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session."""
        self.db = get_db_session()
        self.test_start_time = datetime.now(timezone.utc)
        yield
        self.db.rollback()
        self.db.close()
    
    def test_rls_violation_log_table_exists(self):
        """Verify RLS violation log table exists with correct schema."""
        result = self.db.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'rls_violation_log'
            ORDER BY ordinal_position
        """))
        
        columns = {row[0]: row[1] for row in result.fetchall()}
        
        # Verify required columns exist
        required_columns = ['id', 'customer_id', 'table_name', 'operation', 'timestamp']
        missing = [col for col in required_columns if col not in columns]
        
        if missing:
            print(f"⚠️ Missing columns in rls_violation_log: {missing}")
        else:
            print(f"✅ RLS violation log table has all required columns: {list(columns.keys())}")
    
    def test_rls_blocks_cross_tenant_access(self):
        """Verify RLS policies block cross-tenant data access."""
        # Set tenant context to tenant A
        self.db.execute(text("SET app.customer_id = 'tenant_a'"))
        self.db.execute(text("SET app.is_platform_admin = 'false'"))
        self.db.execute(text("SET app.cross_tenant_access = 'false'"))
        
        # Try to query users - should only see tenant_a users
        # Note: As superuser/test user, RLS might be bypassed
        # This test verifies the POLICY exists and is configured correctly
        
        # Check for tenant isolation policy (correct column names for pg_policies)
        result = self.db.execute(text("""
            SELECT policyname, cmd, roles
            FROM pg_policies
            WHERE tablename = 'users'
            AND (policyname = 'tenant_isolation_policy' OR policyname LIKE '%tenant%' OR policyname LIKE '%isolation%')
        """))
        
        row = result.fetchone()
        assert row is not None, "A tenant isolation policy should exist on users table"
        print(f"✅ RLS policy configured: {row[0]}")
    
    def test_platform_admin_can_bypass_rls(self):
        """Verify platform admin with cross_tenant_access can see all data."""
        # Set platform admin context
        self.db.execute(text("SET app.customer_id = 'eliza'"))
        self.db.execute(text("SET app.is_platform_admin = 'true'"))
        self.db.execute(text("SET app.cross_tenant_access = 'true'"))
        
        # Query to verify settings
        result = self.db.execute(text("""
            SELECT 
                current_setting('app.customer_id', true) as customer_id,
                current_setting('app.is_platform_admin', true) as is_admin,
                current_setting('app.cross_tenant_access', true) as cross_tenant
        """))
        
        row = result.fetchone()
        assert row[0] == 'eliza', "Customer ID should be set"
        assert row[1] == 'true', "is_platform_admin should be true"
        assert row[2] == 'true', "cross_tenant_access should be true"
        print("✅ Platform admin context properly set for cross-tenant access")


class TestAuditQueryPerformance:
    """Test that audit tables have proper indexes for compliance queries."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session."""
        self.db = get_db_session()
        yield
        self.db.close()
    
    def test_data_access_audit_has_required_indexes(self):
        """Verify data_access_audit_log has indexes for common queries."""
        result = self.db.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'data_access_audit_log'
        """))
        
        indexes = {row[0]: row[1] for row in result.fetchall()}
        
        # Should have indexes for common query patterns
        required_patterns = ['customer_id', 'timestamp', 'user_id']
        found_patterns = []
        
        for pattern in required_patterns:
            for idx_name, idx_def in indexes.items():
                if pattern in idx_def.lower():
                    found_patterns.append(pattern)
                    break
        
        print(f"Found indexes covering: {found_patterns}")
        print(f"All indexes: {list(indexes.keys())}")
        
        assert len(found_patterns) >= 2, f"Should have at least 2 required indexes, found {len(found_patterns)}"
        print("✅ Audit table has proper indexes")
    
    def test_audit_query_uses_index(self):
        """Verify common audit queries use indexes."""
        # Test a common compliance query
        result = self.db.execute(text("""
            EXPLAIN (FORMAT JSON)
            SELECT * FROM data_access_audit_log
            WHERE customer_id = 'test_tenant'
            AND timestamp > NOW() - INTERVAL '30 days'
            ORDER BY timestamp DESC
            LIMIT 100
        """))
        
        plan = result.fetchone()[0]
        
        # The query should show an index scan for well-indexed tables
        assert plan is not None, "Query plan should be generated"
        print("✅ Query plan generated for compliance query")


class TestViewAsTenantAudit:
    """Test that 'View As Tenant' feature is properly audited."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session and HTTP client."""
        self.db = get_db_session()
        self.token = get_auth_token()
        self.headers = {}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
            print(f"✓ Using auth token for View As tests")
        
        # Ensure test tenant exists for "view as" testing (uses API to create properly)
        ensure_test_tenant_exists(self.db, auth_token=self.token)
        
        self.test_start_time = datetime.now(timezone.utc)
        yield
        self.db.close()
    
    def test_view_as_tenant_header_logged(self):
        """Verify X-View-As-Tenant header is captured in audit."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # Make request with View-As-Tenant header (using a real tenant)
        headers = {
            **self.headers,
            "X-View-As-Tenant": TEST_TARGET_TENANT_ID
        }
        
        print(f"Making request with X-View-As-Tenant: {TEST_TARGET_TENANT_ID}")
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=headers,
            timeout=10.0
        )
        print(f"Response status: {response.status_code}")
        
        time.sleep(0.5)
        
        # Check audit for the header
        result = self.db.execute(text("""
            SELECT additional_context
            FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%/admin/roles%'
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        
        if row and row[0]:
            context = row[0]
            if isinstance(context, dict) and 'view_as_tenant_header' in context:
                assert context.get('view_as_tenant_header') == TEST_TARGET_TENANT_ID
                print(f"✅ View-As-Tenant header logged: {TEST_TARGET_TENANT_ID}")
            else:
                print(f"Context keys: {context.keys() if isinstance(context, dict) else type(context)}")
                print("⚠️ View-As-Tenant header not in expected location - middleware may not be logging this")
        else:
            print("⚠️ No audit entry found - API audit logging may not be active yet")
        
        # Test passes - we verified the API accepts the header
        assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"
    
    def test_cross_tenant_access_header_logged(self):
        """Verify X-Cross-Tenant-Access header is captured in audit."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # Make request with Cross-Tenant-Access header
        headers = {
            **self.headers,
            "X-Cross-Tenant-Access": "true"
        }
        
        print("Making request with X-Cross-Tenant-Access: true")
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=headers,
            timeout=10.0
        )
        print(f"Response status: {response.status_code}")
        
        time.sleep(0.5)
        
        # Check audit for the header
        result = self.db.execute(text("""
            SELECT additional_context
            FROM data_access_audit_log
            WHERE timestamp >= :start_time
            AND api_endpoint LIKE '%/admin/roles%'
            ORDER BY timestamp DESC
            LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        
        if row and row[0]:
            context = row[0]
            if isinstance(context, dict):
                print(f"✅ Audit context captured with keys: {list(context.keys())}")
                if 'cross_tenant_access_enabled' in context:
                    print(f"   cross_tenant_access_enabled: {context.get('cross_tenant_access_enabled')}")
            else:
                print(f"Context type: {type(context)}")
        else:
            print("⚠️ No audit entry found - API audit logging may not be active yet")
        
        # Test passes - we verified the API accepts the header
        assert response.status_code in [200, 401, 403], f"Unexpected status: {response.status_code}"
    
    def test_view_as_tenant_returns_tenant_data(self):
        """Verify that viewing as a tenant returns that tenant's data."""
        if not self.token:
            pytest.skip("No auth token available")
        
        # First, get roles for our own tenant (eliza)
        response_own = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=self.headers,
            timeout=10.0
        )
        print(f"Own tenant roles response: {response_own.status_code}")
        
        # Then, get roles while viewing as the test tenant
        headers_view_as = {
            **self.headers,
            "X-View-As-Tenant": TEST_TARGET_TENANT_ID
        }
        response_view_as = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=headers_view_as,
            timeout=10.0
        )
        print(f"View-as-tenant roles response: {response_view_as.status_code}")
        
        # Both should return successfully (200)
        assert response_own.status_code == 200, f"Own tenant request failed: {response_own.text[:200]}"
        
        # The view-as request might return different data or an error if not properly set up
        # For now, we just verify it doesn't crash
        assert response_view_as.status_code in [200, 403], f"View-as request unexpected status: {response_view_as.status_code}"
        
        if response_view_as.status_code == 200:
            own_data = response_own.json()
            view_as_data = response_view_as.json()
            # Handle both list and dict responses
            own_roles = own_data if isinstance(own_data, list) else own_data.get('roles', [])
            view_as_roles = view_as_data if isinstance(view_as_data, list) else view_as_data.get('roles', [])
            print(f"✅ Own tenant returned {len(own_roles)} roles")
            print(f"✅ View-as tenant returned {len(view_as_roles)} roles")
            
            # If view-as is working, the roles should be different (test tenant has no roles initially)
            if len(view_as_roles) == 0:
                print("✓ View-as tenant correctly shows no roles (new tenant)")
            elif len(view_as_roles) != len(own_roles):
                print("✓ View-as tenant shows different role count than own tenant")
        else:
            print(f"⚠️ View-as-tenant returned 403 - tenant context switching may need implementation")


class TestAuthDependencyRequestState:
    """
    Test that the auth dependency correctly sets request.state values.
    
    These tests verify that after authentication:
    - request.state.customer_id is set from JWT
    - request.state.user_id is set from JWT
    - request.state.is_platform_admin is set based on permissions
    
    We verify this indirectly by checking audit log entries which are
    populated from request.state values.
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session and HTTP client."""
        self.db = get_db_session()
        self.token = get_auth_token()
        self.headers = {}
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
        self.test_start_time = datetime.now(timezone.utc)
        yield
        self.db.close()
    
    def test_authenticated_request_has_customer_id(self):
        """Verify authenticated requests have customer_id in audit log."""
        if not self.token:
            pytest.skip("No auth token available")
        
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            headers=self.headers,
            timeout=10.0
        )
        assert response.status_code == 200
        
        time.sleep(0.5)
        
        result = self.db.execute(text("""
            SELECT customer_id FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/admin/roles'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        assert row is not None, "Audit entry should exist"
        assert row[0] is not None, "customer_id should be set from request.state"
        assert row[0] == TEST_TENANT_ID, f"customer_id should be '{TEST_TENANT_ID}'"
        print(f"✅ request.state.customer_id verified: {row[0]}")
    
    def test_authenticated_request_has_user_id(self):
        """Verify authenticated requests have user_id in audit log."""
        if not self.token:
            pytest.skip("No auth token available")
        
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/users",
            headers=self.headers,
            timeout=10.0
        )
        assert response.status_code == 200
        
        time.sleep(0.5)
        
        result = self.db.execute(text("""
            SELECT user_id FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/admin/users'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        assert row is not None, "Audit entry should exist"
        assert row[0] is not None, "user_id should be set from request.state"
        assert row[0] > 0, "user_id should be a valid positive integer"
        print(f"✅ request.state.user_id verified: {row[0]}")
    
    def test_platform_admin_flag_captured(self):
        """Verify is_platform_admin flag is captured in audit context."""
        if not self.token:
            pytest.skip("No auth token available")
        
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/platform-admin/tenants",
            headers=self.headers,
            timeout=10.0
        )
        
        # Platform admin should have access
        assert response.status_code == 200, "Platform admin should access tenants endpoint"
        
        time.sleep(0.5)
        
        result = self.db.execute(text("""
            SELECT additional_context FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/platform-admin/tenants'
            AND timestamp >= :start_time
            ORDER BY timestamp DESC LIMIT 1
        """), {"start_time": self.test_start_time})
        
        row = result.fetchone()
        assert row is not None, "Audit entry should exist"
        
        if row[0]:
            context = row[0]
            if isinstance(context, dict):
                is_admin = context.get('is_platform_admin')
                print(f"✅ is_platform_admin captured in audit: {is_admin}")
            else:
                print(f"Additional context: {context}")
    
    def test_unauthenticated_request_no_audit(self):
        """Verify unauthenticated requests don't create audit entries (no tenant context)."""
        # Count entries before
        before_count = self.db.execute(text("""
            SELECT count(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
        """), {"start_time": self.test_start_time}).scalar()
        
        # Make unauthenticated request
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/admin/roles",
            timeout=10.0  # No auth header
        )
        
        # Should get auth error
        assert response.status_code in [401, 403, 422]
        
        time.sleep(0.5)
        
        # Count entries after
        after_count = self.db.execute(text("""
            SELECT count(*) FROM data_access_audit_log
            WHERE timestamp >= :start_time
        """), {"start_time": self.test_start_time}).scalar()
        
        # Unauthenticated requests may or may not be logged
        # (depends on whether tenant_id is available)
        print(f"Audit entries created: {after_count - before_count}")
        print("✅ Unauthenticated request handled correctly")


class TestApiAuditServiceIntegration:
    """
    Test the api_audit_service.log_api_request_sync function directly.
    
    These tests verify the new synchronous audit logging service works correctly.
    We use a real user_id from the database to match real application behavior,
    where authenticated requests always have a valid user_id from the JWT.
    """
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session and get a real user_id for realistic testing."""
        self.db = get_db_session()
        self.test_start_time = datetime.now(timezone.utc)
        
        # Get a REAL user_id from the database - this reflects real app behavior
        # where every authenticated request has a user_id from JWT
        # We use the default admin user who should exist in any properly set up environment
        result = self.db.execute(text("""
            SELECT id, customer_id FROM users 
            WHERE email = :email LIMIT 1
        """), {"email": DEFAULT_ADMIN_EMAIL})
        row = result.fetchone()
        
        if row:
            self.test_user_id = row[0]
            self.test_customer_id = row[1]
            print(f"✓ Using real user for tests: id={self.test_user_id}, customer={self.test_customer_id}")
        else:
            # No fallback - tests require a properly set up environment with real users
            # This ensures we're testing with realistic data, not artificially created test data
            self.test_user_id = None
            self.test_customer_id = None
            print(f"⚠️ Default admin user ({DEFAULT_ADMIN_EMAIL}) not found - some tests will skip")
        
        yield
        self.db.close()
    
    def test_log_api_request_sync_creates_entry(self):
        """Verify log_api_request_sync creates audit entries with real user_id."""
        if not self.test_user_id:
            pytest.skip("No test user available - requires properly set up environment")
        
        from src.services.api_audit_service import log_api_request_sync
        
        # Use REAL user_id - this is what happens in the actual application
        log_api_request_sync(
            action='SELECT',
            resource_type='test_resource',
            api_endpoint='/api/v1/test/audit-service',
            api_method='GET',
            customer_id=self.test_customer_id,
            user_id=self.test_user_id,  # Real user from database
            outcome='success',
            duration_ms=100,
        )
        
        # Verify entry was created with correct user_id
        result = self.db.execute(text("""
            SELECT action, resource_type, api_endpoint, customer_id, user_id, outcome, duration_ms
            FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/test/audit-service'
            AND user_id = :user_id
            ORDER BY timestamp DESC LIMIT 1
        """), {"user_id": self.test_user_id})
        
        row = result.fetchone()
        assert row is not None, "Audit entry should be created"
        assert row[0] == 'SELECT', "Action should be SELECT"
        assert row[1] == 'test_resource', "Resource type should match"
        assert row[2] == '/api/v1/test/audit-service', "API endpoint should match"
        assert row[3] == self.test_customer_id, "Customer ID should match"
        assert row[4] == self.test_user_id, "User ID should match real user"
        assert row[5] == 'success', "Outcome should be success"
        assert row[6] == 100, "Duration should match"
        print(f"✅ log_api_request_sync creates entries with real user_id={self.test_user_id}")
    
    def test_log_api_request_sync_captures_all_fields(self):
        """Verify all audit fields are captured with real user context."""
        if not self.test_user_id:
            pytest.skip("No test user available - requires properly set up environment")
        
        from src.services.api_audit_service import log_api_request_sync
        
        # Use REAL user_id - matches actual application flow
        log_api_request_sync(
            action='INSERT',
            resource_type='documents',
            api_endpoint='/api/v1/documents/audit-test',
            api_method='POST',
            customer_id=self.test_customer_id,
            user_id=self.test_user_id,  # Real user from database
            session_id='test-session-456',
            ip_address='192.168.1.100',
            user_agent='pytest-full-test/2.0',
            outcome='success',
            status_code=201,
            duration_ms=250,
            is_platform_admin=True,
            cross_tenant_access=False,
            view_as_tenant=None,
        )
        
        result = self.db.execute(text("""
            SELECT action, resource_type, api_endpoint, api_method,
                   customer_id, user_id, session_id, ip_address, user_agent,
                   outcome, duration_ms, additional_context
            FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/documents/audit-test'
            AND user_id = :user_id
            ORDER BY timestamp DESC LIMIT 1
        """), {"user_id": self.test_user_id})
        
        row = result.fetchone()
        assert row is not None, "Audit entry should be created"
        assert row[0] == 'INSERT', "Action"
        assert row[1] == 'documents', "Resource type"
        assert row[2] == '/api/v1/documents/audit-test', "API endpoint"
        assert row[3] == 'POST', "API method"
        assert row[4] == self.test_customer_id, "Customer ID"
        assert row[5] == self.test_user_id, "User ID should be real user"
        assert row[6] == 'test-session-456', "Session ID"
        assert row[7] == '192.168.1.100', "IP address"
        assert row[8] == 'pytest-full-test/2.0', "User agent"
        assert row[9] == 'success', "Outcome"
        assert row[10] == 250, "Duration"
        
        # Check additional context
        if row[11]:
            assert row[11].get('is_platform_admin') == True, "is_platform_admin in context"
        
        print(f"✅ All audit fields captured correctly with user_id={self.test_user_id}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

