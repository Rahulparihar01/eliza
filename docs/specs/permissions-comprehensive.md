# Comprehensive Permissions Specification

## Overview

This document defines all permissions for the Eliza Platform. Permissions follow the format:
```
feature:action
feature:subfeature:action
```

All permissions will be created in a single migration, replacing the old permission system.

---

## Permission Categories

| Category | Prefix | Description |
|----------|--------|-------------|
| Platform | `platform:` | Super admin, system-level access |
| AI Assistant | `assistant:` | Documents, Question Log, Chat, Domains |
| AI Recruiter | `recruiter:` | Analysis, Outreach, Templates |
| Administration | `admin:` | Settings, System Config |
| Connections | `connections:` | Data Connections (DB, API connectors) |
| Users & Roles | `users:`, `roles:` | Tenant user management |
| Audit | `audit:` | System logs and audit trails |

---

## 1. Platform (Super Admin)

| Permission | Description | Who Gets It |
|------------|-------------|-------------|
| `platform:admin` | Full system access with all permissions granted. All actions are logged and audited. | Platform Admin only |

---

## 2. AI Assistant

### Core Access

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `assistant:access` | Can open AI Assistant section | All users |

### Documents

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `assistant:documents:read` | View uploaded documents | Viewer+ |
| `assistant:documents:upload` | Upload new documents | Editor+ |
| `assistant:documents:delete` | Remove documents | Admin |

### Question Log

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `assistant:questions:read` | View question history | Viewer+ |
| `assistant:questions:ask` | Submit new questions | User+ |
| `assistant:questions:delete` | Delete question history | Admin |

### Chat (Analytics Domains)

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `assistant:chat:access` | Use the Chat interface | User+ |

### Domain Management

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `assistant:domains:onboard` | Create new analytics domains | Power User |
| `assistant:domains:configure` | Edit domain configuration | Power User |
| `assistant:domains:publish` | Publish domains for use | Power User |
| `assistant:domains:delete` | Remove analytics domains | Admin |

### Domain-Specific Access (Dynamic)

| Permission | Description | Notes |
|------------|-------------|-------|
| `assistant:domains:insurance_analytics:access` | Query Insurance Analytics | Pre-configured domain |
| `assistant:domains:<slug>:access` | Query specific domain | Created when domain is published |

---

## 3. AI Recruiter

### Core Access

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:access` | Can open AI Recruiter section | All users |

### Talent Search Templates (formerly Analysis Config)

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:config:read` | View search/scoring templates | Viewer+ |
| `recruiter:config:create` | Create new templates | Editor+ |
| `recruiter:config:update` | Edit templates | Editor+ |
| `recruiter:config:delete` | Delete templates | Admin |

### Search Results (formerly Candidate Outreach)

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:results:read` | View scored candidates & metrics | Viewer+ |
| `recruiter:results:email` | Generate/send emails | User+ |
| `recruiter:results:feedback` | Provide score feedback | User+ |

### Email Templates

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:email_templates:read` | View email templates | Viewer+ |
| `recruiter:email_templates:create` | Create templates | Editor+ |
| `recruiter:email_templates:update` | Edit templates | Editor+ |
| `recruiter:email_templates:delete` | Delete templates | Admin |
| `recruiter:email_templates:set_default` | Set default template per candidate type | Editor+ |

### Section Library

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:section_library:read` | View section library | Viewer+ |
| `recruiter:section_library:create` | Save sections to library | Editor+ |
| `recruiter:section_library:update` | Edit library sections | Editor+ |
| `recruiter:section_library:delete` | Delete library sections | Admin |

### Blueprints & Company DNA

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:blueprints:read` | View career blueprints | Viewer+ |
| `recruiter:blueprints:create` | Create blueprints | Editor+ |
| `recruiter:blueprints:update` | Edit blueprints | Editor+ |
| `recruiter:blueprints:delete` | Delete blueprints | Admin |
| `recruiter:dna:read` | View company DNA | Viewer+ |
| `recruiter:dna:update` | Edit company DNA | Editor+ |

