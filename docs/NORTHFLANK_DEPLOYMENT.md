# Northflank Deployment Guide

This document captures all the lessons learned deploying the Eliza Platform to Northflank.

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Required Environment Variables](#required-environment-variables)
- [Service Configuration](#service-configuration)
- [Common Issues and Fixes](#common-issues-and-fixes)
- [Initial Setup Checklist](#initial-setup-checklist)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Cloudflare                               │
│                    (DNS, SSL, CDN, WAF)                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                         Northflank                               │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Frontend   │────▶│   Backend    │────▶│   Postgres   │    │
│  │  (nginx:80)  │     │  (app:5001)  │     │    (:5432)   │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         │                    │                                   │
│         │              ┌─────┴─────┐                            │
│         │              │           │                            │
│         │        ┌─────┴───┐ ┌─────┴───┐                       │
│         │        │ Celery  │ │  Redis  │                       │
│         │        │ Workers │ │ (:6379) │                       │
│         │        └─────────┘ └─────────┘                       │
│         │                                                       │
│         └──── nginx proxies /v1/* and /api/* to backend        │
└─────────────────────────────────────────────────────────────────┘
```

### Services

| Service | Image | Port | CMD Override |
|---------|-------|------|--------------|
| **frontend** | `elizaplatform-frontend:dev-latest` | 80 | (default) |
| **app** | `elizaplatform-backend:dev-latest` | 5001 | (default) |
| **celery-worker** | `elizaplatform-backend:dev-latest` | - | `python -m celery -A src.celery_app worker --loglevel=info` |
| **celery-ingestion** | `elizaplatform-backend:dev-latest` | - | `python -m celery -A src.celery_app worker --loglevel=info --concurrency=2 --max-tasks-per-child=10 -Q ingestion --prefetch-multiplier=1` |
| **celery-beat** | `elizaplatform-backend:dev-latest` | - | `python -m celery -A src.celery_app beat --loglevel=info` |
| **flower** | `elizaplatform-backend:dev-latest` | 5555 | `python -m celery -A src.celery_app flower --port=5555` |
| **postgres** | `postgres:15` | 5432 | - |
| **redis** | `redis:7` | 6379 | - |

---

## Required Environment Variables

### Backend (app) Service - Critical

```json
{
  "ALLOWED_HOSTS": "p01--frontend--<project>.code.run,p01--app--<project>.code.run,app,localhost,127.0.0.1",
  "ALLOWED_ORIGINS": "https://p01--frontend--<project>.code.run,http://localhost:3000",
  "RUN_MIGRATIONS": "true",
  "DATABASE_URL": "postgresql://user:password@postgres:5432/ai_enablement",
  "REDIS_URL": "redis://redis:6379/0",
  
  // Platform & Tenant Initialization (first-time setup only)
  "INIT_TENANT": "true",
  "ADMIN_EMAIL": "admin@yourcompany.com",
  "ADMIN_PASSWORD": "secure-password-change-me",
  "CUSTOMER_ID": "your-customer-id",
  "CUSTOMER_NAME": "Your Company Name",
  
  // Frontend URL (REQUIRED for invite links)
  "FRONTEND_URL": "https://your-frontend-domain.com"
}
```

### Frontend (nginx) Service

Set on the **frontend** service so nginx can reach the backend. Required on Northflank when the app service name is not `app`.

```json
{
  "BACKEND_HOST": "elizaplatform-app-branchbuild",
  "BACKEND_PORT": "5001"
}
```

- **BACKEND_HOST**: Internal hostname of the app service (e.g. `elizaplatform-app-branchbuild` for branch builds). Omit for Docker Compose (defaults to `app`).
- **BACKEND_PORT**: Backend port (default `5001`).

### Platform Tenant Architecture

The init script creates:
1. **`platform` tenant** - Special tenant for platform-level resources
2. **Platform Admin user** - Belongs to `platform` tenant, has super_admin privileges
3. **Customer tenant** (optional) - Created from `CUSTOMER_ID` env var

```
┌─────────────────────────────────────────────────────────────────┐
│                     PLATFORM TENANT ("platform")                 │
│  - Platform admin user belongs here                              │
│  - Platform-level AI providers owned by this tenant              │
│  - Platform features managed here                                │
└─────────────────────────────────────────────────────────────────┘
         │ manages
         ▼
┌─────────────────────┐  ┌─────────────────────┐
│  Customer Tenant    │  │  Customer Tenant    │
│  e.g., "caylent"    │  │  e.g., "acme"       │
└─────────────────────┘  └─────────────────────┘
```

**IMPORTANT:** After first-time setup, set `INIT_TENANT=false` or remove it
```

### Why ALLOWED_HOSTS is Critical

The `TrustedHostMiddleware` checks the HTTP `Host` header. You MUST include:

| Host | Why |
|------|-----|
| `p01--frontend--xxx.code.run` | Frontend nginx passes this as Host header when proxying |
| `p01--app--xxx.code.run` | Direct access to backend |
| `app` | Internal service-to-service communication |
| `localhost` | Local development |
| `127.0.0.1` | Health check probes from Northflank |

**Without `127.0.0.1`, health checks fail with 400 and the service won't become healthy!**

### Celery Services

Celery workers use the same backend image but DON'T need:
- `ALLOWED_HOSTS` (no HTTP traffic)
- `ALLOWED_ORIGINS` (no CORS)
- `RUN_MIGRATIONS` (only app should run migrations)
- `INIT_TENANT` (only app should initialize)

They DO need:
- `DATABASE_URL`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`

---

## Service Configuration

### CMD Override for Celery

Northflank wraps commands with its own entrypoint. The `celery` binary isn't in PATH, so use:

```
python -m celery -A src.celery_app worker --loglevel=info
```

**NOT:**
```
celery -A src.celery_app worker --loglevel=info  # ❌ Will fail with "celery: not found"
```

### Health Checks

The backend health check should hit `/health/ready` internally at `127.0.0.1:5001`.

If health checks return 400:
1. Check `ALLOWED_HOSTS` includes `127.0.0.1`
2. Check backend logs for "Invalid host header"

---

## Common Issues and Fixes

### Issue: "Invalid host header"

**Cause:** `TrustedHostMiddleware` rejecting the Host header.

**Fix:** Add the domain to `ALLOWED_HOSTS`:
```
ALLOWED_HOSTS=domain1.code.run,domain2.code.run,app,localhost,127.0.0.1
```

### Issue: Health check returns 400

**Cause:** `127.0.0.1` not in `ALLOWED_HOSTS`.

**Fix:** Add `127.0.0.1` to `ALLOWED_HOSTS`.

### Issue: "celery: not found"

**Cause:** Northflank's entrypoint wrapper doesn't have `/usr/local/bin` in PATH.

**Fix:** Use `python -m celery` instead of `celery`.

### Issue: Login returns "user not found"

**Cause:** User's `customer_id` doesn't match the app's `CUSTOMER_ID` config.

**Fix:** Ensure user's `customer_id` matches the `CUSTOMER_ID` environment variable.

### Issue: Login returns "password incorrect"

**Cause:** Password hash is invalid or generated incorrectly.

**Fix:** Generate a proper bcrypt hash:
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

### Issue: Account locked

**Cause:** Too many failed login attempts.

**Fix:**
```sql
UPDATE users 
SET failed_login_attempts = 0, locked_until = NULL 
WHERE email = 'user@example.com';
```

### Issue: Init tenant script fails

**Cause:** `DATABASE_URL` not passed to Python script.

**Fix:** The script should use environment variables directly. See the fixed `init_tenant.py`.

---

## Initial Setup Checklist

### 1. Deploy Infrastructure Services First
- [ ] PostgreSQL
- [ ] Redis
- [ ] Elasticsearch (if using)
- [ ] Logstash (if using)

### 2. Deploy Backend (app)
- [ ] Set all environment variables (see above)
- [ ] Set `RUN_MIGRATIONS=true`
- [ ] Set `INIT_TENANT=true` for first deploy
- [ ] Verify health check passes

### 3. Create Admin User (if INIT_TENANT didn't work)

Connect to postgres and run:
```sql
-- Create customer first
INSERT INTO customers (customer_id, name, display_name, is_active, subscription_tier, created_at, updated_at)
VALUES ('your-customer-id', 'Your Company', 'Your Company', true, 'enterprise', NOW(), NOW())
ON CONFLICT (customer_id) DO NOTHING;

-- Create admin user
-- First generate hash: python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
INSERT INTO users (email, username, full_name, hashed_password, is_active, is_superuser, customer_id, failed_login_attempts, created_at, updated_at)
VALUES (
    'admin@yourcompany.com',
    'admin',
    'Admin User',
    '$2b$12$YOUR_GENERATED_HASH_HERE',
    true,  -- IMPORTANT: must be true
    true,
    'your-customer-id',  -- Must match CUSTOMER_ID env var
    0,  -- Reset failed attempts
    NOW(),
    NOW()
)
ON CONFLICT (email) DO UPDATE SET 
    is_active = true,
    is_superuser = true,
    failed_login_attempts = 0,
    locked_until = NULL;
```

### 4. Deploy Frontend
- [ ] Expose port 80
- [ ] Set **BACKEND_HOST** to the internal hostname of your app service (required on Northflank)

**Backend host (BACKEND_HOST):** The frontend image uses a template and substitutes `BACKEND_HOST` and `BACKEND_PORT` at container start. Defaults are `app` and `5001` (Docker Compose). On Northflank the app service has a different internal name (e.g. `elizaplatform-app-branchbuild`). Set the **frontend** service env var:

- **BACKEND_HOST** = internal hostname of the app service (e.g. `elizaplatform-app-branchbuild` for branch builds, or your app service name from Northflank)
- **BACKEND_PORT** = `5001` (optional; default is 5001)

Without this, nginx fails at startup with `host not found in upstream "app"` because `app` is only resolvable in Docker Compose.

### 5. Deploy Celery Workers
- [ ] Use `python -m celery` command
- [ ] Verify they connect to Redis and database

### 6. Verify Everything
- [ ] Health check: `https://your-backend/v1/health`
- [ ] Login: Try with curl first
- [ ] Frontend: Navigate and login

---

## Updating the Deployment

### Code Changes
1. Push to `dev` branch
2. GitHub Actions builds new image
3. Northflank auto-pulls `dev-latest` tag
4. Service restarts automatically

### Environment Variable Changes
1. Update in Northflank UI
2. Service restarts automatically
3. No rebuild needed

### Database Migrations
1. Migrations run on app startup if `RUN_MIGRATIONS=true`
2. Only `app` service should run migrations (not celery workers)

---

## Security Notes

1. **Change default passwords** immediately after first login
2. **Remove `INIT_TENANT=true`** after initial setup
3. **Use Northflank secrets** for sensitive values (DATABASE_URL, API keys)
4. **Set up Cloudflare** for DDoS protection and SSL

---

## Quick Reference

### Test Backend Directly
```bash
curl https://p01--app--xxx.code.run/v1/health
```

### Test Login
```bash
curl -X POST https://p01--app--xxx.code.run/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "yourpassword"}'
```

### Connect to Postgres
```bash
# In Northflank postgres shell
psql -U user -d ai_enablement
```

### Generate Password Hash
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

### Unlock User Account
```sql
UPDATE users 
SET failed_login_attempts = 0, locked_until = NULL 
WHERE email = 'user@example.com';
```

