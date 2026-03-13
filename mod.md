# Eliza Platform — Modular Build & Deployment Plan

> **Goal:** Ship subsets of the Eliza Platform into customer clouds (AWS/EKS) as lean, purpose-built containers — without forking the repo or maintaining parallel codebases.

---

## 1. The Problem

Today, every deployment ships the *entire* platform: 50+ API routes, 30+ frontend pages, 16 Celery task modules, heavy ML dependencies (PyTorch, spaCy, Docling), and connections to 5 backing stores. When Cengage only needs the Adoption Dashboard, or another customer only needs a Bedrock RAG pipeline with Langfuse evals and a chat UI, we're deploying 10x the surface area they need — which means:

- Larger images, slower deploys, more infra cost
- Unnecessary attack surface in customer VPCs
- Harder to reason about what's running where
- Painful to support when everything is entangled

---

## 2. Core Concept: Applets

An **applet** is a self-contained, deployable slice of the platform. Each applet declares exactly what it needs from the monorepo — routes, tasks, services, models, frontend pages, infrastructure dependencies, and migrations.

The monorepo stays monolithic for development. Modularity is a **build-time concern only.** You develop against the full platform; when it's time to build a customer image, you pass build args that select which applets to include.

```
                    ┌─────────────────────────────────────────┐
  Development       │         Full Monorepo (all code)        │
                    └──────────────┬──────────────────────────┘
                                   │
                          build --build-arg APPLETS=rag_chat,evals
                                   │
                    ┌──────────────▼──────────────────────────┐
  Customer Image    │  Only RAG Chat + Evals code, routes,    │
                    │  tasks, frontend pages, dependencies    │
                    └─────────────────────────────────────────┘
```

---

## 3. Applet Registry

Each applet is defined by a YAML manifest in `applets/`. No code changes required to define a new applet — just declare what the applet needs.

### 3.1 Manifest Structure

```
applets/
├── _base.yaml              # Always included (auth, health, core middleware)
├── rag_chat.yaml           # RAG pipeline + chat UI
├── adoption.yaml           # Adoption dashboard
├── talent.yaml             # Talent intelligence suite
├── bi.yaml                 # Business intelligence Q&A
├── content_writer.yaml     # Content writer + research
├── evals.yaml              # Langfuse + RAG evaluation
├── data_connections.yaml   # Connector framework
├── reference_checks.yaml   # Reference check voice agent
├── sow.yaml                # SOW generation
└── profiles/               # Pre-composed bundles
    ├── cengage.yaml         # applets: [adoption, evals]
    ├── rag_aws.yaml         # applets: [rag_chat, evals]
    └── full.yaml            # applets: [all]
```

### 3.2 Example Manifest: `applets/rag_chat.yaml`

```yaml
applet: rag_chat
display_name: "RAG Chat Pipeline"
description: "Document ingestion, chunking, embedding, retrieval, and chat UI"

# --- Backend ---
routes:
  - ragflow            # RAG chat endpoints
  - workspace          # Workspace + KB management
  - documents          # Document upload/management
  - models             # Model selection

tasks:
  - ragflow_tasks
  - ragflow_source_sync_tasks
  - documents

services:
  - ragflow_service
  - native_rag_service
  - chunking_service
  - vector_service
  - workspace_seed_service
  - knowledge_base_access_service
  - rag/               # Entire rag/ subdirectory

models:
  - workspace
  - document
  - ragflow_domain

flows: []

# --- Frontend ---
pages:
  - chat
  - data-search

# --- Infrastructure ---
infra:
  required:
    - postgres
    - redis
  optional:
    - elasticsearch    # For OpenSearch-backed retrieval
    - langfuse         # If evals applet also included

# --- Python extras (heavy deps only needed by this applet) ---
python_extras:
  - rag               # Maps to optional dependency group in pyproject.toml

# --- Migrations ---
# Applet declares which migration "tags" it needs.
# Migrations are tagged in their docstrings.
migration_tags:
  - core
  - documents
  - workspaces
  - ragflow
```

### 3.3 The Base Applet (`_base.yaml`)

Always included regardless of applet selection. This is the platform skeleton.

> **Updated team decision:** Chat + RAG + Workspace are considered core platform capability and belong in `_base`.

