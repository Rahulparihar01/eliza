# Alembic Flatten Runbook

This runbook defines a safe, staged process to flatten Eliza's Alembic history.

## Preconditions

- Migration tags are fully backfilled (already done).
- App startup uses applet-aware migration execution (already done).
- `scripts/lint_migration_tags.py` passes with strict flags.
- `scripts/check_alembic_heads.py` is available for topology checks.

## Safety Goals

- Preserve production schema compatibility.
- Avoid data-destructive migration rewrites.
- Keep rollback options until final cutover.

## Phase 0: Baseline Capture

Run from repo root:

```bash
python scripts/validate_flatten_readiness.py --require-single-head
python scripts/check_alembic_heads.py
python scripts/lint_migration_tags.py --enforce-known-tags --enforce-complete-tagging
alembic current
alembic heads
```

Record outputs in the rollout ticket.

## Phase 1: Freeze Window

- Freeze new Alembic revisions while flatten is in progress.
- Allow feature work, but no schema revisions merged during freeze.

## Phase 2: Create a Baseline Revision

Create a new baseline migration that reflects the current schema state:

```bash
alembic revision -m "flatten baseline" --head heads
```

Edit the new revision:

- Keep it as a schema baseline marker (no-op upgrade/downgrade for existing envs).
- Add `tags: Sequence[str] = [...]` aligned with core/base requirements.

## Phase 3: Staged Validation

In a disposable database:

1. Apply legacy tree to `heads`.
2. Stamp/test baseline flow.
3. Verify app startup and health checks.

Suggested checks:

```bash
python scripts/validate_flatten_readiness.py --applets full adoption
```

## Phase 4: Cutover

- Merge baseline revision with clear release notes.
- Keep legacy revisions temporarily for safe transition window.
- After rollout confidence window, archive legacy migration files in a follow-up change.

## Phase 5: Post-Cutover Guardrails

- Enforce single-head policy in CI:

```bash
python scripts/check_alembic_heads.py --expect-single-head
```

- Keep strict migration-tag linting in CI.

## Rollback

If rollout issues appear:

- Revert to pre-flatten branch/release.
- Stamp back to previous known-safe revision chain.
- Re-run app startup migration flow in `auto` mode as recovery fallback.
