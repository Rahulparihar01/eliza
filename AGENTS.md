# Eliza Platform - Feature Development Guide

> **Mission:** Build a platform that makes it extremely easy for AI coding agents to build production-ready software by validating design principles through real products.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Frontend (React + TypeScript)                  │
│  - Component library • SSE real-time updates • Orval API clients   │
└──────────────────────────────────┬──────────────────────────────────┘
                                   ↓ HTTP/SSE
┌─────────────────────────────────────────────────────────────────────┐
│                        API Layer (FastAPI)                          │
│  - REST endpoints • JWT Auth + RBAC • Pydantic validation          │
└──────────────────────────────────┬──────────────────────────────────┘
                                   ↓ Celery Tasks
┌─────────────────────────────────────────────────────────────────────┐
│                   Task Execution (Celery Workers)                   │
│  - Async processing • Flow orchestration • Retries                  │
└──────────────────────────────────┬──────────────────────────────────┘
                                   ↓ Flow Execution
┌─────────────────────────────────────────────────────────────────────┐
│                    AI Agent Layer (CrewAI Flows)                    │
│  - Multi-agent workflows • Tool integration • State management     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   ↓ Data Access
┌─────────────────────────────────────────────────────────────────────┐
│                         Data Layer                                  │
│  PostgreSQL • Elasticsearch • Neo4j • FAISS • Redis                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Directory Structure

```
skills/                   # 🆕 AI Agent Skills Library (CHECK FIRST!)
├── common-actions/       # 🆕 Local dev, Northflank, DB, debugging operations
├── crewai/               # CrewAI development rules & patterns
├── design-system/        # Frontend component guidelines
├── row-level-security/   # Multi-tenant RLS implementation
├── celery-tasks/         # Async background task patterns
├── fastapi-endpoints/    # REST API endpoint development
├── database-migrations/  # Alembic migrations & SQLAlchemy models
├── connectors/           # Data source connector development
├── sse-realtime/         # Server-Sent Events real-time updates
├── code-templates/       # 🆕 Copy-paste boilerplate for new features
└── troubleshooting/      # 🆕 Error recovery playbook

features/                 # 🆕 Feature Development Hub
├── _templates/           # PRD, Tech Spec, Implementation Plan templates
├── active/               # Features currently in development
├── completed/            # Shipped features (reference)
└── backlog/              # Future features (PRDs only)

agent_runs/               # 🆕 Agent Execution History
├── templates/            # Run log template
├── completed/            # Successful run logs
├── failed/               # Failed run logs (for learning)
└── insights/             # Aggregated patterns from past runs

docs/
├── CODEBASE_MAP.md       # 🆕 Module relationships & navigation guide
├── api/                  # API reference
├── architecture/         # System architecture
├── connectors/           # Connector development
├── flows/                # Flow documentation
└── features/             # Feature implementations

scripts/
├── validate_feature.py   # 🆕 Pre-PR validation script
└── ...                   # Other utility scripts

src/
├── api/routes/           # FastAPI endpoints
├── api/schemas/          # Pydantic request/response models
├── tasks/                # Celery async tasks
├── flows/                # CrewAI multi-agent flows
├── crewai_custom_tools/  # Tools for AI agents
├── services/             # Business logic layer
│   ├── ingestion/        # Connector framework
│   │   └── connectors/   # Data source connectors
│   └── search/           # Search services
├── models/               # SQLAlchemy ORM models
├── core/                 # Auth, config, logging
└── middleware/           # Authorization, tenant context

frontend/src/
├── components/           # React components
│   └── ui/               # Design system components
├── pages/                # Route pages
├── api/                  # Orval-generated API clients
└── hooks/                # Custom React hooks

docs/                     # Documentation
├── api/                  # API reference
├── architecture/         # System architecture
├── connectors/           # Connector development
├── flows/                # Flow documentation
└── features/             # Feature implementations

cookbook/                 # CrewAI development cookbook
alembic/                  # Database migrations
```

---