```yaml
applet: _base
display_name: "Platform Core"

routes:
  - health
  - auth
  - config
  - settings
  - permissions
  - mfa
  - audit
  - tenant_admin
  - platform_admin
  - tenant_settings
  - providers
  - agents
  # Core platform capability
  - documents
  - ragflow
  - workspace
  - workspace_templates
  - workspace_chat

tasks:
  # Core platform capability
  - documents
  - ragflow_tasks
  - ragflow_source_sync_tasks

services:
  - auth_service
  - security_service
  - permission_service
  - settings_service
  - database_service
  - provider_service
  - langfuse_service
  - audit_service
  - mfa_service
  - tenant_admin_service

models:
  - database
  - auth
  - customer
  - tenant_admin
  - tenant_theme
  - system_settings
  - provider_config
  - model_info
  - agent_configuration
  - audit

pages:
  - auth
  - admin
  - tenant-admin
  - platform-admin
  - agent-configuration
  - chat
  - workspaces

infra:
  required:
    - postgres
    - redis

migration_tags:
  - core
  - auth
  - rbac
  - tenancy
```

### 3.4 Deployment Profile: `profiles/rag_aws.yaml`

Profiles compose applets into a deployable unit and can override infra/env settings for a target environment.

```yaml
profile: rag_aws
display_name: "Bedrock RAG Pipeline (AWS)"
description: "RAG pipeline with Langfuse evals for AWS EKS deployment"

applets:
  - rag_chat
  - evals

# Environment overrides for this deployment target
env_overrides:
  DEFAULT_LLM_MODEL: "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
  CREWAI_LLM_MODEL: "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
  RAG_USE_LOCAL_ELASTICSEARCH: "false"
  RAG_OPENSEARCH_HOST: "${OPENSEARCH_ENDPOINT}"

# Infrastructure notes for the deploy template
infra_notes: |
  Requires: EKS cluster, RDS PostgreSQL, ElastiCache Redis,
  OpenSearch domain, S3 bucket for document storage.
  Langfuse runs as a sidecar deployment.
```

---

## 4. Build-Time Applet Selection

### 4.1 Backend: Dynamic Router Registration

The key change is in `src/main.py`. Instead of hardcoded `app.include_router()` calls, the app reads an `APPLETS` environment variable (set at build time or runtime) and only registers the routers, tasks, and startup logic for the selected applets.

**Approach: Applet registry in Python — not code generation.**

```python
# src/applets/registry.py

import yaml
from pathlib import Path
from dataclasses import dataclass, field

@dataclass
class AppletSpec:
    name: str
    routes: list[str] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    flows: list[str] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    migration_tags: list[str] = field(default_factory=list)

def load_applets(selected: list[str]) -> AppletSpec:
    """Merge _base + selected applets into a single resolved spec."""
    applets_dir = Path(__file__).parent.parent.parent / "applets"
    merged = AppletSpec(name="merged")

    # Always load base
    manifests = ["_base.yaml"] + [f"{name}.yaml" for name in selected]

    for manifest_file in manifests:
        path = applets_dir / manifest_file
        if not path.exists():
            # Check profiles/
            path = applets_dir / "profiles" / manifest_file
            if not path.exists():
                raise ValueError(f"Applet manifest not found: {manifest_file}")

        spec = yaml.safe_load(path.read_text())

        # If it's a profile, recursively resolve its applet list
        if "applets" in spec:
            sub = load_applets(spec["applets"])
            for attr in ["routes", "tasks", "models", "services", "flows",
                         "pages", "migration_tags"]:
                getattr(merged, attr).extend(getattr(sub, attr))
        else:
            for attr in ["routes", "tasks", "models", "services", "flows",
                         "pages", "migration_tags"]:
                getattr(merged, attr).extend(spec.get(attr, []))

    # Deduplicate while preserving order
    for attr in ["routes", "tasks", "models", "services", "flows",
                 "pages", "migration_tags"]:
        setattr(merged, attr, list(dict.fromkeys(getattr(merged, attr))))

    return merged
```

**Modified `src/main.py` (conceptual diff):**

