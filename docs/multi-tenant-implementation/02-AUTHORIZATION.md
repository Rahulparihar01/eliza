# Authorization System

## ✅ **COMPLETED**

### **Permissions Added**

#### **File:** `scripts/init_rbac_data.py`

#### **New Permissions:**

```python
# Business Intelligence
("bi:read", "business_intelligence", "read", "View BI questions and answers"),
("bi:write", "business_intelligence", "write", "Submit BI questions"),
("bi:admin", "business_intelligence", "admin", "Manage BI system"),

# HR Data Access (Company-Scoped)
("hr:read:company:*", "hr_data", "read", "Read HR data from ALL companies (wildcard)"),
("hr:read:company:caylent", "hr_data", "read", "Read HR data from Caylent"),
("hr:read:company:eliza", "hr_data", "read", "Read HR data from Eliza"),

# Settings Management
("settings:read", "settings", "read", "View system settings"),
("settings:write", "settings", "write", "Modify system settings"),
```

### **Permission Format**

Company-scoped permissions use the format:
```
hr:read:company:{company_id}
```

Examples:
- `hr:read:company:*` - Wildcard (access all companies)
- `hr:read:company:caylent` - Access Caylent only
- `hr:read:company:eliza` - Access Eliza only

### **Role Assignments**

| Role | BI Permissions | HR Access | Settings |
|------|----------------|-----------|----------|
| **super_admin** | All | `hr:read:company:*` (wildcard) | Read + Write |
| **admin** | Read + Write + Admin | `hr:read:company:*` (wildcard) | Read + Write |
| **manager** | Read + Write | `hr:read:company:caylent` | Read |
| **analyst** | Read + Write | `hr:read:company:caylent` | None |
| **viewer** | Read only | None | None |

### **Authorization Middleware**

#### **File:** `src/middleware/authorization.py`

#### **New Methods:**

##### **1. `check_company_access(user, company_id)`**
```python
def check_company_access(self, user: CurrentUserContext, company_id: str, 
                         allow_superuser: bool = True) -> bool:
    """
    Check if user has permission to access a specific company's HR data.
    
    Returns True if:
    - User is superuser (if allow_superuser=True)
    - User has wildcard permission: hr:read:company:*
    - User has specific permission: hr:read:company:{company_id}
    """
```

**Logic:**
1. Check if user is superuser → Allow
2. Check for wildcard `hr:read:company:*` → Allow
3. Check for specific `hr:read:company:{company_id}` → Allow
4. Otherwise → Deny

##### **2. `require_company_access(company_id_param)`**
```python
def require_company_access(self, company_id_param: str = "company_hr_dataset"):
    """
    FastAPI dependency that enforces company access.
    
    Usage:
        @router.post("/questions")
        async def submit_question(
            request: Request,
            current_user = Depends(auth_middleware.require_company_access())
        ):
            company_id = request.query_params.get("company_hr_dataset")
            # User is authorized to access this company
    """
```

**Features:**
- Extracts `company_id` from query or path params
- Validates user has access via `check_company_access()`
- Logs audit event on denial
- Raises `HTTPException(403)` if unauthorized

### **Audit Logging**

All authorization denials are logged:
```python
{
    "action": "PERMISSION_DENIED",
    "user_id": 123,
    "resource_type": "company_hr_data",
    "resource_id": "caylent",
    "required_permission": "hr:read:company:caylent",
    "user_customer_id": "eliza",
    "target_company_id": "caylent",
    "severity": "HIGH"
}
```

### **Usage Examples**

#### **Check Access Programmatically:**
```python
if auth_middleware.check_company_access(current_user, "caylent"):
    # User can access Caylent data
    pass
```

#### **Protect Endpoint:**
```python
@router.get("/hr/data")
async def get_hr_data(
    company_id: str,
    current_user = Depends(auth_middleware.require_company_access("company_id"))
):
    # Only executes if user has access to company_id
    return query_hr_data(company_id)
```

### **Security Properties**

✅ **Least Privilege**: Users only get access to explicitly granted companies  
✅ **Audit Trail**: All access attempts logged  
✅ **Fail Secure**: Denies by default if permission not found  
✅ **Granular Control**: Per-company permissions  
✅ **Wildcard Support**: Admins can access all companies  

## 🔒 **Access Control Matrix**

| User Role | Own Org | Other Orgs | Wildcard |
|-----------|---------|------------|----------|
| super_admin | ✅ | ✅ | ✅ |
| admin | ✅ | ✅ | ✅ |
| manager | ✅ | ❌ | ❌ |
| analyst | ✅ | ❌ | ❌ |
| viewer | ❌ | ❌ | ❌ |

*Viewer role cannot access HR data at all, only view BI questions*

