# Codebase Knowledge Graph

> **Purpose:** Visual map of module relationships, dependencies, and data flow for AI agents navigating the codebase.

---

## 🗺️ High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React)                               │
│  frontend/src/                                                          │
│  ├── pages/         → Route components                                  │
│  ├── components/    → Reusable UI components                           │
│  ├── api/           → Orval-generated API clients                      │
│  └── hooks/         → Custom React hooks (including SSE)               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP/SSE
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            API LAYER (FastAPI)                          │
│  src/api/                                                               │
│  ├── routes/        → Endpoint definitions                             │
│  ├── schemas/       → Pydantic request/response models                 │
│  └── main.py        → Router registration                              │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              ▼                      ▼                      ▼
┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐
│  SERVICES           │  │  CELERY TASKS       │  │  MIDDLEWARE         │
│  src/services/      │  │  src/tasks/         │  │  src/middleware/    │
│  └── Business logic │  │  └── Async workers  │  │  └── Auth, RBAC     │
└──────────┬──────────┘  └──────────┬──────────┘  └─────────────────────┘
           │                        │
           │                        ▼
           │             ┌─────────────────────┐
           │             │  CREWAI FLOWS       │
           │             │  src/flows/         │
           │             │  └── AI workflows   │
           │             └──────────┬──────────┘
           │                        │
           ▼                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                    │
│  src/models/        → SQLAlchemy ORM models                             │
│  src/services/      → Data access logic                                 │
│  alembic/           → Database migrations                               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
┌───────────────┐         ┌───────────────────┐         ┌───────────────┐
│  PostgreSQL   │         │  Elasticsearch    │         │  Redis        │
│  Main DB      │         │  Vector Search    │         │  Cache/Queue  │
└───────────────┘         └───────────────────┘         └───────────────┘
```

---

## 📂 Directory Relationships

### API Request Flow

```
frontend/src/pages/[Page].tsx
    │
    │ imports
    ▼
frontend/src/api/eliza-api.ts (Orval-generated)
    │
    │ HTTP request to
    ▼
src/api/routes/[feature].py
    │
    │ depends on
    ▼
src/api/schemas/[feature].py (Pydantic models)
    │
    │ uses
    ▼
src/middleware/authorization.py (Auth check)
    │
    │ calls
    ▼
src/services/[feature]_service.py
    │
    │ queries
    ▼
src/models/[feature].py (SQLAlchemy)
    │
    │ maps to
    ▼
PostgreSQL tables
```

### Async Task Flow

```
src/api/routes/[feature].py
    │
    │ triggers
    ▼
src/tasks/[feature]_tasks.py
    │
    │ picks up from
    ▼
Redis (Celery queue)
    │
    │ executes via
    ▼
Celery Worker
    │
    │ may invoke
    ▼
src/flows/[feature]_flow.py (CrewAI)
    │
    │ uses tools from
    ▼
src/crewai_custom_tools/[tool].py
    │
    │ updates
    ▼
src/models/[feature].py → PostgreSQL
    │
    │ emits events to
    ▼
SSE Stream → Frontend
```

---

## 🔗 Module Dependencies

### Core Infrastructure

| Module | Location | Depends On | Used By |
|--------|----------|------------|---------|
| **Database** | `src/models/database.py` | SQLAlchemy | All models, services, tasks |
| **Config** | `src/core/config.py` | Pydantic Settings | Everything |
| **Logging** | `src/core/logging.py` | structlog | All modules |
| **Auth** | `src/core/auth_context.py` | JWT | Routes, middleware |
| **Celery App** | `src/celery_app.py` | Redis | Tasks |

### Business Domains

| Domain | Routes | Tasks | Models | Services | Flows |
|--------|--------|-------|--------|----------|-------|
| **Business Intelligence** | `business_intelligence.py` | `business_intelligence_tasks.py` | `business_intelligence.py` | `business_intelligence_service.py` | `task_enrichment_flow.py`, `data_analysis_flow.py` |
| **Talent Intelligence** | `talent_intelligence.py` | - | `talent_analysis.py` | `talent_intelligence_service.py` | `talent_intelligence_flow.py` |
| **Connectors** | `connectors.py` | - | `connector.py` | `connector_service.py` | - |
| **Documents** | `documents.py` | `document_tasks.py` | `document.py` | `document_service.py`, `vector_service.py` | - |
| **Auth/Users** | `auth.py`, `users.py` | - | `auth.py` | `auth_service.py` | - |

---

## 📊 Data Model Relationships

```
┌─────────────┐       ┌─────────────────┐       ┌─────────────────────┐
│  customers  │───┬──▶│     users       │───┬──▶│    bi_questions     │
└─────────────┘   │   └─────────────────┘   │   └──────────┬──────────┘
                  │                         │              │
                  │                         │              ▼
                  │                         │   ┌─────────────────────┐
                  │                         │   │  bi_enriched_prompts │
                  │                         │   └──────────┬──────────┘
                  │                         │              │
                  │                         │              ▼
                  │                         │   ┌─────────────────────┐
                  │                         │   │ bi_analysis_sessions │
                  │                         │   └──────────┬──────────┘
                  │                         │              │
                  │                         │              ▼
                  │                         │   ┌─────────────────────┐
                  │                         │   │  bi_telemetry_events │
                  │                         │   └─────────────────────┘
                  │                         │
                  │                         │   ┌─────────────────────┐
                  │                         └──▶│   talent_analyses   │
                  │                             └──────────┬──────────┘
                  │                                        │
                  │                             ┌──────────▼──────────┐
                  │                             │talent_analysis_events│
                  │                             └─────────────────────┘
                  │
                  │   ┌─────────────────┐       ┌─────────────────────┐
                  └──▶│   documents     │───┬──▶│  document_chunks    │
                      └─────────────────┘   │   └─────────────────────┘
                                            │
                                            │   ┌─────────────────────┐
                                            └──▶│ document_embeddings │
                                                └─────────────────────┘
                  
                  ┌─────────────────────────┐
                  │ connector_configurations │
                  └────────────┬────────────┘
                               │
                  ┌────────────▼────────────┐
                  │   connector_sync_runs   │
                  └─────────────────────────┘
