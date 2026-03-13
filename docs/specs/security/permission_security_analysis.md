# Permission Security Analysis

> **TL;DR**: The `platform:admin` permission cannot be spoofed. Permissions are fetched from the database after JWT validation, not from the token itself. All access is logged.

**Analysis Date**: December 26, 2025  
**Reviewed By**: Security Team

---

## Executive Summary

This document analyzes the security of the permission system, specifically addressing the question: **"Can someone spoof `platform:admin` permissions?"**

**Conclusion**: No. The system implements multiple layers of defense that prevent permission spoofing.

---

## Authentication & Authorization Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         REQUEST AUTHENTICATION FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Client sends request with JWT token in Authorization header             │
│                           │                                                 │
│                           ▼                                                 │
│  2. JWT signature verified using server-side secret key                     │
│     (If modified → signature invalid → 401 Unauthorized)                    │
│                           │                                                 │
│                           ▼                                                 │
│  3. Extract user_id from validated JWT payload                              │
│                           │                                                 │
│                           ▼                                                 │
│  4. Fetch User from DATABASE (not from token)                               │
│                           │                                                 │
│                           ▼                                                 │
│  5. Load User's Roles from DATABASE                                         │
│                           │                                                 │
│                           ▼                                                 │
│  6. Load Permissions from Role → Permission relationships in DATABASE       │
│                           │                                                 │
│                           ▼                                                 │
│  7. Build CurrentUserContext with permissions list                          │
│                           │                                                 │
│                           ▼                                                 │
│  8. Permission check: has_permission('platform:admin') ?                    │
│                           │                                                 │
│                     ┌─────┴─────┐                                           │
│                     │           │                                           │
│                   Yes           No                                          │
│                     │           │                                           │
│                     ▼           ▼                                           │
│              Access Granted   403 Forbidden                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Controls

### 1. JWT Token Signature Verification

**Location**: `src/services/auth_service.py:183-186`

```python
async def verify_token(self, token: str) -> Dict[str, Any]:
    payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
```

**Protection**: 
- JWT tokens are cryptographically signed using HMAC-SHA256 (HS256)
- Any modification to the token payload invalidates the signature
- Verification uses a server-side secret key (not exposed to clients)

**Attack Mitigation**:
| Attack | Result |
|--------|--------|
| Modify payload to add permissions | Signature verification fails → 401 |
| Create token without secret | Invalid signature → 401 |
| Replay old token | Session validation fails (if expired/revoked) |

### 2. Database-Backed Permissions

**Location**: `src/middleware/authorization.py:558-598`

```python
def _build_current_user_context(self, user: User, current_session_token: str | None):
    permissions = user.get_permissions()  # FROM DATABASE
    return CurrentUserContext(
        permissions=permissions,
        ...
    )
```

**Protection**:
- Permissions are **never stored in the JWT token**
- After JWT validation, permissions are fetched fresh from the database
- User → Roles → Permissions chain is traversed server-side

**Attack Mitigation**:
| Attack | Result |
|--------|--------|
| Claim permissions in JWT | Ignored - permissions fetched from DB |
| Modify cached permissions | No client-side cache to modify |

### 3. Permission Hierarchy in Database

**Location**: `src/models/auth.py:146-151, 262-274`

```python
# User model
def get_permissions(self) -> List[str]:
    permissions = set()
    for role in self.roles:
        permissions.update(role.get_permissions())
    return list(permissions)

# Role model  
def get_permissions(self) -> List[str]:
    permissions = set()
    for perm in self.permissions:  # From role_permissions table
        permissions.add(perm.name)
    if self.parent_role:
        permissions.update(self.parent_role.get_permissions())
    return list(permissions)
```

**Protection**:
- Permissions are linked via database relationships
- Adding `platform:admin` requires:
  1. Access to the database
  2. Insert into `role_permissions` linking a role to the `platform:admin` permission
  3. Assign that role to the user via `user_roles`

### 4. Backend Permission Enforcement

**Location**: `src/middleware/authorization.py:159-222`

```python
def require_permission(self, permission: str, ...):
    async def permission_checker(request, current_user):
        has_permission = await self._check_permission_with_context(
            current_user, permission, context, scope
        )
        if not has_permission:
            raise HTTPException(status_code=403, detail=f"Permission required: {permission}")
```

**Protection**:
- Every protected API endpoint validates permissions server-side
- Frontend permission checks are for UX only (hiding/showing UI elements)
- Backend is the source of truth

### 5. Audit Logging

**Location**: `src/middleware/authorization.py:201-214`

```python
if not has_permission:
    await audit_service.log_event(
        AuditAction.PERMISSION_DENIED,
        user_id=current_user.user_id,
        severity=AuditSeverity.HIGH,
        additional_context={
            "required_permission": permission,
            "endpoint": str(request.url),
        }
    )
```

