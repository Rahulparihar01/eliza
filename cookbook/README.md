# CrewAI Enterprise Cookbook

A comprehensive guide to building production-ready AI applications using CrewAI flows and agents, based on real-world implementation patterns from the Eliza Platform.

## 🚀 Start Here

**New to CrewAI?** → Read **[COOKBOOK.md](COOKBOOK.md)** - A single comprehensive guide covering everything you need to build AI-native applications.

**Want detailed deep-dives?** → Browse the individual section documents below.

## 📚 Contents

### Main Document

- **[COOKBOOK.md](COOKBOOK.md)** - ⭐ **Start here!** Single comprehensive guide covering framework, integration, examples, and deployment essentials

### Detailed Sections (For Deep Dives)

1. **[01_INTRODUCTION.md](01_INTRODUCTION.md)** - What is CrewAI, enterprise requirements, architecture overview
2. **[02_CORE_ARCHITECTURE_PATTERNS.md](02_CORE_ARCHITECTURE_PATTERNS.md)** - Flow orchestration, agent specialization, state management, tool integration
3. **[03_INTEGRATION_PATTERNS.md](03_INTEGRATION_PATTERNS.md)** - API integration, Celery tasks, database sessions, SSE events
4. **[04_CONTAINERIZATION.md](04_CONTAINERIZATION.md)** - Docker architecture, multi-container setup, environment configuration
5. **[05_SCALABILITY.md](05_SCALABILITY.md)** - Horizontal scaling, queue management, resource allocation
6. **[06_MONITORING.md](06_MONITORING.md)** - Structured logging, metrics collection, error tracking
7. **[07_OPTIMIZATION.md](07_OPTIMIZATION.md)** - Prompt engineering, model selection, token optimization
8. **[08_REAL_WORLD_EXAMPLES.md](08_REAL_WORLD_EXAMPLES.md)** - Talent Intelligence, Task Enrichment, ML Engineer Matching flows
9. **[09_TROUBLESHOOTING.md](09_TROUBLESHOOTING.md)** - Common issues and solutions

### Reference Documents
- **QUICK_REFERENCE.md** - Quick lookup guide for common patterns and rules
- **OUTLINE.md** - High-level structure and table of contents
- **DETAILED_STRUCTURE.md** - Detailed patterns, code examples, and architectural diagrams

## 🎯 What This Cookbook Covers

### 1. Architecture Patterns
- Flow-based orchestration
- Agent specialization
- State management
- Tool integration
- Database session management

### 2. Integration Patterns
- REST API → Celery → CrewAI flows
- Async task execution
- Real-time event streaming (SSE)
- Multi-tenant isolation

### 3. Containerization
- Docker Compose setup
- Multi-container architecture
- Environment configuration
- Health checks and graceful shutdowns

### 4. Scalability
- Horizontal scaling strategies
- Queue management
- Resource allocation
- Auto-scaling patterns

### 5. Monitoring & Observability
- Structured logging
- Metrics collection
- Distributed tracing
- Error tracking
- Cost monitoring

### 6. Optimization
- Prompt engineering
- Model selection
- Token optimization
- Caching strategies

## 🏗️ Architecture Overview

```
Frontend (React)
    ↓ HTTP/SSE
FastAPI Application
    ↓ Celery Tasks
Celery Workers
    ↓ Flow Execution
CrewAI Flows
    ↓ Tool Execution
Custom Tools & Services
    ↓ Data Access
PostgreSQL / Elasticsearch / Neo4j / Redis
```

## 🔑 Key Patterns Demonstrated

### Flow Execution Pattern
```python
class MyFlow(Flow[FlowState]):
    @start()
    def step_one(self):
        # Initial step
        pass
    
    @listen(step_one)
    def step_two(self):
        # Subsequent step
        pass
```

### API Integration Pattern
```python
@router.post("/execute-flow")
async def execute_flow(request: FlowRequest):
    # Queue task
    task = execute_flow_task.delay(request.dict())
    return {"task_id": task.id, "status": "pending"}
```

### Celery Task Pattern
```python
@celery_app.task(bind=True, max_retries=3)
def execute_flow_task(self, request_data: dict):
    # Initialize database
    db = SessionLocal()
    try:
        # Create and run flow
        flow = MyFlow()
        results = flow.kickoff(request_data)
        # Store results
        return results
    finally:
        db.close()
```

## 📖 Real-World Examples

This cookbook uses actual implementations from the Eliza Platform:

- **Talent Intelligence Flow** (`src/flows/talent_intelligence_flow.py`)
  - Multi-stage candidate analysis pipeline
  - Dual search (internal + external)
  - State management across steps

- **Task Enrichment Flow** (`src/crewai_flows/task_enrichment_flow.py`)
  - Intent analysis
  - Context enrichment via RAG
  - Prompt optimization

- **ML Engineer Matching Flow** (`src/flows/ml_engineer_matching_flow.py`)
  - Multi-source profile synthesis
  - Pattern-informed ranking
  - Adaptive failure recovery

## 🚀 Getting Started

1. **Review the Outline** - Start with `OUTLINE.md` to understand the structure
2. **Read Detailed Structure** - See `DETAILED_STRUCTURE.md` for patterns and examples
3. **Explore Examples** - Check the actual implementations in `src/flows/` and `src/crewai_flows/`
4. **Apply Patterns** - Use the patterns in your own applications

## ⚠️ Critical Rules

### Database Session Management
```python
# ❌ NEVER: Store sessions in flow state
class FlowState(BaseModel):
    db_session: Session  # Causes pickle errors!

# ✅ ALWAYS: Create sessions locally
def my_method(self):
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    try:
        # Use db
        pass
    finally:
        db.close()
```

### Module Imports
```python
# ✅ GOOD: Module import maintains reference
from src.models import database

# ❌ BAD: Direct import creates local binding
from src.models.database import SessionLocal
```

## 📝 Contributing

As we expand this cookbook, please:
- Add examples from real implementations
- Include troubleshooting notes
- Document gotchas and solutions
- Keep patterns generalizable but grounded in reality

## 🔗 References

- [CrewAI Documentation](https://docs.crewai.com)
- [Eliza Platform Source Code](../src/)
- [Design Documents](../design_docs/)

## 📋 Status

1. ✅ Create outline and structure
2. ✅ Write detailed sections (all 9 sections complete)
3. ✅ Create architectural diagrams (Mermaid diagrams throughout)
4. ✅ Add troubleshooting guides (comprehensive troubleshooting section)
5. ✅ Include common pitfalls and solutions (throughout all sections)

## 🎉 Cookbook Complete!

This cookbook provides comprehensive guidance for building enterprise CrewAI applications based on real-world patterns from the Eliza Platform.

