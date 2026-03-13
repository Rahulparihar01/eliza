# Common Actions Quick Reference

> **Purpose:** Quick reference for frequently needed operations: local dev, deployment, database access, and debugging. Check this before running any infrastructure command.

---

## Quick Reference

```bash
# ✅ Most-used commands
./dev-start.sh                    # Start everything (frontend local)
./dev-stop.sh                     # Stop everything

cd docker
docker-compose build app celery-worker   # Rebuild after code changes
docker-compose up -d app celery-worker   # Restart with new images
docker-compose ps                        # Check status
docker-compose logs -f app               # View logs

docker exec -it docker-postgres-1 psql -U user -d ai_enablement  # Database shell
docker exec docker-app-1 alembic upgrade head                     # Run migrations

cd frontend
npm start                         # Frontend dev server
npm run generate-api              # Regenerate API client
```

---

## Critical Rules

### Rule 1: Always Rebuild Containers After Code Changes

**Context:** `docker-compose restart` only restarts containers with the OLD image. Python code changes require a full rebuild or they will not take effect.

```bash
# ❌ WRONG: Restart reuses old image
docker-compose restart celery-worker

# ✅ CORRECT: Rebuild then restart
docker-compose build app celery-worker
docker-compose up -d app celery-worker
```

### Rule 2: Frontend Runs Locally by Default

**Context:** The default dev workflow (`./dev-start.sh`) runs the frontend locally with hot reload. Only use containerized frontend if explicitly requested.

```bash
# ✅ CORRECT: Default workflow — frontend runs locally with hot reload
./dev-start.sh

# Only when explicitly requested — slower, no hot reload
cd docker
docker-compose up -d
```

---

## Patterns

### Local Development

#### Start Local Environment

**Default: Frontend runs locally (with hot reload), backend runs in Docker.**

```bash
./dev-start.sh
```

This will:
1. Start all Docker backend services (postgres, redis, app, celery, etc.)
2. Run database migrations
3. Initialize tenant (if needed)
4. Install frontend dependencies (if needed)
5. Start frontend dev server at `http://localhost:3000`

**Optional pipeline services are excluded by default**:
- Airflow services are behind the `airflow` Compose profile
- Standalone RAG ingestion services are behind the `rag-ingestion` Compose profile

**Services Available:**

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:5001 |
| API Docs | http://localhost:5001/docs |
| Flower (Celery) | http://localhost:5555 |
| Kibana | http://localhost:5601 |
| Neo4j Browser | http://localhost:7474 |
| Elasticsearch | http://localhost:9200 |

#### Start with Containerized Frontend

**Only use this if explicitly requested** (slower, no hot reload):

```bash
cd docker
docker-compose up -d
```

<<<<<<< feature/aws-rag-pipeline-steve
This starts the default Docker stack including frontend in Docker, but still
excludes optional profile-gated services like Airflow and standalone RAG
ingestion.

To include the optional pipeline services:

```bash
cd docker
docker compose --profile airflow up -d
docker compose --profile rag-ingestion up -d
docker compose --profile airflow --profile rag-ingestion up -d
```

---

### Stop Local Environment
=======
#### Stop Local Environment
>>>>>>> dev

```bash
./dev-stop.sh
```

This will:
1. Kill frontend process on port 3000
2. Stop all Docker containers

**Alternative (Docker only):**
```bash
cd docker
docker-compose down
```

#### Rebuild Containers After Code Changes

```bash
cd docker
docker-compose build app celery-worker
docker-compose up -d app celery-worker
```

**Full rebuild (use when troubleshooting):**
```bash
cd docker
docker-compose build --no-cache app celery-worker
docker-compose up -d app celery-worker
```

**Quick reference script:**
```bash
./scripts/rebuild_containers.sh
```

#### Check Service Status

```bash
cd docker
docker-compose ps
```

**Check if app is healthy:**
```bash
curl http://localhost:5001/health/ready
```

### Connecting to Northflank

#### Access Northflank Dashboard

