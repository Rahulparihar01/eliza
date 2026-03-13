# Credential Hardening Plan: Single Admin Entry Point

**Goal:** Eliminate all backdoor admin usernames and passwords so the platform has exactly **one** entry point — `admin@eliza.com` with a strong, auto-generated 12-character password — initialized on every fresh build/startup.

---

## Current State: Audit Summary

### How Many Ways Can Someone Get In Today?

There are **8 distinct hardcoded user accounts** spread across **7 scripts**, plus **default credentials in Docker Compose** that act as implicit backdoors. Anyone with access to the source code can log in through any of these.

---

## Finding 1: Hardcoded Admin Users in Scripts

### 1A. `scripts/seed_admin_user.py` (lines 24–26)

| Field | Value |
|-------|-------|
| Email | `scott@eliza.com` |
| Username | `scott` |
| Password | `admin123` |
| Role | `super_admin` |

This script creates a full super-admin with all permissions. It is **idempotent** (skips if user exists) but leaves the account in the database permanently.

### 1B. `scripts/init_rbac.py` (lines 183–191)

| Field | Value |
|-------|-------|
| Email | `admin@ai-enablement.local` |
| Username | `system_admin` |
| Password | `admin123` |
| Role | `super_admin` (is_superuser=True) |

Creates a separate admin user under the `eliza` customer. Different email domain than the primary admin.

### 1C. `scripts/init_rbac_data.py` (lines 254–263)

| Field | Value |
|-------|-------|
| Email | `admin@eliza.com` |
| Username | `admin` |
| Password | `admin123!` |
| Role | `super_admin` (is_superuser=True) |

Note: slightly different password (`admin123!` with exclamation mark). Creates under `default` customer_id.

### 1D. `scripts/create_test_hiring_manager.py` (lines 70–73)

| Field | Value |
|-------|-------|
| Email | `hiringmanager@eliza.com` |
| Username | `sarah` |
| Password | `admin123` |
| Role | `admin` |

Creates a test user with admin role. Has `system:admin` permission.

### 1E. `scripts/create_hr_users.py` (lines 141, 182–186)

Creates **3 users**, all with the same password:

| Email | Password | Role |
|-------|----------|------|
| `laura.sullivan@caylent.com` | `admin123` | `hr_user` |
| `lisa.cohrs@caylent.com` | `admin123` | `hr_user` |
| `sofia.ferrari@caylent.com` | `admin123` | `hr_user` |

### 1F. `scripts/create_caylent_pdl_connector.py` (lines 12–13)

| Field | Value |
|-------|-------|
| Email | `scott@eliza.com` |
| Password | `admin123` |

Logs in via API to create a connector. Uses hardcoded credentials to authenticate.

### 1G. `scripts/utilities/reset_scott_password.py` (line 14)

| Field | Value |
|-------|-------|
| Target | `scott@eliza.com` |
| New Password | `password123` |

Directly updates the database password for scott. No auth required — runs raw SQL.

---

## Finding 2: Default Credentials in Docker Compose

### 2A. `docker/docker-compose.yml` — App Service (lines 238–239)

```yaml
- ADMIN_EMAIL=${ADMIN_EMAIL:-admin@eliza.com}
- ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}
```

If `ADMIN_EMAIL` and `ADMIN_PASSWORD` are not explicitly set in the environment, Docker Compose falls back to `admin@eliza.com` / `admin123`. This feeds into `scripts/init_tenant.py`.

### 2B. `docker/docker-compose.yml` — Flower Monitoring (line 653)

```yaml
- FLOWER_BASIC_AUTH=${FLOWER_BASIC_AUTH:-admin:admin123}
```

Celery Flower monitoring dashboard defaults to `admin:admin123`. This is a separate entry point to view/manage background tasks.

### 2C. `docker/docker-compose.yml` — Langfuse (lines 74–76)

```yaml
LANGFUSE_INIT_USER_EMAIL: ${LF_INIT_USER_EMAIL:-admin@eliza.local}
LANGFUSE_INIT_USER_PASSWORD: ${LF_INIT_USER_PASSWORD:-LangfuseAdmin123!}
```

