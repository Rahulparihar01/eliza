# ELIZA Accelerate - Adoption Analytics Deployment Guide

## Platform Overview

ELIZA Accelerate is a multi-tenant AI enablement platform. This deployment package includes the **Adoption Analytics** applet, which provides a dashboard for monitoring ChatGPT Enterprise usage across your organization. It syncs conversation metadata, GPT catalog data, and user activity from the OpenAI Compliance API into a local PostgreSQL database and presents it through an interactive dashboard with usage trends, top GPTs, top users, model breakdowns, and cross-team sharing.

No message content is stored -- only metadata (conversation counts, timestamps, user emails, GPT names).

---

## What's in This Package

```
docs/deployment/docker-compose/adoption/
├── docker-compose.yml    # All services, ready to run
├── .env.template         # Configuration template (copy to .env)
└── README.md             # This file
```

---

## 1. Docker Images and Container Registry

The platform ships as **two Docker images**:

| Image | Description |
|-------|-------------|
| `eliza-backend` | Python 3.12 / FastAPI application. Used by the API server, Celery worker, and Celery Beat scheduler (same image, different commands). |
| `eliza-frontend` | React SPA served by nginx. Nginx proxies `/v1/*` API calls to the backend container. |

### Pulling images from GHCR

Images are published to our private GitHub Container Registry. We will provide you with a read-only access token (`GHCR_TOKEN`).

**One-time authentication:**
```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u eliza-platform --password-stdin
```

**Pull the images:**
```bash
docker pull ghcr.io/eliza-platform/eliza-backend:latest
docker pull ghcr.io/eliza-platform/eliza-frontend:latest
```

The `.env.template` is pre-configured with the GHCR registry prefix. If you receive a specific version tag from us, update `ELIZA_IMAGE_TAG` in your `.env`:
```
ELIZA_IMAGE_REGISTRY=ghcr.io/eliza-platform/
ELIZA_IMAGE_TAG=1.0.0
```

**Docker credentials persistence:** After the `docker login` above, credentials are saved to `~/.docker/config.json` and will be used automatically by `docker compose pull`. For CI/CD or automated deployments, store the GHCR token as a secret and run the login step before pulling.

---

## 2. Docker Compose File

The included `docker-compose.yml` defines six services:

| Service | Image | Role | Scales? |
|---------|-------|------|---------|
| `frontend` | `eliza-frontend` | Serves the React UI and proxies API calls to `app` via nginx | Yes |
| `app` | `eliza-backend` | FastAPI API server. Runs database migrations on startup. | Yes |
| `celery-worker` | `eliza-backend` | Processes background adoption sync tasks | Yes |
| `celery-beat` | `eliza-backend` | Cron scheduler that dispatches sync jobs | **No -- singleton only** |
| `postgres` | `postgres:15` | Primary data store | N/A (managed in prod) |
| `redis` | `redis:7-alpine` | Celery message broker and result backend | N/A (managed in prod) |

### Quick start

```bash
cd docs/deployment/docker-compose/adoption
cp .env.template .env
# Edit .env -- at minimum set: ADMIN_PASSWORD, DB_PASSWORD, OPENAI_API_KEY, ENCRYPTION_KEY

# Authenticate with GHCR (one-time)
echo "$GHCR_TOKEN" | docker login ghcr.io -u eliza-platform --password-stdin

# Pull images and start
docker compose pull
docker compose up -d
```

The app takes ~1-2 minutes to start on first boot (runs database migrations and creates the initial tenant). Watch progress with:
```bash
docker compose logs -f app
```

Once you see `Started application`, open http://localhost:3000 and log in with your `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### Startup order

Docker Compose handles this automatically via `depends_on` + health checks:

```
postgres, redis  (start first, must be healthy)
       ↓
      app        (waits for postgres + redis, runs migrations)
       ↓
 celery-worker   (waits for app to be healthy)
 celery-beat     (waits for redis to be healthy)
       ↓
   frontend      (waits for app to be healthy)
```

---

## 3. Environment Variables and Secrets

All configuration is done through environment variables defined in the `.env` file. See `.env.template` for the full list with descriptions.

### Required variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ADMIN_EMAIL` | Initial admin login email | `admin@yourcompany.com` |
| `ADMIN_PASSWORD` | Initial admin login password | Strong password |
| `CUSTOMER_ID` | Your organization identifier | `yourcompany` |
| `CUSTOMER_NAME` | Display name for your organization | `Your Company Name` |
| `OPENAI_API_KEY` | OpenAI API key with `compliance_export` scope | `sk-proj-...` |
| `ENCRYPTION_KEY` | Fernet key for encrypting secrets at rest | See generation command in `.env.template` |
| `DB_PASSWORD` | PostgreSQL password | Strong password |

### Optional / have sensible defaults

