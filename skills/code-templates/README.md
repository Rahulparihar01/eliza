# Code Generation Templates

> **Purpose:** Copy-paste-ready boilerplate for common development patterns. Use these to scaffold new features quickly and consistently.

---

## Quick Reference

```
1. Find the right template  → See Available Templates below
2. Copy and customize       → Replace [PLACEHOLDERS], remove unused sections
3. Place files and register → Save to correct directories, register routes/models
```

---

## Overview

### Available Templates

| Template | Use Case | Files Created |
|----------|----------|---------------|
| **New API Endpoint** | REST API route | routes, schemas |
| **New Celery Task** | Async background processing | task, API trigger |
| **New Database Model** | SQLAlchemy model + migration | model, migration |
| **New CrewAI Flow** | AI agent workflow | flow, tools, state |
| **New Connector** | Data source integration | connector class |
| **New Frontend Page** | React page component | page, hooks, API |

### Backend Templates

| File | Creates |
|------|---------|
| `api_endpoint.py.template` | FastAPI route + Pydantic schemas |
| `celery_task.py.template` | Celery task with proper session handling |
| `database_model.py.template` | SQLAlchemy model |
| `migration.py.template` | Alembic migration |
| `service.py.template` | Business logic service class |
| `crewai_flow.py.template` | CrewAI flow with state management |
| `crewai_tool.py.template` | Custom CrewAI tool |
| `connector.py.template` | Data source connector |

### Frontend Templates

| File | Creates |
|------|---------|
| `page.tsx.template` | React page component |
| `component.tsx.template` | Reusable React component |
| `hook.ts.template` | Custom React hook |
| `sse_hook.ts.template` | SSE streaming hook |

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Copying template without checking the relevant skill | Templates provide structure; skills provide rules — always check the skill first |
| Blindly pasting without understanding | Read each section to understand what it does before customizing |
| Import paths don't match project structure | Verify import paths after pasting; use grep to find actual module locations |
| Forgetting to add tests | Templates don't include tests — add them separately |

---

## Checklist

- [ ] Checked relevant skill before using template (skills provide rules, templates provide structure)
- [ ] Replaced all `[PLACEHOLDERS]` with actual values
- [ ] Removed unused sections from template
- [ ] Verified import paths match project structure
- [ ] Ran linter after pasting to catch issues
- [ ] Added tests for new functionality

---

## References

- `skills/fastapi-endpoints/` — Rules for API endpoint development
- `skills/celery-tasks/` — Rules for async task development
- `skills/database-migrations/` — Rules for migrations and models
- `skills/crewai/` — Rules for CrewAI flow and tool development
- `skills/connectors/` — Rules for data source connector development
- `skills/design-system/` — Rules for frontend component development
