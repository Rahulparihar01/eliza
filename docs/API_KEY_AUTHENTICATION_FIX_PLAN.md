# API Key Authentication Fix Plan

## Current Status: Authentication Failing at Context Building

### Root Cause Analysis

**Problem:** API key authentication fails with 500 error when building `CurrentUserContext`

**Location:** `src/middleware/authorization.py` line 546

**Error Chain:**
1. API key is validated successfully ✅
2. User object is fetched from database ✅
3. Relationships (`roles`, `sessions`) are eagerly loaded ✅
4. User is expunged from session ✅
5. **FAILURE**: `_build_current_user_context()` tries to access `user.primary_role.name`
6. `primary_role` is a `@property` that needs to evaluate `self.roles`
7. After expunge, accessing properties that depend on relationships fails

**Code that's failing:**
```python
# Line 546 in src/middleware/authorization.py
primary_role = user.primary_role.name if user.primary_role else None
```

**Why it fails:**
```python
# In src/models/auth.py
@property
def primary_role(self) -> Optional['Role']:
    """Get user's primary (highest) role."""
    if not self.roles:  # This tries to access the relationship
        return None
    # ... rest of logic
```

After `db.expunge(user)`, the `user.roles` is already loaded in memory (we eagerly loaded it), but the `@property` method evaluation happens in a way that SQLAlchemy doesn't recognize the already-loaded data.

---

## Solution Plan

### Option 1: Evaluate Properties Before Expunge (RECOMMENDED)
**Pros:** Clean, maintains existing architecture
**Cons:** Requires careful pre-evaluation of all lazy properties

**Implementation:**
```python
# In src/services/api_key_service.py - authenticate_with_api_key()

# After loading user with relationships:
user = db.query(User).options(
    joinedload(User.roles),
    joinedload(User.sessions)
).filter(User.id == key.user_id).first()

if user and user.is_active:
    # FORCE evaluation of all properties BEFORE expunge
    _ = user.roles  # Already loaded
    _ = user.sessions  # Already loaded
    primary_role = user.primary_role  # Evaluate @property NOW
    permissions = user.get_permissions()  # Evaluate method NOW
    
    # Store computed values on the object
    user._cached_primary_role = primary_role
    user._cached_permissions = permissions
    
    db.expunge(user)
    return user
```

Then in `_build_current_user_context()`:
```python
def _build_current_user_context(self, user: User, current_session_token: str | None):
    roles = [role.name for role in user.roles]
    
    # Use cached values if available (for API key auth)
    if hasattr(user, '_cached_permissions'):
        permissions = user._cached_permissions
    else:
        permissions = user.get_permissions()
    
    if hasattr(user, '_cached_primary_role'):
        primary_role = user._cached_primary_role.name if user._cached_primary_role else None
    else:
        primary_role = user.primary_role.name if user.primary_role else None
    
    # ... rest of method
```

---

### Option 2: Don't Expunge, Use make_transient()
**Pros:** SQLAlchemy handles relationship access better
**Cons:** More complex state management

**Implementation:**
```python
from sqlalchemy.orm import make_transient

if user and user.is_active:
    _ = user.roles
    _ = user.sessions
    _ = user.primary_role
    
    # Make transient instead of expunge
    make_transient(user)
    return user
```

---

### Option 3: Return DTO Instead of ORM Object (MOST ROBUST)
**Pros:** Clean separation, no session issues ever
**Cons:** Larger refactor, need to create DTO class

**Implementation:**
```python
@dataclass
class AuthenticatedUser:
    """Detached user data for authentication"""
    id: int
    email: str
    username: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    customer_id: str
    department: Optional[str]
    team: Optional[str]
    roles: List[str]  # Role names
    permissions: List[str]
    primary_role_name: Optional[str]
    sessions: List[dict]
    created_at: datetime
    last_login_at: Optional[datetime]

# In authenticate_with_api_key():
if user and user.is_active:
    # Build DTO while session is active
    authenticated_user = AuthenticatedUser(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        customer_id=user.customer_id,
        department=user.department,
        team=user.team,
        roles=[role.name for role in user.roles],
        permissions=user.get_permissions(),
        primary_role_name=user.primary_role.name if user.primary_role else None,
        sessions=[{
            'session_token': s.session_token,
            'ip_address': s.ip_address,
            'user_agent': s.user_agent,
            'created_at': s.created_at,
            'last_activity_at': s.last_activity_at,
            'expires_at': s.expires_at
        } for s in user.sessions],
        created_at=user.created_at,
        last_login_at=user.last_login_at
    )
    return authenticated_user
```

