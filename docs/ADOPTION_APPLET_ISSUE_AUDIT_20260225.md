# Adoption Applet Run - Root Cause Audit (2026-02-25)

## Context

- Run mode: local fresh install with applet-scoped startup
- Command used: `APPLETS=adoption REACT_APP_APPLETS=adoption ./dev-start.sh`
- Goal of this document: identify root cause for each observed issue, propose fixes, and note cross-applet impact

## Root Cause Findings by Issue

### 1) Data Connections appears in sidebar, but page is unavailable

- **Observed**
  - `Data Connections` is visible in Admin Settings navigation.
  - Navigating fails because the route is not enabled for adoption.
- **Root cause**
  - Sidebar items in section navigation are filtered only by permissions, not by applet/page enablement.
  - `Data Connections` is hardcoded in admin section config with no applet/page gate.
  - Route itself is gated correctly by `isFrontendPageEnabled('data-connections')`, creating sidebar/route mismatch.
- **Code evidence**
  - `frontend/src/components/navigation/sectionConfigs.ts` (`adminSettingsConfig` includes `/data-connections`)
  - `frontend/src/components/navigation/SectionNavContent.tsx` (filters by `requiredPermissions`, no `isFrontendPageEnabled` check)
  - `frontend/src/App.tsx` (route guarded with `isDataConnectionsEnabled`)
- **Fix recommendation**
  - Add page-key-aware filtering in `SectionNavContent` so nav items are hidden when their page key is disabled.
  - Alternatively encode `pageKey` in section item config and enforce applet/page filtering centrally.
- **Likely affects other applets?** **Yes (high)**
  - Any sidebar section item with path-only config and no page-gating metadata can leak similarly.
- **Confidence**: **High**

### 2) Workspaces shows unavailable domain + upload fails with 400

- **Observed**
  - Workspaces can be created, but chat/workspace picker marks setup as unavailable.
  - Uploading PDF fails with `400`.
- **Root cause**
  - Workspace availability requires READY state or documents. New workspaces are expected to be unavailable until seeded.
  - Upload path fails because tenant object storage config is missing, and backend returns `400` for that case.
  - Frontend allows upload attempt without pre-check for storage config, so user only learns at submit time.
- **Code evidence**
  - `src/api/routes/workspace.py` (`get_workspace_picker`: `is_available` checks READY/doc count)
  - `src/services/native_rag_service.py` (`upload_document`: raises if storage config unresolved)
  - `src/api/routes/ragflow.py` (`upload_document`: maps storage-config failure to HTTP 400)
  - `frontend/src/pages/domains/DomainDetailPage.tsx` (uploads directly, no storage-config pre-validation)
  - `frontend/src/pages/chat/ChatPage.tsx` (shows unavailable workspaces with "Configure" path)
- **Fix recommendation**
  - Add preflight storage-config check in workspace upload UI and show actionable CTA to `Tenant Admin > Storage`.
  - Return structured backend error code (for example `STORAGE_NOT_CONFIGURED`) to avoid generic `400` UX.
  - Consider blocking workspace creation or showing explicit warning when storage is not configured.
- **Likely affects other applets?** **Yes (medium-high)**
  - Any applet using shared workspaces/document upload flow will hit same behavior.
- **Confidence**: **High**

### 3) AI Recruiter appeared once, then disappeared after hard refresh

- **Observed**
  - `AI Recruiter` was visible on first load, not visible after hard refresh.
- **Root cause (most likely)**
  - Stale frontend bundle/cache state from previous build configuration (`REACT_APP_APPLETS`) on initial load.
  - In current code, `AI Recruiter` visibility in main nav should be hidden for adoption-only because `isFrontendAppEnabled('talent')` depends on enabled pages and adoption only maps to `adoption`.
- **Code evidence**
  - `frontend/src/components/navigation/MainNavContent.tsx` (apps filtered by `isFrontendAppEnabled(app.id)`)
  - `frontend/src/shared/lib/applets.ts` (`ENABLED_APPLETS` from `REACT_APP_APPLETS`; talent page mapping)
  - `frontend/src/shared/lib/applet-manifest.generated.json` (`adoption` maps only to `adoption`)
- **Fix recommendation**
  - Add a startup banner/debug log showing active applets/pages at runtime to detect stale bundles quickly.
  - Optionally add a guard in sidebar render that logs when a route/app is shown but page key is disabled.
- **Likely affects other applets?** **Possible (medium)**
  - Mainly during switching applet builds locally without cache clear/restart discipline.
- **Confidence**: **Medium**

### 4) `/data-search` remains accessible in adoption-only build

- **Observed**
  - `http://localhost:3000/data-search` is reachable when it should not be for adoption-only scope.
