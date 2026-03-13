# Investigation: Chat Endpoint Blocking & Event Loop Starvation

**Date:** 2026-02-10  
**Status:** Investigation complete, fixes pending  
**Severity:** High — causes full application freezes under normal browser usage

---

## Problem Statement

The chat endpoints (`GET /v1/chat/history`, `GET /v1/chat/workspaces`) and the authentication middleware block the single-threaded uvicorn event loop with synchronous database calls. When the browser hits these endpoints after a fresh restart (session cache cold), the entire application freezes for 10+ seconds — no other requests (including health checks) can be processed.

### Observed Behavior (from logs)

```
00:13:31  Incoming: GET /v1/chat/history
00:13:41  Session cache MISS (10 second gap — event loop blocked)
00:13:42  Request completed: 10,710ms
00:13:42  ⚠️ Slow request detected: GET /v1/chat/history (threshold: 1000ms)

00:14:06  Incoming: GET /v1/chat/history (2nd request from browser)
00:14:10  Incoming: OPTIONS /v1/chat/workspaces
          ... app completely frozen, login curl times out after 10s ...
```

---

## Root Causes

There are **4 layers** of blocking, all compounding on a **single uvicorn worker with no `--workers` flag**.

### 1. Auth Session Validation — Sync DB in Async Function (CRITICAL)

**File:** `src/services/auth_service.py:229-272`  
**Impact:** Blocks event loop on every session cache miss (always after restart, and every 5 min per session)

`verify_token()` is `async def` but calls synchronous `get_db_session()` directly:

```python
async def verify_token(self, token: str) -> Dict[str, Any]:
    # ...cache check...
    
    # Cache miss — BLOCKS EVENT LOOP
    with self.get_db_session() as db:            # sync context manager
        session = db.query(UserSession).filter(  # sync DB query
            and_(
                UserSession.session_token == session_token,
                UserSession.is_active == True
            )
        ).first()
        
        # ...validation...
        session.last_activity_at = now
        db.commit()                              # sync commit
```

The `get_db_session()` method (from `BaseService`) creates a synchronous SQLAlchemy session. Because `verify_token` is `async def`, Python runs it directly on the event loop — the sync DB calls block the entire loop until they return.

**Why 10 seconds?** On cold start, the first database connection establishment, combined with SQLAlchemy session factory initialization, can take several seconds. Under connection pool pressure (multiple requests queued), this compounds.

**Note:** `get_user_by_id()` (line 399-401) correctly uses `run_in_threadpool` — but it runs *after* the blocking `verify_token`, so the damage is already done.

### 2. Tenant Active Check — Sync DB in Async Middleware (HIGH)

**File:** `src/middleware/authorization.py:824-861`  
**Impact:** Blocks event loop on every authenticated request

```python
async def _check_tenant_active(self, user_context, request):
    from src.models.database import SessionLocal
    
    db = SessionLocal()              # sync session
    try:
        tenant = db.query(Customer).filter(  # sync query — BLOCKS
            Customer.customer_id == user_context.customer_id
        ).first()
        # ...
    finally:
        db.close()
```

This runs on **every authenticated request**, after `verify_token`. Even on cache hits (where `verify_token` is fast), this still blocks.

### 3. API Audit Logging — Sync DB Write on Every Request (MEDIUM)

**File:** `src/middleware/tenant_context.py:272-283`  
**Impact:** Blocks event loop after every response is sent

```python
# Comment says "in background thread" but it's NOT — it's synchronous inline
if ENABLE_API_AUDIT_LOGGING and effective_tenant_id:
    self._log_api_request_sync(   # BLOCKS — sync DB insert + commit
        request=request,
        status_code=response.status_code,
        # ...
    )
```

`_log_api_request_sync` calls `log_api_request_sync()` from `api_audit_service.py`, which creates a `SessionLocal()`, does `db.add()` + `db.commit()` + `db.close()` — all synchronous and inline on the event loop.

