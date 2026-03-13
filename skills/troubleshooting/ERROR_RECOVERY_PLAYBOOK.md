# Error Recovery Playbook

> **Purpose:** Quick reference for diagnosing and fixing common errors. When you encounter an error, search this document for the error message or symptom.

---

## Quick Reference

| Error Message | Jump To |
|---------------|---------|
| `SessionLocal is None` | [Database Session Errors](#database-session-errors) |
| `column does not exist` | [Schema Mismatch Errors](#schema-mismatch-errors) |
| `Changes not taking effect` | [Container/Deployment Errors](#containerdeployment-errors) |
| `Permission denied` / `403 Forbidden` | [Authentication Errors](#authentication-errors) |
| `Task failed silently` | [Celery Task Errors](#celery-task-errors) |
| `No documents found` / wrong results | [Search/Multi-Tenant Errors](#searchmulti-tenant-errors) |
| `SSE not connecting` | [SSE Streaming Errors](#sse-streaming-errors) |
| `Import error` / `ModuleNotFoundError` | [Import Errors](#import-errors) |

---

## Patterns

### Database Session Errors

#### Error: `SessionLocal is None`

**Symptoms:**
- Task crashes with `TypeError: 'NoneType' object is not callable`
- Error message: `SessionLocal is None after init_database()`

**Root Cause:**
Direct import creates a local binding to `None` at import time. When `init_database()` updates the global, your local binding still points to `None`.

```python
# ❌ WRONG: Direct import creates local binding
from src.models.database import SessionLocal, init_database

if SessionLocal is None:
    init_database()
db = SessionLocal()  # Still None!

# ✅ CORRECT: Module import maintains reference
from src.models import database

if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()  # Works!
```

**Fix Steps:**
1. Find all `from src.models.database import SessionLocal` statements
2. Replace with `from src.models import database`
3. Change `SessionLocal()` to `database.SessionLocal()`
4. Change `init_database()` to `database.init_database()`
5. Rebuild: `docker-compose build celery-worker && docker-compose up -d celery-worker`

#### Error: `Database session closed`

**Symptoms:**
- `DetachedInstanceError`
- `Session is not bound to any factory`

**Root Cause:**
Trying to use ORM objects after the session is closed.

**Fix:**
```python
db = database.SessionLocal()
try:
    result = service.get_entity(id)
    # Access all needed attributes BEFORE closing
    entity_id = result.entity_id
    name = result.name
finally:
    db.close()

# Don't access result.something here!
```

### Schema Mismatch Errors

#### Error: `column [table].[column] does not exist`

**Symptoms:**
- Query works in psql but fails in Python
- Error mentions `updated_at`, `created_at`, or custom column

**Root Cause:**
SQLAlchemy model includes columns that don't exist in the actual database table. Often caused by inheriting from `BaseModel` when the table doesn't have all standard columns.

**Diagnosis:**
```bash
# Check actual table schema
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "\d table_name"

# Compare with SQLAlchemy model
grep -A 30 "class YourModel" src/models/your_model.py
```

**Fix Options:**

**Option 1: Override missing columns in model**
```python
class YourModel(BaseModel):
    __tablename__ = "your_table"
    
    # Table doesn't have updated_at
    updated_at = None  # ✅ Exclude from queries
```

**Option 2: Use Base instead of BaseModel**
```python
class YourModel(Base):  # Not BaseModel
    __tablename__ = "your_table"
    
    id = Column(Integer, primary_key=True)
    # Only define columns that exist
```

**Option 3: Add missing column via migration**
```python
def upgrade():
    op.add_column('your_table', 
        sa.Column('updated_at', sa.DateTime(timezone=True)))
```

#### Error: `relation [table] does not exist`

**Symptoms:**
- First query to a new table fails
- Error after creating a new model

**Root Cause:**
Migration not applied.

**Fix:**
```bash
# Check migration status
docker-compose exec app alembic current
docker-compose exec app alembic heads

# Apply pending migrations
docker-compose exec app alembic upgrade head

# If migration file missing in container
docker-compose build app --no-cache
docker-compose up -d app
```

### Container/Deployment Errors

#### Problem: Code changes not taking effect

**Symptoms:**
- Changed Python code but old behavior persists
- New endpoints return 404
- Task still has old logic

**Root Cause:**
`docker-compose restart` reuses the old image. Code changes require a rebuild.

```bash
# ❌ WRONG: Uses old image
docker-compose restart celery-worker

# ✅ CORRECT: Rebuild then restart
docker-compose build app celery-worker
docker-compose up -d app celery-worker
```

**Verification:**
```bash
# Check when image was built
docker images | grep app

# Check container logs for recent startup
docker-compose logs app --tail=20
```

#### Problem: Migration not in container

**Symptoms:**
- Migration file exists locally
- `alembic upgrade head` says "already at head"
- But table doesn't exist

**Root Cause:**
Migration file not copied into Docker image.

**Fix:**
```bash
# Verify file exists in container
docker exec docker-app-1 ls -la /app/alembic/versions/

# If missing, rebuild with no cache
docker-compose build app --no-cache
docker-compose up -d app

# Then run migrations
docker-compose exec app alembic upgrade head
```

### Authentication Errors

#### Error: `403 Forbidden`

**Diagnosis Checklist:**
1. Token valid? Check expiration
2. User has permission? Check role/permission assignment
3. Resource belongs to user's customer? Check customer_id
4. Company access allowed? Check company_hr_dataset access

**Debug:**
```python
# In route, add logging:
logger.info(
    "auth_check",
    user_id=current_user.user_id,
    customer_id=current_user.customer_id,
    permissions=current_user.permissions,
    resource_customer=resource.customer_id
)
```

#### Error: `401 Unauthorized`

**Common Causes:**
1. Token expired
2. Token malformed
3. Secret key mismatch between environments

**Fix:**
```bash
# Check if token is valid
# In Python:
from src.services.auth_service import auth_service
await auth_service.verify_token(token)
```

### Celery Task Errors

#### Problem: Task submitted but never runs

**Diagnosis:**
```bash
# Check if celery worker is running
docker-compose ps celery-worker

# Check worker logs
docker-compose logs celery-worker --tail=50

# Check Redis connection
docker-compose exec app python -c "
import redis
r = redis.from_url('redis://redis:6379')
print(r.ping())
"
```

**Common Causes:**
1. Worker not running
2. Redis not accessible
3. Task name mismatch
4. Import error in task file (check worker logs)

#### Problem: Task runs but result not visible

**Diagnosis:**
```bash
# Check task status in database
docker exec docker-postgres-1 psql -U user -d ai_enablement -c \
  "SELECT id, status, error_message FROM your_table ORDER BY created_at DESC LIMIT 5;"
```

**Common Causes:**
1. Database session closed before commit
2. Exception caught but status not updated
3. Wrong entity_id passed to task

#### Problem: Task fails with cryptic error

**Debug Steps:**
```bash
# Get full traceback from worker logs
docker-compose logs celery-worker --tail=200 | grep -A 50 "ERROR"

# Run task synchronously for debugging
# In Python console:
from src.tasks.your_tasks import your_task
result = your_task.apply(args=['test-id', 1, 'customer']).get()
```

### Search/Multi-Tenant Errors

#### Problem: Search returns wrong company's documents

**Root Cause:**
Filtering by `customer_id` instead of `company_hr_dataset`.

```python
# ❌ WRONG: Only filters by who owns the document
results = search(customer_id=user.customer_id)

# ✅ CORRECT: Filters by which company's data is IN the document
results = search(company_hr_dataset=target_company)
```

#### Problem: Search returns no results

**Diagnosis:**
1. Check if documents exist for that company:
```sql
SELECT COUNT(*) FROM documents 
WHERE company_hr_dataset = 'target_company';
```

2. Check if embeddings exist:
```sql
SELECT COUNT(*) FROM document_embeddings 
WHERE document_id IN (
    SELECT id FROM documents WHERE company_hr_dataset = 'target_company'
);
```

3. Check vector index health:
```python
from src.services.vector_service import VectorService
vs = VectorService(db)
vs.health_check()
```

### SSE Streaming Errors

#### Problem: EventSource not connecting

**Symptoms:**
- Frontend shows "Disconnected"
- Browser console shows connection errors

**Diagnosis:**
1. Check endpoint URL includes token:
```javascript
// Token must be in query param (EventSource can't send headers)
const url = `${API_URL}/stream?token=${token}`;
```

2. Check CORS headers:
```python
# Endpoint should return these headers
headers={
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no"
}
```

3. Check nginx buffering (if using nginx):
```nginx
proxy_buffering off;
```

#### Problem: Events not appearing in stream

**Diagnosis:**
1. Check if telemetry events are being written:
```sql
SELECT * FROM telemetry_events 
WHERE entity_id = 'your-id' 
ORDER BY timestamp DESC LIMIT 10;
```

2. Check SSE polling logic:
```python
# Endpoint should poll with after_id
events = service.get_events(entity_id, after_id=last_event_id)
```

### Import Errors

#### Error: `ModuleNotFoundError: No module named 'src.something'`

**Diagnosis:**
```bash
# Verify file exists
ls -la src/something/

# Check if __init__.py exists
ls -la src/something/__init__.py

# Verify Python path
docker exec docker-app-1 python -c "import sys; print(sys.path)"
```

**Common Causes:**
1. File doesn't exist at that path
2. Missing `__init__.py`
3. Typo in import path
4. File not copied to container (rebuild needed)

#### Error: `ImportError: cannot import name 'X' from 'Y'`

**Diagnosis:**
```bash
# Check what's exported from module
docker exec docker-app-1 python -c "from Y import *; print(dir())"
```

**Common Causes:**
1. Circular import
2. Name changed/removed
3. Import at wrong level

### General Debugging Commands

```bash
# View recent errors in app logs
docker-compose logs app --tail=100 | grep -i error

# View Celery worker errors
docker-compose logs celery-worker --tail=100 | grep -i error

# Interactive Python in app container
docker exec -it docker-app-1 python

# Database query
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "YOUR SQL HERE"

# Check all container status
docker-compose ps

# Check container resource usage
docker stats

# View all environment variables
docker exec docker-app-1 env | sort

# Test Redis connection
docker exec docker-redis-1 redis-cli ping

# Check Celery task queue depth
docker exec docker-redis-1 redis-cli llen celery
```

---

## Checklist

Before submitting a PR, verify:

- [ ] `docker-compose build app celery-worker` run after code changes
- [ ] `alembic upgrade head` run if migrations added
- [ ] No `from src.models.database import SessionLocal` (use module import)
- [ ] All database sessions closed in `finally` blocks
- [ ] Response models map all database fields (no hardcoded None)
- [ ] Multi-tenant queries filter by correct field (`company_hr_dataset` for searches)
- [ ] SSE endpoints pass token in query param
- [ ] Run `python scripts/validate_feature.py [feature]` to check patterns

---

## References

- `skills/common-actions/COMMON_ACTIONS.md` — Frequently used dev commands
- `skills/database-migrations/` — Migration patterns and rules
- `skills/celery-tasks/` — Celery task development patterns
- `skills/row-level-security/` — Multi-tenant RLS implementation
- `skills/sse-realtime/` — SSE streaming patterns
- `src/models/database.py` — Database session and BaseModel definitions
- `src/middleware/tenant_context.py` — Tenant context middleware
