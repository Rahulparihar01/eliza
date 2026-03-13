# RBAC & Authentication Architecture

## Overview

This document explains the Role-Based Access Control (RBAC) and authentication system architecture, ensuring clean and seamless enforcement across all features.

---

## 🔐 Authentication Flow

### 1. **Login Flow**
```
User → POST /v1/auth/login
  ↓
AuthService.authenticate_user()
  ↓
1. Validate credentials (password hash check)
2. Check account lockout status
3. Create user session in database
4. Generate JWT access token + refresh token
5. Log audit event (LOGIN_SUCCESS)
  ↓
Return: { access_token, refresh_token, user_profile }
```

### 2. **JWT Token Structure**
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "session_token": "unique_session_id",
  "customer_id": "customer_id",
  "role": "primary_role_name",
  "permissions": ["permission1", "permission2"],
  "iat": "issued_at_timestamp (UTC timezone-aware)",
  "exp": "expiration_timestamp (UTC timezone-aware)",
  "iss": "ai-enablement-platform"
}
```

**CRITICAL:** All datetime fields in JWTs and database use **timezone-aware UTC** (`datetime.now(timezone.utc)`).

### 3. **Token Verification Flow**
```
Request → Authorization: Bearer {token}
  ↓
AuthService.verify_token()
  ↓
1. Check session_cache (TTLCache, 5-min TTL)
   ├─ Cache HIT → Return cached payload (fast path)
   └─ Cache MISS → Continue to DB validation
2. Decode JWT and extract session_token
3. Query UserSession from database
4. Verify session is active and not expired
5. Update last_activity_at (if > 60 seconds old)
6. Cache the validated session
  ↓
Return: JWT payload with user context
```

**Session Caching:**
- **Cache Size:** 10,000 sessions
- **TTL:** 5 minutes (300 seconds)
- **Invalidation:** On logout, session is removed from cache
- **Performance:** Reduces DB hits by ~95% for active users

---

## 🛡️ Authorization (RBAC) Flow

### 1. **Middleware: AuthorizationMiddleware**

**Location:** `src/middleware/authorization.py`

**Responsibilities:**
- Extract and verify JWT from `Authorization` header
- Build `CurrentUserContext` DTO from JWT payload
- Enforce permission requirements
- Provide dependency injection for protected endpoints

### 2. **CurrentUserContext DTO**

**Purpose:** Safely pass user data between layers without SQLAlchemy `DetachedInstanceError`.

```python
@dataclass
class CurrentUserContext:
    user_id: int
    email: str
    username: str
    full_name: str
    customer_id: str
    role: str  # Primary role
    roles: List[str]  # All assigned roles
    permissions: List[str]  # All granted permissions
    is_superuser: bool
    is_active: bool
    last_login_at: Optional[datetime]
    created_at: datetime
```

**Key Benefits:**
- No database session required
- All data is serializable
- Prevents lazy-loading errors
- Consistent across all endpoints

### 3. **Permission Enforcement Patterns**

#### **Pattern A: Single Permission Required**
```python
@router.get("/resource")
async def get_resource(
    current_user = Depends(auth_middleware.require_permission("resource:read"))
):
    # Only users with "resource:read" permission can access
    ...
```

#### **Pattern B: Any of Multiple Permissions**
```python
@router.get("/resource")
async def get_resource(
    current_user = Depends(auth_middleware.require_any_permission([
        "resource:read",
        "resource:admin"
    ]))
):
    # Users with EITHER permission can access
    ...
```

#### **Pattern C: Using CurrentUserContext**
```python
from src.middleware.authorization import get_current_user
from src.core.auth_context import CurrentUserContext

@router.get("/resource")
async def get_resource(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    # Access user data:
    user_id = current_user.user_id
    customer_id = current_user.customer_id
    permissions = current_user.permissions
    
    # Manual permission check:
    if "resource:admin" not in current_user.permissions:
        raise HTTPException(403, "Insufficient permissions")
    
    ...
```

### 4. **Resource-Level Authorization**

**Use Case:** Check if user can access a specific resource (e.g., a document, question, etc.)

```python
# Check if user owns the resource or is superuser
if resource.user_id != current_user.user_id and not current_user.is_superuser:
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorized to access this resource"
    )