```python
import os
from src.applets.registry import load_applets

# Determine which applets to load
applet_names = os.environ.get("APPLETS", "all").split(",")
if "all" in applet_names:
    applet_spec = None  # Load everything (current behavior)
else:
    applet_spec = load_applets(applet_names)

# --- Route registration becomes conditional ---
ROUTE_MAP = {
    "health":               ("api.routes.health",               "/health",       "Health"),
    "auth":                 ("api.routes.auth",                  "/v1/auth",      "Authentication"),
    "ragflow":              ("src.api.routes.ragflow",           "",              "RAGFlow"),
    "workspace":            ("src.api.routes.workspace",         "",              "Workspaces"),
    "documents":            ("api.routes.documents",             "",              "Documents"),
    "adoption":             ("src.api.routes.adoption",          "",              "Adoption Dashboard"),
    "rag_eval":             ("src.api.routes.rag_eval",          "/api/v1",       "RAG Evaluation"),
    # ... every route mapped here
}

for route_key, (module_path, prefix, tag) in ROUTE_MAP.items():
    if applet_spec is None or route_key in applet_spec.routes:
        module = importlib.import_module(module_path)
        app.include_router(module.router, prefix=prefix, tags=[tag])
```

**Why this works for upstream development:** When `APPLETS=all` (the default in dev), everything loads exactly as it does today. The conditional path only activates for customer builds. Zero impact on daily development workflow.

### 4.2 Frontend: Build-Time Page Exclusion

The frontend uses React Router. We add an `REACT_APP_APPLETS` build arg that controls which page bundles are included.

**Approach: Conditional dynamic imports in the router.**

```typescript
// frontend/src/appletConfig.ts

const ENABLED_APPLETS = (process.env.REACT_APP_APPLETS || "all").split(",");

export function isAppletEnabled(applet: string): boolean {
  return ENABLED_APPLETS.includes("all") || ENABLED_APPLETS.includes(applet);
}
```

```typescript
// frontend/src/routes.tsx (simplified)

const routes = [
  // Always included (base)
  { path: "/login",    component: lazy(() => import("./pages/auth/LoginPage")) },
  { path: "/settings", component: lazy(() => import("./pages/admin/SettingsPage")) },

  // Conditional — tree-shaken when applet not selected
  ...(isAppletEnabled("rag_chat") ? [
    { path: "/chat",        component: lazy(() => import("./pages/chat/ChatPage")) },
    { path: "/data-search", component: lazy(() => import("./pages/data-search/SearchPage")) },
  ] : []),

  ...(isAppletEnabled("adoption") ? [
    { path: "/adoption",    component: lazy(() => import("./pages/adoption/AdoptionPage")) },
  ] : []),

  // ... etc
];
```

Because `REACT_APP_APPLETS` is a build-time env var resolved by webpack/CRA, unused dynamic imports are dead-code eliminated in the production build. The bundle only includes the pages for the selected applets.

### 4.3 Celery Workers: Selective Task Registration

Celery workers auto-discover tasks from `src/tasks/`. We constrain this using the applet spec.

```python
# src/celery_app.py (modified)

import os

applet_names = os.environ.get("APPLETS", "all").split(",")

if "all" in applet_names:
    celery_app.autodiscover_tasks(["src.tasks"])
else:
    from src.applets.registry import load_applets
    spec = load_applets(applet_names)
    task_modules = [f"src.tasks.{t}" for t in spec.tasks]
    celery_app.autodiscover_tasks(task_modules)
```

---

## 5. Docker Build Integration

### 5.1 Backend Dockerfile Changes

```dockerfile
# Added to the runtime stage of docker/Dockerfile

# Build arg: comma-separated applet names (default: all)
ARG APPLETS=all
ENV APPLETS=$APPLETS

# (Optional future optimization) Selective COPY based on applets
# For now, we copy all source and let the runtime filter.
# Phase 2 can add a build script that prunes unused modules.
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser applets/ ./applets/
COPY --chown=appuser:appuser config/ ./config/
COPY --chown=appuser:appuser alembic/ ./alembic/
```

### 5.2 Frontend Dockerfile Changes

```dockerfile
# In frontend/Dockerfile, the builder stage:

ARG REACT_APP_API_URL=""
ARG REACT_APP_APPLETS="all"

ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_APPLETS=$REACT_APP_APPLETS

RUN npm run build
```

### 5.3 Build Commands

```bash
# Full platform (development, internal use)
docker compose build

# Cengage: Adoption Dashboard + Evals only
docker compose build \
  --build-arg APPLETS=adoption,evals \
  --build-arg REACT_APP_APPLETS=adoption,evals \
  app celery-worker frontend

# AWS RAG deployment
docker compose build \
  --build-arg APPLETS=rag_chat,evals \
  --build-arg REACT_APP_APPLETS=rag_chat,evals \
  app celery-worker frontend
```