### Talent Search History (formerly Analysis History)

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:history:read` | View talent search run history | Viewer+ |
| `recruiter:history:delete` | Delete search history | Admin |

### Reference Checks (Coming Soon - Gated)

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `recruiter:reference_checks:access` | Access Reference Checks feature | Platform Admin only (for now) |
| `recruiter:reference_checks:create` | Create reference check requests | Editor+ |
| `recruiter:reference_checks:read` | View reference check results | Viewer+ |
| `recruiter:reference_checks:manage` | Manage reference check settings | Admin |

---

## 4. Administration

### System Settings

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `admin:settings:read` | View system settings (default company, vector config, providers) | Tenant Admin |
| `admin:settings:update` | Modify system settings | Tenant Admin |
| `admin:settings:providers:manage` | Manage AI provider configurations (OpenAI, Anthropic, etc.) | Tenant Admin |

### Google Email Integration

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `admin:email:read` | View Google email integration status | Tenant Admin |
| `admin:email:configure` | Configure/update Google OAuth credentials | Tenant Admin |
| `admin:email:disconnect` | Disconnect Google email account | Tenant Admin |

---

## 5. Data Connections

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `connections:read` | View configured data connections | Tenant Admin |
| `connections:create` | Add new connections from library | Tenant Admin |
| `connections:update` | Edit connection configuration | Tenant Admin |
| `connections:delete` | Remove data connections | Tenant Admin |
| `connections:test` | Test connection health/connectivity | Tenant Admin |
| `connections:sync` | Trigger manual data synchronization | Tenant Admin |

> **Note:** Connector types (PostgreSQL, MySQL, Greenhouse, PDL, etc.) are managed through the UI connector library. Any tenant admin with `connections:create` can configure any available connector type.

---

## 6. Users & Roles (Tenant Admin)

### User Management

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `users:read` | View users in tenant | Tenant Admin |
| `users:invite` | Send user invitations | Tenant Admin |
| `users:update` | Edit user details and role assignments | Tenant Admin |
| `users:deactivate` | Deactivate/suspend user accounts | Tenant Admin |
| `users:delete` | Permanently delete user accounts | Tenant Admin |

### Role Management

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `roles:read` | View available roles and their permissions | Tenant Admin |
| `roles:create` | Create new custom roles | Tenant Admin |
| `roles:update` | Edit role permissions | Tenant Admin |
| `roles:delete` | Delete custom roles | Tenant Admin |
| `roles:assign` | Assign roles to users | Tenant Admin |

### Invite Management

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `invites:read` | View pending invitations | Tenant Admin |
| `invites:create` | Create new user invitations | Tenant Admin |
| `invites:resend` | Resend invitation emails | Tenant Admin |
| `invites:revoke` | Cancel pending invitations | Tenant Admin |

---

## 7. Audit & Logging

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `audit:read` | View audit logs | Tenant Admin |
| `audit:export` | Export audit data to file | Tenant Admin |
| `audit:filter` | Filter audit logs by user/action | Tenant Admin |

---

## 8. Coming Soon Features (Platform Admin Gated)

These features are in development and only accessible to Platform Admins for testing.

### Agent Configuration

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `labs:agents:access` | Access Agent Configuration page | Platform Admin only |
| `labs:agents:configure` | Configure AI agent parameters | Platform Admin only |
| `labs:agents:test` | Test agent configurations | Platform Admin only |

### Resume Parsing Test

| Permission | Description | Typical Role |
|------------|-------------|--------------|
| `labs:resume_parsing:access` | Access Resume Parsing Test page | Platform Admin only |
| `labs:resume_parsing:upload` | Upload test resumes | Platform Admin only |
| `labs:resume_parsing:analyze` | Run parsing analysis | Platform Admin only |

---

## Default Roles

### Platform Admin (System-Level)
- Role name: `platform_admin`
- Customer ID: `platform`
- `platform:admin` permission - Has everything, bypasses all checks
- This is the only role that can access `labs:*` (Coming Soon) features

### Admin (Tenant-Level)
- Role name: `admin`
- Created per-tenant with the tenant's `customer_id`
- Full administrative access within their tenant:
```
# AI Assistant
assistant:access, assistant:documents:*, assistant:questions:*, 
assistant:chat:access, assistant:domains:*

