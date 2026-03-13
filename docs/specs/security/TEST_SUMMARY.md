# Security Test Suite Summary

This document provides an overview of the security test suite, what each test verifies, and how to run them.

---

## Quick Reference

| Metric | Value |
|--------|-------|
| **Total Tests** | 56 |
| **Test Files** | 3 |
| **Last Run** | December 25, 2025 |
| **Status** | ✅ All Passing |

```bash
# Run all security tests
docker compose exec app pytest tests/security/ -v

# Run specific test file
docker compose exec app pytest tests/security/test_audit_integration.py -v

# Run with coverage
docker compose exec app pytest tests/security/ --cov=src/middleware --cov=src/services
```

---

## Test Files Overview

### 1. `test_audit_integration.py` (26 tests)

**Purpose**: End-to-end integration tests that verify API requests are properly logged and tenant context flows correctly through the system.

| Test Class | Tests | What It Verifies |
|------------|-------|------------------|
| `TestAPIAuditLogging` | 7 | API requests create audit entries with correct action, tenant, duration, client info |
| `TestDatabaseTriggerAudit` | 3 | Database INSERT/UPDATE operations create audit entries via triggers |
| `TestTenantContextInAudit` | 2 | `customer_id` and cross-tenant flags captured in audit logs |
| `TestRLSViolationDetection` | 3 | RLS violations logged, platform admin bypass works |
| `TestAuditQueryPerformance` | 2 | Indexes exist for efficient compliance queries |
| `TestViewAsTenantAudit` | 3 | `X-View-As-Tenant` and `X-Cross-Tenant-Access` headers processed |
| `TestAuthDependencyRequestState` | 4 | Auth dependency sets `request.state.customer_id/user_id` correctly |
| `TestApiAuditServiceIntegration` | 2 | `log_api_request_sync()` creates entries with real user IDs |

### 2. `test_tenant_isolation.py` (18 tests)

**Purpose**: Verify PostgreSQL Row Level Security (RLS) is correctly configured and enforces tenant isolation.

| Test Class | Tests | What It Verifies |
|------------|-------|------------------|
| `TestDatabaseConnection` | 1 | Database is accessible |
| `TestRLSConfiguration` | 4 | RLS enabled on `users`, `documents`, `roles` tables; policies exist |
| `TestTenantContextFunctions` | 4 | PostgreSQL functions `current_tenant_id()`, `is_cross_tenant_access_allowed()` work |
| `TestTenantIsolation` | 2 | Users and roles filtered by tenant via RLS |
| `TestCrossTenantAccess` | 1 | Cross-tenant requires BOTH `is_platform_admin` AND `cross_tenant_access` flags |
| `TestAuditLogging` | 3 | Audit tables exist with required columns |
| `TestMiddlewareIntegration` | 3 | Middleware classes importable and validate tenant_id |

### 3. `test_audit_logging.py` (12 tests)

**Purpose**: Direct database tests for audit logging tables, triggers, and compliance reporting.

| Test Class | Tests | What It Verifies |
|------------|-------|------------------|
| `TestAuditLogWriting` | 2 | Can insert entries into `data_access_audit_log` with all fields |
| `TestRLSViolationLogging` | 2 | Can insert RLS violations; indexes exist for queries |
| `TestUserAuditLogEnhanced` | 2 | `user_audit_log` has `customer_id`, `severity`, `outcome` columns |
| `TestAuditTriggers` | 3 | Triggers attached to `users`, `roles`, `document` tables |
| `TestComplianceReporting` | 3 | `tenant_activity_summary` and `compliance_reports` tables exist |

---

## Key Test Scenarios

### Scenario 1: API Request Creates Audit Entry (CRITICAL)

```python
def test_api_request_creates_audit_entry(self):
    """Every authenticated API request MUST create an audit entry."""
    response = httpx.get("/api/v1/admin/roles", headers=auth_headers)
    
    # Verify audit entry exists
    result = db.execute(text("""
        SELECT action, customer_id, user_id, outcome, duration_ms
        FROM data_access_audit_log
        WHERE api_endpoint = '/api/v1/admin/roles'
    """))
    row = result.fetchone()
    
    assert row is not None  # Entry MUST exist
    assert row.action == 'SELECT'  # GET → SELECT
    assert row.customer_id == 'eliza'  # Tenant captured
    assert row.user_id is not None  # User captured
    assert row.outcome == 'success'
    assert row.duration_ms > 0  # Duration captured
```

**Why This Matters**: SOC2 requires complete audit trail of all data access.

---

### Scenario 2: Auth Dependency Sets Request State (CRITICAL)

```python
def test_authenticated_request_has_customer_id(self):
    """Auth dependency MUST set request.state.customer_id from JWT."""
    response = httpx.get("/api/v1/admin/roles", headers=auth_headers)
    
    # Audit entry proves customer_id was available to middleware
    result = db.execute(text("""
        SELECT customer_id FROM data_access_audit_log
        WHERE api_endpoint = '/api/v1/admin/roles'
    """))
    
    assert result.fetchone()[0] == 'eliza'  # Customer ID from JWT
```

**Why This Matters**: Tenant context must flow from JWT → auth dependency → request.state → middleware → audit log.

---

### Scenario 3: RLS Filters by Tenant (CRITICAL)

```python
def test_users_filtered_by_tenant(self):
    """RLS MUST filter queries to current tenant only."""
    # Set tenant context
    db.execute(text("SET app.customer_id = 'acme'"))
    
    # Query without WHERE clause
    result = db.execute(text("SELECT customer_id FROM users"))
    
    # RLS automatically adds: WHERE customer_id = 'acme'
    assert all(row[0] == 'acme' for row in result)
```

**Why This Matters**: Even raw SQL queries must be filtered by RLS.

---

