# Modularization Feedback & Open Issues

Review of the `roman-modularization` branch. Each item includes what's wrong, why it matters, and a proposed fix.

---

## 1. Frontend-Backend Applet Name Mismatch

**Problem:**
The frontend `applets.ts` utility and the backend YAML manifests use different identifier namespaces, and nothing validates they stay in sync.

The frontend hardcodes this mapping:

```typescript
// frontend/src/shared/lib/applets.ts
const APP_ID_TO_APPLETS: Record<string, string[]> = {
  talent: ["talent"],
  chat: ["rag_chat", "bi"],
  workspaces: ["rag_chat"],
  sow: ["sow"],
  "content-research": ["content_writer"],
  adoption: ["adoption"],
};
```

But the YAML applet names are `content`, `business_intelligence`, `adoption`, etc. The frontend references `sow`, `content_writer`, and `rag_chat` -- none of which are real applet names. They're route keys or internal identifiers.

**Impact:**
Setting `REACT_APP_APPLETS=content` will **not** enable SOW or Content Research pages, because the frontend checks for `sow` and `content_writer` (route keys), not `content` (the applet name). This is a functional bug for any modular frontend build that isn't `all`.

**Proposed fix:**
- The YAML manifests already declare `pages:` lists. The frontend should derive its visibility from the same page keys, not a separate hand-maintained map.
- Option A: Generate a JSON manifest at build time from the YAML files and import it in the frontend.
- Option B: Have the frontend fetch enabled pages from a backend discovery endpoint (see item 7).
- Either way, eliminate the hardcoded `APP_ID_TO_APPLETS` map. It will always drift.

---

## 2. Startup Seeding Should Be Applet-Aware and Flag-Controlled

**Problem:**
The FastAPI lifespan handler in `src/main.py` unconditionally seeds eval sets and FASB workspaces on every startup, regardless of which applets are enabled:

```python
# Always runs, even on adoption-only deployments
eval_set_service.ensure_static_sets_exist()          # belongs to ai_console
workspace_seed_service.ensure_default_workspaces_exist()  # FASB-specific
```

**Impact:**
- On a selective-migration deployment (e.g., `APPLETS=adoption`), the eval/workspace tables may not exist, causing startup errors.
- Even when tables exist, seeding customer-specific data (FASB workspaces) into every deployment is wrong for multi-customer scenarios.

**Proposed fix:**
1. Gate seeding behind applet checks:
   ```python
   if is_applet_enabled("ai_console"):
       eval_set_service.ensure_static_sets_exist()
   ```
2. Add a `SEED_DATA=true|false` environment variable so seeding can be disabled entirely in production deployments where data is managed through migrations or admin tooling.
3. Move customer-specific seed data (FASB workspaces) out of application startup and into a one-time setup script or migration.

Each applet's YAML manifest could optionally declare a `seed_module` that gets called during startup only when that applet is active.

---

## 3. No Cross-Applet Dependency Declaration

**Problem:**
Applets can have runtime dependencies on each other, but the YAML schema has no way to express this. For example:
- `business_intelligence` declares the `search` route, which may depend on connector infrastructure from `data_connections`.
- A future applet might need `retrieval` tables to function.

The migration runner handles schema dependencies via ancestor-closure (walking up the Alembic parent chain), but that only covers database schema. It doesn't help with runtime service dependencies (e.g., a route handler importing a service class that expects another applet's tables or configuration to exist).

**Impact:**
A user could deploy `APPLETS=business_intelligence` and get routes that call services expecting tables or infrastructure from `data_connections` that were never set up.

**Proposed fix:**
Add an optional `depends_on` field to the applet manifest schema:

```yaml
applet: business_intelligence
depends_on:
  - data_connections
routes:
  - business_intelligence
  - data_analyst
  - search
```

The registry's `resolve_applet_spec()` would automatically pull in dependencies (it already does this for profiles -- extend the same logic to applet-level dependencies). The CI lint should validate that declared dependencies exist and that there are no circular references.

---

## 4. All SQLAlchemy Models Are Imported Unconditionally

**Problem:**
The database module imports every ORM model to register them with SQLAlchemy metadata. Even an adoption-only deployment loads the full model graph (talent, BI, content, eval, etc.) into memory. If selective migrations skipped creating certain tables, any accidental query against those models would fail at runtime.

**What a fix would look like:**

This is a harder problem because SQLAlchemy's metadata registry is global. Options, from least to most invasive:

**Option A: Lazy model imports (low effort, partial win)**
Move model imports from module-level in `database.py` into a function gated by applet selection. Models for disabled applets never get imported, so their table mappings never register. Risk: if any enabled code has a transitive import to a disabled model, it breaks.

