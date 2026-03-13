# Modular Applet Guide

> **Purpose:** This skill helps developers add or modify features in modular builds without breaking applet gating, navigation behavior, or migration CI checks.

---

## Quick Reference

```bash
# ✅ CORRECT sequence when adding a feature
# 1. Classify: platform-core (permission-gated) or applet-scoped (applet-gated)
# 2. If applet-scoped, update applets/*.yaml (routes, tasks, pages, depends_on)
# 3. If frontend pages: changed, regenerate manifest:
python3 scripts/generate_frontend_applet_manifest.py
# 4. Wire backend + frontend gating in the right places
# 5. If schema changed, add migration tags = [...]
# 6. Run modular lint checks before PR:
python scripts/lint_applets.py
python scripts/lint_frontend_applet_pages.py
python scripts/lint_migration_tags.py --enforce-known-tags --enforce-complete-tagging
python scripts/check_alembic_heads.py
```

---

## Overview

The Eliza Platform uses a modular applet system to control which features are available in a given build. Every feature must be classified as either **platform-core** (always available, permission-gated) or **applet-scoped** (optional per build, applet-gated).

### Applet Contract

- `routes:` = backend route modules
- `tasks:` = Celery task modules
- `pages:` = frontend page keys for `isFrontendPageEnabled("<key>")`
- `depends_on:` = applet dependencies

### Frontend Gating Contract

Source-of-truth chain:

1. `applets/*.yaml` declares page keys
2. `scripts/generate_frontend_applet_manifest.py` generates:
   - `frontend/src/shared/lib/applet-manifest.generated.json`
3. `frontend/src/shared/lib/applets.ts` resolves enabled pages from `REACT_APP_APPLETS`
4. UI uses `pageKey` + `isFrontendPageEnabled()`

### Platform-Core vs Applet-Scoped

**Platform-Core Features** (always present): Use for shared platform/admin capabilities (for example Users & Roles, tenant/platform SSO settings).

- Route is registered normally in `frontend/src/App.tsx`
- Access is controlled by `ProtectedRoute` permissions
- Sidebar item has **no `pageKey`**
- No entry required in applet `pages:` for visibility

**Applet-Scoped Features** (optional by build): Use for features that should disappear in applet-limited builds (for example Data Connections, AI Console pages).

- Add page key to applet YAML `pages:`
- Regenerate manifest
- Add `pageKey` to nav item in `sectionConfigs.ts`
- Gate route/menu visibility via `isFrontendPageEnabled("<page-key>")`

---

## Critical Rules

### Rule 1: Admin/Platform Features Must Be Platform-Core

**Context:** SSO settings/policy and similar admin capabilities are platform-core. Applet-gating them creates empty side panels in applet-limited builds and breaks admin workflows. Follow the same pattern as Users & Roles.

```typescript
// ❌ WRONG: Applet-gating a platform admin feature
{
  label: "SSO Settings",
  path: "/settings/sso",
  pageKey: "sso_settings",  // Don't applet-gate admin features!
  permissions: ["system:admin"]
}

// ✅ CORRECT: Permission-gated only, no pageKey
{
  label: "SSO Settings",
  path: "/settings/sso",
  permissions: ["system:admin"]  // Platform-core, always available
}
```

Do not introduce ad-hoc "always enabled page" constants for SSO if SSO is not page-key gated. This avoids drift and keeps behavior consistent with existing admin-shell policy.

### Rule 2: Always Tag Migrations

**Context:** Alembic migrations without `tags` fail CI. Every migration must include tags from the approved list so the modular build system can determine which migrations apply to which applet configurations.

```python
# ❌ WRONG: Migration without tags — CI will reject
revision = "abc123"
down_revision = "def456"
# No tags!

def upgrade():
    ...

# ✅ CORRECT: Migration with approved tags
revision = "abc123"
down_revision = "def456"
tags = ["tenancy", "auth"]

def upgrade():
    ...
```

Current allowed tags in CI:

- `adoption`
- `ai_console`
- `auth`
- `bi`
- `connectors`
- `content`
- `core`
- `evals`
- `ops`
- `retrieval`
- `talent`
- `tenancy`

For tenant/admin SSO schema changes, use:

```python
tags = ["tenancy", "auth"]
```

### Rule 3: Regenerate Manifest After YAML Changes

