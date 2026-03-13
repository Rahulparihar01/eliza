# AWS SharePoint RAG Pipeline — Fixes & Open Items

Branch: `feature/aws-rag-pipeline` (merged with `origin/dev` on 2026-03-03)

This document catalogs every issue, gap, and required update identified in the
initial implementation of the AWS SharePoint → MWAA → OpenSearch RAG pipeline.

Items are grouped by severity. Each item includes the affected file(s), a
description of the problem, and a recommended fix.

---

## Implementation Progress

### 2026-03-03 — Merge with `origin/dev` + Terraform Split

Merged `origin/dev` into feature branch, resolving 10 conflict files across
Terraform, Python, Docker Compose, and TypeScript. Key merge outcomes:

- **Embeddings service** (`eliza_rag/embeddings.py`): unified Bedrock credentials
  (env var fallbacks + `aws_session_token`), corrected Titan model dimensions,
  preserved sync retry logic (`_invoke_bedrock_embedding`) with exponential
  backoff.
- **Config** (`src/core/config.py`): merged both branches' additions — RAG
  metadata enrichment settings + Bedrock embedding provider selection.
- **RAGFlow routes** (`src/api/routes/ragflow.py`): combined Agent Mesh SSE
  streaming (`import json`) with PDF serving fallback (`KnowledgeBase` import).
- **Frontend** (`RAGFlowConversationView.tsx`): took `origin/dev`'s Agent Mesh
  UI updates (richer `RetrievedChunk` interface, metadata chunk filtering).

**Terraform directory split** — the monolithic `terraform/` directory was split
into two fully independent Terraform projects:

| Directory | Purpose | Files |
|-----------|---------|-------|
| `terraform/platform/` | Full Eliza platform on AWS ECS Fargate | 11 `.tf` files |
| `terraform/rag-pipeline/` | Standalone RAG pipeline (MWAA, S3, OpenSearch, API GW) | 11 `.tf` files + README |

The `rag-pipeline` project is **fully atomic** — it provisions its own VPC
(`10.1.0.0/16`), IAM roles, security groups, and secrets. Zero `remote_state`
dependencies on the platform. It can be copied to another repo for customer
deployments as-is.

### 2026-03-02 — Package Extraction (Phase 1–5)

The team implemented **Fix #1** using a **repo-local Python package** strategy
so RAG ingestion/retrieval can be installed in multiple runtimes (platform app,
MWAA/Airflow, MCP server, and future external repos).

**Phase 1 — Package Scaffold + Module Extraction**

Created `packages/eliza-rag-ingestion/` with namespace `eliza_rag`:
`embeddings.py`, `vector_store.py`, `retrieval.py`, `chat.py`, `chunking.py`,
`document_parser.py`, `metadata_enrichment.py`.

**Phase 2 — Platform-Only Backend Split**

Moved `src/services/rag/pydantic_backend.py` →
`src/services/workspace_rag_backend.py`. Updated all importers.

**Phase 3 — Runtime Import Cutover**

Switched all consumers (`native_rag_service`, `document_parsing` route, DAGs,
MCP server, rag-ingestion service) to `eliza_rag.*`. Removed all `sys.path`
hacks.

**Phase 4 — Build / Dependency Wiring**

Wired `pyproject.toml`, `uv.lock`, and all Dockerfiles to install from the
local package path.

**Phase 5 — Legacy Module Removal**

Deleted `src/services/rag/` directory. Platform backend now at
`src/services/workspace_rag_backend.py`.

### Next Planned Phase

- **Phase 6:** End-to-end smoke validation across platform + Airflow + MCP.

---

## Critical — Pipeline Will Not Run

### 1. ~~`document_pipeline` cannot import RAG services~~ RESOLVED

**Status:** Fixed (Phase 1–5, 2026-03-02)

**Resolution:** Option C — extracted `src/services/rag/` into a local Python
package `packages/eliza-rag-ingestion/` (namespace `eliza_rag`). All
Dockerfiles (`Dockerfile`, `Dockerfile.airflow`, `terraform/rag-pipeline/mcp_server/Dockerfile`,
`services/rag-ingestion/Dockerfile`) install the package. DAGs, MCP server,
and platform all import from `eliza_rag.*`. No more `sys.path` hacks.

**Remaining:** Phase 6 end-to-end smoke tests to confirm the full chain works
at runtime (platform → Airflow → MCP).

---

