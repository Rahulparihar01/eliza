# Common Patterns from Agent Runs

> **Purpose:** Aggregated learnings from agent execution logs to inform skill updates and platform improvements.

---

## 🔄 Last Updated

**Date:** 2025-01-16  
**Runs Analyzed:** Initial setup (update as runs are logged)

---

## ✅ Patterns That Work Well

### 1. Skills-First Approach
**Pattern:** Checking relevant skill before implementation
**Success Rate:** High
**Why It Works:** Prevents common mistakes, provides correct patterns upfront

### 2. Module-Level Database Imports
**Pattern:** Using `from src.models import database` instead of direct imports
**Success Rate:** 100% when followed
**Why It Works:** Avoids stale binding issues with SessionLocal

### 3. Feature Pipeline Workflow
**Pattern:** PRD → Technical Spec → Implementation Plan
**Success Rate:** High
**Why It Works:** Clarifies requirements before coding begins

### 4. Incremental Testing
**Pattern:** Testing each component as it's built
**Success Rate:** High
**Why It Works:** Catches issues early, easier to debug

---

## ⚠️ Common Pitfalls

### 1. Direct SessionLocal Import
**Frequency:** Common in early runs
**Impact:** Tasks fail with "SessionLocal is None"
**Fix:** Always use module import pattern (see `skills/celery-tasks/`)

### 2. Missing Container Rebuild
**Frequency:** Very common
**Impact:** Code changes don't take effect
**Fix:** Always run `docker-compose build app celery-worker` after changes

### 3. Hardcoded Response Values
**Frequency:** Occasional
**Impact:** API returns None for fields that exist in database
**Fix:** Always map database fields to response model (see `skills/fastapi-endpoints/`)

### 4. BaseModel Inheritance Mismatch
**Frequency:** Occasional
**Impact:** "column does not exist" errors
**Fix:** Verify migration schema matches SQLAlchemy model (see `skills/database-migrations/`)

### 5. Missing company_hr_dataset Filter
**Frequency:** Occasional for multi-tenant features
**Impact:** Searches return wrong company's data
**Fix:** Always filter by company_hr_dataset for searches (see `skills/row-level-security/`)

---

## 📈 Efficiency Patterns

### Fast Completions (< 2 hours)
- Clear requirements in PRD
- Existing pattern to follow
- Single domain (backend only or frontend only)
- Skills consulted early

### Slow Completions (> 4 hours)
- Ambiguous requirements
- Cross-cutting concerns (backend + frontend + migrations)
- New pattern needed (no existing example)
- Skills not consulted or outdated

---

## 🎯 Skill Gaps Identified

| Gap | Frequency | Recommended Action |
|-----|-----------|-------------------|
| Testing patterns | Medium | Create `skills/testing/` |
| Frontend state management | Low | Add to `skills/design-system/` |
| Error message standardization | Medium | Create error handling guide |
| Performance optimization | Low | Future consideration |

---

## 📊 Statistics

### By Task Type
| Type | Count | Avg Duration | Success Rate |
|------|-------|--------------|--------------|
| Feature | - | - | - |
| Bugfix | - | - | - |
| Refactor | - | - | - |
| Migration | - | - | - |

### By Complexity
| Complexity | Count | Avg Duration | Success Rate |
|------------|-------|--------------|--------------|
| Simple | - | - | - |
| Moderate | - | - | - |
| Complex | - | - | - |

### Skills Most Referenced
| Skill | Times Referenced | Helpfulness |
|-------|------------------|-------------|
| `celery-tasks/` | - | - |
| `fastapi-endpoints/` | - | - |
| `database-migrations/` | - | - |

---

## 🔄 Action Items

### Skills to Update
- [ ] [Skill] - [What needs updating]

### Templates to Create
- [ ] [Template] - [Why it's needed]

### Documentation to Improve
- [ ] [Doc] - [What's missing]

---

## 📝 Notes

Add observations here as patterns emerge from run logs:

1. [Date] - [Observation]
2. [Date] - [Observation]
