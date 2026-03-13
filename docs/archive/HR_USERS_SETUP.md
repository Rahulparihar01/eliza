# HR Users Setup Summary

## ✅ Completed Setup

### Created Role: `hr_user` (HR User)

A new role with **full access to all TALENT section features** has been created with the following permissions:

#### Permissions Granted:
- **`talent:*`** - All talent intelligence permissions
  - View talent analyses and results
  - Run talent intelligence analyses
  - Manage talent data and configurations
  - View analysis history

- **`connectors:*`** - All data connector permissions
  - View data connector configurations
  - Create and configure data connectors
  - Trigger and manage data syncs

- **`outreach:*`** - All candidate outreach permissions
  - View candidate outreach and engagement
  - Create and manage outreach campaigns
  - Create and edit email templates

### Created Users:

Three HR users have been created with the `hr_user` role:

| Email | Full Name | Role | Password |
|-------|-----------|------|----------|
| laura.sullivan@caylent.com | Laura Sullivan | hr_user | admin123 |
| lisa.cohrs@caylent.com | Lisa Cohrs | hr_user | admin123 |
| sofia.ferrari@caylent.com | Sofia Ferrari | hr_user | admin123 |

### Access Details:

**Login URL:** https://caylent-hr-intel.lhr.rocks/login

**Available Features (TALENT Section):**
- ✅ Data Connections - Configure and manage HR data sources
- ✅ Talent Intelligence - AI-powered talent analysis
- ✅ Analysis History - View past talent analyses
- ✅ Candidate Outreach - Manage candidate communications
- ✅ Email Templates - Create and edit outreach templates

## 🔒 Security Notes

1. **Default Password:** All users are set up with the password `admin123`. Consider having them change it on first login.

2. **Role Hierarchy:** The `hr_user` role has `hierarchy_level=2`, similar to the `analyst` role, but with TALENT-specific permissions instead of general document permissions.

3. **Customer Scope:** All users are scoped to the `caylent` customer.

## 🛠️ Managing HR Users

### Add More HR Users

To create additional HR users with the same permissions:

```bash
docker exec docker-app-1 python << 'PYTHON'
import sys
sys.path.append('/app')
from src.models.database import get_db, init_database
from src.models.auth import Role, User

init_database()
with next(get_db()) as db:
    # Get the hr_user role
    role = db.query(Role).filter(Role.name == "hr_user").first()
    
    # Create new user
    user = User(
        email="new.user@caylent.com",
        username="new_user",
        full_name="New User",
        customer_id="caylent",
        is_active=True,
        is_superuser=False
    )
    user.set_password("admin123")
    user.roles = [role]
    
    db.add(user)
    db.commit()
    print(f"Created user: {user.email}")
PYTHON
```

### Reset a User's Password

```bash
docker exec docker-app-1 python << 'PYTHON'
import sys
sys.path.append('/app')
from src.models.database import get_db, init_database
from src.models.auth import User

init_database()
with next(get_db()) as db:
    user = db.query(User).filter(User.email == "laura.sullivan@caylent.com").first()
    if user:
        user.set_password("newpassword123")
        db.commit()
        print(f"Password reset for {user.email}")
PYTHON
```

### View All HR Users

```bash
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
SELECT u.email, u.full_name, u.is_active, u.created_at 
FROM users u 
JOIN user_roles ur ON u.id = ur.user_id 
JOIN roles r ON ur.role_id = r.id 
WHERE r.name = 'hr_user' 
ORDER BY u.email;
"
```

### Deactivate a User (without deleting)

```bash
docker exec docker-app-1 python << 'PYTHON'
import sys
sys.path.append('/app')
from src.models.database import get_db, init_database
from src.models.auth import User

init_database()
with next(get_db()) as db:
    user = db.query(User).filter(User.email == "user@caylent.com").first()
    if user:
        user.is_active = False
        db.commit()
        print(f"Deactivated user: {user.email}")
PYTHON
```

## 📊 Verification

You can verify the setup with these queries:

```bash
# Check users and their roles
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
SELECT u.email, u.full_name, r.name as role, r.display_name 
FROM users u 
JOIN user_roles ur ON u.id = ur.user_id 
JOIN roles r ON ur.role_id = r.id 
WHERE u.email LIKE '%@caylent.com' 
ORDER BY u.email;
"

# Check hr_user role permissions
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
SELECT r.name as role_name, p.name as permission, p.description 
FROM roles r 
JOIN role_permissions rp ON r.id = rp.role_id 
JOIN permissions p ON rp.permission_id = p.id 
WHERE r.name = 'hr_user' 
ORDER BY p.name;
"
```

## 🚀 Testing Login

Test a user login via API:

```bash
curl -X POST http://localhost:5001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "laura.sullivan@caylent.com", "password": "admin123"}' | jq
```

Or test via the public URL:

```bash
curl -X POST https://api-caylent-hr-intel.lhr.rocks/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "laura.sullivan@caylent.com", "password": "admin123"}' | jq
```

## 📝 Notes

- The `hr_user` role uses wildcard permissions (`talent:*`, `connectors:*`, `outreach:*`) which automatically grant all actions for these resources.
- Users with this role will **only** see and access the TALENT section of the application.
- They do **not** have access to:
  - Business Intelligence
  - Document Management
  - System Administration
  - User Management
  - AI Model Configuration

## 🔄 Script Location

The user creation script is saved at:
`/Users/scottgay/Documents/Eliza/eliza-platform/scripts/create_hr_users.py`

You can modify and re-run it as needed.

