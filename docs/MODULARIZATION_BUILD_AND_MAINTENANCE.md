# Eliza Platform Modularization: Build and Maintenance Guide

## Implemented vs Pending

### Implemented

- Frontend/backend modular name mismatch mitigation via generated frontend applet-page manifest and page-based gating.
- Startup seeding controls (`SEED_DATA`, `SEED_DEFAULT_WORKSPACES`) with applet-aware checks.
- Cross-applet dependency declaration support (`depends_on`) in applet manifests and registry.
- Applet composition fixes from review (`bedrock` to `_base`, `hr`/`compliance` to `talent`, `api_keys` removed from `ops`).
- Fallback hardening (`celery` no silent load-all on empty applet task resolution, migration runner strict mode and explicit fallback warnings).
- Customer profile image hygiene and CI enforcement for required applets/profile exclusion checks.

### Pending / Deferred

- SQLAlchemy model-loading optimization work is intentionally paused (per decision); revisit after effort estimate for Option B.
- Optional frontend hardening: automatically regenerate and verify `frontend/src/shared/lib/applet-manifest.generated.json` in CI/build to remove manual drift risk.

## Modularization Summary

Here is what changed to make Eliza modular and deployable by selected feature sets (applets).

- Added an applet manifest system (`applets/*.yaml` + profiles) to declare:
  - backend routes
  - celery task modules
  - frontend pages/navigation
  - migration tags
- Added applet registry/loading in `src/applets/`:
  - parses `APPLETS`
  - resolves dependencies/base features
  - supports applet-level `depends_on` resolution
  - validates/normalizes manifest values
- Made backend route registration applet-aware in `src/main.py`.
- Made Celery task discovery applet-aware in `src/celery_app.py`.
- Made frontend feature visibility applet-aware (sidebar/home/nav + applet utility), including page-level checks from a generated manifest.
- Added applet-aware migration flow:
  - `scripts/run_migrations.py` for selective migration planning/execution
  - migration tag linting and readiness checks (`scripts/lint_migration_tags.py`, `scripts/validate_flatten_readiness.py`)
  - head topology checks (`scripts/check_alembic_heads.py`)
- Updated container startup to use modular migration runner (`docker/entrypoint.sh`).
- Backfilled migration metadata tags across existing Alembic revisions (modified existing files, not mass-created new migrations).
- Added one bridge merge revision: `alembic/versions/zz26_flatten_baseline_merge.py`.
- Added docs/runbooks and CI checks for modularity + migration safety.
- Added startup seeding controls and applet-aware seeding in `src/main.py`:
  - `SEED_DATA=true|false`
  - `SEED_DEFAULT_WORKSPACES=true|false` (default false)
- Hardened silent fallback behavior:
  - Celery no longer silently loads all task modules when applet task resolution is empty.
  - Migration runner now supports `--mode strict` and emits explicit warning/error logs on fallback.
- Applied composition fixes from review decisions:
  - moved `bedrock` to `_base`
  - moved `hr` and `compliance` to `talent`
  - removed `api_keys` from `ops` until route module exists

## Docker Compose Changes

The base compose file (`docker/docker-compose.yml`) was updated to support modular build and runtime behavior:

- `app` and `celery-worker` build with `APPLETS: ${APPLETS:-all}`.
- `frontend` build uses `REACT_APP_APPLETS: ${REACT_APP_APPLETS:-all}`.
- Runtime envs pass through `APPLETS=${APPLETS:-all}` so backend route/task loading is applet-aware.
- Startup migrations now run through `scripts/run_migrations.py` (via `docker/entrypoint.sh`) using applet selection and migration mode guardrails.
- Startup seed behavior is env-controlled via `SEED_DATA` and `SEED_DEFAULT_WORKSPACES`.
- Worker topology is profile-gated so modular deployments can run lean by default.

Two new compose override files were added:

- `docker/docker-compose.applet-adoption.yml`
  - Purpose: quick adoption-only deployment/demo.
  - Sets `APPLETS=adoption` for app/worker and `REACT_APP_APPLETS=adoption` for frontend build.
  - Disables optional integrations for lighter runtime (`LOGSTASH_ENABLED`, `ELASTICSEARCH_SYNC_ENABLED`, `NEO4J_SYNC_ENABLED`, `LANGFUSE_ENABLED`, `RAG_KB_S3_SYNC_ENABLED`).

- `docker/docker-compose.modular-single-worker.yml`
  - Purpose: enforce a single primary worker path for modular deployments.
  - Keeps `celery-worker` active.
  - Moves `celery-beat`, `celery-ingestion-worker`, and `flower` behind a disabled profile unless explicitly enabled.

Example layered run:

```bash
docker compose \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.applet-adoption.yml \
  -f docker/docker-compose.modular-single-worker.yml \
  up -d --build
```

## Build and Run Commands

Run these from repo root (`/Users/romanwicky/Projects/ElizaPlatform`).

### 0) Prerequisite

```bash
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"
```

### 1) Base only

```bash
APPLETS=_base docker compose -f docker/docker-compose.yml build app celery-worker
REACT_APP_APPLETS=_base docker compose -f docker/docker-compose.yml build frontend
APPLETS=_base REACT_APP_APPLETS=_base docker compose -f docker/docker-compose.yml up -d --force-recreate app celery-worker frontend
```

### 2) Base + 1 applet (example: adoption)

```bash
APPLETS=adoption docker compose -f docker/docker-compose.yml build app celery-worker
REACT_APP_APPLETS=adoption docker compose -f docker/docker-compose.yml build frontend
APPLETS=adoption REACT_APP_APPLETS=adoption docker compose -f docker/docker-compose.yml up -d --force-recreate app celery-worker frontend
```

### 3) Base + 2 applets (example: adoption + content)

```bash
APPLETS=adoption,content docker compose -f docker/docker-compose.yml build app celery-worker
REACT_APP_APPLETS=adoption,content docker compose -f docker/docker-compose.yml build frontend
APPLETS=adoption,content REACT_APP_APPLETS=adoption,content docker compose -f docker/docker-compose.yml up -d --force-recreate app celery-worker frontend
```

### 4) All applets

```bash
APPLETS=all docker compose -f docker/docker-compose.yml build app celery-worker
REACT_APP_APPLETS=all docker compose -f docker/docker-compose.yml build frontend
APPLETS=all REACT_APP_APPLETS=all docker compose -f docker/docker-compose.yml up -d --force-recreate app celery-worker frontend
```

### Optional startup-seeding controls

```bash
# Disable all startup seeding (recommended for most production deployments)
SEED_DATA=false

# Keep generic seeding on, but do not seed customer-specific default workspaces
SEED_DATA=true
SEED_DEFAULT_WORKSPACES=false

# Explicitly enable default workspace seeding when needed
SEED_DATA=true
SEED_DEFAULT_WORKSPACES=true
```

## Alembic Notes (Short)

Alembic already existed in this project before modularization. The modular work added migration tagging and selective execution support so applet-specific builds can safely plan/apply only the required migration graph. Most Alembic version files were modified to add metadata tags; only one new bridge merge revision was added (`zz26_flatten_baseline_merge.py`).

Migration runner mode guidance:
- `safe`: always run full migration tree
- `auto`: try selective, fallback to full with warning logs
- `selective`: fail if selective planning is invalid
- `strict`: fail on selective mismatches/no-op (use in CI/validation)

## Quick Verification Commands

```bash
curl -sf http://localhost:5001/health/ready
curl -sfI http://localhost:3000
docker compose -f docker/docker-compose.yml logs --tail=120 app
docker compose -f docker/docker-compose.yml logs --tail=120 celery-worker
docker compose -f docker/docker-compose.yml logs --tail=80 frontend
```

Optional OpenAPI spot-check:

```bash
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://localhost:5001/openapi.json", timeout=10) as r:
    paths = sorted(json.load(r).get("paths", {}).keys())
print("total_paths:", len(paths))
print("adoption_paths:", len([p for p in paths if "adoption" in p.lower()]))
print("content_paths:", len([p for p in paths if "content" in p.lower()]))
PY
```

## How This Is Maintained

- **Applet manifests are the source of truth**  
  Add/change features in `applets/*.yaml` (and profiles if needed), not scattered conditionals.
- **Declare applet dependencies explicitly**  
  Use `depends_on` in applet manifests for runtime dependencies.
- **Route/task/page wiring is declarative**  
  Keep manifests aligned with actual Python/TS modules.
- **Migrations stay tag-aware**  
  New migration files should include `tags` so selective mode remains safe.
- **CI guardrails enforce consistency**  
  Lints/checks catch missing tags, invalid applet references, profile image-hygiene rules, and Alembic head issues.
- **Operational pattern stays consistent**  
  Build with `APPLETS` + `REACT_APP_APPLETS`, deploy same image pattern per customer/environment.
- **Customer profile hygiene**  
  Customer-specific profile names are excluded from runtime images; keep deployment/customer mapping in CI/deployment config.

## Practical Team Rules

- When adding a new feature/applet:
  - create/update applet YAML
  - add `depends_on` when runtime dependencies exist
  - wire backend routes + task modules + frontend nav/page entries
  - add migration tags if schema changes
  - run modular build for that applet and for `all`
