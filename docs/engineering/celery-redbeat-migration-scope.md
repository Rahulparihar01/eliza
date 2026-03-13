# Celery RedBeat Migration — Scope & Estimate

## Problem

Celery Beat's built-in scheduler uses a static in-memory schedule defined at
process startup. When tenants change their adoption sync schedule via the UI,
Beat doesn't pick it up without a restart.

To work around this, a **dispatcher pattern** was introduced: Beat fires a
lightweight "check" task every 60 seconds, the task reads each tenant's cron
from the database, and enqueues the real sync only when a match is found.

This causes:

- **1,440 wasted task dispatches per day** (almost all are no-ops)
- **Misleading Job Scheduler UI** (shows "Every 1 minute" instead of the real
  schedule)
- **Extra code complexity** (`dispatch_adoption_schedules`, `_cron_matches_utc_minute`,
  `_cron_field_matches` — ~120 lines of hand-rolled cron parsing)
- **Same pattern duplicated** for the RAGFlow S3 KB sync dispatcher

## Proposed Solution — `celery-redbeat`

[RedBeat](https://github.com/sibinber/redbeat) is a Celery Beat scheduler that
stores schedules in Redis. Schedules are read from Redis on every tick, so any
schedule change made via the API is picked up within seconds — no restart, no
polling task.

We already run Redis as both the Celery broker and result backend, so no new
infrastructure is needed.

---

## What Changes

### 1. Install `celery-redbeat` (5 min)

```
pip install celery-redbeat
```

Add to `requirements.txt`.

### 2. Configure Beat to use RedBeat scheduler (10 min)

**File:** `src/celery_app.py`

```python
celery_app.conf.update(
    # Replace the default Beat scheduler with RedBeat
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.celery_broker_url,  # reuse existing Redis
    redbeat_key_prefix="eliza-beat:",

    # Keep existing static schedules for non-tenant tasks
    beat_schedule=beat_schedule,
    ...
)
```

Static entries in `beat_schedule` (like a future global health-check task)
continue to work — RedBeat merges them with dynamic entries.

### 3. Write/delete RedBeat entries when tenant saves schedule (30 min)

**File:** `src/api/routes/tenant_admin.py` (PUT `/adoption-settings`)

When a tenant saves their adoption schedule, write a RedBeat entry directly
instead of saving a cron string for the dispatcher to poll:

```python
from redbeat import RedBeatSchedulerEntry
from celery.schedules import crontab

def _sync_adoption_beat_entry(customer_id: str, cron_expr: str | None, enabled: bool):
    """Create or remove a RedBeat entry for a tenant's adoption sync."""
    entry_name = f"adoption-sync:{customer_id}"

    if not enabled or not cron_expr:
        # Remove the entry if schedule is disabled
        try:
            existing = RedBeatSchedulerEntry.from_key(
                f"eliza-beat:{entry_name}", app=celery_app
            )
            existing.delete()
        except KeyError:
            pass
        return

    minute, hour, dom, month, dow = cron_expr.split()
    schedule = crontab(minute=minute, hour=hour, day_of_week=dow,
                       day_of_month=dom, month_of_year=month)

    entry = RedBeatSchedulerEntry(
        name=entry_name,
        task="adoption.daily_sync",
        schedule=schedule,
        kwargs={"customer_id": customer_id, "track_job": True},
        app=celery_app,
    )
    entry.save()
```

Call this from the PUT `/adoption-settings` endpoint after saving the config.

### 4. Update `celery-beat` Docker command (5 min)

**File:** `docker/docker-compose.yml`

No change needed to the command — `celery -A src.celery_app beat ...` still
works. RedBeat is activated by the `beat_scheduler` config, not the CLI.

### 5. Remove dispatcher code (30 min)

Delete or simplify these pieces:

| File | What to remove |
|------|----------------|
| `src/tasks/adoption_sync_tasks.py` | `dispatch_adoption_schedules()`, `_cron_matches_utc_minute()`, `_cron_field_matches()` (~120 lines) |
| `src/celery_app.py` | `adoption-sync-dispatch` beat_schedule entry |
| `src/api/routes/platform_admin.py` | `_build_job_dict()` workaround for adoption display |

### 6. Update `ScheduledJobConfig` row (10 min)

Migration to update the `adoption-daily-sync` row:

- `task_name` → `adoption.daily_sync` (direct task, not dispatcher)
- `schedule_type` → `cron`
- `schedule_value` → tenant's cron (or a sensible default like `0 11 * * *`)
- `description` → updated to remove dispatcher references

Or: remove the `ScheduledJobConfig` row entirely and drive the Job Scheduler
page from RedBeat entries via `RedBeatSchedulerEntry.from_key()`.

### 7. Job Scheduler page — show real schedule (15 min)

Two options:

**Option A (simpler):** Keep `ScheduledJobConfig` for display/history. When
saving adoption settings, update both RedBeat (for actual scheduling) and
`ScheduledJobConfig` (for UI display). This preserves the execution history
table and the Job Scheduler UI as-is.

**Option B (cleaner):** Read schedules from RedBeat via its Redis keys. The
Job Scheduler page would list entries from Redis. More work, but single source
of truth.

**Recommendation:** Option A. Keep `ScheduledJobConfig` for display and
execution tracking, use RedBeat purely for schedule execution.

### 8. Seed existing tenants (10 min)

One-time migration or script to create RedBeat entries for all tenants that
already have `AdoptionSyncConfig.schedule_enabled = True`:

```python
configs = db.query(AdoptionSyncConfig).filter(
    AdoptionSyncConfig.schedule_enabled.is_(True),
    AdoptionSyncConfig.schedule_cron.isnot(None),
).all()

for config in configs:
    _sync_adoption_beat_entry(config.customer_id, config.schedule_cron, True)
```

### 9. Apply same pattern to RAGFlow S3 sync (15 min, optional)

The `ragflow-s3-kb-sync-dispatch` entry in `beat_schedule` uses the same
dispatcher pattern (interval polling). Can be migrated to RedBeat the same way,
but it's lower priority since it's a fixed interval, not a tenant-configurable
cron.

---

## What Stays the Same

- **`AdoptionSyncConfig` table** — still stores the tenant's schedule
  preferences (start date, cron, enabled flag). Source of truth for the UI.
- **`ScheduledJobConfig` / `ScheduledJobExecution` tables** — still used for
  Job Scheduler display and execution history.
- **`daily_adoption_sync` task** — unchanged. RedBeat calls it directly instead
  of going through the dispatcher.
- **Manual sync endpoint** — unchanged (`POST /adoption/sync`).
- **Celery Beat container** — same container, same command. Just uses a
  different scheduler backend internally.
- **Redis** — already running, no new infrastructure.

---

## Estimate

| Task | Effort |
|------|--------|
| Install + configure RedBeat | 15 min |
| Write/delete entries on schedule save | 30 min |
| Remove dispatcher code | 30 min |
| Update `ScheduledJobConfig` migration | 10 min |
| Update Job Scheduler page display | 15 min |
| Seed existing tenants | 10 min |
| Testing (save schedule, verify fires, check UI) | 30 min |
| **Total** | **~2–3 hours** |

## Risks

| Risk | Mitigation |
|------|------------|
| RedBeat has a Redis dependency | Already using Redis for broker + results |
| RedBeat entries persist in Redis; orphaned entries if tenant deleted | Clean up in tenant deletion flow |
| Redis restart loses schedules | RedBeat entries survive Redis restart (persisted to disk via Redis RDB/AOF). Re-seed script as backup. |
| Beat must be restarted to pick up the new scheduler class | One-time restart during deploy |
| `celery-redbeat` maintenance/compatibility | Well-maintained, 1.5k+ GitHub stars, works with Celery 5.x |

## Decision

Proceed? The migration is ~2–3 hours of work, removes ~120 lines of dispatcher
code, eliminates 1,440 daily no-op tasks, and makes the Job Scheduler UI show
accurate schedules natively.
