# Security Quick Start Guide

> **TL;DR**: Every database query is automatically filtered by tenant. Platform admins can view other tenants using special headers. All access is logged to `data_access_audit_log`.

## The 4 Rules

### 1. Every User Belongs to a Tenant
```
Your User → customer_id: "eliza"
           ↓
All your queries automatically filter: WHERE customer_id = 'eliza'
```

### 2. RLS Enforces Isolation at Database Level
Even if you write raw SQL, PostgreSQL Row Level Security ensures you only see your tenant's data:

```sql
-- This query:
SELECT * FROM documents;

-- Becomes (automatically):
SELECT * FROM documents WHERE customer_id = 'eliza';
```

### 3. Platform Admins Need Explicit Headers
Platform admins (`platform:admin` permission) can access other tenants, but must be explicit:

| Want to... | Use Header | Result |
|------------|------------|--------|
| View as Acme tenant | `X-View-As-Tenant: acme` | See only Acme's data |
| Run cross-tenant report | `X-Cross-Tenant-Access: true` | See ALL tenants' data |
| Normal operation | (no headers) | See only your tenant (eliza) |

### 4. Every API Request is Logged (NEW)
The middleware automatically logs every authenticated API request:

```sql
-- What gets logged:
SELECT * FROM data_access_audit_log WHERE api_endpoint = '/api/v1/documents';

-- Shows:
--  action  | customer_id | user_id | outcome | duration_ms | api_endpoint
-- ---------+-------------+---------+---------+-------------+------------------
--  SELECT  | eliza       | 2       | success | 45          | /api/v1/documents
```

---

## Quick Reference

### For Regular API Calls (No Action Needed)
```typescript
// Just make the call - tenant filtering is automatic
const response = await axios.get('/api/v1/documents');
// Returns only YOUR tenant's documents
```

### For Platform Admin - View As Tenant
```typescript
// View as specific tenant
const response = await axios.get('/api/v1/documents', {
  headers: { 'X-View-As-Tenant': 'acme' }
});
// Returns Acme's documents
```

### For Platform Admin - Cross-Tenant Reports
```typescript
// View all tenants (reporting only)
const response = await axios.get('/api/v1/compliance/reports', {
  headers: { 'X-Cross-Tenant-Access': 'true' }
});
// Returns documents from ALL tenants
```

---

## Visual Indicators

When viewing as another tenant or in cross-tenant mode, banners appear:

| Mode | Banner Color | Message |
|------|--------------|---------|
| **View As Tenant** | 🟠 Amber | "You are viewing as **Acme Corp**" |
| **Cross-Tenant** | 🟣 Purple | "Cross-Tenant Access Mode - viewing ALL tenants" |

---

## Common Questions

**Q: Do I need to add `customer_id` to my WHERE clauses?**
A: No! RLS handles it automatically. But you SHOULD still include it for clarity and belt-and-suspenders safety.

**Q: What happens if I try to access another tenant's data?**
A: You get an empty result set. RLS silently filters out rows you can't access.

**Q: How do I know what tenant I'm operating as?**
A: Check the `X-Tenant-ID` response header, or look for the banner in the UI.

**Q: Can I write data to another tenant?**
A: No. Even with cross-tenant access, writes are restricted to your own tenant.

**Q: How is my access being logged?**
A: The `TenantContextMiddleware` logs every authenticated request to `data_access_audit_log` with:
- Your `user_id` and `customer_id`
- The API endpoint and HTTP method (mapped to action)
- Request duration, IP address, user agent
- Outcome (success/denied/error)

**Q: Where does the tenant context come from?**
A: The flow is:
1. JWT token contains your `user_id`
2. Auth dependency decodes JWT and sets `request.state.customer_id` from user's tenant
3. Middleware reads `request.state` and sets PostgreSQL session variables
4. RLS uses these session variables to filter queries

---

## See Also

- [Test Summary](./TEST_SUMMARY.md) - Overview of all 56 security tests
- [Security for Dev Team](./security_for_dev_team.md) - Detailed implementation guide
- [Security Details for SOC2](./security_details_for_soc2.md) - Compliance documentation
- [Multi-Tenant RLS Spec](../multi-tenant-rls.md) - Full technical specification

