# Implementation Plan
## Adoption Sync Integrity, Tenant Settings, and Provenance

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | In Progress (Phases 0-4 complete; Phase 5 in progress) |
| **Last Updated** | Mar 2, 2026 |
| **Tech Spec Reference** | `features/active/adoption-sync-integrity/02_TECHNICAL_SPEC.md` |
| **Estimated Total Time** | 6-9 dev days |

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Implementation Phases](#implementation-phases)
3. [Database Migrations](#database-migrations)
4. [Deployment Checklist](#deployment-checklist)
5. [Rollback Plan](#rollback-plan)
6. [Progress Tracking](#progress-tracking)

---

## Prerequisites

Before starting implementation:

- [x] Product scope approved (`01_PRODUCT_SPEC.md`)
- [x] Technical approach drafted (`02_TECHNICAL_SPEC.md`)
- [x] Resolve open technical decisions:
  - [x] Storage location for adoption sync config (new table)
  - [x] Final permission matrix for tenant settings + scheduler endpoints
  - [x] `scheduled_job_executions` metadata strategy (JSON + typed `sync_run_id`)
- [ ] Confirm fresh-install behavior for new migration path
- [ ] Confirm no remaining cross-tenant dependency on platform scheduler endpoints (API-level audit)

---

## Implementation Phases

### Phase 0: Finalize Decisions + Scaffolding (Est: 0.5 day)

#### Task 0.1: Lock unresolved technical decisions

**Owner:** Backend lead  
**Files:** `02_TECHNICAL_SPEC.md` (decision section)

**Changes:**
1. Finalize sync config storage approach.
2. Finalize permissions on:
   - `GET/PUT /api/v1/admin/adoption-settings`
   - tenant scheduler endpoints.
3. Finalize execution-history metadata shape.

**Checkpoint:** Team confirms no blocking open technical question remains.

---

### Phase 1: Data Foundation (Est: 1-1.5 days)

#### Task 1.1: Migration - adoption sync config storage

**Files:**
- `alembic/versions/[rev]_add_adoption_sync_config.py`
- `src/models/[model-file].py` (or `src/models/adoption.py`)

**Changes:**
1. Create config storage for per-tenant:
   - `initial_sync_start_date`
   - schedule fields (`enabled`, `cron`).
2. Add tenant index/unique constraint.
3. Implement downgrade.

**Checkpoint:** `alembic upgrade head` succeeds locally.

---

#### Task 1.2: Migration - sync provenance columns

**Files:**
- `alembic/versions/[rev]_add_sync_run_id_to_adoption_tables.py`
- `src/models/adoption.py`

**Changes:**
1. Add `sync_run_id` (UUID) to:
   - `adoption_conversations`
   - `adoption_daily_metrics`.
2. Add indexes on `sync_run_id`.
3. Keep nullable for legacy compatibility.

**Checkpoint:** ORM queries function with new columns present.

---

### Phase 2: Backend Sync Logic (Est: 2-2.5 days)

#### Task 2.1: Tenant-scoped sync execution

**Files:**
- `src/tasks/adoption_sync_tasks.py`
- `src/api/routes/tenant_admin.py`
- `src/api/routes/platform_admin.py`

**Changes:**
1. Ensure sync trigger requires `customer_id` context.
2. Remove/deprecate platform adoption scheduler paths.
3. Ensure tenant scheduler list/trigger/stream are isolated by tenant.

**Checkpoint:** Tenant A cannot view/trigger tenant B jobs.

---

#### Task 2.2: Configurable start date + integrity recovery path

**Files:**
- `src/services/adoption/sync_service.py`
- `src/api/routes/tenant_admin.py`
- `src/api/schemas/[adoption settings schemas].py`

**Changes:**
1. Replace hardcoded initial lookback fallback with configured start date.
2. Add pre-sync consistency check.
3. Add cleanup path:
   - prefer `sync_run_id` rollback
   - fallback to date-based cleanup for legacy rows.
4. Record cleanup details for execution history.

**Checkpoint:** First sync uses user-configured date; recovery works on partial failure.

---

#### Task 2.3: OOM optimization (GPT metadata caching)

**Files:**
- `src/services/adoption/openai_compliance_client.py`
- `src/services/adoption/sync_service.py`

**Changes:**
1. Cache GPT metadata once per sync run/client instance.
2. Reuse cached GPT lookup across daily summary loop.
3. Add guard logging to confirm no repeated GPT list fetches per day.

**Checkpoint:** Logs show one GPT metadata fetch per run, not per day.

---

### Phase 3: API + Scheduler Visibility (Est: 1-1.5 days)

#### Task 3.1: Adoption settings endpoint

**Files:**
- `src/api/routes/tenant_admin.py`
- `src/api/schemas/[adoption settings schemas].py`

**Changes:**
1. Add `GET /api/v1/admin/adoption-settings`.
2. Add `PUT /api/v1/admin/adoption-settings`.
3. Validate start date and schedule payload.

**Checkpoint:** Endpoint round-trip works from API docs/manual test.

---

#### Task 3.2: Integrity check endpoint

**Files:**
- `src/api/routes/adoption.py`
- `src/api/schemas/[integrity schemas].py`

**Changes:**
1. Add `GET /api/v1/adoption/sync/integrity-check`.
2. Return consistency status + recommended recovery hint.

**Checkpoint:** Endpoint reflects expected state for healthy vs tampered sample data.

---

#### Task 3.3: Scheduler event enrichment

**Files:**
- `src/tasks/adoption_sync_tasks.py`
- scheduler stream payload mapping file(s)

**Changes:**
1. Emit auto-recovery events.
2. Include cleanup metadata and `sync_run_id` in execution details.

**Checkpoint:** Tenant scheduler stream displays recovery events with context.

---

### Phase 4: Frontend UX Consolidation (Est: 1.5-2 days)

#### Task 4.1: New Adoption Settings page (single source of truth)

**Files:**
- `frontend/src/pages/admin/AdoptionSettingsPage.tsx`
- `frontend/src/pages/admin/AdoptionAccessPage.tsx` (component extraction/reuse)
- `frontend/src/App.tsx`
- `frontend/src/components/navigation/sectionConfigs.ts`

**Changes:**
1. Build page sections:
   - setup wizard (start date/provider/schedule)
   - sync status
   - access sharing (embedded).
2. Route at `/admin/adoption-settings`.
3. Replace standalone Adoption Access nav with consolidated Adoption Settings entry.

**Checkpoint:** Tenant admin can complete setup and manage sharing from one page.

---

#### Task 4.2: Dashboard + scheduler UX alignment

**Files:**
- `frontend/src/pages/adoption/AdoptionDashboardPage.tsx`
- `frontend/src/pages/admin/JobSchedulerPage.tsx`
- `frontend/src/hooks/useJobSchedulerStream.ts`

**Changes:**
1. Dashboard top-right "Last synced" control links to Adoption Settings.
2. Dashboard empty state CTA: "Set up Adoption Sync".
3. Job Scheduler remains ops-only:
   - status/history/run now
   - "Configure" links to Adoption Settings
   - no inline schedule editing.

**Checkpoint:** No duplicated schedule controls in UI.

---

### Phase 5: Stabilization + Validation (Est: 1 day)

#### Task 5.1: Test pass + bug fixes

**Files:**
- `tests/...` (backend + frontend related tests)

**Changes:**
1. Unit tests for sync date selection, integrity checks, provenance cleanup.
2. Integration tests for settings endpoints and tenant scheduler isolation.
3. E2E smoke for first-time setup path.

**Checkpoint:** All required tests pass in CI and local smoke runs.

**Current Validation Status (Mar 2, 2026):**
- ✅ DB migration upgraded to head (`zz27_adoption_sync_cfg`) in running app container.
- ✅ Adoption settings load failure resolved (missing `adoption_sync_configs` table fixed by migration).
- ⚠️ `pytest -q` currently fails due to unrelated script-style test discovery issues in `scripts/`:
  - `scripts/test_data_analyst_single_question.py::test_single_question` (missing fixture `question`)
  - `scripts/utilities/test_openai_key.py::test_model` (missing fixture `client`)
- ⚠️ Frontend production build fails due to pre-existing repo-wide lint violations unrelated to this feature area.
- ⚠️ `scripts/validate_feature.py --all` reports existing repository failures unrelated to this feature scope.

---

## Database Migrations

### Migration A: Sync Config Storage

**File:** `alembic/versions/[rev]_add_adoption_sync_config.py`

**Run Order:** First

### Migration B: Provenance Columns

**File:** `alembic/versions/[rev]_add_sync_run_id_to_adoption_tables.py`

**Run Order:** Second

### Migration Notes

- Keep `sync_run_id` nullable for compatibility with existing rows.
- Add index on `sync_run_id` for rollback queries.
- Use forward-only migration in production unless explicit data export is performed.

---

## Deployment Checklist

### Pre-Deployment

- [ ] All backend tests passing (currently blocked by unrelated script-style tests in `scripts/`)
- [ ] Frontend build passes (currently blocked by pre-existing repo-wide lint violations)
- [ ] Migrations tested against fresh DB
- [x] Tenant-permission checks validated for adoption settings and tenant admin path
- [ ] Product sign-off on settings page copy/warnings

### Deployment Steps

1. [ ] Run DB migrations (`alembic upgrade head`).
2. [ ] Deploy backend updates.
3. [ ] Deploy frontend updates.
4. [ ] Rebuild and restart both app and worker images.
5. [ ] Smoke test:
   - Adoption Settings load/save
   - Tenant Job Scheduler load/trigger
   - Dashboard "Last synced" and empty-state CTA.

### Post-Deployment Verification

- [ ] No platform-level adoption scheduler menu/routes in active tenant flow
- [ ] Tenant isolation confirmed
- [ ] `sync_run_id` appears on new sync rows
- [ ] Recovery events visible in scheduler history/stream

---

## Rollback Plan

If issues are detected:

### App Rollback

1. Revert frontend deployment first.
2. Revert backend deployment second.
3. Keep migrations if data already written with `sync_run_id`.

### Data Rollback

- For bad sync data: delete by `sync_run_id` (preferred).
- For legacy rows without provenance: use date-based fallback with explicit operator confirmation.

### Operational Safeguard

- Temporarily disable schedule in Adoption Settings to stop recurring failures while investigating.

---

## Progress Tracking

### Overall Progress

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 0: Decisions + Scaffolding | ✅ Complete | 100% |
| Phase 1: Data Foundation | ✅ Complete | 100% |
| Phase 2: Backend Sync Logic | ✅ Complete | 100% |
| Phase 3: API + Visibility | ✅ Complete | 100% |
| Phase 4: Frontend UX Consolidation | ✅ Complete | 100% |
| Phase 5: Stabilization + Validation | 🟡 In Progress | 60% |

### Detailed Task Tracking

| Phase | Task | Status | Assignee | Notes |
|-------|------|--------|----------|-------|
| 0 | 0.1 Finalize open decisions | ✅ | | Decisions locked in spec updates |
| 1 | 1.1 Migration: sync config storage | ✅ | | Migration applied; table verified |
| 1 | 1.2 Migration: sync_run_id columns | ✅ | | Migration applied with indexes |
| 2 | 2.1 Tenant-scoped sync tasks/routes | ✅ | | Tenant-scoped sync path implemented |
| 2 | 2.2 Start-date + integrity recovery | ✅ | | Configurable start date + recovery path implemented |
| 2 | 2.3 GPT metadata cache | ✅ | | Cache + reuse implemented |
| 3 | 3.1 Adoption settings endpoint | ✅ | | GET/PUT endpoint live |
| 3 | 3.2 Integrity-check endpoint | ✅ | | Endpoint implemented |
| 3 | 3.3 Scheduler event enrichment | ✅ | | Provenance/recovery metadata surfaced |
| 4 | 4.1 Adoption Settings page | ✅ | | DS-aligned consolidated page shipped |
| 4 | 4.2 Dashboard + scheduler UX alignment | ✅ | | Empty-state/last-synced/ops-only scheduler done |
| 5 | 5.1 Test + stabilization pass | 🟡 | | Validation run complete; blocked by unrelated repo baseline failures |

**Status Legend:** ⬜ Not Started | 🟡 In Progress | ✅ Complete | ❌ Blocked

---

## Notes

- This plan intentionally prioritizes safe, incremental delivery over a single large refactor.
- Phase 2 and Phase 4 can run partially in parallel after migration contracts are locked.
- If timeline pressure increases, ship Phase 1 + Phase 2 first, then Phase 4 UI consolidation, then Phase 3 provenance exposure improvements.