### 5.4 Docker Compose Profiles (for infrastructure)

Different applets need different backing services. Docker Compose profiles let us start only what's needed.

```yaml
# docker/docker-compose.yml additions

services:
  postgres:
    profiles: ["base", "full"]   # Always needed

  redis:
    profiles: ["base", "full"]   # Always needed

  elasticsearch:
    profiles: ["rag_chat", "bi", "talent", "full"]

  neo4j:
    profiles: ["talent", "full"]

  langfuse-web:
    profiles: ["evals", "full"]

  langfuse-worker:
    profiles: ["evals", "full"]
```

```bash
# Start only what the RAG applet needs
COMPOSE_PROFILES=base,rag_chat,evals docker compose up -d
```

---

## 6. Deployment Pipeline

### 6.1 The Standard Pattern

```
┌────────────┐     ┌─────────────┐     ┌────────────────────┐     ┌──────────────┐
│ Git Push   │────▶│ Northflank   │────▶│ Cloud Deploy       │────▶│ Customer VPC │
│ (branch/   │     │ Build        │     │ Template           │     │ EKS Cluster  │
│  tag)      │     │ Pipeline     │     │ (Terraform/Helm)   │     │              │
└────────────┘     └─────────────┘     └────────────────────┘     └──────────────┘
                         │
                   Build args:
                   APPLETS=rag_chat,evals
                   REACT_APP_APPLETS=rag_chat,evals
```

### 6.2 Northflank Build Configuration

Each customer deployment gets a Northflank build pipeline that:

1. **Pulls from the same repo** (monorepo, specific branch/tag)
2. **Sets build args** per customer profile
3. **Pushes images** to customer's container registry (ECR, etc.)

```yaml
# northflank/builds/cengage.yaml (conceptual)
build:
  repo: ElizaPlatform
  branch: release/v2.x
  services:
    app:
      dockerfile: docker/Dockerfile
      build_args:
        APPLETS: adoption,evals
    frontend:
      dockerfile: frontend/Dockerfile
      build_args:
        REACT_APP_APPLETS: adoption,evals
        REACT_APP_API_URL: ""
    celery-worker:
      dockerfile: docker/Dockerfile
      build_args:
        APPLETS: adoption,evals
```

### 6.3 Cloud Deploy Template (AWS)

The deploy template is cloud-provider-specific and creates the infrastructure. For AWS:

```
deploy-templates/
├── aws/
│   ├── terraform/
│   │   ├── main.tf           # VPC, subnets, security groups
│   │   ├── eks.tf            # EKS cluster
│   │   ├── rds.tf            # PostgreSQL (always)
│   │   ├── elasticache.tf    # Redis (always)
│   │   ├── opensearch.tf     # OpenSearch (conditional on applet)
│   │   ├── s3.tf             # Document storage
│   │   └── variables.tf      # Customer-specific params
│   └── helm/
│       ├── Chart.yaml
│       ├── values.yaml       # Defaults
│       └── templates/
│           ├── app.yaml
│           ├── celery.yaml
│           ├── frontend.yaml
│           ├── migrations.yaml   # Job: runs once
│           └── ingress.yaml
```

**Terraform variables driven by the applet profile:**

```hcl
variable "applets" {
  type    = list(string)
  default = ["rag_chat", "evals"]
}

# Conditionally create OpenSearch
module "opensearch" {
  count  = contains(var.applets, "rag_chat") || contains(var.applets, "bi") ? 1 : 0
  source = "./modules/opensearch"
  # ...
}

# Conditionally create Neo4j
module "neo4j" {
  count  = contains(var.applets, "talent") ? 1 : 0
  source = "./modules/neo4j"
  # ...
}
```

### 6.4 Helm Values Per Customer

```yaml
# helm/values-cengage.yaml
image:
  repository: 123456789.dkr.ecr.us-east-1.amazonaws.com/eliza
  tag: "release-2.1.0-adoption-evals"

applets: "adoption,evals"

app:
  replicas: 2
  resources:
    requests: { cpu: "500m", memory: "1Gi" }
    limits:   { cpu: "2",    memory: "4Gi" }

celery:
  replicas: 1
  resources:
    requests: { cpu: "250m", memory: "512Mi" }

frontend:
  replicas: 2

env:
  DATABASE_URL: "postgresql://..."
  REDIS_URL: "redis://..."
  LANGFUSE_HOST: "http://langfuse:3000"
  DEFAULT_LLM_MODEL: "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
```