The comment says "in background thread" but no threadpool/executor is used.

### 4. Chat History N+1 Query (LOW — but wasteful)

**File:** `src/api/routes/workspace.py:654-655`  
**Impact:** O(N) extra queries; minor latency but poor practice

```python
for conv in conversations:
    workspace = db.query(RAGFlowDomain).filter(    # N+1 query!
        RAGFlowDomain.id == conv.domain_id
    ).first()
```

The initial query already JOINs `RAGFlowDomain`, but the loop re-queries it for each conversation. With 50 conversations, that's 50 extra queries.

**Note on `async def` + sync `Depends(get_db)`:** FastAPI runs sync generator dependencies (`get_db`) in a threadpool automatically. However, when the endpoint is `async def`, the SQLAlchemy queries *inside the endpoint body* (like `db.query(...)`) execute directly on the event loop — they block. If the endpoint were `def` (not `async def`), FastAPI would run the entire function in a threadpool.

---

## Blocking Call Inventory

| Location | Method | Blocking Operation | Runs When | Est. Time |
|----------|--------|--------------------|-----------|-----------|
| `auth_service.py:244` | `verify_token` | `get_db_session()` + query + commit | Session cache miss | 5-200ms+ |
| `authorization.py:828` | `_check_tenant_active` | `SessionLocal()` + query | Every auth'd request | 5-15ms |
| `tenant_context.py:273` | `dispatch` | `_log_api_request_sync` (DB insert) | Every request with tenant | 10-50ms |
| `authorization.py:461` | `check_adoption_access` | `SessionLocal()` + query | Adoption route access | 5-15ms |
| `authorization.py:520` | `get_accessible_adoption_companies` | Multiple `SessionLocal()` + queries | Adoption list routes | 10-30ms |
| `workspace.py:655` | `get_chat_history` | N+1 `db.query(RAGFlowDomain)` | Chat history list | 2-5ms × N |
| `audit_service.py:153` | `log_event` | `get_db_session()` + insert + commit | Auth failures | 5-20ms |

**Cumulative worst case per request: ~50-300ms+ of event loop blocking**

With a single uvicorn worker, even 50ms of blocking prevents any other request from being processed. Under concurrent browser requests (which send 3-5 API calls simultaneously on page load), these compound to cause multi-second freezes.

---

## Why Now? — The Workspaces Branch Trigger

The blocking sync calls in the middleware and auth service have existed since late 2025. Uvicorn with a single worker has been the server since October 2025. **The workspaces branch (merged ~Feb 4, 2026) changed the frontend's request pattern, which exposed the latent issue.**

### Before the Workspaces Merge

The old `DomainChatPage` made **targeted, sequential** API calls:
- `GET /v1/ragflow/domains/by-name/{name}` — single domain fetch
- `GET /v1/ragflow/conversations/by-uuid/{uuid}` — single conversation fetch
- No `chat/history` or `chat/workspaces` endpoints existed at all

With 1-2 light sequential requests per page load, the cumulative event loop blocking (~50-100ms) was imperceptible.

### After the Workspaces Merge

The new `ChatPage` + `SectionNavContent` sidebar fire **3+ concurrent requests** on every page navigation:

| Request | Source | New? |
|---------|--------|------|
| `GET /v1/chat/history` | Sidebar (`SectionNavContent.tsx:421`) | **Yes — new endpoint** |
| `GET /v1/chat/workspaces` | Chat page (`ChatPage.tsx:58`) | **Yes — new endpoint** |
| `GET /v1/ragflow/domains` | Domains page (pre-existing) | No, but now concurrent |

Each request hits the full blocking auth chain (`verify_token` sync DB → `_check_tenant_active` sync DB → endpoint body sync DB → audit log sync DB). On a cold session cache, the first request blocks for seconds. The remaining requests queue behind it on the single event loop, each blocking in turn, compounding to 10+ seconds of total freeze.

**The blocking code was always technical debt. The workspaces branch turned it into a user-facing outage by tripling concurrent request volume on page load.**

