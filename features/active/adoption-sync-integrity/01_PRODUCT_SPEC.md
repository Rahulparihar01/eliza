# Adoption Sync Integrity & Auto-Recovery

**Status:** Scope Approved  
**Date:** Feb 6, 2026  
**Author:** AI Agent + Steven  
**Priority:** High -- data integrity issue with no current safeguards  
**Approved Scope:** V1 + V2 + V3 (sync_run_id only)

---

## Problem Statement

The adoption sync process can leave tables in an inconsistent state when a sync partially completes. This has already caused a real production issue:

- **What happened:** On Feb 2, a manual sync was triggered. The conversations table synced ~1,784 records (up through Feb 2), but the daily metrics aggregation step never completed because the Celery chord callback never fired. The job was stuck in "running" for 4 days.
- **Result:** `adoption_conversations` had data through Feb 2, but `adoption_daily_metrics` only had data through Jan 11. The dashboard (which relies on daily metrics) appeared frozen at Jan 11 while raw data existed well beyond that.
- **Manual fix required:** Had to manually delete 1,784 partial conversation records and reset the job status to get back to a clean state.

This will happen again because there are **zero integrity checks** in the current sync pipeline.

---

## Current Architecture (What Exists Today)

### Sync Pipeline (4-step sequential process inside `_sync_openai`)

```
Step 1: Sync GPTs (global metadata)
   └── commits per batch
Step 2: Sync Conversations (batched, memory-safe)
   └── commits per batch (100 at a time)
Step 3: Update User-GPT Interactions (aggregated from conversations)
   └── single commit
Step 4: Sync Daily Metrics (one day at a time from API)
   └── single commit at the end
```

### Five Adoption Tables

| Table | What It Stores | Sync Step |
|-------|---------------|-----------|
| `adoption_gpts` | GPT metadata (45 records) | Step 1 |
| `adoption_conversations` | Individual conversation records (913 records) | Step 2 |
| `adoption_user_gpt_interactions` | Aggregated user-GPT usage (15 records) | Step 3 |
| `adoption_daily_metrics` | Daily aggregated stats for dashboard (37 records) | Step 4 |
| `adoption_data_shares` | Data sharing configs | N/A (not part of sync) |

### How "Last Sync Date" Is Determined

```python
# Only checks adoption_daily_metrics -- ignores all other tables
result = db.query(AdoptionDailyMetrics.metric_date)
    .filter(customer_id=..., source_type=...)
    .order_by(metric_date.desc())
    .first()
```

This means the sync determines "where to start" based solely on daily metrics. If conversations synced further ahead but metrics didn't, the next sync won't re-pull those conversation dates -- it will start from where metrics left off. But the conversations for those dates already exist, creating duplicates or gaps.

### What's NOT in Place

| Safeguard | Exists? | Notes |
|-----------|---------|-------|
| Cross-table consistency check | No | No validation that tables are in sync |
| Atomic sync (all-or-nothing) | No | Each step commits independently |
| Rollback on partial failure | No | Successful steps remain committed |
| Stale run detection | Now yes | Just added -- resets jobs stuck >30 min |
| Sync watermark / checkpoint | No | Only uses daily_metrics max date |
| Data cleanup before re-sync | No | No mechanism to purge partial data |
| Sync transaction/run ID | No | No way to identify which records came from which sync run |

---

## Proposed Feature: Sync Integrity & Auto-Recovery

### Core Idea

When a sync is triggered (manual or scheduled), the system should:

1. **Detect inconsistency** -- Check if the adoption tables are out of sync with each other
2. **Clean up partial data** -- Delete any records that exist beyond the last fully-complete sync point
3. **Re-sync from the clean point** -- Pull fresh data starting from the last consistent date

### User Experience

**From the Adoption Dashboard (top-right sync control):**

```
User clicks "Last synced: <timestamp>" control, then "Refresh now"
    │
    ▼
System checks table consistency
    │
    ├── All tables in sync? ──────────► Normal sync from last date + 1
    │
    └── Tables out of sync? ──────────► Show notification:
                                           "Detected incomplete sync.
                                            Conversations: through Feb 2
                                            Daily Metrics: through Jan 11
                                            Cleaning up 1,784 partial records
                                            and re-syncing from Jan 12..."
                                               │
                                               ▼
                                        Delete partial data back to Jan 11
                                        Re-sync from Jan 12 to today
```