- **Root cause**
  - Route is gated by `isBaseChatPlatformEnabled()` (always true), not by `isFrontendPageEnabled('data-search')`.
  - `data-search` belongs to `retrieval` applet, but route guard bypasses applet manifest.
- **Code evidence**
  - `frontend/src/App.tsx` (`/data-search` route under `isRagEnabled`)
  - `frontend/src/shared/lib/applets.ts` (`isBaseChatPlatformEnabled` returns true)
  - `frontend/src/shared/lib/applet-manifest.generated.json` (`retrieval` -> `data-search`)
- **Fix recommendation**
  - Gate `data-search` routes with `isFrontendPageEnabled('data-search')` (or equivalent applet-aware helper).
- **Likely affects other applets?** **Yes (high)**
  - Any route still tied to global/base flags instead of page-key checks can leak across applet boundaries.
- **Confidence**: **High**

### 5) No default roles available in invite flow

- **Status**: **Implemented** (2026-02-26)
- **Observed**
  - Invite modal shows: `No roles available. Create roles first.`
- **Root cause**
  - `scripts/init_tenant.py` fallback creates only tenant `platform_admin` when no roles exist.
  - Invite modal explicitly excludes `platform_admin`, leaving zero assignable roles.
  - For tenant admin-created tenants, `create_default_roles_for_tenant` creates `admin/editor/viewer`; but this path is not used by `init_tenant.py` fallback.
- **Code evidence**
  - `scripts/init_tenant.py` (`ensure_platform_admin_role` creates only `platform_admin` role)
  - `frontend/src/components/users-roles/InviteUserModal.tsx` (filters out `platform_admin`; shows "No roles available")
  - `src/services/tenant_admin_service.py` (`create_default_roles_for_tenant` defines `admin/editor/viewer`)
- **Implementation notes**
  - Updated `scripts/init_tenant.py` to ensure default assignable roles (`admin`, `editor`, `viewer`) are seeded for initialized tenant(s), in addition to `platform_admin`.
  - Invite flow now has baseline assignable roles available by default.
- **Likely affects other applets?** **Yes (high)**
  - This is bootstrap-path-specific, not adoption-specific.
- **Confidence**: **High**

### 6) Create Role flow shows all applet permissions/roles instead of adoption scope

- **Status**: **Implemented** (2026-02-26)
- **Observed**
  - Role creation picker surfaces full permission universe rather than adoption-limited tenant scope.
- **Root cause**
  - Role editor calls `/api/v1/admin/permissions/all`.
  - Backend endpoint returns all permissions for users with `platform:admin`.
  - In local bootstrap, active user is platform admin, so filtering by allocated tenant features is bypassed.
- **Code evidence**
  - `frontend/src/components/users-roles/RoleEditorModal.tsx` (uses `/api/v1/admin/permissions/all`)
  - `src/api/routes/tenant_admin.py` (`get_all_permissions`: platform admins see all permissions)
- **Implementation notes**
  - Role editor now calls tenant scope explicitly: `/api/v1/admin/permissions/all?scope=tenant`.
  - Backend `get_all_permissions` now defaults to tenant scope and only returns global permissions when explicitly requested with `scope=global` by a platform admin context.
- **Likely affects other applets?** **Yes (high)**
  - Any applet using the same role editor endpoint will show global permissions for platform admins.
- **Confidence**: **High**

### 7) Platform admin role surfaces show all possible roles

- **Status**: **Implemented** (2026-02-26)
- **Observed**
  - Platform-admin-visible role surfaces include global/full role set.
- **Root cause**
  - Role listing path is customer-scoped but not feature/applet-scoped.
  - Permission catalog for platform-admin principal is intentionally global in current code.
  - Adoption migration also introduces system roles with `customer_id IS NULL` (global/system role model), which increases perceived cross-applet role surface.
- **Code evidence**
  - `src/services/tenant_admin_service.py` (`get_tenant_roles` filters by `customer_id`, not by allocated features)
  - `src/api/routes/tenant_admin.py` (`list_roles` returns `get_tenant_roles`)
  - `alembic/versions/ee5ff6gg7hh8_add_adoption_feature_and_permissions.py` (creates adoption system roles with `customer_id IS NULL`)
- **Implementation notes**
  - Added tenant feature-scoped role filtering in `TenantAdminService.get_tenant_roles(..., filter_by_allocated_features=True)`.
  - `GET /api/v1/admin/roles` now supports `scoped_to_allocated_features` and defaults to `true`.
  - Tenant admin role surfaces (and invite/user role validation paths) now use scoped role catalogs.
- **Likely affects other applets?** **Yes (high)**
  - This is structural in role catalog/filtering logic.