---

## 7. Migration Strategy

Migrations need to be applet-aware so we don't run talent-related migrations in a RAG-only deployment.

### 7.1 Tag Migrations

Add a `tags` marker to each migration file's docstring:

```python
"""Add workspace and knowledge base tables

Revision ID: 045_add_workspaces
Tags: core, workspaces, ragflow
"""
```

### 7.2 Selective Migration Runner

```python
# scripts/run_migrations.py

import os
from alembic.config import Config
from alembic import command
from src.applets.registry import load_applets

applets = os.environ.get("APPLETS", "all").split(",")

if "all" in applets:
    # Run everything
    command.upgrade(Config("alembic.ini"), "head")
else:
    spec = load_applets(applets)
    allowed_tags = set(spec.migration_tags)
    # Custom migration runner that skips migrations
    # whose tags don't intersect with allowed_tags
    run_tagged_migrations(allowed_tags)
```

**Pragmatic shortcut for Phase 1:** Run all migrations regardless. The extra tables are empty and harmless. Selective migration execution is a Phase 2 optimization — it's safer to have unused empty tables than to risk missing a dependency.

---

## 8. Dependency Optimization (Phase 2)

The current image includes PyTorch, spaCy, Docling, and other heavy ML libraries. For applets that don't need them, we can use Python optional dependency groups.

### 8.1 `pyproject.toml` Extras

```toml
[project.optional-dependencies]
rag = ["docling", "PyMuPDF", "pypdfium2"]
talent = ["spacy", "scikit-learn", "faiss-cpu"]
ml = ["torch", "torchvision", "datasets", "huggingface-hub"]
content = ["dspy"]
voice = ["twilio"]
base = []  # Core deps only
```

### 8.2 Dockerfile with Selective Dependencies

```dockerfile
ARG APPLETS=all
ARG PIP_EXTRAS=all

# In the deps stage:
RUN if [ "$PIP_EXTRAS" = "all" ]; then \
      uv sync --locked --no-install-project --compile-bytecode --link-mode=copy; \
    else \
      uv sync --locked --no-install-project --compile-bytecode --link-mode=copy \
        --extra base --extra $PIP_EXTRAS; \
    fi
```

**Impact estimate:** Removing PyTorch + spaCy + Docling from a RAG-only image could cut the image size by 2-3 GB.

---

## 9. Applet Catalog (Initial)

| Applet | Description | Routes | Infra | Heavy Deps |
|---|---|---|---|---|
| `_base` | Auth, RBAC, health, config | 12 | Postgres, Redis | None |
| `rag_chat` | Document RAG + chat UI | 4 | + Elasticsearch/OpenSearch | docling, PyMuPDF |
| `evals` | Langfuse tracing + RAG eval | 2 | + Langfuse stack | None |
| `adoption` | Adoption metrics dashboard | 1 | — | None |
| `bi` | Business intelligence Q&A | 2 | + Elasticsearch | vanna |
| `talent` | Talent intelligence suite | 8 | + Neo4j, Elasticsearch | spaCy, faiss, torch |
| `content_writer` | Long-form content writer | 2 | — | dspy |
| `data_connections` | Connector framework | 2 | — | None |
| `reference_checks` | Voice reference checks | 2 | — | twilio |
| `sow` | SOW generation | 1 | — | None |
| `data_analyst` | SQL data analyst chat | 1 | — | vanna |
| `retrieval` | HubSpot CRM search | 2 | — | None |

---

## 10. Customer Deployment Examples

### 10.1 Cengage — Adoption Dashboard in AWS

```
Profile: cengage
Applets: adoption, evals
Infra:   EKS (2 nodes), RDS PostgreSQL, ElastiCache Redis, Langfuse sidecar
Images:  app (slim), celery-worker (slim), frontend (2 pages)
Est. size: ~800MB backend image (vs ~4GB full)
```

### 10.2 Generic RAG Pipeline in AWS

```
Profile: rag_aws
Applets: rag_chat, evals
Infra:   EKS, RDS PostgreSQL, ElastiCache Redis, OpenSearch, S3, Langfuse
Images:  app (medium), celery-worker (medium), frontend (3 pages)
Model:   Bedrock Claude via provider config
```

