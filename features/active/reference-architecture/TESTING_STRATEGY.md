# Testing Strategy: Reference Architecture (Bedrock + OpenSearch + RAG)

This document describes how to verify that the reference-architecture integrations (Bedrock embeddings, vector store index naming, Bedrock generation, Native RAG) are working.

---

## 1. Test levels

| Level | What it covers | When to run |
|-------|----------------|-------------|
| **Unit** | Index naming normalization, embedding dimensions, provider enum, config parsing | Every change; no AWS required for naming/embeddings unit tests. |
| **Integration** | Real Bedrock (embeddings/generation), real OpenSearch (if configured) | After deploying or when validating AWS setup. |
| **Smoke / manual** | End-to-end: config → embed → (optional) index → generate | Before release or when “seeing if it’s working.” |

---

## 2. Unit tests (no AWS)

Run from repo root:

```bash
pytest tests/reference_architecture/ -v
```

These tests:

- **Vector store index naming**: `VectorStore._normalize_index_prefix`, `_normalize_index_suffix`, `_get_index_name` produce OpenSearch Serverless–safe names (lowercase, `[a-z0-9_-]`, no leading `_`/`-`, max 255 chars).
- **Embeddings**: `EmbeddingProvider` enum, `EmbeddingService.MODEL_DIMENSIONS` for Titan models, `dimensions` property for Bedrock model names.
- **Bedrock config**: Optional `base_url` in create/update models and that it is stored/returned.

No credentials or network required for the naming and dimension tests.

---

## 3. Smoke / manual checks (see if it’s working)

Use these to confirm behaviour with your real environment (Bedrock API, optional OpenSearch).

### 3.1 Bedrock Titan embeddings

1. **Set env (or use IAM):**
   - `RAG_EMBEDDING_PROVIDER=bedrock`
   - `RAGFLOW_DEFAULT_EMBEDDING_MODEL=amazon.titan-embed-text-v1` (or `amazon.titan-embed-text-v2:0`)
   - `RAG_BEDROCK_EMBEDDING_REGION=us-east-1` (or your region)
   - If not using IAM: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (and optional `AWS_SESSION_TOKEN`).

2. **Run the smoke script (embeddings only):**
   ```bash
   python scripts/reference_architecture_smoke_test.py --embed
   ```
   This uses `EmbeddingService(provider=BEDROCK, ...)` and calls `embed_texts(["Hello world"])`. Success = no exception and a 1024-dim vector (Titan).

3. **Or call the app (if you use Native RAG behind an API):**  
   Trigger a RAG path that uses embeddings (e.g. ingest or search). Check logs for Bedrock embedding calls and no errors.

### 3.2 Vector store index naming

1. **Set env (optional, to match Terraform):**
   - `RAG_OPENSEARCH_INDEX_PREFIX=eliza_rag_dev` (or your prefix)
   - `RAG_OPENSEARCH_HOST=<collection-endpoint>` and `RAG_OPENSEARCH_REGION` if you want to hit real OpenSearch.

2. **Unit test only (no OpenSearch needed):**
   ```bash
   pytest tests/reference_architecture/test_vector_store_index_naming.py -v
   ```
   Confirms that whatever `domain_id` and prefix you use, index names are normalized and safe.

3. **With real OpenSearch:**  
   Run the app and create a RAG domain / index; then check in OpenSearch that the index name matches the normalized form (e.g. `eliza_rag_dev_<domain_id>`).

### 3.3 Bedrock generation (Bedrock service / provider)

1. **Create a Bedrock config (IAM role):**
   - Call `POST /v1/bedrock/configurations` with:
     - `auth_method: "iam_role"`
     - `aws_region: "us-east-1"` (or your region)
     - No API keys; optional `base_url` if using a VPC endpoint.
   - Or use API keys: `auth_method: "api_keys"`, `aws_access_key_id`, `aws_secret_access_key`.

2. **Test connection:**
   - `POST /v1/bedrock/configurations/{config_id}/test` (or your test endpoint).
   - Expect success and healthy status.

3. **Use for generation:**  
   Trigger any flow that uses the Bedrock provider (e.g. chat, RAG answer). Check logs and response for successful Bedrock calls.

### 3.4 Native RAG with Bedrock end-to-end

1. **Env:**
   - `RAG_EMBEDDING_PROVIDER=bedrock`
   - `RAGFLOW_DEFAULT_EMBEDDING_MODEL=amazon.titan-embed-text-v1`
   - `RAG_BEDROCK_EMBEDDING_REGION=us-east-1`
   - If using OpenSearch: `RAG_OPENSEARCH_HOST`, `RAG_OPENSEARCH_REGION`, `RAG_OPENSEARCH_INDEX_PREFIX` (and credentials via IAM or env).

2. **Run full smoke (embed + optional generate):**
   ```bash
   python scripts/reference_architecture_smoke_test.py --embed [--generate]
   ```
   `--embed`: Bedrock Titan embeddings only.  
   `--generate`: Also exercises Bedrock generation (requires a Bedrock config in DB and a model id; see script help).

3. **In-app:**  
   Create a knowledge base, ingest a document (so it’s embedded with Titan and indexed), then run a RAG query. Confirm answers and (if applicable) that the index name in OpenSearch matches the naming convention.

---

## 4. Integration tests (optional, with AWS)

- **Bedrock embeddings:** Run `scripts/reference_architecture_smoke_test.py --embed` with real AWS credentials (or IAM). CI can run this only when e.g. `RUN_BEDROCK_TESTS=1` and credentials are present.
- **Bedrock generation:** Same script with `--generate` and a valid config id, or an API test that creates a config and calls the test endpoint.
- **OpenSearch:** Integration tests that create an index, index documents, and search (e.g. in a test collection) can be gated on `RAG_OPENSEARCH_HOST` and credentials.

---

## 5. Quick reference: env vars

| Env var | Purpose |
|---------|--------|
| `RAG_EMBEDDING_PROVIDER` | `openai` \| `local` \| `bedrock` |
| `RAGFLOW_DEFAULT_EMBEDDING_MODEL` | e.g. `amazon.titan-embed-text-v1` for Bedrock |
| `RAG_BEDROCK_EMBEDDING_REGION` | AWS region for Titan |
| `RAG_OPENSEARCH_INDEX_PREFIX` | Index prefix (Terraform-aligned) |
| `RAG_OPENSEARCH_HOST` | AOSS collection endpoint (optional) |
| `RAG_OPENSEARCH_REGION` | AOSS region |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Optional; omit to use IAM |

---

## 6. Success criteria

- **Unit:** All tests in `tests/reference_architecture/` pass.
- **Smoke:** `reference_architecture_smoke_test.py --embed` succeeds with Bedrock env (or IAM).
- **Generation:** Bedrock config test endpoint returns success; a generation path (e.g. RAG answer) completes using Bedrock.
- **Naming:** Index names in OpenSearch (if used) match normalized `{prefix}_{domain_id}` and are AOSS-safe.
