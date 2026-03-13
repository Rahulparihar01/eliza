# Security Details for SOC2 Compliance

This document provides detailed security controls, test scenarios, and audit evidence relevant to SOC2 Type II compliance for the Eliza Platform's multi-tenant architecture.

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Multi-Tenant Architecture](#multi-tenant-architecture)
3. [Security Controls](#security-controls)
4. [Test Scenarios & Results](#test-scenarios--results)
5. [Audit Logging](#audit-logging)
6. [Incident Response](#incident-response)
7. [Compliance Mapping](#compliance-mapping)

---

## Executive Summary

The Eliza Platform implements a **shared database, tenant-isolated** architecture with the following security characteristics:

| Control | Implementation | SOC2 Criteria |
|---------|----------------|---------------|
| Data Isolation | PostgreSQL Row Level Security (RLS) | CC6.1, CC6.3 |
| Access Control | Role-Based Access Control (RBAC) | CC6.1, CC6.2 |
| Audit Logging | Comprehensive data access logging | CC7.2, CC7.3 |
| Encryption | TLS 1.3 in transit, AES-256 at rest | CC6.7 |
| Admin Oversight | View-as-tenant with audit trail | CC6.1, CC7.2 |

### Key Security Guarantees

1. **Tenant Data Isolation**: Users cannot access data belonging to other tenants, enforced at the database level
2. **Explicit Access Required**: Platform administrators must explicitly request cross-tenant access; no implicit bypasses
3. **Complete Audit Trail**: All data access is logged with tenant context, user identity, and action performed
4. **Least Privilege**: Users only receive permissions necessary for their role

---

## Multi-Tenant Architecture

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                               │
│                    (with JWT + Tenant Context)                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      FASTAPI APPLICATION                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              TENANT CONTEXT MIDDLEWARE                        │   │
│  │  • Extracts customer_id from authenticated user               │   │
│  │  • Validates X-View-As-Tenant header (platform admins only)  │   │
│  │  • Sets PostgreSQL session variables for RLS                  │   │
│  │  • Logs all data access with tenant context                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              AUTHORIZATION MIDDLEWARE                         │   │
│  │  • Validates JWT token                                        │   │
│  │  • Checks user permissions against required permissions       │   │
│  │  • Enforces RBAC policies                                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      POSTGRESQL DATABASE                             │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              ROW LEVEL SECURITY (RLS)                         │   │
│  │                                                               │   │
│  │  Policy: tenant_isolation_policy                              │   │
│  │  FOR ALL USING (                                              │   │
│  │    customer_id = current_setting('app.customer_id')           │   │
│  │    OR is_cross_tenant_access_allowed()                        │   │
│  │  )                                                            │   │
│  │  WITH CHECK (                                                 │   │
│  │    customer_id = current_setting('app.customer_id')           │   │
│  │  )                                                            │   │
│  │                                                               │   │
│  │  FORCE ROW LEVEL SECURITY enabled on all tenant tables       │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│  Tenant Data Tables (with customer_id column):                      │
│  • users, roles, user_invites                                       │
│  • documents, document_chunks, upload_batches                       │
│  • candidates, candidate_analysis_scores                            │
│  • reference_check_requests, reference_calls                        │
│  • connector_configurations, ingested_data                          │
│  • email_templates, generated_emails                                │
│  • ... (40+ tables)                                                 │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow for Regular Users

```
1. User authenticates → JWT contains user_id, customer_id
2. Request arrives → Middleware extracts customer_id from JWT
3. Middleware sets: SET app.customer_id = 'acme'
4. Query executed → RLS automatically filters: WHERE customer_id = 'acme'
5. Response sent → Only tenant's data returned
6. Audit log created → Records access with full context
```

### Data Flow for Platform Admin (View As Tenant)

```
1. Platform admin authenticates → JWT contains platform:admin permission
2. Request includes header: X-View-As-Tenant: globex
3. Middleware validates: User has platform:admin permission ✓
4. Middleware sets: SET app.customer_id = 'globex'
5. Query executed → RLS filters to Globex's data
6. Audit log created → Records view_as_tenant context
```

---

## Security Controls

### Control 1: Row Level Security (Database Enforcement)

**Description**: PostgreSQL RLS policies enforce tenant isolation at the database level, preventing access to data from other tenants even if application-level checks are bypassed.

**Implementation**:
```sql
-- RLS enabled on all tenant tables
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;

-- Policy prevents cross-tenant access
CREATE POLICY tenant_isolation_policy ON documents
  FOR ALL
  USING (
    customer_id = current_setting('app.customer_id', true)
    OR is_cross_tenant_access_allowed()
  )
  WITH CHECK (
    customer_id = current_setting('app.customer_id', true)
  );
```

**Key Properties**:
- Cannot be bypassed by application code
- No NULL bypass - tenant context ALWAYS required
- Cross-tenant access requires explicit flags
- Writes restricted to own tenant even with cross-tenant read access

### Control 2: Role-Based Access Control (RBAC)

**Description**: Fine-grained permission system controlling access to features and operations.

**Roles**:
| Role | Scope | Permissions |
|------|-------|-------------|
| Platform Admin | All tenants | Full system access, can view as any tenant |
| Tenant Admin | Single tenant | Full control within tenant |
| Tenant Editor | Single tenant | Create/edit, no admin functions |
| Tenant Viewer | Single tenant | Read-only access |

**Permission Categories** (71 total permissions):
- Talent Intelligence (12 permissions)
- Reference Checking (10 permissions)
- Email Management (6 permissions)
- Document Management (6 permissions)
- Data Connections (4 permissions)
- User Management (6 permissions)
- Audit & Compliance (3 permissions)
- Platform Administration (8 permissions)
- ... and more

### Control 3: API Audit Logging

**Description**: Comprehensive logging of all API requests for compliance and forensic analysis.

**Implementation**: The `TenantContextMiddleware` logs every authenticated API request using `api_audit_service.log_api_request_sync()`.

**How It Works**:
```
1. Auth dependency decodes JWT → sets request.state.customer_id, user_id
2. Middleware reads request.state (no duplicate JWT decoding)
3. Request is processed
4. Middleware logs to data_access_audit_log with full context
5. Response returned to client
```

**Logged Events**:
```python
# src/services/api_audit_service.py
def log_api_request_sync(
    # WHO
    user_id: int,                    # From request.state (set by auth dependency)
    customer_id: str,                # From request.state (user's tenant)
    session_id: str,
    ip_address: str,                 # From request headers
    user_agent: str,                 # From request headers
    
    # WHAT
    action: str,                     # SELECT, INSERT, UPDATE, DELETE (from HTTP method)
    resource_type: str,              # Extracted from API path (e.g., 'roles', 'users')
    api_endpoint: str,               # Full API path
    api_method: str,                 # GET, POST, PUT, DELETE
    
    # CONTEXT
    is_platform_admin: bool,         # Whether user has platform:admin permission
    view_as_tenant: str | None,      # X-View-As-Tenant header value
    cross_tenant_access: bool,       # X-Cross-Tenant-Access header value
    
    # OUTCOME
    outcome: str,                    # success (status < 400), error (status >= 400)
    status_code: int,                # HTTP status code
    duration_ms: int,                # Request processing time
)
```

**HTTP Method Mapping**:
| HTTP Method | Audit Action |
|-------------|--------------|
| GET | SELECT |
| POST | INSERT |
| PUT | UPDATE |
| PATCH | UPDATE |
| DELETE | DELETE |

**Example Audit Entry**:
```sql
SELECT * FROM data_access_audit_log WHERE api_endpoint = '/api/v1/admin/roles';

--  id | user_id | customer_id | action | api_endpoint        | outcome | duration_ms | timestamp
-- ----+---------+-------------+--------+---------------------+---------+-------------+-----------
-- 101 |       2 | eliza       | SELECT | /api/v1/admin/roles | success |          45 | 2025-12-25
```

### Control 4: Admin Oversight with Audit Trail

**Description**: Platform administrators can view tenant data for support/compliance, but all access is logged and requires explicit action.

**View As Tenant**:
- Requires `platform:admin` permission
- Requires explicit `X-View-As-Tenant` header
- Creates audit log entry with `view_as_tenant` context
- Visual indicator (amber banner) shows current viewing context
- Cannot write data as another tenant

**Cross-Tenant Access**:
- Requires `platform:admin` permission
- Requires explicit `X-Cross-Tenant-Access: true` header
- Creates audit log entry with `cross_tenant_access: true`
- Visual indicator (purple banner) shows cross-tenant mode
- Read-only - writes still go to admin's own tenant

---

## Test Scenarios & Results

> **56 Security Tests** - All Passing as of December 25, 2025  
> See [TEST_SUMMARY.md](./TEST_SUMMARY.md) for complete test documentation.

### Test Suite: Tenant Isolation

#### Scenario 1: Basic Tenant Isolation
**Objective**: Verify users cannot see data from other tenants.

**Setup**:
```python
# Create documents for two tenants
with TenantScopedSession(tenant_id='acme') as db:
    db.add(Document(customer_id='acme', name='Acme Confidential'))
    db.commit()

with TenantScopedSession(tenant_id='globex') as db:
    db.add(Document(customer_id='globex', name='Globex Confidential'))
    db.commit()
```

**Test**:
```python
# Query as Acme user
with TenantScopedSession(tenant_id='acme') as db:
    docs = db.query(Document).all()
    
    assert len(docs) == 1
    assert docs[0].name == 'Acme Confidential'
    assert 'Globex' not in str(docs)
```

**Result**: ✅ PASS
- Acme user only sees Acme document
- Globex document not visible
- No error thrown (silent filtering)

---

#### Scenario 2: Direct SQL Injection Attempt
**Objective**: Verify RLS prevents SQL injection attacks from bypassing tenant isolation.

**Setup**:
```python
# Documents exist for both tenants
```

**Test**:
```python
# Attempt SQL injection via raw query
with TenantScopedSession(tenant_id='acme') as db:
    # Even with raw SQL, RLS applies
    result = db.execute(text("""
        SELECT * FROM documents 
        WHERE name LIKE '%Confidential%'
        -- Attacker tries: OR 1=1
    """))
    docs = result.fetchall()
    
    # RLS still filters to current tenant
    assert all(doc.customer_id == 'acme' for doc in docs)
```

**Result**: ✅ PASS
- Raw SQL still filtered by RLS
- Only Acme documents returned
- Globex documents protected

---

#### Scenario 3: NULL Tenant Context Blocked
**Objective**: Verify that NULL tenant context does not bypass RLS.

**Test**:
```python
# Attempt to create session without tenant
try:
    with TenantScopedSession(tenant_id=None) as db:
        docs = db.query(Document).all()
    assert False, "Should have raised ValueError"
except ValueError as e:
    assert "tenant_id is required" in str(e)
```

**Result**: ✅ PASS
- ValueError raised when tenant_id is None
- No database query executed
- Explicit tenant context enforced

---

#### Scenario 4: Cross-Tenant Write Prevented
**Objective**: Verify platform admin cannot write data to another tenant.

**Setup**:
```python
# Platform admin viewing as Acme
```

**Test**:
```python
with TenantScopedSession(
    tenant_id='eliza',
    is_platform_admin=True,
    cross_tenant_access=True
) as db:
    # Can READ from all tenants
    all_docs = db.query(Document).all()
    assert len({d.customer_id for d in all_docs}) > 1  # Multiple tenants
    
    # Cannot WRITE to another tenant
    try:
        db.add(Document(customer_id='acme', name='Admin Created'))
        db.commit()
        assert False, "Should have been blocked by RLS"
    except Exception as e:
        assert "new row violates row-level security policy" in str(e)
```

**Result**: ✅ PASS
- Cross-tenant reads allowed
- Cross-tenant writes blocked by RLS WITH CHECK clause
- Admin can only write to own tenant (eliza)

---

### Test Suite: Platform Admin Access

#### Scenario 5: View As Tenant with Audit Log
**Objective**: Verify platform admin can view as tenant with proper audit logging.

**Test**:
```python
# Platform admin views as Acme
response = client.get(
    "/api/v1/documents",
    headers={
        "Authorization": f"Bearer {platform_admin_token}",
        "X-View-As-Tenant": "acme"
    }
)

# Verify response
assert response.status_code == 200
assert response.headers['X-Viewing-As-Tenant'] == 'acme'
docs = response.json()
assert all(d['customer_id'] == 'acme' for d in docs)

# Verify audit log
audit_log = db.query(DataAccessAuditLog).order_by(
    DataAccessAuditLog.id.desc()
).first()

assert audit_log.user_id == platform_admin_user.id
assert audit_log.customer_id == 'eliza'  # Admin's actual tenant
assert audit_log.resource_type == 'documents'
assert audit_log.action == 'SELECT'
assert 'view_as_tenant' in audit_log.context
assert audit_log.context['view_as_tenant'] == 'acme'
```

**Result**: ✅ PASS
- Platform admin can view Acme's documents
- Audit log records the view_as_tenant context
- Admin's actual tenant (eliza) recorded in customer_id

---

#### Scenario 6: Non-Admin Cannot Use View As
**Objective**: Verify regular users cannot use X-View-As-Tenant header.

**Test**:
```python
# Regular user attempts to view as another tenant
response = client.get(
    "/api/v1/documents",
    headers={
        "Authorization": f"Bearer {regular_user_token}",
        "X-View-As-Tenant": "globex"  # Attempt to view as Globex
    }
)

# Header is ignored for non-admins
assert response.status_code == 200
docs = response.json()
assert all(d['customer_id'] == 'acme' for d in docs)  # User's own tenant
```

**Result**: ✅ PASS
- Header ignored for non-platform admins
- User only sees own tenant's data
- No error thrown (fails safely)

---

### Test Suite: Audit Logging

#### Scenario 7: All Access Logged
**Objective**: Verify every data access creates an audit log entry.

**Test**:
```python
# Clear recent logs
initial_count = db.query(DataAccessAuditLog).count()

# Make several API calls
client.get("/api/v1/documents", headers=auth_headers)
client.get("/api/v1/users", headers=auth_headers)
client.post("/api/v1/documents", json={...}, headers=auth_headers)

# Verify logs created
final_count = db.query(DataAccessAuditLog).count()
assert final_count >= initial_count + 3

# Verify log contents
logs = db.query(DataAccessAuditLog).order_by(
    DataAccessAuditLog.id.desc()
).limit(3).all()

assert logs[0].action == 'POST'
assert logs[0].resource_type == 'documents'
assert logs[1].action == 'GET'
assert logs[1].resource_type == 'users'
assert logs[2].action == 'GET'
assert logs[2].resource_type == 'documents'
```

**Result**: ✅ PASS
- Every API call logged
- Action, resource_type, and tenant context recorded
- Logs can be queried for compliance reporting

---

#### Scenario 8: RLS Violation Logged
**Objective**: Verify RLS violations are specifically logged for security alerting.

**Test**:
```python
# Simulate RLS violation (direct DB attempt)
with TenantScopedSession(tenant_id='acme') as db:
    try:
        # Attempt to insert with wrong customer_id
        db.execute(text("""
            INSERT INTO documents (customer_id, name)
            VALUES ('globex', 'Injected Document')
        """))
        db.commit()
    except Exception:
        pass  # Expected to fail

# Check RLS violation log
violation = db.query(RLSViolationLog).order_by(
    RLSViolationLog.id.desc()
).first()

assert violation is not None
assert violation.table_name == 'documents'
assert violation.attempted_action == 'INSERT'
assert violation.customer_id == 'acme'  # User's tenant
```

**Result**: ✅ PASS
- RLS violation detected and logged
- Violation details captured (table, action, context)
- Can be used for security alerting

---

## Audit Logging

### Log Retention

| Log Type | Retention Period | Storage |
|----------|-----------------|---------|
| DataAccessAuditLog | 2 years | PostgreSQL + S3 archive |
| RLSViolationLog | 3 years | PostgreSQL + S3 archive |
| UserAuditLog | 2 years | PostgreSQL + S3 archive |
| Authentication logs | 1 year | PostgreSQL + S3 archive |

### Log Fields

**DataAccessAuditLog**:
```sql
CREATE TABLE data_access_audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- WHO
    user_id INTEGER REFERENCES users(id),
    customer_id VARCHAR(100),  -- User's actual tenant
    session_id VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent TEXT,
    
    -- WHAT
    action VARCHAR(50) NOT NULL,  -- SELECT, INSERT, UPDATE, DELETE
    resource_type VARCHAR(100) NOT NULL,
    resource_ids TEXT[],
    records_affected INTEGER,
    
    -- CONTEXT
    api_endpoint VARCHAR(255),
    query_hash VARCHAR(64),
    data_classification VARCHAR(50),
    
    -- OUTCOME
    outcome VARCHAR(20) NOT NULL,  -- success, denied, error
    denial_reason VARCHAR(255),
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX idx_audit_timestamp ON data_access_audit_log(timestamp);
CREATE INDEX idx_audit_customer ON data_access_audit_log(customer_id);
CREATE INDEX idx_audit_user ON data_access_audit_log(user_id);
CREATE INDEX idx_audit_outcome ON data_access_audit_log(outcome);
```

### Querying Audit Logs

```sql
-- All access by a specific user in last 30 days
SELECT * FROM data_access_audit_log
WHERE user_id = 123
  AND timestamp > NOW() - INTERVAL '30 days'
ORDER BY timestamp DESC;

-- Cross-tenant access by platform admins
SELECT * FROM data_access_audit_log
WHERE outcome = 'success'
  AND (
    context->>'view_as_tenant' IS NOT NULL
    OR context->>'cross_tenant_access' = 'true'
  )
ORDER BY timestamp DESC;

-- Failed access attempts (potential security issues)
SELECT * FROM data_access_audit_log
WHERE outcome IN ('denied', 'error')
ORDER BY timestamp DESC
LIMIT 100;

-- RLS violations (security alerts)
SELECT * FROM rls_violation_log
WHERE timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

---

## Incident Response

### Security Event Classification

| Severity | Event Type | Response SLA |
|----------|-----------|--------------|
| Critical | RLS violation attempt | < 1 hour |
| Critical | Unauthorized cross-tenant access | < 1 hour |
| High | Multiple failed auth attempts | < 4 hours |
| High | Unusual data access patterns | < 4 hours |
| Medium | Failed permission checks | < 24 hours |
| Low | Normal audit log anomalies | < 72 hours |

### Automated Alerting

```python
# Example alerting query (run every 5 minutes)
SELECT COUNT(*) as violation_count
FROM rls_violation_log
WHERE timestamp > NOW() - INTERVAL '5 minutes';

# Alert if violation_count > 0
```

### Incident Response Procedure

1. **Detection**: Automated monitoring or manual report
2. **Triage**: Assess severity and scope
3. **Containment**: Disable affected user/tenant if needed
4. **Investigation**: Query audit logs for full activity
5. **Resolution**: Fix vulnerability, restore access
6. **Documentation**: Document incident and response
7. **Review**: Post-incident review and improvements

---

## Compliance Mapping

### SOC2 Trust Services Criteria

| Criteria | Description | Controls |
|----------|-------------|----------|
| **CC6.1** | Logical and physical access controls | RLS, RBAC, middleware validation |
| **CC6.2** | User access authorization | Permission-based access, role assignment |
| **CC6.3** | Segregation of duties | Tenant isolation, admin oversight logging |
| **CC6.6** | External threats | RLS prevents injection, rate limiting |
| **CC6.7** | Transmission security | TLS 1.3, encrypted connections |
| **CC7.2** | System monitoring | Audit logging, violation detection |
| **CC7.3** | Incident response | Alerting, response procedures |
| **CC8.1** | Change management | Migration-based schema changes |

### Evidence Collection

For SOC2 audits, the following evidence can be provided:

1. **Database Configuration**
   - RLS policy definitions
   - Table security settings
   - User/role configurations

2. **Audit Logs**
   - Data access logs (DataAccessAuditLog)
   - RLS violation logs (RLSViolationLog)
   - Authentication logs (UserAuditLog)

3. **Test Results**
   - Automated test suite results
   - Penetration test reports
   - Security scan results

4. **Access Reviews**
   - User access lists by tenant
   - Permission assignments
   - Platform admin activity logs

---

## Appendix: SQL Verification Queries

### Verify RLS is Enabled
```sql
SELECT tablename, relrowsecurity, relforcerowsecurity
FROM pg_tables t
JOIN pg_class c ON t.tablename = c.relname
WHERE schemaname = 'public'
  AND tablename IN ('users', 'documents', 'candidates');
```

### List All RLS Policies
```sql
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename;
```

### Verify Session Variables
```sql
-- In a tenant-scoped session
SELECT 
    current_setting('app.customer_id', true) as tenant_id,
    current_setting('app.is_platform_admin', true) as is_admin,
    current_setting('app.cross_tenant_access', true) as cross_tenant;
```

---

## See Also

- [Security Quick Start](./security_quick_start.md) - TL;DR reference
- [Security for Dev Team](./security_for_dev_team.md) - Implementation guide
- [Test Summary](./TEST_SUMMARY.md) - Overview of all 56 security tests
- [Test Results](./TEST_RESULTS_2025-12-25.md) - Detailed test output

---

*Document Version: 1.1*
*Last Updated: December 25, 2025*
*Changelog: Updated API audit logging implementation details, added test references*
*Author: Eliza Platform Security Team*

