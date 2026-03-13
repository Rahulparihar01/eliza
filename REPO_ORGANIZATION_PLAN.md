# Repo Organization & Skills Development Plan

**Branch:** `feature/repo-organization-and-skills`  
**Created:** January 16, 2026  
**Off of:** `dev` (commit: `dd972469`)

---

## 🎯 Objectives

1. **Create a Skills Directory** - Centralized location for reusable knowledge that AI agents should reference
2. **Build Three Core Skills** - CrewAI Rules, Design System Components, Row Level Security
3. **Establish Feature Development Workflow** - Structured path from Product Spec → Technical Spec → Implementation Plan
4. **Update AGENTS.md** - Ensure agents always check skills folder for relevant domain knowledge
5. **Clean Up Repository** - Remove clutter, organize documentation, improve discoverability

---

## 📁 Proposed Directory Structure

```
skills/                              # NEW - AI Agent Skills Library
├── README.md                        # How to use and create skills
├── crewai/                          # CrewAI Development Rules
│   ├── CREWAI_DEVELOPMENT_RULES.md  # Core rules for CrewAI development
│   ├── flow_patterns.md             # Common flow patterns
│   └── tool_development.md          # Tool creation guidelines
├── design-system/                   # Frontend Design System
│   ├── DESIGN_SYSTEM_GUIDE.md       # Component library overview
│   ├── component_patterns.md        # Reusable component patterns
│   └── theming.md                   # Theme tokens and variables
└── row-level-security/              # Multi-tenant RLS
    ├── RLS_IMPLEMENTATION_GUIDE.md  # How to implement RLS
    ├── patterns.md                  # Common RLS patterns
    └── testing.md                   # Testing RLS policies
```

---

## 🔄 Feature Development Workflow

### Overview

Every feature follows a three-stage development pipeline:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FEATURE DEVELOPMENT PIPELINE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐      ┌──────────────┐      ┌──────────────────┐          │
│  │ PRODUCT SPEC │ ───► │ TECHNICAL    │ ───► │ IMPLEMENTATION   │          │
│  │    (PRD)     │      │    SPEC      │      │      PLAN        │          │
│  └──────────────┘      └──────────────┘      └──────────────────┘          │
│         │                     │                       │                     │
│         ▼                     ▼                       ▼                     │
│   Business needs        Architecture &          Task breakdown              │
│   User stories          API contracts           Execution order             │
│   Success metrics       Data models             Time estimates              │
│   Acceptance criteria   Integration points      Dependencies                │
│                         Agent analysis          Checkpoints                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Stage 1: Product Spec (PRD)
**Input:** Business requirements, stakeholder needs  
**Output:** `01_PRODUCT_SPEC.md`

- Executive summary & problem statement
- Goals and non-goals
- Target users and personas
- User stories and acceptance criteria
- Success metrics
- Open questions

### Stage 2: Technical Spec
**Input:** Product Spec + Development Agent review  
**Output:** `02_TECHNICAL_SPEC.md`

The development agent:
1. Reviews the PRD and asks clarifying questions
2. Identifies edge cases and risks
3. Proposes architecture and data models
4. Defines API contracts
5. Maps integration points with existing systems
6. Outputs a hardened technical specification

### Stage 3: Implementation Plan
**Input:** Technical Spec  
**Output:** `03_IMPLEMENTATION_PLAN.md`

- Ordered task breakdown
- File-by-file changes required
- Database migrations needed
- Test requirements
- Estimated time per task
- Checkpoints and milestones
- Rollback procedures

---

## 📁 Features Directory Structure