1. Go to: https://app.northflank.com
2. Login with your credentials
3. Select the project (e.g., `eliza-platform-dev` or `eliza-platform-prod`)

#### Connect to Northflank Postgres

**Via Northflank UI:**
1. Go to Project → Add-ons → PostgreSQL
2. Click "Connect" → "Shell"
3. You're now in psql

**Via CLI (if configured):**
```bash
psql "postgresql://user:password@host:port/database"
```

#### Connect to Northflank Redis

1. Go to Project → Add-ons → Redis
2. Click "Connect" → "Shell"
3. Run: `redis-cli`

#### View Service Logs

1. Go to Project → Services → [service-name]
2. Click "Logs" tab
3. Use search/filter to find relevant entries

#### Restart a Service

1. Go to Project → Services → [service-name]
2. Click the "⋮" menu → "Restart"

**Or redeploy (to pull latest image):**
1. Click "⋮" menu → "Redeploy"

#### Update Environment Variables

1. Go to Project → Services → [service-name]
2. Click "Environment" tab
3. Edit variables
4. Click "Update" (service restarts automatically)

#### Check Deployment Status

1. Go to Project → Services → [service-name]
2. Check "Health" status (green = healthy)
3. If unhealthy, check "Events" tab for reasons

### Database Access

#### Local Database (Docker)

```bash
docker exec -it docker-postgres-1 psql -U user -d ai_enablement
```

**Common queries:**
```sql
-- List all tables
\dt

-- Describe a table
\d table_name

-- Count users
SELECT COUNT(*) FROM users;

-- Find recent questions
SELECT id, question, status, created_at 
FROM bi_questions 
ORDER BY created_at DESC 
LIMIT 10;
```

#### Northflank Database

Connect via Northflank UI (see above) or get connection string and use:
```bash
psql "postgresql://user:password@host:port/ai_enablement"
```

### Database Migrations

#### Run Migrations (Local)

```bash
# Via Docker
docker exec docker-app-1 alembic upgrade head

# Or from project root with venv
alembic upgrade head
```

#### Create New Migration

```bash
alembic revision -m "add_your_table"

# Edit the generated file in alembic/versions/
# Then apply:
alembic upgrade head
```

#### Check Migration Status

```bash
alembic current
alembic history
alembic heads
```

#### Rollback Migration

```bash
# Rollback one step
alembic downgrade -1

# Rollback to specific revision
alembic downgrade abc123
```

### Viewing Logs

#### Local Docker Logs

```bash
# All services
docker-compose logs -f

# Specific services
docker-compose logs -f app celery-worker

# Last 100 lines
docker-compose logs --tail=100 app

# Filter for errors
docker-compose logs app 2>&1 | grep -i error
```

#### Celery Task Logs

```bash
docker-compose logs -f celery-worker celery-ingestion-worker
```

#### Frontend Logs (Local)

When running `./dev-start.sh`, frontend logs appear in terminal.

### User Management

#### Create Admin User

**Via script:**
```bash
docker exec docker-app-1 python scripts/seed_admin_user.py
```

**Via SQL:**
```sql
-- First generate password hash:
-- python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"

INSERT INTO users (email, username, full_name, hashed_password, is_active, is_superuser, customer_id, failed_login_attempts, created_at, updated_at)
VALUES (
    'admin@example.com',
    'admin',
    'Admin User',
    '$2b$12$YOUR_GENERATED_HASH',
    true,
    true,
    'eliza',
    0,
    NOW(),
    NOW()
);
```

#### Reset User Password