### 2. ~~`sharepoint_sync` does not actually trigger `document_pipeline`~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:** Replaced the `trigger_processing` task with:
- `collect_uploaded_keys` — flattens all uploaded S3 keys into a summary dict.
- `has_new_files` — `@task.short_circuit()` that skips triggering when no files were synced.
- `TriggerDagRunOperator` — triggers `document_pipeline` with the summary dict as `conf`, `wait_for_completion=False`.

The DAG flow is now: `list_drives → fetch_delta → download_to_s3 → collect_uploaded_keys → has_new_files → trigger_document_pipeline`.

---

### 3. ~~SharePoint credentials not wired to MWAA in Terraform~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:** Three parts completed:
1. `terraform/rag-pipeline/secrets.tf` — Secrets Manager secret for SharePoint
   credentials (`tenant_id`, `client_id`, `client_secret`, `site_id`).
2. `terraform/rag-pipeline/variables.tf` — all four SharePoint variables
   declared (including `site_id` which was previously missing).
3. `terraform/rag-pipeline/mwaa.tf` — Airflow Secrets Backend configured via
   `airflow_configuration_options` to read connections and variables from
   Secrets Manager under `${var.project}/${var.env}/airflow/`.

The MWAA execution IAM role already has `secretsmanager:GetSecretValue` scoped
to `${var.project}/*`.

**Note:** Actual SharePoint credential values not yet available — will be
supplied via `terraform.tfvars` when ready.

---

### 4. ~~OAuth token caching & expiry not handled~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:** Added `_token_expiry` tracking to `SharePointClient.__init__`.
`_ensure_token()` now checks `time.time() < self._token_expiry - 60` before
reusing the cached token. On refresh, `expires_in` from the OAuth response is
used to set the expiry timestamp. Tokens are refreshed 60 seconds before
actual expiry to avoid edge-case 401s during in-flight requests.

---

## High — Correctness / Data Integrity

### 5. ~~`embed_and_index` calls async `embed_fn` from sync `asyncio.run`~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:**
- `dags/document_pipeline.py` now uses an async wrapper `_embed_batch` that
  runs the synchronous `EmbeddingService._invoke_bedrock_embedding` in executor
  workers for each text.
- `EmbeddingLoadBalancer.embed_batched(...)` now receives this wrapper instead
  of `EmbeddingService.embed_texts`, eliminating the problematic nested
  `asyncio.run` + `get_event_loop` interaction path in Airflow subprocesses.

---

### 6. ~~No deduplication or idempotency in `download_to_s3`~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:**
- Added `head_object` check in `dags/sharepoint_sync.py` before download/upload.
- Compares existing S3 metadata `sharepoint_etag` with incoming SharePoint
  `etag`; unchanged files are skipped.
- Upload metadata now stores `sharepoint_etag`, enabling idempotent retries.

---

### 7. ~~`download_bytes` reads only first 1 KB for classification~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:**
- Added `download_head_bytes(bucket, key, size=1024)` to `dags/common/s3_utils.py`
  using S3 `Range` reads.
- `classify_file` now uses this helper for unknown extensions instead of loading
  entire objects into memory.

---

### 8. ~~Preprocessors download files a second time~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:**
- Classification now avoids downloading bytes for known extensions
  (`EXTENSION_MAP` fast path) and only uses 1 KB range reads for unknown types.
- Preprocessors remain the only full-content readers. This removes the prior
  "full download for classify + full download for preprocess" behavior.

---

### 9. ~~OpenSearch network policy blocks external access~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:** Added full ECS infrastructure to `terraform/rag-pipeline/`:
- `ecr.tf` — ECR repository for MCP server image (with lifecycle policy).
- `ecs.tf` — ECS cluster, CloudWatch log group, Cloud Map service discovery
  (`mcp-server.${project}.local`), Fargate task definition with health check,
  and ECS service. The MCP server runs in private subnets with the `ecs`
  security group, registered with Cloud Map so the API Gateway VPC Link
  (already configured) can route to it.
- `secrets.tf` — MCP API key stored in Secrets Manager, injected as a secret
  into the ECS task.
- `variables.tf` — `mcp_api_key`, `mcp_server_image_tag`, `mcp_server_cpu`,
  `mcp_server_memory`, `mcp_server_desired_count`.
- `outputs.tf` — ECR repo URL, ECS cluster name, Cloud Map namespace.

---

## Medium — Operational / Configuration

### 10. Hardcoded Postgres credentials in Terraform ECS definitions

**Files:** `terraform/platform/ecs.tf`, `terraform/platform/secrets.tf`

**Problem:**
The Postgres ECS task definition and the Secrets Manager secret both contain
`"POSTGRES_PASSWORD": "password"`. Production deployments should not use
hardcoded credentials.