## 🎯 Skills - Check FIRST Before Implementing

**ALWAYS check the relevant skill before implementing in these domains:**

| Domain | Skill Location | When to Check |
|--------|---------------|---------------|
| **Local Dev / Northflank** | `skills/common-actions/` | Starting env, connecting to services, debugging |
| **CrewAI Development** | `skills/crewai/` | Building flows, agents, tools, tasks |
| **UI Components** | `skills/design-system/` | Creating frontend components |
| **Multi-Tenancy** | `skills/row-level-security/` | Adding tenant-scoped features |
| **Celery Tasks** | `skills/celery-tasks/` | Creating async background tasks |
| **FastAPI Endpoints** | `skills/fastapi-endpoints/` | Building REST API endpoints |
| **Database Migrations** | `skills/database-migrations/` | Creating migrations or models |
| **Connectors** | `skills/connectors/` | Building data source connectors |
| **SSE Real-Time** | `skills/sse-realtime/` | Streaming progress to frontend |

Skills contain codified rules, patterns, and examples that prevent common mistakes.

---

## 🔄 Feature Development Workflow

Every feature follows a three-stage pipeline:

```
Product Spec (PRD)  →  Technical Spec  →  Implementation Plan
     WHAT                  HOW               EXECUTION
```

| Stage | Document | Owner |
|-------|----------|-------|
| 1. Product Spec | `01_PRODUCT_SPEC.md` | Product owner |
| 2. Technical Spec | `02_TECHNICAL_SPEC.md` | Dev agent (reviews PRD, asks questions) |
| 3. Implementation Plan | `03_IMPLEMENTATION_PLAN.md` | Dev agent (task breakdown) |

**Working on a feature?** Check `features/active/[feature-name]/` for all three documents.

**Starting a new feature?** Copy templates from `features/_templates/`.

---

## 🔑 Critical Development Rules

### 1. Database Sessions (NEVER store in serializable state)

```python
# ✅ CORRECT: Module import, local sessions
from src.models import database

def my_method(self):
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    try:
        # Use db here
    finally:
        db.close()

# ❌ WRONG: Direct import creates stale binding
from src.models.database import SessionLocal  # Will be None!
```

### 2. Container Updates (ALWAYS rebuild after code changes)

```bash
# ✅ CORRECT: Rebuild both app and celery-worker
docker-compose build app celery-worker
docker-compose up -d app celery-worker

# ❌ WRONG: Restart uses old image
docker-compose restart celery-worker
```

### 3. Multi-Tenancy (Use correct filters)

```python
# ✅ CORRECT: Filter by company_hr_dataset for searches
doc_tool = DocumentSearchTool(
    customer_id=user.customer_id,      # Ownership
    company_hr_dataset=target_company,  # Data filtering (CRITICAL!)
    limit=10
)

# ❌ WRONG: customer_id alone doesn't filter company data
```

### 4. API Response Fields (NEVER hardcode placeholder values)

```python
# ✅ CORRECT: Return actual database values
return Response(name=provider.name)

# ❌ WRONG: Hardcoding creates silent data loss
return Response(name=None)  # BAD!
```

---

## 🚀 Feature Development Patterns

### Pattern 1: New API Endpoint

**Files to modify:**
1. `src/api/schemas/your_feature.py` - Pydantic models
2. `src/api/routes/your_feature.py` - FastAPI endpoints
3. `src/main.py` - Register router

```python
# src/api/routes/your_feature.py
from fastapi import APIRouter, Depends
from src.middleware.authorization import require_permission

router = APIRouter(prefix="/your-feature", tags=["Your Feature"])

@router.post("/", response_model=YourResponse)
async def create_feature(
    request: YourRequest,
    current_user = Depends(require_permission(["feature:write"])),
    db: Session = Depends(get_db)
):
    """Create a new feature."""
    # Implementation
    return YourResponse(...)
```

### Pattern 2: Async Task (Long-running operations)