- **Confidence**: **High**

## Cross-Applet Impact Summary

- **High cross-applet risk**
  - Sidebar-vs-route gating mismatches where nav is permission-only.
  - Routes gated by global/base flags instead of page-key checks.
  - Role editor using global permission endpoint for platform-admin principals.
  - Bootstrap path creating only `platform_admin` without tenant assignable defaults.
- **Medium cross-applet risk**
  - Workspace upload/storage-config UX gap for all RAG/workspace-enabled applets.
  - First-load inconsistency if stale frontend bundles are reused while switching applet build scopes.

## Proposed Fix Plan (No Code Changes Yet)

1. **Frontend gating parity**
   - Introduce `pageKey` metadata for nav items and enforce `isFrontendPageEnabled(pageKey)` in shared nav filtering.
   - Replace `isRagEnabled` guards for applet-specific routes (like `data-search`) with page-key checks.
2. **Bootstrap roles**
   - Update `init_tenant.py` to seed assignable tenant roles (`admin/editor/viewer`) consistently.
3. **Tenant role scoping**
   - Add tenant-feature filtering for role catalogs and ensure tenant-admin UIs call tenant-scoped permission endpoints.
4. **Workspace upload UX**
   - Add frontend preflight check and explicit storage-setup guidance before document upload.
5. **Validation across applets**
   - Run applet-by-applet smoke matrix for: visible nav items, route accessibility, role picker scope, invite role availability.

## Deferred TODOs

- **TODO (deferred): Issue #4 (`/data-search` route exposure)**
  - Decision: skip for now because `data-search` is being consolidated into shared `workspaces` + `rag chat` flows.
  - Follow-up plan:
    - convert `/data-search` to a legacy redirect during consolidation,
    - then remove standalone `data-search` applet/page wiring from modular manifests and frontend gating once complete.

## Active Priority Order (Updated)

1. Issue #1 - Sidebar/route gating parity (`Data Connections` visible but route unavailable)
2. Issue #3 - AI Recruiter first-load inconsistency
3. Issue #4 - Deferred (consolidation path)
4. Issue #2 - Last (teammate-owned workspace/upload flow)

## Implemented Fixes (Issue #1)

### Status

- **Implemented** (frontend)

### What was changed

- Added generic `pageKey` metadata support for section/submenu nav items.
- Updated section submenu filtering to enforce applet/page enablement using `isFrontendPageEnabled(pageKey)` when provided.
- Refactored section activation (`getSectionFromPath`) to be item-driven and page-aware:
  - matches current path against configured submenu items,
  - returns section only when matched item is enabled,
  - prevents disabled applet paths from activating contextual submenus.
- Added `pageKey` coverage for key submenu surfaces:
  - Admin settings submenu (`data-connections`, tenant admin/settings/theme/storage)
  - AI Console submenu (`evals`, `telemetry`, `gepa-optimizer`, `prompt-management`)
  - AI Recruiter submenu (`talent-intelligence`, `reference-checks`)
  - Platform settings submenu (`admin`/`adoption` scoped items)
- Workspace telemetry CTA now uses the same submenu-path enablement helper and shows:
  - `"Function is disabled, contact an admin for help."`
  - instead of navigating into disabled flows.

### Files updated

- `frontend/src/components/navigation/sectionConfigs.ts`
- `frontend/src/components/navigation/SectionNavContent.tsx`
- `frontend/src/pages/domains/DomainDetailPage.tsx`

### Why this addresses the issue

- Eliminates sidebar/route drift for section submenus by making applet visibility declarative and centralized.
- Applies the same modular gating rule across submenus (not just one hardcoded path).
- Prevents contextual sidebar states from opening for disabled applet pages.

## Implemented Fixes (Issue #5, #6, #7)

### Status

- **Implemented** (backend + frontend integration validated)

### What was changed

- `scripts/init_tenant.py` now seeds default assignable roles (`admin`, `editor`, `viewer`) in bootstrap path.
- `RoleEditorModal` now requests tenant-scoped permission catalog (`scope=tenant`).
- `tenant_admin` permissions endpoint now distinguishes explicit `scope=global` from default tenant scope.
- Tenant role listing now supports and defaults to allocated-feature scoping (`scoped_to_allocated_features=true`).
- Role validation in invite and user-role assignment paths uses scoped tenant role catalogs.

### Validation notes

- Invite flow no longer depends on manual role creation in fresh bootstrap path.
- Tenant admin role surfaces return scoped roles (`admin/editor/viewer/platform_admin`) instead of broad/global role sets.
- Permission picker scope now follows tenant allocation context (empty list when tenant has no allocated features, by design).