**Fix:**
Use a generated random password stored in Secrets Manager and reference it
from the ECS task definition.

---

### 11. `Dockerfile.airflow` does not copy DAGs

**Files:** `docker/Dockerfile.airflow`

**Problem:**
The Dockerfile only installs Python dependencies. For MWAA this is fine (DAGs
are loaded from S3), but for local Docker Compose the DAGs are mounted via
volume. If someone uses this image standalone (for example, CI DAG validation),
it contains no DAG files.

**Fix:**
Add optional `COPY dags/ /opt/airflow/dags/` in the image build. Compose mounts
can continue to override it locally.

---

### 12. ~~Missing `requirements.txt` for MWAA~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution (rag-pipeline scoped):**
- Added `terraform/rag-pipeline/files/requirements-airflow.txt`.
- Added `aws_s3_object.airflow_requirements` in `terraform/rag-pipeline/mwaa.tf`.
- Added `requirements_s3_path` and `requirements_s3_object_version` to MWAA.
- Added `plugins_s3_path` support in `mwaa.tf` (via `mwaa_plugins_s3_path` variable).
- Requirements now include:
  - `--find-links /usr/local/airflow/plugins`
  - `eliza-rag-ingestion`
- Added script `terraform/rag-pipeline/scripts/deploy_mwaa_assets.sh` that:
  - builds `eliza-rag-ingestion` wheel
  - creates `plugins.zip` with the wheel
  - uploads DAGs, requirements, and plugins assets to the MWAA DAG bucket

---

### 13. ~~MCP server has no health check or authentication~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:** Rewrote the SSE entry point in `terraform/rag-pipeline/mcp_server/server.py`
to use a custom Starlette app instead of `mcp.run()`:
- `/health` endpoint returns `{"status": "healthy"}` — used by ECS health
  checks and the Docker `HEALTHCHECK` instruction.
- `APIKeyAuthMiddleware` — checks `Authorization: Bearer <key>` or `X-API-Key`
  header on all non-health requests. Configured via `MCP_API_KEY` env var.
  When the env var is empty, auth is disabled (dev mode).
- `config.py` — added `api_key`, `host`, `port` fields.
- `requirements.txt` — added `uvicorn`, `starlette`.
- `Dockerfile` — set `MCP_TRANSPORT=sse` default, added `HEALTHCHECK`.

MCP server moved from repo root `mcp_server/` to `terraform/rag-pipeline/mcp_server/`
so it's co-located with the RAG pipeline infrastructure and extracts atomically.

Rate limiting is handled at the API Gateway layer via WAF (already configured
in `terraform/rag-pipeline/api_gateway.tf` — 1000 req/5min/IP).

---

### 14. ~~`embedding_load_balancer` uses stale event loop reference~~ RESOLVED

**Status:** Fixed (2026-03-03)

**Resolution:**
- `dags/common/embedding_load_balancer.py` now initializes semaphore lazily via
  `_get_semaphore()` inside async execution context.
- This prevents cross-loop semaphore binding when the balancer is constructed
  before `asyncio.run()` creates the active loop.

---

### 15. ~~No MWAA DAG deployment mechanism~~ RESOLVED

**Status:** Fixed (2026-03-03, rag-pipeline scoped)

**Resolution:**
- Added script `terraform/rag-pipeline/scripts/deploy_mwaa_assets.sh`.
- Script performs:
  - `aws s3 sync dags/ s3://<bucket>/dags/ --delete`
  - uploads `requirements/requirements.txt`
  - uploads package wheel + `plugins/plugins.zip`
- This provides a repeatable deploy path without touching root-level workflows.

---

## Low — Code Quality / DX

### 16. Inconsistent `requests` import pattern in `sharepoint_client.py`

**Files:** `dags/common/sharepoint_client.py`

**Problem:**
`requests` is imported inside each method (`list_drives`, `delta`,
`download_file`, `_ensure_token`) via `import requests`. This is presumably
to keep the module importable without `requests` installed, but `requests` is
in `requirements-airflow.txt` and will always be available.

**Fix:**
Move `import requests` to the top of the file for clarity.

---

### 17. `.env.template` missing MCP server variables

**Files:** `.env.template`

**Problem:**
The template includes SharePoint, Airflow, and Bedrock variables, but is
missing MCP server configuration variables (OpenSearch host/region, Bedrock
model for the MCP server, SSE port, etc.).

**Fix:**
Add:

```bash
# =============================================================================
# MCP Server Configuration
# =============================================================================
MCP_TRANSPORT=stdio
MCP_SSE_PORT=8888
MCP_OPENSEARCH_HOST=
MCP_OPENSEARCH_REGION=us-east-1
MCP_OPENSEARCH_INDEX_PREFIX=rag_domains
MCP_BEDROCK_MODEL=amazon.titan-embed-text-v2:0
MCP_BEDROCK_REGION=us-east-1
```

---

### 18. No unit tests for DAGs or MCP server

**Files:** (none exist)

**Problem:**
There are no tests for DAG import validation, preprocessor logic, the
SharePoint client, or the MCP server tools/agents.

**Fix:**
At minimum add:
- `tests/test_dag_imports.py` — Verify all DAGs parse without errors.
- `tests/test_document_classifier.py` — Test file classification logic.
- `tests/test_sharepoint_client.py` — Mock Graph API responses.
- `tests/test_mcp_tools.py` — Test search tools with mocked vector store.

---

### 19. `document_pipeline` processes all categories even if empty

**Files:** `dags/document_pipeline.py` (lines 231–240)

**Problem:**
All four preprocessor tasks run unconditionally even when their category has
zero files. This creates unnecessary Airflow task instances and clutters the
DAG run view.

**Fix:**
Use `ShortCircuitOperator` or Airflow's branching to skip empty categories:

```python
@task.short_circuit()
def has_unstructured(routed):
    return bool(routed.get(DocCategory.UNSTRUCTURED.value))
```

---

### 20. `docker-compose.yml` Airflow services share Postgres with the platform

**Files:** `docker/docker-compose.yml` (lines 1019–1067)

**Problem:**
The `airflow-init` service creates a database named `airflow` inside the same
Postgres instance used by the platform (`ai_enablement`). While this works for
local dev, it couples Airflow's metadata DB to the platform DB. If someone runs
`docker-compose down -v`, all Airflow metadata (delta links, DAG history) is
lost along with platform data.

**Fix (optional for local dev):**
Consider adding a separate Postgres service for Airflow if isolation is
desired, or document that `docker-compose down -v` destroys Airflow state.

---

## Summary Table

| # | Severity | Component | Issue | Status |
|---|----------|-----------|-------|--------|
| 1 | Critical | DAG / Docker | `embed_and_index` can't import `src/services/rag` | **RESOLVED** — `eliza-rag-ingestion` package |
| 2 | Critical | DAG | `sharepoint_sync` never triggers `document_pipeline` | **RESOLVED** — `TriggerDagRunOperator` + short-circuit gate |
| 3 | Critical | Terraform | SharePoint creds not in Secrets Manager / MWAA | **RESOLVED** — secret + Secrets Backend configured |
| 4 | Critical | DAG | OAuth token never refreshed (expires after ~60 min) | **RESOLVED** — expiry tracking + 60s buffer |
| 5 | High | DAG | Nested `asyncio.run` + `get_event_loop()` conflict | **RESOLVED** — sync Bedrock invoke path via executor wrapper |
| 6 | High | DAG | No dedup — retries re-upload same files | **RESOLVED** — SharePoint etag metadata check + skip |
| 7 | High | DAG | Downloads full file just to read 1 KB header | **RESOLVED** — S3 range read helper (`download_head_bytes`) |
| 8 | High | DAG | Same file downloaded twice (classify + preprocess) | **RESOLVED** — classify fast path + head-only reads |
| 9 | High | Terraform | MCP server has no ECS service definition | **RESOLVED** — ECS cluster, task, service, ECR, Cloud Map |
| 10 | Medium | Terraform | Hardcoded Postgres password in ECS + Secrets Manager | Open — out of current rag-pipeline scope |
| 11 | Medium | Docker | `Dockerfile.airflow` doesn't copy DAGs | Open — out of current rag-pipeline scope |
| 12 | Medium | Terraform | MWAA missing `requirements_s3_path` | **RESOLVED** — requirements + plugins wheel install path configured |
| 13 | Medium | MCP | No auth or health check on MCP server | **RESOLVED** — `/health` endpoint + API key middleware |
| 14 | Medium | DAG | Semaphore bound to wrong event loop | **RESOLVED** — lazy semaphore initialization |
| 15 | Medium | Terraform | No CI/CD mechanism to deploy DAGs to S3 | **RESOLVED** — rag-pipeline deploy script for DAG/assets upload |
| 16 | Low | DAG | Redundant per-method `import requests` | Open |
| 17 | Low | Config | `.env.template` missing MCP server vars | Open |
| 18 | Low | Testing | No unit tests for DAGs or MCP server | Open |
| 19 | Low | DAG | Empty categories still run preprocessor tasks | Open |
| 20 | Low | Docker | Airflow and platform share same Postgres instance | Open |