**Generate new hash:**
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'newpassword', bcrypt.gensalt()).decode())"
```

**Update in database:**
```sql
UPDATE users 
SET hashed_password = '$2b$12$YOUR_NEW_HASH'
WHERE email = 'user@example.com';
```

#### Unlock User Account

```sql
UPDATE users 
SET failed_login_attempts = 0, locked_until = NULL 
WHERE email = 'user@example.com';
```

#### List All Users

```sql
SELECT id, email, username, customer_id, is_active, is_superuser 
FROM users 
ORDER BY created_at DESC;
```

### Frontend Operations

#### Regenerate API Client

After backend API changes, regenerate the Orval client:

```bash
cd frontend
npm run generate-api
```

This reads the OpenAPI spec from the backend and generates TypeScript hooks.

#### Install New Package

```bash
cd frontend
npm install package-name
```

#### Clear Frontend Cache

```bash
cd frontend
rm -rf node_modules/.cache
npm start
```

#### Build Production Frontend

```bash
cd frontend
npm run build
```

### Debugging Operations

#### Test Backend Endpoint

```bash
# Health check
curl http://localhost:5001/health/ready

# With authentication
TOKEN="your-jwt-token"
curl -H "Authorization: Bearer $TOKEN" http://localhost:5001/v1/users/me
```

#### Test Login

```bash
curl -X POST http://localhost:5001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "yourpassword"}'
```

#### Check Redis Queue

```bash
docker exec docker-redis-1 redis-cli

# Inside redis-cli:
LLEN celery           # Queue depth
KEYS *                # All keys
INFO                  # Server info
```

#### Check Celery Workers

```bash
# Via Flower UI
open http://localhost:5555

# Via command
docker exec docker-celery-worker-1 celery -A src.celery_app inspect active
```

#### Interactive Python Shell (in container)

```bash
docker exec -it docker-app-1 python

# Then import modules:
>>> from src.models import database
>>> database.init_database()
>>> db = database.SessionLocal()
>>> # Query database...
```

### Deployment Operations

#### Push to Northflank (Dev)

```bash
git push origin dev
```

GitHub Actions will:
1. Build Docker images
2. Push to GHCR
3. Northflank auto-pulls new images
4. Services restart

#### Check CI/CD Status

1. Go to GitHub → Actions
2. Check the latest workflow run
3. View logs for any failures

#### Manual Northflank Redeploy

If auto-deploy didn't trigger:
1. Northflank → Services → [service]
2. Click "⋮" → "Redeploy"

### Secrets and Environment

#### Set API Keys (Local)

Create/edit `.env` in project root:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

#### View Current Environment (Container)

```bash
docker exec docker-app-1 env | sort
```

#### Set Claude API Key

```bash
./scripts/set-claude-key.sh sk-ant-your-key-here
```

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Code changes not taking effect | Rebuild containers: `docker-compose build app celery-worker && docker-compose up -d` |
| Frontend not hot-reloading | Make sure you used `./dev-start.sh`, not `docker-compose up` |
| Can't connect to database | Check `docker-compose ps` — is postgres running? |
| Migration says "at head" but table missing | Rebuild container with `--no-cache` to include new migration files |
| API returns 404 for new endpoint | Rebuild app container and verify router is registered in `src/main.py` |
| Celery task never runs | Check `docker-compose ps celery-worker` and worker logs for import errors |

---

## Checklist

When something isn't working:

- [ ] Check service status: `docker-compose ps`
- [ ] Check logs: `docker-compose logs app celery-worker --tail=100`
- [ ] Check health: `curl http://localhost:5001/health/ready`
- [ ] Rebuild containers: `docker-compose build app celery-worker && docker-compose up -d`
- [ ] Check database: Can you connect? Are migrations applied?
- [ ] Check environment: Are all required env vars set?
- [ ] Check the Error Recovery Playbook: `skills/troubleshooting/ERROR_RECOVERY_PLAYBOOK.md`

---

## References

- `skills/troubleshooting/ERROR_RECOVERY_PLAYBOOK.md` — Detailed error diagnosis and fixes
- `skills/database-migrations/` — Migration creation and management patterns
- `skills/celery-tasks/` — Celery task development patterns
- `skills/fastapi-endpoints/` — API endpoint development patterns
- `docker/docker-compose.yml` — Container service definitions
- `scripts/rebuild_containers.sh` — Quick rebuild script
