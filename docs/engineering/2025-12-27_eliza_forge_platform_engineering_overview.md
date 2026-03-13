# Eliza Forge Platform Architecture

**Version:** 1.0  
**Last Updated:** December 27, 2025  
**Classification:** Internal Engineering Documentation

---

## Table of Contents

1. [Introduction & Design Philosophy](#1-introduction--design-philosophy)
2. [Multi-Tenancy: The Foundation](#2-multi-tenancy-the-foundation)
3. [The Permission Stack](#3-the-permission-stack)
4. [Feature Allocation: Controlling What Tenants Can Access](#4-feature-allocation-controlling-what-tenants-can-access)
5. [Authentication & User Lifecycle](#5-authentication--user-lifecycle)
6. [Data Connections: Bringing External Data In](#6-data-connections-bringing-external-data-in)
7. [AI Provider Management: Shared Intelligence](#7-ai-provider-management-shared-intelligence)
8. [Audit Logging: Trust Through Transparency](#8-audit-logging-trust-through-transparency)
9. [Frontend Architecture](#9-frontend-architecture)
10. [Deployment & Initialization](#10-deployment--initialization)
11. [Quick Reference](#11-quick-reference)

---

## 1. Introduction & Design Philosophy

Eliza Forge is a multi-tenant AI enablement platform that serves two distinct user communities: **AI Assistant** capabilities for document intelligence and domain-specific analytics, and **AI Recruiter** capabilities for talent acquisition workflows. The platform is designed to be deployed either as a SaaS offering or as an on-premise solution for enterprise customers.

### Why These Architectural Choices Matter

When we set out to build Eliza Forge, we faced several competing requirements that shaped our fundamental architecture:

**Security First, Always.** Enterprise customers need ironclad guarantees that their data cannot leak to other tenants—even in the face of application bugs. This led us to embrace PostgreSQL Row Level Security (RLS) as our primary isolation mechanism, rather than relying solely on application-level filtering.

**Flexibility Without Fragility.** Different tenants have different needs. Some want access to every feature; others only need document intelligence. Our feature allocation system allows platform administrators to customize each tenant's experience without code changes.

**Trust Through Transparency.** SOC2 compliance requires comprehensive audit trails. Rather than bolting on logging as an afterthought, we designed audit capture into the middleware layer from day one.

**Developer Velocity.** Despite the security complexity, developers should be able to add new features without understanding every nuance of the permission system. The architecture provides sensible defaults and clear patterns to follow.

### Tech Stack Overview

| Layer | Technology | Why We Chose It |
|-------|------------|-----------------|
| Frontend | React 18, TypeScript, TailwindCSS | Type safety, modern component patterns, rapid styling |
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 | Async-first, excellent ORM, automatic API docs |
| Database | PostgreSQL 15 | RLS support, JSONB, mature ecosystem |
| Cache | Redis | Session storage, Celery broker, real-time features |
| Search | Elasticsearch | Vector embeddings, document indexing |
| Task Queue | Celery | Long-running AI operations, scheduled syncs |

---

## 2. Multi-Tenancy: The Foundation

The most critical architectural decision in Eliza Forge is how we isolate tenant data. We chose a **shared database with Row Level Security** model over alternatives like database-per-tenant or schema-per-tenant.

### Why Shared Database with RLS?

**Database-per-tenant** provides strong isolation but creates operational nightmares: migrations must run against potentially thousands of databases, connection pooling becomes complex, and costs scale linearly with tenant count.

**Schema-per-tenant** is a middle ground but still requires schema migrations across many targets and doesn't leverage PostgreSQL's native security features.

**Shared database with RLS** provides:
- Single migration target for schema changes
- Database-enforced isolation (not just application-level)
- Efficient resource utilization
- Platform admin can query across tenants when needed

### How RLS Works in Practice

Every tenant-scoped table includes a `customer_id` column. When a user authenticates, we set a PostgreSQL session variable with their tenant identifier:

```python
# Set during request middleware
db.execute(text("SET app.customer_id = :customer_id"), {"customer_id": user.customer_id})
```

RLS policies then automatically filter every query. Even if application code forgets a WHERE clause, the database refuses to return rows from other tenants:

```sql
-- Simplified policy pattern (actual implementation varies by table)
CREATE POLICY tenant_isolation ON documents USING (
    customer_id = current_setting('app.customer_id', true)
);
```

The `current_setting(..., true)` syntax returns NULL instead of erroring if the variable isn't set—a safety mechanism that causes queries to return zero rows rather than failing unexpectedly.

### Platform Admin Access

Platform administrators need to manage all tenants. Rather than exempting them from RLS entirely (which would be dangerous), we use additional session variables:

```python
# Platform admin viewing a specific tenant
SET app.customer_id = 'target-tenant';
SET app.is_platform_admin = 'true';

# Platform admin viewing all data (cross-tenant reporting)
SET app.cross_tenant_access = 'true';
```

The RLS policies check these flags, but critically, **all access is still logged**. A platform admin bypassing tenant isolation is recorded in the audit log with the reason for cross-tenant access.

### Tables Under RLS Protection

All business data tables have RLS enabled, including:
- Core entities: `users`, `roles`, `user_invites`
- Documents: `documents`, `document_chunks`
- Recruiter: `candidates`, `analysis_configs`, `email_templates`
- Reference checks: All reference-related tables
- Connectors: `data_connectors`, `connector_sync_logs`

The pattern is consistent: if a table has a `customer_id` column, it has RLS enabled.

---

## 3. The Permission Stack

Eliza Forge implements Role-Based Access Control (RBAC) with a hierarchical structure designed to balance security with usability.

### The Hierarchy: Platform → Tenant → User

```
┌─────────────────────────────────────────────────────────────────┐
│                      PLATFORM ADMIN                              │
│  The "superuser" of Eliza Forge. Can manage all tenants,        │
│  allocate features, and view cross-tenant data. Actions are     │
│  fully logged. This is NOT an unaudited backdoor.               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TENANT ADMIN                                │
│  Full control within their organization. Can manage users,      │
│  roles, and configurations—but only for features allocated      │
│  to their tenant.                                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TENANT USERS                                │
│  Editor: Can create and modify content                          │
│  Viewer: Read-only access                                       │
│  Custom: Tenant admins can create custom role combinations      │
└─────────────────────────────────────────────────────────────────┘
```

### Why 71 Granular Permissions?

Early designs used coarse permissions like "can_access_recruiter" or "is_admin." This proved insufficient as customers requested nuanced access control: "Our recruiters should be able to email candidates but not delete search configurations."

We adopted a `resource:action` naming convention that's both human-readable and machine-parseable:

| Permission | What It Controls |
|------------|-----------------|
| `recruiter:config:create` | Creating new talent search configurations |
| `recruiter:results:email` | Sending outreach emails to candidates |
| `assistant:documents:upload` | Uploading documents to the AI Assistant |
| `audit:export` | Exporting audit logs for compliance reporting |

This granularity allows tenant admins to craft precise roles. A "Junior Recruiter" role might have `recruiter:results:read` and `recruiter:results:email` but not `recruiter:config:delete`.

### Roles Are Tenant-Scoped

A critical design decision: **roles belong to tenants, not to the platform**. The same role name ("editor") can have different permissions in different tenants based on what features that tenant has allocated.

This means:
- Tenant A's "editor" role has document permissions
- Tenant B's "editor" role has recruiter permissions  
- Neither can affect the other

The uniqueness constraint is `(customer_id, name)`, not just `name`. This prevents the confusion of globally-shared roles while allowing familiar role names across tenants.

### Permission Enforcement: Defense in Depth

Permissions are checked at multiple layers:

1. **Frontend Navigation**: Items hidden if user lacks permission
2. **Frontend UI**: Buttons disabled, forms hidden
3. **Backend API**: FastAPI dependency injection validates permissions
4. **Database RLS**: Final safety net for data access

```python
# Backend enforcement example
@router.post("/documents")
async def upload_document(
    user: User = Depends(require_permission('assistant:documents:upload'))
):
    # If we reach here, user definitely has permission
    ...
```

This defense-in-depth approach means a frontend bug that shows a disabled button as enabled will still be caught by the backend. A backend bug that forgets a permission check will still be blocked by RLS if the user tries to access another tenant's data.

---

## 4. Feature Allocation: Controlling What Tenants Can Access

Not every tenant needs every feature. A recruiting firm might only use AI Recruiter; a document-heavy consultancy might only need AI Assistant. Feature allocation controls what capabilities are available to each tenant.

### The Feature Catalog

Platform features are defined centrally and allocated to tenants:

| Feature Key | Description | Default Allocation |
|-------------|-------------|-------------------|
| `ai_assistant` | Document upload, RAG Q&A, chat | Most tenants |
| `ai_recruiter` | Talent search, email outreach | Recruiter-focused tenants |
| `data_connections` | External data source integration | Advanced tenants |
| `audit` | Compliance and audit log access | Enterprise tenants |
| `labs_agents` | Experimental agent configuration | Beta testers |

### Why Feature Allocation Matters

Feature allocation serves multiple purposes:

**Commercial Flexibility**: Different pricing tiers can unlock different features without code changes.

**Complexity Management**: A tenant that doesn't use AI Recruiter shouldn't see recruiter-related navigation, permissions, or configuration options. This reduces cognitive load for their users.

**Permission Scoping**: When a tenant admin creates roles, they only see permissions for features they have access to. This prevents confusion ("Why is there a 'recruiter:config:create' permission when we don't have AI Recruiter?").

### How Allocation Affects Permissions

The relationship between features and permissions is defined in a mapping:

```python
FEATURE_PERMISSION_MAP = {
    'ai_assistant': ['assistant:*'],       # All assistant permissions
    'ai_recruiter': ['recruiter:*'],       # All recruiter permissions
    'data_connections': ['connections:*'], # All connection permissions
    # ... etc
}
```

When default roles are created for a new tenant, only permissions for allocated features are included. If a tenant doesn't have `ai_recruiter`, their admin role won't include `recruiter:config:create`—it simply doesn't exist in their permission universe.

### Enforcement Across the Stack

Feature allocation is enforced at:

1. **Tenant Creation**: Allocated features determine initial role permissions
2. **Role Editor UI**: Only shows permissions for allocated features
3. **Navigation**: Feature check before permission check
4. **API Endpoints**: Can optionally require both feature and permission

```typescript
// Frontend navigation filtering
const visibleItems = navItems.filter(item => {
  // First: does the tenant have this feature?
  if (item.feature && !user.allocated_features.includes(item.feature)) {
    return false;
  }
  // Second: does the user have permission?
  if (item.permission && !hasPermission(item.permission)) {
    return false;
  }
  return true;
});
```

---

## 5. Authentication & User Lifecycle

### The Login Flow

Authentication uses JWT tokens with a 15-minute access token lifetime and longer-lived refresh tokens. The token payload includes everything needed for authorization decisions:

```python
# JWT payload structure
{
    "sub": "user_id:123",
    "customer_id": "acme-corp",
    "permissions": ["assistant:access", "assistant:documents:read", ...],
    "allocated_features": ["ai_assistant", "ai_recruiter"],
    "is_platform_admin": false,
    "exp": 1735300800
}
```

Embedding permissions in the token means most authorization checks don't require database queries—improving performance for the common case.

### Multi-Tenant Users

A user can belong to multiple tenants. This is common for consultants who work with multiple clients, or for agency recruiters managing different company accounts.

The `user_tenant_memberships` table tracks which tenants a user can access:

```
User: alice@consulting.com
├── Membership: Acme Corp (default)
├── Membership: Beta Industries
└── Membership: Gamma LLC
```

On login, users authenticate against their default tenant. A tenant switcher in the UI allows jumping between organizations. Each switch issues a new JWT with the new tenant's context.

The first time a multi-tenant user logs in, we show a brief tutorial explaining how tenant switching works. After dismissal, a subtle info icon reminds them of the capability without being intrusive.

### User Invitations

New users join through an invitation flow:

1. Tenant admin creates invite (specifies email and role)
2. System generates unique token, sends email
3. Invitee clicks link, lands on acceptance page
4. **New user**: Sets password, account created, membership established
5. **Existing user**: Membership added to their account, redirected to login

For existing users, this means no password creation—they already have credentials. The acceptance flow simply adds them to the new tenant with the specified role.

### Tenant Deactivation

Platform admins can deactivate tenants (for non-payment, policy violations, etc.). Deactivation:

- Requires typing "DEACTIVATE" to confirm (preventing accidents)
- Requires a reason (logged for compliance)
- Immediately blocks all tenant users from accessing the platform
- Preserves all data (can be reactivated later)
- Displays a clear full-screen message to affected users

The middleware checks tenant status on every authenticated request:

```python
if not customer.is_active:
    raise HTTPException(403, detail="TENANT_DEACTIVATED")
```

The frontend intercepts this specific error code and shows the deactivation banner with instructions to contact support.

---

## 6. Data Connections: Bringing External Data In

The AI capabilities of Eliza Forge are powered by tenant data. Data connections allow tenants to integrate external sources.

### Supported Connectors

| Connector | Use Case |
|-----------|----------|
| PostgreSQL | Query databases for structured data |
| S3/GCS | Ingest documents from cloud storage |
| Greenhouse | Sync candidate data from ATS |

### Connection Lifecycle

1. **Configuration**: Tenant admin provides connection details
2. **Testing**: Platform validates connectivity before saving
3. **Sync**: Manual or scheduled data synchronization
4. **Processing**: Ingested data chunked, embedded, indexed

Connection credentials are encrypted at rest using envelope encryption. Only the connection service can decrypt them at runtime.

### Why Generic Permissions?

Early designs had connector-specific permissions (`connections:postgresql:create`, `connections:s3:sync`). This proved overly complex—a tenant admin who can configure PostgreSQL connections should generally be able to configure any connector type.

We simplified to generic CRUD permissions:
- `connections:read` - View configured connections
- `connections:create` - Add new connections  
- `connections:test` - Validate connectivity
- `connections:sync` - Trigger data synchronization

This reflects the reality that connector management is a single administrative function, not multiple distinct capabilities.

---

## 7. AI Provider Management: Shared Intelligence

AI providers (OpenAI, Anthropic, Azure OpenAI) power the platform's intelligence features. Managing these configurations across many tenants presented a design challenge.

### The Problem: API Key Management at Scale

If every tenant must configure their own AI provider, onboarding friction is high. But if we use a single platform-wide provider, we can't offer tenant-specific customization or cost tracking.

### The Solution: Tiered Provider Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│              PLATFORM LEVEL (customer_id = 'platform')          │
│  Global Providers      │  Selectively Shared Providers         │
│  Auto-available to     │  Platform admin chooses which         │
│  ALL tenants           │  tenants receive access               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      TENANT LEVEL                                │
│  Tenant-Owned          │  Received Shared                       │
│  Full control          │  Read-only, can toggle on/off         │
└─────────────────────────────────────────────────────────────────┘
```

### How It Works

**Platform-level providers** are owned by a special `platform` customer ID. The platform admin creates these and decides their sharing scope:

- **Global**: Automatically available to every tenant. Good for a "default" model everyone should have access to.
- **Selective**: Shared with specific tenants via the tenant management UI. Good for premium models allocated to enterprise customers.

**Tenant-level providers** are owned by individual tenants. Tenant admins can:
- Create their own providers (perhaps with their own API keys for cost tracking)
- Enable/disable shared providers they've received
- **Not** modify or delete shared providers

This design achieves:
- **Low friction onboarding**: New tenants immediately have working AI via global providers
- **Customization**: Enterprise tenants can add their own keys
- **Cost flexibility**: Tenants can bring their own API keys for billing isolation
- **Administrative efficiency**: Platform admin manages common configurations once

---

## 8. Audit Logging: Trust Through Transparency

Comprehensive audit logging is essential for SOC2 compliance and building customer trust. Our approach: capture everything, query what you need.

### What Gets Logged

| Category | Events | Severity |
|----------|--------|----------|
| Authentication | Login, logout, failed attempts, password changes | HIGH |
| Data Access | Document views, searches, downloads | INFO |
| Data Modification | Creates, updates, deletes | WARNING |
| Admin Actions | User invites, role changes, permission grants | HIGH |
| Platform Admin | Tenant operations, feature allocation | CRITICAL |

### Non-Blocking Audit Capture

Early implementations logged synchronously, which slowed down API responses. We moved to background task logging:

```python
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    
    # Fire-and-forget audit logging
    background_tasks.add_task(
        audit_service.log_event,
        action=f"{request.method} {request.url.path}",
        user_id=user_id,
        customer_id=customer_id,
        # ... additional context
    )
    
    return response
```

This ensures audit logging never impacts user experience while maintaining complete capture.

### Query Capabilities

Audit logs support:
- **Filtering**: By user, tenant, action type, time range, severity
- **Export**: CSV/JSON for compliance reporting
- **Cross-tenant**: Platform admins can query across all tenants

The `audit:read`, `audit:filter`, and `audit:export` permissions control access to these capabilities.

### Retention and Compliance

Audit logs are retained according to configurable policies (default: 2 years). For SOC2:
- All authentication events captured
- Data access tracked at record level
- Admin actions logged with elevated severity
- Tenant deactivations include documented reasons

---

## 9. Frontend Architecture

### State Management with Zustand

We chose Zustand over Redux for its simplicity and excellent TypeScript support. The auth store manages:

```typescript
interface AuthState {
  user: User | null;
  accessToken: string | null;
  
  // Computed helpers
  isAuthenticated: boolean;
  hasMultipleTenants: boolean;
  
  // Actions
  login: (credentials) => Promise<void>;
  logout: () => void;
  switchTenant: (customerId) => Promise<void>;
  hasPermission: (permission: string) => boolean;
  hasFeature: (feature: string) => boolean;
}
```

### Permission and Feature Hooks

Consistent access patterns through custom hooks:

```typescript
// Component can check permissions
const canUpload = usePermission('assistant:documents:upload');

// Component can check feature allocation
const hasRecruiter = useFeature('ai_recruiter');

// Combined for navigation/conditional rendering
if (canUpload && hasRecruiter) {
  // Show recruiter document upload
}
```

### Navigation Filtering

The navigation component applies a two-stage filter:

1. **Feature check**: Does the tenant have access to this feature area?
2. **Permission check**: Does the user's role grant this specific permission?

This means:
- Tenant without AI Recruiter: Recruiter nav section completely hidden
- Tenant with AI Recruiter, user without permissions: Section visible but items hidden/disabled

Section headers automatically hide when all their children are filtered out, preventing empty "AI Recruiter" headers for users without any recruiter permissions.

### API Integration

We use TanStack Query (React Query) for server state and Orval for API client generation from our OpenAPI spec. This provides:
- Type-safe API calls
- Automatic caching and invalidation
- Consistent loading/error states
- Generated types matching backend schemas

---

## 10. Deployment & Initialization

### Startup Sequence

The container startup follows a precise sequence:

```
1. Wait for PostgreSQL
   └── Health check with pg_isready
   
2. Run Alembic Migrations
   └── Creates/updates schema, permissions, RLS policies
   
3. Initialize Default Tenant
   └── Creates customer, admin user, role assignments
   
4. Start FastAPI Application
   └── uvicorn with configured workers
```

Step 3 (tenant initialization) is idempotent—running it multiple times won't create duplicates or errors. This allows containers to restart safely.

### Environment Configuration

| Variable | Purpose | Notes |
|----------|---------|-------|
| `DATABASE_URL` | PostgreSQL connection | Required |
| `CUSTOMER_ID` | Initial tenant identifier | Default: `eliza` |
| `ADMIN_EMAIL` | Platform admin email | Used for initial login |
| `JWT_SECRET_KEY` | Token signing | Must be secure in production |
| `RUN_MIGRATIONS` | Auto-run on startup | Set `true` for app container only |

**Important**: Only one container should run migrations (`RUN_MIGRATIONS=true`). In multi-container deployments, set this only on the primary app container to prevent race conditions.

### Migration Philosophy

Migrations use idempotent patterns throughout:

```python
# Safe to run multiple times
CREATE TABLE IF NOT EXISTS ...
CREATE INDEX IF NOT EXISTS ...
INSERT ... ON CONFLICT DO NOTHING
```

This allows migrations to be re-run safely during troubleshooting without causing duplicate constraint errors.

---

## 11. Quick Reference

### Permission Naming Convention

```
resource:sub_resource:action

Examples:
  assistant:documents:upload
  recruiter:config:create
  admin:settings:update
```

### Role Hierarchy Summary

| Role | Scope | Can Manage |
|------|-------|------------|
| Platform Admin | All tenants | Everything |
| Tenant Admin | Single tenant | Users, roles, configurations |
| Editor | Single tenant | Content within permissions |
| Viewer | Single tenant | Read-only |

### Feature → Permission Mapping

| Feature | Permission Prefix |
|---------|------------------|
| AI Assistant | `assistant:*` |
| AI Recruiter | `recruiter:*` |
| Data Connections | `connections:*` |
| Administration | `admin:*`, `users:*`, `roles:*`, `invites:*` |
| Audit | `audit:*` |
| Labs | `labs:*` |

### Adding a New Feature Checklist

When extending the platform:

1. ☐ Add feature to `platform_features` table
2. ☐ Create permissions (follow naming convention)
3. ☐ Update `FEATURE_PERMISSION_MAP`
4. ☐ Add RLS policy if new tables have `customer_id`
5. ☐ Add `require_permission()` to API routes
6. ☐ Add feature/permission checks to frontend navigation
7. ☐ Update default role creation logic if needed
8. ☐ Add audit logging for sensitive operations

### Key Database Relationships

```
customers (tenants)
    ├── users (belong to tenant)
    ├── roles (scoped to tenant)
    └── [all business data]

permissions (global, shared)
    └── role_permissions → links to tenant roles

user_tenant_memberships
    └── allows user in multiple tenants
```

---

*Document maintained by the Eliza Engineering Team.*