### 10.3 Full Platform (Eliza Internal / Northflank)

```
Profile: full
Applets: all
Infra:   Full docker-compose stack
Images:  Full images
```

---

## 11. Implementation Phases

### Phase 1: Foundation (1–2 weeks)
**Goal:** Prove the pattern works end-to-end with the Adoption Dashboard.

- [ ] Create `applets/` directory with `_base.yaml` and `adoption.yaml`
- [ ] Build `src/applets/registry.py` — YAML parser + merger
- [ ] Refactor `src/main.py` — route map + conditional registration
- [ ] Add `APPLETS` build arg to `docker/Dockerfile`
- [ ] Add `REACT_APP_APPLETS` build arg to `frontend/Dockerfile`
- [ ] Add `isAppletEnabled()` gating to frontend router
- [ ] Build a `cengage` profile and validate it boots with only adoption routes
- [ ] Document the pattern in `skills/modularity/`

**Success criteria:** `docker compose build --build-arg APPLETS=adoption` produces images where `/docs` only shows base + adoption endpoints.

### Phase 2: RAG Pipeline + Cloud Deploy (2–3 weeks)
**Goal:** Deploy a Bedrock RAG pipeline to a test AWS account.

- [ ] Create `rag_chat.yaml` and `evals.yaml` applet manifests
- [ ] Create `profiles/rag_aws.yaml`
- [ ] Build Terraform modules for AWS (EKS, RDS, Redis, OpenSearch, S3)
- [ ] Build Helm chart with applet-aware values
- [ ] Set up Northflank build pipeline with applet build args
- [ ] Deploy to test AWS VPC and validate end-to-end
- [ ] Add dependency extras to `pyproject.toml` for image slimming

### Phase 3: Mature & Scale (Ongoing)
**Goal:** Fill out the applet catalog, optimize images, add more cloud targets.

- [ ] Define remaining applet manifests (talent, bi, content_writer, etc.)
- [ ] Implement selective `uv sync` with dependency extras
- [ ] Add migration tagging and selective runner
- [ ] Build deploy templates for Azure (AKS) and GCP (GKE)
- [ ] Build a `eliza deploy` CLI tool that orchestrates the full pipeline
- [ ] Add applet-level health checks and /status endpoint

---

## 12. Upstream Development Impact

**This is the critical design constraint.** Modularity must not create friction for day-to-day development.

| Concern | Resolution |
|---|---|
| "Do I need to update a manifest when I add a route?" | Yes — add your route key to the relevant applet YAML. But if you forget, it still works in dev because `APPLETS=all` loads everything. CI can lint for unregistered routes. |
| "Will this break my local dev?" | No. `APPLETS` defaults to `all`. `dev-start.sh` doesn't set it. Everything loads as before. |
| "Can I test a specific applet locally?" | Yes. `APPLETS=rag_chat,evals docker compose up app` will boot only those routes. |
| "What about shared services?" | Services used by multiple applets are included by any applet that needs them. The registry deduplicates. |
| "What about database models?" | All models stay in the codebase. The ORM loads them all (needed for migration integrity). The filtering is at the route/task layer, not the model layer. |
| "Do I need to learn a new framework?" | No. It's YAML manifests + a ~100-line registry module + a conditional loop in `main.py`. |

### CI Guard Rail

Add a CI check that ensures every route file in `src/api/routes/` is listed in at least one applet manifest:

```bash
# scripts/lint_applets.py
# Compares ROUTE_MAP keys in main.py against union of all applet manifests
# Fails if any route is "orphaned" (not in any applet)
```

---

## 13. What We Share With Customers

For customers deploying in their cloud, we provide:

1. **Infrastructure requirements document** — generated from the applet profile (what AWS services are needed, sizing estimates)
2. **Terraform/Helm package** — they apply it to their AWS account to create VPC + EKS + backing services
3. **Container images** — pushed to their ECR from our Northflank build pipeline
4. **Helm values file** — customer-specific config (endpoints, secrets, model providers)
5. **Runbook** — upgrade procedure, monitoring, scaling guidance

They do not need access to our source code. They get OCI images and infrastructure-as-code.

---

## 14. Team Decisions (Resolved)

The following decisions replace the previous open questions:

1. **Migration strategy:** flatten/reset the Alembic history and move to a **tag-based migration approach** for modular deployments.
   - Rationale: we are pre-scale on external production customers, so now is the right time to cleanly reset migration debt.
   - Direction: implement applet-aware migration tags after flattening.

2. **Model organization:** move toward **per-applet model boundaries** instead of a single permanently shared model surface.
   - Rationale: cleaner ownership and easier modular packaging.
   - Direction: phase this in gradually to avoid breaking existing imports.

3. **Celery topology:** start with **one worker service** (plus scheduler as needed) with filtered task discovery; revisit multi-worker topology later for scale.
   - Rationale: keep operations simple in early modular rollout.

4. **Frontend build tooling:** **decision deferred** (CRA vs Vite).
   - Current stance: keep CRA for now, evaluate Vite once modular route/page gating is stable.

5. **Registry format:** keep applet manifests **YAML-driven**, but enforce stronger Python-side validation/typing.
   - Rationale: YAML remains readable for operators; Python validation improves safety.
   - Direction: evolve toward stricter schema validation and potentially Python-first declarations later.

6. **Langfuse deployment model:** **one Langfuse service per customer deployment**, shared by all applets for that customer.
   - Confirmed by team: "1 langfuse per customer for sure."

7. **Base functionality update:** Chat app + RAG + Workspace are now platform base functionality.
   - Interpretation: these are `_base` capabilities, and applets/tools power responses inside that base chat experience.

### Current Implementation vs. Decisions

Status snapshot against the above decisions:

- **Migration strategy (flatten + tag-based):** **Partially implemented.**
  - Revision graph is now consolidated to a single head via `zz26_flatten_baseline_merge`.
  - Applet migration tags are now resolved by a dedicated migration runner (`scripts/run_migrations.py`), and container startup uses this applet-aware runner.
  - Phase 2 selective execution engine is implemented (`safe` / `auto` / `selective` modes), and app startup now uses strict `selective` mode by default.
  - Migration tag linting is added (`scripts/lint_migration_tags.py`) and wired into CI in strict mode (`--enforce-known-tags --enforce-complete-tagging`).
  - Existing Alembic revisions now have migration tags backfilled across the full `alembic/versions/` tree.
  - Flatten execution prep is documented in `docs/migrations/ALEMBIC_FLATTEN_RUNBOOK.md`, with topology guardrails in `scripts/check_alembic_heads.py`.

- **Per-applet model boundaries:** **Not implemented yet.**
  - Current code still uses shared `src/models/`.

- **Single worker topology to start:** **Partially implemented.**
  - Applet-based task filtering is implemented.
  - Modular compose now has an explicit single-worker override (`docker/docker-compose.modular-single-worker.yml`) for applet deployments.
  - Full consolidation across all deployment templates is still pending.

- **Frontend tooling (CRA for now):** **Aligned.**
  - CRA remains in use.

- **Registry format (YAML + stronger Python validation):** **Partially implemented.**
  - YAML manifests + Python loader exist.
  - Basic validation is in place; schema hardening is still pending.

- **One Langfuse per customer:** **Conceptually aligned, operational template pending.**
  - Current plan/doc supports a single deployment-scoped Langfuse service.
  - Rule now codified in `docs/deploy/LANGFUSE_SINGLETON_PER_CUSTOMER.md`.
  - Customer cloud deploy templates still need to codify this explicitly.

### Follow-on Tasks to Reach Full Alignment

1. (Optional cleanup) archive/squash legacy migration history after rollout confidence window.
   - Cutover guardrails are active via `scripts/check_alembic_heads.py --expect-single-head`.
   - Readiness automation is available via `scripts/validate_flatten_readiness.py --require-single-head`.
2. Define applet model packaging/refactor plan (incremental per domain).
3. Consolidate worker topology to one primary worker path in modular compose/deploy templates.
4. Add stricter manifest schema validation (Pydantic/jsonschema) and CI checks.
5. Encode "single Langfuse per customer" directly in deploy templates and runbooks.

---

## Summary

The approach is: **YAML manifests define applets → build args select applets → runtime conditionally loads only what's needed → same repo, same dev workflow, lean customer images.**

No forks. No feature branches per customer. No code generation. The monorepo stays monolithic for development; modularity is a build-time knife that carves out exactly what each customer needs.
