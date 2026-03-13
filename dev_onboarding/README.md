# Engineer Onboarding Guide - Eliza Platform

**Welcome!** This guide will help you understand the goals, architecture, and development practices of the Eliza Platform.

---

## 🎯 The Core Mission

**The Eliza Platform is designed to become one of the most AI-friendly repositories for building production-ready software.**

Our primary goals are:

1. **Validate and Improve Design Principles**: Use real-world products to validate architectural patterns and design principles across all layers of the stack
2. **Define AI Agent Patterns**: Establish and iterate on agent frameworks that enable extremely fast development of new features and products
3. **Build a Product Framework**: Create a "product and feature building framework" optimized for AI coding agents to build excellent software

**Think of this repository as:**
- A **platform** that provides core infrastructure and design patterns
- A **framework** for rapidly building new products and features
- A **laboratory** for validating architectural decisions through real implementations
- A **reference implementation** showing how to build AI-native applications correctly

---

## 🏗️ Platform vs. Products: Understanding the Boundaries

### Core Platform (Foundation Layer)

The **platform** provides reusable infrastructure and patterns that all products build upon. This is the foundation that should be **stable, well-documented, and generalized**.

**Core Platform Components:**

1. **Database Infrastructure**
   - PostgreSQL (relational data)
   - Elasticsearch (full-text search)
   - Neo4j (graph relationships)
   - FAISS (vector similarity search)
   - Redis (caching and task queues)

2. **Connector Framework**
   - Extensible `BaseConnector` class for building new data source integrations
   - Standardized interface: `check()`, `discover()`, `read_stream()`, `validate_config()`
   - Examples: People Data Labs, Greenhouse, FileSystem connectors
   - **Location**: `src/services/ingestion/connectors/`
   - **Documentation**: [`docs/connectors/README.md`](../docs/connectors/README.md)

3. **Authentication & RBAC**
   - JWT-based authentication
   - Role-Based Access Control (RBAC) with fine-grained permissions
   - Multi-tenant isolation (`customer_id` scoping)
   - **Location**: `src/core/auth.py`, `src/middleware/authorization.py`
   - **Documentation**: [`docs/api/01-authentication.md`](../docs/api/01-authentication.md)

4. **Design Patterns & Stack Layers**
   - Database connection and query patterns
   - API layer conventions (FastAPI)
   - Task execution layer (Celery)
   - Logging and observability
   - Data transmission and caching
   - Frontend component patterns

### Products Built on Platform (Application Layer)

**Products** are complete, user-facing applications that demonstrate how to use the platform effectively. They validate platform patterns through real-world usage.

**Current Products:**

1. **Talent Intelligence Tool** (`src/flows/talent_intelligence_flow.py`)
   - Analyzes job descriptions and finds ideal candidate personas
   - Dual pipeline: scores applicants from HR platforms + searches market candidates
   - Uses CrewAI agents with specialized search tools
   - **Documentation**: [`docs/talent/TALENT_INTELLIGENCE_COMPLETE.md`](../docs/talent/TALENT_INTELLIGENCE_COMPLETE.md)

2. **Business Intelligence Q&A Tool** (`src/tasks/business_intelligence_tasks.py`)
   - Natural language questions about business data
   - Task enrichment flow + data analysis flow
   - Real-time progress updates via Server-Sent Events (SSE)
   - **Documentation**: [`docs/api/02-business-intelligence.md`](../docs/api/02-business-intelligence.md)

---

## 📚 Key Documentation References

### Getting Started

- **[CrewAI Cookbook](../cookbook/README.md)** - Comprehensive guide to building AI applications with CrewAI
  - Start with [`COOKBOOK.md`](../cookbook/COOKBOOK.md) for the complete guide
  - Use [`QUICK_REFERENCE.md`](../cookbook/QUICK_REFERENCE.md) for common patterns
  - See [`08_REAL_WORLD_EXAMPLES.md`](../cookbook/08_REAL_WORLD_EXAMPLES.md) for product examples

- **[API Documentation](../docs/api/README.md)** - Complete API reference
  - Authentication, Business Intelligence, Talent Intelligence endpoints
  - Request/response formats, error handling, SSE patterns

### Architecture & Design

- **[Connector Development Guide](../docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md)** - How to build new connectors
- **[Talent Intelligence Flow](../docs/flows/TALENT_INTELLIGENCE_FLOW.md)** - Example of a complete product implementation
- **[BI Pipeline Analysis](../docs/architecture/BI_PIPELINE_ANALYSIS.md)** - Architecture deep-dive

