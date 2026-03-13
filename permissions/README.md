# Permissions & RBAC Overview

## Role Hierarchy

The platform uses a single-tenant RBAC model with hierarchical inheritance:

```
viewer → analyst → manager → admin → super_admin
```

Each role inherits all permissions granted to its parent. Assigning `super_admin` automatically grants the full system access.

## Backend Flow

1. **Authentication**
   - `/v1/auth/login` authenticates credentials and returns tokens plus a `UserProfile` snapshot.
2. **Current User**
   - `/v1/auth/me` reloads the active user, eagerly loads roles/permissions, computes the primary role, and responds with:
     - `roles`: list of role names
     - `permissions`: flattened list of unique permission strings (including inherited)
     - `is_superuser`: Boolean flag
3. **Role Inheritance**
   - Database `roles.parent_role_id` encodes the hierarchy.
   - `Role.get_permissions()` recursively collects permissions through the chain.

## Frontend Flow

1. **State Management**
   - `AuthContext` calls `/v1/auth/login` and `/v1/auth/me`, feeding the Zustand store (`useAuth`).
   - Store exposes helpers `hasPermission`, `hasAnyPermission`, `hasAllPermissions`, `hasRole`.
2. **Route Guards / UI**
   - Layouts and components call these helpers to gate navigation (e.g., Quick Actions, admin pages).

## Assigning Users

- Assign a role by inserting into `user_roles` (e.g., via admin UI or SQL).
- For superusers, ensure `is_superuser=true` and assign `super_admin` role.
- With inheritance, only the top-level role needs to be managed (e.g., demoting an `admin` automatically limits access).

## Permissions Naming

Permissions follow the pattern `resource:action`. Wildcards like `documents:*` grant all actions for a resource.

Examples:
- `documents:read`
- `documents:upload`
- `search:execute`
- `models:*`

## Future Enhancements

- Seed script to auto-assign `super_admin` to platform admins.
- Admin UI for role/permission management.
- Audit log review when permissions change.










