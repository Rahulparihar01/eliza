# Multi-Tenant Row Level Security (RLS) Implementation

## Overview

This document describes the Row Level Security (RLS) implementation for the Eliza Platform, designed for SOC2 compliance and robust multi-tenant data isolation.

## Architecture

### Defense in Depth

The platform implements three layers of tenant isolation:

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

## Implementation Details

### 1. PostgreSQL Session Variable

Before any database query, the application sets a session variable:

```sql
SET LOCAL app.customer_id = 'tenant_123';
```

This variable is used by RLS policies to filter all queries automatically.

### 2. RLS Policies

Every tenant-scoped table has a policy like:

```sql
CREATE POLICY tenant_isolation_policy ON documents
  FOR ALL
  USING (
    -- Normal case: user can only see their own tenant's data
    customer_id = current_tenant_id()
    -- Platform admin cross-tenant access: requires EXPLICIT flags
    OR is_cross_tenant_access_allowed()
  )
  WITH CHECK (
    -- Writes MUST specify the correct tenant (no cross-tenant writes)
    customer_id = current_tenant_id()
  );
```

**Security Note:** There is NO NULL bypass. Every query requires:
- `app.customer_id` - The tenant context (REQUIRED)
- `app.is_platform_admin` - Whether user is platform admin
- `app.cross_tenant_access` - Whether cross-tenant reads are allowed

Cross-tenant access requires BOTH flags to be explicitly set to 'true'.

### 3. Platform Admin Access Modes

| Mode | Headers | Can Read | Can Write |
|------|---------|----------|-----------|
| Normal (own tenant) | None | Own tenant only | Own tenant only |
| View As Tenant | `X-View-As-Tenant: acme` | Target tenant only | Target tenant only |
| Cross-Tenant Reports | `X-Cross-Tenant-Access: true` | All tenants | Own tenant only |

### 3. Tables with RLS Enabled

The following tables have RLS policies:

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

## Usage

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

### For Platform Admin Cross-Tenant Operations

When platform admins need to access all tenants (reports, dashboards):

```python
from src.middleware.tenant_context import TenantScopedSession
from src.core.config import get_settings

settings = get_settings()

# Platform admin doing cross-tenant report
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

### For Database Migrations

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

## Audit Logging

### Data Access Logs

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

### RLS Violation Logs

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

## Compliance Reporting

### Available Reports

1. **User Access Report**: All data access by a specific user
2. **Tenant Security Report**: Security events, RLS violations, denied access
3. **Activity Summary**: Aggregated activity metrics

### API Endpoints

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

## SOC2 Compliance Mapping

| SOC2 Requirement | Implementation |
|-----------------|----------------|
| CC6.1 - Logical access security | RLS policies + RBAC |
| CC6.2 - Authorized access | Authentication + tenant context |
| CC6.3 - Access monitoring | DataAccessAuditLog |
| CC7.2 - Anomaly detection | RLSViolationLog + severity tracking |
| CC7.3 - Security events | Audit logging with severity levels |

## Testing RLS

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

## Troubleshooting

### "No rows returned when I expect data"

1. Check if `app.customer_id` is set correctly
2. Verify the data belongs to the current tenant
3. Check RLS policy with: `\dp tablename` in psql

### "RLS not enforcing"

1. Verify RLS is enabled: `SELECT relrowsecurity FROM pg_class WHERE relname = 'tablename';`
2. Check if FORCE ROW LEVEL SECURITY is set
3. Verify the session user isn't a superuser (superusers bypass RLS)

### "Admin operations failing"

For admin operations that need all-tenant access:
1. Don't set `app.customer_id` (leave it NULL)
2. Or use a database superuser connection for migrations

## Security Considerations

1. **Never expose raw SQL execution** to users - RLS only protects properly parameterized queries
2. **Always validate tenant context** in application layer as defense-in-depth
3. **Monitor RLS violations** - they may indicate bugs or attack attempts
4. **Audit log retention** - Keep logs for compliance period (default: 7 years)
5. **Test RLS policies** after schema changes