### Critical Rules & Patterns

- **[Repository Rules](../.cursorrules)** - Critical development rules (database sessions, imports, containers, etc.)
- **[CrewAI Quick Reference](../cookbook/QUICK_REFERENCE.md)** - Common patterns and anti-patterns

---

## 🏛️ Architecture Overview

### Stack Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  - Component library and UI patterns                     │
│  - Real-time updates via SSE                             │
└─────────────────────────────────────────────────────────┘
                        ↓ HTTP/SSE
┌─────────────────────────────────────────────────────────┐
│              API Layer (FastAPI)                        │
│  - REST endpoints                                        │
│  - Authentication & RBAC                                 │
│  - Request validation                                    │
└─────────────────────────────────────────────────────────┘
                        ↓ Celery Tasks
┌─────────────────────────────────────────────────────────┐
│         Task Execution Layer (Celery Workers)           │
│  - Async task processing                                 │
│  - Flow orchestration                                   │
│  - Error handling & retries                             │
└─────────────────────────────────────────────────────────┘
                        ↓ Flow Execution
┌─────────────────────────────────────────────────────────┐
│            AI Agent Layer (CrewAI Flows)                │
│  - Multi-agent workflows                                │
│  - Tool integration                                      │
│  - State management                                      │
└─────────────────────────────────────────────────────────┘
                        ↓ Tool Execution
┌─────────────────────────────────────────────────────────┐
│              Services & Tools Layer                     │
│  - Document search tools                                 │
│  - Database services                                     │
│  - Vector search services                                │
│  - Connector services                                    │
└─────────────────────────────────────────────────────────┘
                        ↓ Data Access
┌─────────────────────────────────────────────────────────┐
│              Data Layer (Databases)                      │
│  - PostgreSQL (relational)                               │
│  - Elasticsearch (full-text)                             │
│  - Neo4j (graph)                                         │
│  - FAISS (vectors)                                       │
│  - Redis (cache/queue)                                   │
└─────────────────────────────────────────────────────────┘
```

### Design Principles by Layer

#### a. Database Connection and Query
- **Pattern**: Always check `SessionLocal` initialization before use
- **Rule**: Never store database sessions in serializable state (breaks Celery)
- **Pattern**: Use module imports (`from src.models import database`) not direct imports
- **Reference**: See [Repository Rules](../.cursorrules) - Rules 1-4

#### b. API Layer
- **Pattern**: FastAPI routers with dependency injection
- **Pattern**: Pydantic models for request/response validation
- **Pattern**: Permission decorators: `@Depends(auth_middleware.require_permission("resource:action"))`
- **Location**: `src/api/routes/`
- **Example**: [`src/api/routes/business_intelligence.py`](../src/api/routes/business_intelligence.py)

#### c. Task Execution Layer
- **Pattern**: Celery tasks for async processing
- **Pattern**: Return immediately with `202 Accepted` status
- **Pattern**: Use task IDs for status tracking
- **Location**: `src/tasks/`
- **Example**: [`src/tasks/business_intelligence_tasks.py`](../src/tasks/business_intelligence_tasks.py)

#### d. Logging
- **Pattern**: Structured logging with `structlog`
- **Pattern**: Include context: `user_id`, `customer_id`, `operation_name`
- **Pattern**: Log at state transitions (create, update, complete, fail)
- **Location**: `src/core/logging.py`

#### e. Data Transmission and Caching
- **Pattern**: Server-Sent Events (SSE) for real-time updates
- **Pattern**: Redis for caching and task queues
- **Pattern**: Multi-tenant data isolation via `customer_id` and `company_hr_dataset`
- **Example**: [`src/api/routes/business_intelligence.py`](../src/api/routes/business_intelligence.py) - SSE endpoint

#### f. Authentication and RBAC
- **Pattern**: JWT tokens with refresh mechanism
- **Pattern**: Fine-grained permissions: `resource:action` format
- **Pattern**: Multi-tenant isolation at database query level
- **Location**: `src/core/auth.py`, `src/middleware/authorization.py`
- **Documentation**: [`docs/api/01-authentication.md`](../docs/api/01-authentication.md)

#### g. Frontend Component Usage
- **Pattern**: Reusable React components with TypeScript
- **Pattern**: Orval-generated API clients from OpenAPI spec
- **Pattern**: Real-time updates via EventSource (SSE)
- **Location**: `frontend/src/components/`
- **Documentation**: [`docs/ui/`](../docs/ui/)

---

## 🎓 Learning Path for New Engineers

### Week 1: Understanding the Foundation

1. **Read Core Documentation**
   - [ ] Read this onboarding guide completely
   - [ ] Review [Cookbook README](../cookbook/README.md)
   - [ ] Skim [Repository Rules](../.cursorrules) - understand critical patterns
   - [ ] Read [API Documentation Overview](../docs/api/README.md)

2. **Explore the Codebase Structure**
   - [ ] Understand `src/` directory organization
   - [ ] Review `src/models/` - database models
   - [ ] Review `src/api/routes/` - API endpoints
   - [ ] Review `src/services/` - business logic layer
   - [ ] Review `src/flows/` and `src/crewai_flows/` - AI agent workflows

3. **Set Up Local Environment**
   - [ ] Follow [README.md](../README.md) setup instructions
   - [ ] Run Docker Compose setup
   - [ ] Access API docs at `http://localhost:5001/docs`
   - [ ] Test authentication flow