- If you edit applet `pages:` values, regenerate frontend page manifest:
  - `python3 scripts/generate_frontend_applet_manifest.py`
- Always rebuild images after modular changes (do not rely on restart-only).
- Keep `_base` minimal and stable (chat/rag/workspace core as agreed).
- Treat warnings like missing optional env keys as ops/config hygiene unless they block health checks.

## How `pages:` Works (Quick Guide)

This is the most common source of confusion.

- `routes:` = backend route modules to load (FastAPI side)
- `tasks:` = Celery task modules to load (worker side)
- `pages:` = frontend **page keys/features** to show/hide (React side)

`pages:` is **not** a raw URL list, and usually **not** a parent section like `/admin`.
It is a set of feature keys used by frontend gating helpers (for example `isFrontendPageEnabled("telemetry")`).

### Mental model

- Use `pages:` for feature-level UI visibility (menu items, routes, buttons).
- Parent sections (like Admin/Platform Settings containers) may be permission-driven and always present.
- Applet-specific exceptions under those sections (for example Data Connections, AI Console pages) should use page keys.

### Examples

`applets/ai_console.yaml`:

```yaml
pages:
  - evals
  - telemetry
  - gepa-optimizer
  - prompt-management
```

This means AI Console feature pages are enabled in frontend when `ai_console` is active.

`applets/data_connections.yaml`:

```yaml
pages:
  - data-connections
```

This enables only the Data Connections feature surface in frontend.

`applets/adoption.yaml`:

```yaml
pages:
  - adoption
```

This enables Adoption-specific frontend surfaces.

### Rule of thumb when adding a feature

1. Add backend module name under `routes:` if it has API endpoints.
2. Add worker module under `tasks:` if it runs background jobs.
3. Add frontend feature key under `pages:` if UI visibility should be applet-scoped.
4. Keep shared/core admin shells permission-based unless intentionally applet-scoped.

## Frontend Modular Wiring (End-to-End)

This section explains exactly how the modular frontend pieces connect so agents do not introduce drift.

### Source-of-truth chain

1. `applets/*.yaml` defines applet `pages:` keys.
2. `scripts/generate_frontend_applet_manifest.py` compiles YAML into:
   - `frontend/src/shared/lib/applet-manifest.generated.json`
3. `frontend/src/shared/lib/applets.ts` resolves enabled page keys from:
   - `REACT_APP_APPLETS`
   - generated manifest mapping
4. Frontend route/nav gating uses those keys via:
   - `isFrontendPageEnabled("<page-key>")`
   - config `pageKey` fields in section/submenu items

### Where gating should live

- Route-level gating: `frontend/src/App.tsx`
- Section/submenu gating: `frontend/src/components/navigation/SectionNavContent.tsx`
- Section activation and path checks: `frontend/src/components/navigation/sectionConfigs.ts`

### Current policy: base shells vs applet exceptions

- **Base admin/platform shells**
  - Keep permission-gated (not applet page-gated by default).
  - Prevents empty Admin/Platform panels in applet-scoped builds.
- **Applet-specific exceptions**
  - Must use `pageKey` and page-key checks.
  - Examples: `data-connections`, AI Console pages, adoption-specific access surfaces.

### CI checks that enforce this

`check-applet-modularity.yml` now validates both backend and frontend modular consistency:

- `scripts/lint_applets.py`
  - applet/profile resolution
  - route key coverage vs `src/main.py`
- `scripts/lint_migration_tags.py`
  - migration tag validity/completeness
- `scripts/check_alembic_heads.py`
  - single-head topology
- `scripts/lint_frontend_applet_pages.py`
  - generated manifest matches YAML `pages`
  - `pageKey` values in `sectionConfigs.ts` must exist in manifest page keys
  - `isFrontendPageEnabled("...")` keys in `App.tsx` must exist in manifest page keys

### Agent-safe change workflow (mandatory)

When changing any applet frontend gating:

1. Update `applets/*.yaml` `pages:` if adding/removing page keys.
2. Run:
   - `python3 scripts/generate_frontend_applet_manifest.py`
3. Update frontend route/nav gating (`App.tsx`, `sectionConfigs.ts`, `SectionNavContent.tsx`) with matching page keys.
4. Run:
   - `python3 scripts/lint_frontend_applet_pages.py`
5. Run modular CI checks or equivalent local checks before merge.

### Common failure modes to avoid

- Adding a new `pageKey` in frontend but not in applet YAML `pages`.
- Editing YAML `pages` and forgetting to regenerate the generated manifest.
- Gating base admin/platform shell items by applet page keys (causes empty side panels).
- Using route/path strings as page keys instead of defined feature keys.