### Scenario 4: Cross-Tenant Requires Both Flags (CRITICAL)

```python
def test_cross_tenant_requires_both_flags(self):
    """Cross-tenant access requires is_platform_admin AND cross_tenant_access."""
    # Only is_platform_admin = true (not enough)
    db.execute(text("SET app.is_platform_admin = 'true'"))
    db.execute(text("SET app.cross_tenant_access = 'false'"))
    result = db.execute(text("SELECT customer_id FROM users"))
    assert all(row[0] == 'eliza' for row in result)  # Own tenant only
    
    # Both flags true (cross-tenant allowed)
    db.execute(text("SET app.cross_tenant_access = 'true'"))
    result = db.execute(text("SELECT customer_id FROM users"))
    assert len(set(row[0] for row in result)) > 1  # Multiple tenants
```

**Why This Matters**: Prevents accidental cross-tenant access.

---

### Scenario 5: Real User IDs in Audit (IMPORTANT)

```python
def test_log_api_request_sync_creates_entry(self):
    """Audit service MUST use real user_id (FK constraint validation)."""
    # Get REAL user from database
    result = db.execute(text("SELECT id FROM users WHERE email = 'scott@eliza.com'"))
    real_user_id = result.fetchone()[0]  # id=2
    
    log_api_request_sync(
        action='SELECT',
        customer_id='eliza',
        user_id=real_user_id,  # Real user, not fake ID
        ...
    )
    
    # Entry created with valid FK
    assert db.query(DataAccessAuditLog).filter_by(user_id=real_user_id).first()
```

**Why This Matters**: FK constraint ensures audit logs reference actual users, not fake data.

---

## Test Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TEST EXECUTION                                │
└─────────────────────────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌───────────────┐    ┌─────────────────┐    ┌────────────────┐
│ Integration   │    │ RLS/Isolation   │    │ Direct Audit   │
│ Tests (26)    │    │ Tests (18)      │    │ Tests (12)     │
└───────┬───────┘    └────────┬────────┘    └───────┬────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌─────────────────┐    ┌────────────────┐
│ Makes HTTP    │    │ Sets PostgreSQL │    │ Direct DB      │
│ requests to   │    │ session vars    │    │ operations     │
│ running app   │    │ and queries     │    │ and queries    │
└───────┬───────┘    └────────┬────────┘    └───────┬────────┘
        │                     │                     │
        └──────────────────────┼─────────────────────┘
                               ▼
                    ┌─────────────────────┐
                    │   PostgreSQL DB     │
                    │  - RLS policies     │
                    │  - Audit tables     │
                    │  - Triggers         │
                    └─────────────────────┘
```

---

## Running Tests

### Prerequisites

1. Docker containers running:
   ```bash
   cd docker && docker compose up -d
   ```

2. Database migrations applied:
   ```bash
   docker compose exec app alembic upgrade head
   ```

3. Test user exists (`scott@eliza.com` with password `admin123`)

### Run All Security Tests

```bash
docker compose exec app pytest tests/security/ -v
```

### Run Specific Test Class

```bash
# API audit logging tests
docker compose exec app pytest tests/security/test_audit_integration.py::TestAPIAuditLogging -v

# RLS configuration tests
docker compose exec app pytest tests/security/test_tenant_isolation.py::TestRLSConfiguration -v
```

### Run with Verbose Output

```bash
docker compose exec app pytest tests/security/ -v -s
```

### Run with Coverage

```bash
docker compose exec app pytest tests/security/ --cov=src/middleware --cov=src/services --cov-report=term-missing
```

---

## Test Results History

| Date | Tests | Passed | Failed | Notes |
|------|-------|--------|--------|-------|
| 2025-12-25 21:45 | 56 | 56 | 0 | Added auth dependency and audit service tests |
| 2025-12-25 21:38 | 47 | 47 | 0 | API audit logging implemented |
| 2025-12-25 20:51 | 47 | 47 | 0 | Initial RLS + audit tests |

See [TEST_RESULTS_2025-12-25.md](./TEST_RESULTS_2025-12-25.md) for detailed test output.

---

## Adding New Tests

When adding new security-related functionality, add tests that verify:

1. **Tenant isolation**: New data is filtered by `customer_id`
2. **Audit logging**: Operations create audit entries
3. **Permission checks**: Unauthorized access is blocked
4. **Error handling**: Failures don't leak tenant data

### Test Template

```python
class TestNewFeature:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.db = get_db_session()
        self.token = get_auth_token()
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.test_start_time = datetime.now(timezone.utc)
        yield
        self.db.close()
    
    def test_feature_respects_tenant_isolation(self):
        """New feature should only access current tenant's data."""
        # Make API call
        response = httpx.get("/api/v1/new-feature", headers=self.headers)
        
        # Verify tenant isolation
        assert response.status_code == 200
        data = response.json()
        assert all(item['customer_id'] == 'eliza' for item in data)
    
    def test_feature_creates_audit_entry(self):
        """New feature should log data access."""
        response = httpx.get("/api/v1/new-feature", headers=self.headers)
        
        time.sleep(0.5)  # Wait for audit
        
        result = self.db.execute(text("""
            SELECT * FROM data_access_audit_log
            WHERE api_endpoint = '/api/v1/new-feature'
            AND timestamp >= :start_time
        """), {"start_time": self.test_start_time})
        
        assert result.fetchone() is not None
```

---

## See Also

- [Security Quick Start](./security_quick_start.md) - TL;DR for developers
- [Security for Dev Team](./security_for_dev_team.md) - Implementation guide
- [Security Details for SOC2](./security_details_for_soc2.md) - Compliance documentation
- [Test Results](./TEST_RESULTS_2025-12-25.md) - Detailed test output

---

*Document Version: 1.0*
*Last Updated: December 25, 2025*

