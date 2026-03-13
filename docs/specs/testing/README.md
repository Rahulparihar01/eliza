# Permission Testing

This folder contains API-based tests for verifying permission enforcement.

## Philosophy

All tests in this folder:
- **Use the API exactly as the frontend would** - no direct database access
- **Test permission enforcement** - verify users can/cannot access endpoints based on their roles
- **Are reproducible** - can be run repeatedly without side effects

## Test Files

| File | Description |
|------|-------------|
| `test_connector_permissions.py` | Tests for `connections:*` permissions on connector endpoints |
| `quick_permission_test.py` | Quick script to manually test permissions for a specific user |

## Running Tests

### Prerequisites

1. Local environment running:
   ```bash
   cd docker && docker compose up -d
   ```

2. Test users exist with appropriate roles (platform_admin, admin, editor, viewer)

### Run All Connector Permission Tests

```bash
cd docs/specs/testing
pytest test_connector_permissions.py -v
```

### Run Quick Smoke Test Only

```bash
pytest test_connector_permissions.py -v -k "smoke"
```

### Run Quick Manual Test

```bash
python quick_permission_test.py
```

## Test Users

For full test coverage, you need users with these roles:

| Role | Expected Connector Access |
|------|--------------------------|
| `platform_admin` | Full access (all `connections:*` permissions) |
| `admin` (tenant) | Full access within their tenant |
| `editor` (tenant) | NO access (connections are admin-only) |
| `viewer` (tenant) | NO access (connections are admin-only) |

## Expected Results

### Platform Admin / Tenant Admin

```
GET  /api/connectors/types           → 200 OK
GET  /api/connectors/configurations  → 200 OK
POST /api/connectors/configurations  → 201 Created (or 400/500 if validation fails)
POST /api/connectors/test-connection → 200 OK (or error if connection fails)
GET  /api/connectors/sync-runs       → 200 OK
```

### Editor / Viewer

```
GET  /api/connectors/types           → 403 Forbidden
GET  /api/connectors/configurations  → 403 Forbidden
POST /api/connectors/configurations  → 403 Forbidden
POST /api/connectors/test-connection → 403 Forbidden
GET  /api/connectors/sync-runs       → 403 Forbidden
```

### Unauthenticated

```
All endpoints → 401 Unauthorized
```

## Debugging Permission Issues

If a user is getting unexpected 403 errors:

1. **Check the user's roles** via `/api/v1/auth/me`
2. **Check the role's permissions** - the admin role should have `connections:*`
3. **Verify the permission exists** - `connections:read`, `connections:create`, etc.
4. **Check feature allocation** - the tenant must have the `connectors` feature allocated

## Adding New Tests

When adding new permission tests:

1. Create a new test file: `test_<feature>_permissions.py`
2. Follow the same pattern as `test_connector_permissions.py`
3. Use fixtures for authenticated sessions
4. Test both positive cases (user HAS permission) and negative cases (user LACKS permission)
5. Always test unauthenticated access (should be 401)