---

## Recommended Solution: Option 1 (Quick Fix)

### Files to Modify:

#### 1. `src/services/api_key_service.py`
```python
# Line 290-296 (authenticate_with_api_key method)

if user and user.is_active:
    # Force load all relationships before expunging
    _ = user.roles
    _ = user.sessions
    
    # Pre-evaluate properties that depend on relationships
    primary_role = user.primary_role  # Evaluate NOW
    permissions = user.get_permissions()  # Evaluate NOW
    
    # Cache computed values on user object
    user._cached_primary_role = primary_role
    user._cached_permissions = permissions
    
    db.expunge(user)
    logger.info(f"Authenticated user {user.id} via API key {key.key_id}")
    return user
```

#### 2. `src/middleware/authorization.py`
```python
# Line 544-546 (_build_current_user_context method)

def _build_current_user_context(self, user: User, current_session_token: str | None):
    """Convert ORM user to DTO while session is active."""
    roles = [role.name for role in user.roles]
    
    # Use cached values if available (for expunged/API key users)
    if hasattr(user, '_cached_permissions'):
        permissions = user._cached_permissions
    else:
        permissions = user.get_permissions()
    
    if hasattr(user, '_cached_primary_role'):
        primary_role = user._cached_primary_role.name if user._cached_primary_role else None
    else:
        primary_role = user.primary_role.name if user.primary_role else None
    
    # ... rest of method unchanged
```

---

## Testing Plan

### 1. Unit Tests
```python
async def test_api_key_authentication():
    # Create API key
    api_key, full_key = await api_key_service.create_api_key(
        user_id=test_user.id,
        name="Test Key"
    )
    
    # Authenticate with API key
    user = await api_key_service.authenticate_with_api_key(full_key)
    assert user is not None
    assert user.id == test_user.id
    
    # Verify cached properties exist
    assert hasattr(user, '_cached_primary_role')
    assert hasattr(user, '_cached_permissions')
    
    # Verify they can be accessed after expunge
    assert isinstance(user._cached_permissions, list)
```

### 2. Integration Tests
```bash
# Test API key with /auth/me endpoint
curl -X GET http://localhost:5001/v1/auth/me \
  -H "Authorization: Bearer uak_xxxx"

# Expected: 200 OK with user data

# Test API key with protected endpoint
curl -X GET http://localhost:5001/api/v1/bi/questions \
  -H "Authorization: Bearer uak_xxxx"

# Expected: 200 OK with questions data

# Test invalid API key
curl -X GET http://localhost:5001/v1/auth/me \
  -H "Authorization: Bearer uak_invalid"

# Expected: 401 Unauthorized

# Test expired API key
curl -X GET http://localhost:5001/v1/auth/me \
  -H "Authorization: Bearer uak_expired"

# Expected: 401 Unauthorized
```

### 3. Load Tests
```bash
# Test 100 concurrent API key authentications
ab -n 1000 -c 100 \
  -H "Authorization: Bearer uak_xxxx" \
  http://localhost:5001/v1/auth/me

# Verify no memory leaks or session issues
```

---

## Additional Robustness Improvements

### 1. Add API Key Usage Limits
```python
# In UserAPIKey model
daily_request_limit = Column(Integer, nullable=True)
daily_request_count = Column(Integer, default=0)
last_request_date = Column(Date, nullable=True)

def check_rate_limit(self) -> bool:
    if self.daily_request_limit is None:
        return True
    
    today = date.today()
    if self.last_request_date != today:
        self.daily_request_count = 0
        self.last_request_date = today
    
    return self.daily_request_count < self.daily_request_limit
```

### 2. Add API Key Scopes/Permissions
```python
# In UserAPIKey model
scopes = Column(ARRAY(String), default=[])  # e.g., ["read:documents", "write:analyses"]

def has_scope(self, required_scope: str) -> bool:
    return required_scope in self.scopes or "*" in self.scopes
```

### 3. Add API Key IP Whitelist
```python
# In UserAPIKey model
allowed_ips = Column(ARRAY(String), nullable=True)

def is_ip_allowed(self, ip_address: str) -> bool:
    if not self.allowed_ips:
        return True
    return ip_address in self.allowed_ips
```

### 4. Add Automatic Key Rotation Warning
```python
def days_until_expiry(self) -> Optional[int]:
    if not self.expires_at:
        return None
    delta = self.expires_at - datetime.now(timezone.utc)
    return delta.days

def needs_rotation(self, warning_days: int = 30) -> bool:
    days = self.days_until_expiry()
    return days is not None and days <= warning_days
```

