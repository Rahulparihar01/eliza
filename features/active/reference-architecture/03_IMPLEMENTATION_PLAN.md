# Implementation Plan: Reference Architecture (AWS Bedrock + Terraform)

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Ready |
| **Last Updated** | 2025-02-17 |
| **PRD Reference** | [ReferenceArchitecture_PRD.md](../../../ReferenceArchitecture_PRD.md) |
| **Estimated Total Time** | 8–10 weeks (aligned with PRD Phase 1–4) |

---

## Table of Contents

1. [Scope & Objectives](#1-scope--objectives)
2. [Current State vs. Target State](#2-current-state-vs-target-state) — incl. [§2.3 Where RAG services are available](#23-where-rag-services-are-available-platform-touchpoints)
3. [AWS + Bedrock + Terraform Design](#3-aws--bedrock--terraform-design)
4. [Demo Data & Use-Case Strategy](#4-demo-data--use-case-strategy)
5. [Implementation Phases (PRD-Aligned)](#5-implementation-phases-prd-aligned)
6. [Terraform Module Layout](#6-terraform-module-layout)
7. [Integration Points with Eliza Platform](#7-integration-points-with-eliza-platform)
8. [Prerequisites & Dependencies](#8-prerequisites--dependencies)
9. [Success Criteria & Progress Tracking](#9-success-criteria--progress-tracking)

---

## 1. Scope & Objectives

### 1.1 In Scope

- **System features** from Reference Architecture PRD (§2):
  - **2.1** Bedrock-based RAG: document ingestion, chunking, embedding, retrieval; prompt augmentation; model abstraction.
  - **2.2** Vector search & knowledge retrieval: semantic/hybrid search; managed/self-hosted vector options; index lifecycle and re-embedding.
  - **2.3** IaC standardization: Terraform templates for secure GenAI infra; network isolation, private connectivity, least-privilege IAM; multi-environment patterns.
  - **2.4** Runtime reliability & human-in-the-loop: centralized error handling and retry; circuit breakers and fallback model routing; human review and escalation workflows.
  - **2.5** Safety, observability & guardrails: prompt tracing and versioning; audit logging of AI interactions; red-team scenarios and policy-based content filtering.

- **Demo**: Representative data and use cases for large-scale organizations—multiple file types (PDF, Excel, presentations, databases) and business domains (HR, Payroll, IT, Sales)—to validate the architecture end-to-end.

- **Design focus**: AWS-only, Bedrock-centric, Terraform for IaC. This plan is **implementation plan only**; no application code changes are specified here.

### 1.2 Out of Scope (This Plan)

- Implementation of application code (FastAPI, Celery, frontend); only where the plan calls out “integration points” and “touchpoints” for future work.
- Non-AWS vector stores or non-Bedrock LLM providers as primary path (existing platform support can remain; reference architecture path is AWS/Bedrock).
- Detailed technical spec for each component (to be done in a separate 02_TECHNICAL_SPEC.md if needed).

---

## 2. Current State vs. Target State

### 2.1 Current State (Eliza Platform)

| Area | Current | Notes |
|------|---------|--------|
| **RAG** | Native RAG service: docling/VLM/GPT-4o parsing, configurable embeddings (OpenAI/local/Bedrock Titan), Elasticsearch/OpenSearch vector store, LiteLLM chat | `src/services/rag/`, `src/services/native_rag_service.py` |
| **Knowledge-base extract** | Document parsing only: naive, docling, VLM (hosted), or GPT-4o vision; no Bedrock-based extract path yet | `src/services/rag/document_parser.py`, `NativeRAGService._process_document` |
| **Vector** | FAISS + Elasticsearch/OpenSearch; company-scoped indices | `src/services/vector_service.py`, `src/services/rag/vector_store.py` |
| **Bedrock** | Bedrock as inference provider (config, discovery, invoke); Bedrock Titan already supported for RAG embeddings | `src/services/bedrock_service.py`, `src/api/routes/bedrock.py`, `src/services/rag/embeddings.py` |
| **Embeddings** | OpenAI, sentence-transformers (local), and Bedrock Titan in RAG path via `RAG_EMBEDDING_PROVIDER=bedrock` | `src/services/rag/embeddings.py`, `native_rag_service._init_components` |
| **IaC** | None | No Terraform or CloudFormation in repo |
| **Observability** | Langfuse, CloudWatch (per existing docs) | Not fully aligned to PRD “audit logging of all AI interactions” |
| **Guardrails** | Not standardized | No red-team or policy-based content filtering framework |

### 2.2 Target State (Reference Architecture)

- **RAG**: Bedrock as primary for both embeddings (e.g. Titan) and generation (Claude); ingestion/chunking/retrieval patterns standardized and documentable as “blueprints.”
- **Vector**: Managed vector store option (e.g. OpenSearch Serverless or Amazon OpenSearch with k-NN) provisioned via Terraform; index lifecycle and re-embedding strategy documented and, where applicable, automated.
- **IaC**: Terraform modules for VPC, Bedrock access, OpenSearch/vector store, S3 document storage, IAM, optional private connectivity (e.g. VPC endpoints), and multi-environment (dev/stage/prod) layout.
- **Runtime**: Centralized error handling, retries, circuit breakers, and fallback model routing; human-in-the-loop workflows (e.g. escalation queues, review UI contract).
- **Safety & observability**: Prompt versioning and tracing; audit log of every Bedrock (and RAG) interaction; red-team scenarios and content-filtering guardrails.

### 2.3 Where RAG Services Are Available (Platform Touchpoints)

RAG is delivered by a **single implementation** (`NativeRAGService`) used everywhere knowledge-base ingestion or retrieval is needed. There is no separate “Bedrock RAG service” yet; Bedrock is wired in only for **embeddings** (and optionally for **generation** via LiteLLM/Bedrock provider). Adding a **Bedrock-based knowledge-base extract** path means adding a new parser/backend option in this same pipeline.

| Where RAG is used | Entry point | Pipeline (parse → chunk → embed → index / retrieve) |
|-------------------|-------------|----------------------------------------------------------------|
| **Workspace / KB document upload** | `POST /documents/upload` with `workspace_id` + optional `knowledge_base_id` | `documents.py` → `NativeRAGService.upload_domain_document` → `_process_document` |
| **RAGFlow-style domain APIs** | `src/api/routes/ragflow.py` (domain/KB CRUD, chat, document ops) | Same service, alias `RAGFlowService = NativeRAGService` |
| **Workspace index creation** | `workspace.py` (create workspace) | `NativeRAGService` used to create vector index for workspace |
| **Knowledge-base S3 sync** | `KnowledgeBaseS3SyncService.sync_knowledge_base` | Uses `NativeRAGService.ingest_external_document` → `_process_document` |

**Pipeline components (all in `src/services/`):**

| Component | Role | Current options | Bedrock hook today |
|-----------|------|-----------------|---------------------|
| **Document parsing (extract)** | Turn binary/docs into text for chunking | `DocumentParser`: naive, docling, vlm, custom-vlm, gpt-4o | None; no Bedrock parser type |
| **Chunking** | Split text into chunks | `ChunkingService` (semantic, etc.) | N/A |
| **Embeddings** | Vectorize chunks | `EmbeddingService`: OpenAI, local, **Bedrock Titan** | **Implemented**: `RAG_EMBEDDING_PROVIDER=bedrock`, `RAG_BEDROCK_EMBEDDING_REGION`, model e.g. `amazon.titan-embed-text-v1` |
| **Vector store** | Store/query vectors | `VectorStore`: local Elasticsearch or AWS OpenSearch (AOSS) | Same store; Terraform provisions OpenSearch |
| **Retrieval / chat** | Retrieve chunks, generate answer | `RetrievalService`, `RAGChatService` (LiteLLM) | Generation can use Bedrock via provider config; not specific to “RAG service type” |

To support a **new type of RAG service that uses Bedrock for knowledge-base extract**:

1. **Add a Bedrock-based document extraction path**  
   Either extend `DocumentParser` with a Bedrock-backed strategy (e.g. Bedrock document/vision API or Claude for extract), or introduce a separate “Bedrock extract” step that the existing parser can delegate to. Parser choice is today resolved per knowledge base / workspace in `_get_parser_for_knowledge_base` (and default from `RAGFLOW_DEFAULT_PARSER`).

2. **Wire Bedrock as a “connector” for that path**  
   - **Config**: New settings (e.g. `RAG_EXTRACT_PROVIDER=bedrock`, `RAG_BEDROCK_EXTRACT_REGION`, optional model) and/or a new parser type (e.g. `bedrock` or `bedrock-vision`) in the parser map in `native_rag_service._get_parser_for_knowledge_base` and in `rag/document_parser.ParserType`.  
   - **Credentials**: Same pattern as embeddings: IAM (default boto3 chain) or explicit AWS credentials; Terraform attaches `bedrock:InvokeModel` (and if needed document/vision APIs) to the app principal.  
   - **Optional**: Per-workspace or per–knowledge-base “backend” (e.g. `backend_type: opensearch_fasb` vs `bedrock_ref_arch`) to select full Bedrock extract + embed + generate in one go; implementation plan can call out this as a future extension.

---

## 3. AWS + Bedrock + Terraform Design

### 3.1 High-Level AWS Architecture

- **Identity & access**: IAM roles and policies (least privilege) for Bedrock, OpenSearch, S3, and application roles; no long-lived keys in Terraform state where avoidable.
- **Network**: VPC with public/private subnets; Bedrock and OpenSearch accessed via VPC endpoints (or private connectivity) where required; no public exposure of data stores.
- **Compute (for demo/app integration)**: Placeholder for ECS Fargate or Lambda (per existing `design_docs/rag_aws_architecture.md`); Terraform to define networking and IAM so that when app code is added, it can run in private subnets and call Bedrock/OpenSearch without going over the public internet.
- **Data**:
  - **Document storage**: S3 bucket(s) for raw and processed documents; lifecycle and encryption (KMS) defined in Terraform.
  - **Metadata and audit**: RDS PostgreSQL (or existing platform DB) for document metadata, chunk references, and audit logs; Terraform can define RDS and security groups if net-new, or document use of existing DB.
  - **Vector**: OpenSearch Service (or OpenSearch Serverless) with k-NN; index naming and access control aligned to “collection” or “company_hr_dataset” isolation.
- **AI/ML**: Amazon Bedrock for Titan Embeddings and Claude (and optionally other FM) for generation; model access and any Bedrock-specific policies in Terraform.
- **Security & compliance**: KMS for S3 and OpenSearch; Secrets Manager for any required secrets; CloudTrail and CloudWatch Logs for audit and observability; Terraform to enable and configure these.

### 3.2 Terraform Design Principles

- **Modular layout**: Separate modules for network, Bedrock (IAM + model access), OpenSearch, S3, RDS (if new), security (KMS, Secrets Manager), and observability (CloudTrail, CloudWatch). Root modules per environment (e.g. `envs/dev`, `envs/stage`, `envs/prod`) that compose these.
- **State**: Remote state (S3 + DynamoDB) with locking; no sensitive values in state where possible; use of variables and optional Secrets Manager references for secrets.
- **Multi-environment**: Same module set parameterized by environment (e.g. `environment = dev|stage|prod`); naming and tagging consistent (e.g. `project = eliza`, `feature = reference-architecture`).
- **Bedrock-specific**: IAM policies scoped to `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`, and list/get foundation models; optional VPC endpoint for Bedrock runtime if required for private-only access.

### 3.3 Component Mapping (PRD → AWS + Terraform)

| PRD Feature | AWS / Terraform Focus |
|-------------|------------------------|
| 2.1 Bedrock RAG | Terraform: Bedrock IAM, VPC endpoint (optional), S3 + OpenSearch for RAG pipeline; design doc for ingestion/chunking/embedding/retrieval with Bedrock Titan + Claude. |
| 2.2 Vector search | Terraform: OpenSearch (or Serverless) with k-NN; index naming and IAM for app; doc for hybrid/semantic patterns and index lifecycle/re-embedding. |
| 2.3 IaC | Terraform: All of the above as reusable modules; network isolation, private connectivity, least-privilege IAM; multi-account optional (single-account multi-env minimum). |
| 2.4 Runtime reliability | Terraform: No direct implementation; design doc and interface contract for retries, circuit breakers, fallback routing, and human-review workflow (e.g. SQS + review API). |
| 2.5 Safety & observability | Terraform: CloudTrail, CloudWatch Logs, optional X-Ray; KMS; IAM for Bedrock and app; design doc for prompt versioning, audit schema, red-team scenarios, and content filtering integration. |

---

## 4. Demo Data & Use-Case Strategy

### 4.1 Goals

- Demonstrate RAG and vector search across **multiple file types** and **business domains** typical of large organizations.
- Provide data that supports diverse **question types** (policy, numeric, process, compliance, lookup).
- Keep dataset size manageable for a demo while being representative (e.g. tens to low hundreds of documents per domain).

### 4.2 File Types to Support

| Type | Format | Use in Demo | Notes |
|------|--------|-------------|--------|
| **Documents** | PDF | Policies, handbooks, reports | Primary; already supported by docling. |
| **Spreadsheets** | Excel (.xlsx) | Payroll summaries, headcount, budgets | Structured + tables; need parsing strategy (e.g. table extraction, sheet-level or range-level chunking). |
| **Presentations** | PPTX | Training decks, org updates, sales decks | Slide-level chunking; titles and speaker notes as context. |
| **Structured/DB** | CSV/export or synthetic DB schema | HR lists, IT assets, sales pipeline | Represent “database” as CSV exports or JSON; chunk by row ranges or logical segments with schema context. |
| **Text / Markdown** | .md, .txt | Runbooks, playbooks, FAQs | Simple chunking; good for IT and process questions. |

### 4.3 Business Domains and Sample Content

| Domain | Example Data | Example Questions |
|--------|--------------|-------------------|
| **HR** | Employee handbook (PDF), benefits summary (PDF/Excel), org chart (Excel/PPTX), leave policy (PDF) | “What is the leave policy?” “Who do I report to for benefits?” “What are the remote work guidelines?” |
| **Payroll** | Pay bands (Excel), payroll calendar (PDF/Excel), tax withholding guide (PDF) | “When is payday?” “What are the pay bands for level 4?” “How do I update my W-4?” |
| **IT** | Password policy (PDF), asset list (Excel/CSV), runbooks (MD/PDF), VPN setup (PDF) | “How do I connect to VPN?” “What is the password expiry policy?” “Where is the runbook for incident X?” |
| **Sales** | Commission rules (PDF), pipeline template (Excel), product one-pager (PPTX/PDF), pricing (Excel) | “What is the commission for enterprise deals?” “What is the discount approval process?” “What are the key product differentiators?” |

### 4.4 Demo Dataset Structure (Recommended)

- **Repository or S3 prefix** (e.g. `demo/reference-architecture/`):
  - `hr/` — handbooks, benefits, org data (PDF, Excel, PPTX).
  - `payroll/` — calendars, pay bands, tax docs (PDF, Excel).
  - `it/` — policies, runbooks, asset lists (PDF, Excel, MD, CSV).
  - `sales/` — commission, pipeline, product, pricing (PDF, Excel, PPTX).
- **Metadata**: Each asset tagged with domain, file type, and optional “sensitivity” or “classification” for future guardrail demos.
- **Synthetic DB content**: CSV/JSON exports with clear schema (e.g. `employees.csv`, `assets.csv`, `deals.csv`) and a short “schema description” document so RAG can answer schema-aware questions.

### 4.5 Question Set (Demo Validation)

- Maintain a **curated question set** per domain (10–20 questions each) covering:
  - Factual lookup, policy interpretation, numeric (pay bands, dates), process (“how do I…”), and multi-doc synthesis.
- Use this set to validate retrieval quality and generation quality after RAG and guardrails are implemented.

---

## 5. Implementation Phases (PRD-Aligned)

Phases follow the PRD §5 (Discovery & Alignment → Platform Foundation → AI Capability → Validation & Scale Readiness), with Terraform and design deliverables called out explicitly.

### Phase 1: Discovery & Alignment (Weeks 1–2)

| # | Task | Deliverable | Owner |
|---|------|-------------|--------|
| 1.1 | Stakeholder alignment and use-case prioritization | Short memo: scope, demo use cases, success criteria | Product/Eng |
| 1.2 | Data and compliance assessment | Data classification and retention notes; constraints for S3, OpenSearch, RDS | Security/Compliance |
| 1.3 | Target-state architecture definition | Architecture doc (update or create) with AWS diagram; Terraform module list and env strategy | Eng |
| 1.4 | Demo data inventory and sourcing | List of demo assets (by domain and file type); sourcing plan (create synthetic vs. use sanitized samples) | Product/Eng |

**Checkpoint:** Architecture doc and Terraform module list agreed; demo data plan approved.

---

### Phase 2: Platform Foundation (Weeks 3–4)

| # | Task | Deliverable | Owner |
|---|------|-------------|--------|
| 2.1 | Terraform repo layout and state backend | Directory structure (see §6); S3 + DynamoDB for state; README for running Terraform | Eng |
| 2.2 | Network module | VPC, subnets, NACLs; optional VPC endpoints for Bedrock, S3, OpenSearch | Eng |
| 2.3 | IAM and security module | IAM roles and policies for Bedrock, OpenSearch, S3, RDS (least privilege); KMS keys; Secrets Manager pattern | Eng |
| 2.4 | S3 and RDS (if new) | S3 bucket(s) for documents and index snapshots; encryption; optional RDS for metadata/audit if not using existing platform DB | Eng |
| 2.5 | OpenSearch (or Serverless) module | OpenSearch domain with k-NN; index naming convention; security group and access policies | Eng |
| 2.6 | Bedrock “foundation” in Terraform | IAM for Bedrock invoke/list; optional VPC endpoint; no application code yet | Eng |
| 2.7 | Observability baseline | CloudTrail, CloudWatch Logs (and optional metrics); log retention and tagging | Eng |

**Checkpoint:** `terraform plan` and `apply` succeed for one environment (e.g. dev); all resources created and documented.

---

### Phase 3: AI Capability Deployment (Weeks 5–6)

| # | Task | Deliverable | Owner |
|---|------|-------------|--------|
| 3.1 | RAG blueprint document | Design: ingestion (S3 → parse → chunk), embedding with Bedrock Titan, indexing into OpenSearch, retrieval and prompt augmentation, generation with Claude | Eng |
| 3.2 | Model abstraction design | How the platform will switch between Bedrock models (and optionally other providers) for embed and generate; config and IAM implications | Eng |
| 3.3 | Vector search and index lifecycle doc | Semantic and hybrid search patterns; index lifecycle, re-embedding triggers, and versioning | Eng |
| 3.4 | Application integration touchpoints | List of code touchpoints in Eliza platform (e.g. `EmbeddingService`, `VectorStore`, `native_rag_service`, Bedrock provider) for later implementation | Eng |
| 3.5 | Bedrock knowledge-base extract design | Design for a new RAG path that uses Bedrock for document extraction: `DocumentParser` extension (e.g. `ParserType.BEDROCK`), config (`RAG_EXTRACT_PROVIDER` / parser map), and IAM; align with §2.3 and §7.3 so Terraform and app can add Bedrock extract without changing ingestion entry points | Eng |
| 3.6 | Demo data ingestion path | Design for loading demo data (per §4) into S3 and into the RAG pipeline (manual or scripted); no production code required in this plan | Eng |
| 3.7 | Runtime reliability design | Document: retry and backoff, circuit breaker and fallback model routing, human-in-the-loop (e.g. SQS queue + API contract for review) | Eng |

**Checkpoint:** Blueprints and design docs reviewed; integration touchpoints and demo ingestion path clear.

---

### Phase 4: Validation & Scale Readiness (Weeks 7–8)

| # | Task | Deliverable | Owner |
|---|------|-------------|--------|
| 4.1 | Safety and guardrails design | Prompt versioning and tracing; audit log schema for all Bedrock/RAG calls; red-team scenarios list; policy-based content filtering (e.g. PII, toxicity) and where it plugs in | Eng |
| 4.2 | Terraform multi-environment | Parameterize and apply to stage (and optionally prod); document promotion and drift process | Eng |
| 4.3 | Demo runbook | Steps to load demo data, run ingestion, and execute the curated question set; record results for baseline | Eng |
| 4.4 | Documentation and handover | Runbooks, architecture diagram, Terraform README, and “how to extend” for additional use cases | Eng |

**Checkpoint:** Stage (or prod) Terraform applied; demo runbook executed; documentation complete.

---

## 6. Terraform Module Layout

Suggested layout under a single root (e.g. `infra/` or `terraform/`):

```
terraform/
├── README.md                    # How to run, state, env vars
├── backend.tf                   # Or backend config per env
├── versions.tf                  # Provider versions (AWS, etc.)
├── variables.tf
├── outputs.tf
├── modules/
│   ├── network/                 # VPC, subnets, endpoints
│   ├── iam/                     # Roles and policies (Bedrock, OpenSearch, app)
│   ├── security/                # KMS, Secrets Manager
│   ├── storage/                 # S3 buckets and policies
│   ├── opensearch/              # OpenSearch domain + k-NN
│   ├── bedrock/                 # IAM + optional VPC endpoint for Bedrock
│   ├── observability/           # CloudTrail, CloudWatch
│   └── rds/                     # Optional, if net-new DB for metadata/audit
└── envs/
    ├── dev/
    │   ├── main.tf
    │   ├── variables.tf
    │   └── terraform.tfvars
    ├── stage/
    └── prod/
```

- **State**: Per-environment state (e.g. `eliza-refarch-dev`) in S3 with DynamoDB lock.
- **Naming**: Resource names and tags include `environment`, `project`, and optionally `module` for cost and ops.

---

## 7. Integration Points with Eliza Platform

When moving from “plan only” to implementation, these are the main touchpoints (no code changes in this plan):

| Platform Component | Integration Direction |
|--------------------|------------------------|
| `src/services/rag/embeddings.py` | **Implemented.** Bedrock Titan added as `EmbeddingProvider.BEDROCK`; supports `amazon.titan-embed-text-v1`, `amazon.titan-embed-text-v2:0`; uses Terraform-provisioned IAM (default boto3 chain) or optional `aws_access_key_id`/`aws_secret_access_key`. |
| `src/services/rag/vector_store.py` | **Implemented.** Index naming normalized for OpenSearch Serverless (`[a-z0-9_-]`, no leading `_`/`-`, max 255 chars). Prefix and suffix configurable; `RAG_OPENSEARCH_INDEX_PREFIX` can be set from Terraform output. IAM: app uses default boto3 credential chain; Terraform must attach data access policy for the collection. See §7.1 for questions to finalize alignment. |
| `src/services/native_rag_service.py` | **Implemented.** Embedding provider selectable via `RAG_EMBEDDING_PROVIDER=bedrock`; `RAG_BEDROCK_EMBEDDING_REGION` and `RAGFLOW_DEFAULT_EMBEDDING_MODEL` (e.g. `amazon.titan-embed-text-v1`) configure Bedrock Titan. Vector store unchanged; use with Terraform-managed OpenSearch. **Planned:** Support Bedrock for knowledge-base extract (see §7.3). |
| `src/services/rag/document_parser.py` | **Planned.** Today: naive, docling, vlm, custom-vlm, gpt-4o. Add a Bedrock-backed parser type (e.g. Bedrock document/vision or Claude for extract) so the same ingestion path can use Bedrock for the extract step; parser resolved in `NativeRAGService._get_parser_for_knowledge_base` (KB/workspace + `RAGFLOW_DEFAULT_PARSER`). |
| `src/services/bedrock_service.py` / Bedrock provider | **Implemented.** Generation uses BedrockProvider with auth_method=iam_role (default credential chain) or api_keys. Optional base_url on create/update for VPC endpoint override. Terraform: attach bedrock:InvokeModel (and InvokeModelWithResponseStream) to app principal; optional Bedrock VPC endpoint. See §7.2. |
| Document ingestion | Design S3 → platform ingestion path (e.g. S3 event → Lambda or Celery task) and chunking for Excel/PPTX/CSV per §4. |
| Audit and observability | Extend or add logging to meet “audit log of all AI interactions” with schema that can be shipped to CloudWatch/CloudTrail or SIEM. |
| Guardrails and human-in-the-loop | New or extended services that call Bedrock (or existing APIs) and write to audit store and optional review queue. |

### 7.1 Questions for Terraform / OpenSearch alignment

To ensure the platform is ready to use Terraform-managed OpenSearch, the following need to be decided and (where applicable) wired into Terraform outputs and data access policies:

1. **Index prefix**  
   What prefix will Terraform use for RAG indexes (e.g. `eliza_rag_dev`, `rag_domains`, or per-environment)? The app reads this from `RAG_OPENSEARCH_INDEX_PREFIX`; it should match whatever convention Terraform (or ops) uses so index names align.

2. **OpenSearch type**  
   Will the reference architecture use **OpenSearch Serverless (AOSS)** only, or also **managed OpenSearch**? The app currently targets AOSS (SigV4, `aoss` service, collection endpoint). If managed OpenSearch is in scope, we may need a separate code path or config (e.g. IAM auth vs fine-grained access).

3. **IAM principal for the app**  
   Which IAM principal will the Eliza app use in AWS (e.g. ECS task role, Lambda execution role, EC2 instance profile ARN)? Terraform must attach an OpenSearch Serverless **data access policy** that allows this principal to access the collection (and optionally restrict to an index pattern such as `{prefix}_*`).

4. **Domain vs tenant/company**  
   Is the RAG "domain" (used in index names as the suffix after the prefix) the same as `company_hr_dataset` or a separate ID? If they differ, how should we map domain_id to the index suffix so Terraform index-pattern policies (if any) stay correct?

5. **Collection endpoint and region**  
   Terraform should output the AOSS collection endpoint and region. The app expects `RAG_OPENSEARCH_HOST` = endpoint host (e.g. `xxxxx.us-east-1.aoss.amazonaws.com`) and `RAG_OPENSEARCH_REGION` = same region. Confirm these will be provided (e.g. as Terraform outputs or SSM/Secrets Manager) for the runtime environment.

Once these are answered, Terraform can be wired to output the right values and attach the correct data access policy; the platform code is already aligned to use them.

### 7.2 Bedrock (generation) – IAM and VPC endpoint

The platform is aligned for Terraform-managed Bedrock used for generation (Claude, etc.):

- **IAM**: Create/update a Bedrock config with `auth_method: "iam_role"` and no API keys. The app then uses the default boto3 credential chain (ECS task role, Lambda role, instance profile, or env vars). Terraform should attach an IAM policy to that principal with at least `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` for the intended model ARNs (and optionally `bedrock:ListFoundationModels` / `GetFoundationModel` for discovery).
- **VPC endpoint**: If Terraform creates a VPC endpoint for `bedrock-runtime`, either (1) run the app in the same VPC so traffic goes through the endpoint automatically (no config change), or (2) set `base_url` on the Bedrock configuration to the VPC endpoint URL (e.g. from Terraform output) when creating or updating the config via the API.
- **Config**: Each customer can have one or more Bedrock configurations (region, auth, optional base_url). The reference architecture can use a single config per environment (e.g. `iam_role` + one region, optional base_url from Terraform).

No open questions required for this point; optional follow-up: whether to drive default Bedrock config (e.g. region, base_url) from env or Terraform-injected SSM/Secrets for new deployments.

### 7.3 Bedrock for knowledge-base extract (new RAG service type)

To support a **RAG service that uses Bedrock for the knowledge-base extract** step (in addition to existing Bedrock embeddings and generation), the following touchpoints and hook-up are recommended.

**Goal:** Allow document parsing/extraction to be performed by a Bedrock model (e.g. document understanding or vision API), so the reference architecture can offer an end-to-end Bedrock path: extract → embed (Titan) → store (OpenSearch) → generate (Claude).

**Where to hook Bedrock as the “extract” connector:**

| Touchpoint | Purpose |
|------------|---------|
| `src/services/rag/document_parser.py` | Add `ParserType.BEDROCK` (or similar) and implement a path that calls Bedrock (e.g. `InvokeModel` with a document/vision-capable model) to produce text from uploaded documents. Reuse the same chunking and embedding pipeline after extract. |
| `src/services/native_rag_service.py` | In `_get_parser_for_knowledge_base`, extend the parser map with a new value (e.g. `bedrock`, `bedrock-vision`) that maps to the new parser type. Optionally resolve Bedrock extract region/model from KB or workspace config. |
| `src/core/config.py` | Add settings for Bedrock extract when used globally (e.g. `RAG_EXTRACT_PROVIDER=bedrock`, `RAG_BEDROCK_EXTRACT_REGION`, `RAG_BEDROCK_EXTRACT_MODEL`). Defaults can align with Terraform-provisioned Bedrock access. |
| Terraform / IAM | Ensure the app principal has `bedrock:InvokeModel` (and any document/vision-specific permissions) for the extract model; can share the same Bedrock IAM policy as generation if using the same endpoint. |

**Implementation approach (for a later technical spec):**

1. **Parser**: New Bedrock-backed parser that accepts `file_content`, `filename`, `mime_type`, and returns a `ParsedDocument` (same contract as existing parsers). Use boto3 `bedrock-runtime` with the chosen model; handle page-by-page or doc-level API depending on Bedrock API shape.
2. **Config**: Use IAM or explicit AWS credentials (same pattern as `EmbeddingService` Bedrock client); Terraform provisions IAM so no keys in code.
3. **Optional per-KB/workspace choice**: Store a parser type or `backend_type` on the knowledge base or workspace (e.g. `bedrock_ref_arch`) so some KBs use Bedrock extract + Bedrock embed while others keep docling/VLM + OpenAI embed. The same `NativeRAGService` and `_process_document` flow run both; only the parser and embedding provider selection change.

Phase 3 (AI Capability) should include a design task for “Bedrock document extraction” and the above touchpoints so that when application code is implemented, Terraform and IAM are already aligned.

---

## 8. Prerequisites & Dependencies

- **AWS**: Account(s) with Bedrock model access (Titan, Claude) and quotas; ability to create VPC, OpenSearch, S3, IAM, KMS, CloudTrail, CloudWatch.
- **Terraform**: >= 1.x; AWS provider >= 5.x; state backend (S3 + DynamoDB) available.
- **Team**: Access to run Terraform and deploy to at least one environment (dev); security/compliance input for data classification and retention.
- **Demo data**: Legal/compliance approval to use chosen demo content (synthetic or sanitized).

---

## 9. Success Criteria & Progress Tracking

### 9.1 Success Criteria (from PRD §6, Adapted)

- Terraform successfully provisions a full reference-architecture stack (network, Bedrock, OpenSearch, S3, IAM, observability) in at least one environment.
- RAG and vector search blueprints are documented and aligned with Bedrock (Titan + Claude) and Terraform-managed OpenSearch.
- Demo dataset (multi-format, multi-domain) is defined and ingestion path designed; demo question set is defined.
- Runtime reliability and safety/observability designs are documented and integration points with the platform identified.
- Documentation and runbooks enable another team to replicate and extend the architecture.

### 9.2 Progress Tracking

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Discovery & Alignment | ⬜ Not Started | 0% |
| Phase 2: Platform Foundation (Terraform) | ⬜ Not Started | 0% |
| Phase 3: AI Capability (RAG + runtime design) | ⬜ Not Started | 0% |
| Phase 4: Validation & scale readiness | ⬜ Not Started | 0% |

**Status legend:** ⬜ Not Started | 🟡 In Progress | ✅ Complete | ❌ Blocked

### 9.3 Testing strategy

A **testing strategy** and runnable tests are in place so you can verify the reference-architecture integrations:

- **Doc**: [features/active/reference-architecture/TESTING_STRATEGY.md](TESTING_STRATEGY.md) – test levels, unit vs integration vs smoke, env vars, and success criteria.
- **Unit tests** (no AWS):  
  `pytest tests/reference_architecture/ -v`  
  Covers: vector store index naming normalization, embedding provider/dimensions (including Bedrock Titan), Bedrock config optional `base_url`.
- **Smoke script** (Bedrock embeddings and optional generation):  
  `python scripts/reference_architecture_smoke_test.py --embed`  
  Set `RAG_EMBEDDING_PROVIDER=bedrock`, `RAGFLOW_DEFAULT_EMBEDDING_MODEL=amazon.titan-embed-text-v1`, `RAG_BEDROCK_EMBEDDING_REGION`, and AWS credentials (or IAM), then run to confirm Titan embeddings work. Use `--generate` to run a Bedrock connection test via the app’s Bedrock config.

Run unit tests from repo root (with project venv/poetry/uv activated so `pytest` is available).

---

## Notes

- This plan is **design and implementation plan only**. Code changes to the Eliza Platform (FastAPI, Celery, frontend, or RAG services) will be specified in a subsequent technical spec and/or implementation plan that references this document.
- Terraform modules should be kept reusable so that other products or portfolio companies can adopt the same reference architecture with minimal forking.
- Demo data and question set should be versioned (e.g. in repo or S3) so that regressions and improvements in RAG/guardrails can be measured over time.
