# Celery Adoption & Migration Plan

## 1. Why Celery for Document Processing

### 1.1 Pain Points Today
- Upload API executes the full processing pipeline inside the FastAPI container.
- Async coroutine `_process_document_async()` mixes sync SQLAlchemy and CPU-heavy work, causing crashes and blocks under load.
- Long-running tasks compete for the same resources as request handling, risking timeouts and cascading failures.
- No durable task queue: application restarts drop in-flight jobs with no retry history.

### 1.2 Celery Benefits
- **Workload Isolation**: dedicated worker processes handle chunking and embeddings; the API returns immediately.
- **Scalable Concurrency**: increase worker count or allocate high-memory/GPU hosts without impacting API instances.
- **Resilient Task Lifecycle**: built-in states, retries, and backoff; tasks survive web restarts.
- **Observability**: leverage Flower/Prometheus for queue depth, runtime, failure rates.
- **Extensibility**: same infrastructure supports future background jobs (reports, nightly maintenance, webhooks).

## 2. Architecture & Design Decisions

### 2.1 Redis Architecture
Redis serves two distinct roles in Celery:

**Broker (Queue)** - `redis://redis:6379/0`
- Stores task messages waiting to be processed
- Transient storage: messages removed when worker picks them up
- Typical lifecycle: seconds to minutes
- Storage: ~1KB per queued task

**Result Backend** - `redis://redis:6379/1`
- Stores task execution results and state
- Persistent storage with TTL (72 hours configured)
- Used for debugging, retry logic, and admin dashboards
- Storage: ~2KB per completed task
- **Production Impact**: 1000 docs/day × 3 days = 6MB max in Redis (negligible)

**Configuration Decision**: Keep results enabled for debugging and monitoring. Redis can easily handle realistic workloads.

### 2.2 Worker Scaling & Concurrency Model

Document processing is a **mixed workload**:
- **I/O heavy**: PDF reading, file operations
- **CPU heavy**: Text extraction, chunking, embeddings

