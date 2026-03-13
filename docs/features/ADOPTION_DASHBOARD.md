# ChatGPT Enterprise Adoption Dashboard

> Full specification for tracking ChatGPT Enterprise and LLM adoption metrics across tenants.

## 🚀 Implementation Status

**Status: ✅ FULLY FUNCTIONAL**

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | Database & Models | ✅ Complete |
| Phase 2 | Permissions & Roles | ✅ Complete |
| Phase 3 | API Routes & Services | ✅ Complete |
| Phase 4 | Sync Infrastructure | ✅ Complete |
| Phase 5 | Frontend Dashboard | ✅ Complete |
| Phase 6 | Platform Admin UI | ✅ Complete |
| Phase 7 | Move Adoption Config to Tenant Level | ✅ Complete |
| Phase 8 | Portfolio Company Setup on Tenant Creation | ✅ Complete |
| Phase 9 | Tenant Adoption Access View (Admin Section) | ✅ Complete |
| Phase 10 | Platform Job Scheduler Settings | ✅ Complete |

### Remaining Configuration Tasks

- [ ] **OpenAI Compliance API Key**: Request Compliance API access from OpenAI (email `support@openai.com`)
- [ ] **Workspace ID**: Add `CHATGPT_WORKSPACE_ID` to environment configuration
- [ ] **Feature Allocation**: Enable `adoption_dashboard` feature for tenants via Platform Admin

---

## 🔧 TODO: Required Fixes & Enhancements

### ✅ COMPLETE: Move Adoption Key Configuration to Tenant Level

**Solution Implemented:** Adoption tracking is now configured at the tenant level via Admin Settings → AI Provider Configuration.

**What was done:**
- Added adoption toggle and workspace ID input to `AdminSettingsPage.tsx` (tenant-level)
- Added expandable rows in provider table to show adoption settings
- Created `PUT /v1/providers/configurations/{id}/adoption` endpoint (tenant-level)
- Updated `TenantProviderResponse` schema to include `is_adoption_source` and `chatgpt_workspace_id`
- Removed platform-level adoption section entirely (was showing info message, now removed)
- Platform admin endpoint retained for support/override purposes only
- Added confirmation modal when switching adoption keys (warns user that enabling will disable the currently enabled key)
- **Added "Test Compliance API Access" button** during key creation to verify API key has the `compliance_export` scope
  - Shows success message if access is confirmed
  - Shows detailed instructions if access is denied (how to email OpenAI support)
- **Added persistent compliance status tracking** - status is stored in database and displayed in UI
  - Green "Adoption" badge = Compliance API verified
  - Amber "Adoption (Not Tested)" badge = Needs testing
  - Red "Adoption (Error)" badge = Compliance API test failed

**Files Modified:**
```
frontend/src/pages/admin/AdminSettingsPage.tsx  (Added adoption section with confirmation modal + test button)
src/api/routes/providers.py  (Added tenant-level adoption endpoint + POST /test-compliance-api)
src/models/provider_config.py  (Updated TenantProviderResponse)
frontend/src/pages/platform-admin/PlatformSettingsPage.tsx  (Removed adoption section entirely)
```

---

### Phase 8: Portfolio Company Setup on Tenant Creation

**Feature:** When creating a new tenant, allow the platform admin to configure adoption sharing grants **in both directions** as part of the tenant creation wizard.

#### Use Cases

| Scenario | Direction | Example |
|----------|-----------|---------|
| Creating a **holdco** (e.g., Blackstone) | Inbound grants | "Which existing portcos should Blackstone be able to view?" |
| Creating a **portco** (e.g., Acme) | Outbound grants | "Which existing holdcos should be granted view access to Acme's data?" |

#### TODO 8.1: Update Tenant Creation Form
- [ ] Add "Adoption Sharing" section to tenant creation modal/wizard
- [ ] **Inbound Access** multi-select: "This tenant can VIEW adoption data from:"
  - Shows list of existing tenants
  - Selected tenants will grant read access TO the new tenant
- [ ] **Outbound Access** multi-select: "These tenants can VIEW this tenant's adoption data:"
  - Shows list of existing tenants  
  - Selected tenants will be granted read access FROM the new tenant

#### TODO 8.2: Auto-Create Adoption Grants on Tenant Creation
- [ ] When tenant is created with sharing configured:
  - **Inbound**: Create `AdoptionDataShare` records where `source_customer_id` = selected tenant, `target_customer_id` = new tenant
  - **Outbound**: Create `AdoptionDataShare` records where `source_customer_id` = new tenant, `target_customer_id` = selected tenant
  - Set `share_level = "read"`, `is_enabled = true` for all
- [ ] Update `POST /api/v1/platform-admin/tenants` to accept:
  - `adoption_inbound_from: List[str]` (tenant IDs this tenant can view)
  - `adoption_outbound_to: List[str]` (tenant IDs that can view this tenant)

#### TODO 8.3: Update Tenant Edit to Manage Sharing
- [ ] Allow editing adoption sharing relationships after creation
- [ ] Show current inbound/outbound grants and allow adding/removing

**Files to Modify:**
```
frontend/src/pages/platform-admin/PlatformSettingsPage.tsx (tenant creation modal)
src/api/routes/platform_admin.py
src/api/schemas/tenant_admin.py
src/services/tenant_admin_service.py
```

---

### Phase 9: Tenant Adoption Access View (Admin Section)

