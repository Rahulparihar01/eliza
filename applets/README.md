# Applet Manifests

Applets define modular deployment slices for the platform.

## Quick Usage

- `APPLETS=all` (default): current behavior, load all routes/tasks.
- `APPLETS=adoption`: load `_base.yaml` + `adoption.yaml`.
- `APPLETS=cengage`: resolve profile from `profiles/cengage.yaml`.
- `APPLETS=full`: resolve profile from `profiles/full.yaml`.

### Important base behavior

- `_base` always includes Chat + RAG + Workspace platform capability.
- Any applet build (for example `APPLETS=adoption`) still includes base chat/workspace/rag routes and tasks.
- Applets represent additional capabilities layered on top of base.

### Adoption slim local run

Use the adoption applet override to run a lighter stack:

```bash
APPLETS=adoption REACT_APP_APPLETS=adoption docker compose \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.modular-single-worker.yml \
  -f docker/docker-compose.applet-adoption.yml \
  up -d --build app celery-worker frontend
```

Optional extended worker services (beat/ingestion/flower) are under profile `extended-workers`.

## Validate manifests

Run strict route coverage validation:

```bash
python scripts/lint_applets.py --enforce-route-coverage
```

## Migration runner

Use the applet-aware migration runner directly:

```bash
python scripts/run_migrations.py --applets adoption
```

Dry-run migration tag resolution:

```bash
python scripts/run_migrations.py --applets adoption --dry-run
```

Selective mode options:

```bash
# Safe mode: always full tree
python scripts/run_migrations.py --applets adoption --mode safe

# Auto mode (default): selective if migration metadata is ready, otherwise fallback to full tree
python scripts/run_migrations.py --applets adoption --mode auto

# Strict selective mode: fail if revisions are not fully tagged
python scripts/run_migrations.py --applets adoption --mode selective
```

Selective execution requires migration revisions to define tags metadata
(`tags = [...]` or `migration_tags = [...]`).

Lint migration tag coverage:

```bash
# Report mode (current baseline)
python scripts/lint_migration_tags.py --enforce-known-tags

# Strict mode
python scripts/lint_migration_tags.py --enforce-known-tags --enforce-complete-tagging
```

## Manifest Files

- `_base.yaml`: core routes required for every deployment.
- `<name>.yaml`: applet-specific routes/tasks/services.
- `profiles/<name>.yaml`: composed applet bundles.

Current applets:
- `adoption`, `ai_console`, `business_intelligence`, `talent`, `data_connections`,
  `content`, `retrieval`, `ops`

## Required Keys

Each applet manifest should define:

- `routes`: route keys from `src/main.py`
- `tasks`: task module names from `src/tasks/` (without `src.tasks.` prefix is allowed)

Optional:

- `services`, `models`, `flows`, `pages`, `migration_tags`

## Validation Rules

- Unknown keys are rejected (strict schema validation).
- Applet manifests must include `applet`.
- Profile manifests (`applets/profiles/*.yaml`) must include `profile` and `applets`.
- Circular profile/app list references are rejected.
- Manifest filename must match declared `applet`/`profile` values.
- `tasks` accepts `src.tasks.<name>` or `<name>` and normalizes to `<name>`.
- `migration_tags` are normalized to lowercase with `_` separators.