### Week 2: Deep Dive into Products

1. **Study Talent Intelligence Product**
   - [ ] Read [`docs/talent/TALENT_INTELLIGENCE_COMPLETE.md`](../docs/talent/TALENT_INTELLIGENCE_COMPLETE.md)
   - [ ] Trace flow: API → Celery Task → CrewAI Flow → Tools → Database
   - [ ] Review [`src/flows/talent_intelligence_flow.py`](../src/flows/talent_intelligence_flow.py)
   - [ ] Understand dual pipeline architecture (applicants + market search)

2. **Study Business Intelligence Product**
   - [ ] Read [`docs/api/02-business-intelligence.md`](../docs/api/02-business-intelligence.md)
   - [ ] Review [`src/tasks/business_intelligence_tasks.py`](../src/tasks/business_intelligence_tasks.py)
   - [ ] Understand task enrichment flow pattern
   - [ ] Study SSE telemetry implementation

3. **Understand Connector Framework**
   - [ ] Read [`docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md`](../docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md)
   - [ ] Review [`src/services/ingestion/connectors/base.py`](../src/services/ingestion/connectors/base.py)
   - [ ] Study example connectors (PDL, Greenhouse, FileSystem)

### Week 3: Platform Patterns & Best Practices

1. **Database Patterns**
   - [ ] Study database session management (Rules 1-4 in `.cursorrules`)
   - [ ] Review SQLAlchemy model patterns in `src/models/`
   - [ ] Understand migration workflow (Alembic)

2. **API Patterns**
   - [ ] Review FastAPI router patterns
   - [ ] Study authentication middleware
   - [ ] Understand RBAC permission system
   - [ ] Review error handling patterns

3. **CrewAI Flow Patterns**
   - [ ] Read [`cookbook/02_CORE_ARCHITECTURE_PATTERNS.md`](../cookbook/02_CORE_ARCHITECTURE_PATTERNS.md)
   - [ ] Study state management patterns
   - [ ] Understand tool integration
   - [ ] Review real-world examples in [`cookbook/08_REAL_WORLD_EXAMPLES.md`](../cookbook/08_REAL_WORLD_EXAMPLES.md)

### Week 4: Ready to Contribute

1. **Identify Contribution Areas**
   - [ ] Review open issues/PRs
   - [ ] Identify areas for improvement in platform patterns
   - [ ] Consider new connector implementations
   - [ ] Look for opportunities to validate design principles

2. **Start Small**
   - [ ] Fix a bug or add a small feature
   - [ ] Add tests for existing functionality
   - [ ] Improve documentation
   - [ ] Refactor code following established patterns

---

## 🚦 What Should Engineers Focus On?

### ✅ DO: Platform Improvements

- **Enhance Core Infrastructure**: Improve database patterns, connector framework, auth system
- **Validate Design Principles**: Build new products that test platform patterns
- **Document Patterns**: Add examples and documentation for common use cases
- **Improve Developer Experience**: Make it easier for AI agents to build on the platform
- **Optimize Performance**: Improve query performance, caching strategies, agent efficiency

### ✅ DO: Build New Products

- **Use Platform Components**: Leverage existing connectors, auth, database patterns
- **Follow Established Patterns**: Use the same patterns as Talent Intelligence and BI tools
- **Validate Platform**: Test that platform components work well for new use cases
- **Document Learnings**: Share insights about what works and what doesn't

### ❌ DON'T: Break Platform Boundaries