**Feature:** Allow tenant admins to view and manage adoption sharing grants that affect their tenant. This is a **read/toggle-only** view (no creating new shares) that shows both inbound and outbound grants.

#### What Tenants Can See & Do

| Grant Type | Description | Actions Available |
|------------|-------------|-------------------|
| **Inbound** | Tenants whose data WE can view | Enable/disable receiving their data |
| **Outbound** | Tenants who can view OUR data | Enable/disable sharing our data with them |

**Note:** Tenants cannot CREATE new shares - only platform admins can do that. Tenants can only toggle existing grants on/off.

#### TODO 9.1: Create Tenant Adoption Access Page
- [ ] New page: `frontend/src/pages/admin/AdoptionAccessPage.tsx`
- [ ] Add to Administration menu in navigation (new menu item)
- [ ] Route: `/admin/adoption-access`

#### TODO 9.2: Inbound Grants Section
- [ ] List all tenants that have shared their adoption data WITH this tenant
- [ ] For each: Show tenant name, date granted, current status (enabled/disabled)
- [ ] Toggle to enable/disable receiving that tenant's data in our dashboard
- [ ] When disabled, that tenant's data won't appear in our adoption dashboard

#### TODO 9.3: Outbound Grants Section  
- [ ] List all tenants that can view OUR adoption data
- [ ] For each: Show tenant name, date granted, current status (enabled/disabled)
- [ ] Toggle to enable/disable sharing our data with that tenant
- [ ] When disabled, our data won't appear in their adoption dashboard

#### TODO 9.4: Backend API Endpoints
- [ ] `GET /api/v1/admin/adoption-access` - Get inbound and outbound grants for current tenant
- [ ] `PUT /api/v1/admin/adoption-access/{grant_id}` - Toggle grant enabled/disabled

**Files to Create/Modify:**
```
frontend/src/pages/admin/AdoptionAccessPage.tsx (new)
frontend/src/components/layout/Navigation.tsx (add menu item)
frontend/src/App.tsx (add route)
src/api/routes/tenant_admin.py (or new adoption_admin.py)
src/api/schemas/adoption.py (add schemas if needed)
```

---

### ✅ COMPLETE: Phase 10 - Platform Job Scheduler Settings

**Completed:** January 5, 2026

**Feature:** A platform-level admin UI to view and manage Celery scheduled tasks. This is a **generic platform feature** that covers all background jobs, not just adoption sync.

#### Supported Jobs

| Job Name | Default Schedule | Description |
|----------|------------------|-------------|
| `adoption-daily-sync` | Every 6 hours | Sync adoption metrics from OpenAI Compliance API |

#### What Was Implemented

**10.1: Job Scheduler Page** ✅
- New page: `frontend/src/pages/platform-admin/settings/JobSchedulerPage.tsx`
- Route: `/platform-admin/settings/jobs`
- Integrated into Platform Settings sub-navigation

**10.2: Job List View** ✅
- Display all scheduled jobs with status
- Shows: Job name, schedule, last run time, status (idle/running/success/failed), duration
- Auto-refreshes every 10 seconds to show real-time status

**10.3: Job Controls** ✅
- **Trigger Manual Run**: Button to immediately execute a job
- **Enable/Disable Toggle**: Pause/resume scheduled execution
- **View Execution History**: Expandable row shows recent executions with timestamps and results
- **Error Display**: Shows last error message for failed jobs

**10.4: Backend API Endpoints** ✅
- `GET /api/v1/platform-admin/jobs` - List all scheduled jobs with status
- `GET /api/v1/platform-admin/jobs/{job_name}` - Get single job details
- `PUT /api/v1/platform-admin/jobs/{job_name}` - Update schedule/enabled status
- `POST /api/v1/platform-admin/jobs/{job_name}/trigger` - Manually trigger a job
- `GET /api/v1/platform-admin/jobs/{job_name}/executions` - Get recent execution logs

**10.5: Database Schema** ✅
- `scheduled_job_configs` table stores:
  - `job_name`, `display_name`, `description`, `task_name`
  - `schedule_type` (interval/cron), `schedule_value`
  - `is_enabled`, `last_run_at`, `last_run_status`, `last_run_duration_seconds`
  - `last_error`, `last_task_id`, `next_run_at`, `updated_by_user_id`
- `scheduled_job_executions` table stores execution history:
  - `job_name`, `task_id`, `started_at`, `completed_at`, `duration_seconds`
  - `status`, `error_message`, `triggered_by`, `result_summary`

**Files Created/Modified:**
```
frontend/src/pages/platform-admin/settings/JobSchedulerPage.tsx (new)
frontend/src/components/navigation/platformAdminNav.ts (enabled Job Scheduler menu)
frontend/src/App.tsx (added route)
src/api/routes/platform_admin.py (added job endpoints)
src/models/scheduled_job.py (new - ScheduledJobConfig, ScheduledJobExecution models)
alembic/versions/kk1ll2mm3nn4_add_scheduled_job_tables.py (new migration)
src/tasks/adoption_sync_tasks.py (integrated status tracking)
```

**Technical Notes:**
- Schedule changes in database are configuration-only; Celery Beat reads from `celery_app.py`
- For dynamic schedule updates, would need `celery-redbeat` or restart workers
- Execution history is tracked per-job for debugging and monitoring

---

### ✅ COMPLETE: Bug Fix - Adoption Metrics Parsing Logic

**Problem:** The adoption dashboard was displaying incorrect counts. Messages were showing cumulative counts (201K+ instead of ~1.5K) because ALL messages in a conversation were being counted when that conversation was created, not just messages created on that specific day.