Langfuse observability dashboard creates its own admin user with default credentials.

### 2D. `docker/docker-compose.yml` — PostgreSQL (line 691)

```yaml
POSTGRES_PASSWORD: password
```

Hardcoded database password. Not an app login, but direct database access.

### 2E. `docker/docker-compose.yml` — Neo4j (line 726)

```yaml
NEO4J_AUTH: neo4j/password
```

Hardcoded graph database credentials. Direct database access.

---

## Finding 3: Default Credentials in Application Config

### 3A. `src/core/config.py` (line 67)

```python
jwt_secret_key: str = Field(default="change-this-secret-key", alias="JWT_SECRET_KEY")
```

Default JWT signing secret. Anyone who knows this can forge authentication tokens for any user.

### 3B. `src/core/config.py` (lines 42, 49)

```python
database_url: str = Field(default="postgresql://postgres:password@postgres:5432/ai_platform", ...)
neo4j_password: str = Field(default="password", ...)
```

Default database passwords in the config fallback. Matches the Docker Compose defaults.

---

## Finding 4: `dev-start.sh` Runs init_tenant.py Unconditionally

### 4A. `dev-start.sh` (line 95)

```bash
docker exec docker-app-1 python scripts/init_tenant.py
```

Every time `dev-start.sh` runs, it executes `init_tenant.py` which uses the Docker Compose default credentials (`admin@eliza.com` / `admin123`) unless env vars are overridden. This **re-creates or re-sets** the admin password on every dev start.

---

## Finding 5: `docker/entrypoint.sh` Conditional Tenant Init

### 5A. `docker/entrypoint.sh` (lines 54–64)

```bash
if [ "$INIT_TENANT" = "true" ]; then
    python scripts/init_tenant.py
fi
```

When `INIT_TENANT=true`, the container entrypoint runs `init_tenant.py`. The `init_tenant.py` script uses an `ON CONFLICT (email) DO UPDATE SET hashed_password = EXCLUDED.hashed_password` which **overwrites** the password every time it runs. This is the correct mechanism to use — but it must use a strong password.

---

## Finding 6: Test and Documentation Files with Credentials

| File | Email | Password |
|------|-------|----------|
| `tests/security/test_audit_integration.py` | `scott@eliza.com` | `admin123` |
| `tests/test_talent_feedback_api.py` | `laura.sullivan@caylent.com` | `admin123` |
| `tests/test_create_filesystem_connector.py` | `scott@eliza.com` | `admin123` |
| `docs/specs/testing/test_tenant_connector_flow.py` | `scott@eliza.com` | `admin123` |
| `docs/architecture/FRONTEND_BLANK_PAGE_DIAGNOSIS.md` | `admin@ai-enablement.com` | `admin123` |
| `northflank/DIAGNOSIS_20251223.md` | `admin@eliza.com` | `admin123` |

---

## Complete Attack Surface Summary

| # | Entry Point | Credential | Source | Severity |
|---|-------------|-----------|--------|----------|
| 1 | App login | `scott@eliza.com` / `admin123` | `seed_admin_user.py` | **CRITICAL** |
| 2 | App login | `admin@ai-enablement.local` / `admin123` | `init_rbac.py` | **CRITICAL** |
| 3 | App login | `admin@eliza.com` / `admin123!` | `init_rbac_data.py` | **CRITICAL** |
| 4 | App login | `admin@eliza.com` / `admin123` | `init_tenant.py` (via docker-compose default) | **CRITICAL** |
| 5 | App login | `hiringmanager@eliza.com` / `admin123` | `create_test_hiring_manager.py` | **HIGH** |
| 6 | App login | `laura.sullivan@caylent.com` / `admin123` | `create_hr_users.py` | **HIGH** |
| 7 | App login | `lisa.cohrs@caylent.com` / `admin123` | `create_hr_users.py` | **HIGH** |
| 8 | App login | `sofia.ferrari@caylent.com` / `admin123` | `create_hr_users.py` | **HIGH** |
| 9 | App login | `scott@eliza.com` / `password123` | `reset_scott_password.py` | **HIGH** |
| 10 | Flower UI | `admin` / `admin123` | `docker-compose.yml` | **HIGH** |
| 11 | Langfuse UI | `admin@eliza.local` / `LangfuseAdmin123!` | `docker-compose.yml` | **MEDIUM** |
| 12 | PostgreSQL | `user` / `password` | `docker-compose.yml` | **MEDIUM** |
| 13 | Neo4j | `neo4j` / `password` | `docker-compose.yml` | **MEDIUM** |
| 14 | JWT Forgery | Anyone with `change-this-secret-key` can forge tokens | `config.py` | **CRITICAL** |