The user shouldn't have to do anything special -- clicking refresh should just work, even if the previous sync left things in a bad state.

### Consistency Check Logic

Define "last complete sync date" as the **minimum** of the max dates across the key tables:

```
last_complete_date = MIN(
    MAX(adoption_daily_metrics.metric_date),
    MAX(adoption_conversations.conversation_created_at)::date
)
```

If these two values differ, the sync is inconsistent.

**Note:** `adoption_gpts` and `adoption_user_gpt_interactions` are derived/aggregated data and don't need to participate in the watermark check. GPTs are global (not date-scoped), and interactions are rebuilt from conversations each sync.

### Cleanup Logic

When inconsistency is detected:

1. Identify the `last_complete_date` (the earlier of the two max dates)
2. Delete from `adoption_conversations` where `conversation_created_at > last_complete_date`
3. Delete from `adoption_daily_metrics` where `metric_date > last_complete_date`
4. Delete from `adoption_user_gpt_interactions` where records reference cleaned-up conversations
5. Log everything that was cleaned up (counts, date ranges)
6. Proceed with normal sync starting from `last_complete_date + 1`

### Where This Logic Lives

Two options:

**Option A: Pre-sync hook inside `sync_provider` (Recommended)**
- Add consistency check at the start of `AdoptionSyncService.sync_provider()`
- Before determining the date range, run the consistency check
- If inconsistent, clean up and adjust `start_date` accordingly
- Transparent to the caller -- works for both manual triggers and scheduled runs

**Option B: Separate API endpoint + UI prompt**
- Add a `/adoption/sync/integrity-check` endpoint
- Frontend calls it before triggering sync
- Shows user a dialog if inconsistent, asks to confirm cleanup
- More user control but more complex

---

## Detailed Requirements

### R1: Consistency Check Query

A single query that returns the sync watermark for each table:

```sql
SELECT
    (SELECT MAX(metric_date) FROM adoption_daily_metrics 
     WHERE customer_id = $1) as metrics_latest,
    (SELECT MAX(conversation_created_at)::date FROM adoption_conversations 
     WHERE customer_id = $1) as conversations_latest,
    (SELECT COUNT(*) FROM adoption_conversations 
     WHERE customer_id = $1 
     AND conversation_created_at::date > (
         SELECT COALESCE(MAX(metric_date), '1970-01-01') 
         FROM adoption_daily_metrics WHERE customer_id = $1
     )) as orphaned_conversations
```

### R2: Cleanup Operation