#### Worker Architecture
```
┌─────────────────────────────────────────┐
│   Host Machine (Docker Container)      │
│                                         │
│  ┌────────────────────────────────┐    │
│  │  Worker Process 1              │    │
│  │  ├─ Task Thread 1 (Doc 51)     │    │
│  │  ├─ Task Thread 2 (Doc 52)     │    │
│  │  ├─ Task Thread 3 (Doc 53)     │    │
│  │  └─ Task Thread 4 (Doc 54)     │    │
│  └────────────────────────────────┘    │
│                                         │
│  ┌────────────────────────────────┐    │
│  │  Worker Process 2              │    │
│  │  ├─ Task Thread 1 (Doc 55)     │    │
│  │  ├─ Task Thread 2 (Doc 56)     │    │
│  │  └─ ...                         │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

#### Key Scaling Parameters

| Setting | Meaning | Recommendation |
|---------|---------|----------------|
| **Worker Processes** | Separate Python processes | Start with 3, scale to 6+ |
| **Concurrency** | Threads per worker | 4 threads per worker |
| **Prefetch Multiplier** | Tasks fetched ahead | 1 (process one at a time) |
| **Max Tasks Per Child** | Restart after N tasks | 100 (prevent memory leaks) |

**Starting Configuration**: 3 workers × 4 threads = **12 concurrent documents**

#### Tuning Guidelines

**If CPU-bound** (embeddings taking long):
- Increase worker count, decrease concurrency per worker
- Use `--pool=prefork` instead of threads
- Example: 6 workers × 2 threads = 12 concurrent

**If I/O-bound** (waiting on disk/network):
- Keep fewer workers, increase concurrency
- Use `--pool=threads` (current choice)
- Example: 3 workers × 8 threads = 24 concurrent

**If memory constrained**:
- Decrease concurrency, use prefork pool
- Set resource limits per worker
- Monitor with `docker stats`

### 2.3 Performance Optimization Strategy

Given variable document sizes and processing strategies:
- **No fixed SLA initially** - measure and establish baselines
- **Optimize for throughput** without excessive resource usage
- **Monitor and tune** based on real workload patterns
- **Horizontal scaling** as primary growth mechanism

## 3. Migration Overview
1. Prepare infrastructure and dependencies.
2. Refactor processing pipeline into idempotent, worker-friendly units.
3. Wire Celery tasks and update API endpoints to enqueue jobs.
4. Introduce worker services and logging/metrics.
5. Verify end-to-end, backfill stuck jobs, and deploy incrementally.

Each phase below maps to concrete tasks in this repository.

---

## 3. Detailed Migration Steps

### Phase 0 – Preparation
1. **Dependencies**
   - Update `requirements.txt` (backend):
     ```
     celery[redis]>=5.4.0
     flower>=2.0.1  # optional admin UI
     ```
   - Run `pip install -r requirements.txt` locally and in Docker build.

2. **Configuration Skeleton**
   - Create `src/celery_app.py` with production-ready configuration:
     ```python
     """
     Celery application configuration for document processing.
     Optimized for mixed I/O and CPU workloads.
     """
     from celery import Celery, signals
     from src.core.config import get_settings
     from src.core.logging import get_logger

     settings = get_settings()
     logger = get_logger(__name__)

     celery_app = Celery(
         "eliza",
         broker=settings.celery_broker_url,
         backend=settings.celery_result_backend,
         include=["src.tasks.documents"],
     )

     celery_app.conf.update(
         # Serialization (security: never use pickle)
         task_serializer="json",
         result_serializer="json",
         accept_content=["json"],
         
         # Timezone
         timezone="UTC",
         enable_utc=True,
         
         # Task execution
         task_track_started=True,
         task_acks_late=True,              # Only acknowledge after completion
         worker_prefetch_multiplier=1,      # Fetch one task at a time
         worker_max_tasks_per_child=100,    # Restart worker after 100 tasks
         
         # Result backend
         task_ignore_result=False,          # Keep results for debugging
         result_expires=259200,             # 72 hour TTL (3 days)
         result_backend_transport_options={
             'socket_keepalive': True,
             'socket_connect_timeout': 5,
             'retry_on_timeout': True,
         },
         
         # Retry configuration
         task_autoretry_for=(Exception,),
         task_retry_kwargs={'max_retries': 3},
         task_default_retry_delay=120,     # 2 minutes between retries
         
         # Performance
         worker_disable_rate_limits=True,
         
         # Logging format
         worker_log_format='[%(levelname)s/%(processName)s] %(message)s',
         worker_task_log_format='[%(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
     )

     # Task lifecycle logging for metrics
     @signals.task_prerun.connect
     def task_prerun_handler(sender=None, task_id=None, task=None, args=None, **kwargs):
         logger.info("task_started", extra={
             "task_id": task_id,
             "task_name": task.name,
             "args": args,
         })

     @signals.task_postrun.connect
     def task_postrun_handler(sender=None, task_id=None, task=None, state=None, **kwargs):
         logger.info("task_finished", extra={
             "task_id": task_id,
             "task_name": task.name,
             "state": state,
             "runtime": kwargs.get('runtime'),
         })

     @signals.task_failure.connect
     def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
         logger.error("task_failed", extra={
             "task_id": task_id,
             "task_name": sender.name,
             "exception": str(exception),
             "traceback": kwargs.get('traceback'),
         })
     ```
   
   - Extend `src/core/config.py` + `.env` templates with:
     ```python
     # Celery configuration
     celery_broker_url: str = Field(default="redis://redis:6379/0", env="CELERY_BROKER_URL")
     celery_result_backend: str = Field(default="redis://redis:6379/1", env="CELERY_RESULT_BACKEND")
     ```
   
   - Add to `.env`:
     ```bash
     CELERY_BROKER_URL=redis://redis:6379/0
     CELERY_RESULT_BACKEND=redis://redis:6379/1
     ```

3. **Docker Compose**
   - Ensure Redis service exists (already running). If absent, add `redis` service.
   - Plan to add `celery-worker` (and optional `celery-beat`, `flower`) later.

4. **Logging Utilities**
   - Verify `src/core/logging` supports structured logs from multiple processes (no stdout-only assumptions).

### Phase 1 – Refactor Processing Pipeline
1. **Extract Sync Pipeline Function**
   - In `src/services/document_processor.py`, create `def process_document_sync(document_id: int) -> None` that encapsulates the full pipeline using `BaseService.get_db_session()`.
   - Make the function idempotent by checking `Document.status`; skip if already `COMPLETED` unless a `force` flag is passed.

2. **Async Helpers**
   - Keep existing async helpers (`_extract_text_content`, etc.) but expose sync wrappers using `asyncio.run` in worker context, or refactor them to sync if feasible.
   - Alternatively, move file I/O heavy lifting into dedicated utility module that Celery tasks can call synchronously (Celery workers operate outside the event loop).

3. **Centralize Status Updates**
   - Create helper `DocumentProcessingContext` to log and update status transitions (`UPLOADED -> PROCESSING -> COMPLETED/FAILED`).
   - Ensure all exceptions are caught, logged with `error_id`, and status transitions recorded.

4. **Testing**
   - Add unit tests for `process_document_sync` (mock heavy services).

### Phase 2 – Introduce Celery Tasks
1. **Task Module**
   - Create `src/tasks/documents.py`:
     ```python
     from src.celery_app import celery_app
     from src.services.document_processor import DocumentProcessor

     processor = DocumentProcessor()

     @celery_app.task(bind=True, autoretry_for=(Exception,), max_retries=3, default_retry_delay=120)
     def process_document_task(self, document_id: int, force: bool = False):
         processor.process_document_sync(document_id, force=force)
     ```

2. **API Upload Endpoint** (`src/api/routes/documents.py`)
   - After creating the document record, replace `asyncio.create_task(...)` with `process_document_task.delay(document_id)`.
   - Return task ID if desired for status polling.

3. **Retry Endpoint**
   - Update `/v1/documents/{id}/retry` to enqueue the Celery task instead of invoking processor directly.

4. **Task Metadata Storage**
   - Optional: extend database schema with `upload_jobs` table capturing `task_id`, `document_id`, `attempt`, `status`, `started_at`, `finished_at`, `error`. Update as part of task lifecycle.

### Phase 3 – Infrastructure & Deployment
1. **Docker Compose Additions**
   Add to `docker/docker-compose.yml`:
   ```yaml
   # Celery Worker - Document Processing
   celery-worker:
     build:
       context: ..
       dockerfile: docker/Dockerfile
     command: >
       celery -A src.celery_app worker
       --loglevel=info
       --concurrency=4
       --pool=threads
       --max-tasks-per-child=100
       --time-limit=1800
       --soft-time-limit=1500
     environment:
       # Celery configuration
       - CELERY_BROKER_URL=${CELERY_BROKER_URL:-redis://redis:6379/0}
       - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://redis:6379/1}
       
       # Database & services (same as app)
       - DATABASE_URL=${DATABASE_URL}
       - REDIS_URL=${REDIS_URL}
       - NEO4J_URI=${NEO4J_URI}
       - NEO4J_USER=${NEO4J_USER}
       - NEO4J_PASSWORD=${NEO4J_PASSWORD}
       
       # Customer & environment
       - CUSTOMER_ID=${CUSTOMER_ID}
       - ENVIRONMENT=${ENVIRONMENT}
       - LOG_LEVEL=${LOG_LEVEL:-INFO}
       
       # AI API keys
       - OPENAI_API_KEY=${OPENAI_API_KEY}
       - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
       - GROQ_API_KEY=${GROQ_API_KEY}
       
       # Python settings
       - PYTHONPATH=/app
     depends_on:
       postgres:
         condition: service_healthy
       redis:
         condition: service_healthy
       neo4j:
         condition: service_healthy
     volumes:
       # Share data volumes with app
       - app_data:/app/data
       - app_logs:/app/logs
       - app_cache:/app/cache
     networks:
       - ai-platform
     deploy:
       replicas: 3  # 3 workers × 4 threads = 12 concurrent tasks
       resources:
         limits:
           cpus: '2'      # Each worker can use up to 2 CPUs
           memory: 2G     # Each worker gets 2GB RAM
         reservations:
           cpus: '0.5'    # Minimum guaranteed
           memory: 512M
     restart: unless-stopped
     healthcheck:
       test: ["CMD-SHELL", "celery -A src.celery_app inspect ping -d celery@$$HOSTNAME"]
       interval: 30s
       timeout: 10s
       retries: 3

   # Celery Beat - Scheduled Tasks (optional)
   celery-beat:
     build:
       context: ..
       dockerfile: docker/Dockerfile
     command: celery -A src.celery_app beat --loglevel=info
     environment:
       - CELERY_BROKER_URL=${CELERY_BROKER_URL:-redis://redis:6379/0}
       - DATABASE_URL=${DATABASE_URL}
       - PYTHONPATH=/app
     depends_on:
       redis:
         condition: service_healthy
     volumes:
       - app_data:/app/data
     networks:
       - ai-platform
     restart: unless-stopped

   # Flower - Celery Monitoring UI (optional)
   flower:
     build:
       context: ..
       dockerfile: docker/Dockerfile
     command: >
       celery -A src.celery_app flower
       --port=5555
       --basic_auth=admin:changeme
     environment:
       - CELERY_BROKER_URL=${CELERY_BROKER_URL:-redis://redis:6379/0}
       - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://redis:6379/1}
     ports:
       - "5555:5555"
     depends_on:
       - redis
     networks:
       - ai-platform
     restart: unless-stopped
   ```
   
   - Ensure `Dockerfile` installs Celery deps (already in requirements.txt)
   - Update `.env` file with Celery URLs

2. **Prod Deployment Script**
   - Update CI/CD manifests (Kubernetes or ECS) to include new worker deployments/services.

3. **Logging Integration**
   - Celery workers inherit logging config from `src/core/logging`
   - Structured logs with task lifecycle events (prerun, postrun, failure)
   - All logs include: `task_id`, `task_name`, `document_id`, `customer_id`
   - Logs go to same destinations as app logs (files, stdout)

4. **Monitoring & Metrics**
   
   **Built-in Tools (no additional infrastructure)**:
   ```bash
   # Monitor active tasks
   celery -A src.celery_app inspect active
   
   # Check worker stats
   celery -A src.celery_app inspect stats
   
   # View registered tasks
   celery -A src.celery_app inspect registered
   
   # Check queue lengths
   celery -A src.celery_app inspect active_queues
   
   # Real-time event stream
   celery -A src.celery_app events
   ```
   
   **Flower Dashboard** (http://localhost:5555):
   - Real-time task monitoring
   - Worker status and resource usage
   - Task history and failure tracking
   - Queue depth visualization
   - Basic auth: admin/changeme (change in production)
   
   **Log-Based Metrics** (grep structured logs):
   ```bash
   # Count tasks by status today
   grep "task_finished" logs/*.log | grep "$(date +%Y-%m-%d)" | wc -l
   
   # Find failed tasks
   grep "task_failed" logs/*.log | jq '.task_id, .exception'
   
   # Average task duration
   grep "task_finished" logs/*.log | jq '.runtime' | awk '{sum+=$1; count++} END {print sum/count}'
   ```
   
   **Performance Baselines to Establish**:
   - Documents processed per hour
   - Average processing time by file size
   - Memory usage per worker
   - CPU utilization under load
   - Queue depth during peak usage
   
   **Key Metrics to Track**:
   - `task_started` count (throughput)
   - `task_finished` count (success rate)
   - `task_failed` count (error rate)
   - `task_runtime` distribution (performance)
   - Queue length (backlog indicator)

### Phase 4 – Verification & Backfill
1. **Local Test**
   - `docker-compose up app celery-worker` and run upload flow. Confirm documents reach `COMPLETED`.
   - Simulate failure (e.g., raise exception), verify retry and status update.

2. **Backfill Stuck Jobs**
   - Write script `scripts/requeue_documents.py` to enqueue Celery tasks for documents with status `PROCESSING` or `FAILED`.

3. **Load Test**
   - Use Locust/JMeter to simulate concurrent uploads. Monitor worker CPU, queue depth, and throughput.

4. **QA Verification**
   - Smoke test UI retry button, ensure status tooltips reflect new states (`queued`, `processing`, `retrying`).

### Phase 5 – Rollout & Cleanup
1. **Staged Deployment**
   - Deploy Celery infrastructure alongside existing async routine but keep old path disabled behind feature flag.
   - Switch API to enqueue tasks in staging, monitor, then promote to production.

2. **Post-Migration Cleanup**
   - Remove manual `SessionLocal()` handling and obsolete async `create_task` call.
   - Update documentation and developer onboarding materials.

3. **Operational Runbook**
   
   **Daily Operations**:
   ```bash
   # Check worker health
   docker-compose -f docker/docker-compose.yml ps celery-worker
   
   # View worker logs
   docker-compose -f docker/docker-compose.yml logs -f celery-worker
   
   # Check active tasks
   docker exec docker-celery-worker-1 celery -A src.celery_app inspect active
   
   # Monitor queue depth
   docker exec docker-celery-worker-1 celery -A src.celery_app inspect active_queues
   ```
   
   **Scaling Operations**:
   ```bash
   # Scale up to 6 workers (6 × 4 threads = 24 concurrent)
   docker-compose -f docker/docker-compose.yml up -d --scale celery-worker=6
   
   # Scale down gracefully (let tasks finish)
   docker-compose -f docker/docker-compose.yml stop celery-worker
   docker-compose -f docker/docker-compose.yml up -d --scale celery-worker=2
   ```
   
   **Emergency Procedures**:
   ```bash
   # Stop all workers immediately
   docker-compose -f docker/docker-compose.yml stop celery-worker
   
   # Purge all pending tasks (DANGEROUS - only if needed)
   docker exec docker-celery-worker-1 celery -A src.celery_app purge
   
   # Revoke specific stuck task
   docker exec docker-celery-worker-1 celery -A src.celery_app control revoke <task_id> --terminate
   
   # Restart single worker
   docker-compose -f docker/docker-compose.yml restart celery-worker
   ```
   
   **Troubleshooting**:
   ```bash
   # Document stuck in PROCESSING for >30 minutes
   # 1. Check if task is active:
   celery -A src.celery_app inspect active | grep <document_id>
   
   # 2. If not active, reset in database:
   docker exec docker-postgres-1 psql -U user -d ai_enablement -c \
     "UPDATE documents SET status='UPLOADED', processing_lock=NULL WHERE id=<doc_id>"
   
   # 3. Retry via API:
   curl -X POST http://localhost:5001/v1/documents/<doc_id>/retry
   
   # High memory usage
   # 1. Check worker memory:
   docker stats docker-celery-worker-1
   
   # 2. Restart workers (max_tasks_per_child prevents leaks):
   docker-compose -f docker/docker-compose.yml restart celery-worker
   
   # 3. If persistent, reduce concurrency:
   # Edit docker-compose.yml: --concurrency=2
   ```
   
   **Performance Tuning**:
   ```bash
   # Monitor CPU usage during processing
   docker stats --no-stream | grep celery
   
   # If CPU maxed out: add more workers
   # If CPU idle: increase concurrency per worker
   # If memory high: reduce concurrency or use prefork pool
   ```

4. **Continuous Improvement**
   - **Baseline Measurements**: After 1 week, document average processing times
   - **Queue Routing**: If needed, add customer-specific queues for isolation
   - **Priority Queues**: Implement high/normal/low priority for different document types
   - **Scheduled Tasks**: Use Celery Beat for cleanup jobs (prune old results, archive logs)
   - **Resource Optimization**: Adjust worker count and concurrency based on metrics
   - **Error Analysis**: Review failed tasks weekly, improve error handling

---

## 4. Timeline & Responsibilities (Suggested)
- **Week 1**: Phase 0–1 (deps, config, pipeline refactor).
- **Week 2**: Phase 2 (tasks + API wiring) with unit tests.
- **Week 3**: Phase 3 infrastructure updates; local/staging verification.
- **Week 4**: Phase 4–5 testing, load validation, production rollout.

Adjust timeline based on team velocity and QA requirements.

## 5. Post-Migration Optimization Opportunities

### Immediate (Week 1-2)
- **Establish Baselines**: Document processing time distribution by file size
- **Error Classification**: Categorize failure types (validation, extraction, embedding, etc.)
- **Resource Monitoring**: Track CPU/memory usage patterns under normal load

### Short-term (Month 1-2)
- **Multi-tenant Isolation** (if needed):
  - Route tasks to customer-specific queues
  - Guarantee fair processing across customers
  - Example: `documents.customer-123` queue
  
- **Priority Queues** (if needed):
  - Separate queues for urgent vs. batch uploads
  - Example: `documents.high`, `documents.normal`, `documents.low`
  
- **Task Progress Tracking** (if UI needs it):
  - Store intermediate status in database (`EXTRACTING`, `CHUNKING`, `EMBEDDING`)
  - Expose progress via polling endpoint or WebSocket
  - Show percentage complete in UI

### Long-term (Month 3+)
- **Scheduled Maintenance Tasks**:
  - Celery Beat for nightly cleanup (old results, temporary files)
  - Weekly quality score recalculation
  - Monthly index optimization
  
- **Advanced Retry Logic**:
  - Exponential backoff for transient errors
  - Dead letter queue for permanent failures
  - Automatic reprocessing with different strategies
  
- **Resource Optimization**:
  - Dedicated workers for heavy documents (>10MB)
  - GPU workers for embedding generation (if using local models)
  - Auto-scaling based on queue depth

## 6. Success Criteria

Migration is considered successful when:
- ✅ All new uploads process via Celery workers
- ✅ API response time <500ms for upload endpoint
- ✅ Zero document processing crashes (vs. current state)
- ✅ Failed tasks retry automatically (3 attempts)
- ✅ Workers recover gracefully from restarts
- ✅ Processing throughput >= 100 documents/hour (baseline)
- ✅ Memory usage stable over 24 hours (no leaks)
- ✅ Monitoring dashboards operational (Flower or logs)

## 7. Rollback Plan

If critical issues arise:

1. **Set Feature Flag**: `ENABLE_CELERY=false` in environment
2. **Update API**: Check flag, fall back to old `asyncio.create_task` path
3. **Drain Queue**: Let pending tasks finish or purge if necessary
4. **Stop Workers**: Scale celery-worker to 0
5. **Document Issues**: Log root cause for future retry

**Rollback triggers**:
- Processing failure rate >20%
- Worker crashes >3 times/hour
- Queue depth growing indefinitely
- Memory/CPU exhaustion

Keep both code paths for 1-2 weeks after migration for safety.