---

## Why It's Worse After Restart

1. **Session cache is in-memory `TTLCache`** — completely cold after restart
2. **Every request triggers a cache miss** → every request hits the blocking `verify_token` DB path
3. **Browser sends multiple concurrent requests** on page load (chat/history, chat/workspaces, ragflow/domains, etc.)
4. **Single uvicorn worker** — requests are serialized; each blocking call delays all queued requests
5. **Connection pool cold start** — first few DB connections take longer to establish

---

## Long-Term Fix Strategy

The quick fixes (`run_in_threadpool` wrappers) are the right immediate response, but they treat symptoms. The underlying issue is that the codebase mixes sync SQLAlchemy with async FastAPI without a consistent strategy. As the platform grows, more endpoints and middleware will hit the same pattern. The long-term plan addresses the root architecture.

### Phase 1: Stop the Bleeding (Immediate — 1-2 days)

Wrap all identified blocking calls in `run_in_threadpool`. This is the correct short-term fix — it's what FastAPI and Starlette provide specifically for this pattern.

#### 1a. Auth session validation — offload to threadpool

**File:** `src/services/auth_service.py`

Extract the sync DB work from `verify_token` into a sync helper, wrap with `run_in_threadpool`:

```python
from starlette.concurrency import run_in_threadpool

def _verify_session_sync(self, session_token: str) -> dict:
    """Sync helper — runs in threadpool, safe to block."""
    with self.get_db_session() as db:
        session = db.query(UserSession).filter(
            and_(UserSession.session_token == session_token, UserSession.is_active == True)
        ).first()
        if not session or session.is_expired():
            raise AuthenticationError("Session expired")
        now = datetime.now(timezone.utc)
        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)
        if (now - last_activity).total_seconds() > 60:
            session.last_activity_at = now
            db.commit()
        return {"user_id": session.user_id, "expires_at": session.expires_at, "validated_at": now}

async def verify_token(self, token: str) -> Dict[str, Any]:
    # ...JWT decode, cache check (fast, non-blocking)...
    session_data = await run_in_threadpool(self._verify_session_sync, session_token)
    self.session_cache[session_token] = session_data
    return payload
```

#### 1b. Tenant active check — offload to threadpool

**File:** `src/middleware/authorization.py`

```python
def _check_tenant_active_sync(self, customer_id: str):
    """Sync helper for tenant check."""
    from src.models.database import SessionLocal
    from src.models.customer import Customer
    db = SessionLocal()
    try:
        return db.query(Customer).filter(Customer.customer_id == customer_id).first()
    finally:
        db.close()

async def _check_tenant_active(self, user_context, request):
    tenant = await run_in_threadpool(self._check_tenant_active_sync, user_context.customer_id)
    if tenant and not tenant.is_active:
        raise HTTPException(status_code=403, detail={...})
```

#### 1c. Audit logging — fire-and-forget via executor

**File:** `src/middleware/tenant_context.py`

The audit log should never delay the response. Use `asyncio.get_event_loop().run_in_executor` for true fire-and-forget:

```python
import asyncio

if ENABLE_API_AUDIT_LOGGING and effective_tenant_id:
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, self._log_api_request_sync, ...)
```

#### 1d. Chat endpoints — remove `async` keyword

**File:** `src/api/routes/workspace.py`

Change `async def` to `def` on all endpoints that only do sync SQLAlchemy work. FastAPI auto-runs plain `def` handlers in a threadpool:

```python
# Before (blocks event loop):
@chat_router.get("/history")
async def get_chat_history(...):
    db.query(...)  # blocks

# After (auto-threadpooled):
@chat_router.get("/history")
def get_chat_history(...):
    db.query(...)  # runs in threadpool
```

This is a one-word change per endpoint with high impact. Apply to all endpoints in `workspace.py` that use `Depends(get_db)` with sync queries.

#### 1e. Fix N+1 query in chat/history