```

---

## 🛠️ Tool & Flow Relationships

### CrewAI Tools

| Tool | Location | Purpose | Used By Flows |
|------|----------|---------|---------------|
| `DocumentSearchTool` | `crewai_custom_tools/document_search.py` | Vector search in documents | Data Analysis, Task Enrichment |
| `HRDatabaseTool` | `crewai_custom_tools/hr_database.py` | Query HR database | Data Analysis |
| `CandidateSearchTool` | `crewai_custom_tools/candidate_search.py` | Search candidates | Talent Intelligence |
| `WebSearchTool` | (built-in) | External web search | Various |

### CrewAI Flows

| Flow | Location | Purpose | Tasks Invoked | Tools Used |
|------|----------|---------|---------------|------------|
| `TaskEnrichmentFlow` | `crewai_flows/task_enrichment_flow.py` | Enrich user queries | BI tasks | DocumentSearch |
| `DataAnalysisFlow` | `crewai_flows/data_analysis_flow.py` | Analyze data | BI tasks | DocumentSearch, HRDatabase |
| `TalentIntelligenceFlow` | `flows/talent_intelligence_flow.py` | Match candidates | Talent tasks | CandidateSearch |

---

## 🔐 Security Boundaries

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        PUBLIC (No Auth)                                 │
│  - Health check endpoints                                               │
│  - Login/Register endpoints                                             │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                              JWT Verification
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AUTHENTICATED (JWT Required)                        │
│  - All /v1/* endpoints                                                  │
│  - Permission-based access via middleware                               │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                            Permission Check
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      TENANT ISOLATED (customer_id)                      │
│  - All data queries filtered by customer_id                            │
│  - Cross-tenant access requires superuser                              │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                          Company Access Check
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   COMPANY SCOPED (company_hr_dataset)                   │
│  - HR data filtered by company_hr_dataset                              │
│  - Documents filtered by company_hr_dataset for searches               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 File Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| API Routes | `src/api/routes/{domain}.py` | `business_intelligence.py` |
| Pydantic Schemas | `src/api/schemas/{domain}.py` | `business_intelligence.py` |
| SQLAlchemy Models | `src/models/{domain}.py` | `business_intelligence.py` |
| Celery Tasks | `src/tasks/{domain}_tasks.py` | `business_intelligence_tasks.py` |
| Services | `src/services/{domain}_service.py` | `business_intelligence_service.py` |
| CrewAI Flows | `src/flows/{domain}_flow.py` or `src/crewai_flows/{flow_name}_flow.py` | `talent_intelligence_flow.py` |
| CrewAI Tools | `src/crewai_custom_tools/{tool_name}.py` | `document_search.py` |
| Migrations | `alembic/versions/{revision}_{description}.py` | `abc123_add_bi_tables.py` |
| Frontend Pages | `frontend/src/pages/{PageName}Page.tsx` | `BusinessIntelligencePage.tsx` |
| Frontend Components | `frontend/src/components/{domain}/{ComponentName}.tsx` | `QuestionInput.tsx` |

---

## 🔍 Finding Things

### "Where is X implemented?"

| Looking For | Check These Locations |
|-------------|----------------------|
| API endpoint | `src/api/routes/*.py` |
| Database table | `src/models/*.py` |
| Background job | `src/tasks/*_tasks.py` |
| AI workflow | `src/flows/*.py`, `src/crewai_flows/*.py` |
| AI tool | `src/crewai_custom_tools/*.py` |
| Data connector | `src/services/ingestion/connectors/*.py` |
| Auth logic | `src/middleware/authorization.py`, `src/services/auth_service.py` |
| Frontend page | `frontend/src/pages/*.tsx` |
| UI component | `frontend/src/components/**/*.tsx` |

### "How does feature X work?"

1. Start with the API route: `src/api/routes/{feature}.py`
2. Follow the service: `src/services/{feature}_service.py`
3. Check for async tasks: `src/tasks/{feature}_tasks.py`
4. If AI-powered, check flows: `src/flows/{feature}_flow.py`
5. Review the data model: `src/models/{feature}.py`

---

## 🔄 Common Modification Patterns

### Adding a New Feature

```
1. src/models/{feature}.py          → Define data models
2. alembic/versions/...             → Create migration
3. src/services/{feature}_service.py → Business logic
4. src/api/schemas/{feature}.py     → Request/response models
5. src/api/routes/{feature}.py      → API endpoints
6. src/main.py                      → Register router
7. [Optional] src/tasks/            → Async processing
8. [Optional] src/flows/            → AI workflows
9. frontend/src/pages/              → UI
```

### Adding a New API Endpoint

```
1. src/api/schemas/{feature}.py     → Add request/response models
2. src/api/routes/{feature}.py      → Add endpoint function
3. [No registration needed if router exists]
```

### Adding Background Processing

```
1. src/tasks/{feature}_tasks.py     → Create task
2. src/api/routes/{feature}.py      → Add trigger endpoint
3. [Optional] Add SSE streaming endpoint
```

---

## 📚 Related Documentation

| Document | Purpose |
|----------|---------|
| `AGENTS.md` | Feature development guide |
| `skills/README.md` | Skills library overview |
| `.cursorrules` | Critical development rules |
| `cookbook/COOKBOOK.md` | CrewAI development patterns |
| `docs/connectors/` | Connector development guide |