**Context:** The frontend manifest is generated from `applets/*.yaml`. If you update the YAML but forget to regenerate, the frontend won't see the new page keys and gating will be stale.

```bash
# ❌ WRONG: Updated applets/*.yaml but skipped regeneration
# Frontend still uses old manifest — new page keys are invisible

# ✅ CORRECT: Always regenerate after YAML changes
python3 scripts/generate_frontend_applet_manifest.py
```

### Rule 4: Run Validation Before PR

**Context:** Modular lint checks catch mismatches between applet YAML declarations, frontend page keys, migration tags, and Alembic head state. Skipping these leads to CI failures.

```bash
# ✅ CORRECT: Run all modular lint checks
python scripts/lint_applets.py
python scripts/lint_frontend_applet_pages.py
python scripts/lint_migration_tags.py --enforce-known-tags --enforce-complete-tagging
python scripts/check_alembic_heads.py
```

If `pages:` changed, regenerate before linting:

```bash
python3 scripts/generate_frontend_applet_manifest.py
```

---

## Patterns

### Modular Build Commands

```bash
# Base only
APPLETS=_base docker compose -f docker/docker-compose.yml build app celery-worker
REACT_APP_APPLETS=_base docker compose -f docker/docker-compose.yml build frontend

# Example applet build
APPLETS=adoption docker compose -f docker/docker-compose.yml build app celery-worker
REACT_APP_APPLETS=adoption docker compose -f docker/docker-compose.yml build frontend
```

---

## File Locations

### Backend

```
src/
├── main.py              # Route registration (applet loading)
├── celery_app.py         # Task discovery (applet loading)
applets/
└── *.yaml               # Applet declarations (routes, tasks, pages, depends_on)
```

### Frontend

```
frontend/src/
├── App.tsx                                          # Route-level modular gating
├── components/navigation/
│   ├── sectionConfigs.ts                            # Section item definitions and path-to-section mapping
│   └── SectionNavContent.tsx                        # Section item filtering by permissions and page keys
└── shared/lib/
    ├── applets.ts                                   # Enabled applet/page helpers
    └── applet-manifest.generated.json               # Generated mapping (do not edit manually)
```

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Added `pageKey` in frontend but forgot to add key under applet `pages:` | Add the key to the relevant `applets/*.yaml` file and regenerate manifest |
| Updated applet YAML but forgot to regenerate frontend manifest | Run `python3 scripts/generate_frontend_applet_manifest.py` |
| Applet-gated a base admin/platform shell item, creating empty side panels | Remove `pageKey` from admin items; use permission-gating only |
| Used URL paths as `pageKey` values instead of feature keys | Use descriptive feature keys (e.g., `data_connections`) not paths (e.g., `/data/connections`) |
| Added migration without `tags`, causing CI failure | Add `tags = [...]` with approved tag values to every migration |
| Tagged migration with unknown/non-approved tags | Check the approved tags list; only use values from the allowed set |

---

## Checklist

- [ ] Classified feature correctly: platform-core vs applet-scoped
- [ ] Updated `applets/*.yaml` (`routes`, `tasks`, `pages`, `depends_on`) if applet-scoped
- [ ] Regenerated frontend applet manifest when `pages:` changed
- [ ] Kept admin/platform shell items permission-gated unless intentionally applet-scoped
- [ ] Added/updated `pageKey` only for applet-scoped UI surfaces
- [ ] Added migration tags for any schema change
- [ ] Ran modular lint checks locally
- [ ] Rebuilt containers after modular changes

---

## References

- `docs/MODULARIZATION_BUILD_AND_MAINTENANCE.md` — Full modularization architecture and maintenance guide
- `applets/*.yaml` — Applet declarations
- `frontend/src/shared/lib/applets.ts` — Enabled applet/page resolution helpers
- `frontend/src/components/navigation/sectionConfigs.ts` — Section item definitions and path mapping
- `frontend/src/components/navigation/SectionNavContent.tsx` — Section item filtering logic
- `frontend/src/App.tsx` — Route-level modular gating
- `scripts/generate_frontend_applet_manifest.py` — Manifest generation script
- `scripts/lint_applets.py` — Applet declaration linter
- `scripts/lint_frontend_applet_pages.py` — Frontend page key linter
- `scripts/lint_migration_tags.py` — Migration tag linter