| Variable | Default | Description |
|----------|---------|-------------|
| `INIT_TENANT` | `true` | Set to `false` after first successful boot |
| `DB_HOST` | `postgres` | Change if using external RDS |
| `DB_PORT` | `5432` | |
| `DB_USER` | `eliza` | |
| `DB_NAME` | `ai_enablement` | |
| `REDIS_HOST` | `redis` | Change if using external ElastiCache |
| `REDIS_PORT` | `6379` | |
| `FRONTEND_PORT` | `3000` | Host port for the UI |
| `APP_PORT` | `5001` | Host port for the API (direct access) |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS origins, comma-separated |
| `FRONTEND_URL` | `http://localhost:3000` | Used in email invite links |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ELIZA_IMAGE_REGISTRY` | `ghcr.io/eliza-platform/` | GHCR registry prefix |
| `ELIZA_IMAGE_TAG` | `latest` | Image tag to deploy |

### Secrets handling

For production, we recommend storing sensitive values in **AWS Secrets Manager** or **AWS Systems Manager Parameter Store** rather than in a `.env` file on disk. The variables that contain secrets are:

- `ADMIN_PASSWORD`
- `DB_PASSWORD`
- `OPENAI_API_KEY`
- `ENCRYPTION_KEY`

---

## 4. Minimum Resource Requirements

### Per-service resources

| Service | CPU (min) | CPU (limit) | Memory (min) | Memory (limit) |
|---------|-----------|-------------|--------------|----------------|
| `frontend` | 0.25 vCPU | 0.5 vCPU | 256 MB | 512 MB |
| `app` | 1 vCPU | 2 vCPU | 2 GB | 4 GB |
| `celery-worker` | 1 vCPU | 2 vCPU | 2 GB | 4 GB |
| `celery-beat` | 0.25 vCPU | 0.5 vCPU | 512 MB | 1 GB |
| `postgres` | 0.5 vCPU | 1 vCPU | 512 MB | 2 GB |
| `redis` | 0.25 vCPU | 0.5 vCPU | 256 MB | 512 MB |

### Host machine total

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| **CPU** | 4 vCPU | 8 vCPU |
| **Memory** | 8 GB | 16 GB |
| **Disk** | 20 GB | 50 GB (mostly PostgreSQL data growth) |
| **OS** | Any Linux with Docker 24+ and Docker Compose v2 | Amazon Linux 2023, Ubuntu 22.04+ |

### Recommended AWS instance types (single-host Docker Compose)

| Instance | vCPU | Memory | Monthly (on-demand) | Notes |
|----------|------|--------|---------------------|-------|
| `t3.xlarge` | 4 | 16 GB | ~$120 | Minimum for evaluation |
| `m6i.xlarge` | 4 | 16 GB | ~$140 | Better sustained performance |
| `m6i.2xlarge` | 8 | 32 GB | ~$280 | Room to grow |

### Storage

| Volume | Expected size | Growth rate |
|--------|--------------|-------------|
| `postgres_data` | 1-10 GB | ~50 MB/month per 1000 daily conversations |
| `redis_data` | < 100 MB | Minimal (transient task data) |
| `app_data` | < 1 GB | Minimal |
| `app_logs` | 1-5 GB | Depends on log level, rotate with Docker log driver |

### Production upgrade path

For production workloads, replace the bundled PostgreSQL and Redis containers with managed AWS services:

| Component | Managed Service | Recommended SKU |
|-----------|----------------|-----------------|
| PostgreSQL | Amazon RDS for PostgreSQL 15 | `db.t3.medium` (Multi-AZ) |
| Redis | Amazon ElastiCache for Redis 7.x | `cache.t3.small` |

To switch, update `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `REDIS_HOST`, `REDIS_PORT` in your `.env` and remove the `postgres` and `redis` services from `docker-compose.yml`.

---

## 5. Network and Port Mapping

### Exposed ports (host-accessible)

| Port | Service | Protocol | Purpose |
|------|---------|----------|---------|
| **3000** | `frontend` | HTTP | Web UI -- **primary user access point** |
| **5001** | `app` | HTTP | REST API (direct access, optional) |
| **5432** | `postgres` | TCP | PostgreSQL (optional, for external DB tools) |
| **6379** | `redis` | TCP | Redis (optional, for debugging) |

In production, only port **3000** (or your HTTPS proxy port) needs to be exposed to end users. Ports 5001, 5432, and 6379 can be restricted to the private network.

### Internal service communication (Docker network)

All containers communicate over the internal `eliza` Docker bridge network. No host ports are needed for internal traffic.

```
frontend (nginx)  ──── /v1/* ────▶  app:5001    (API)
                                      │
                                      ├────────▶  postgres:5432
                                      └────────▶  redis:6379

celery-worker     ─────────────────▶  postgres:5432
                  ─────────────────▶  redis:6379
                  ─────────────────▶  api.chatgpt.com:443  (outbound HTTPS)

celery-beat       ─────────────────▶  redis:6379
```

### Outbound network requirements

The platform requires outbound HTTPS (port 443) access to:

| Destination | Purpose | Required? |
|-------------|---------|-----------|
| `api.chatgpt.com` | OpenAI Compliance API (adoption data sync) | Yes |
| `ghcr.io` | Pull Docker images from GitHub Container Registry | Yes (at deploy time) |

No other outbound access is needed. The adoption applet does not call OpenAI's chat/completions API.

### Reverse proxy / load balancer (production)

For production, place an ALB, nginx, or Caddy in front of port 3000 with TLS termination:

```
Internet ── HTTPS:443 ──▶ ALB/nginx ── HTTP:3000 ──▶ frontend container
```

If using an ALB with path-based routing directly (without the frontend nginx proxy), the rules are:

| Path | Target | Port |
|------|--------|------|
| `/v1/*` | `app` | 5001 |
| `/api/*` | `app` | 5001 |
| `/docs`, `/redoc`, `/openapi.json` | `app` | 5001 |
| `/health/ready` | `app` | 5001 |
| `/*` (default) | `frontend` | 80 |

### Health check endpoints

| Endpoint | Service | Purpose |
|----------|---------|---------|
| `GET /` | frontend | Nginx liveness |
| `GET /health` | frontend | Nginx health (returns `200 healthy`) |
| `GET /health/ready` | app | Full readiness (DB connected, migrations complete) |

---

## 6. AWS / IAM Permissions

### Minimal EC2 instance permissions

Since images are pulled from GHCR (not ECR), **no IAM permissions are required at runtime**. The platform does not call any AWS services for the adoption applet.

The EC2 instance only needs:
- Docker 24+ and Docker Compose v2 installed
- GHCR credentials stored via `docker login` (see Section 1)
- Outbound HTTPS access to `ghcr.io` (deploy time) and `api.chatgpt.com` (runtime)

### Optional: If using managed AWS data stores

Add these if you replace the bundled containers with RDS and ElastiCache:

| Permission | Why |
|------------|-----|
| `rds-db:connect` | Connect to RDS via IAM auth (if using IAM auth instead of password) |
| VPC/security group access | RDS and ElastiCache must be reachable from the EC2 instance's VPC/subnet |

### Optional: If using AWS Secrets Manager

```json
{
  "Sid": "ReadSecrets",
  "Effect": "Allow",
  "Action": ["secretsmanager:GetSecretValue"],
  "Resource": "arn:aws:secretsmanager:*:*:secret:eliza/*"
}
```

### Security group rules (if running on EC2)

| Direction | Port | Source | Purpose |
|-----------|------|--------|---------|
| Inbound | 443 (or 3000) | Your users' IP range / VPN | Web UI access |
| Inbound | 22 | Your admin IP range | SSH (optional) |
| Outbound | 443 | `0.0.0.0/0` | OpenAI API (`api.chatgpt.com`) + GHCR (`ghcr.io`) |
| Outbound | 5432 | RDS security group | Only if using external RDS |
| Outbound | 6379 | ElastiCache security group | Only if using external Redis |

---

## Post-Deployment Setup

### 1. Log in and configure adoption sync

1. Open `http://<your-host>:3000` (or your domain)
2. Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`
3. Go to **Admin Settings** > **AI Providers**
4. Add an **OpenAI** provider:
   - Paste your ChatGPT Enterprise **Compliance API key** (needs `compliance_export` scope)
   - Enter your **ChatGPT Workspace ID**
   - Enable the provider as an adoption data source
5. Go to **Adoption Settings**:
   - Set the **sync start date** (how far back to pull historical data)
   - Enable the **scheduled sync** (runs automatically on your chosen schedule)
6. Click **Sync Now** to trigger the first data pull and verify connectivity

### 2. Disable first-time initialization

After the first successful boot, update your `.env`:
```
INIT_TENANT=false
```
Then restart:
```bash
docker compose up -d app
```

### 3. Verify everything is running

```bash
# All containers should show "Up" and "(healthy)"
docker compose ps

# Check API health
curl http://localhost:5001/health/ready

# Watch adoption sync logs
docker compose logs -f celery-worker
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| App container keeps restarting | `docker compose logs app` -- likely DB connection issue or missing env vars |
| "relation does not exist" errors | Migrations didn't run. Check `RUN_MIGRATIONS=true` is set on `app` only |
| Adoption sync fails | Check `celery-worker` logs. Verify `OPENAI_API_KEY` has `compliance_export` scope and worker can reach `api.chatgpt.com:443` |
| Frontend shows blank page | `docker compose logs frontend` -- verify `app` is healthy first |
| Can't log in | Verify `INIT_TENANT=true` was set on first boot. Check `app` logs for tenant initialization output |
| Port conflict | Change `FRONTEND_PORT`, `APP_PORT`, `DB_PORT`, or `REDIS_PORT` in `.env` |

---

## Updating

To deploy a new version:

```bash
# Pull new images from GHCR
docker compose pull

# Restart services (app runs migrations automatically)
docker compose up -d
```

The `app` container runs database migrations on every startup, so schema changes are applied automatically. No manual migration step is needed.
