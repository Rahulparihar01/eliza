# AWS-Native Knowledge RAG Pipeline

## Product Requirements Document (PRD)

**Client:** Falfarius Management Partners  
**Status:** Active — Planning Phase  
**Last Updated:** 2026-02-23

---

## 1. Objective

Build a scalable, production-ready ingestion pipeline that mirrors **SharePoint** data into **AWS S3**, processes/classifies documents using **Managed Airflow (MWAA)**, and generates embeddings for a **RAG (Retrieval-Augmented Generation)** system using **AWS Bedrock**. The solution must be deployable both within the Eliza platform and as a standalone AWS-native stack.

---

## 2. Target Scope

- **Initial Client:** Falfarius Management Partners (~2TB of data).
- **Integration:** Must be "AWS Native" to satisfy PE/Institutional requirements.
- **Client Interface:** ChatGPT Enterprise (client already has it). Platform chat UI available as an alternative.

---

## 3. Functional Requirements

### A. Data Ingestion & Storage

- **SharePoint Connector:** Secure connection via Microsoft Graph API to pull data into AWS.
- **S3 Staging (The "Mirror"):**
  - "Raw" landing zone in S3 mirroring the SharePoint directory structure.
  - Incremental syncing (CDC) for version control and updates.
  - URI concatenation with metadata tags for file tracking.

### B. Orchestration (Managed Airflow)

- **Terraformed MWAA:** Fully terraformed Managed Airflow environment.
- **The DAG Pipeline:**
  - **Document Classifier:** Fargate task to identify file types and metadata.
  - **Router:** Route by doc metadata to type-specific post-processors.
  - **Post-Processors (3 paths):**
    - Unstructured text: NLP cleaning + ranking
    - Structured data: Schema validation + normalization
    - PDF / Scanned docs: OCR + text extraction

### C. Embedding & Vector Retrieval

- **AWS Bedrock Integration:** Bedrock Titan embeddings at scale.
- **Load Balancer / Fuse Box:** Fan out embedding requests, handle Bedrock rate limits.
- **Vector Store:** OpenSearch Serverless (Terraform-provisioned) or PGVector PostgreSQL.

### D. Retrieval & Response

- **MCP Server — Tools:** Metadata filter, vector search, keyword search, doc fetcher.
- **MCP Server — Agents:** Hybrid retriever (RRF scoring), reranker, response formatter with inline citations, query planner.
- **Citation Pipeline:** Retrieve → rerank → generate answer → extract/renumber citations → append sources.
- **Client Interface:** MCP connection (SSE / Streamable HTTP) → ChatGPT Enterprise.
- **API Layer:** API Gateway with rate limiting + WAF, OAuth 2.0 / JWT auth.

---

## 4. Constraints

- **AWS Native:** The end product must stand alone as a "pure AWS stack." Avoid heavy dependencies on the internal platform if the client demands a 100% native hand-off.
- **Scaling for 2TB:** Pipeline needs to support massively parallelized workers. Airflow is preferred over Celery for enterprise-scale orchestration.
- **Preprocessing Quality:** PowerPoints and Tables must be pre-processed with type-specific logic *before* embedding to ensure retrieval quality. Don't just dump raw text.
- **One RAG Pipeline:** Maintain a single pipeline regardless of where it deploys. No forking the codebase.
- **Terraform First:** Everything must be `terraform apply` ready.
- **Testing Environment:** Use the dedicated `rw` area only. Do not test in production client accounts.

---

## 5. What Already Exists in the Platform

### RAG Core (`src/services/rag/`)

| Component | Status | Details |
|-----------|--------|---------|
| Document parser | **Done** | `DocumentParser` — naive, docling, VLM, GPT-4o parsers. Handles PDF, DOCX, TXT, HTML, Markdown |
| Chunking | **Done** | `ChunkingService` — semantic, fixed, sentence strategies. Configurable chunk size + overlap |
| Embeddings | **Done** | `EmbeddingService` — OpenAI, local (sentence-transformers), **Bedrock Titan** (Ryan) |
| Vector store | **Done** | `VectorStore` — AWS OpenSearch Serverless (SigV4), local Elasticsearch |
| Retrieval | **Done** | `RetrievalService` — semantic search, keyword search, **hybrid with RRF scoring** |

### Citation Pipeline (`src/services/fasb_service.py`)

