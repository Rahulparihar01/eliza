# Fix: RAG Eval `ObjectDeletedError` Crash

## Problem

Eval runs crash in the celery worker with:

```
sqlalchemy.orm.exc.ObjectDeletedError: Instance '<RAGEvalRun at 0x...>'
has been deleted, or its row is otherwise not present.
```

Two crash sites:
1. `_evaluate_single` (line 628): `if eval_run.validate_citations`
2. `_emit_telemetry` (line 685): `eval_run_id=eval_run.id`

The error handler (line 1152-1175) also crashes trying to access `eval_run.id` / `eval_run.status`, turning a recoverable error into an unrecoverable one.

## Root Cause

`RAGEvalService` receives a live SQLAlchemy ORM object (`eval_run`) and shares a single `self.db` session across the entire long-running async evaluation. The problem:

1. `_emit_telemetry` calls `self.db.commit()` after every progress event
2. Each `commit()` expires all ORM objects in the session (SQLAlchemy default behavior)
3. Next access to `eval_run.validate_citations` or `eval_run.id` triggers a lazy-load refresh
4. If the row was deleted (user clicked "Delete" in the UI) or the session is in a bad state, SQLAlchemy raises `ObjectDeletedError`
5. The `except` block (line 1152) also crashes because it accesses the same expired `eval_run`

## Fix (3 changes, all in `rag_eval_service.py`)

### Change 1: Snapshot scalar fields at the start of `run_evaluation_v2`

Instead of accessing `eval_run.validate_citations`, `eval_run.id`, `eval_run.concurrency` etc. throughout the method, read them once into local variables right after the first commit.

```python
# At the top of run_evaluation_v2, after the first commit:
eval_run.status = EvalRunStatus.RUNNING
eval_run.started_at = datetime.utcnow()
self.db.commit()

# Snapshot immutable fields so we never need to lazy-load them again
run_id = eval_run.id
run_run_id = eval_run.run_id
run_domain = eval_run.domain
run_concurrency = eval_run.concurrency
run_validate_citations = eval_run.validate_citations
run_eval_source = eval_run.eval_source
run_eval_set_id = eval_run.eval_set_id
run_eval_set_name = eval_run.eval_set_name
```

Then use `run_id`, `run_validate_citations`, etc. everywhere instead of `eval_run.id`, `eval_run.validate_citations`.

### Change 2: Make `_emit_telemetry` accept `eval_run_id: int` instead of `eval_run: RAGEvalRun`

```python
def _emit_telemetry(
    self,
    eval_run_id: int,          # <-- plain int, not ORM object
    event_type: str,
    stage_name: str = None,
    message: str = None,
    progress: float = None,
    data: Dict = None,
):
    event = RAGEvalTelemetryEvent(
        eval_run_id=eval_run_id,  # <-- no ORM access
        ...
    )
    try:
        self.db.add(event)
        self.db.commit()
    except Exception:
        self.db.rollback()
```

Update all call sites to pass `run_id` instead of `eval_run`.

### Change 3: Wrap the error handler to be crash-proof

```python
except Exception as e:
    logger.error(f"Evaluation failed: {e}", exc_info=True)
    try:
        # Re-fetch the run fresh — it may have been deleted
        fresh_run = self.db.query(RAGEvalRun).filter(RAGEvalRun.id == run_id).first()
        if fresh_run:
            fresh_run.status = EvalRunStatus.FAILED
            fresh_run.error_message = str(e)[:2000]
            fresh_run.completed_at = datetime.utcnow()
            self.db.commit()
    except Exception as db_err:
        logger.error(f"Failed to update run status: {db_err}")
        self.db.rollback()
    
    # Telemetry is best-effort
    try:
        self._emit_telemetry(run_id, "error", "Error", f"Evaluation failed: {str(e)}", -1)
    except Exception:
        pass
    raise
```

## Files Changed

| File | Change |
|------|--------|
| `src/services/rag_eval_service.py` | All 3 changes above |

## Not Changed

- `src/tasks/rag_eval_tasks.py` — no changes needed, it passes the ORM object to the service
- Database schema — no migrations
- Frontend — no changes

## Testing

1. Start an eval run
2. While running, delete it from the UI → should log a warning, not crash the worker
3. Start an eval run normally → should complete with metrics as before
4. Check celery logs for no `ObjectDeletedError`

## Secondary Issue: Clock Drift

The celery logs also show:

```
Substantial drift from celery@... may mean clocks are out of sync. Current drift is 35 seconds.
```

This is a Docker container time sync issue. Fix: restart Docker Desktop, or run `docker run --rm --privileged alpine hwclock -s` to resync. Not blocking but can cause task scheduling jitter.