```
features/                                    # NEW - Feature Development Hub
├── README.md                               # Workflow guide & templates location
├── _templates/                             # Document templates
│   ├── 01_PRODUCT_SPEC_TEMPLATE.md
│   ├── 02_TECHNICAL_SPEC_TEMPLATE.md
│   └── 03_IMPLEMENTATION_PLAN_TEMPLATE.md
│
├── active/                                 # Features currently in development
│   └── clearhaven-portfolio-intelligence/  # Example feature
│       ├── 01_PRODUCT_SPEC.md
│       ├── 02_TECHNICAL_SPEC.md           # Generated after agent review
│       ├── 03_IMPLEMENTATION_PLAN.md      # Generated from tech spec
│       └── assets/                         # Diagrams, mockups, etc.
│           └── user_flow_diagram.md
│
├── completed/                              # Shipped features (reference)
│   └── talent-intelligence/
│       ├── 01_PRODUCT_SPEC.md
│       ├── 02_TECHNICAL_SPEC.md
│       └── 03_IMPLEMENTATION_PLAN.md
│
└── backlog/                                # Future features (PRDs only)
    └── voice-reference-checks/
        └── 01_PRODUCT_SPEC.md
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Feature folder | `kebab-case` | `clearhaven-portfolio-intelligence/` |
| Documents | Numbered prefix | `01_PRODUCT_SPEC.md`, `02_TECHNICAL_SPEC.md` |
| Assets folder | `assets/` | Contains diagrams, mockups |
| Status | Directory location | `active/`, `completed/`, `backlog/` |

### Feature Lifecycle

```
backlog/                    # PRD drafted, waiting for prioritization
    │
    ▼
active/                     # In development (has all 3 docs)
    │
    ▼
