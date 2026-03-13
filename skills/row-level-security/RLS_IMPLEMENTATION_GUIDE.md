# Multi-Tenant Row Level Security (RLS) Implementation

> **Purpose:** Describes the Row Level Security implementation for the Eliza Platform, designed for SOC2 compliance and robust multi-tenant data isolation. Reference this before adding tenant-scoped features or modifying data access patterns.

---

## Quick Reference

```python
# ✅ CORRECT: Tenant-scoped database access
from src.middleware.tenant_context import TenantScopedSession

async def process_for_tenant(tenant_id: str):
    with TenantScopedSession(tenant_id=tenant_id) as db:
        # All queries automatically scoped to tenant_id
        docs = db.query(Document).all()
```

---

## Overview

The platform implements three layers of tenant isolation (defense in depth):

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Application Layer                                       │
│ - Manual customer_id filtering in service methods                │
│ - Context validation in API routes                               │
│ - Permission checks via RBAC                                     │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Database Layer (RLS)                                    │
│ - PostgreSQL Row Level Security policies                         │
│ - Automatic filtering based on session variable                  │
│ - Cannot be bypassed even with raw SQL                          │
│ - NO NULL BYPASS - every query requires explicit tenant context │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Audit Layer                                             │
│ - All data access logged                                         │
│ - RLS violations tracked                                         │
│ - Compliance reports generated                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Tenant Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT HIERARCHY                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  'eliza' (Platform Operator Tenant) ← CUSTOMER_ID env var       │
│    └── Platform Admins (Eliza team)                             │
│    └── Platform-level settings                                  │
│    └── Can "View As" any tenant with X-View-As-Tenant header   │
│                                                                  │
│  'acme' (Customer Tenant)                                       │
│    └── Tenant Admins                                            │
│    └── Tenant Users                                             │
│    └── Tenant data (isolated by RLS)                            │
│                                                                  │
│  'globex' (Customer Tenant)                                     │
│    └── Tenant Admins                                            │
│    └── Tenant Users                                             │
│    └── Tenant data (isolated by RLS)                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### How RLS Works

Before any database query, the application sets a session variable:

```sql
SET LOCAL app.customer_id = 'tenant_123';
```

Every tenant-scoped table has a policy like:

```sql
CREATE POLICY tenant_isolation_policy ON documents
  FOR ALL
  USING (
    customer_id = current_tenant_id()
    OR is_cross_tenant_access_allowed()
  )
  WITH CHECK (
    customer_id = current_tenant_id()
  );
```

### Platform Admin Access Modes

| Mode | Headers | Can Read | Can Write |
|------|---------|----------|-----------|
| Normal (own tenant) | None | Own tenant only | Own tenant only |
| View As Tenant | `X-View-As-Tenant: acme` | Target tenant only | Target tenant only |
| Cross-Tenant Reports | `X-Cross-Tenant-Access: true` | All tenants | Own tenant only |

### Tables with RLS Enabled

- `users`
- `roles`
- `user_invites`
- `documents`
- `document_chunks`
- `candidates`
- `reference_check_requests`
- `analysis_configs`
- `email_templates`
- `outreach_emails`
- `connector_configurations`
- ... (all tables with `customer_id` column)

---

## Critical Rules

### Rule 1: Every Query Requires Explicit Tenant Context

**Context:** There is NO NULL bypass in RLS policies. Every query requires `app.customer_id` to be set. Queries without tenant context will return zero rows, not all rows.

```sql
-- ❌ WRONG: No tenant context set — returns empty results
SELECT * FROM documents;

-- ✅ CORRECT: Set tenant context first
SET LOCAL app.customer_id = 'tenant_123';
SELECT * FROM documents;
```

### Rule 2: Cross-Tenant Access Requires Both Flags

**Context:** Cross-tenant access requires BOTH `app.is_platform_admin` AND `app.cross_tenant_access` to be explicitly set to `'true'`. Setting only one is not sufficient.