**Files to modify:**
1. `src/tasks/your_tasks.py` - Celery task
2. `src/api/routes/your_feature.py` - Endpoint that queues task

```python
# src/tasks/your_tasks.py
from src.celery_app import celery_app
from src.models import database

@celery_app.task(bind=True)
def process_feature(self, feature_id: int, user_id: int, customer_id: str):
    """Process feature asynchronously."""
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        # Long-running work
        pass
    finally:
        db.close()
```

```python
# API endpoint queues task and returns immediately
@router.post("/", status_code=202)
async def create_feature(...):
    db_record = create_db_record(...)
    process_feature.delay(db_record.id, user.id, user.customer_id)
    return {"id": db_record.id, "status": "processing"}
```

### Pattern 3: CrewAI Flow (AI Agent Workflow)

**Files to modify:**
1. `src/flows/your_flow.py` - CrewAI flow
2. `src/crewai_custom_tools/your_tools.py` - Agent tools
3. `src/tasks/your_tasks.py` - Task that runs flow

```python
# src/flows/your_flow.py
from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel

class YourFlowState(BaseModel):
    input_data: str
    result: Optional[str] = None
    # NEVER store database sessions here!

class YourFlow(Flow[YourFlowState]):
    @start()
    def analyze_input(self):
        agent = Agent(
            role="Analyst",
            goal="Analyze input data",
            tools=[YourTool()]
        )
        # Run agent and update state
        self.state.result = "..."
    
    @listen(analyze_input)
    def synthesize_results(self):
        # Next step in flow
        pass
```

### Pattern 4: New Connector (Data Source Integration)

**Files to modify:**
1. `src/models/connector.py` - Add enum value
2. `src/services/ingestion/connectors/your_connector.py` - Implementation
3. `src/api/routes/connectors.py` - Add to available types
4. `frontend/src/components/data-connections/CreateConnectionModal.tsx` - UI

```python
# src/services/ingestion/connectors/your_connector.py
from src.services.ingestion.connectors.base import BaseConnector

class YourConnector(BaseConnector):
    async def check(self) -> bool:
        """Test connectivity."""
        # Verify API key works
        
    def discover(self) -> Dict[str, Any]:
        """Return available streams."""
        return {"streams": [...]}
    
    def read_stream(self, stream_name: str, ...) -> Iterator[Dict]:
        """Yield records from stream."""
        for record in self.fetch_data():
            yield record
    
    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration."""
        return {"status": "valid", "errors": []}
```

### Pattern 5: SSE Real-Time Updates