---

## Migration Required

### Add New Columns for Rate Limiting
```python
"""add api key rate limiting

Revision ID: g7h8i9j0k1l2
"""

def upgrade():
    op.add_column('user_api_keys', 
        sa.Column('daily_request_limit', sa.Integer(), nullable=True))
    op.add_column('user_api_keys', 
        sa.Column('daily_request_count', sa.Integer(), default=0))
    op.add_column('user_api_keys', 
        sa.Column('last_request_date', sa.Date(), nullable=True))
    op.add_column('user_api_keys', 
        sa.Column('scopes', sa.ARRAY(sa.String()), default=[]))
    op.add_column('user_api_keys', 
        sa.Column('allowed_ips', sa.ARRAY(sa.String()), nullable=True))

def downgrade():
    op.drop_column('user_api_keys', 'daily_request_limit')
    op.drop_column('user_api_keys', 'daily_request_count')
    op.drop_column('user_api_keys', 'last_request_date')
    op.drop_column('user_api_keys', 'scopes')
    op.drop_column('user_api_keys', 'allowed_ips')
```

---

## Security Best Practices

### 1. Key Storage
- ✅ Store only bcrypt hash, never plaintext
- ✅ Use `uak_` prefix for easy identification
- ✅ Generate cryptographically secure random keys
- ✅ Key shown only once at creation

### 2. Key Validation
- ✅ Check expiration before use
- ✅ Check if key is revoked
- ✅ Check if user is still active
- ✅ Track usage (request count, last used, IP)
- 🔲 Add rate limiting (TODO)
- 🔲 Add IP whitelist (TODO)
- 🔲 Add scope checking (TODO)

### 3. Audit Logging
- ✅ Log key creation
- ✅ Log key usage
- ✅ Log failed authentication attempts
- 🔲 Log rate limit exceeded (TODO)
- 🔲 Alert on suspicious activity (TODO)

### 4. Key Lifecycle
- ✅ Support expiration dates
- ✅ Support revocation
- ✅ Track last used date
- 🔲 Automatic rotation warnings (TODO)
- 🔲 Force rotation after N days (TODO)

---

## Implementation Priority

### P0 (Critical - Must Fix Now)
1. Fix `_build_current_user_context` to handle expunged users
2. Add property caching in `authenticate_with_api_key`
3. Test end-to-end authentication flow

### P1 (High - This Week)
1. Add comprehensive integration tests
2. Add rate limiting
3. Add API key scopes
4. Document MCP server integration

### P2 (Medium - This Month)
1. Add IP whitelist support
2. Add automatic rotation warnings
3. Add admin dashboard for key management
4. Add key usage analytics

### P3 (Low - Future)
1. Add key templates/presets
2. Add team-level keys
3. Add service account keys
4. Add key inheritance/delegation

---

## Success Criteria

- [x] API key creation works
- [x] API key listing works
- [ ] API key authentication works ← **FIXING NOW**
- [ ] API key works with all protected endpoints
- [ ] API key revocation works immediately
- [ ] API key expiration is enforced
- [ ] Usage statistics are tracked accurately
- [ ] No memory leaks or session issues
- [ ] Performance: <50ms overhead vs JWT
- [ ] Security: Passes penetration testing

---

## Rollout Plan

### Phase 1: Fix Core Authentication (Now)
- Implement Option 1 (caching fix)
- Test thoroughly
- Deploy to dev environment

### Phase 2: Add Tests (This Week)
- Unit tests
- Integration tests
- Load tests
- Security tests

### Phase 3: Enhance Features (Next Week)
- Rate limiting
- Scopes
- IP whitelist

### Phase 4: Documentation (Next Week)
- API documentation
- MCP server integration guide
- Security best practices guide
- Migration guide from JWT to API keys

---

## Estimated Timeline

- **Fix core auth**: 1 hour
- **Testing**: 2 hours
- **Rate limiting**: 3 hours
- **Scopes**: 3 hours
- **Documentation**: 4 hours
- **Total**: ~13 hours (~2 days)

---

## Next Immediate Steps

1. ✅ Identify root cause (DONE - line 546 in authorization.py)
2. 🔲 Implement caching fix in api_key_service.py
3. 🔲 Update _build_current_user_context in authorization.py
4. 🔲 Rebuild Docker container
5. 🔲 Test authentication
6. 🔲 Verify all endpoints work with API key
7. 🔲 Create comprehensive test suite