```python
# ❌ WRONG: Only one flag set
with TenantScopedSession(
    tenant_id=settings.customer_id,
    is_platform_admin=True
) as db:
    all_users = db.query(User).all()  # Only sees own tenant!

# ✅ CORRECT: Both flags set
with TenantScopedSession(
    tenant_id=settings.customer_id,
    is_platform_admin=True,
    cross_tenant_access=True
) as db:
    all_users = db.query(User).all()  # Sees all tenants
```

### Rule 3: Never Expose Raw SQL Execution to Users

**Context:** RLS only protects properly parameterized queries. Raw SQL execution could bypass protections if tenant context is not properly set.

```python
# ❌ WRONG: User-provided SQL without context
db.execute(text(user_provided_query))

# ✅ CORRECT: Always use ORM with tenant-scoped session
with TenantScopedSession(tenant_id=tenant_id) as db:
    results = db.query(Document).filter(Document.status == 'active').all()
```

### Rule 4: Always Validate Tenant Context in Application Layer

**Context:** RLS is the last line of defense. The application layer should also validate tenant context as defense-in-depth.

```python
# ❌ WRONG: Relying solely on RLS
@router.get("/documents/{id}")
async def get_document(id: int, db: Session = Depends(get_db)):
    return db.query(Document).get(id)

# ✅ CORRECT: Application-layer validation + RLS
@router.get("/documents/{id}")
async def get_document(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc = db.query(Document).get(id)
    if doc and doc.customer_id != current_user.customer_id:
        raise HTTPException(403, "Access denied")
    return doc
```

---

## Patterns

### In FastAPI Routes

The `TenantContextMiddleware` automatically sets the tenant context based on the authenticated user:

```python
@router.get("/items")
async def get_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # RLS automatically filters to current_user's tenant
    items = db.query(Item).all()
    return items
```

### In Service Methods

Use the `TenantScopedSession` context manager:

```python
from src.middleware.tenant_context import TenantScopedSession

async def process_for_tenant(tenant_id: str):
    with TenantScopedSession(tenant_id=tenant_id) as db:
        # All queries scoped to tenant_id
        docs = db.query(Document).all()
```

### In Celery Tasks

Set tenant context before database operations:

```python
from src.middleware.tenant_context import set_tenant_context, clear_tenant_context

@celery_app.task
def process_documents(tenant_id: str, user_id: int):
    set_tenant_context(tenant_id, user_id)
    try:
        with TenantScopedSession(tenant_id=tenant_id) as db:
            # Process documents
            pass
    finally:
        clear_tenant_context()
```

### Platform Admin Cross-Tenant Operations

When platform admins need to access all tenants (reports, dashboards):

```python
from src.middleware.tenant_context import TenantScopedSession
from src.core.config import get_settings

settings = get_settings()

with TenantScopedSession(
    tenant_id=settings.customer_id,  # Platform admin's home tenant (e.g., 'eliza')
    is_platform_admin=True,
    cross_tenant_access=True
) as db:
    # Can read from all tenants
    all_users = db.query(User).all()
    
    # Writes still go to their own tenant
    new_setting = SystemSetting(customer_id=settings.customer_id, ...)
    db.add(new_setting)
```

### Database Migrations

Migrations run as the database superuser, which bypasses RLS:

```python
# In Alembic migration
def upgrade():
    conn = op.get_bind()
    # Superuser bypasses RLS - no need to set context
    conn.execute(text("UPDATE users SET ..."))
```

### Frontend: View As Tenant

Platform admins can view as a specific tenant by sending a header:

```typescript
// In API client
const response = await axios.get('/api/v1/users', {
  headers: {
    'X-View-As-Tenant': 'acme'  // View as Acme's admin
  }
});

// For cross-tenant reports
const response = await axios.get('/api/v1/compliance/reports', {
  headers: {
    'X-Cross-Tenant-Access': 'true'  // See all tenants
  }
});
```

### Audit Logging

#### Data Access Logs

Every significant data operation is logged to `data_access_audit_log`:

```python
await audit_service.log_data_access(
    action='SELECT',
    resource_type='documents',
    resource_id='123',
    records_affected=10,
    outcome='success'
)
```

#### RLS Violation Logs

When cross-tenant access is detected and blocked, it's logged:

```python
await audit_service.log_rls_violation(
    customer_id='tenant_123',
    target_customer_id='tenant_456',
    table_name='documents',
    operation='SELECT',
    blocked_by='application'
)
```

### Compliance Reporting

#### Available Reports

1. **User Access Report**: All data access by a specific user
2. **Tenant Security Report**: Security events, RLS violations, denied access
3. **Activity Summary**: Aggregated activity metrics

#### API Endpoints

```bash
# Get audit dashboard
GET /api/v1/compliance/dashboard?days=30

# List data access logs
GET /api/v1/compliance/audit/data-access?resource_type=documents

# List RLS violations
GET /api/v1/compliance/audit/rls-violations

# Generate compliance report
POST /api/v1/compliance/reports/generate
{
    "report_type": "tenant_security",
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-12-31T23:59:59Z"
}
```

### SOC2 Compliance Mapping

| SOC2 Requirement | Implementation |
|-----------------|----------------|
| CC6.1 - Logical access security | RLS policies + RBAC |
| CC6.2 - Authorized access | Authentication + tenant context |
| CC6.3 - Access monitoring | DataAccessAuditLog |
| CC7.2 - Anomaly detection | RLSViolationLog + severity tracking |
| CC7.3 - Security events | Audit logging with severity levels |

---

## Testing

### Verify RLS is Working

```sql
-- As application user, set tenant context
SET app.customer_id = 'tenant_a';

-- Should only return tenant_a's documents
SELECT * FROM documents;

-- Verify count matches expected
SELECT COUNT(*) FROM documents;
```

### Test Cross-Tenant Isolation

```sql
-- Set to tenant_a
SET app.customer_id = 'tenant_a';

-- Try to select tenant_b's document by ID (should return empty)
SELECT * FROM documents WHERE id = 123;  -- 123 belongs to tenant_b

-- Result: Empty (RLS blocked it)
```

### Verify RLS is Enabled on a Table

```sql
SELECT relrowsecurity FROM pg_class WHERE relname = 'tablename';
```

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| No rows returned when data expected | Check if `app.customer_id` is set correctly; verify data belongs to the current tenant |
| RLS not enforcing | Verify RLS is enabled: `SELECT relrowsecurity FROM pg_class WHERE relname = 'tablename';` Check FORCE ROW LEVEL SECURITY and that session user isn't a superuser |
| Admin operations failing | Use `TenantScopedSession` with `is_platform_admin=True` and `cross_tenant_access=True`, or use superuser connection for migrations |
| Querying wrong tenant's data | Use `company_hr_dataset` for document searches, not `customer_id` |
| Audit log retention too short | Keep logs for compliance period (default: 7 years) |

---

## Checklist

- [ ] `TenantScopedSession` used for all out-of-request database access
- [ ] Tenant context set before any database operation in Celery tasks
- [ ] `clear_tenant_context()` called in `finally` block
- [ ] Cross-tenant access uses both `is_platform_admin` and `cross_tenant_access` flags
- [ ] Application-layer tenant validation present (defense-in-depth)
- [ ] RLS policies tested after schema changes
- [ ] Audit logging enabled for significant data operations
- [ ] RLS violations monitored
- [ ] Container rebuilt: `docker-compose build app celery-worker`

---

## References

- `src/middleware/tenant_context.py` — TenantScopedSession and tenant context utilities
- `src/middleware/authorization.py` — RBAC permission checks
- `src/core/config.py` — Platform settings including `customer_id`
- `alembic/versions/` — Migration files with RLS policy definitions
- `skills/common-actions/COMMON_ACTIONS.md` — Common dev operations
- `skills/fastapi-endpoints/` — API endpoint patterns with auth
- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) — Official RLS reference