- **Don't Modify Core Platform Without Discussion**: Core infrastructure changes affect all products
- **Don't Create Product-Specific Platform Code**: Keep platform generalized
- **Don't Skip Documentation**: Every new pattern should be documented
- **Don't Ignore Existing Patterns**: Follow established conventions

---

## 🔍 Key Concepts to Understand

### Multi-Tenancy

- **Customer ID**: Top-level tenant isolation (`customer_id`)
- **Company HR Dataset**: Sub-tenant isolation for company-specific data (`company_hr_dataset`)
- **Data Filtering**: All queries must filter by `customer_id` and optionally `company_hr_dataset`
- **Reference**: See [Repository Rules](../.cursorrules) - Rule 11

### CrewAI Flow Architecture

- **Flows**: Multi-step workflows with `@start()` and `@listen()` decorators
- **Agents**: Specialized AI agents with roles, goals, and tools
- **State Management**: Pydantic models for state passed between steps
- **Tool Integration**: Custom tools that connect agents to databases and services
- **Reference**: [`cookbook/02_CORE_ARCHITECTURE_PATTERNS.md`](../cookbook/02_CORE_ARCHITECTURE_PATTERNS.md)

### Async Task Processing

- **Pattern**: API endpoint queues Celery task → returns immediately
- **Status Tracking**: Use task IDs and database records for status
- **Real-Time Updates**: SSE endpoints for progress telemetry
- **Error Handling**: Retry logic, error logging, status updates
- **Reference**: [`cookbook/03_INTEGRATION_PATTERNS.md`](../cookbook/03_INTEGRATION_PATTERNS.md)

### Connector Framework

- **Base Class**: `BaseConnector` provides standard interface
- **Methods**: `check()`, `discover()`, `read_stream()`, `validate_config()`
- **Registry**: Connectors registered in `CONNECTOR_REGISTRY`
- **Extensibility**: Easy to add new connectors following the pattern
- **Reference**: [`docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md`](../docs/connectors/20251024_CONNECTOR_DEVELOPMENT_GUIDE.md)

---

## 🛠️ Development Workflow

### Making Changes

1. **Understand the Impact**
   - Is this a platform change or product change?
   - Does it affect multiple products?
   - Does it follow established patterns?

2. **Follow Patterns**
   - Review similar implementations
   - Check repository rules
   - Use existing code as reference

3. **Test Thoroughly**
   - Test locally with Docker Compose
   - Verify database migrations
   - Test API endpoints
   - Verify Celery tasks work

4. **Document Changes**
   - Update relevant documentation
   - Add examples if introducing new patterns
   - Update API docs if changing endpoints

### Common Commands

```bash
# Start development environment
docker-compose up -d

# Rebuild after code changes (CRITICAL!)
docker-compose build app celery-worker
docker-compose up -d app celery-worker

# View logs
docker-compose logs -f app celery-worker

# Run database migrations
docker-compose exec app alembic upgrade head

# Access API docs
open http://localhost:5001/docs
```

**⚠️ Critical**: Always rebuild containers after code changes! `docker-compose restart` uses old images.

---

## 📖 Additional Resources

### Internal Documentation

- **[Cookbook](../cookbook/)** - Complete CrewAI development guide
- **[API Docs](../docs/api/)** - API reference and examples
- **[Architecture Docs](../docs/architecture/)** - Deep architectural analysis
- **[Design Docs](../design_docs/)** - Design specifications and planning

### External Resources

- [CrewAI Documentation](https://docs.crewai.com) - Official CrewAI framework docs
- [FastAPI Documentation](https://fastapi.tiangolo.com) - FastAPI framework reference
- [Celery Documentation](https://docs.celeryproject.org) - Celery task queue docs

---

## ❓ Questions?

If you have questions about:

- **Architecture decisions**: Review design docs and architecture documentation
- **Development patterns**: Check the cookbook and repository rules
- **API usage**: See API documentation
- **Specific implementations**: Review existing product code (Talent Intelligence, BI)

**Remember**: The goal is to build a platform that makes it easy for AI agents to build excellent software. Every decision should support that goal.

---

## 🎯 Success Metrics

You'll know you're contributing effectively when:

1. ✅ You can build new features following established patterns
2. ✅ You understand the distinction between platform and products
3. ✅ You can identify opportunities to improve platform patterns
4. ✅ Your code follows repository rules and conventions
5. ✅ You're documenting new patterns for future engineers

**Welcome to the team! Let's build something amazing.** 🚀