completed/                  # Shipped (kept for reference)
```

---

## 📋 Phase 1: Skills Directory Setup

### 1.1 Create Skills Directory Structure
- [ ] Create `skills/` root directory
- [ ] Create `skills/README.md` with usage instructions
- [ ] Create subdirectories for each skill domain

### 1.2 Skills README Contents
The skills README should explain:
- What skills are and why they exist
- How AI agents should discover and use skills
- How to create new skills
- Skill naming conventions

---

## 📋 Phase 2: Build Core Skills

### 2.1 CrewAI Rules Skill (`skills/crewai/`)

**Purpose:** Codify patterns, rules, and best practices for CrewAI development in this codebase.

**Contents:**
1. **CREWAI_DEVELOPMENT_RULES.md** (Primary)
   - Database session management (module imports, not direct imports)
   - State management (never store non-serializable objects)
   - Tool development patterns
   - Flow vs Crew decision matrix
   - Error handling in flows
   - Testing flows

2. **flow_patterns.md**
   - Multi-step analysis flows
   - Parallel execution patterns
   - State persistence patterns
   - SSE event emission

3. **tool_development.md**
   - Tool interface requirements
   - Input/output validation
   - Error handling
   - Integration with services

**Source Material:**
- `.cursorrules` (rules 1-4, 11-13)
- `cookbook/COOKBOOK.md`
- `cookbook/02_CORE_ARCHITECTURE_PATTERNS.md`
- `src/flows/*.py` (existing flow implementations)
- `src/crewai_custom_tools/*.py` (existing tools)

---

### 2.2 Design System Component Skill (`skills/design-system/`)

**Purpose:** Document the frontend design system for consistent UI development.

**Contents:**
1. **DESIGN_SYSTEM_GUIDE.md** (Primary)
   - Component library overview
   - Available components and their props
   - Styling conventions (Tailwind + CSS variables)
   - Accessibility requirements
   - When to use shared components vs custom

2. **component_patterns.md**
   - Form patterns (validation, error states)
   - Table/list patterns
   - Modal/dialog patterns
   - Loading/error states
   - Toast notifications

3. **theming.md**
   - Color tokens and their meanings
   - Spacing scale
   - Typography scale
   - Dark mode considerations
   - Animation/transition standards

**Source Material:**
- `frontend/src/shared/ui/*.tsx` (existing shared components)
- `frontend/src/components/common/*.tsx` (common components)
- `frontend/src/index.css` (CSS variables)
- `frontend/tailwind.config.js` (Tailwind configuration)

---

### 2.3 Row Level Security Skill (`skills/row-level-security/`)

**Purpose:** Document RLS implementation for multi-tenant data isolation.

**Contents:**
1. **RLS_IMPLEMENTATION_GUIDE.md** (Primary)
   - RLS architecture overview
   - When RLS is required vs optional
   - Implementation checklist for new tables
   - Integration with SQLAlchemy
   - Testing requirements

2. **patterns.md**
   - Tenant isolation patterns
   - Platform admin access patterns
   - Cross-tenant reporting
   - Audit logging patterns
   - Migration patterns for adding RLS

3. **testing.md**
   - How to test RLS policies
   - Test fixtures for multi-tenant scenarios
   - Verifying isolation in integration tests
   - Common testing pitfalls

**Source Material:**
- `docs/specs/multi-tenant-rls.md` (comprehensive RLS doc)
- `src/middleware/tenant_context.py` (tenant context implementation)
- `alembic/versions/b6c7d8e9f0a1_add_rls_and_enhanced_audit.py` (RLS migration)
- `tests/security/test_tenant_isolation.py` (isolation tests)

---

## 📋 Phase 3: Update AGENTS.md

### 3.1 Add Skills Discovery Section

Add a new section to `AGENTS.md` instructing agents to:
1. **Always check `skills/` directory** before implementing features in these domains
2. **Reference the skills README** for skill discovery
3. **Follow skill guidelines** as authoritative for their domains

### 3.2 Update Quick Reference Table

Add skills to the quick reference:
```
| Need to...                | Look at...                            |
|---------------------------|---------------------------------------|
| Build CrewAI flow         | `skills/crewai/`, `cookbook/`         |
| Build UI component        | `skills/design-system/`, `frontend/`  |
| Implement multi-tenancy   | `skills/row-level-security/`          |
```

---

## 📋 Phase 4: Features Directory & Templates

### 4.1 Create Features Directory Structure
- [ ] Create `features/` root directory
- [ ] Create `features/README.md` with workflow guide
- [ ] Create `features/_templates/` directory
- [ ] Create `features/active/` directory
- [ ] Create `features/completed/` directory
- [ ] Create `features/backlog/` directory

### 4.2 Create Document Templates

#### 4.2.1 Product Spec Template (`01_PRODUCT_SPEC_TEMPLATE.md`)
```markdown
# Product Requirements Document
## [Feature Name]

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft / In Review / Approved |
| **Last Updated** | [Date] |
| **Product Owner** | [Name] |
| **Engineering Lead** | [Name] |

## Executive Summary
[2-3 sentences describing what this feature does and why it matters]

## Problem Statement
### Current State Challenges
[What problems exist today?]

### The Opportunity
[What value does solving this create?]

## Goals and Non-Goals
### Goals (P0/P1/P2)
| Priority | Goal |
|----------|------|
| P0 | [Must have for MVP] |
| P1 | [Should have] |
| P2 | [Nice to have] |

### Non-Goals (Out of Scope)
| Item | Rationale |
|------|-----------|
| [Feature X] | [Why it's excluded] |

## Target Users
[Who will use this? What are their needs?]

## User Stories
- As a [user type], I want to [action] so that [benefit]

## Feature Details
[Detailed description of the feature]

## Technical Requirements (High-Level)
[Any known technical constraints or requirements]

## Dependencies
[External systems, APIs, or features this depends on]

## Acceptance Criteria
- [ ] [Specific, testable criteria]

## Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| [Metric name] | [Target value] | [How to measure] |

## Open Questions
- [ ] [Unresolved questions that need answers]

## Appendix
[Additional context, mockups, references]
```

#### 4.2.2 Technical Spec Template (`02_TECHNICAL_SPEC_TEMPLATE.md`)
```markdown
# Technical Specification
## [Feature Name]

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Draft / Reviewed / Approved |
| **Last Updated** | [Date] |
| **PRD Reference** | [Link to 01_PRODUCT_SPEC.md] |
| **Author** | [Engineering Lead / Development Agent] |

## Overview
[Summary of technical approach based on PRD requirements]

## Architecture

### System Context
[How this feature fits into the existing system]

### Component Diagram
```
[ASCII or Mermaid diagram of components]
```

### Data Flow
[How data moves through the system]

## Data Model

### New Tables
```sql
CREATE TABLE [table_name] (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,  -- Multi-tenant
    [columns...]
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Modified Tables
[Existing tables that need changes]

### Indexes
[Required indexes for performance]

## API Design

### New Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/[resource]` | [Description] |
| GET | `/api/v1/[resource]/{id}` | [Description] |

### Request/Response Models
```python
class [Resource]Request(BaseModel):
    [field]: [type]

class [Resource]Response(BaseModel):
    [field]: [type]
```

## Integration Points

### Existing Services
| Service | Usage |
|---------|-------|
| [Service name] | [How it's used] |

### External APIs
[Third-party integrations required]

## Security Considerations

### Authentication & Authorization
[How access is controlled]

### Row Level Security
[RLS policies needed - reference `skills/row-level-security/`]

### Data Validation
[Input validation requirements]

## Error Handling
| Error Case | Handling |
|------------|----------|
| [Scenario] | [How it's handled] |

## Performance Considerations
- [Caching strategy]
- [Query optimization]
- [Rate limiting]

## Testing Strategy
- Unit tests for [components]
- Integration tests for [flows]
- E2E tests for [user journeys]

## Migration Strategy
[How to deploy without breaking existing functionality]

## Open Technical Questions
- [ ] [Resolved during agent review]

## Agent Review Notes
[Questions asked and decisions made during technical review]
```

#### 4.2.3 Implementation Plan Template (`03_IMPLEMENTATION_PLAN_TEMPLATE.md`)
```markdown
# Implementation Plan
## [Feature Name]

| **Document Version** | 1.0 |
|---------------------|-----|
| **Status** | Ready / In Progress / Complete |
| **Last Updated** | [Date] |
| **Tech Spec Reference** | [Link to 02_TECHNICAL_SPEC.md] |
| **Estimated Total Time** | [X hours/days] |

## Prerequisites
- [ ] [Dependencies that must be complete first]
- [ ] [Environment setup required]

## Implementation Phases

### Phase 1: [Phase Name] (Est: X hours)

#### Task 1.1: [Task Name]
**Files:**
- `src/models/[file].py` - [Change description]
- `src/api/routes/[file].py` - [Change description]

**Changes:**
1. [Specific change 1]
2. [Specific change 2]

**Tests:**
- [ ] Unit test: [test description]

**Checkpoint:** [How to verify this task is complete]

---

#### Task 1.2: [Task Name]
[Same structure...]

---

### Phase 2: [Phase Name] (Est: X hours)
[Tasks...]

---

## Database Migrations

### Migration 1: [Description]
```python
def upgrade():
    # [Migration code]

def downgrade():
    # [Rollback code]
```

**Run order:** [When to run relative to code deployment]

---

## Deployment Checklist

### Pre-Deployment
- [ ] All tests passing
- [ ] Migration tested locally
- [ ] Feature flag configured (if applicable)

### Deployment Steps
1. [ ] Run database migrations
2. [ ] Deploy backend changes
3. [ ] Deploy frontend changes
4. [ ] Verify health checks

### Post-Deployment Verification
- [ ] [Specific verification step]
- [ ] Monitor error rates for [X minutes]

## Rollback Plan
1. [Step to rollback if issues occur]
2. [Database rollback if needed]

## Progress Tracking

| Phase | Task | Status | Assignee | Notes |
|-------|------|--------|----------|-------|
| 1 | Task 1.1 | ⬜ Not Started | | |
| 1 | Task 1.2 | ⬜ Not Started | | |
| 2 | Task 2.1 | ⬜ Not Started | | |

**Status Legend:** ⬜ Not Started | 🟡 In Progress | ✅ Complete | ❌ Blocked
```

### 4.3 Migrate Existing PRDs
- [ ] Move `design_docs/PRD_CLEARHAVEN_PORTFOLIO_INTELLIGENCE.md` → `features/active/clearhaven-portfolio-intelligence/01_PRODUCT_SPEC.md`
- [ ] Create placeholder `02_TECHNICAL_SPEC.md` and `03_IMPLEMENTATION_PLAN.md` for in-progress features

---

## 📋 Phase 5: Repository Cleanup

### 5.1 Root-Level Session Files
There are ~60 session files (e.g., `20251013_SESSION_COMPLETE_SUMMARY.md`) in the root directory. These should be:
- [ ] Moved to `docs/sessions/` or `docs/archive/`
- [ ] Or added to `.gitignore` if they're personal notes

**Files to move:**
- `20251013_*.md` through `20251020_*.md` (session summaries)
- `*_STATUS.md`, `*_COMPLETE.md`, `*_FIX.md` files
- Test result files (`*_test_results.txt`, etc.)

### 5.2 Test Artifacts
These files appear to be test artifacts that shouldn't be in version control:
- `test_document.txt`
- `test_job_description.txt`
- `test_results.txt`
- `test_results_latest.txt`
- `*_test_output.txt` files

Options:
- [ ] Add to `.gitignore`
- [ ] Move to `tests/fixtures/` if they're test fixtures
- [ ] Delete if they're temporary artifacts

### 5.3 Backup Files
SQL backups should not be in version control:
- `backup_predeploy_20251006_145349.sql`
- `backup_predeploy_20251006_145356.sql`

- [ ] Add `*.sql` backup patterns to `.gitignore`
- [ ] Remove existing backups from git history (optional)

### 5.4 Documentation Organization

**Current Issues:**
- `docs/` has both dated files (e.g., `20251024_*.md`) and organized subdirectories
- Design docs in `design_docs/` could be merged with `docs/specs/` or `docs/architecture/`

**Proposed Structure:**
```
docs/
├── README.md
├── api/                    # API documentation (keep)
├── architecture/           # System architecture (keep)
├── connectors/             # Connector guides (keep)
├── engineering/            # Engineering guides (keep)
├── features/               # Feature documentation (keep)
├── flows/                  # Flow documentation (keep)
├── specs/                  # Technical specifications (keep)
├── sessions/               # NEW - Session summaries moved here
│   └── 2025-10/            # Organized by month
└── archive/                # NEW - Old/outdated docs
```

---

## 📋 Phase 6: Update .cursorrules

### 6.1 Add Skills and Features Reference Rules
Add new rules to `.cursorrules`:

```
### Rule 20: Check Skills Directory for Domain Knowledge
**Context:** The skills directory contains codified knowledge for specific domains.

**ALWAYS:**
1. Before implementing CrewAI flows/tools → Check `skills/crewai/`
2. Before creating UI components → Check `skills/design-system/`
3. Before adding multi-tenant features → Check `skills/row-level-security/`

The skills directory is the authoritative source for patterns in these domains.

### Rule 21: Follow Feature Development Workflow
**Context:** All features follow a structured three-stage pipeline: Product Spec → Technical Spec → Implementation Plan.

**ALWAYS:**
1. Check `features/active/` for the current feature you're working on
2. Reference the Technical Spec (02_TECHNICAL_SPEC.md) for architecture decisions
3. Follow the Implementation Plan (03_IMPLEMENTATION_PLAN.md) for task execution
4. Update progress in the Implementation Plan as tasks complete

**FILE LOCATIONS:**
- Features in development: `features/active/[feature-name]/`
- Completed features: `features/completed/[feature-name]/`
- Templates: `features/_templates/`

**DOCUMENT HIERARCHY:**
- Product Spec defines WHAT to build
- Technical Spec defines HOW to build it
- Implementation Plan defines the EXECUTION ORDER
```

---

## 📊 Implementation Order

| Order | Task | Est. Time | Dependencies |
|-------|------|-----------|--------------|
| 1 | Create skills directory structure | 10 min | None |
| 2 | Write skills/README.md | 20 min | #1 |
| 3 | Build CrewAI Rules skill | 45 min | #1, #2 |
| 4 | Build Design System skill | 45 min | #1, #2 |
| 5 | Build RLS skill | 30 min | #1, #2 |
| 6 | Create features directory structure | 10 min | None |
| 7 | Create feature document templates | 30 min | #6 |
| 8 | Write features/README.md (workflow guide) | 20 min | #6, #7 |
| 9 | Migrate existing PRD(s) to features/ | 10 min | #6 |
| 10 | Update AGENTS.md | 20 min | #3, #4, #5, #8 |
| 11 | Update .cursorrules | 15 min | #10 |
| 12 | Move session files to archive | 15 min | None |
| 13 | Clean up test artifacts | 10 min | None |
| 14 | Update .gitignore | 5 min | #12, #13 |

**Total Estimated Time:** ~4.5 hours

---

## ✅ Success Criteria

1. **Skills are discoverable**: AI agents can find relevant skills via `skills/README.md`
2. **Skills are comprehensive**: Each skill contains enough context for autonomous implementation
3. **Feature workflow is clear**: Three-stage pipeline is documented and templates exist
4. **Existing PRDs are migrated**: All product specs are in `features/` with proper structure
5. **AGENTS.md references skills + features**: Clear guidance on when to check each directory
6. **Root directory is clean**: No more than 10 non-essential files in root
7. **Documentation is organized**: Clear separation between specs, guides, and session notes

---

## 🚧 Out of Scope

These items are intentionally not included in this cleanup:
- Refactoring existing code
- Changing the src/ structure
- Modifying the frontend component library itself
- Adding new features
- Database schema changes

---

## 📝 Notes

- Skills should be written as reference material, not tutorials
- Each skill should have a "Quick Start" section for common use cases
- Skills should reference existing code examples in the codebase
- Keep skills concise - link to detailed docs rather than duplicating

---

**Next Steps:** Review this plan and confirm before proceeding with implementation.