**File:** `src/api/routes/workspace.py`

Replace the per-conversation domain lookup with a single batch query:

```python
domain_ids = {conv.domain_id for conv in conversations}
domains = db.query(RAGFlowDomain).filter(RAGFlowDomain.id.in_(domain_ids)).all()
domain_map = {d.id: d for d in domains}

for conv in conversations:
    workspace = domain_map.get(conv.domain_id)
    if workspace:
        conversation_summaries.append(...)
```

### Phase 2: Establish Async Database Foundation (1-2 weeks)

The codebase already has `get_async_session()` in `database.py` and an `AsyncBaseService` in `base_service.py`, but they're not used. Phase 2 makes async the default for the API layer.

#### 2a. Migrate auth service to async SQLAlchemy

Replace `BaseService` (sync) with `AsyncBaseService` for `AuthService`. This eliminates the need for `run_in_threadpool` wrappers — the DB calls become truly non-blocking:

```python
class AuthService(AsyncBaseService):
    async def verify_token(self, token: str) -> Dict[str, Any]:
        # ...cache check...
        async with self.get_async_session() as db:
            result = await db.execute(
                select(UserSession).where(
                    UserSession.session_token == session_token,
                    UserSession.is_active == True
                )
            )
            session = result.scalar_one_or_none()
            # Truly non-blocking — no threadpool needed
```

#### 2b. Migrate middleware DB calls to async

Convert `_check_tenant_active`, `check_adoption_access`, and `get_accessible_adoption_companies` to use async sessions. These run on every request and should be native async.

#### 2c. Create `get_async_db` FastAPI dependency

Add an async version of the `get_db` dependency that yields an `AsyncSession`:

```python
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session
```

New endpoints should use `Depends(get_async_db)` with `async def`. Existing endpoints using `Depends(get_db)` with `def` (plain sync) are fine — FastAPI handles them correctly in a threadpool.

#### 2d. Establish the endpoint convention

Codify this rule for the team:

| Endpoint uses... | Declare as... | Why |
|---|---|---|
| `Depends(get_db)` + sync SQLAlchemy | `def` (not `async def`) | FastAPI runs `def` in threadpool automatically |
| `Depends(get_async_db)` + async SQLAlchemy | `async def` | Native async, no blocking |
| `await` calls to external async services | `async def` | Needs event loop |
| Mix of sync DB + async calls | `async def` + `run_in_threadpool` for sync parts | Explicit about what blocks |

### Phase 3: Infrastructure Resilience (1 week)

#### 3a. Add uvicorn workers

Currently running a single worker:

```dockerfile
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5001"]
```

Add `--workers` based on available CPU (2× vCPU is a common starting point). With 2 vCPU:

```dockerfile
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5001", "--workers", "4"]
```

**Trade-off:** Multiple workers means multiple in-memory session caches. Each worker has its own `TTLCache`. This is fine — cache misses just hit the DB, and with async DB (Phase 2) this is non-blocking. If cache hit rates become a concern, move to shared Redis cache (Phase 3c).

#### 3b. Add connection pool warm-up

Pre-establish database connections on startup to avoid cold-start latency:

```python
# In src/main.py startup event
@app.on_event("startup")
async def startup():
    # Warm up the connection pool with a simple query
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
```

#### 3c. Move session cache to Redis (if needed)

If multi-worker cache miss rates are problematic, move from `TTLCache` (per-process) to Redis (shared):

```python
# Only if metrics show cache hit rate dropped significantly with multiple workers
import redis
r = redis.Redis(host=settings.redis_host, port=settings.redis_port)

async def verify_token(self, token: str):
    cached = r.get(f"session:{session_token}")
    if cached:
        return json.loads(cached)
    # ...DB lookup...
    r.setex(f"session:{session_token}", 300, json.dumps(session_data))
```

This is optional — measure first. The in-memory cache is simpler and may be sufficient.

### Phase 4: Codebase-Wide Audit (Ongoing)

