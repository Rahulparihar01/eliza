# Technical Specification
## Adoption Sync Integrity, Tenant Settings, and Provenance

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft |
| **Last Updated** | Feb 6, 2026 |
| **PRD Reference** | `features/active/adoption-sync-integrity/01_PRODUCT_SPEC.md` |
| **Author** | Development Agent + Steven |

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Data Model](#data-model)
4. [API Design](#api-design)
5. [Integration Points](#integration-points)
6. [Security Considerations](#security-considerations)
7. [Error Handling](#error-handling)
8. [Performance Considerations](#performance-considerations)
9. [Testing Strategy](#testing-strategy)
10. [Migration Strategy](#migration-strategy)
11. [Agent Review Notes](#agent-review-notes)

---

## Overview

This feature addresses three production issues in adoption sync: (1) partial syncs leave adoption tables inconsistent, (2) sync execution was platform-scoped and caused cross-tenant failures/OOM risk, and (3) cleanup logic relied on date heuristics rather than deterministic run lineage.

The technical approach shifts adoption sync control to tenant scope, adds pre-sync integrity checks with auto-recovery, and introduces per-run provenance (`sync_run_id`) so rollback can be surgical. It also consolidates tenant setup UX into a single `Adoption Settings` page that owns sync configuration (including initial start date), while `Job Scheduler` remains operational/monitoring only.

Implementation is phased to reduce risk and get value quickly: Phase 1 (safety and tenant scope), Phase 2 (visibility and UX), Phase 3 (provenance and surgical rollback).

### Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Tenant-scoped sync execution (`customer_id` required) | Prevents cross-tenant interference and eliminates platform-wide chord fan-out risk |
| Single source of truth for schedule config = Adoption Settings page | Avoids duplicated controls between setup and scheduler surfaces |
| User-configured initial sync start date | Replaces hardcoded fallback and makes onboarding explicit |
| `sync_run_id` on fact tables | Enables deterministic rollback by run, not date guesses |
| Keep Job Scheduler as ops-only | Preserves operational visibility while reducing configuration confusion |

### Implementation Phasing

| Phase | Goal | Exit Criteria |
|------|------|---------------|
| Phase 1 | Integrity + tenant scope + OOM fix | Tenant sync runs safely; no hardcoded start-date fallback in first setup path; no platform scheduler dependency for adoption |
| Phase 2 | Visibility + consolidated settings UX | Adoption Settings page live; dashboard links and empty state live; tenant scheduler operational view in place |
| Phase 3 | Provenance + surgical rollback | `sync_run_id` stamped on all affected rows; cleanup by run ID available and used in recovery paths |

---

## Architecture

### System Context

This feature spans FastAPI routes, Celery tasks, adoption sync services, SQLAlchemy models/migrations, and tenant-facing React pages. The major architecture change is replacing platform-triggered adoption sync orchestration with tenant-scoped execution and tenant-owned configuration.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Frontend                                                                    │
│  - Adoption Dashboard (last synced + setup CTA)                             │
│  - Tenant Admin: Adoption Settings (config)                                 │
│  - Tenant Admin: Job Scheduler (ops/monitoring)                             │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ HTTP + SSE
┌─────────────────────────────────────────────────────────────────────────────┐
│ FastAPI                                                                     │
│  - /api/v1/admin/adoption-settings (GET/PUT)                                │
│  - /api/v1/admin/jobs/* (tenant-scoped scheduler ops)                       │
│  - /api/v1/adoption/sync/integrity-check                                    │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ Celery task dispatch (tenant-scoped)
┌─────────────────────────────────────────────────────────────────────────────┐
│ Celery + Services                                                            │
│  - adoption.sync_provider(customer_id, provider_id, ...)                    │
│  - pre-sync integrity check + cleanup                                        │
│  - sync_run_id generation and row stamping                                   │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
┌─────────────────────────────────────────────────────────────────────────────┐
│ PostgreSQL                                                                   │
│  - adoption_daily_metrics (sync_run_id)                                      │
│  - adoption_conversations (sync_run_id)                                      │
│  - adoption sync config storage (initial start date + schedule config)       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
AdoptionSettingsPage
  ├─ SyncSetupSection (start date, provider summary, schedule)
  ├─ SyncStatusSection (last sync, health, recent state)
  └─ AccessSharingSection (embedded current tenant access UI)

AdoptionDashboardPage
  ├─ LastSyncedControl -> link to /admin/adoption-settings
  └─ EmptyStateCTA -> link to /admin/adoption-settings

JobSchedulerPage (tenant)
  ├─ Job list + run now + history
  └─ Configure action -> link to /admin/adoption-settings
```

### Data Flow

#### Flow A: First-time setup + initial sync
1. Tenant admin opens Adoption Settings page.
2. Frontend `GET /api/v1/admin/adoption-settings`.
3. User sets `initial_sync_start_date` and schedule; frontend `PUT /api/v1/admin/adoption-settings`.
4. User clicks Run Now (either here or Job Scheduler).
5. Backend dispatches tenant-scoped sync task.
6. Sync service runs integrity check, then sync, then records execution state.

#### Flow B: Scheduled run
1. Celery beat schedules tenant job execution.
2. Task runs with tenant `customer_id`.
3. Service computes effective start date from last complete sync; fallback to configured initial date (not hardcoded).
4. Service executes sync with `sync_run_id`; logs cleanup/recovery as needed.

#### Flow C: Recovery
1. Integrity check detects partial inconsistency.
2. If run provenance available, cleanup targets failed/partial `sync_run_id`.
3. If provenance unavailable (legacy rows), fallback cleanup by date heuristics.
4. Recovery event emitted to scheduler stream; execution details persisted.

---

## Data Model

### New Tables

```sql
CREATE TABLE adoption_sync_configs (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL UNIQUE,
    initial_sync_start_date DATE NOT NULL,
    schedule_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    schedule_cron VARCHAR(100) NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_adoption_sync_configs_customer_id
    ON adoption_sync_configs(customer_id);
```

> Note: if existing provider tables already hold schedule data cleanly, this can be embedded there. Preferred default is dedicated `adoption_sync_configs` for clear ownership and fewer side effects.

### Modified Tables

| Table | Change | Migration Notes |
|-------|--------|-----------------|
| `adoption_conversations` | Add `sync_run_id UUID NULL` + index | Backfill not required for fresh install; legacy rows remain NULL |
| `adoption_daily_metrics` | Add `sync_run_id UUID NULL` + index | Same as above |
| `scheduled_job_executions` (if available) | Add `sync_run_id UUID NULL` and recovery metadata fields | Optional if metadata can be stored in JSON payload safely |

### Entity Relationships

```
customers 1──────1 adoption_sync_configs
    │
    ├──────* adoption_conversations (sync_run_id)
    └──────* adoption_daily_metrics (sync_run_id)

scheduled_job_executions *──────0..1 sync_run_id (logical linkage)
```

---

## API Design

### New Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/admin/adoption-settings` | Fetch tenant adoption sync settings + sharing summary | `adoption:read` |
| PUT | `/api/v1/admin/adoption-settings` | Update start date and schedule config | `adoption:write` or `adoption:manage_sharing` (finalize) |
| GET | `/api/v1/adoption/sync/integrity-check` | On-demand integrity diagnostics for current tenant | `adoption:read` |
| GET | `/api/v1/admin/jobs` | Tenant-scoped job list | `system:admin` or tenant admin permission |
| POST | `/api/v1/admin/jobs/{job_name}/trigger` | Trigger tenant-scoped job run | `system:admin` or tenant admin permission |
| GET | `/api/v1/admin/jobs/stream` | Tenant-scoped scheduler SSE stream | `system:admin` or tenant admin permission |

### Request/Response Models

```python
# src/api/schemas/adoption_settings.py

class AdoptionSettingsResponse(BaseModel):
    customer_id: str
    initial_sync_start_date: date
    schedule_enabled: bool
    schedule_cron: str | None
    last_synced_at: datetime | None
    sync_health: Literal["healthy", "recovering", "degraded", "unknown"]

class AdoptionSettingsUpdateRequest(BaseModel):
    initial_sync_start_date: date | None = None
    schedule_enabled: bool | None = None
    schedule_cron: str | None = None
```

```python
# src/api/schemas/adoption_integrity.py

class AdoptionIntegrityCheckResponse(BaseModel):
    customer_id: str
    is_consistent: bool
    last_complete_sync_date: date | None
    detected_gap_days: int | None
    suggested_recovery_start_date: date | None
    suggested_recovery_run_id: UUID | None
```

### API Examples

```bash
# Fetch tenant settings
curl -X GET /api/v1/admin/adoption-settings \
  -H "Authorization: Bearer $TOKEN"

# Update initial start date and schedule
curl -X PUT /api/v1/admin/adoption-settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"initial_sync_start_date":"2026-01-01","schedule_enabled":true,"schedule_cron":"0 6 * * *"}'
```

---

## Integration Points

### Existing Services

| Service | Usage | Location |
|---------|-------|----------|
| Adoption sync orchestrator | Add pre-sync integrity + cleanup + provenance stamping | `src/services/adoption/sync_service.py` |
| OpenAI compliance client | Add GPT metadata cache to prevent repeated fetches | `src/services/adoption/openai_compliance_client.py` |
| Tenant admin routes | Add settings and tenant scheduler endpoints | `src/api/routes/tenant_admin.py` |
| Platform admin routes | Remove/deprecate adoption scheduler endpoints | `src/api/routes/platform_admin.py` |

### External APIs

| API | Purpose | Auth Method |
|-----|---------|-------------|
| OpenAI Compliance API | Conversations + GPT metadata + daily summaries | API key (encrypted at rest) |

### Celery Tasks

| Task | Purpose | Queue |
|------|---------|-------|
| `adoption.daily_sync` | Tenant-scoped scheduled sync execution | `default` |
| `adoption.sync_provider` | Provider-specific sync with integrity checks and provenance | `default` |
| `adoption.sync_chord_error` | Legacy safeguard while removing platform chord paths | `default` |

---

## Security Considerations

### Authentication & Authorization

- Tenant endpoints require authenticated tenant context and permission checks.
- All queries and writes must be scoped by `customer_id`.
- Platform endpoints for adoption scheduler should be removed or return deprecation error.

### Multi-tenant Isolation

- `customer_id` is required on all scheduler and settings operations.
- Job listing and execution history must never leak cross-tenant rows.
- SSE stream filtering must be tenant-aware end-to-end.

### Data Validation

| Input | Validation |
|-------|------------|
| `initial_sync_start_date` | Must be <= yesterday; not in future |
| `schedule_cron` | Cron format validation; reject invalid expressions |
| `job_name` | Must be allowlisted (`adoption.daily_sync`) for tenant scheduler trigger |

---

## Error Handling

| Error Case | HTTP Code | Response | Handling |
|------------|-----------|----------|----------|
| Adoption settings missing | 404 or auto-create then 200 | `{"detail":"Settings not found"}` (if strict) | Prefer lazy create on first GET |
| Invalid start date (future) | 422 | Validation error | Pydantic + explicit guard |
| Unauthorized tenant access | 403 | `{"detail":"Permission denied"}` | Authorization middleware |
| Integrity check fails unexpectedly | 500 | `{"detail":"Integrity check failed"}` | Log + return actionable message |
| Sync task failure | 200 from trigger with execution failure in stream/history | Structured execution error payload | Preserve run record with failure reason |

---

## Performance Considerations

### Caching Strategy

- Cache GPT metadata once per sync client instance/run.
- Reuse GPT lookup across day-by-day metrics aggregation.

### Query Optimization

- Add index on `sync_run_id` for both adoption fact tables.
- Keep existing date-range indexes used by dashboard queries.
- Keep tenant filter (`customer_id`) in all cleanup and read queries.

### Operational Limits

- Remove parallel platform fan-out/chord for adoption sync.
- Tenant-triggered runs reduce peak memory by isolating workload.
- If needed, enforce one active sync per tenant via lock/status guard.

---

## Testing Strategy

### Unit Tests

- `sync_service` computes effective start date from settings when no previous sync.
- Integrity check identifies mismatched conversation vs daily metrics boundaries.
- Cleanup by `sync_run_id` deletes only rows for that run.
- GPT caching avoids repeated `get_all_gpts()` calls in daily loop.

### Integration Tests

- `GET/PUT /admin/adoption-settings` works and persists per tenant.
- Tenant scheduler endpoints only return current tenant jobs.
- Triggered sync run stamps `sync_run_id` on conversations and daily metrics.
- Auto-recovery emits execution metadata and SSE event.

### E2E Tests

- First-time tenant opens dashboard -> empty state -> Adoption Settings wizard -> Run Now -> dashboard populated.
- Job Scheduler displays run status/history and links to Adoption Settings for config.
- Access sharing section works within consolidated Adoption Settings page.

---

## Migration Strategy

### Database Migration

1. Add `adoption_sync_configs` table.
2. Add `sync_run_id` columns + indexes to:
   - `adoption_conversations`
   - `adoption_daily_metrics`
3. Optionally extend `scheduled_job_executions` for provenance fields.

### Deployment Order

1. Run database migrations.
2. Deploy backend changes (routes, services, tasks).
3. Deploy frontend changes (Adoption Settings, dashboard links, scheduler UX).
4. Rebuild and redeploy both `app` and `celery-worker`.
5. Verify tenant scheduler and first-time setup flow.

### Rollback Plan

1. Revert frontend first (safe UI rollback).
2. Revert backend routes/services/tasks.
3. Keep schema columns (`sync_run_id`) if already populated; avoid downgrade data loss in production.
4. If strict downgrade required, export affected rows before dropping new columns/tables.

---

## Agent Review Notes

### Questions Asked During Review

| Question | Resolution |
|----------|------------|
| Should V2 proceed? | Yes, approved |
| What from V3 is in scope? | Only `sync_run_id` provenance and surgical rollback |
| Separate Adoption Access page? | No, merge into Adoption Settings page |
| Is dual schedule UI confusing? | Resolved by making Adoption Settings config-only and Job Scheduler ops-only |
| Initial sync lookback hardcoded? | Replace with user-selected start date in settings |

### Edge Cases Identified

| Edge Case | Handling |
|-----------|----------|
| Tenant has no settings row yet | Lazy-create defaults on first read |
| Tenant already has partial legacy data with NULL `sync_run_id` | Fallback recovery heuristics by date where provenance absent |
| User changes start date after first successful sync | Require explicit warning/confirmation; create new run lineage |
| Concurrent trigger attempts for same tenant | Block second run while one is active; return informative message |

### Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Mixed legacy + new provenance data complicates cleanup | Medium | High | Support dual recovery paths (`sync_run_id` preferred, date fallback) |
| Permission ambiguity for tenant scheduler/actions | Medium | Medium | Define explicit permission matrix before implementation |
| UI sprawl in Adoption Settings page | Low | Medium | Keep sections modular and collapsible |
| Regression from platform endpoint removal | Medium | Medium | Route audit + deprecation window + integration tests |

---

## Open Technical Questions

- [ ] Should adoption settings storage be a dedicated `adoption_sync_configs` table or embedded in existing provider config?
- [ ] Which permission should own settings write: `adoption:write`, `adoption:manage_sharing`, or a new scope?
- [ ] Should `scheduled_job_executions` get typed provenance columns, or should recovery metadata remain JSON payload?
- [ ] Do we enforce hard lock (1 active sync per tenant) at DB level, task level, or both?