```python
# Backend: Streaming endpoint
from fastapi.responses import StreamingResponse

@router.get("/{id}/stream")
async def stream_updates(id: int, token: str = Query(...)):
    async def event_generator():
        while not is_complete(id):
            event = get_latest_event(id)
            yield f"data: {json.dumps(event)}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

```typescript
// Frontend: EventSource client
const eventSource = new EventSource(
  `${API_URL}/feature/${id}/stream?token=${token}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateUI(data);
};
```

---

## 🔐 Authentication & RBAC

### Permission Format
Permissions use `resource:action` format:
- `bi:read`, `bi:write` - Business Intelligence
- `talent:read`, `talent:write` - Talent Intelligence
- `documents:read`, `documents:write` - Documents
- `connectors:read`, `connectors:write` - Connectors
- `system:admin` - Admin access

### Protecting Endpoints
```python
from src.middleware.authorization import require_permission

@router.get("/protected")
async def protected_endpoint(
    current_user = Depends(require_permission(["resource:read"]))
):
    # Only accessible with permission
```

---

## 🗃️ Database Patterns

### Model Definition
```python
# src/models/your_model.py
from src.models.database import BaseModel, Column, Integer, String, ForeignKey

class YourModel(BaseModel):  # Inherits id, created_at, updated_at
    __tablename__ = "your_table"
    
    customer_id = Column(String(100), index=True)  # Multi-tenant
    name = Column(String(255))
    status = Column(String(50), default="pending")
```

### Migration
```bash
# Create migration
alembic revision -m "add_your_table"

# Apply migration
alembic upgrade head
```

### SQLAlchemy Model Must Match Database
```python
# If table lacks updated_at column:
class YourModel(BaseModel):
    __tablename__ = "your_table"
    updated_at = None  # Override to exclude
```

---

## 🎨 Frontend Patterns

### API Client (Orval-generated)
```typescript
// Auto-generated from OpenAPI spec
import { useCreateFeature, useGetFeature } from '../api/eliza-api';

function FeaturePage() {
  const { mutate: create, isPending } = useCreateFeature();
  const { data, isLoading } = useGetFeature(id);
  
  return (/* JSX */);
}
```

### Component Pattern
```typescript
// frontend/src/components/YourComponent.tsx
import { useState, useEffect } from 'react';

interface Props {
  featureId: number;
  onComplete?: () => void;
}

export function YourComponent({ featureId, onComplete }: Props) {
  const [state, setState] = useState<State>(initialState);
  
  return (
    <div className="p-6 bg-surface rounded-lg">
      {/* Component JSX */}
    </div>
  );
}
```

---

## 🧪 Testing Checklist

Before deploying any feature:

- [ ] API endpoints return correct response models
- [ ] Database sessions properly closed in try/finally
- [ ] Multi-tenant filtering applied (customer_id, company_hr_dataset)
- [ ] Celery tasks handle errors gracefully
- [ ] Frontend displays loading/error states
- [ ] SSE connections handle reconnection
- [ ] Permissions checked on all endpoints
- [ ] Docker containers rebuilt after code changes

---

## 🐳 Development Commands

```bash
# Start all services
docker-compose up -d

# Rebuild after code changes (CRITICAL!)
docker-compose build app celery-worker
docker-compose up -d app celery-worker

# View logs
docker-compose logs -f app celery-worker

# Database migration
docker-compose exec app alembic upgrade head

# Access API docs
open http://localhost:5001/docs

# Frontend dev server
cd frontend && npm run start
```

---

## 📊 Langfuse Observability (Self-Hosted)

Langfuse provides LLM observability, tracing, and evaluation capabilities for the platform.

### Self-Hosting Langfuse

**Option 1: Docker Compose (Recommended for Development)**

Create a `docker-compose.langfuse.yml`:

```yaml
version: '3.8'

services:
  langfuse-server:
    image: langfuse/langfuse:2
    depends_on:
      langfuse-db:
        condition: service_healthy
    ports:
      - "3001:3000"
    environment:
      - DATABASE_URL=postgresql://langfuse:langfuse@langfuse-db:5432/langfuse
      - NEXTAUTH_SECRET=your-secret-key-change-in-production
      - SALT=your-salt-change-in-production
      - NEXTAUTH_URL=http://localhost:3001
      - TELEMETRY_ENABLED=false
      - LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=false
    restart: unless-stopped

  langfuse-db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=langfuse
      - POSTGRES_PASSWORD=langfuse
      - POSTGRES_DB=langfuse
    volumes:
      - langfuse_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langfuse"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  langfuse_postgres_data:
```

Start with:
```bash
docker-compose -f docker-compose.langfuse.yml up -d
```

Access Langfuse UI at: http://localhost:3001

**Option 2: Kubernetes/Helm**

```bash
helm repo add langfuse https://langfuse.github.io/langfuse-k8s
helm install langfuse langfuse/langfuse \
  --set postgresql.enabled=true \
  --set langfuse.nextauth.secret=your-secret \
  --set langfuse.salt=your-salt
```

### Configuring Eliza Platform to Use Langfuse

1. **Set environment variables** in your `.env` or `docker/.env`:

```bash
LANGFUSE_SECRET_KEY=sk-lf-...         # From Langfuse UI → Settings → API Keys
LANGFUSE_PUBLIC_KEY=pk-lf-...         # From Langfuse UI → Settings → API Keys
LANGFUSE_HOST=http://localhost:3001   # Your Langfuse server URL
LANGFUSE_ENABLED=true                 # Enable/disable tracing
```

2. **Get API Keys from Langfuse UI:**
   - Log in to Langfuse (http://localhost:3001)
   - Create a new project or use existing
   - Go to Settings → API Keys
   - Create new API key pair (public + secret)

### How Langfuse is Integrated

The platform uses `LangfuseService` (`src/services/langfuse_service.py`) which:

1. **Automatic LLM Tracing**: Configures LiteLLM callbacks to automatically trace all LLM calls
2. **Manual Trace/Span Creation**: Allows explicit tracing of operations
3. **Generation Logging**: Logs prompts, responses, and metadata

**Key Integration Points:**

| Component | Integration |
|-----------|-------------|
| `src/services/rag/pydantic_backend.py` | PydanticAI agents with Langfuse tracing |
| `src/services/rag_eval_service.py` | RAG evaluation runs traced to Langfuse |
| `src/services/langfuse_service.py` | Core service wrapper |

**Usage in Code:**

```python
from src.services.langfuse_service import LangfuseService

# Initialize (usually done at service startup)
langfuse_service = LangfuseService()

# Trace a generation/operation
langfuse_service.trace_generation(
    name="rag_query",
    input_data={"query": user_question},
    output_data={"response": answer},
    metadata={"workspace_id": workspace.id},
    model="gpt-4o",
    usage={"input_tokens": 100, "output_tokens": 200}
)

# Create traces with spans
with langfuse_service.trace(name="complex_operation") as trace:
    with trace.span(name="step_1"):
        # ... do step 1
        pass
    with trace.span(name="step_2"):
        # ... do step 2
        pass
```

### Viewing Traces

1. Open Langfuse UI (http://localhost:3001)
2. Select your project
3. Navigate to **Traces** to see all LLM interactions
4. Use **Sessions** to group related traces
5. Check **Generations** for individual LLM calls

### Production Deployment

For production, use [Langfuse Cloud](https://langfuse.com) or deploy self-hosted with:

- Proper secrets management (not hardcoded)
- PostgreSQL with backups
- SSL/TLS termination
- Authentication configured
- Resource limits set

**Cloud Setup:**
```bash
LANGFUSE_SECRET_KEY=sk-lf-...         # From cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_ENABLED=true
```

---

## 🤖 Agent-Optimized Resources

These resources are specifically designed to help AI agents work effectively in this codebase.

### Recommended Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        AGENT DEVELOPMENT WORKFLOW                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. UNDERSTAND THE TASK                                                 │
│     ├── Check features/active/[name]/ for PRD & specs                  │
│     ├── Review agent_runs/completed/ for similar past work             │
│     └── Read docs/CODEBASE_MAP.md to understand module relationships   │
│                                                                         │
│  2. PLAN THE IMPLEMENTATION                                             │
│     ├── Check relevant skills/ for domain rules                        │
│     └── Identify which code-templates/ to use                          │
│                                                                         │
│  3. IMPLEMENT                                                           │
│     ├── Copy from skills/code-templates/ as starting point             │
│     ├── Follow patterns in skills/[domain]/ guides                     │
│     └── If stuck, check skills/troubleshooting/ for fixes              │
│                                                                         │
│  4. VALIDATE                                                            │
│     ├── Run: python scripts/validate_feature.py [name]                 │
│     ├── Fix any failures or warnings                                   │
│     └── Rebuild containers: docker-compose build app celery-worker     │
│                                                                         │
│  5. COMPLETE                                                            │
│     └── Log work in agent_runs/completed/ for future agents            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. Code Templates (`skills/code-templates/`)

**What:** Copy-paste-ready boilerplate for common patterns.

**When to Use:** Starting any new file (endpoint, task, model, migration, page).

**How to Use:**
```
1. Open the relevant template (e.g., api_endpoint.py.template)
2. Copy the entire content
3. Paste into your new file
4. Replace all [PLACEHOLDERS] with actual values
5. Remove sections you don't need
```

**Available Templates:**
- `api_endpoint.py.template` - Full CRUD API with schemas
- `celery_task.py.template` - Async task with session handling
- `database_model.py.template` - SQLAlchemy model + enums
- `migration.py.template` - Alembic migration with indexes
- `service.py.template` - Business logic layer
- `frontend_page.tsx.template` - React page component
- `sse_hook.ts.template` - Real-time streaming hook

---

### 2. Codebase Map (`docs/CODEBASE_MAP.md`)

**What:** Visual map of module relationships and data flow.

**When to Use:** 
- Starting work in an unfamiliar area
- Understanding how components connect
- Finding where something is implemented

**Key Sections:**
- **Architecture diagrams** - How layers connect
- **Module dependency tables** - What imports what
- **Data model relationships** - Table relationships
- **"Where is X implemented?"** - Quick lookup table
- **File naming conventions** - How to name new files

---

### 3. Error Recovery Playbook (`skills/troubleshooting/ERROR_RECOVERY_PLAYBOOK.md`)

**What:** Quick fixes for common errors, searchable by error message.

**When to Use:** When you encounter an error during development.

**How to Use:**
```
1. Copy the error message
2. Search the playbook for keywords (e.g., "SessionLocal is None")
3. Follow the fix steps provided
4. Check the "Root Cause" to understand why it happened
```

**Covers:**
- Database session errors
- Schema mismatch errors  
- Container/deployment issues
- Authentication errors
- Celery task failures
- Search/multi-tenant issues
- SSE streaming problems
- Import errors

---

### 4. Validation Script (`scripts/validate_feature.py`)

**What:** Automated checker that catches common pattern violations.

**When to Use:** Before submitting any PR or after completing a feature.

**How to Use:**
```bash
# Validate a specific feature
python scripts/validate_feature.py business_intelligence

# Validate all code
python scripts/validate_feature.py --all

# Check only routes
python scripts/validate_feature.py --check routes

# Check only tasks
python scripts/validate_feature.py --check tasks
```

**What It Checks:**
- ✅ Response models on endpoints
- ✅ Authorization middleware usage
- ✅ No hardcoded placeholder values
- ✅ Correct database import pattern
- ✅ Session cleanup in finally blocks
- ✅ Multi-tenant fields present
- ✅ Migration chaining correct

---

### 5. Agent Execution Logs (`agent_runs/`)

**What:** Historical record of how past tasks were completed.

**When to Use:**
- **Before starting:** Check `agent_runs/completed/` for similar past tasks
- **After completing:** Log your work using the template

**How to Use (Before Starting):**
```
1. Browse agent_runs/completed/ for similar features
2. Review the "Approach Taken" and "Key Decisions"
3. Note any "Blockers Encountered" to avoid
4. Apply relevant patterns to your current task
```

**How to Use (After Completing):**
```
1. Copy agent_runs/templates/RUN_LOG_TEMPLATE.md
2. Fill in task summary, approach, blockers, lessons
3. Save to agent_runs/completed/YYYY-MM-DD_feature-name.md
```

**Why This Matters:** Future agents learn from past successes and failures.

---

### 6. Common Actions (`skills/common-actions/COMMON_ACTIONS.md`)

**What:** Quick reference for local dev, Northflank, database, and debugging operations.

**When to Use:**
- Starting or stopping the local development environment
- Connecting to Northflank services (database, redis, logs)
- Managing users (create, reset password, unlock)
- Debugging issues
- Deployment operations

**Key Sections:**
- **Local Development** - Start/stop scripts, rebuild containers
- **Northflank** - Connect to dashboard, database, redis, logs
- **Database Access** - Local and production connections
- **Database Migrations** - Run, create, rollback
- **User Management** - Create admin, reset password, unlock account
- **Debugging** - Test endpoints, check logs, inspect celery

**Important Rule:** 
> **Frontend runs locally by default** (via `./dev-start.sh`) for hot reload. Only use containerized frontend if explicitly requested.

**Quick Commands:**
```bash
./dev-start.sh              # Start dev (frontend local)
./dev-stop.sh               # Stop everything
docker-compose build app    # Rebuild after code changes
docker exec -it docker-postgres-1 psql -U user -d ai_enablement  # DB access
```

---

## 📚 Key Documentation

| Document | Purpose |
|----------|---------|
| **`skills/README.md`** | **🆕 Skills library - CHECK FIRST for domain knowledge** |
| **`skills/common-actions/`** | **🆕 Local dev, Northflank, DB, debugging operations** |
| **`skills/code-templates/`** | **🆕 Copy-paste templates for new features** |
| **`skills/troubleshooting/`** | **🆕 Error recovery playbook** |
| **`features/README.md`** | **🆕 Feature development workflow** |
| **`docs/CODEBASE_MAP.md`** | **🆕 Module relationships and navigation guide** |
| **`agent_runs/`** | **🆕 Agent execution logs for learning** |
| **`scripts/validate_feature.py`** | **🆕 Pre-PR validation script** |
| `dev_onboarding/README.md` | Full onboarding guide |
| `cookbook/COOKBOOK.md` | CrewAI development patterns |
| `docs/api/README.md` | API reference |
| `.cursorrules` | Critical development rules |

---

## 🏷️ Platform vs Products

### Platform (Foundation - Be Careful!)
- Database infrastructure (PostgreSQL, Elasticsearch, Neo4j, FAISS, Redis)
- Connector framework (`BaseConnector` class)
- Authentication & RBAC
- API patterns, logging, caching

### Products (Built on Platform)
- **Talent Intelligence**: Job analysis + candidate matching (`src/flows/talent_intelligence_flow.py`)
- **Business Intelligence**: Natural language Q&A (`src/tasks/business_intelligence_tasks.py`)

**Rule:** Products validate platform patterns. Platform stays generalized.

---

## ⚡ Quick Reference

| Need to... | Look at... |
|------------|------------|
| **Start/stop local dev** | **`skills/common-actions/`** - use `./dev-start.sh` (frontend local) |
| **Connect to Northflank** | **`skills/common-actions/`** - Northflank section |
| **Access database** | **`skills/common-actions/`** - Database Access section |
| **Build CrewAI flow/tool** | **`skills/crewai/` FIRST**, then `src/flows/*.py` |
| **Build UI component** | **`skills/design-system/` FIRST**, then `frontend/src/components/ui/` |
| **Implement multi-tenancy** | **`skills/row-level-security/` FIRST** |
| **Add API endpoint** | **`skills/fastapi-endpoints/` FIRST**, then `src/api/routes/*.py` |
| **Add async task** | **`skills/celery-tasks/` FIRST**, then `src/tasks/*.py` |
| **Add database migration** | **`skills/database-migrations/` FIRST**, then `alembic/versions/` |
| **Add connector** | **`skills/connectors/` FIRST**, then `src/services/ingestion/connectors/` |
| **Stream real-time updates** | **`skills/sse-realtime/` FIRST**, then existing SSE endpoints |
| **Scaffold new feature** | **`skills/code-templates/`** for copy-paste boilerplate |
| **Start new feature** | **`features/_templates/`** for PRD → Tech Spec → Impl Plan |
| **Navigate codebase** | **`docs/CODEBASE_MAP.md`** for module relationships |
| **Fix an error** | **`skills/troubleshooting/`** for common fixes |
| **Validate before PR** | **`python scripts/validate_feature.py [name]`** |
| **Log agent work** | **`agent_runs/templates/`** for run log template |
| Fix database session error | Check module import pattern (Rule 4b in .cursorrules) |
| Fix "column doesn't exist" | Verify SQLAlchemy model matches DB schema |
| Fix container old code | Rebuild: `docker-compose build app celery-worker` |

---

**Remember:** The goal is to build a platform that makes it easy for AI agents to build excellent software. Every decision should support that goal. 🚀