**Option B: Separate metadata per applet (medium effort)**
Use SQLAlchemy's `metadata` parameter on `Base` to create isolated metadata objects per applet group. Only the metadata for enabled applets gets bound to the engine. This is cleaner but requires refactoring model definitions to specify which metadata they belong to.

**Option C: Accept it and guard at the query layer (low effort, pragmatic)**
Keep all models loaded but add a runtime check that raises a clear error ("Applet X is not enabled") if code attempts to query a model belonging to a disabled applet. This doesn't reduce memory but prevents confusing "table does not exist" errors.

**Recommendation:** Start with Option C (cheap, prevents confusing errors), and move to Option A or B if memory footprint becomes a deployment concern.

---

## 5. Applet Composition Needs Revisiting

**Problem:**
Several applets have questionable route assignments that suggest the initial grouping was done mechanically rather than by domain logic. For example:

`ops.yaml` currently contains:
```yaml
routes:
  - admin
  - hr
  - compliance
  - bedrock
  - api_keys    # Route module doesn't exist (commented out in main.py)
```

- `hr` and `compliance` are arguably domain features (talent/HR product), not platform operations.
- `bedrock` is an AI provider integration that any applet might need -- belongs in `_base`.
- `api_keys` is declared in the manifest but the route module doesn't exist yet (`# TODO` in `main.py`).

The CI lint (`lint_applets.py` with `--enforce-route-coverage`) should catch `api_keys` as a phantom route, but currently the regex only matches uncommented `_include_router_if_enabled()` calls, so the mismatch slips through.

