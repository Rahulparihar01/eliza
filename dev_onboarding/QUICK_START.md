# Quick Start Guide - Eliza Platform

**For engineers who want to get productive fast.**

---

## 🎯 The One-Sentence Mission

**Build a platform that makes it extremely easy for AI coding agents to build production-ready software by validating design principles through real products.**

---

## 🏗️ Platform vs. Products (The Critical Distinction)

### Platform = Foundation (Don't Break It)
- **Databases**: PostgreSQL, Elasticsearch, Neo4j, FAISS, Redis
- **Connector Framework**: `BaseConnector` class for data integrations
- **Auth & RBAC**: JWT authentication, permission system
- **Design Patterns**: Database, API, tasks, logging, caching, frontend

### Products = Examples Built on Platform
1. **Talent Intelligence**: Job analysis + candidate matching
2. **Business Intelligence**: Natural language Q&A over business data

**Rule**: Products validate platform patterns. Platform stays generalized.

---

## 📚 Essential Reading (In Order)

1. **[Main Onboarding Guide](./README.md)** ← Start here
2. **[Repository Rules](../.cursorrules)** - Critical development rules
3. **[Cookbook Quick Reference](../cookbook/QUICK_REFERENCE.md)** - Common patterns
4. **[API Documentation](../docs/api/README.md)** - API reference

---

## 🚀 Get Running in 5 Minutes

```bash
# 1. Clone and setup
git clone <repo-url>
cd eliza-platform
chmod +x scripts/*.sh

# Note: frontend dependencies are installed locally via the lockfile.
# If you run the frontend outside Docker, run:
#   cd frontend && npm ci

# 2. Run setup script
./scripts/setup-local.sh

# 3. Update API keys in .env file

# 4. Start services
docker-compose up -d

# 5. Access API docs
open http://localhost:5001/docs
```

---

## 🎓 First Week Checklist

### Day 1: Foundation
- [ ] Read [Main Onboarding Guide](./README.md)
- [ ] Review [Repository Rules](../.cursorrules) - Rules 1-4 (database sessions)
- [ ] Set up local environment
- [ ] Access API docs and test authentication

### Day 2-3: Study Products
- [ ] Read Talent Intelligence docs: [`docs/talent/TALENT_INTELLIGENCE_COMPLETE.md`](../docs/talent/TALENT_INTELLIGENCE_COMPLETE.md)
- [ ] Trace Talent Intelligence flow: API → Task → Flow → Tools → DB
- [ ] Read BI docs: [`docs/api/02-business-intelligence.md`](../docs/api/02-business-intelligence.md)
- [ ] Understand task enrichment pattern

### Day 4-5: Platform Patterns
- [ ] Study connector framework: [`docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md`](../docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md)
- [ ] Review CrewAI patterns: [`cookbook/02_CORE_ARCHITECTURE_PATTERNS.md`](../cookbook/02_CORE_ARCHITECTURE_PATTERNS.md)
- [ ] Understand multi-tenancy (`customer_id`, `company_hr_dataset`)

---

## ⚡ Critical Rules (Memorize These)

### Database Sessions
```python
# ✅ ALWAYS: Module import, check initialization, local sessions
from src.models import database

if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()
try:
    # Use db
finally:
    db.close()

# ❌ NEVER: Store sessions in flow state (breaks Celery)
```

### Container Updates
```bash
# ✅ ALWAYS: Rebuild after code changes
docker-compose build app celery-worker
docker-compose up -d app celery-worker

# ❌ NEVER: Just restart (uses old image)
docker-compose restart celery-worker
```

### Multi-Tenancy
```python
# ✅ ALWAYS: Filter by company_hr_dataset for document searches
doc_tool = DocumentSearchTool(
    customer_id=user.customer_id,
    company_hr_dataset=target_company,  # ← Critical!
    limit=10
)

# ❌ NEVER: Filter by customer_id alone for company-specific data
```

---

## 🗺️ Codebase Map

```
src/
├── api/routes/          # API endpoints (FastAPI)
├── tasks/              # Celery tasks (async processing)
├── flows/              # CrewAI flows (AI agents)
├── services/           # Business logic
│   ├── ingestion/      # Connector framework
│   └── ...
├── models/             # SQLAlchemy models
├── core/              # Core infrastructure (auth, config, logging)
└── crewai_custom_tools/  # Tools for AI agents

docs/
├── api/               # API documentation
├── connectors/        # Connector development guides
├── talent/            # Talent Intelligence docs
└── architecture/      # Architecture deep-dives

cookbook/              # CrewAI development cookbook
dev_onboarding/        # This directory!
```

---

## 🎯 What Should I Work On?

### ✅ Good First Contributions

1. **Add a New Connector**
   - Follow [`docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md`](../docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md)
   - Use `BaseConnector` pattern
   - Test thoroughly

2. **Improve Documentation**
   - Add examples to cookbook
   - Document new patterns
   - Fix outdated docs

3. **Build a Small Product Feature**
   - Use existing platform components
   - Follow established patterns
   - Document learnings

4. **Fix Bugs or Improve Patterns**
   - Review existing code
   - Identify improvements
   - Follow repository rules

### ❌ Avoid These

- Modifying core platform without discussion
- Creating product-specific platform code
- Skipping documentation
- Ignoring established patterns

---

## 🔍 Key Concepts (One-Liners)

- **Multi-Tenancy**: `customer_id` (org) + `company_hr_dataset` (company)
- **CrewAI Flows**: Multi-step workflows with `@start()` and `@listen()`
- **Async Tasks**: API queues Celery task → returns immediately → SSE for updates
- **Connector Framework**: `BaseConnector` with `check()`, `discover()`, `read_stream()`
- **RBAC**: Permissions format `resource:action` (e.g., `bi:write`)

---

## 🆘 Common Issues & Solutions

### "ModuleNotFoundError: No module named 'src.core.database'"
- **Fix**: Use `from src.models import database` (not `src.core.database`)
- **Rule**: Always verify import paths with grep

### "PickleError: Can't pickle database session"
- **Fix**: Never store `Session` in flow state. Create sessions locally.
- **Rule**: See Repository Rule 1

### "Container has old code"
- **Fix**: Rebuild containers: `docker-compose build app celery-worker`
- **Rule**: Always rebuild after code changes

### "Column doesn't exist" error
- **Fix**: Check if model inherits `BaseModel` but table lacks `updated_at`
- **Rule**: Verify SQLAlchemy model matches database schema (Rule 19)

---

## 📞 Getting Help

1. **Check Documentation**
   - [Main Onboarding Guide](./README.md) - Comprehensive overview
   - [Cookbook](../cookbook/) - CrewAI patterns
   - [API Docs](../docs/api/) - API reference

2. **Review Existing Code**
   - Talent Intelligence: `src/flows/talent_intelligence_flow.py`
   - Business Intelligence: `src/tasks/business_intelligence_tasks.py`
   - Connectors: `src/services/ingestion/connectors/`

3. **Check Repository Rules**
   - [`.cursorrules`](../.cursorrules) - Critical development rules
   - Common patterns and anti-patterns

---

## ✅ Success Checklist

You're ready to contribute when you can:

- [ ] Explain the difference between platform and products
- [ ] Set up local environment successfully
- [ ] Trace a request from API → Task → Flow → Database
- [ ] Understand multi-tenancy (`customer_id` vs `company_hr_dataset`)
- [ ] Follow database session management rules
- [ ] Rebuild containers correctly after code changes
- [ ] Find relevant documentation quickly

---

**Next Steps**: Read the [Main Onboarding Guide](./README.md) for comprehensive details.

