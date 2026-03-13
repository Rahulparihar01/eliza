# Multi-Tenant Admin Management System
## Comprehensive Specification

**Version:** 1.0  
**Date:** December 23, 2025  
**Branch:** `feature/admin-tenant-management`

---

## Table of Contents
1. [Overview](#overview)
2. [User Hierarchy](#user-hierarchy)
3. [Feature Allocation System](#feature-allocation-system)
4. [Permission System](#permission-system)
5. [Data Models](#data-models)
6. [API Endpoints](#api-endpoints)
7. [Frontend Components](#frontend-components)
8. [User Flows](#user-flows)
9. [Implementation Phases](#implementation-phases)

---

## 1. Overview

### Purpose
Create a comprehensive multi-tenant administration system that allows:
1. **Platform Super Admins** (Eliza team) to create and manage tenants (customers) and allocate feature access
2. **Tenant Admins** to manage users, roles, and permissions within their own tenant

### Key Principles
- **Tenant Isolation**: All data is filtered by `customer_id` - tenants cannot see each other's data
- **Feature-Based Licensing**: Platform admins control which features each tenant can access
- **Flexible Permissions**: Tenant admins can create custom roles with granular permissions
- **Northflank-Style UX**: Permission management uses toggle chips for clean, intuitive experience

---

## 2. User Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLATFORM LEVEL (Eliza Team)                  │
├─────────────────────────────────────────────────────────────────┤
│  Platform Super Admin                                           │
│  ├── Can create/manage ALL tenants                              │
│  ├── Can allocate features to tenants                           │
│  ├── Can view all tenant data (for support)                     │
│  └── Can impersonate tenant admins (for troubleshooting)        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT LEVEL (Per Customer)                  │
├─────────────────────────────────────────────────────────────────┤
│  Tenant Admin (created during tenant setup)                     │
│  ├── Can manage users within their tenant                       │
│  ├── Can create/manage custom roles                             │
│  ├── Can assign roles to users                                  │
│  ├── Can configure tenant settings                              │
│  └── CANNOT access features not allocated by platform admin     │
│                                                                 │
│  Tenant Users                                                   │
│  ├── Permissions based on assigned roles                        │
│  ├── Can have multiple roles (permissions are unioned)          │
│  └── Limited to features allocated to their tenant              │
└─────────────────────────────────────────────────────────────────┘
```

### Default Roles (Created Automatically for Each Tenant)

| Role | Description | Default Permissions |
|------|-------------|---------------------|
| **Admin** | Full access within tenant | All permissions for allocated features |
| **Viewer** | Read-only access | Read permissions for allocated features |

Tenant admins can create additional custom roles as needed.

---

## 3. Feature Allocation System

### Platform-Level Features
The Platform Super Admin allocates features to each tenant. This controls what the tenant can access and what permissions are available.

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLATFORM FEATURES                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Documents &   │  │    Business     │  │     Talent      │ │
│  │   RAG System    │  │  Intelligence   │  │  Intelligence   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Data           │  │  AI Provider    │  │   Operations    │ │
│  │  Connectors     │  │  Configuration  │  │  Intelligence   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │     HR          │  │    Audit &      │  │   Advanced      │ │
│  │  Intelligence   │  │    Logging      │  │   Analytics     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Feature Allocation Matrix (Example)

| Feature | Tenant A (Enterprise) | Tenant B (Standard) | Tenant C (Basic) |
|---------|----------------------|---------------------|------------------|
| Documents & RAG | ✅ | ✅ | ✅ |
| Business Intelligence | ✅ | ✅ | ❌ |
| Talent Intelligence | ✅ | ❌ | ❌ |
| Data Connectors | ✅ | ✅ | ❌ |
| AI Provider Config | ✅ | ✅ | ✅ |
| Operations Intelligence | ✅ | ❌ | ❌ |
| HR Intelligence | ✅ | ✅ | ❌ |
| Audit & Logging | ✅ | ✅ | ✅ |
| Advanced Analytics | ✅ | ❌ | ❌ |

---

## 4. Permission System

### Permission Categories & Granular Permissions

Permissions are organized by category. Each category has specific actions that can be granted or revoked using toggle chips (Northflank-style).

```
┌─────────────────────────────────────────────────────────────────┐
│                    PERMISSION CATEGORIES                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📄 DOCUMENTS                                                   │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐   │
│  │ Create │ │  Read  │ │ Update │ │ Delete │ │ RAG Query  │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────────┘   │
│                                                                 │
│  🔌 DATA CONNECTORS                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐   │
│  │ Create │ │  Read  │ │ Update │ │ Delete │ │ Run Sync   │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────────┘   │
│  ┌──────────────┐                                              │
│  │ View Telemetry│                                              │
│  └──────────────┘                                              │
│                                                                 │
│  🤖 AI PROVIDERS                                                │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐   │
│  │ Create │ │  Read  │ │ Update │ │ Delete │ │ Test Keys  │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────────┘   │
│                                                                 │
│  📊 BUSINESS INTELLIGENCE                                       │
│  ┌────────┐ ┌────────┐ ┌────────────────┐ ┌────────────────┐  │
│  │  Read  │ │ Write  │ │ Run Queries    │ │ Export Reports │  │
│  └────────┘ └────────┘ └────────────────┘ └────────────────┘  │
│                                                                 │
│  🎯 TALENT INTELLIGENCE                                         │
│  ┌────────┐ ┌────────┐ ┌────────────────┐ ┌────────────────┐  │
│  │  Read  │ │ Write  │ │ Run Analysis   │ │ Manage Configs │  │
│  └────────┘ └────────┘ └────────────────┘ └────────────────┘  │
│                                                                 │
│  👥 USERS & ROLES                                               │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐   │
│  │ Create │ │  Read  │ │ Update │ │ Delete │ │Manage Roles│   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────────┘   │
│                                                                 │
│  ⚙️ SETTINGS                                                    │
│  ┌────────┐ ┌────────┐                                         │
│  │  Read  │ │ Write  │                                         │
│  └────────┘ └────────┘                                         │
│                                                                 │
│  📋 AUDIT LOGS                                                  │
│  ┌────────┐ ┌────────────┐                                     │
│  │  Read  │ │  Export    │                                     │
│  └────────┘ └────────────┘                                     │
│                                                                 │
│  🏢 HR INTELLIGENCE                                             │
│  ┌────────┐ ┌────────┐ ┌────────────────┐ ┌────────────────┐  │
│  │  Read  │ │ Write  │ │ Company Access │ │ Run Reports    │  │
│  └────────┘ └────────┘ └────────────────┘ └────────────────┘  │
│                                                                 │
│  🔧 OPERATIONS INTELLIGENCE                                     │
│  ┌────────┐ ┌────────┐ ┌────────────────┐                     │
│  │  Read  │ │ Write  │ │ Run Analysis   │                     │
│  └────────┘ └────────┘ └────────────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Permission Inheritance Rules

1. **User permissions = Union of all assigned role permissions**
   - If Role A has `documents:read` and Role B has `documents:write`, user gets both
   
2. **Feature allocation limits available permissions**
   - If tenant doesn't have Talent Intelligence allocated, those permissions aren't available
   
3. **Tenant Admin always has full access to allocated features**
   - Cannot be restricted below admin level

---

## 5. Data Models

### 5.1 Platform Feature Allocation

```python
# src/models/tenant_features.py

class PlatformFeature(Base):
    """Master list of all platform features"""
    __tablename__ = "platform_features"
    
    id = Column(Integer, primary_key=True)
    feature_key = Column(String(100), unique=True, nullable=False)  # e.g., "talent_intelligence"
    display_name = Column(String(255), nullable=False)  # e.g., "Talent Intelligence"
    description = Column(Text)
    category = Column(String(50))  # e.g., "intelligence", "data", "admin"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship to permissions this feature enables
    permissions = relationship("FeaturePermission", back_populates="feature")


class TenantFeatureAllocation(Base):
    """Features allocated to each tenant by platform admin"""
    __tablename__ = "tenant_feature_allocations"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    feature_id = Column(Integer, ForeignKey("platform_features.id"), nullable=False)
    is_enabled = Column(Boolean, default=True)
    allocated_by = Column(Integer, ForeignKey("users.id"))  # Platform admin who allocated
    allocated_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)  # Optional expiration
    
    # Usage limits (optional)
    usage_limit = Column(Integer, nullable=True)  # e.g., max documents, max analyses
    
    customer = relationship("Customer", back_populates="feature_allocations")
    feature = relationship("PlatformFeature")


class FeaturePermission(Base):
    """Permissions available within each feature"""
    __tablename__ = "feature_permissions"
    
    id = Column(Integer, primary_key=True)
    feature_id = Column(Integer, ForeignKey("platform_features.id"), nullable=False)
    permission_key = Column(String(100), nullable=False)  # e.g., "documents:create"
    display_name = Column(String(255), nullable=False)  # e.g., "Create Documents"
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    
    feature = relationship("PlatformFeature", back_populates="permissions")
    
    __table_args__ = (
        UniqueConstraint('feature_id', 'permission_key', name='uq_feature_permission'),
    )
```

### 5.2 Tenant Roles & Permissions

```python
# src/models/tenant_roles.py

class TenantRole(Base):
    """Roles defined within a tenant"""
    __tablename__ = "tenant_roles"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    role_name = Column(String(100), nullable=False)
    description = Column(Text)
    is_system_role = Column(Boolean, default=False)  # True for Admin, Viewer
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Relationships
    customer = relationship("Customer", back_populates="roles")
    permissions = relationship("TenantRolePermission", back_populates="role", cascade="all, delete-orphan")
    users = relationship("TenantUserRole", back_populates="role")
    
    __table_args__ = (
        UniqueConstraint('customer_id', 'role_name', name='uq_tenant_role_name'),
    )


class TenantRolePermission(Base):
    """Permissions assigned to a role"""
    __tablename__ = "tenant_role_permissions"
    
    id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("tenant_roles.id", ondelete="CASCADE"), nullable=False)
    permission_id = Column(Integer, ForeignKey("feature_permissions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    
    role = relationship("TenantRole", back_populates="permissions")
    permission = relationship("FeaturePermission")
    
    __table_args__ = (
        UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'),
    )


class TenantUserRole(Base):
    """Users assigned to roles within a tenant"""
    __tablename__ = "tenant_user_roles"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("tenant_roles.id", ondelete="CASCADE"), nullable=False)
    assigned_by = Column(Integer, ForeignKey("users.id"))
    assigned_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", foreign_keys=[user_id], back_populates="tenant_roles")
    role = relationship("TenantRole", back_populates="users")
    assigner = relationship("User", foreign_keys=[assigned_by])
    
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
    )
```

### 5.3 User Invite System

```python
# src/models/user_invites.py

class UserInvite(Base):
    """Invites for new users created by tenant admins"""
    __tablename__ = "user_invites"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    email = Column(String(255), nullable=False)
    invite_token = Column(String(255), unique=True, nullable=False)
    
    # Pre-assigned roles
    role_ids = Column(ARRAY(Integer))  # Roles to assign upon acceptance
    
    # Invite metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    
    # Status
    status = Column(String(20), default="pending")  # pending, accepted, expired, revoked
    accepted_at = Column(DateTime, nullable=True)
    accepted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    customer = relationship("Customer")
    creator = relationship("User", foreign_keys=[created_by])
```

### 5.4 Updated Customer Model

```python
# Updates to src/models/customer.py

class Customer(Base):
    """Customer/Tenant model"""
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Tenant status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    # Tenant configuration
    settings = Column(JSON, default={})
    
    # Primary contact
    primary_contact_email = Column(String(255))
    primary_contact_name = Column(String(255))
    
    # Relationships
    users = relationship("User", back_populates="customer")
    roles = relationship("TenantRole", back_populates="customer")
    feature_allocations = relationship("TenantFeatureAllocation", back_populates="customer")
    ai_providers = relationship("CustomerAIProvider", back_populates="customer")
```

### 5.5 Platform Admin Model

```python
# src/models/platform_admin.py

class PlatformAdmin(Base):
    """Platform-level administrators (Eliza team)"""
    __tablename__ = "platform_admins"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    admin_level = Column(String(50), default="admin")  # admin, super_admin
    can_create_tenants = Column(Boolean, default=True)
    can_allocate_features = Column(Boolean, default=True)
    can_impersonate = Column(Boolean, default=False)  # For support
    created_at = Column(DateTime, server_default=func.now())
    
    user = relationship("User", back_populates="platform_admin")
```

---

## 6. API Endpoints

### 6.1 Platform Admin Endpoints (Eliza Team Only)

```
PREFIX: /v1/platform-admin

# Tenant Management
POST   /tenants                          Create new tenant
GET    /tenants                          List all tenants
GET    /tenants/{customer_id}            Get tenant details
PUT    /tenants/{customer_id}            Update tenant
DELETE /tenants/{customer_id}            Deactivate tenant

# Feature Allocation
GET    /features                         List all platform features
GET    /tenants/{customer_id}/features   Get tenant's allocated features
PUT    /tenants/{customer_id}/features   Update tenant's feature allocation
POST   /tenants/{customer_id}/features/{feature_id}/enable    Enable feature
POST   /tenants/{customer_id}/features/{feature_id}/disable   Disable feature

# Platform Admin Management
GET    /admins                           List platform admins
POST   /admins                           Create platform admin
DELETE /admins/{user_id}                 Remove platform admin
```

### 6.2 Tenant Admin Endpoints

```
PREFIX: /v1/admin

# User Management
GET    /users                            List users in tenant
POST   /users                            Create new user
GET    /users/{user_id}                  Get user details
PUT    /users/{user_id}                  Update user
DELETE /users/{user_id}                  Deactivate user
POST   /users/{user_id}/roles            Assign roles to user
DELETE /users/{user_id}/roles/{role_id}  Remove role from user

# User Invites
POST   /invites                          Create user invite
GET    /invites                          List pending invites
DELETE /invites/{invite_id}              Revoke invite
POST   /invites/{invite_id}/resend       Resend invite

# Role Management
GET    /roles                            List roles in tenant
POST   /roles                            Create new role
GET    /roles/{role_id}                  Get role details
PUT    /roles/{role_id}                  Update role
DELETE /roles/{role_id}                  Delete role (if not system role)
GET    /roles/{role_id}/permissions      Get role permissions
PUT    /roles/{role_id}/permissions      Update role permissions (bulk)
POST   /roles/{role_id}/permissions/{permission_id}    Add permission to role
DELETE /roles/{role_id}/permissions/{permission_id}    Remove permission from role

# Available Permissions (based on allocated features)
GET    /permissions                      List available permissions for tenant
GET    /permissions/by-feature           List permissions grouped by feature
```

### 6.3 Public Endpoints

```
PREFIX: /v1/auth

# Invite Acceptance
GET    /invite/{token}                   Validate invite token
POST   /invite/{token}/accept            Accept invite and set password
```

---

## 7. Frontend Components

### 7.1 Design System Alignment

All components follow the existing Eliza Platform design system:

**Color Palette (CSS Variables)**
- `--brand: #FF9580` (Coral Pink) - Primary actions, selected states
- `--brand-strong: #FF7B6B` (Salmon) - Hover states
- `--brand-soft: rgba(255,149,128,0.15)` - Selected backgrounds
- `--surface / --surface-2` - Glass surfaces with backdrop blur
- `--text: #2B1420` - Primary text
- `--muted: #8B3A52` - Secondary text
- `--muted-2: #C96B75` - Tertiary/meta text

**UI Patterns**
- Use `.ui-list` / `.ui-item` for all lists (NO bulky cards)
- Glass surfaces (`bg-surface`, `bg-surface-2`) with `border-border`
- Linear-inspired 3-pane layouts where appropriate
- Compact spacing (`py-2 px-3` for list items)
- Small typography (`text-sm` for body, `text-xs` for meta)

**Component Library**
- shadcn/ui components (vanilla, unstyled where possible)
- Heroicons (`@heroicons/react/24/outline`)
- Tailwind CSS with design tokens

**Reference Components for Pill Design**

The permission toggle pills mirror existing patterns in Talent Intelligence:

| Component | Location | Pattern |
|-----------|----------|---------|
| Job Title Pills | `PersonaDefinitionForm.tsx` | `px-3 py-1 bg-primary/10 text-primary rounded-full` with XMarkIcon |
| Skill Pills | `PersonaDefinitionForm.tsx` | `px-3 py-1 bg-success/10 text-success rounded-full` with XMarkIcon |
| Company Pills | `PersonaDefinitionForm.tsx` | `px-3 py-1 bg-info/10 text-info rounded-full` with XMarkIcon |
| Skill Tags | `EmployeeSelector.tsx` | `px-2 py-0.5 text-xs bg-brand/10 text-brand rounded` |
| Highlights | `CandidateOutreachPage.tsx` | `px-3 py-1 bg-brand/10 text-brand rounded-full` |

For permissions, we use the **brand color** (`bg-brand/10 text-brand`) for selected state consistency across the admin UI. The toggle behavior follows the Northflank UX pattern:
- **Selected**: Filled coral pill + XMarkIcon (click to remove)
- **Unselected**: Outlined pill + PlusIcon (click to add)

---

### 7.2 Platform Admin UI (Eliza Team)

#### Route Structure
```
/platform-admin
├── /tenants                    # Tenant list (3-pane layout)
│   ├── /new                    # Create tenant inline panel
│   └── /{customer_id}          # Tenant details panel
├── /features                   # Feature management
└── /admins                     # Platform admin list
```

#### Component Structure
```typescript
src/pages/platform-admin/
├── PlatformAdminLayout.tsx     // 3-pane layout with nav rail
├── TenantsPage.tsx             // List + detail pane
├── FeaturesPage.tsx            // Feature management
└── PlatformAdminsPage.tsx      // Admin user list

src/components/platform-admin/
├── TenantListItem.tsx          // Single row in tenant list (.ui-item)
├── TenantDetailPane.tsx        // Right pane for tenant details
├── CreateTenantPane.tsx        // Inline creation form
├── FeatureAllocationMatrix.tsx // Toggle matrix for features
└── TenantStatusBadge.tsx       // Active/inactive indicator
```

---

### 7.3 Tenant Admin UI

#### Route Structure
```
/admin
├── /users                      # User list (3-pane)
│   └── /{user_id}              # User details panel
├── /invites                    # Pending invites list
├── /roles                      # Role list (3-pane)
│   ├── /new                    # Create role panel
│   └── /{role_id}              # Edit role panel
└── /settings                   # Tenant settings
```

#### Component Structure
```typescript
src/pages/admin/
├── UsersPage.tsx               // User list with detail pane
├── InvitesPage.tsx             // Invite management
├── RolesPage.tsx               // Role list with edit pane
└── TenantSettingsPage.tsx      // Tenant config

src/components/admin/
├── UserListItem.tsx            // User row (.ui-item style)
├── UserDetailPane.tsx          // User edit/view pane
├── CreateUserForm.tsx          // Compact inline form
├── RoleListItem.tsx            // Role row with permission count
├── RoleEditPane.tsx            // Permission matrix in pane
├── RoleBadge.tsx               // Small inline role indicator
├── PermissionMatrix.tsx        // THE CORE COMPONENT (see below)
├── PermissionCategory.tsx      // Collapsible category section
├── PermissionChip.tsx          // Toggle chip (selected/unselected)
├── InviteLinkCopy.tsx          // Copy-to-clipboard for invite URL
└── InviteListItem.tsx          // Pending invite row
```

---

### 7.4 Permission Matrix Component

The core component for role permission management. Uses the same pill design pattern as the Talent Intelligence `PersonaDefinitionForm` component.

```typescript
// src/components/admin/PermissionMatrix.tsx

interface PermissionMatrixProps {
  categories: PermissionCategory[];
  selectedPermissions: Set<number>;
  disabledFeatures?: Set<string>;  // Features not allocated to tenant
  onChange: (permissionId: number, selected: boolean) => void;
  onSelectAllCategory: (categoryId: string) => void;
  onClearCategory: (categoryId: string) => void;
}
```

#### Visual Structure (Mirroring PersonaDefinitionForm Pills)

The pill design follows the existing patterns in `PersonaDefinitionForm.tsx`:
- **Selected pills**: Filled background with color, XMarkIcon for toggle-off
- **Unselected pills**: Subtle outline with PlusIcon for toggle-on
- **Rounded-full** shape for consistency with skill/company/job title pills

```
┌─────────────────────────────────────────────────────────────────┐
│ Permissions                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 📄 Documents                                   Select all Clear │
│ ─────────────────────────────────────────────────────────────── │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │
│ │ Create  ×  │ │ Read    ×  │ │ + Update   │ │ + Delete   │    │
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘    │
│ ┌────────────┐                                                  │
│ │ Query   ×  │  ← Coral filled bg, × to remove                 │
│ └────────────┘                                                  │
│                                                                 │
│ 🔌 Connectors                                  Select all Clear │
│ ─────────────────────────────────────────────────────────────── │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐    │
│ │ Create  ×  │ │ Read    ×  │ │ Update  ×  │ │ + Delete   │    │
│ └────────────┘ └────────────┘ └────────────┘ └────────────┘    │
│ ┌────────────┐                                                  │
│ │ Sync    ×  │                                                  │
│ └────────────┘  ← Unselected: subtle border, + to add          │
│                                                                 │
│ 📊 Business Intelligence              ⚠️ Not enabled for tenant │
│ ─────────────────────────────────────────────────────────────── │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐ (grayed out)      │
│ │   Read     │ │   Write    │ │   Export   │                   │
│ └────────────┘ └────────────┘ └────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### Permission Pill Styles (Matching Talent Intelligence Pills)

Pattern from `PersonaDefinitionForm.tsx`:
- Job titles: `px-3 py-1 bg-primary/10 text-primary rounded-full`
- Skills: `px-3 py-1 bg-success/10 text-success rounded-full`
- Companies: `px-3 py-1 bg-info/10 text-info rounded-full`

For permissions, we use brand color for consistency across admin UI:

```tsx
// SELECTED PILL - Matches existing talent intelligence pill pattern
// Example from PersonaDefinitionForm:
// <span className="px-3 py-1 bg-primary/10 text-primary rounded-full text-sm flex items-center gap-2">
//   {title}
//   <button onClick={() => handleRemoveItem('job_titles', idx)}>
//     <XMarkIcon className="w-3 h-3" />
//   </button>
// </span>

// For permissions, we use brand color:
className="px-3 py-1 bg-brand/10 text-brand rounded-full text-sm flex items-center gap-2"
// With XMarkIcon for toggle-off

// UNSELECTED PILL - Subtle outline style
className="px-3 py-1 border border-border text-muted rounded-full text-sm flex items-center gap-2 hover:bg-surface-2 hover:border-muted"
// With PlusIcon for toggle-on

// DISABLED PILL - Feature not allocated
className="px-3 py-1 bg-surface-2 text-muted-2 rounded-full text-sm opacity-50 cursor-not-allowed"
```

#### Chip Component Implementation

```tsx
// src/components/admin/PermissionChip.tsx
import { XMarkIcon, PlusIcon } from '@heroicons/react/24/outline';
import { cn } from '../../lib/utils';

interface PermissionChipProps {
  label: string;
  selected: boolean;
  disabled?: boolean;
  disabledReason?: string;
  onClick: () => void;
}

export function PermissionChip({ 
  label, 
  selected, 
  disabled, 
  disabledReason,
  onClick 
}: PermissionChipProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={disabled ? disabledReason : undefined}
      className={cn(
        // Base styles - matches PersonaDefinitionForm pills
        "px-3 py-1 rounded-full text-sm flex items-center gap-2 transition-colors",
        
        // SELECTED: Coral brand fill (like job title pills)
        selected && !disabled && [
          "bg-brand/10 text-brand",
          "hover:bg-brand/20"
        ],
        
        // UNSELECTED: Subtle border (click to add)
        !selected && !disabled && [
          "border border-border text-muted",
          "hover:bg-surface-2 hover:border-muted hover:text-text"
        ],
        
        // DISABLED: Grayed out, feature not allocated
        disabled && "bg-surface-2 text-muted-2 opacity-50 cursor-not-allowed"
      )}
    >
      {label}
      {/* Icon after label, like PersonaDefinitionForm pills */}
      {selected && !disabled && <XMarkIcon className="w-3 h-3" />}
      {!selected && !disabled && <PlusIcon className="w-3 h-3" />}
    </button>
  );
}
```

#### Full PermissionMatrix Component

```tsx
// src/components/admin/PermissionMatrix.tsx
import { PermissionChip } from './PermissionChip';

interface PermissionCategory {
  id: string;
  displayName: string;
  icon: string;
  isEnabled: boolean;
  disabledReason?: string;
  permissions: {
    id: number;
    key: string;
    name: string;
  }[];
}

interface PermissionMatrixProps {
  categories: PermissionCategory[];
  selectedPermissions: Set<number>;
  onChange: (permissionId: number, selected: boolean) => void;
  onSelectAllCategory: (categoryId: string) => void;
  onClearCategory: (categoryId: string) => void;
}

export function PermissionMatrix({
  categories,
  selectedPermissions,
  onChange,
  onSelectAllCategory,
  onClearCategory
}: PermissionMatrixProps) {
  return (
    <div className="space-y-6">
      {categories.map((category) => (
        <div key={category.id}>
          {/* Category Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-text">
                {category.displayName}
              </span>
              {!category.isEnabled && (
                <span className="text-xs text-warning">
                  ⚠️ Not enabled for tenant
                </span>
              )}
            </div>
            {category.isEnabled && (
              <div className="flex items-center gap-3 text-xs">
                <button
                  onClick={() => onSelectAllCategory(category.id)}
                  className="text-brand hover:text-brand-strong"
                >
                  Select all
                </button>
                <button
                  onClick={() => onClearCategory(category.id)}
                  className="text-muted hover:text-text"
                >
                  Clear
                </button>
              </div>
            )}
          </div>
          
          {/* Permission Pills - flex wrap like PersonaDefinitionForm */}
          <div className="flex flex-wrap gap-2">
            {category.permissions.map((permission) => (
              <PermissionChip
                key={permission.id}
                label={permission.name}
                selected={selectedPermissions.has(permission.id)}
                disabled={!category.isEnabled}
                disabledReason={category.disabledReason}
                onClick={() => onChange(
                  permission.id, 
                  !selectedPermissions.has(permission.id)
                )}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

#### Interactive Behavior (Northflank UX)

The interaction follows Northflank's clean toggle pattern:

1. **Toggle On**: Click an unselected pill → pill fills with `bg-brand/10`, shows `×` icon
2. **Toggle Off**: Click the `×` on a selected pill → pill becomes outlined with `+` icon
3. **Select All**: Click "Select all" → all pills in category become selected
4. **Clear**: Click "Clear" → all pills in category become unselected
5. **Disabled**: Pills for unallocated features are grayed out and non-interactive

---

### 7.5 List Item Patterns (No Cards)

All list views use the `.ui-item` pattern - clean rows, not bulky cards.

#### User List Item

```tsx
// Compact row with inline info, no card wrapper
<div className="ui-item group">
  {/* Avatar */}
  <div className="w-8 h-8 rounded-full bg-brand-soft flex items-center justify-center flex-shrink-0">
    <span className="text-brand-strong text-xs font-medium">JD</span>
  </div>
  
  {/* Info */}
  <div className="ml-3 flex-1 min-w-0">
    <div className="flex items-center gap-2">
      <span className="text-sm font-medium text-text truncate">John Doe</span>
      <RoleBadge role="Admin" />
      <RoleBadge role="Sales" />
    </div>
    <span className="text-xs text-muted">john@acme.com</span>
  </div>
  
  {/* Meta */}
  <span className="text-xs text-muted-2">Active</span>
</div>
```

#### Role List Item

```tsx
<div className="ui-item group">
  <div className="flex-1 min-w-0">
    <span className="text-sm font-medium text-text">Sales Team</span>
    <span className="text-xs text-muted ml-2">12 permissions</span>
  </div>
  <span className="text-xs text-muted-2">3 users</span>
</div>
```

#### Tenant List Item (Platform Admin)

```tsx
<div className="ui-item group">
  {/* Logo/Initial */}
  <div className="w-8 h-8 rounded-lg bg-surface-2 border border-border flex items-center justify-center flex-shrink-0">
    <span className="text-text text-xs font-bold">AC</span>
  </div>
  
  {/* Info */}
  <div className="ml-3 flex-1 min-w-0">
    <span className="text-sm font-medium text-text truncate">Acme Corporation</span>
    <span className="text-xs text-muted block">acme-corp · 24 users</span>
  </div>
  
  {/* Status */}
  <TenantStatusBadge status="active" />
</div>
```

---

### 7.6 Create Role Page Layout

Uses right pane pattern, not a separate page with cards.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ROLES                                                                    │
├─────────────────────────┬────────────────────────────────────────────────┤
│                         │                                                │
│  [+ New Role]           │  Create Role                           [Save] │
│                         │  ─────────────────────────────────────────────│
│  ┌─────────────────┐    │                                                │
│  │ Admin        ▪4 │    │  Name                                          │
│  │ system role     │    │  ┌──────────────────────────────────────────┐ │
│  └─────────────────┘    │  │ Sales Team                               │ │
│  ┌─────────────────┐    │  └──────────────────────────────────────────┘ │
│  │ Viewer       ▪2 │    │                                                │
│  │ system role     │    │  Description (optional)                        │
│  └─────────────────┘    │  ┌──────────────────────────────────────────┐ │
│  ┌─────────────────┐    │  │ Access for sales team members            │ │
│  │ HR Manager   ▪8 │    │  └──────────────────────────────────────────┘ │
│  │ custom          │    │                                                │
│  └─────────────────┘    │  ─────────────────────────────────────────────│
│                         │                                                │
│                         │  Permissions                                   │
│                         │                                                │
│                         │  📄 Documents                  Select all Clear│
│                         │  ─────────────────────────────────────────────│
│                         │  (selected = coral bg-brand/10, × to remove)   │
│                         │  ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│                         │  │ Read   × │ │+ Write   │ │+ Delete  │       │
│                         │  └──────────┘ └──────────┘ └──────────┘       │
│                         │  ┌──────────┐                                  │
│                         │  │ Query  × │                                  │
│                         │  └──────────┘                                  │
│                         │                                                │
│                         │  🎯 Talent Intelligence        Select all Clear│
│                         │  ─────────────────────────────────────────────│
│                         │  ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│                         │  │ Read   × │ │ Write  × │ │ Run Analysis ×│  │
│                         │  └──────────┘ └──────────┘ └──────────────┘   │
│                         │                                                │
└─────────────────────────┴────────────────────────────────────────────────┘
```

---

### 7.7 Invite Link UX

Simple inline display with copy button, not a modal or card.

```tsx
// After user creation, show inline:
<div className="flex items-center gap-2 p-3 bg-ai-success/10 border border-ai-success/20 rounded-md">
  <CheckCircleIcon className="w-5 h-5 text-ai-success flex-shrink-0" />
  <div className="flex-1 min-w-0">
    <p className="text-sm text-text">User created successfully</p>
    <p className="text-xs text-muted truncate">{inviteUrl}</p>
  </div>
  <button 
    onClick={copyToClipboard}
    className="text-xs text-brand hover:text-brand-strong flex items-center gap-1"
  >
    <ClipboardIcon className="w-4 h-4" />
    Copy link
  </button>
</div>
```

---

## 8. User Flows

### 8.1 Platform Admin: Create New Tenant

```
┌─────────────────────────────────────────────────────────────────┐
│ FLOW: Platform Admin Creates New Tenant                         │
└─────────────────────────────────────────────────────────────────┘

1. Platform Admin clicks [+ New Tenant] in tenants list

2. Right pane opens with creation form:

   ┌────────────────────────────────────────────────────────────┐
   │ New Tenant                                         [Create]│
   ├────────────────────────────────────────────────────────────┤
   │                                                            │
   │ TENANT DETAILS                                             │
   │ ─────────────────────────────────────────────────────────  │
   │                                                            │
   │ Customer ID (slug)                                         │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │acme-corp                                               ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │ Company Name                                               │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │Acme Corporation                                        ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │ ADMIN USER                                                 │
   │ ─────────────────────────────────────────────────────────  │
   │                                                            │
   │ Admin Email                                                │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │admin@acme.com                                          ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │ Admin Name                                                 │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │John Admin                                              ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │ FEATURE ALLOCATION                                         │
   │ ─────────────────────────────────────────────────────────  │
   │                                                            │
   │ Feature pills (selected = coral fill, unselected = outline)│
   │                                                            │
   │ ┌──────────────────┐ ┌──────────────────┐ ┌─────────────┐ │
   │ │ Documents & RAG ×│ │ Business Intel ×│ │+ Talent     │ │
   │ └──────────────────┘ └──────────────────┘ └─────────────┘ │
   │ ┌──────────────────┐ ┌──────────────────┐ ┌─────────────┐ │
   │ │ Data Connectors ×│ │ AI Providers   ×│ │+ Operations │ │
   │ └──────────────────┘ └──────────────────┘ └─────────────┘ │
   │ ┌──────────────────┐ ┌──────────────────┐                 │
   │ │ HR Intelligence ×│ │ Audit & Logging ×│                │
   │ └──────────────────┘ └──────────────────┘                 │
   │                                                            │
   └────────────────────────────────────────────────────────────┘

3. On success, inline confirmation with invite link:

   ┌────────────────────────────────────────────────────────────┐
   │ ✓ Tenant created                                           │
   │   Admin invite: https://app.eliza.com/invite/...   [Copy]  │
   └────────────────────────────────────────────────────────────┘

4. System automatically creates:
   - Customer record with customer_id
   - TenantFeatureAllocation records for selected features
   - Default Admin role (all permissions for allocated features)
   - Default Viewer role (read-only for allocated features)
   - Tenant Admin user with invite link
```

### 8.2 Tenant Admin: Create New Role

```
┌─────────────────────────────────────────────────────────────────┐
│ FLOW: Tenant Admin Creates Custom Role                          │
└─────────────────────────────────────────────────────────────────┘

1. Tenant Admin clicks [+ New Role] in roles list

2. Right pane opens with role editor (see Section 7.6 for layout)

3. Permission matrix shows ONLY permissions for allocated features
   - Features not allocated to tenant appear grayed out with tooltip

4. Interaction:
   - Click unselected chip → chip becomes coral with × icon (selected)
   - Click selected chip (×) → chip becomes outlined with + icon (unselected)
   - "Select all" → enables all permissions in category
   - "Clear" → removes all permissions in category

5. Click [Save] in pane header

6. System creates:
   - TenantRole record (customer_id, role_name, description)
   - TenantRolePermission records for each selected permission

7. Role appears in list, pane shows role details with user assignment
```

### 8.3 Tenant Admin: Create & Invite User

```
┌─────────────────────────────────────────────────────────────────┐
│ FLOW: Tenant Admin Creates User & Generates Invite              │
└─────────────────────────────────────────────────────────────────┘

1. Tenant Admin clicks [+ New User] in users list

2. Right pane opens with compact form:
   
   ┌────────────────────────────────────────────────────────────┐
   │ New User                                           [Create]│
   ├────────────────────────────────────────────────────────────┤
   │                                                            │
   │ Email *                                                    │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │john.doe@acme.com                                       ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │ Full Name *                                                │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │John Doe                                                ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │ Roles                                                      │
   │ (selected = coral pill with ×, unselected = outline with +)│
   │ ┌──────────┐ ┌─────────────┐ ┌─────────────┐              │
   │ │ Viewer × │ │ Sales Team ×│ │+ HR Manager │              │
   │ └──────────┘ └─────────────┘ └─────────────┘              │
   │                                                            │
   └────────────────────────────────────────────────────────────┘

3. On success, inline banner appears:

   ┌────────────────────────────────────────────────────────────┐
   │ ✓ User created · https://app.eliza.com/invite/... [Copy]  │
   └────────────────────────────────────────────────────────────┘

4. User appears in list, status shows "Pending Invite"
```

### 8.4 User: Accept Invite

```
┌─────────────────────────────────────────────────────────────────┐
│ FLOW: User Accepts Invite                                       │
└─────────────────────────────────────────────────────────────────┘

1. User clicks invite link: https://app.eliza.com/invite/{token}

2. Clean, minimal acceptance page (glass surface, centered):

   ┌────────────────────────────────────────────────────────────┐
   │                                                            │
   │               Welcome to Acme Corporation                  │
   │                                                            │
   │          You've been invited to Eliza Platform             │
   │                                                            │
   │ ─────────────────────────────────────────────────────────  │
   │                                                            │
   │ john.doe@acme.com                                          │
   │                                                            │
   │ Password                                                   │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │••••••••••••                                            ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │ Confirm Password                                           │
   │ ┌────────────────────────────────────────────────────────┐│
   │ │••••••••••••                                            ││
   │ └────────────────────────────────────────────────────────┘│
   │                                                            │
   │              ┌─────────────────────────┐                   │
   │              │   Activate Account      │                   │
   │              └─────────────────────────┘                   │
   │                                                            │
   │           Link expires in 6 days, 23 hours                 │
   │                                                            │
   └────────────────────────────────────────────────────────────┘

3. On submit:
   - Password hashed and saved
   - User activated
   - Invite marked used
   - Auto-login to application
```

---

## 9. Implementation Phases

### Phase 1: Database & Core Models (Week 1)
- [ ] Create migration for platform_features table
- [ ] Create migration for tenant_feature_allocations table
- [ ] Create migration for feature_permissions table
- [ ] Create migration for tenant_roles table
- [ ] Create migration for tenant_role_permissions table
- [ ] Create migration for tenant_user_roles table
- [ ] Create migration for user_invites table
- [ ] Create migration for platform_admins table
- [ ] Update Customer model with new relationships
- [ ] Seed initial platform features and permissions

### Phase 2: Platform Admin Backend (Week 1-2)
- [ ] Create PlatformAdminService
- [ ] Create TenantManagementService
- [ ] Create FeatureAllocationService
- [ ] Implement platform admin authentication/authorization
- [ ] Create /v1/platform-admin/* endpoints
- [ ] Add platform admin middleware

### Phase 3: Tenant Admin Backend (Week 2)
- [ ] Create TenantRoleService
- [ ] Create TenantUserService
- [ ] Create UserInviteService
- [ ] Implement permission checking based on feature allocation
- [ ] Create /v1/admin/* endpoints
- [ ] Update auth flow to include tenant permissions

### Phase 4: Platform Admin Frontend (Week 3)
- [ ] Create platform admin layout and navigation
- [ ] Build TenantsListPage
- [ ] Build CreateTenantPage with feature allocation
- [ ] Build TenantDetailsPage
- [ ] Build FeatureAllocationPage with toggle matrix
- [ ] Implement platform admin authentication

### Phase 5: Tenant Admin Frontend (Week 3-4)
- [ ] Create tenant admin layout and navigation
- [ ] Build UsersListPage
- [ ] Build CreateUserPage
- [ ] Build UserDetailsPage with role assignment
- [ ] Build RolesListPage
- [ ] Build CreateRolePage with permission toggle matrix
- [ ] Build RoleDetailsPage
- [ ] Create PermissionToggleMatrix component (Northflank-style)
- [ ] Create PermissionChip component
- [ ] Build InviteLinkGenerator component

### Phase 6: User Invite Flow (Week 4)
- [ ] Build invite acceptance page
- [ ] Implement invite token validation
- [ ] Implement password setting flow
- [ ] Add invite expiration handling
- [ ] Email integration for invite notifications (optional)

### Phase 7: Testing & Polish (Week 5)
- [ ] Unit tests for all services
- [ ] Integration tests for API endpoints
- [ ] E2E tests for key flows
- [ ] Permission matrix validation
- [ ] Security audit
- [ ] Documentation

---

## Appendix A: Permission Definitions

### Full Permission List

```typescript
const PLATFORM_PERMISSIONS = {
  documents: {
    displayName: "Documents",
    icon: "FileText",
    permissions: [
      { key: "documents:create", name: "Create Documents" },
      { key: "documents:read", name: "Read Documents" },
      { key: "documents:update", name: "Update Documents" },
      { key: "documents:delete", name: "Delete Documents" },
      { key: "documents:rag_query", name: "RAG Query" },
    ]
  },
  
  connectors: {
    displayName: "Data Connectors",
    icon: "Plug",
    permissions: [
      { key: "connectors:create", name: "Create Connectors" },
      { key: "connectors:read", name: "Read Connectors" },
      { key: "connectors:update", name: "Update Connectors" },
      { key: "connectors:delete", name: "Delete Connectors" },
      { key: "connectors:run_sync", name: "Run Sync" },
      { key: "connectors:view_telemetry", name: "View Telemetry" },
    ]
  },
  
  ai_providers: {
    displayName: "AI Providers",
    icon: "Brain",
    permissions: [
      { key: "ai_providers:create", name: "Create Providers" },
      { key: "ai_providers:read", name: "Read Providers" },
      { key: "ai_providers:update", name: "Update Providers" },
      { key: "ai_providers:delete", name: "Delete Providers" },
      { key: "ai_providers:test_keys", name: "Test API Keys" },
    ]
  },
  
  business_intelligence: {
    displayName: "Business Intelligence",
    icon: "BarChart",
    permissions: [
      { key: "bi:read", name: "Read" },
      { key: "bi:write", name: "Write" },
      { key: "bi:run_queries", name: "Run Queries" },
      { key: "bi:export_reports", name: "Export Reports" },
    ]
  },
  
  talent_intelligence: {
    displayName: "Talent Intelligence",
    icon: "Users",
    permissions: [
      { key: "talent:read", name: "Read" },
      { key: "talent:write", name: "Write" },
      { key: "talent:run_analysis", name: "Run Analysis" },
      { key: "talent:manage_configs", name: "Manage Configurations" },
    ]
  },
  
  hr_intelligence: {
    displayName: "HR Intelligence",
    icon: "Building",
    permissions: [
      { key: "hr:read", name: "Read" },
      { key: "hr:write", name: "Write" },
      { key: "hr:company_access", name: "Company Data Access" },
      { key: "hr:run_reports", name: "Run Reports" },
    ]
  },
  
  operations_intelligence: {
    displayName: "Operations Intelligence",
    icon: "Settings",
    permissions: [
      { key: "ops:read", name: "Read" },
      { key: "ops:write", name: "Write" },
      { key: "ops:run_analysis", name: "Run Analysis" },
    ]
  },
  
  users_roles: {
    displayName: "Users & Roles",
    icon: "UserCog",
    permissions: [
      { key: "users:create", name: "Create Users" },
      { key: "users:read", name: "Read Users" },
      { key: "users:update", name: "Update Users" },
      { key: "users:delete", name: "Delete Users" },
      { key: "roles:manage", name: "Manage Roles" },
    ]
  },
  
  settings: {
    displayName: "Settings",
    icon: "Cog",
    permissions: [
      { key: "settings:read", name: "Read Settings" },
      { key: "settings:write", name: "Write Settings" },
    ]
  },
  
  audit: {
    displayName: "Audit Logs",
    icon: "ClipboardList",
    permissions: [
      { key: "audit:read", name: "Read Audit Logs" },
      { key: "audit:export", name: "Export Audit Logs" },
    ]
  },
};
```

---

## Appendix B: API Response Examples

### Create Tenant Response

```json
{
  "success": true,
  "data": {
    "tenant": {
      "customer_id": "acme-corp",
      "name": "Acme Corporation",
      "is_active": true,
      "created_at": "2025-12-23T15:30:00Z"
    },
    "admin_user": {
      "id": 42,
      "email": "admin@acme.com",
      "full_name": "John Admin",
      "invite_link": "https://app.eliza.com/invite/abc123def456"
    },
    "allocated_features": [
      "documents",
      "business_intelligence",
      "connectors",
      "ai_providers",
      "audit"
    ],
    "default_roles": [
      { "id": 1, "name": "Admin", "is_system_role": true },
      { "id": 2, "name": "Viewer", "is_system_role": true }
    ]
  }
}
```

### Get Available Permissions Response

```json
{
  "success": true,
  "data": {
    "categories": [
      {
        "id": "documents",
        "display_name": "Documents",
        "icon": "FileText",
        "is_enabled": true,
        "permissions": [
          { "id": 1, "key": "documents:create", "name": "Create Documents" },
          { "id": 2, "key": "documents:read", "name": "Read Documents" },
          { "id": 3, "key": "documents:update", "name": "Update Documents" },
          { "id": 4, "key": "documents:delete", "name": "Delete Documents" },
          { "id": 5, "key": "documents:rag_query", "name": "RAG Query" }
        ]
      },
      {
        "id": "talent_intelligence",
        "display_name": "Talent Intelligence",
        "icon": "Users",
        "is_enabled": false,
        "disabled_reason": "Feature not allocated to your tenant",
        "permissions": []
      }
    ]
  }
}
```

---

## Appendix C: Security Considerations

1. **Tenant Isolation**: All queries MUST filter by `customer_id` for tenant-scoped data
2. **Permission Validation**: Every API endpoint must validate user has required permissions
3. **Feature Allocation Check**: Before granting permissions, verify feature is allocated to tenant
4. **Invite Token Security**: Tokens should be cryptographically secure, single-use, time-limited
5. **Rate Limiting**: Apply rate limits to invite creation to prevent abuse
6. **Audit Logging**: Log all admin actions (user creation, role changes, permission updates)
7. **Password Requirements**: Enforce strong password policy on invite acceptance

---

*End of Specification*