| Component | Status | Details |
|-----------|--------|---------|
| Citation builder | **Done** | `FASBService._build_citation()` — structured citations with source, doc, pages, chunk, section |
| Reranking | **Done** | LLM-based reranking of retrieved contexts (configurable `rerank_keep`) |
| Inline citations in answers | **Done** | Numbered `[1]`, `[2]` references with sources list appended |
| Citation validation | **Done** | `CitationValidationService` — GPT-4o vision validation against PDF pages |
| API exposure | **Done** | `POST /ragflow/chat` and `GET /ragflow/retrieve` return full citation metadata |

### MCP Server

| Component | Status | Details |
|-----------|--------|---------|
| MCP server implementation | **Done** | Talent Intelligence MCP server (`Eliza-platform-talent-mcp/`) using FastMCP |
| MCP integration guide | **Done** | `docs/api/MCP_INTEGRATION_GUIDE.md` — architecture, tool definitions, auth patterns |
| Workspace/applet MCP exposure | **Not yet** | Need to expose workspaces and applets as MCP servers |
| Standalone MCP (no platform) | **Not yet** | Need a version that works outside the platform for AWS-native deployments |

### Multi-KB Retrieval

| Component | Status | Details |
|-----------|--------|---------|
| Multi-KB data model | **Done** | Workspaces contain multiple knowledge bases (1:N) |
| Multi-KB filtering in retrieval | **Done** | `knowledge_base_ids` parameter throughout all retrieval services and vector store |
| KB access control | **Done** | `KnowledgeBaseAccessService` — per-user, per-workspace KB permissions |
| Query planner (general) | **Done** | `src/flows/retrieval_flow.py` — Planner → Executor → Evaluator → Synthesizer |
| Multi-KB query planning | **In progress** | Per-KB query decomposition on another branch |

### Bedrock & AWS Integration (Ryan's Branch)

| Component | Status | Details |
|-----------|--------|---------|
| Bedrock Titan embeddings | **Done** | `EmbeddingProvider.BEDROCK`, IAM + explicit credentials, Titan v1 + v2 |
| OpenSearch Serverless | **Done** | SigV4 auth, Terraform-aligned index naming |
| Bedrock text generation | **Done** | Claude models via `BedrockProvider`, IAM role support |
| Bedrock model discovery | **Done** | `BedrockDiscoveryService` |
| Smoke tests | **Done** | `scripts/reference_architecture_bedrock_test.py` |

### Full Platform Terraform (Ryan's Branch — `terraform/`)

Ryan Terraformed the **entire Eliza platform** for AWS ECS Fargate (added 2026-02-22):

**Infrastructure:** VPC (2 AZs, public/private subnets, NAT), ALB (path-based routing), EFS (encrypted persistent volumes), Cloud Map service discovery (`*.eliza.local`), Secrets Manager, IAM roles.

**All services as ECS Fargate tasks:** Postgres, Redis, Neo4j, Elasticsearch, Logstash, App (FastAPI), Celery Worker, Celery Beat, Celery Ingestion Worker, Flower, Frontend.

The entire platform is `terraform apply`-able on AWS.

---

## 6. What Needs to Be Built

### Ingestion Layer (Net-New)

| Component | Description |
|-----------|-------------|
| **MWAA Terraform module** | Add to Ryan's `terraform/` — uses same VPC/subnets, IAM patterns, security groups |
| **SharePoint → S3 sync DAG** | Airflow DAG using Microsoft Graph API for incremental mirroring to S3 |
| **Document classifier task** | Fargate task to classify files and route by doc metadata |
| **Unstructured text preprocessor** | NLP cleaning + ranking for unstructured docs |
| **Structured data preprocessor** | Schema validation + normalization for Excel/CSV |
| **PPT preprocessor** | Slide-aware extraction: one chunk per slide + speaker notes |
| **PDF/scanned preprocessor** | Enhancement to existing OCR parsers for scale |
| **Embedding load balancer** | Fan out requests, handle Bedrock rate limits at 2TB scale |

### Retrieval Layer (Adapt Existing)