**Proposed fix:**
1. Audit every applet manifest against actual usage patterns. Ask: "If a customer only has this applet, do all these routes make sense together?"
2. Move `hr` and `compliance` to `talent` (or a dedicated `hr` applet if they're used independently).
3. Move `bedrock` to `_base` if it's a core AI provider route, or to a new `ai_providers` applet.
4. Remove `api_keys` from the manifest until the route module exists.
5. Update the CI lint to also flag manifest routes that are commented out in `main.py`.

---

## 6. Frontend Image Portability vs. Build-Time Applet Baking

**Problem:**
`REACT_APP_APPLETS` is injected at build time via Webpack's `process.env` replacement (standard CRA behavior). This means:
- Each customer/applet combination requires a separate frontend Docker image build.
- You cannot share a single frontend image across customers with different applet sets.
- Backend `APPLETS` and frontend `REACT_APP_APPLETS` can drift if someone updates one but not the other.

**Is it possible to keep the same frontend image?**
Yes, but it requires changes. CRA bakes `REACT_APP_*` vars at build time, so you'd need one of:
- **Runtime config injection**: Serve a `/config.json` from the backend (or nginx) that the frontend fetches at startup. The applet list comes from this file instead of `process.env`. Many production React apps do this.
- **Server-side rendering / reverse proxy**: Have the backend inject a `<script>window.__APPLETS__=["adoption"]</script>` into the HTML before serving it.

**Would we want to?**
Tradeoffs:

| | Build-time baking (current) | Runtime config |
|---|---|---|
| **Image reuse** | One image per customer | One image for all customers |
| **Security** | Only ships enabled code to customer | All frontend code ships, just hidden |
| **Build pipeline** | More builds, simpler runtime | Fewer builds, slightly more complex runtime |
| **Drift risk** | High (two env vars to keep in sync) | Low (single source of truth from backend) |

**The security angle is real**: with runtime config, a customer receives a frontend bundle containing the JavaScript for every applet. The routes/pages are hidden via JS conditionals, but the code is in the bundle and inspectable. If applets contain proprietary UI logic you don't want Customer A to see, build-time baking is the safer choice.

**Recommendation:**
- For now, keep build-time baking. It's simpler and more secure.
- If image proliferation becomes an ops burden, switch to runtime config + code-splitting so only the enabled applet chunks are fetched (React lazy + dynamic imports gated by the config).
- Either way, the frontend should validate its applet config against the backend discovery endpoint (item 7) at startup and warn on mismatch.

---

## 7. No Runtime API to Discover Enabled Applets

**Problem:**
There's no endpoint that tells a client which applets are active on the current deployment. The frontend hardcodes its knowledge at build time, and there's no way for external tooling, monitoring, or a future runtime-configured frontend to discover what's available.

**Proposed fix:**
Add a `GET /v1/applets` endpoint (gated to authenticated users) that returns:

```json
{
  "applets": ["_base", "adoption"],
  "pages": ["adoption"],
  "features": {
    "adoption": {
      "display_name": "Adoption Dashboard",
      "routes": ["adoption"],
      "pages": ["adoption"]
    }
  }
}
```

This serves multiple purposes:
- Frontend can validate its build-time config matches the backend at startup.
- Admin tooling can display what's deployed.
- Health checks can verify expected applets are loaded.
- Future runtime-configured frontend can use this as its source of truth.

The data is already available in the registry -- it just needs an HTTP surface.

---

## 8. Silent Fallback to "All" Should Be Hardened

**Problem:**
Multiple places in the codebase silently fall back to loading everything when the applet resolution produces an empty result:

```python
# src/celery_app.py
enabled_task_modules = get_enabled_task_modules(os.getenv("APPLETS"))
if enabled_task_modules is None:
    task_modules = ALL_TASK_MODULES
else:
    task_modules = []
    for task_name in enabled_task_modules:
        # ...
    if not task_modules:
        task_modules = ALL_TASK_MODULES  # <-- silent fallback
```

If someone sets `APPLETS=adoption` but the adoption manifest has an empty `tasks: []` (which it doesn't today, but could after a refactor), the system silently loads every task module. A typo in a task name that doesn't match any module would also result in an empty list, triggering this fallback.

Similarly, the migration runner's `--mode=auto` silently falls back to running the full migration tree if selective planning fails. This is reasonable as a safety net during the transition period, but should not be the permanent default.

**Proposed fix:**
1. **Remove the empty-list fallback** in `celery_app.py`. If the resolved task list is empty and `APPLETS` is not `all`, that should be a warning log, not a silent load-everything.
2. **Log loudly on fallback**. Any time the system falls back from selective to full mode, it should log at WARNING level with the reason, so ops can catch misconfigurations.
3. **Add a `--mode=strict` option** for the migration runner that errors on any fallback. Use `strict` in CI and `auto` in production during the transition.
4. **Validate applet names early**. When `APPLETS=adpotion` (typo), the registry raises a ValueError for missing manifest. Make sure this surfaces clearly in container logs rather than being swallowed.

---

## 9. Customer Profile Names Should Not Ship in Images

**Problem:**
The `applets/profiles/` directory contains customer-specific profile files like `cengage.yaml`. These files are copied into the Docker image. Even though they're not exposed via API or frontend, they exist on the container filesystem and reveal customer names to anyone with shell access to the container.

**Impact:**
Low security risk in practice (container access is already privileged), but it's a data hygiene issue. If we deploy to Walmart, they could `docker exec` into the container and see `cengage.yaml`.

**Proposed fix:**
Profiles are a developer/CI convenience -- they don't need to ship in production images.

1. **Exclude profiles from the Docker image**: Add `applets/profiles/` to `.dockerignore`, or change the `COPY` command to only copy applet manifests (not profiles).
2. **Use generic names**: If profiles must ship, name them by function not customer: `adoption-only.yaml` instead of `cengage.yaml`.
3. **Move profiles to CI/ops config**: Store customer deployment profiles in the deployment pipeline (Helm values, Northflank config, CI variables) rather than in the application repo.

Option 3 is the cleanest long-term. The repo should define applets (what features exist), and the deployment pipeline should define profiles (which features go to which customer).

---

## Priority Summary

| # | Issue | Severity | Effort |
|---|---|---|---|
| 1 | Frontend-backend applet name mismatch | **High** | Medium |
| 2 | Startup seeding not applet-aware | **Medium** | Low |
| 3 | No cross-applet dependency declaration | **Medium** | Medium |
| 5 | Applet composition needs revisiting | **Medium** | Low |
| 8 | Silent fallback to "all" masks bugs | **Medium** | Low |
| 6 | Frontend image portability | **Medium** | High |
| 7 | No applet discovery endpoint | **Low** | Low |
| 4 | All models imported unconditionally | **Low** | High |
| 9 | Customer profile names in images | **Low** | Low |

---

## Review Decisions (Updated)

The following decisions were made in the modularization review and should be treated as the current direction:

1. **Frontend-backend applet name mismatch**
   - Decision: proceed with **Option A**.

2. **Startup seeding**
   - Decision: implement the proposed seeding fix.
   - Decision: make seed-data inclusion configurable at build/deploy time.

3. **No cross-applet dependency declaration**
   - Decision: proceed with the proposed fix.

4. **SQLAlchemy optimization / model loading**
   - Decision: **pause for now** (not high priority).
   - Decision: request effort estimate from dev team for **Option B**.
   - Decision: keep **Option A** as fallback if Option B is too time-consuming, noting Option A risk concerns.

5. **Applet composition**
   - Decision: proceed with the proposed composition fix.

6. **Fallback-to-all hardening**
   - Decision: proceed with hardening fix.

7. **Customer profile names**
   - Decision: exclude customer profile names from Docker image.
   - Decision: add CI workflow checks to verify applets/profiles that should be present (and not present).