#### 4a. Lint rule for sync-in-async

Add a custom linting rule (or code review checklist item) that flags synchronous DB operations inside `async def` functions. Pattern to detect:

```
# Flag: sync SessionLocal() or get_db_session() inside async def
async def any_function():
    db = SessionLocal()          # ← VIOLATION
    with self.get_db_session():  # ← VIOLATION
    db.query(...)                # ← VIOLATION (if in async def)
```

#### 4b. Audit all `async def` endpoints using `Depends(get_db)`

Every `async def` endpoint using the sync `get_db` dependency is a potential blocker. Systematically convert them:
- If they only do sync DB work → change to `def`
- If they mix sync DB + async calls → wrap sync parts in `run_in_threadpool`
- If they can be fully async → migrate to `get_async_db`

#### 4c. VectorStore sync calls (already identified)

The `run_in_executor` wrappers added to `vector_store.py:get_stats` were the right approach. The WARNING comments on `create_index`, `delete_index`, `index_documents`, `search`, etc. should be addressed in this phase — wrap each in `run_in_executor` or convert the Elasticsearch client to its async variant (`AsyncElasticsearch`).

---

## Implementation Order Summary

| Phase | Fix | Effort | Impact | Risk |
|-------|-----|--------|--------|------|
| **1a** | `verify_token` → `run_in_threadpool` | Small | Very High | Low |
| **1b** | `_check_tenant_active` → `run_in_threadpool` | Small | High | Low |
| **1c** | Audit logging → `run_in_executor` fire-and-forget | Small | Medium | Low |
| **1d** | Chat endpoints `async def` → `def` | Trivial | High | Very Low |
| **1e** | N+1 query fix | Small | Low | Low |
| **2a** | Auth service → `AsyncBaseService` | Medium | High | Medium |
| **2b** | Middleware → async sessions | Medium | High | Medium |
| **2c** | `get_async_db` dependency | Small | Foundation | Low |
| **2d** | Document endpoint conventions | Trivial | Prevention | None |
| **3a** | Uvicorn `--workers 4` | Config | Medium | Low |
| **3b** | Connection pool warm-up | Small | Medium | Low |
| **3c** | Redis session cache (if needed) | Medium | Low-Medium | Medium |
| **4a** | Lint rule for sync-in-async | Small | Prevention | None |
| **4b** | Audit all `async def` + `get_db` endpoints | Medium | Comprehensive | Low |
| **4c** | VectorStore async wrappers | Medium | Medium | Low |

Phase 1 can ship this week. Phase 2 should be the next sprint. Phase 3 is infrastructure tuning. Phase 4 is ongoing hygiene.

---

## How to Verify

After applying fixes, test with:

```bash
# 1. Restart app (cold cache)
docker compose restart app

# 2. Wait for healthy
sleep 15 && curl -s -w "%{time_total}s" http://localhost:5001/health/ready

# 3. Login
TOKEN=$(curl -s -X POST http://localhost:5001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@eliza.com","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 4. Hit chat/history (should be < 1s even on cold cache)
curl -s -w "\nTime: %{time_total}s\n" \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:5001/v1/chat/history

# 5. Hit chat/workspaces
curl -s -w "\nTime: %{time_total}s\n" \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:5001/v1/chat/workspaces

# 6. Concurrent test — all should complete in parallel, not serialized
time (
  curl -s -o /dev/null -w "history: %{time_total}s\n" -H "Authorization: Bearer $TOKEN" http://localhost:5001/v1/chat/history &
  curl -s -o /dev/null -w "workspaces: %{time_total}s\n" -H "Authorization: Bearer $TOKEN" http://localhost:5001/v1/chat/workspaces &
  curl -s -o /dev/null -w "domains: %{time_total}s\n" -H "Authorization: Bearer $TOKEN" http://localhost:5001/v1/ragflow/domains &
  wait
)
# Target: all three complete in < 1s total (currently: 10s+ serialized)
```