| Component | What Exists | What's Needed |
|-----------|-------------|---------------|
| **MCP tools** (metadata filter, vector search, keyword search, doc fetcher) | VectorStore has search + keyword_search; FASB has doc fetching | Wrap as MCP tools; create standalone version without platform |
| **Hybrid retriever with RRF** | `RetrievalService.hybrid_retrieve()` already does RRF | Expose via MCP agent |
| **Reranker** | FASB service has LLM reranking | Extract to standalone; add Fargate on-demand option |
| **Citation builder + response formatter** | Full pipeline in `FASBService` (build → rerank → cite → format) | Extract to reusable service; expose via MCP |
| **Query planner** | General planner in `retrieval_flow.py`; multi-KB planning in progress | Complete multi-KB planning; expose via MCP |

### Platform Integration

| Component | What's Needed |
|-----------|---------------|
| **Workspace MCP server** | Expose workspaces/applets as MCP servers so ChatGPT Enterprise (or any MCP client) can connect |
| **Standalone MCP server** | Version that works without the platform — for AWS-native deployments |
| **RAG core packaging** | Ensure `src/services/rag/` + citation + retrieval can be imported standalone |
| **API Gateway + WAF** | AWS API Gateway in front of standalone deployment (platform already has FastAPI rate limiting + JWT auth) |

---

## 7. Airflow Deployment Strategy: Open-Source + MWAA

### Approach

Use **open-source Apache Airflow** (self-hosted, in docker-compose) for the platform, and **MWAA** (AWS Managed Workflows for Apache Airflow) for client deployments. DAG files are identical — just Python files. The only difference is who operates the infrastructure.

### Platform (Self-Hosted)

Added to existing docker-compose: `airflow-webserver`, `airflow-scheduler`, `airflow-worker(s)`, `airflow-init`. Points at existing Postgres (separate `airflow` database) and existing Redis. Three new containers, no new infrastructure.

### Client Deployments (MWAA via Terraform)

Add `mwaa.tf` to Ryan's existing `terraform/` — reuses same VPC, subnets, IAM patterns, security groups. MWAA handles worker autoscaling for 2TB+ workloads.

### Same DAGs, Different Runtime

```
Development & Platform                Client AWS Account
┌──────────────────────────┐          ┌──────────────────────────┐
│ Self-hosted Airflow      │          │ MWAA (managed)           │
│ (docker-compose)         │          │ (Terraform-provisioned)  │
│                          │          │                          │
│ DAGs: dags/              │  same    │ DAGs: s3://dag-bucket/   │
│  ├─ sharepoint_sync.py   │  files   │  ├─ sharepoint_sync.py   │
│  ├─ document_process.py  │ ══════>  │  ├─ document_process.py  │
│  └─ ...                  │          │  └─ ...                  │
└──────────────────────────┘          └──────────────────────────┘
```

### Estimated Lift for Self-Hosted Setup

| Task | Effort |
|------|--------|
| Add Airflow to docker-compose | ~half a day |
| Configure connections | ~half a day |
| DAGs loading + webserver accessible | ~half a day |
| First real DAG | 1-2 days |
| **Total to working V0** | **~2-3 days** |

---

## 8. Reference Architecture — Component Mapping

Based on the full MWAA reference architecture diagram.

### Ingestion & Classification

| Component | Platform Status | Notes |
|---|---|---|
| MWAA Orchestrator | **Not built** | New — `mwaa.tf` + DAGs |
| SharePoint data source | **Not built** | New — Graph API connector |
| S3 Landing Zone | **Infra ready** | Ryan's VPC/IAM; need S3 bucket + sync logic |
| Document Classifier (Fargate) | **Not built** | New — classification task |
| Route by Doc Metadata | **Not built** | New — routing logic |
| Unstructured Text NLP Cleaning | **Partial** | DocumentParser handles basics; need NLP cleaning/ranking |
| Structured Data Schema Validation | **Not built** | New — table/schema-aware processing |
| PDF/Scanned OCR Extraction | **Done** | DocumentParser VLM + GPT-4o parsers |
| Load Balancer → Embedding | **Not built** | New — Bedrock rate limit management |

### Embedding & Storage

| Component | Platform Status | Notes |
|---|---|---|
| Embedding Model (Fargate, scale up/down) | **Done** | Ryan's `EmbeddingService` with Bedrock Titan |
| S3 Processed Docs Store | **Partial** | `ObjectStorageService` exists; need Terraform for processed bucket |
| PGVector PostgreSQL | **Not this store** | We use OpenSearch; PGVector is an option — decision needed |
| Audit Logger | **Partial** | Langfuse integration exists |

