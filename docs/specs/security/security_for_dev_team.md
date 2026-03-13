# Security Guide for Development Team

This document provides comprehensive guidance on implementing secure, multi-tenant features in the Eliza Platform.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Row Level Security (RLS)](#row-level-security-rls)
3. [Tenant Context Management](#tenant-context-management)
4. [Platform Admin Features](#platform-admin-features)
5. [Writing Secure Code](#writing-secure-code)
6. [Testing Security](#testing-security)
7. [Common Pitfalls](#common-pitfalls)

---

## Architecture Overview

### Defense in Depth

The platform implements **three layers** of tenant isolation:

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Application Layer                                       │
│ - Permission checks via RBAC                                     │
│ - Middleware validates tenant context                            │
│ - Service methods filter by customer_id                          │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Database Layer (RLS)                                    │
│ - PostgreSQL Row Level Security policies                         │
│ - Automatic filtering based on app.customer_id session var       │
│ - Cannot be bypassed even with raw SQL                          │
│ - NO NULL BYPASS - every query requires explicit tenant         │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Audit Layer                                             │
│ - All data access logged (DataAccessAuditLog)                   │
│ - RLS violations tracked (RLSViolationLog)                      │
│ - Cross-tenant access flagged and logged                        │
└─────────────────────────────────────────────────────────────────┘
```

### Tenant Hierarchy

```
'eliza' (Platform Operator Tenant)
    └── Platform Admins (Eliza team)
    └── Can "View As" any tenant
    └── Can enable cross-tenant access for reports

'acme' (Customer Tenant)
    └── Tenant Admins → Full control within tenant
    └── Tenant Editors → Can create/edit within tenant
    └── Tenant Viewers → Read-only within tenant

'globex' (Customer Tenant)
    └── Same role structure, completely isolated
```

---

## Row Level Security (RLS)

### How RLS Works

Every tenant-scoped table has policies that automatically filter rows:

```sql
-- The policy definition (created by migration)
CREATE POLICY tenant_isolation_policy ON documents
  FOR ALL
  USING (
    -- Normal case: see only your tenant
    customer_id = current_tenant_id()
    -- Platform admin cross-tenant: requires EXPLICIT flags
    OR is_cross_tenant_access_allowed()
  )
  WITH CHECK (
    -- Writes MUST specify correct tenant (no cross-tenant writes)
    customer_id = current_tenant_id()
  );
```

### PostgreSQL Session Variables

The middleware sets these session variables for every request:

| Variable | Type | Description |
|----------|------|-------------|
| `app.customer_id` | string | Current tenant ID (REQUIRED) |
| `app.is_platform_admin` | boolean | Is user a platform admin? |
| `app.cross_tenant_access` | boolean | Is cross-tenant enabled? |

### Tables with RLS Enabled

All tenant-scoped tables have RLS enabled:

- `users`, `roles`, `user_invites`
- `documents`, `document_chunks`, `upload_batches`
- `connector_configurations`, `connector_sync_runs`, `ingested_data`
- `candidates`, `candidate_analysis_scores`, `career_blueprints`
- `reference_check_requests`, `reference_calls`, `reference_call_transcripts`
- `email_templates`, `generated_emails`, `outreach_emails`
- ... and more (see migration for full list)

---

## Tenant Context Management

### How Tenant Context Flows (Updated Architecture)

The system uses a clean separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. AUTH DEPENDENCY (src/middleware/authorization.py)            │
│    - Decodes JWT token                                          │
│    - Loads user from database                                   │
│    - Sets request.state.customer_id, user_id, is_platform_admin │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. TENANT CONTEXT MIDDLEWARE (src/middleware/tenant_context.py) │
│    - Reads from request.state (NO JWT decoding)                 │
│    - Sets PostgreSQL session variables for RLS                  │
│    - Logs API request via api_audit_service                     │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. DATABASE (PostgreSQL with RLS)                               │
│    - Reads app.customer_id session variable                     │
│    - Automatically filters queries                              │
└─────────────────────────────────────────────────────────────────┘
```

### Auth Dependency (Source of Truth)

```python
# src/middleware/authorization.py

async def get_current_user_context(request: Request, token: str = Depends(oauth2_scheme)):
    """Auth dependency - single source of truth for user context."""
    # Decode JWT
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])
    user_id = payload.get("sub")
    
    # Load user from database
    user = db.query(User).filter(User.id == user_id).first()
    
    # Set request.state - this is what middleware reads
    request.state.customer_id = user.customer_id
    request.state.user_id = user.id
    request.state.is_platform_admin = has_permission(user, 'platform:admin')
    
    return user
```

### Middleware Flow (Simplified - No JWT Decoding)

```python
# src/middleware/tenant_context.py

class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 1. Read from request.state (set by auth dependency)
        tenant_id = getattr(request.state, 'customer_id', None)
        user_id = getattr(request.state, 'user_id', None)
        is_platform_admin = getattr(request.state, 'is_platform_admin', False)
        
        # 2. Handle "View As" for platform admins
        view_as_tenant = None
        if is_platform_admin:
            view_as_tenant = request.headers.get('X-View-As-Tenant')
            if view_as_tenant:
                tenant_id = view_as_tenant  # Override tenant context
        
        # 3. Set context variables
        set_tenant_context(tenant_id, user_id)
        
        # 4. Process request
        start_time = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start_time) * 1000)
        
        # 5. Log API request (runs synchronously in background)
        log_api_request_sync(
            action=HTTP_METHOD_TO_ACTION.get(request.method, 'UNKNOWN'),
            resource_type=extract_resource_type(request.url.path),
            api_endpoint=request.url.path,
            api_method=request.method,
            customer_id=tenant_id,
            user_id=user_id,
            duration_ms=duration_ms,
            outcome='success' if response.status_code < 400 else 'error',
            ...
        )
        
        # 6. Clean up
        clear_tenant_context()
        return response
```

### Using TenantScopedSession

For database operations outside the request context (Celery tasks, background jobs):

```python
from src.middleware.tenant_context import TenantScopedSession

# Normal tenant-scoped query
with TenantScopedSession(tenant_id='acme') as db:
    documents = db.query(Document).all()
    # Only returns Acme's documents

# Platform admin cross-tenant query
with TenantScopedSession(
    tenant_id='eliza',
    is_platform_admin=True,
    cross_tenant_access=True
) as db:
    all_documents = db.query(Document).all()
    # Returns documents from ALL tenants
```

### Important: Tenant ID is NEVER NULL

```python
# ❌ WRONG - Will raise ValueError
with TenantScopedSession(tenant_id=None) as db:
    ...

# ✅ CORRECT - Always provide tenant_id
with TenantScopedSession(tenant_id=settings.customer_id) as db:
    ...
```

---

## Platform Admin Features

### View As Tenant

Allows platform admin to see the app as a specific tenant's admin:

**Frontend:**
```typescript
// In TenantManagementPage - "View As" button per tenant
const handleViewAsTenant = (tenant: Tenant) => {
  setViewingAsTenant({
    tenantId: tenant.customer_id,
    tenantName: tenant.name,
  });
  navigate('/');  // Go to dashboard as that tenant
};
```

**API Client (automatic):**
```typescript
// api-client.ts adds headers automatically from auth store
if (authState?.viewingAsTenant?.tenantId) {
  config.headers['X-View-As-Tenant'] = authState.viewingAsTenant.tenantId;
}
```

**Visual Indicator:**
- Amber banner at top of screen
- "Viewing As Tenant | You are viewing the application as **Acme Corp**"

### Cross-Tenant Access

Allows platform admin to see data from ALL tenants (for reports/compliance):

**Frontend:**
```typescript
// "View All Tenants" button on Tenant Management page
const handleToggleCrossTenantAccess = () => {
  setCrossTenantAccess(true);
};
```

**API Client (automatic):**
```typescript
if (authState?.crossTenantAccess) {
  config.headers['X-Cross-Tenant-Access'] = 'true';
}
```

**Visual Indicator:**
- Purple banner at top of screen
- "Cross-Tenant Access Mode | Viewing data from ALL TENANTS"

**Important Restrictions:**
- Cross-tenant allows **READS only**
- Writes always go to the user's own tenant
- This is enforced at the RLS policy level

---

## Writing Secure Code

### DO: Use Existing Patterns

```python
# ✅ Use the tenant-scoped session
from src.middleware.tenant_context import TenantScopedSession

async def get_documents_for_tenant(tenant_id: str):
    with TenantScopedSession(tenant_id=tenant_id) as db:
        return db.query(Document).all()
```

### DO: Filter by customer_id (Belt and Suspenders)

```python
# ✅ Even though RLS filters, explicit filtering is good practice
def get_user_documents(db: Session, user: User):
    return db.query(Document).filter(
        Document.customer_id == user.customer_id
    ).all()
```

### DO: Validate Tenant Access in Service Layer

```python
# ✅ Validate before operations
def update_document(db: Session, doc_id: int, user: User, data: dict):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    
    if not doc:
        raise NotFoundError("Document not found")
    
    if doc.customer_id != user.customer_id:
        raise ForbiddenError("Cannot access document from another tenant")
    
    # Proceed with update...
```

### DON'T: Assume NULL Bypasses RLS

```python
# ❌ WRONG - NULL tenant_id will raise an error
db = SessionLocal()
db.execute("SET app.customer_id = NULL")  # Won't work!

# ✅ CORRECT - Always set explicit tenant
db.execute(f"SET app.customer_id = '{tenant_id}'")
```

### DON'T: Hardcode Tenant IDs

```python
# ❌ WRONG - Hardcoded tenant ID
documents = db.query(Document).filter(
    Document.customer_id == 'acme'
).all()

# ✅ CORRECT - Get from user context
documents = db.query(Document).filter(
    Document.customer_id == current_user.customer_id
).all()
```

### DON'T: Skip Tenant Validation on Writes

```python
# ❌ WRONG - Trusting client-provided customer_id
@router.post("/documents")
def create_document(data: DocumentCreate, db: Session):
    doc = Document(customer_id=data.customer_id, ...)  # Don't trust this!

# ✅ CORRECT - Use authenticated user's tenant
@router.post("/documents")
def create_document(data: DocumentCreate, db: Session, user: User):
    doc = Document(customer_id=user.customer_id, ...)  # Use user's tenant
```

---

## Testing Security

We have **56 comprehensive security tests**. See [TEST_SUMMARY.md](./TEST_SUMMARY.md) for full details.

### Running All Security Tests

```bash
# Run all 56 tests
docker compose exec app pytest tests/security/ -v

# Run specific test file
docker compose exec app pytest tests/security/test_audit_integration.py -v

# Run with coverage
docker compose exec app pytest tests/security/ --cov=src/middleware --cov=src/services
```

### Unit Testing Tenant Isolation

```python
import pytest
from src.middleware.tenant_context import TenantScopedSession

def test_tenant_isolation():
    """Documents from other tenants should not be visible."""
    # Create documents for two tenants
    with TenantScopedSession(tenant_id='acme') as db:
        db.add(Document(customer_id='acme', name='Acme Doc'))
        db.commit()
    
    with TenantScopedSession(tenant_id='globex') as db:
        db.add(Document(customer_id='globex', name='Globex Doc'))
        db.commit()
    
    # Query as Acme - should only see Acme's doc
    with TenantScopedSession(tenant_id='acme') as db:
        docs = db.query(Document).all()
        assert len(docs) == 1
        assert docs[0].name == 'Acme Doc'

def test_cross_tenant_requires_flag():
    """Cross-tenant access requires explicit flag."""
    # Without flag - only see own tenant
    with TenantScopedSession(
        tenant_id='eliza',
        is_platform_admin=True,
        cross_tenant_access=False
    ) as db:
        docs = db.query(Document).all()
        assert all(d.customer_id == 'eliza' for d in docs)
    
    # With flag - see all tenants
    with TenantScopedSession(
        tenant_id='eliza',
        is_platform_admin=True,
        cross_tenant_access=True
    ) as db:
        docs = db.query(Document).all()
        tenant_ids = {d.customer_id for d in docs}
        assert len(tenant_ids) > 1  # Multiple tenants visible
```

### Testing API Audit Logging (NEW)

```python
def test_api_request_creates_audit_entry(self):
    """Every API request MUST create an audit entry."""
    response = httpx.get("/api/v1/admin/roles", headers=auth_headers)
    assert response.status_code == 200
    
    time.sleep(0.5)  # Wait for sync audit
    
    result = db.execute(text("""
        SELECT action, customer_id, user_id, outcome, duration_ms
        FROM data_access_audit_log
        WHERE api_endpoint = '/api/v1/admin/roles'
    """))
    row = result.fetchone()
    
    assert row is not None, "Audit entry MUST exist"
    assert row.action == 'SELECT'  # GET → SELECT
    assert row.customer_id == 'eliza'
    assert row.user_id is not None
    assert row.outcome == 'success'
    assert row.duration_ms > 0
```

### Testing Auth Dependency request.state (NEW)

```python
def test_authenticated_request_has_customer_id(self):
    """Auth dependency MUST set request.state.customer_id."""
    response = httpx.get("/api/v1/admin/roles", headers=auth_headers)
    
    # Audit entry proves customer_id was set by auth dependency
    result = db.execute(text("""
        SELECT customer_id, user_id FROM data_access_audit_log
        WHERE api_endpoint = '/api/v1/admin/roles'
    """))
    row = result.fetchone()
    
    assert row.customer_id == 'eliza'  # From JWT via auth dependency
    assert row.user_id is not None     # From JWT via auth dependency
```

### Integration Testing with Headers

```python
def test_view_as_tenant_header(client, platform_admin_token):
    """Platform admin can view as specific tenant."""
    # Without header - see own tenant
    response = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {platform_admin_token}"}
    )
    assert response.headers['X-Tenant-ID'] == 'eliza'
    
    # With header - see target tenant
    response = client.get(
        "/api/v1/documents",
        headers={
            "Authorization": f"Bearer {platform_admin_token}",
            "X-View-As-Tenant": "acme"
        }
    )
    assert response.headers['X-Viewing-As-Tenant'] == 'acme'
```

---

## Common Pitfalls

### Pitfall 1: Forgetting to Set Tenant in Background Tasks

```python
# ❌ WRONG - No tenant context in Celery task
@celery.task
def process_documents():
    db = SessionLocal()
    docs = db.query(Document).all()  # Fails! No tenant context

# ✅ CORRECT - Set tenant context
@celery.task
def process_documents(tenant_id: str):
    with TenantScopedSession(tenant_id=tenant_id) as db:
        docs = db.query(Document).all()  # Works!
```

### Pitfall 2: Direct Import of SessionLocal

```python
# ❌ WRONG - SessionLocal may not be initialized
from src.models.database import SessionLocal
db = SessionLocal()  # May fail!

# ✅ CORRECT - Use TenantScopedSession or check initialization
from src.models import database
if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()
```

### Pitfall 3: Assuming Empty Results = Error

```python
# RLS silently filters out inaccessible rows
# ❌ Don't assume something is wrong
docs = db.query(Document).filter(Document.id == 123).all()
if not docs:
    raise Exception("RLS is broken!")  # Wrong assumption!

# ✅ Check if the document exists for the user's tenant
doc = db.query(Document).filter(
    Document.id == 123,
    Document.customer_id == user.customer_id
).first()
if not doc:
    raise NotFoundError("Document not found or access denied")
```

### Pitfall 4: Logging Sensitive Data

```python
# ❌ WRONG - Logging full query results
logger.info(f"Found documents: {documents}")  # May leak tenant data!

# ✅ CORRECT - Log counts and IDs only
logger.info(f"Found {len(documents)} documents for tenant {tenant_id}")
```

---

## See Also

- [Security Quick Start](./security_quick_start.md) - TL;DR reference
- [Test Summary](./TEST_SUMMARY.md) - Overview of all 56 security tests
- [Security Details for SOC2](./security_details_for_soc2.md) - Compliance documentation
- [Multi-Tenant RLS Spec](../multi-tenant-rls.md) - Full technical specification
- [Permissions Comprehensive Spec](../permissions-comprehensive.md) - RBAC details

---

*Document Version: 1.1*
*Last Updated: December 25, 2025*
*Changelog: Added API audit logging architecture, auth dependency request.state flow*