```

**Best Practice:** Always check resource ownership + superuser bypass.

---

## 📊 Database Models

### **User**
- `id`: Primary key
- `email`: Unique email
- `username`: Unique username
- `customer_id`: Foreign key to Customer
- `primary_role_id`: Foreign key to Role
- `is_superuser`: Boolean flag
- `is_active`: Boolean flag
- `last_login_at`: Timestamp (UTC timezone-aware)
- `created_at`, `updated_at`: Timestamps (UTC timezone-aware)

### **Role**
- `id`: Primary key
- `name`: Role name (e.g., "admin", "analyst", "viewer")
- `description`: Human-readable description
- `customer_id`: Foreign key to Customer (for customer-specific roles)

### **Permission**
- `id`: Primary key
- `name`: Permission name (e.g., "document:read", "bi:write")
- `resource_type`: Resource category (e.g., "document", "bi")
- `action`: Action type (e.g., "read", "write", "delete")

### **UserSession**
- `id`: Primary key
- `user_id`: Foreign key to User
- `session_token`: Unique session identifier (stored in JWT)
- `is_active`: Boolean flag
- `expires_at`: Expiration timestamp (UTC timezone-aware)
- `last_activity_at`: Last activity timestamp (UTC timezone-aware)
- `ip_address`: Client IP
- `user_agent`: Client user agent
- `device_fingerprint`: Device identifier for security

---

## 🔄 Session Management

### **Session Lifecycle**
1. **Creation:** On successful login
2. **Validation:** On every authenticated request (with caching)
3. **Renewal:** On token refresh
4. **Expiration:** After 8 hours (configurable)
5. **Termination:** On logout or manual revocation

### **Concurrent Session Limit**
- **Max Sessions Per User:** 3 (configurable)
- **Enforcement:** On login, oldest sessions are terminated if limit exceeded
- **Rationale:** Prevents credential sharing while allowing multiple devices

### **Session Cleanup**
- **Automatic:** Expired sessions are marked inactive
- **Manual:** Admins can revoke sessions via `/v1/users/{user_id}/sessions/{session_id}`

---

## 🚨 Security Features

### 1. **Account Lockout**
- **Trigger:** 5 failed login attempts
- **Duration:** 30 minutes
- **Audit:** All lockouts are logged to `UserAuditLog`

### 2. **Audit Logging**
- **All Actions Logged:**
  - Login success/failure
  - Logout
  - Permission checks (success/failure)
  - Resource access (create, read, update, delete)
  - Session creation/termination
- **Stored In:** `user_audit_log` table
- **Indexed By:** `user_id`, `action`, `created_at`

### 3. **Device Fingerprinting**
- **Purpose:** Track sessions by device
- **Hashed From:** User-Agent + Accept-Language + IP range
- **Use Case:** Detect suspicious activity (e.g., same session token from multiple devices)

---

## ⚠️ Common Pitfalls & Solutions

### **Issue 1: Timezone-Naive vs. Timezone-Aware Datetimes**

**Problem:**
```python
# BAD - Creates timezone-naive datetime
now = datetime.utcnow()

# Database has timezone-aware timestamps (TIMESTAMP WITH TIMEZONE)
# Comparison fails: "can't subtract offset-naive and offset-aware datetimes"
```

**Solution:**
```python
# GOOD - Creates timezone-aware UTC datetime
from datetime import datetime, timezone

now = datetime.now(timezone.utc)
```

**Rule:** **ALWAYS use `datetime.now(timezone.utc)` for all datetime creation in the backend.**

### **Issue 2: DetachedInstanceError**

**Problem:**
```python
# BAD - Passing SQLAlchemy model directly
def some_function(user: User):
    # Later, accessing user.customer_id fails if session is closed
    ...
```

**Solution:**
```python
# GOOD - Use CurrentUserContext DTO
def some_function(current_user: CurrentUserContext):
    customer_id = current_user.customer_id  # Always works
    ...
```

**Rule:** **Never pass SQLAlchemy models across function/layer boundaries. Always use DTOs.**

### **Issue 3: Permission Check Location**

**Problem:**
```python
# BAD - Permission check buried in business logic
def process_document(doc_id):
    # ... 50 lines later ...
    if user doesn't have permission:
        raise error
```

**Solution:**
```python
# GOOD - Permission check at API layer (FastAPI Depends)
@router.post("/documents")
async def upload_document(
    current_user = Depends(auth_middleware.require_permission("document:write"))
):
    # Permission already verified before function executes
    ...