# AI Recruiter
recruiter:access, recruiter:config:*, recruiter:results:*, 
recruiter:email_templates:*, recruiter:section_library:*,
recruiter:blueprints:*, recruiter:dna:*, recruiter:history:*

# Administration
admin:settings:*, admin:email:*

# Data Connections
connections:*

# Users & Roles
users:*, roles:*, invites:*

# Audit
audit:read, audit:filter
```

### Editor (Tenant-Level)
- Role name: `editor`
- Created per-tenant with the tenant's `customer_id`
- Can create and modify content, but not manage users or settings:
```
# AI Assistant
assistant:access, assistant:documents:read, assistant:documents:upload,
assistant:questions:read, assistant:questions:ask,
assistant:chat:access, assistant:domains:*:access

# AI Recruiter
recruiter:access, recruiter:config:read, recruiter:config:create, recruiter:config:update,
recruiter:results:read, recruiter:results:email, recruiter:results:feedback,
recruiter:email_templates:read, recruiter:email_templates:create, recruiter:email_templates:update,
recruiter:section_library:read, recruiter:section_library:create, recruiter:section_library:update,
recruiter:blueprints:read, recruiter:blueprints:create, recruiter:blueprints:update,
recruiter:dna:read, recruiter:dna:update,
recruiter:history:read
```

### Viewer (Tenant-Level)
- Role name: `viewer`
- Created per-tenant with the tenant's `customer_id`
- Read-only access to view content:
```
# AI Assistant
assistant:access, assistant:documents:read, assistant:questions:read,
assistant:chat:access, assistant:domains:*:access

# AI Recruiter  
recruiter:access, recruiter:config:read, recruiter:results:read,
recruiter:email_templates:read, recruiter:section_library:read,
recruiter:blueprints:read, recruiter:dna:read, recruiter:history:read
```

---

## Summary Count

| Category | Count | Status |
|----------|-------|--------|
| Platform | 1 | ✅ Finalized |
| AI Assistant | 13 | ✅ Finalized |
| AI Recruiter | 22 | ✅ Finalized |
| Administration | 6 | ✅ Finalized |
| Data Connections | 6 | ✅ Finalized |
| Users & Roles | 14 | ✅ Finalized |
| Audit | 3 | ✅ Finalized |
| Coming Soon (Labs) | 6 | ✅ Finalized |
| **Total** | **71** | ✅ |

---

## Permission Hierarchy

```
platform:admin
    └── (bypasses all checks)

admin:*
    ├── admin:settings:*
    │   ├── admin:settings:read
    │   ├── admin:settings:update
    │   └── admin:settings:providers:manage
    └── admin:email:*
        ├── admin:email:read
        ├── admin:email:configure
        └── admin:email:disconnect

connections:*
    ├── connections:read
    ├── connections:create
    ├── connections:update
    ├── connections:delete
    ├── connections:test
    └── connections:sync

users:*, roles:*, invites:*
    ├── users:read, users:invite, users:update, users:deactivate, users:delete
    ├── roles:read, roles:create, roles:update, roles:delete, roles:assign
    └── invites:read, invites:create, invites:resend, invites:revoke

labs:* (Platform Admin only)
    ├── labs:agents:*
    └── labs:resume_parsing:*