- Must be idempotent (safe to run multiple times)
- Must log what was deleted (table, count, date range)
- Must operate within a single transaction (cleanup is atomic even if sync isn't)
- Must respect `customer_id` (multi-tenant safe)

### R3: Sync Run Tracking (Nice-to-Have for V2)

Add a `sync_run_id` (UUID) column to conversations and daily metrics so we can:
- Identify which records came from which sync run
- Clean up by run ID instead of date range (more precise)
- Track sync provenance for debugging

### R4: SSE / UI Feedback

When auto-recovery triggers, the user should see:
- A status message indicating inconsistency was detected
- What's being cleaned up (counts)
- That the sync is proceeding from the corrected start point

### R5: Execution History Enhancement

The job execution record should capture:
- Whether auto-recovery was triggered
- How many records were cleaned up
- The adjusted sync start date

---

## Approved Scope (Feb 6)

### V1: Integrity & Tenant-Scoped Sync

- Consistency check at the start of `sync_provider`
- Automatic cleanup of orphaned data
- Logging of cleanup actions
- Adjusted start date based on last complete sync
- GPT re-fetch cache (OOM fix)
- Tenant-scoped sync (move from platform to tenant admin)
- Disable platform provider duplicate
- Expose tenant adoption access page in nav
- No UI changes needed for integrity -- works transparently

**Estimated effort:** Small-medium

### V2: Visibility & Ops (APPROVED)

- Everything in V1, plus:
- "Last synced at" control on adoption dashboard header with link to tenant scheduler
- SSE event for "auto-recovery triggered" shown in tenant Job Scheduler UI
- Execution history records cleanup details (was recovery triggered, rows cleaned, adjusted start date)
- `/adoption/sync/integrity-check` endpoint for on-demand health checks
- Per-tenant scheduler in tenant admin menu
- Better execution log detail for support/debugging

**Estimated effort:** Medium

### V3: Sync Run Provenance (APPROVED -- scoped down)

Only the `sync_run_id` provenance items. No audit log table, no admin UI for browsing history.

- `sync_run_id` (UUID) column added to `adoption_conversations` and `adoption_daily_metrics`
- Each sync run generates a UUID and stamps all rows it creates/updates
- Cleanup can delete by `sync_run_id` instead of date heuristics (surgical rollback)
- `sync_run_id` recorded in execution history for traceability

**NOT included (deferred):**
- ~~Sync audit log table~~
- ~~Admin UI for browsing sync history and data lineage~~
- ~~Shared workspace deduplication architecture~~

**Estimated effort:** Small -- one migration + minor service changes

---

## NEW: Move Sync to Tenant-Scoped (Critical)

**Discovered Feb 6, 2026 during live sync debugging.**

### The Problem

The current `daily_adoption_sync` task runs at the **platform level** -- it queries ALL providers with `is_adoption_source=true` across ALL tenants and syncs them in parallel via a Celery chord. This caused a real failure:

- Two providers exist: `eliza` (id=10) and `platform` (id=14), both pointing at the **same OpenAI workspace ID**
- The chord dispatched two parallel sync tasks, both hitting the same API and doubling memory usage
- One worker was OOM-killed (SIGKILL), leaving the chord incomplete
- The `platform` provider completed (2,670 conversations + 30 daily metrics)
- The `eliza` provider's worker died mid-conversation-sync, leaving partial data

### Current Architecture (Broken)

```
Platform Admin → Job Scheduler → daily_adoption_sync
                                    │
                                    ├── sync_adoption_provider(eliza, provider_id=10)    → Worker 2 (OOM KILLED)
                                    └── sync_adoption_provider(platform, provider_id=14) → Worker 1 (completed)
```

- Job is global (platform-scoped), syncs ALL tenants at once
- No tenant isolation -- one tenant's failure kills the whole chord
- Duplicate API calls when multiple tenants share the same workspace
- Memory doubles per additional tenant

### Proposed Architecture

```
Tenant Admin Settings → Adoption Sync → sync for THIS tenant only
                                           │
                                           └── sync_adoption_provider(eliza, provider_id=10)
```

### Requirements

**R5: Tenant-Scoped Sync Trigger**
- Move the "Run Now" sync trigger from Platform Admin → Job Scheduler to Tenant Admin → Adoption Settings
- Sync should only run for the current tenant's providers
- The `customer_id` must be passed to the sync task so it only queries providers for that tenant

**R6: Tenant-Scoped Scheduled Sync**
- Each tenant should have its own sync schedule (or opt-in to sync)
- Scheduled syncs should be per-tenant, not a single global job
- If a global job is kept, it should iterate tenants sequentially (not parallel chord) to avoid OOM

**R7: Deduplicate Shared Workspaces**
- If two tenants point at the same workspace ID, the API data only needs to be fetched once
- Consider: should a workspace be synced once and data copied to both tenants?
- Or: prevent duplicate workspace IDs across tenants (validation)

**R8: Memory-Safe Sync**
- The conversation sync fetches ~490 records per batch and re-fetches all GPTs each cycle
- With 26 days of backfill, this means thousands of API calls and growing memory
- Consider: reduce batch processing memory footprint, or add a memory limit check

### Tenant Investigation (Feb 6)

**How tenants are created:**
- `scripts/init_tenant.py` runs on container startup when `INIT_TENANT=true`
- Always creates the `platform` tenant (`customer_id="platform"`, name="Eliza Platform")
- Optionally creates an additional tenant from `CUSTOMER_ID` env var
- `.env` currently has `CUSTOMER_ID=local-dev` (not `eliza`)

**Tenants in the database (6 total):**

| customer_id | name | subscription_tier | Notes |
|-------------|------|-------------------|-------|
| `platform` | Eliza Platform | enterprise | Auto-created by init script. System tenant for platform admin. |
| `eliza` | Eliza | basic | The real tenant. Adoption data should live here. |
| `caylent` | Local Development Customer | development | From `CUSTOMER_ID=local-dev` mapping |
| `acme` | Acme | standard | Test tenant |
| `steve-org` | Steve's Org | enterprise | Test tenant |
| `test2` | test2 | standard | Test tenant |

**How the `platform` provider (id=14) got created:**
- Not auto-seeded. Created manually via the Platform Admin UI (`POST /api/v1/platform-admin/ai-providers`)
- Someone (likely during setup) created an OpenAI provider under the `platform` tenant and marked it `is_adoption_source=true`
- It uses the **same workspace ID** as the `eliza` provider -- it's a duplicate

**Conclusion:**
- The `platform` tenant is a system/admin tenant, not an actual customer tenant
- Adoption data should only be synced for the `eliza` tenant
- The `platform` provider (id=14) with `is_adoption_source=true` is a mistake -- should be disabled or removed
- The sync job should be tenant-scoped so this can't happen again

### Impact on Scope

| Scope Level | What Changes |
|-------------|-------------|
| V1 | Add `customer_id` filter to `daily_adoption_sync`; move trigger to tenant admin; remove/disable platform provider; GPT cache fix |
| V2 | Per-tenant scheduled sync; tenant admin scheduler page; "Last synced" dashboard control; integrity-check endpoint |
| V3 | `sync_run_id` provenance on conversations + daily metrics; surgical rollback by run ID |

### Files That Would Change

| File | Change |
|------|--------|
| `src/tasks/adoption_sync_tasks.py` | `daily_adoption_sync` accepts `customer_id` param; single-provider sync instead of chord |
| `src/api/routes/adoption.py` | Add tenant-scoped `/sync/trigger` endpoint |
| `frontend/src/pages/adoption/` | Add sync trigger to adoption settings or dashboard |
| `src/api/routes/platform_admin.py` | (Optional) Keep global trigger but iterate sequentially |

---

## Decision Points

1. **Option A vs Option B for where the logic lives?**
   - Recommendation: Option A (pre-sync hook) for V1. Transparent, works for both manual and scheduled. Can add Option B UI in V2.

2. **Should cleanup require user confirmation?**
   - Recommendation: No for V1. Auto-cleanup is safer than leaving bad data. Log everything for audit trail. Can add confirmation dialog in V2 if needed.

3. **Should we also make the 4-step sync atomic?**
   - This is a bigger change (wrapping all steps in a single transaction). Deferred to V3. The auto-recovery mechanism is a pragmatic band-aid that handles the failure case without rearchitecting the sync pipeline.

4. **What about the chord pattern in Celery?**
   - The chord issue (callback not firing) is separately addressed by the stale detection fix and errback handler already committed. The integrity check handles the data-level consequence of that failure.

5. **Should the sync be tenant-scoped or platform-scoped?**
   - **Decision: Tenant-scoped.** The platform-level chord approach is fundamentally broken -- one tenant's OOM kills the other's sync. Move trigger to tenant admin settings. Each tenant triggers/schedules their own sync.

6. **What to do about the `platform` tenant's provider (id=14)?**
   - It shares the same workspace ID as `eliza`. Its sync completed successfully with 2,670 conversations + 30 daily metrics.
   - Options: (a) Remove it as a duplicate, (b) Keep it but deduplicate API calls, (c) Leave as-is with tenant-scoped sync preventing parallel OOM.

7. **Should we keep the global Job Scheduler entry?**
   - With tenant-scoped sync, the global `adoption-daily-sync` job may not be needed. Could be replaced by per-tenant scheduled tasks, or kept as a sequential fan-out (sync tenant A, then tenant B).

---

## Locked Refinements (Feb 6)

These decisions are confirmed and should drive implementation:

1. **Dashboard Sync Control (Tenant UI):**
   - Add a top-right control on the adoption dashboard showing:
     - `Last synced: <date/time>`
   - This control links to Tenant Admin > Adoption Settings page.
   - Tenant users can trigger a sync or adjust config from there.

2. **Fresh Install Scope:**
   - Historical cleanup of legacy duplicate/platform data is out of scope for this feature branch.
   - We are targeting a fresh DB install flow, so migration/backfill cleanup tasks are not required for MVP.

3. **Scheduler Ownership and Navigation:**
   - Remove the Platform Admin Job Scheduler menu item.
   - Move scheduler access to Tenant Admin menu.
   - Scope scheduler execution to current tenant only (`customer_id` required).
   - Schedule **configuration** (on/off, cron) lives on Adoption Settings page only.
   - Job Scheduler page is ops/monitoring: shows job rows, status, history, "Run Now" — but "Configure" links to Adoption Settings.

4. **Consolidated Adoption Settings Page:**
   - Merge "Adoption Access" into "Adoption Settings" as one page.
   - Page layout: Setup wizard (start date, provider, schedule) → Sync status → Access sharing (scroll down).
   - Single tenant-admin nav entry: "Adoption Settings" at `/admin/adoption-settings`.
   - Remove standalone "Adoption Access" nav entry (content is a section within Adoption Settings).
   - Dashboard empty state links to Adoption Settings for first-time setup.

5. **Configurable Sync Start Date:**
   - Replace hardcoded `timedelta(days=30)` fallback with user-chosen start date.
   - Date picker on Adoption Settings page, defaulting to 30 days ago.
   - Stored per tenant. Read-only after initial sync (or editable with re-sync warning).
   - Backend: new endpoint `GET/PUT /api/v1/admin/adoption-settings` + storage (provider config field or new table).

6. **Cross-Tenant Dependency Check (Completed Discovery):**
   - Current platform scheduler usage appears isolated to:
     - Frontend route/menu: `frontend/src/App.tsx`, `frontend/src/components/navigation/sectionConfigs.ts`, `frontend/src/components/navigation/platformAdminNav.ts`
     - Frontend page/hook: `frontend/src/pages/platform-admin/JobSchedulerPage.tsx`, `frontend/src/hooks/useJobSchedulerStream.ts`
     - Backend route: `src/api/routes/platform_admin.py` (`/jobs/*`, `/jobs/stream`)
   - No additional product flows were found that require cross-tenant scheduler behavior.
   - Implementation should still include a final route/permission audit before removing platform endpoints.

7. **OOM Fix Priority:**
   - GPT re-fetch optimization is mandatory for V1 (cache or pass-through metadata).
   - Do not ship tenant scheduler move without this fix.

8. **Tenant Admin Nav Structure:**
   ```
   Admin Settings (Tenant Admin)
     ├── Data Connections
     ├── Users & Roles
     ├── AI Providers
     ├── Adoption Settings    ← NEW (setup wizard + schedule + access sharing)
     ├── Job Scheduler        ← moved from platform (ops view, no schedule editing)
     ├── Theme
     └── Storage
   ```

---

## NEW: Adoption Settings Page (Consolidated)

**Combines:** Setup wizard + sync configuration + access sharing — all in one tenant-admin page.

### Page Layout (Top to Bottom)

**Section 1: Sync Setup (Wizard / First-Time Config)**
- **Sync start date picker** — "How far back should we pull data?" Date picker defaulting to 30 days ago, user can adjust.
  - On first setup: editable, required before first sync.
  - After initial sync: read-only (or editable with warning "Changing this will re-sync all data from the new date").
- **Provider info** — Which AI provider is the adoption source (read-only summary, links to AI Providers page to change).
- **Sync schedule toggle** — On/Off + cron expression. This is the single source of truth for schedule config.
  - The Job Scheduler page shows this job as a row but does NOT have inline schedule editing — its "Configure" action links here.
- **"Run Now" button** — Also available on Job Scheduler, but convenient here during setup.

**Section 2: Sync Status**
- Last synced date/time
- Current sync status (idle / running / error)
- Quick health summary (consistent / needs recovery)

**Section 3: Access Sharing (Scroll Down)**
- Inbound grants: who can view our data (toggle on/off)
- Outbound grants: whose data we can view (toggle on/off)
- Re-uses existing `AdoptionAccessPage.tsx` component content, embedded as a section rather than a separate page.

### What Already Exists (Adoption Access)

1. **Tenant Admin page exists:** `frontend/src/pages/admin/AdoptionAccessPage.tsx`
   - Shows inbound/outbound grants and allows toggle on/off
   - Uses tenant admin endpoints under `/api/v1/admin/adoption-access`

2. **Tenant Admin backend endpoints exist:**
   - `src/api/routes/tenant_admin.py`
   - `GET /api/v1/admin/adoption-access`
   - `PUT /api/v1/admin/adoption-access/{grant_id}`

3. **Route is already wired:** `frontend/src/App.tsx` includes `/admin/adoption-access`

4. **Platform Admin grant management also exists:**
   - `frontend/src/pages/platform-admin/AdoptionAccessPage.tsx`
   - Full create/delete/toggle grant management via `/api/v1/platform-admin/adoption/grants`

### What's New (Sync Setup)

1. **New backend: sync config storage**
   - Store `initial_sync_start_date` per tenant (on provider config or new `adoption_sync_config` table)
   - Sync service reads this instead of hardcoding `timedelta(days=30)`

2. **New backend endpoint:**
   - `GET/PUT /api/v1/admin/adoption-settings` — read/update sync config (start date, schedule)

3. **New frontend page:**
   - `frontend/src/pages/admin/AdoptionSettingsPage.tsx` — unified setup + access page
   - Replaces standalone `AdoptionAccessPage.tsx` (access sharing content merged in as a section)

### Schedule Duplication Resolved

| Surface | What It Shows | Can Edit Schedule? |
|---------|--------------|-------------------|
| **Adoption Settings** (tenant admin) | Full sync config: start date, provider, schedule, access sharing | **Yes** — single source of truth for schedule config |
| **Job Scheduler** (tenant admin) | All tenant jobs as rows: status, history, "Run Now" | **No** — "Configure" link goes to Adoption Settings |
| **Dashboard header** | "Last synced: date/time" | **No** — links to Adoption Settings |

### Dashboard Empty State

When no sync has ever run:
- Dashboard shows an empty state card: "Set up Adoption Sync"
- CTA button links to Adoption Settings page
- No data panels rendered until first sync completes

### Request Workflow Note

- There is no explicit "request access grant" workflow implemented yet.
- Current behavior:
  - Tenant users can manage shares if they have `adoption:manage_sharing` (via adoption dashboard sharing manager).
  - Platform admins can create cross-tenant grants in platform admin page.
- If product wants formal request/approval workflow, treat as V2+ (new table/state machine + notifications + approval UI).

---

## Files That Would Change

### V1: Integrity & Tenant-Scoped Sync

| File | Change |
|------|--------|
| `src/services/adoption/sync_service.py` | Add `check_consistency()` and `cleanup_partial_sync()` methods; read sync start date from config instead of hardcoding 30 days |
| `src/services/adoption/openai_compliance_client.py` | Cache `get_all_gpts()` on client instance to eliminate N×3 redundant API calls |
| `src/tasks/adoption_sync_tasks.py` | Accept `customer_id` param; single-provider sync (no chord); log auto-recovery in task result |
| `src/api/routes/platform_admin.py` | Remove/deprecate platform-level job scheduler endpoints |
| `src/api/routes/tenant_admin.py` | Add `GET/PUT /admin/adoption-settings` endpoint for sync config (start date, schedule) |
| `src/models/adoption.py` (or new) | Add model/table for per-tenant sync config (initial start date, schedule settings) |
| `alembic/versions/xxx_add_adoption_sync_config.py` | Migration for sync config storage |
| `frontend/src/pages/admin/AdoptionSettingsPage.tsx` | New consolidated page: setup wizard + sync status + access sharing sections |
| `frontend/src/pages/admin/AdoptionAccessPage.tsx` | Refactor: extract grant list components for re-use in AdoptionSettingsPage |
| `frontend/src/components/navigation/sectionConfigs.ts` | Add "Adoption Settings" + "Job Scheduler" to tenant-admin nav; remove from platform nav |
| `frontend/src/components/navigation/platformAdminNav.ts` | Remove Job Scheduler menu item |
| `frontend/src/pages/adoption/AdoptionDashboardPage.tsx` | Add empty state CTA linking to Adoption Settings; add "Last synced" control linking to Adoption Settings |

### V2: Visibility & Ops

| File | Change |
|------|--------|
| `src/api/routes/adoption.py` | Add `/sync/integrity-check` endpoint for on-demand health checks |
| `src/api/routes/tenant_admin.py` | Add tenant-scoped job scheduler endpoints (trigger, list, stream) |
| `frontend/src/pages/admin/JobSchedulerPage.tsx` | New tenant-admin scheduler page (ops view: job rows, status, history, "Run Now"; "Configure" links to Adoption Settings) |
| `frontend/src/hooks/useJobSchedulerStream.ts` | Adapt SSE hook for tenant-scoped scheduler endpoint |
| `src/tasks/adoption_sync_tasks.py` | Emit SSE events for auto-recovery; enrich execution history with cleanup details |

### V3: Sync Run Provenance

| File | Change |
|------|--------|
| `alembic/versions/xxx_add_sync_run_id.py` | Migration: add `sync_run_id` UUID column to `adoption_conversations` and `adoption_daily_metrics` |
| `src/models/adoption.py` | Add `sync_run_id` column to ORM models |
| `src/services/adoption/sync_service.py` | Generate UUID per sync run; stamp all created/updated rows; cleanup by `sync_run_id` |
| `src/tasks/adoption_sync_tasks.py` | Record `sync_run_id` in execution history |

---

## Open Questions (Remaining)

1. Should we also check `adoption_user_gpt_interactions` in the consistency check, or is it safe to treat it as derived data that gets rebuilt each sync?
2. What's the right threshold for "inconsistent"? Any difference, or only if the gap is > 1 day?
3. Should the cleanup also purge GPT records that were added in a partial sync, or are GPTs safe to keep (they're global metadata, not date-scoped)?
4. For the scheduled (Celery Beat) runs, should auto-recovery be on by default, or should it require a flag?

## Decided Questions

5. **Remove `platform` provider (id=14)?** → Yes, disable it. Duplicate of eliza's provider pointing at same workspace.
6. **Tenant scheduler: dedicated page or adoption sub-page?** → Dedicated tenant-admin scheduler page for ops/monitoring. Schedule config lives on Adoption Settings page only.
7. **V2 scope?** → Approved as-is (visibility, ops, tenant scheduler).
8. **V3 scope?** → Approved scoped-down: `sync_run_id` provenance only. No audit log table, no history browser UI.
9. **Platform Job Scheduler menu?** → Remove it. No cross-tenant dependencies found. Move to tenant-admin menu.
10. **Adoption Access as separate page?** → No. Merged into Adoption Settings page as a scroll-down section. Single nav entry.
11. **Configurable sync start date?** → Yes. Date picker on Adoption Settings page. Replaces hardcoded 30-day fallback. Stored per tenant.
12. **Schedule config duplication?** → Resolved. Adoption Settings is the single source of truth for schedule on/off and cron. Job Scheduler shows job status/history/run-now but links to Adoption Settings for config changes.

---

## NEW: GPT Re-Fetch Optimization (Fix OOM Root Cause)

**Discovered Feb 6, 2026 during live sync debugging.**

### The Problem

The daily metrics sync (Step 4) calls `get_daily_summary()` once per day in a loop. Inside that method, `get_all_gpts()` is called every single time, re-fetching all 45 GPTs (3 API pages) for every day in the date range.

**Code path:**
```
sync_provider()
  _sync_openai()
    Step 4: for each day in range:
      client.get_daily_summary(current_date)
        client.count_conversations_for_day()   <-- lists conversations (logs "Listed 489 conversations")
        client.get_all_gpts()                  <-- RE-FETCHES ALL GPTs (logs "Listed 20 GPTs" x3)
```

**Source:** `openai_compliance_client.py` line 562 inside `get_daily_summary()` calls `get_all_gpts()`.

**Impact for a 26-day backfill:**
- 26 days x 3 GPT API pages = 78 unnecessary API calls for metadata that does not change
- Each call loads response data into memory
- Combined with conversation pagination, this balloons memory and leads to OOM kill

### The Fix (Should Be Part of V1)

GPTs are already fully synced in Step 1. The metadata is static and does not change per day.

**Option A (recommended):** Cache `get_all_gpts()` on the client instance so repeated calls return the cached result. Simple, no API changes needed.

**Option B:** Pass the GPT metadata dict from Step 1 into `get_daily_summary()` as a parameter, skipping the internal fetch.

Either approach eliminates N x 3 API calls where N = number of days being synced.

**Files:**
- `src/services/adoption/openai_compliance_client.py` -- `get_daily_summary()` line 562
- `src/services/adoption/sync_service.py` -- Pass GPT metadata from Step 1 into Step 4