```

**Rule:** **Enforce permissions at the API layer using FastAPI dependencies, not in service layers.**

---

## 🧪 Testing RBAC

### **Manual Testing Checklist**

1. **Login as different roles:**
   - Admin
   - Analyst
   - Viewer
   
2. **Verify each role can:**
   - Access allowed endpoints (200/201)
   - Not access forbidden endpoints (403)
   
3. **Verify resource ownership:**
   - User A cannot access User B's private resources
   - Admins/superusers can access all resources
   
4. **Verify session management:**
   - Logout invalidates token
   - Expired tokens are rejected
   - Concurrent session limits work

### **Example Test Cases**

```python
# Test: Admin can access all documents
response = client.get("/v1/documents", headers={"Authorization": f"Bearer {admin_token}"})
assert response.status_code == 200

# Test: Viewer cannot delete documents
response = client.delete("/v1/documents/123", headers={"Authorization": f"Bearer {viewer_token}"})
assert response.status_code == 403

# Test: User cannot access another user's BI question
response = client.get("/v1/bi/questions/abc", headers={"Authorization": f"Bearer {user_a_token}"})
assert response.status_code == 403  # If question belongs to User B
```

---

## 📚 Reference: Permission Naming Convention

**Format:** `{resource}:{action}`

**Examples:**
- `document:read` - View documents
- `document:write` - Upload/create documents
- `document:delete` - Delete documents
- `bi:read` - View BI questions and results
- `bi:write` - Submit new BI questions
- `bi:admin` - Manage all BI questions
- `user:manage` - Create/update/delete users
- `system:health` - Access system health metrics

**Wildcards:**
- `document:*` - All document permissions
- `*:read` - Read access to all resources
- `*:*` - Superuser (all permissions)

---

## 🚀 Adding New Protected Endpoints

**Step-by-Step Guide:**

1. **Define Permission**
   - Add permission to database (if new resource type)
   - Assign to appropriate roles

2. **Create Endpoint with Protection**
   ```python
   from src.middleware.authorization import get_current_user, require_permission
   from src.core.auth_context import CurrentUserContext
   
   @router.post("/new-resource")
   async def create_resource(
       request: ResourceCreateRequest,
       current_user: CurrentUserContext = Depends(get_current_user)
   ):
       # Check permission manually or use Depends(require_permission("resource:write"))
       if "resource:write" not in current_user.permissions:
           raise HTTPException(403, "Insufficient permissions")
       
       # Use current_user.user_id and current_user.customer_id
       resource = await service.create_resource(
           user_id=current_user.user_id,
           customer_id=current_user.customer_id,
           data=request
       )
       
       return resource
   ```

3. **Add Audit Logging (if needed)**
   ```python
   from src.services.audit_service import audit_service, AuditAction
   
   await audit_service.log_action(
       user_id=current_user.user_id,
       action=AuditAction.RESOURCE_CREATED,
       resource_type="new_resource",
       resource_id=resource.id,
       details={"name": resource.name}
   )
   ```

4. **Test RBAC**
   - Test with user having permission → 200
   - Test with user lacking permission → 403
   - Test with expired token → 401

---

## 🔧 Maintenance Commands

### **Revoke All User Sessions**
```python
from src.services.auth_service import auth_service

# Revoke all sessions for a user
auth_service.revoke_all_user_sessions(user_id=123)
```

### **Check Active Sessions**
```sql
SELECT 
    u.email,
    s.session_token,
    s.last_activity_at,
    s.expires_at,
    s.ip_address
FROM user_session s
JOIN "user" u ON s.user_id = u.id
WHERE s.is_active = true
ORDER BY s.last_activity_at DESC;
```

### **Audit Failed Login Attempts**
```sql
SELECT 
    user_id,
    details->>'email' as email,
    ip_address,
    COUNT(*) as failed_attempts,
    MAX(created_at) as last_attempt
FROM user_audit_log
WHERE action = 'login_failed'
  AND created_at > NOW() - INTERVAL '1 hour'
GROUP BY user_id, details->>'email', ip_address
HAVING COUNT(*) > 3
ORDER BY failed_attempts DESC;
```

---

## 📖 Summary

**Key Principles:**
1. ✅ Always use `datetime.now(timezone.utc)` for all datetime operations
2. ✅ Always use `CurrentUserContext` DTO, never pass SQLAlchemy models
3. ✅ Enforce permissions at API layer using FastAPI dependencies
4. ✅ Check resource ownership + superuser bypass for resource-level auth
5. ✅ Log all security-relevant actions to `UserAuditLog`
6. ✅ Use session caching to minimize database load
7. ✅ Never hardcode customer IDs or user IDs - always use `current_user`

**This architecture ensures:**
- 🔒 Secure authentication with JWT + session management
- 🛡️ Fine-grained RBAC with role and permission enforcement
- 📊 Complete audit trail for compliance
- ⚡ High performance with intelligent caching
- 🔧 Easy to maintain and extend