**Root Cause Identified:**
1. Messages were counted cumulatively - when syncing Dec 3, ALL messages ever added to conversations started on Dec 3 were counted
2. Users were counted by conversation creation, not by message activity on that day
3. The Compliance API's `since_timestamp` parameter returns conversations UPDATED since that time, requiring client-side filtering

**Solution Implemented:**
- Modified `openai_compliance_client.py` to filter by `message.created_at` timestamp
- Now only counts messages where `created_at` falls within the target day's 24-hour window
- Users are counted based on who **sent messages** on that day, not who created conversations
- Conversations are counted based on **activity** on that day

**Files Modified:**
```
src/services/adoption/openai_compliance_client.py  - Fixed count_conversations_for_day()
src/services/adoption/sync_service.py  - Memory optimization, skip bulk conversation storage
docker/docker-compose.yml  - Increased celery-worker memory (3G → 6G), reduced concurrency (4 → 2)
```

**Results (Before → After):**
| Metric | Before Fix ❌ | After Fix ✅ |
|--------|--------------|--------------|
| Total Conversations | 6,162 | 419 |
| Total Messages | 201,886 | 1,530 |
| Daily Message Counts | 2,000-3,000+ | 10-100 |

**Sync Performance:**
- Initial 30-day backfill: ~6 minutes
- Daily incremental sync: ~10-20 seconds (only yesterday's data)
- Memory required: 6GB for celery-worker

---

### Enhancement: Top GPTs Time Filtering

**Problem:** The Top GPTs list does not filter based on the selected time range (7d/30d/90d). The database schema supports this (`top_gpts` JSON is stored per `metric_date`), but the backend currently returns the latest snapshot.

#### TODO 3.1: Backend Changes
- [ ] Update `AdoptionService.get_company_overview()` to accept `start_date`/`end_date` params
- [ ] Aggregate `top_gpts` usage counts across the filtered date range
- [ ] Sum `uses`, `users`, `conversations` for each GPT across all days in range

#### TODO 3.2: Frontend Changes
- [ ] Update `useAdoptionOverview` hook to pass date range params
- [ ] Re-fetch overview when date range changes

#### TODO 3.3: Update Dummy Data
- [ ] Create varied daily GPT usage data for testing
- [ ] Each day should have different usage counts

**Files to Modify:**
```
src/services/adoption_service.py
src/api/routes/adoption.py
frontend/src/hooks/useAdoption.ts
frontend/src/pages/adoption/AdoptionDashboardPage.tsx
```

---

### Assessment: What Was Built vs. What Needs Fixing

| Component | Status | Notes |
|-----------|--------|-------|
| Database Schema | ✅ Correct | `is_adoption_source`, `chatgpt_workspace_id` on `CustomerAIProvider` |
| Permissions & Roles | ✅ Correct | `adoption_analyst`, `adoption_admin` roles created |
| Adoption Dashboard UI | ✅ Correct | Works for viewing metrics |
| Top GPTs List | ✅ Correct | Shows ranked GPTs with company badges |
| View More/Less | ✅ Correct | Expands to 50 GPTs |
| Cross-Tenant Sharing (Platform Admin) | ✅ Correct | Read-only grants via platform admin |
| Sync Infrastructure | ✅ Correct | Celery tasks, OpenAI client, memory optimized |
| Adoption Key Toggle Location | ✅ Fixed | Now in Tenant Admin Settings (expandable row) |
| **Metrics Parsing Logic** | ✅ Fixed | Daily counts now filter by message.created_at |
| **GPT Adoption Chart** | ✅ Added | Pie chart showing GPT vs Base ChatGPT usage |
| **Token Metrics** | ❌ Removed | Not available from Compliance API |
| **Portfolio Company Setup** | ❌ Missing | Phase 8: Bidirectional sharing on tenant creation |
| **Tenant Adoption Access View** | ❌ Missing | Phase 9: Admin section for tenant to view/toggle grants |
| **Job Scheduler Settings** | ❌ Missing | Phase 10: Platform-level Celery job management UI |
| **Top GPTs Time Filter** | ⚠️ Partial | Schema supports it, logic not implemented |

---

### Priority Order

1. ~~**P0 (Critical):** Move adoption key configuration to tenant level~~ ✅ DONE
2. ~~**P0 (Critical):** Bug Fix - Adoption metrics parsing logic~~ ✅ DONE (Jan 5, 2026)
3. **P1 (High):** Phase 8 - Portfolio company setup on tenant creation (bidirectional)
4. **P1 (High):** Phase 9 - Tenant adoption access view (Admin section)
5. **P2 (Medium):** Phase 10 - Platform job scheduler settings (generic feature)
6. **P3 (Nice to have):** Top GPTs time filtering

---

## Implementation Summary

### Phase 1: Database & Models ✅

**Completed:** December 29, 2024

**Files Created/Modified:**
- `alembic/versions/ee5ff6gg7hh8_add_adoption_feature_and_permissions.py` - Main migration
- `alembic/versions/ff6gg7hh8ii9_add_chatgpt_workspace_id.py` - Workspace ID migration
- `src/models/adoption.py` - SQLAlchemy models
- `src/models/customer.py` - Added `is_adoption_source` and `chatgpt_workspace_id` to `CustomerAIProvider`

**Database Changes:**
- Added `is_adoption_source` boolean to `customer_ai_providers`
- Added `chatgpt_workspace_id` to `customer_ai_providers`
- Created `adoption_data_shares` table for tenant-to-tenant sharing
- Created `adoption_daily_metrics` table for aggregated metrics
- Created `platform_adoption_grants` table for platform admin grants

---

### Phase 2: Permissions & Roles ✅

**Completed:** December 29, 2024

**Files Created/Modified:**
- `src/middleware/authorization.py` - Added adoption access methods
- `scripts/init_rbac_data.py` - Added adoption permissions and roles

**Permissions Added:**
| Permission | Description |
|------------|-------------|
| `adoption:view_dashboard` | Access adoption dashboard UI |
| `adoption:read:company:*` | View ALL companies' metrics (wildcard) |
| `adoption:admin:company:*` | Configure adoption for ALL companies |
| `adoption:manage_sharing` | Share own tenant's data with others |
| `adoption:manage_sync` | Trigger manual adoption data syncs |

**Roles Added:**
| Role | Description |
|------|-------------|
| `adoption_analyst` | View adoption metrics and dashboards |
| `adoption_admin` | Manage adoption data sources, sharing, and syncs |

**Authorization Methods:**
- `check_adoption_access()` - Verify user can access specific company's adoption data
- `get_accessible_adoption_companies()` - Get all companies user can view
- `require_adoption_access()` - FastAPI dependency for route protection

---

### Phase 3: API Routes & Services ✅

**Completed:** December 29, 2024

**Files Created:**
- `src/api/routes/adoption.py` - All adoption API endpoints
- `src/api/schemas/adoption.py` - Pydantic request/response models
- `src/services/adoption_service.py` - Business logic layer

**API Endpoints Implemented:**
```
GET  /api/v1/adoption/metrics       - Get metrics for accessible companies
GET  /api/v1/adoption/overview      - High-level adoption overview
GET  /api/v1/adoption/dashboard     - Dashboard widget data

GET  /api/v1/adoption/shares        - List adoption shares
POST /api/v1/adoption/shares        - Create new share
PATCH /api/v1/adoption/shares/{id}  - Update share
DELETE /api/v1/adoption/shares/{id} - Delete share

GET  /api/v1/adoption/providers     - List adoption providers
POST /api/v1/adoption/providers/{id}/enable  - Enable for adoption
POST /api/v1/adoption/providers/{id}/disable - Disable for adoption

POST /api/v1/adoption/sync          - Trigger manual sync (Celery task)
```

---

### Phase 4: Sync Infrastructure ✅

**Completed:** December 29, 2024

**Files Created:**
- `src/tasks/adoption_sync_tasks.py` - Celery tasks for data syncing
- `src/services/adoption/sync_service.py` - Sync orchestration service
- `src/services/adoption/openai_compliance_client.py` - OpenAI Compliance API client
- `src/services/adoption/openapi.json` - OpenAI Compliance API spec (reference)

**Celery Tasks:**
| Task | Description |
|------|-------------|
| `sync_adoption_provider` | Sync single provider's adoption data |
| `sync_all_adoption_providers` | Sync all enabled providers |
| `daily_adoption_sync` | Scheduled daily sync (every 6 hours) |

**Incremental Sync Behavior:**
The sync service implements smart incremental syncing:
- `start_date = last_sync_date + 1 day` (only new days)
- `end_date = yesterday` (complete days only, not today)
- Initial backfill: 30 days (~6 minutes)
- Daily incremental: 1 day (~10-20 seconds)
- No duplicate data: Each day synced only once unless `force=True`

**Memory Requirements:**
- celery-worker: 6GB memory limit (up from 3GB)
- Reduced concurrency: 2 workers (down from 4)
- Reason: Each day's sync fetches 300-400 conversations with full message history

**OpenAI Compliance API Client:**
- Connects to `https://api.chatgpt.com/v1/compliance/`
- Fetches users and conversations via workspace endpoints
- Derives daily metrics from raw data
- Supports pagination for large datasets

**Note:** The Compliance API requires manual approval from OpenAI. Email `support@openai.com` with:
- Last 4 digits of API key
- Key Name
- Created By Name
- Requested scope: `read`

---

### Phase 5: Frontend Dashboard ✅

**Completed:** December 30, 2024

**Files Created:**
- `frontend/src/pages/adoption/AdoptionDashboardPage.tsx` - Main dashboard page
- `frontend/src/components/adoption/MetricCard.tsx` - Summary metric cards
- `frontend/src/components/adoption/UsageChart.tsx` - Area/line charts (Recharts)
- `frontend/src/components/adoption/CompanySelector.tsx` - Company filter dropdown
- `frontend/src/components/adoption/SharingManager.tsx` - Share management UI
- `frontend/src/components/adoption/TopGPTsList.tsx` - Ranked GPT list with "View More"
- `frontend/src/components/adoption/GPTAdoptionChart.tsx` - Pie chart for GPT adoption rate
- `frontend/src/hooks/useAdoption.ts` - React Query hooks for all endpoints

**Dashboard Features:**
- **Overview Tab**: Summary metrics (avg daily users, conversations, messages)
- **Trends Tab**: Time-series charts for users, conversations, messages over time
- **Details Tab**: Breakdown by company with status indicators
- **GPT Adoption Chart**: Pie chart showing custom GPT vs base ChatGPT usage percentage
- **Top GPTs List**: Ranked GPTs with usage counts, users, and clickable links
- **Company Selector**: Filter by accessible companies (or "All Companies")
- **Date Range**: 7/30/90 day views
- **Auto-refresh**: Data refreshed via background Celery tasks (no manual refresh needed)

**Navigation:**
- Added "Adoption Dashboard" under new "ANALYTICS" section in sidebar
- Protected by `adoption:view_dashboard` permission and `adoption_dashboard` feature flag

---

### Phase 6: Platform Admin UI ✅

**Completed:** December 30, 2024

**Files Created:**
- `frontend/src/pages/platform-admin/AdoptionAccessPage.tsx` - Adoption grants management

**Backend Additions:**
- `src/models/platform_admin.py` - `PlatformAdoptionGrant` model
- `src/api/routes/platform_admin.py` - Added adoption grant endpoints:
  ```
  GET  /api/v1/platform-admin/adoption/grants
  POST /api/v1/platform-admin/adoption/grants
  PATCH /api/v1/platform-admin/adoption/grants/{id}
  DELETE /api/v1/platform-admin/adoption/grants/{id}
  ```
- `src/api/schemas/tenant_admin.py` - Grant request/response schemas
- `src/services/tenant_admin_service.py` - Grant CRUD operations

**Platform Admin Features:**
- View all cross-tenant adoption grants
- Create new grants (source tenant → target tenant)
- Enable/disable grants without deleting (toggle with "Yes/No" label)
- Delete grants

> **Note:** All grants are **Read Only**. The ability to set admin/refresh level was removed to simplify the permission model.

**Navigation:**
- Added "Adoption Access" under Platform Admin section in sidebar
- Requires `platform_admin` role

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture Decisions](#architecture-decisions)
3. [Permission Model](#permission-model)
4. [Access Patterns](#access-patterns)
5. [API Keys & Data Sources](#api-keys--data-sources)
6. [Database Schema](#database-schema)
7. [Data Flow](#data-flow)
8. [Roles & Feature Flags](#roles--feature-flags)
9. [API Endpoints](#api-endpoints)
10. [Implementation Checklist](#implementation-checklist)

---

## Overview

### Business Context

- **Problem**: OpenAI's native admin console lacks multi-tenant visibility for PE firms and holding companies
- **Solution**: Build adoption tracking that allows parent companies to view metrics across portfolio companies
- **Target Users**: 
  - PE/Holding company leadership (aggregate view across child companies)
  - Portfolio company admins (single-company view)
  - Change management and enablement teams

### What We Track

| Category | Metrics |
|----------|---------|
| **Platform Usage** | Eliza Platform internal metrics (from existing CustomerAIProvider data) |
| **ChatGPT Enterprise** | Messages, conversations, GPT usage, user activity (via OpenAI Compliance API) |
| **Future** | Google Gemini, Anthropic Claude, Microsoft Copilot adoption |

**Important**: We store aggregated metrics only. **NO message content is stored.**

---

## Architecture Decisions

### Decision 1: No Customer Hierarchy

**❌ Rejected**: Adding `parent_customer_id` to Customer model

**✅ Chosen**: Permission-based access with explicit grants

**Rationale**: Hierarchy in Customer model creates cascading permission complexity. Instead, we use explicit permission grants (`adoption:read:company:X`) which is the same pattern as the existing HR module.

---

### Decision 2: Two Paths to Access

| Path | Who Initiates | Use Case |
|------|--------------|----------|
| **Platform Admin Grant** | Eliza platform admin | PE firm contract - Blackstone can see portfolio companies |
| **Tenant Self-Service Share** | Portco admin (e.g., Acme) | Acme opts-in to share with Blackstone |

Both paths result in the same access. The system checks both sources.

---

### Decision 5: Read-Only Cross-Tenant Access

**❌ Rejected**: Admin/refresh permissions for cross-tenant data access

**✅ Chosen**: All cross-tenant grants are **Read Only**

**Rationale**: Allowing a target tenant to trigger data refreshes for a source tenant creates permission complexity and potential abuse. Data refresh is handled by:
- The **source tenant** (can refresh their own data)
- **Platform admins** (can trigger manual syncs)
- **Celery scheduler** (automated daily syncs)

This simplifies the permission model significantly - grants only control **viewing** access, not **modification** actions.

---

### Decision 3: Reuse Existing Provider Infrastructure

**❌ Rejected**: New `AdoptionDataSource` table for API keys

**✅ Chosen**: Extend existing `CustomerAIProvider` + `SharedAIProvider` pattern

**Changes needed**:
- Add `is_adoption_source` boolean to `CustomerAIProvider`
- Add `chatgpt_workspace_id` to `CustomerAIProvider`
- Add new `provider_name` values: `openai_compliance`, `google_gemini_compliance`, etc.

**Rationale**: Scott already built platform-level AI provider sharing. We reuse it instead of duplicating.

---

### Decision 4: Union Query Pattern

For adoption routes, instead of filtering by single `current_user.customer_id`, we union:
1. User's own tenant
2. Permissions granted by platform admin (`adoption:read:company:X`)
3. Shares from `AdoptionDataShare` table (tenant self-service)

---

## Permission Model

### Permission Naming Convention

```
adoption:{action}:company:{target}

Where:
  action = read | manage_sharing | manage_sync | view_dashboard
  target = * (wildcard) | {customer_id}
```

### Permission Definitions

| Permission | Description |
|------------|-------------|
| `adoption:read:company:*` | View ALL companies' adoption metrics (platform admin) |
| `adoption:read:company:acme` | View Acme's adoption metrics |
| `adoption:view_dashboard` | Access the adoption dashboard UI |
| `adoption:manage_sharing` | Share MY tenant's adoption data with others |
| `adoption:manage_sync` | Trigger manual syncs for MY tenant's data |

> **Note:** The `adoption:admin:company:*` permission was removed. Cross-tenant access is always read-only. Data refresh is restricted to the source tenant only.

### Access Check Logic

```python
def get_accessible_adoption_companies(
    user: CurrentUserContext, 
    db: Session
) -> List[str]:
    """
    Get all company IDs the user can access for adoption metrics.
    
    All cross-tenant access is read-only. Checks:
    1. User's own tenant (always included)
    2. Explicit permission grants (from platform admin)
    3. AdoptionDataShare records (from tenant self-service)
    """
    accessible = set()
    
    # Always include own tenant
    accessible.add(user.customer_id)
    
    # PATH 1: Check permission grants (platform admin created)
    for perm in user.permissions:
        if perm.startswith("adoption:read:company:"):
            company_id = perm.split(":")[-1]
            if company_id == "*":
                # Wildcard - return all companies
                all_companies = db.query(Customer.customer_id).all()
                return [c[0] for c in all_companies]
            accessible.add(company_id)
    
    # PATH 2: Check adoption shares (tenant self-service)
    # All shares are read-only now
    shares = db.query(AdoptionDataShare).filter(
        AdoptionDataShare.target_customer_id == user.customer_id,
        AdoptionDataShare.is_enabled == True,
        or_(
            AdoptionDataShare.expires_at.is_(None),
            AdoptionDataShare.expires_at > func.now()
        )
    )
    
    for share in shares.all():
        accessible.add(share.source_customer_id)
    
    return list(accessible)
```

> **Note:** The `action` parameter was removed as all cross-tenant access is now read-only. The "Refresh Data" functionality is only available for the user's own tenant.

---

## Access Patterns

### Path 1: Platform Admin Grants Access (Top-Down)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Eliza Platform Admin grants Blackstone access to Acme              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Platform admin goes to: Platform Admin → Adoption Access        │
│  2. Clicks "Add Grant"                                              │
│  3. Source: Acme, Target: Blackstone, Level: Read                   │
│  4. Clicks "Create Grant"                                           │
│                                                                     │
│  Result: PlatformAdoptionGrant record created                       │
│                                                                     │
│  Use case: PE firm contract specifies portfolio company access      │
└─────────────────────────────────────────────────────────────────────┘
```

### Path 2: Tenant Self-Service Share (Bottom-Up)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Acme admin shares their adoption data with Blackstone              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. Acme admin goes to: Adoption Dashboard → Sharing Manager        │
│  2. Clicks "Share with another company"                             │
│  3. Selects: Blackstone                                             │
│  4. Permission level: View Only / Admin                             │
│                                                                     │
│  Result: AdoptionDataShare record created                           │
│                                                                     │
│  Use case: Portco opts-in to share with their parent company        │
└─────────────────────────────────────────────────────────────────────┘
```

### What Users See

**Blackstone user in adoption dashboard:**
- Sees ONLY companies they have access to (Acme, Beta, Gamma)
- Does NOT see other tenants (Delta, Epsilon)
- API filters to accessible companies only

---

## API Keys & Data Sources

### Reusing Existing Infrastructure

We extend `CustomerAIProvider` with new fields:

```python
# Add to CustomerAIProvider model
is_adoption_source = Column(Boolean, default=False, nullable=False)
chatgpt_workspace_id = Column(String(100), nullable=True)  # UUID format
adoption_compliance_status = Column(String(20), nullable=True)  # 'success', 'failed', 'untested'
adoption_compliance_last_checked = Column(DateTime(timezone=True), nullable=True)
adoption_compliance_error = Column(Text, nullable=True)
```

### Provider Types for Adoption

| provider_name | Description |
|---------------|-------------|
| `openai_compliance` | OpenAI Compliance API for ChatGPT Enterprise metrics |
| `google_gemini_compliance` | Google Gemini usage metrics (future) |
| `anthropic_compliance` | Anthropic Claude usage metrics (future) |

### API Key Management

| Question | Answer |
|----------|--------|
| **Where is the key stored?** | `CustomerAIProvider.api_key_encrypted` (JSON with `api_key` and `workspace_id`) |
| **Which company is it for?** | `CustomerAIProvider.customer_id` (e.g., "acme") |
| **Who can configure it?** | Tenant admin or platform admin |
| **Can it be shared?** | **NO** - Adoption keys must be tenant-specific (see below) |

### Decision 6: Adoption Keys Cannot Be Shared

**Rule:** API keys used for adoption tracking (`is_adoption_source = true`) **cannot be shared** with other tenants.

**Rationale:**
- Each tenant's ChatGPT Enterprise workspace has a unique Workspace ID
- Adoption metrics are tenant-specific - sharing would mix data incorrectly
- Compliance API credentials should remain within the tenant that owns them

**Enforcement:**
1. **Backend validation**: Cannot enable `is_adoption_source` on a key that is globally shared or shared with specific tenants
2. **UI indication**: If a key is shared, the adoption section is disabled with message: *"Adoption tracking requires a dedicated, non-shared API key. Either unshare this key or create a new key for adoption metrics."*
3. **Uniqueness**: Each tenant can have only ONE key per provider type marked as adoption source

**Summary:**
```
| Key Type                      | Can Enable Adoption? |
|-------------------------------|----------------------|
| Tenant-specific (not shared)  | ✅ Yes               |
| Shared globally               | ❌ No                |
| Shared with specific tenants  | ❌ No                |
| Platform-level key            | ❌ No (platform keys are meant to be shared) |
```

### OpenAI Compliance API Requirements

The Compliance API requires manual approval:

1. **Email**: `support@openai.com`
2. **Include**:
   - Last 4 digits of API key
   - Key Name (from OpenAI Platform)
   - Created By Name
   - Requested scope: `read`
3. **Workspace ID**: Found in ChatGPT Enterprise admin console (UUID format)

---

## Database Schema

### New Table: `AdoptionDataShare`

Tenant-to-tenant adoption data sharing (self-service):

```python
class AdoptionDataShare(BaseModel):
    """
    Allows a tenant to share their adoption metrics with another tenant.
    All shares are read-only - target tenant can view but not modify/refresh data.
    """
    __tablename__ = "adoption_data_shares"
    
    source_customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    target_customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    share_level = Column(String(20), default="read", nullable=False)  # Always "read" (legacy field)
    shared_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    shared_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
```

> **Note:** The `share_level` field is retained for backwards compatibility but is always set to "read". The UI no longer offers an "admin" option for cross-tenant sharing.

### New Table: `AdoptionDailyMetrics`

Aggregated metrics per company per day:

```python
class AdoptionDailyMetrics(BaseModel):
    __tablename__ = "adoption_daily_metrics"
    
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    metric_date = Column(Date, nullable=False, index=True)
    
    # Core metrics
    active_users = Column(Integer, default=0)  # Unique users who sent messages on this day
    total_messages = Column(Integer, default=0)  # User messages sent on this day
    total_conversations = Column(Integer, default=0)  # Conversations with activity on this day
    
    # GPT adoption metrics (added Jan 2026)
    gpt_conversations = Column(Integer, default=0)  # Conversations using custom GPTs
    base_conversations = Column(Integer, default=0)  # Conversations using base ChatGPT
    unique_gpts = Column(Integer, default=0)  # Count of distinct GPTs used
    
    # Legacy fields (not populated - Compliance API doesn't provide tokens)
    input_tokens = Column(BigInteger, default=0)  # Not available from API
    output_tokens = Column(BigInteger, default=0)  # Not available from API
    
    # JSON breakdowns
    model_breakdown = Column(JSON, nullable=True)
    top_gpts = Column(JSON, nullable=True)  # List of {id, name, uses, users, creator_email}
    user_distribution = Column(JSON, nullable=True)
    sync_metadata = Column(JSON, nullable=True)  # {synced_at: timestamp}
```

### New Table: `PlatformAdoptionGrant`

Platform admin grants for cross-tenant access:

```python
class PlatformAdoptionGrant(BaseModel):
    __tablename__ = "platform_adoption_grants"
    
    source_customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    target_customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    share_level = Column(String(20), default="read", nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Path A: Platform admin creates PlatformAdoptionGrant               │
│          (Acme → Blackstone)                                        │
│                                                                     │
│  Path B: Acme admin creates AdoptionDataShare targeting Blackstone  │
│                                                                     │
│  Path C: Acme admin configures CustomerAIProvider                   │
│          (openai_compliance with is_adoption_source=true)           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        DAILY SYNC                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Celery Beat (every 6 hours)                                        │
│         │                                                           │
│         ▼                                                           │
│  daily_adoption_sync task                                           │
│         │                                                           │
│         ▼                                                           │
│  For each enabled adoption provider:                                │
│    ├── Decrypt credentials                                          │
│    ├── Call OpenAI Compliance API                                   │
│    │   ├── GET /compliance/workspaces/{id}/users                    │
│    │   └── GET /compliance/workspaces/{id}/conversations            │
│    ├── Aggregate metrics (NO content stored!)                       │
│    └── Upsert into adoption_daily_metrics                           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        VIEWING                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Blackstone user opens adoption dashboard                           │
│         │                                                           │
│         ▼                                                           │
│  GET /api/v1/adoption/metrics                                       │
│         │                                                           │
│         ▼                                                           │
│  get_accessible_adoption_companies(user, db)                        │
│    ├── Check PlatformAdoptionGrant records                          │
│    ├── Check AdoptionDataShare records                              │
│    └── Return: ["blackstone", "acme", "beta", "gamma"]              │
│         │                                                           │
│         ▼                                                           │
│  Dashboard UI renders metrics, charts, comparisons                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Roles & Feature Flags

### Feature Flag

```yaml
Feature Key: adoption_dashboard
Display Name: "Adoption Dashboard"
Description: "Track ChatGPT Enterprise and LLM adoption across companies"
Default: Disabled (platform admin enables per tenant)
```

### Custom Roles

#### adoption_analyst

```yaml
Role: adoption_analyst
Display Name: "Adoption Analyst"
Description: "View adoption metrics for granted companies"
Tenant-scoped: YES
System role: NO

Default Permissions:
  - adoption:view_dashboard
  # adoption:read:company:X permissions granted separately
```

#### adoption_admin

```yaml
Role: adoption_admin
Display Name: "Adoption Administrator"  
Description: "Configure adoption data sources and sharing"
Tenant-scoped: YES
System role: NO

Default Permissions:
  - adoption:view_dashboard
  - adoption:manage_sharing
  - adoption:manage_sync
  # adoption:read:company:X and adoption:admin:company:X granted separately
```

---

## API Endpoints

### Metrics Endpoints

```
GET  /api/v1/adoption/metrics       # Get metrics for accessible companies
GET  /api/v1/adoption/overview      # High-level overview with summaries
GET  /api/v1/adoption/dashboard     # Dashboard widget data
```

### Sharing Endpoints (Self-Service)

```
GET    /api/v1/adoption/shares        # List all shares (inbound + outbound)
POST   /api/v1/adoption/shares        # Create new share
PATCH  /api/v1/adoption/shares/{id}   # Update share
DELETE /api/v1/adoption/shares/{id}   # Delete share
```

### Provider Endpoints

```
GET  /api/v1/adoption/providers              # List providers with adoption flag
POST /api/v1/adoption/providers/{id}/enable  # Enable for adoption sync
POST /api/v1/adoption/providers/{id}/disable # Disable from adoption sync
```

### Sync Endpoints

```
POST /api/v1/adoption/sync          # Trigger manual sync (queues Celery task)
```

### Platform Admin Endpoints

```
GET    /api/v1/platform-admin/adoption/grants        # List all grants
POST   /api/v1/platform-admin/adoption/grants        # Create grant
PATCH  /api/v1/platform-admin/adoption/grants/{id}   # Update grant
DELETE /api/v1/platform-admin/adoption/grants/{id}   # Delete grant
```

---

## Implementation Checklist

### Database Migration ✅

- [x] Add `is_adoption_source` to `customer_ai_providers` table
- [x] Add `chatgpt_workspace_id` to `customer_ai_providers` table
- [x] Create `adoption_data_shares` table
- [x] Create `adoption_daily_metrics` table
- [x] Create `platform_adoption_grants` table

### Backend ✅

- [x] Create `src/models/adoption.py` with new models
- [x] Add `get_accessible_adoption_companies()` to authorization middleware
- [x] Add `check_adoption_access()` helper
- [x] Add `require_adoption_access()` FastAPI dependency
- [x] Create `src/api/routes/adoption.py`
- [x] Create `src/api/schemas/adoption.py`
- [x] Create `src/services/adoption_service.py`
- [x] Create `src/tasks/adoption_sync_tasks.py`
- [x] Create `src/services/adoption/sync_service.py`
- [x] Create `src/services/adoption/openai_compliance_client.py`
- [x] Register adoption tasks in `src/celery_app.py`
- [x] Add platform admin adoption grant endpoints

### Permissions & Roles ✅

- [x] Add adoption permissions to database via migration
- [x] Create `adoption_analyst` role
- [x] Create `adoption_admin` role
- [x] Add `adoption_dashboard` feature flag

### Platform Admin UI ✅

- [x] Create "Adoption Access" page for managing grants
- [x] Add navigation to Platform Admin section
- [x] Grant CRUD operations (create, read, update, delete)

### Dashboard Frontend ✅

- [x] Create `frontend/src/pages/adoption/AdoptionDashboardPage.tsx`
- [x] Create metric cards component
- [x] Create usage charts component (Recharts)
- [x] Create company selector component
- [x] Create sharing manager component
- [x] Create React Query hooks (`useAdoption.ts`)
- [x] Add navigation under "Analytics" section
- [x] Route protection with permissions and feature flags

### Tests ✅

- [x] `tests/adoption/test_adoption_api.py` - API endpoint tests
- [x] `tests/adoption/test_adoption_auth.py` - Authorization tests
- [x] `tests/adoption/test_adoption_sharing.py` - Sharing functionality tests

---

## Metrics Definitions

| Metric | Definition |
|--------|------------|
| **Daily Active Users (DAU)** | Unique users who sent at least 1 message on a given day |
| **Weekly Active Users (WAU)** | Unique users active in the past 7 days |
| **Monthly Active Users (MAU)** | Unique users active in the past 30 days |
| **Avg Daily Users** | Average DAU over the selected date range (displayed in dashboard) |
| **Messages per User** | Total messages / Active users for a period |
| **GPT Conversations** | Conversations that used a custom GPT (has `gpt_id` in messages) |
| **Base Conversations** | Conversations using only base ChatGPT (no custom GPT) |
| **GPT Adoption Rate** | (GPT Conversations / Total Conversations) × 100% |
| **Top GPTs** | Ranked by total usage count within company |
| **Power User** | User in top 10% by message count |

> **Note:** Token metrics (input_tokens, output_tokens) are NOT available from the OpenAI Compliance API and have been removed from the dashboard.

---

## Technical Stack

| Component | Technology |
|-----------|------------|
| Frontend | React 18 + TypeScript + CRA |
| UI Library | shadcn/ui + Tailwind CSS |
| Charts | Recharts |
| Backend API | Python FastAPI |
| Database | PostgreSQL 15+ |
| Task Queue | Celery + Redis |
| Deployment | Docker + Northflank |

---

## Security Considerations

- **API keys encrypted at rest** using existing `encrypt_value()` utility
- **No message content stored** - only aggregated metrics
- **Tenant isolation** via permission checks (not RLS for cross-tenant reads)
- **Audit logging** for all access and configuration changes
- **Share expiration** optional for time-limited access

---

## Related Documents

- [Security for Dev Team](../specs/security/security_for_dev_team.md) - Auth framework details
- [Provider Refactor Summary](./PROVIDER_REFACTOR_SUMMARY.md) - SharedAIProvider pattern

---

*Last Updated: January 5, 2026*  
*Version: 3.5 - Fixed metrics parsing bug, added GPT adoption chart, removed token metrics, memory optimization*