### MCP Server — Tools

| Component | Platform Status | Notes |
|---|---|---|
| Metadata Filter Tool | **Exists as code** | Retrieval filtering exists; need MCP tool wrapper |
| Vector Search Tool | **Exists as code** | `VectorStore.search()` exists; need MCP tool wrapper |
| Keyword Search Tool | **Exists as code** | `VectorStore.keyword_search()` exists; need MCP tool wrapper |
| Doc Fetcher Tool | **Exists as code** | FASB doc fetching exists; need MCP tool wrapper |
| Citation Builder Tool | **Done** | `FASBService._build_citation()` — full pipeline |

### MCP Server — Agents

| Component | Platform Status | Notes |
|---|---|---|
| Hybrid Retriever Agent (RRF) | **Done** | `RetrievalService.hybrid_retrieve()` does RRF |
| Reranker (Fargate on-demand) | **Done (LLM-based)** | FASB + RAGFlow services; could add cross-encoder option |
| Response Formatter with inline citations | **Done** | FASB answer pipeline with `[1]`, `[2]` inline citations |
| Query Planner Agent | **In progress** | General planner done; multi-KB planning on another branch |

### API Layer & Client Interface

| Component | Platform Status | Notes |
|---|---|---|
| API Gateway + WAF | **Not built (as AWS service)** | Platform has FastAPI; need AWS API GW for standalone |
| OAuth 2.0 / JWT Auth | **Done** | Platform JWT auth + RBAC |
| MCP Connection (SSE / Streamable HTTP) | **Partial** | Platform has SSE; MCP server exists for Talent; need workspace MCP |
| ChatGPT Enterprise (Client) | **Not our build** | Client uses ChatGPT Enterprise — we provide MCP endpoint |

### Overall: ~60% of the reference architecture exists in platform code. The gap is primarily the ingestion layer and MCP packaging (wrapping existing code as MCP tools/agents).

---

## 9. One-Pager

### Facilitating AWS-Native Tooling Into What We Already Have

**Problem:** Enterprise clients (starting with Falfarius, ~2TB SharePoint) need an AWS-native RAG solution. We need to deliver this without building and maintaining a second pipeline.

**What we already have:**
- **RAG core** — parse, chunk, embed, index (provider-agnostic, works with Bedrock + OpenSearch today)
- **Citation pipeline** — full retrieve → rerank → cite → format with inline references
- **Hybrid retrieval with RRF** — semantic + keyword search with reciprocal rank fusion
- **Reranking** — LLM-based context reranking
- **Query planner** — Planner → Executor → Evaluator → Synthesizer flow
- **MCP server** — working implementation (Talent Intelligence); needs workspace/standalone versions
- **Multi-KB retrieval** — workspace-level retrieval across multiple knowledge bases
- **Bedrock integration** — Titan embeddings + Claude generation (Ryan, done)
- **Full platform Terraform** — entire platform deployable on AWS ECS Fargate (Ryan, done)

**What we're adding:** A new **Airflow ingestion provider** and **MCP packaging** of existing retrieval capabilities.

- The **ingestion provider** handles enterprise-scale data movement (SharePoint) via Airflow with file classification, type-specific preprocessing, and S3 staging.
- The **MCP packaging** wraps our existing retrieval tools (search, citations, reranking) so they're accessible to ChatGPT Enterprise or any MCP client.

**One pipeline, two deployment modes:**

```
            ┌─────────────────────────────┐
            │     INGESTION LAYER         │
            │  (Airflow / MWAA)           │
            │  SharePoint → S3 → Classify │
            │  → Preprocess (PPT/Tables)  │
            └─────────────┬───────────────┘
                          │
            ┌─────────────▼───────────────┐
            │     RAG CORE + RETRIEVAL    │
            │  (same code, both modes)    │
            │  Parse → Chunk → Embed →    │
            │  Index → Retrieve → Cite    │
            └─────────────┬───────────────┘
                          │
            ┌─────────────▼───────────────┐
            │     MCP SERVER              │
            │  Tools: search, filter,     │
            │  fetch, cite                │
            │  Agents: hybrid retriever,  │
            │  reranker, query planner    │
            └─────────────┬───────────────┘
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
       Platform Mode          Standalone AWS Mode
       (our product)          (client's AWS account)
```