```

---

## Notes

1. **Dynamic permissions**: Domain-specific permissions (`assistant:domains:<slug>:access`) are created when domains are published
2. **platform:admin**: This permission bypasses ALL checks - holders can do anything
3. **Wildcards in code**: Backend should check patterns like `assistant:documents:*` using glob matching
4. **Tenant-scoped**: All permissions except `platform:admin` and `labs:*` are tenant-scoped
5. **labs:* permissions**: Reserved for Platform Admins to test unreleased features

---

## Migration Plan

The migration to implement these permissions should:

1. **Clear existing permissions** (except `platform:admin`)
2. **Create all permissions** listed in this document
3. **Create default roles**: `platform_admin` (system-level), `admin`, `editor`, `viewer` (per-tenant)
4. **Assign permissions to roles** according to the Default Roles section
5. **Preserve platform:admin** role assignments (existing platform admins keep access)

## Role Architecture

| Role | Name in DB | Scope | customer_id |
|------|------------|-------|-------------|
| Platform Admin | `platform_admin` | System-wide | `platform` |
| Admin | `admin` | Per-tenant | Tenant's customer_id |
| Editor | `editor` | Per-tenant | Tenant's customer_id |
| Viewer | `viewer` | Per-tenant | Tenant's customer_id |

**Note:** When a new tenant is created, the system automatically creates `admin`, `editor`, and `viewer` roles scoped to that tenant with appropriate permissions based on allocated features.

---

## Feature → Permission Mapping

When the Platform Admin allocates features to a tenant, the system grants permissions based on this mapping:

| Feature Key | Display Name | Permission Prefixes |
|-------------|--------------|---------------------|
| `documents` | AI Assistant - Documents | `assistant:documents:`, `assistant:domains:` |
| `business_intelligence` | AI Assistant - Question Log | `assistant:questions:` |
| `assistant_chat` | AI Assistant - Chat | `assistant:chat:`, `assistant:access` |
| `talent_intelligence` | AI Recruiter | `recruiter:access`, `recruiter:config:`, `recruiter:dna:`, `recruiter:results:`, `recruiter:history:` |
| `recruiter_email_templates` | AI Recruiter - Email Templates | `recruiter:email_templates:`, `recruiter:section_library:` |
| `recruiter_blueprints` | AI Recruiter - Blueprints & DNA | `recruiter:blueprints:` |
| `recruiter_reference_checks` | AI Recruiter - Reference Checks | `recruiter:reference_checks:` |
| `connectors` | Data Connections | `connections:` |
| `settings` | Admin Settings | `admin:settings:`, `admin:email:` |
| `users_roles` | Users & Roles | `users:`, `roles:` |
| `invites` | User Invites | `invites:` |
| `audit` | Audit & Logging | `audit:` |
| `ai_providers` | Labs - Agent Configuration | `labs:agents:` |
| `labs_resume_parsing` | Labs - Resume Parsing | `labs:resume_parsing:` |

### How Feature Allocation Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PLATFORM ADMIN ALLOCATES FEATURES                    │
│                         to a Tenant (e.g., Caylent)                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Tenant gets: documents, business_intelligence, talent_intelligence,    │
│               connectors, settings, users_roles, audit, invites         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  create_default_roles_for_tenant() runs:                                │
│                                                                         │
│  1. Looks up FEATURE_PERMISSION_MAP for allocated features              │
│  2. Builds list of allowed permission prefixes                          │
│  3. Queries all permissions matching those prefixes                     │
│  4. Assigns to roles based on permission type:                          │
│     - admin: ALL matching permissions                                   │
│     - editor: read + write permissions (non-admin)                      │
│     - viewer: read permissions only (non-admin)                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Permission → Feature → Role Matrix

| Permission | Feature Key | Admin | Editor | Viewer |
|------------|-------------|:-----:|:------:|:------:|
| **Platform** |||||
| `platform:admin` | *(platform only)* | ❌ | ❌ | ❌ |
| **AI Assistant - Documents** |||||
| `assistant:documents:read` | `documents` | ✅ | ✅ | ✅ |
| `assistant:documents:upload` | `documents` | ✅ | ✅ | ❌ |
| `assistant:documents:delete` | `documents` | ✅ | ❌ | ❌ |
| `assistant:domains:onboard` | `documents` | ✅ | ❌ | ❌ |
| `assistant:domains:configure` | `documents` | ✅ | ❌ | ❌ |
| `assistant:domains:publish` | `documents` | ✅ | ❌ | ❌ |
| `assistant:domains:delete` | `documents` | ✅ | ❌ | ❌ |
| `assistant:domains:insurance_analytics:access` | `documents` | ✅ | ✅ | ✅ |
| **AI Assistant - Question Log** |||||
| `assistant:questions:read` | `business_intelligence` | ✅ | ✅ | ✅ |
| `assistant:questions:ask` | `business_intelligence` | ✅ | ✅ | ❌ |
| `assistant:questions:delete` | `business_intelligence` | ✅ | ❌ | ❌ |
| **AI Assistant - Chat** |||||
| `assistant:access` | `assistant_chat` | ✅ | ✅ | ✅ |
| `assistant:chat:access` | `assistant_chat` | ✅ | ✅ | ✅ |
| **AI Recruiter** |||||
| `recruiter:access` | `talent_intelligence` | ✅ | ✅ | ✅ |
| `recruiter:config:read` | `talent_intelligence` | ✅ | ✅ | ✅ |
| `recruiter:config:create` | `talent_intelligence` | ✅ | ✅ | ❌ |
| `recruiter:config:update` | `talent_intelligence` | ✅ | ✅ | ❌ |
| `recruiter:config:delete` | `talent_intelligence` | ✅ | ❌ | ❌ |
| `recruiter:results:read` | `talent_intelligence` | ✅ | ✅ | ✅ |
| `recruiter:results:email` | `talent_intelligence` | ✅ | ✅ | ❌ |
| `recruiter:results:feedback` | `talent_intelligence` | ✅ | ✅ | ❌ |
| `recruiter:dna:read` | `talent_intelligence` | ✅ | ✅ | ✅ |
| `recruiter:dna:update` | `talent_intelligence` | ✅ | ✅ | ❌ |
| `recruiter:history:read` | `talent_intelligence` | ✅ | ✅ | ✅ |
| `recruiter:history:delete` | `talent_intelligence` | ✅ | ❌ | ❌ |
| **AI Recruiter - Email Templates** |||||
| `recruiter:email_templates:read` | `recruiter_email_templates` | ✅ | ✅ | ✅ |
| `recruiter:email_templates:create` | `recruiter_email_templates` | ✅ | ✅ | ❌ |
| `recruiter:email_templates:update` | `recruiter_email_templates` | ✅ | ✅ | ❌ |
| `recruiter:email_templates:delete` | `recruiter_email_templates` | ✅ | ❌ | ❌ |
| `recruiter:email_templates:set_default` | `recruiter_email_templates` | ✅ | ✅ | ❌ |
| `recruiter:section_library:read` | `recruiter_email_templates` | ✅ | ✅ | ✅ |
| `recruiter:section_library:create` | `recruiter_email_templates` | ✅ | ✅ | ❌ |
| `recruiter:section_library:update` | `recruiter_email_templates` | ✅ | ✅ | ❌ |
| `recruiter:section_library:delete` | `recruiter_email_templates` | ✅ | ❌ | ❌ |
| **AI Recruiter - Blueprints** |||||
| `recruiter:blueprints:read` | `recruiter_blueprints` | ✅ | ✅ | ✅ |
| `recruiter:blueprints:create` | `recruiter_blueprints` | ✅ | ✅ | ❌ |
| `recruiter:blueprints:update` | `recruiter_blueprints` | ✅ | ✅ | ❌ |
| `recruiter:blueprints:delete` | `recruiter_blueprints` | ✅ | ❌ | ❌ |
| **AI Recruiter - Reference Checks** |||||
| `recruiter:reference_checks:access` | `recruiter_reference_checks` | ✅ | ✅ | ✅ |
| `recruiter:reference_checks:create` | `recruiter_reference_checks` | ✅ | ✅ | ❌ |
| `recruiter:reference_checks:read` | `recruiter_reference_checks` | ✅ | ✅ | ✅ |
| `recruiter:reference_checks:manage` | `recruiter_reference_checks` | ✅ | ❌ | ❌ |
| **Administration - Settings** |||||
| `admin:settings:read` | `settings` | ✅ | ❌ | ❌ |
| `admin:settings:update` | `settings` | ✅ | ❌ | ❌ |
| `admin:settings:providers:manage` | `settings` | ✅ | ❌ | ❌ |
| `admin:email:read` | `settings` | ✅ | ❌ | ❌ |
| `admin:email:configure` | `settings` | ✅ | ❌ | ❌ |
| `admin:email:disconnect` | `settings` | ✅ | ❌ | ❌ |
| **Data Connections** |||||
| `connections:read` | `connectors` | ✅ | ❌ | ❌ |
| `connections:create` | `connectors` | ✅ | ❌ | ❌ |
| `connections:update` | `connectors` | ✅ | ❌ | ❌ |
| `connections:delete` | `connectors` | ✅ | ❌ | ❌ |
| `connections:test` | `connectors` | ✅ | ❌ | ❌ |
| `connections:sync` | `connectors` | ✅ | ❌ | ❌ |
| **Users & Roles** |||||
| `users:read` | `users_roles` | ✅ | ❌ | ❌ |
| `users:invite` | `users_roles` | ✅ | ❌ | ❌ |
| `users:update` | `users_roles` | ✅ | ❌ | ❌ |
| `users:deactivate` | `users_roles` | ✅ | ❌ | ❌ |
| `users:delete` | `users_roles` | ✅ | ❌ | ❌ |
| `roles:read` | `users_roles` | ✅ | ❌ | ❌ |
| `roles:create` | `users_roles` | ✅ | ❌ | ❌ |
| `roles:update` | `users_roles` | ✅ | ❌ | ❌ |
| `roles:delete` | `users_roles` | ✅ | ❌ | ❌ |
| `roles:assign` | `users_roles` | ✅ | ❌ | ❌ |
| **Invites** |||||
| `invites:read` | `invites` | ✅ | ❌ | ❌ |
| `invites:create` | `invites` | ✅ | ❌ | ❌ |
| `invites:resend` | `invites` | ✅ | ❌ | ❌ |
| `invites:revoke` | `invites` | ✅ | ❌ | ❌ |
| **Audit** |||||
| `audit:read` | `audit` | ✅ | ❌ | ❌ |
| `audit:export` | `audit` | ✅ | ❌ | ❌ |
| `audit:filter` | `audit` | ✅ | ❌ | ❌ |
| **Labs (Platform Admin Gated)** |||||
| `labs:agents:access` | `ai_providers` | ✅ | ❌ | ❌ |
| `labs:agents:configure` | `ai_providers` | ✅ | ❌ | ❌ |
| `labs:agents:test` | `ai_providers` | ✅ | ❌ | ❌ |
| `labs:resume_parsing:access` | `labs_resume_parsing` | ✅ | ❌ | ❌ |
| `labs:resume_parsing:upload` | `labs_resume_parsing` | ✅ | ❌ | ❌ |
| `labs:resume_parsing:analyze` | `labs_resume_parsing` | ✅ | ❌ | ❌ |

---

## Permissions Currently Used in Code

The following permissions are actively checked in API routes (verified December 30, 2025):

```
admin:settings:read         admin:settings:update
assistant:access            assistant:documents:delete
assistant:documents:read    assistant:documents:upload
assistant:questions:ask     assistant:questions:delete
assistant:questions:read    audit:read
connections:create          connections:delete
connections:read            connections:sync
connections:test            connections:update
labs:agents:configure       labs:resume_parsing:analyze
recruiter:blueprints:create recruiter:blueprints:read
recruiter:config:create     recruiter:results:read
roles:create                roles:read
roles:update                users:invite
users:read                  users:update
```

All permissions used in code are:
- ✅ Defined in the permissions table
- ✅ Mapped to a platform feature
- ✅ Assigned to appropriate roles when features are allocated

---

*Last Updated: December 30, 2025*

