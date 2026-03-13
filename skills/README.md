# Skills Directory

> **Purpose:** Centralized library of domain-specific knowledge for AI coding agents.

---

## 🎯 What Are Skills?

Skills are codified knowledge packages that AI agents should reference when working in specific domains. They contain:

- **Rules and constraints** - What to do and what to avoid
- **Patterns and examples** - How to implement common scenarios
- **Integration guidance** - How to work with existing codebase

---

## 📚 Available Skills

| Skill | Directory | Use When... |
|-------|-----------|-------------|
| **Common Actions** | `common-actions/` | Local dev, Northflank, database, debugging operations |
| **CrewAI Development** | `crewai/` | Building flows, agents, tools, or tasks |
| **Design System** | `design-system/` | Creating frontend UI components |
| **Row Level Security** | `row-level-security/` | Implementing multi-tenant data isolation |
| **Celery Tasks** | `celery-tasks/` | Creating async background tasks |
| **FastAPI Endpoints** | `fastapi-endpoints/` | Building REST API endpoints |
| **Database Migrations** | `database-migrations/` | Creating Alembic migrations and SQLAlchemy models |
| **Modular Applets** | `modular-applets/` | Adding features without breaking modular builds |
| **Connectors** | `connectors/` | Building data source connectors |
| **SSE Real-Time** | `sse-realtime/` | Streaming real-time updates to frontend |
| **Code Templates** | `code-templates/` | Scaffolding new features with copy-paste templates |
| **Troubleshooting** | `troubleshooting/` | Diagnosing and fixing common errors |

---

## 🔍 How to Use Skills

### For AI Agents

**ALWAYS check the relevant skill before implementing:**

```
1. Identify the domain of work (CrewAI, UI, multi-tenant, etc.)
2. Read the primary guide in that skill directory (e.g., CREWAI_DEVELOPMENT_RULES.md)
3. Follow the patterns and rules defined there
4. Reference supporting files for specific scenarios
```

### Skill Directory Structure

```
skills/
└── [skill-name]/
    ├── [PRIMARY_GUIDE].md      # Main reference (READ FIRST)
    ├── patterns.md             # Common implementation patterns
    └── [supporting-docs].md    # Additional context
```

---

## 📁 Quick Reference

### CrewAI Development (`skills/crewai/`)
- `CREWAI_DEVELOPMENT_RULES.md` - Core rules for flows, agents, and tools
- `flow_patterns.md` - Common flow patterns in Eliza Platform
- `tool_development.md` - How to build custom tools

### Design System (`skills/design-system/`)
- `DESIGN_SYSTEM_GUIDE.md` - Component library overview and patterns

### Row Level Security (`skills/row-level-security/`)
- `RLS_IMPLEMENTATION_GUIDE.md` - Multi-tenant isolation guide

### Celery Tasks (`skills/celery-tasks/`)
- `CELERY_TASK_DEVELOPMENT.md` - Async task patterns, session management, retry logic

### FastAPI Endpoints (`skills/fastapi-endpoints/`)
- `FASTAPI_ENDPOINT_DEVELOPMENT.md` - REST API patterns, validation, authorization

### Database Migrations (`skills/database-migrations/`)
- `DATABASE_MIGRATION_GUIDE.md` - Alembic migrations, model alignment, indexes

### Modular Applets (`skills/modular-applets/`)
- `MODULAR_APPLET_GUIDE.md` - Applet wiring, page-key gating, migration tag checks

### Connectors (`skills/connectors/`)
- `CONNECTOR_DEVELOPMENT.md` - Data source connector patterns

### SSE Real-Time (`skills/sse-realtime/`)
- `SSE_REALTIME_UPDATES.md` - Server-Sent Events for progress streaming

### Code Templates (`skills/code-templates/`)
- `README.md` - Overview of all templates
- `api_endpoint.py.template` - FastAPI route + schemas
- `celery_task.py.template` - Celery task with session handling
- `database_model.py.template` - SQLAlchemy model
- `migration.py.template` - Alembic migration
- `service.py.template` - Business logic service
- `frontend_page.tsx.template` - React page component
- `sse_hook.ts.template` - SSE streaming React hook

### Troubleshooting (`skills/troubleshooting/`)
- `ERROR_RECOVERY_PLAYBOOK.md` - Quick fixes for common errors

### Common Actions (`skills/common-actions/`)
- `COMMON_ACTIONS.md` - Local dev, Northflank, database, user management operations

---

## ➕ Creating New Skills

### When to Create a Skill

Create a new skill when:
- A domain has recurring patterns that agents need to follow
- There are critical rules that prevent bugs or security issues
- The domain is complex enough to warrant documented guidance

### Skill Template

```markdown
# [Skill Name]

## Overview
[What this skill covers and why it exists]

## Quick Start
[Most common use case with minimal code]

## Rules
[Critical constraints - what to do and avoid]

## Patterns
[Common implementation scenarios]

## Integration
[How to integrate with existing Eliza Platform code]

## References
[Links to related code, docs, external resources]
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Skill directory | `kebab-case` | `row-level-security/` |
| Primary guide | `SCREAMING_SNAKE_CASE.md` | `RLS_IMPLEMENTATION_GUIDE.md` |
| Supporting docs | `snake_case.md` | `flow_patterns.md` |

---

## 🔗 Related Resources

- **AGENTS.md** - Feature development guide (references skills)
- **`.cursorrules`** - Critical development rules (some duplicated in skills for context)
- **`cookbook/`** - CrewAI-specific development cookbook

---

**Remember:** Skills are the authoritative source for their domain. When in doubt, follow the skill guidelines.