---

## 10. Deployment Paths Summary

### Path A — Standalone AWS (No Platform Dependency)

For clients who need a pure AWS stack they own and operate. Uses the platform's RAG core as a Python package but doesn't deploy the platform itself.

```
terraform apply → provisions:
  ├─ MWAA (Airflow)           — orchestration
  ├─ S3                       — document staging + processed storage
  ├─ Bedrock                  — Titan embeddings + Claude generation
  ├─ OpenSearch Serverless    — vector store (or PGVector on RDS)
  ├─ ECS Fargate              — preprocessor tasks + MCP server
  ├─ API Gateway + WAF        — rate limiting, auth
  └─ Secrets Manager          — credentials

Code deployed:
  ├─ Airflow DAGs             — sharepoint_sync, document_process
  ├─ RAG core package         — parse, chunk, embed, index (from platform)
  ├─ Retrieval package        — hybrid search, RRF, reranking, citations (from platform)
  ├─ MCP server               — standalone, exposes tools + agents
  └─ Preprocessors            — PPT, tables, unstructured text, OCR

Client connects via:
  ChatGPT Enterprise → MCP endpoint (SSE/HTTP) → retrieval tools
```

**What needs to happen:**
1. Package `src/services/rag/` + `fasb_service` + `retrieval` as standalone Python package (no platform imports)
2. Build standalone MCP server that uses the package directly (no FastAPI/Celery dependency)
3. Add `mwaa.tf` + `api_gateway.tf` to Terraform
4. Build Airflow DAGs (SharePoint sync, document processing)
5. Build preprocessors (PPT, tables, unstructured NLP)

### Path B — Platform-Integrated (Full Eliza Deployment)

For clients who use our platform, or for our own hosted offering. The Airflow ingestion provider is a new capability alongside existing connectors.

```
terraform apply (Ryan's terraform/) → full Eliza platform on ECS Fargate
  ├─ All existing services    — App, Celery, Postgres, Redis, etc.
  ├─ + MWAA (or self-hosted Airflow) — new ingestion provider
  └─ + Workspace MCP server   — expose workspaces/applets to ChatGPT Enterprise

Everything already built:
  ├─ RAG core                 — embedded in platform
  ├─ Citation pipeline        — FASB service
  ├─ Hybrid retrieval + RRF   — RetrievalService
  ├─ Reranking                — FASB + RAGFlow services
  ├─ Multi-KB retrieval       — workspace-level, access-controlled
  ├─ Query planner            — retrieval_flow.py
  ├─ JWT auth + RBAC          — existing middleware
  └─ Platform UI              — chat interface, workspace management

New additions:
  ├─ Airflow ingestion provider — new connector for enterprise-scale data
  ├─ Workspace MCP server     — expose workspaces as MCP endpoints
  └─ Preprocessors            — PPT, tables (shared with Path A)
```

### Shared Code Between Both Paths

```
shared/
  ├─ src/services/rag/          — parse, chunk, embed, index
  ├─ src/services/fasb_service  — citations, reranking
  ├─ src/services/rag/retrieval — hybrid search, RRF
  ├─ dags/                      — Airflow DAGs (identical files)
  └─ preprocessors/             — PPT, tables, NLP, OCR
```

Both paths use the same RAG core, same DAGs, same preprocessors. Path A packages them standalone; Path B uses them within the platform.

---

## 11. Next Steps

1. **Sync with Ryan:** Confirm Terraform hand-off points. Decide OpenSearch vs. PGVector for standalone path.
2. **RAG core packaging:** Identify and remove platform dependencies from `src/services/rag/`, `fasb_service`, and `retrieval` so they can be imported standalone.
3. **MWAA Terraform:** Add `mwaa.tf` to Ryan's `terraform/`.
4. **Self-hosted Airflow:** Add Airflow to docker-compose for local development.
5. **V0 SharePoint Sync DAG:** Graph API incremental sync to S3.
6. **V0 Document Classifier:** File classification and routing task.
7. **PPT/Table Preprocessors:** Slide-aware and schema-aware extraction.
8. **Workspace MCP Server:** Expose workspaces/applets as MCP endpoints for ChatGPT Enterprise.
9. **Standalone MCP Server:** Version for Path A that doesn't require the platform.