**Protection**:
- All permission denials are logged with HIGH severity
- Failed access attempts are traceable
- Enables anomaly detection for brute-force attempts

---

## Attack Vector Analysis

### ❌ Cannot Exploit

| Attack Vector | Why It Fails |
|--------------|--------------|
| **Modify JWT payload** | Signature verification fails |
| **Create fake JWT** | Requires server-side secret key |
| **Claim permissions in token** | Permissions fetched from DB, not token |
| **Bypass frontend checks** | Backend re-validates every request |
| **SQL injection** | SQLAlchemy uses parameterized queries |
| **Session hijacking** | Sessions tracked by IP/user-agent, short expiry |

### ⚠️ Requires Compromise

| Attack Vector | Required Access |
|--------------|-----------------|
| **Forge valid JWT** | JWT_SECRET_KEY (environment variable) |
| **Add role to user** | Direct database access |
| **Steal active session** | Network access + valid session token |
| **Modify permissions table** | Database admin credentials |

---

## Configuration Requirements

### Critical: JWT Secret Key

The JWT secret key **MUST** be:
- Unique per environment
- At least 256 bits (32 bytes) of entropy
- Stored securely (environment variable, not in code)
- Rotated periodically

**Generate a secure key**:
```bash
openssl rand -hex 32
```

**Set in environment**:
```bash
JWT_SECRET_KEY=your-256-bit-secure-random-key-here
```

**⚠️ WARNING**: The default value `"change-this-secret-key"` must NEVER be used in production.

### Database Security

- Database credentials must be secured
- Network access to database should be restricted
- Consider encryption at rest for sensitive tables
- Regular backups with access logging

---

## Security Layers Summary

```
┌────────────────────────────────────────────────────────────────┐
│ Layer 1: TRANSPORT                                              │
│ - TLS 1.3 encryption for all traffic                           │
│ - Certificate validation                                        │
├────────────────────────────────────────────────────────────────┤
│ Layer 2: AUTHENTICATION                                         │
│ - JWT signature verification                                    │
│ - Session validation against database                           │
│ - Token expiration enforcement                                  │
├────────────────────────────────────────────────────────────────┤
│ Layer 3: AUTHORIZATION                                          │
│ - Database-backed permissions                                   │
│ - Role-based access control (RBAC)                             │
│ - Per-endpoint permission requirements                          │
├────────────────────────────────────────────────────────────────┤
│ Layer 4: DATA ISOLATION                                         │
│ - PostgreSQL Row Level Security (RLS)                          │
│ - Tenant context enforcement                                    │
│ - Cross-tenant access requires explicit flags                   │
├────────────────────────────────────────────────────────────────┤
│ Layer 5: AUDIT                                                  │
│ - All API requests logged                                       │
│ - Permission denials tracked                                    │
│ - RLS violations recorded                                       │
│ - Cross-tenant access flagged                                   │
└────────────────────────────────────────────────────────────────┘
```

---

## Frontend vs Backend Permission Checks

| Aspect | Frontend | Backend |
|--------|----------|---------|
| **Purpose** | UX (hide/show elements) | Security enforcement |
| **Bypassable?** | Yes (dev tools) | No |
| **Data exposure** | None (just UI) | Actual data access |
| **Implementation** | `useAuth().hasPermission()` | `require_permission()` decorator |

**Important**: Frontend permission checks improve UX but provide **zero security**. All security is enforced backend.

---

## Recommendations

### Immediate Actions
1. ✅ Verify `JWT_SECRET_KEY` is set and secure in production
2. ✅ Ensure database credentials are not exposed
3. ✅ Enable audit log monitoring for `PERMISSION_DENIED` events

### Periodic Reviews
1. Review platform admin assignments quarterly
2. Rotate JWT secret key annually (or after any suspected compromise)
3. Audit `role_permissions` table for unexpected entries
4. Review RLS violation logs weekly

### Monitoring Alerts
Set up alerts for:
- Multiple `PERMISSION_DENIED` events from same user/IP
- Any `platform:admin` role assignments
- Cross-tenant access patterns
- RLS violations

---

## Conclusion

The permission system is secure against spoofing attacks because:

1. **JWT tokens are signed** - modifications invalidate the signature
2. **Permissions come from the database** - not from client-provided data
3. **Backend enforces all checks** - frontend is UX only
4. **All access is logged** - anomalies are detectable
5. **RLS provides defense-in-depth** - even raw SQL is tenant-scoped

The only way to gain `platform:admin` is through:
- Legitimate assignment by an existing platform admin
- Compromise of the database or JWT secret

---

## Related Documents

- [Security Quick Start](./security_quick_start.md)
- [Security for Dev Team](./security_for_dev_team.md)
- [Security Details for SOC2](./security_details_for_soc2.md)
- [Multi-Tenant RLS Specification](../multi-tenant-rls.md)

---

*Document Version: 1.0*  
*Last Updated: December 26, 2025*  
*Classification: Internal - Security Documentation*