**Total: 14 distinct entry points / attack vectors**

---

## Remediation Plan

### Phase 1: Consolidate to Single Admin Entry Point

#### Task 1.1: Update `scripts/init_tenant.py` to be the ONLY admin creation path

`init_tenant.py` is already the best candidate — it reads from environment variables and uses `ON CONFLICT DO UPDATE`. Changes needed:

- [x] Already requires `ADMIN_EMAIL` and `ADMIN_PASSWORD` env vars
- [ ] Add password strength validation (reject passwords < 12 chars, require complexity)
- [ ] Change the hardcoded email to `admin@eliza.com` (or keep it env-var driven)
- [ ] Log a warning if the password matches any known weak pattern

#### Task 1.2: Remove or disable `scripts/seed_admin_user.py`

- [ ] Delete the file entirely, OR
- [ ] Rename to `scripts/archived/seed_admin_user.py.DEPRECATED` with a comment explaining it's been superseded by `init_tenant.py`
- [ ] Remove the hardcoded `scott@eliza.com` / `admin123` credentials

#### Task 1.3: Remove admin creation from `scripts/init_rbac.py`

- [ ] Remove lines 181–202 that create the `admin@ai-enablement.local` user
- [ ] Keep the role and permission creation logic (that's still needed)
- [ ] The admin user should be created by `init_tenant.py`, not by RBAC init

#### Task 1.4: Remove admin creation from `scripts/init_rbac_data.py`

- [ ] Remove lines 253–284 that create the `admin@eliza.com` / `admin123!` user
- [ ] Keep the role and permission seeding logic
- [ ] The admin user should be created by `init_tenant.py`, not by RBAC data init

#### Task 1.5: Delete `scripts/create_test_hiring_manager.py`

- [ ] Delete entirely — test users should never be created via standalone scripts with hardcoded passwords
- [ ] If a hiring manager test user is needed, create it through the admin UI or via invite flow

#### Task 1.6: Delete `scripts/create_hr_users.py`

- [ ] Delete entirely — HR users should be created through the invite flow or admin UI
- [ ] The 3 Caylent HR users should be provisioned through normal user management

#### Task 1.7: Delete `scripts/utilities/reset_scott_password.py`

- [ ] Delete entirely — password resets should go through the proper auth flow
- [ ] This script bypasses all security controls

#### Task 1.8: Update `scripts/create_caylent_pdl_connector.py`

- [ ] Remove hardcoded `EMAIL` and `PASSWORD` (lines 12–13)
- [ ] Accept credentials via environment variables or CLI arguments
- [ ] Or require an API token instead of username/password

---

### Phase 2: Harden Docker Compose Defaults

#### Task 2.1: Remove default admin password fallback

Change in `docker/docker-compose.yml`:

```yaml
# BEFORE (insecure)
- ADMIN_PASSWORD=${ADMIN_PASSWORD:-admin123}

# AFTER (no fallback — MUST be set explicitly)
- ADMIN_PASSWORD=${ADMIN_PASSWORD:?ADMIN_PASSWORD must be set}
```

Do the same for `ADMIN_EMAIL`:

```yaml
- ADMIN_EMAIL=${ADMIN_EMAIL:?ADMIN_EMAIL must be set}
```

#### Task 2.2: Harden Flower monitoring credentials

```yaml
# BEFORE
- FLOWER_BASIC_AUTH=${FLOWER_BASIC_AUTH:-admin:admin123}

# AFTER
- FLOWER_BASIC_AUTH=${FLOWER_BASIC_AUTH:?FLOWER_BASIC_AUTH must be set}
```

#### Task 2.3: Harden Langfuse default credentials

```yaml
# BEFORE
LANGFUSE_INIT_USER_PASSWORD: ${LF_INIT_USER_PASSWORD:-LangfuseAdmin123!}

# AFTER
LANGFUSE_INIT_USER_PASSWORD: ${LF_INIT_USER_PASSWORD:?LF_INIT_USER_PASSWORD must be set}
```

#### Task 2.4: Harden infrastructure passwords

For PostgreSQL, Neo4j — either:
- Require env vars with no defaults, OR
- Generate random passwords at first boot and persist them

```yaml
# PostgreSQL
POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD must be set}

# Neo4j
NEO4J_AUTH: ${NEO4J_AUTH:?NEO4J_AUTH must be set}
```

---

### Phase 3: Harden Application Config Defaults

#### Task 3.1: Remove default JWT secret

In `src/core/config.py`:

```python
# BEFORE
jwt_secret_key: str = Field(default="change-this-secret-key", ...)

# AFTER — require explicit configuration
jwt_secret_key: str = Field(..., alias="JWT_SECRET_KEY")  # No default, MUST be set
```

Add a startup check in `src/main.py` that refuses to start if `jwt_secret_key` is a known weak value.

#### Task 3.2: Remove default database passwords from config

```python
# BEFORE
database_url: str = Field(default="postgresql://postgres:password@postgres:5432/ai_platform", ...)
neo4j_password: str = Field(default="password", ...)

# AFTER
database_url: str = Field(..., alias="DATABASE_URL")  # No default
neo4j_password: str = Field(..., alias="NEO4J_PASSWORD")  # No default
```

---

### Phase 4: Enforce Single Admin on Every Build

#### Task 4.1: Create a startup admin enforcement mechanism

Add to `scripts/init_tenant.py` or create a new startup step:

1. On every startup (when `INIT_TENANT=true`):
   - Create/update `admin@eliza.com` with the password from `ADMIN_PASSWORD` env var
   - **Deactivate** all other `is_superuser=True` users that are NOT `admin@eliza.com`
   - Log which accounts were deactivated

```python
# Deactivate any other superuser accounts
db.execute(text("""
    UPDATE users 
    SET is_active = false, is_superuser = false
    WHERE is_superuser = true 
    AND email != :admin_email
"""), {"admin_email": admin_email})
```

2. Add a password strength check:

```python
import re

def validate_admin_password(password: str) -> bool:
    if len(password) < 12:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True
```

#### Task 4.2: Update `dev-start.sh`

- [ ] Ensure `dev-start.sh` sets `ADMIN_EMAIL=admin@eliza.com` and requires `ADMIN_PASSWORD` from `.env` or prompts for it
- [ ] Remove the unconditional `init_tenant.py` call or gate it behind proper credential sourcing

#### Task 4.3: Update `docker/entrypoint.sh`

The entrypoint is already correct (gated behind `INIT_TENANT=true`). No changes needed.

---

### Phase 5: Clean Up Test Files

#### Task 5.1: Remove hardcoded credentials from tests

Update these files to use environment variables or test fixtures:

- [ ] `tests/security/test_audit_integration.py` — use `os.environ.get("TEST_ADMIN_EMAIL")`
- [ ] `tests/test_talent_feedback_api.py` — use env vars or pytest fixtures
- [ ] `tests/test_create_filesystem_connector.py` — use env vars
- [ ] `docs/specs/testing/test_tenant_connector_flow.py` — use env vars

#### Task 5.2: Scrub documentation

- [ ] Remove real credentials from `docs/architecture/FRONTEND_BLANK_PAGE_DIAGNOSIS.md`
- [ ] Remove real credentials from `northflank/DIAGNOSIS_20251223.md`
- [ ] Replace with placeholder like `<your-admin-password>`

---

### Phase 6: Update `.env.template`

#### Task 6.1: Add strong password requirement

```bash
# Platform Admin (REQUIRED - no defaults)
ADMIN_EMAIL=admin@eliza.com
ADMIN_PASSWORD=  # Must be >= 12 chars with uppercase, lowercase, digits, and special chars

# Flower Monitoring (REQUIRED)
FLOWER_BASIC_AUTH=admin:<strong-password-here>

# JWT Secret (REQUIRED - generate with: openssl rand -hex 32)
JWT_SECRET_KEY=

# Database (REQUIRED)
POSTGRES_PASSWORD=
NEO4J_AUTH=neo4j/<strong-password-here>

# Langfuse (REQUIRED)
LF_INIT_USER_PASSWORD=
```

---

## Desired End State

After all changes, the platform should work like this:

```
┌──────────────────────────────────────────────────────────┐
│ Fresh Build / Container Start                            │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. Docker reads ADMIN_PASSWORD from .env (required)     │
│  2. entrypoint.sh runs init_tenant.py                    │
│  3. init_tenant.py:                                      │
│     a. Validates password >= 12 chars + complexity        │
│     b. Creates/updates admin@eliza.com                   │
│     c. Deactivates all other superusers                  │
│  4. App starts with ONE admin: admin@eliza.com           │
│                                                          │
│  No other scripts create users.                          │
│  No hardcoded passwords exist anywhere.                  │
│  No default fallback passwords in docker-compose.        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Single Entry Point

| Field | Value |
|-------|-------|
| Email | `admin@eliza.com` |
| Password | Set via `ADMIN_PASSWORD` env var (12+ chars, complex) |
| Role | `platform_admin` with `is_superuser=True` |
| Created by | `scripts/init_tenant.py` on startup |

All other users must be created through:
- The admin UI (user management)
- The invite flow (email invitations)
- SSO (OIDC/SAML JIT provisioning)

---

## Files to Modify/Delete

### Delete (7 files)

| File | Reason |
|------|--------|
| `scripts/seed_admin_user.py` | Replaced by `init_tenant.py` |
| `scripts/create_test_hiring_manager.py` | Hardcoded test user |
| `scripts/create_hr_users.py` | Hardcoded HR users |
| `scripts/utilities/reset_scott_password.py` | Backdoor password reset |

### Modify (10+ files)

| File | Change |
|------|--------|
| `scripts/init_tenant.py` | Add password validation, add superuser deactivation |
| `scripts/init_rbac.py` | Remove admin user creation (lines 181–202) |
| `scripts/init_rbac_data.py` | Remove admin user creation (lines 253–284) |
| `scripts/create_caylent_pdl_connector.py` | Replace hardcoded creds with env vars |
| `docker/docker-compose.yml` | Remove all default password fallbacks |
| `src/core/config.py` | Remove default JWT secret and DB passwords |
| `dev-start.sh` | Require `ADMIN_PASSWORD` from `.env` |
| `.env.template` | Document required strong passwords |
| `tests/security/test_audit_integration.py` | Use env vars for credentials |
| `tests/test_talent_feedback_api.py` | Use env vars for credentials |
| `tests/test_create_filesystem_connector.py` | Use env vars for credentials |
| `docs/specs/testing/test_tenant_connector_flow.py` | Use env vars for credentials |
| `docs/architecture/FRONTEND_BLANK_PAGE_DIAGNOSIS.md` | Scrub credentials |

---

## Implementation Priority

| Priority | Phase | Effort | Impact |
|----------|-------|--------|--------|
| **P0** | Phase 1 (Remove scripts) | Low | Eliminates 8 backdoor accounts |
| **P0** | Phase 4.1 (Superuser enforcement) | Medium | Guarantees single admin |
| **P1** | Phase 2 (Docker defaults) | Low | Prevents accidental weak creds |
| **P1** | Phase 3 (Config defaults) | Low | Prevents JWT forgery |
| **P2** | Phase 4.2–4.3 (Dev scripts) | Low | Consistent dev experience |
| **P3** | Phase 5 (Tests/docs) | Low | Clean up references |
| **P3** | Phase 6 (.env.template) | Low | Documentation |
