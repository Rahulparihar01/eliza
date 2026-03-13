# Eliza Platform - Development Workflow & Code Promotion

## Platform Architecture Overview

The Eliza Platform follows a **two-layer architecture** with clear separation between shared platform capabilities and the solutions built on top:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SOLUTIONS                                      │
│                                                                             │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐    │
│  │    AI     │ │    AI     │ │ Reference │ │ Analytics │ │  Engage   │    │
│  │ Assistant │ │ Recruiter │ │  Checks   │ │ Dashboard │ │           │    │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘ └───────────┘    │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                        PLATFORM CAPABILITIES                                │
│                                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ Auth &   │ │  Data    │ │  Vector  │ │  Agent   │ │  Audit   │         │
│  │Multi-Tent│ │Connectors│ │  Search  │ │Framework │ │ Logging  │         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │   RBAC   │ │ Document │ │Task Queue│ │  Graph   │ │   API    │         │
│  │Permissions│ │Processing│ │ (Celery) │ │  (Neo4j) │ │ Gateway  │         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer 1: Platform Capabilities
Shared foundational functionality used by all solutions:
- **Auth & Multi-Tenancy**: Authentication, authorization, tenant isolation
- **Data Connectors**: Integrations with external systems (Greenhouse, PDL, etc.)
- **Vector Search**: Semantic search and document retrieval
- **Agent Framework**: CrewAI-based agent orchestration
- **Audit Logging**: Compliance and activity tracking
- **RBAC/Permissions**: Role-based access control
- **Document Processing**: Parsing, chunking, embedding
- **Task Queue**: Background job processing (Celery)
- **Graph Database**: Relationship mapping (Neo4j)
- **API Gateway**: Request routing, rate limiting

### Layer 2: Solutions
Features and products built on top of platform capabilities:
- **AI Assistant**: Document Q&A, business intelligence queries
- **AI Recruiter**: Talent intelligence, candidate scoring, market search, outreach automation
- **Reference Checks**: Automated reference collection and analysis
- **Analytics Dashboard**: Metrics, reporting, and operational insights
- **Engage**: Candidate and client engagement workflows

---

## Development Workflow

### 1. Feature Specification

| Stage | Tool/Process | Description |
|-------|--------------|-------------|
| **Ideation** | Conversational AI Assistant (Custom GPT) | Interactive spec building through conversation |
| **Enrichment** | Rules-Based Enrichment | Automated enrichment of specs with platform standards, security requirements, and integration patterns |
| **Output** | Feature Spec Document | Complete specification ready for development |

### 2. Feature Development (Distributed Model)

```
         ┌─────────────────────────────────────────────────┐
         │                   main (prod)                   │
         └─────────────────────────────────────────────────┘
                              │
                              ▼
         ┌─────────────────────────────────────────────────┐
         │                 dev (integration)               │◄──── Changelog to Slack
         └─────────────────────────────────────────────────┘
              │           │           │           │
              ▼           ▼           ▼           ▼
         ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
         │feature/│  │feature/│  │feature/│  │feature/│
         │  auth  │  │recruit │  │connect │  │ applet │
         │        │  │        │  │        │  │        │
         │ Dev A  │  │ Dev B  │  │ Dev C  │  │ Dev D  │
         └────────┘  └────────┘  └────────┘  └────────┘
```

**Branch Strategy:**
- Developers branch from `dev` (integration branch)
- Each developer works in **isolated feature branches**
- `dev` changelog posted to **shared Slack channel** so all feature developers stay informed of platform changes
- Feature branches are short-lived and focused

---

## Code Review Process

### Automated Review (Agentic)

| Check | Description |
|-------|-------------|
| **Secrets Scanner** | AI agent reviews for sensitive information (API keys, secrets, passwords, credentials) |
| **Migration Validator** | Ensures Alembic migrations are properly merged and sequenced |
| **Branch History Check** | Validates branch is properly rebased off `dev` |
| **Code Format Validation** | Pre-commit hooks enforce formatting standards |

### Human Review

| Requirement | Description |
|-------------|-------------|
| **PR Required** | Branch protection prevents direct merges to `dev` |
| **Reviewer Approval** | At least one human reviewer must approve |
| **CI Checks Pass** | All automated checks must pass before merge |

---

## Code Promotion Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Feature    │     │     Dev      │     │      QA      │     │    Prod      │
│   Branch     │────▶│  (Continuous)│────▶│   (Manual)   │────▶│  (Release)   │
│              │     │              │     │              │     │              │
│  Developer   │     │  Auto-deploy │     │  Validation  │     │ Admin-tagged │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
      │                    │                    │                    │
      │                    │                    │                    │
      ▼                    ▼                    ▼                    ▼
  Pre-commit           CI/CD runs          Manual test          Release tag
  hooks run            auto-build         by feature           by admin(s)
                       & deploy           if needed            (1-2 approvers)
```

### Environment Stages

| Environment | Purpose | Deployment | Access Control |
|-------------|---------|------------|----------------|
| **Feature Branch** | Isolated development | Manual / On-demand | Developer |
| **Dev** | Integration testing | **Continuous** (auto-deploy on merge) | Development team |
| **QA** | Manual validation | On-demand | QA team + Developers |
| **Prod** | Production release | **Controlled** (tagged releases only) | Repo admins (1-2) |

---

## Automated Controls Summary

### Pre-Commit (Local)
```bash
# Runs before every commit
✓ Code formatting (Black, isort, Prettier)
✓ Linting (Ruff, ESLint)
✓ Type checking (mypy)
✓ Secrets detection (pre-commit hooks)
```

### CI/CD Pipeline (GitHub Actions)
```yaml
# Runs on every PR and push
✓ Unit tests
✓ Integration tests
✓ Migration validation
✓ Security scanning
✓ Build verification
✓ Auto-deploy to Dev (on merge)
```

### Branch Protection Rules
```
dev branch:
  ✓ Require PR for all changes
  ✓ Require at least 1 approval
  ✓ Require status checks to pass
  ✓ No direct pushes allowed

main branch:
  ✓ Require PR for all changes
  ✓ Require 2 approvals (admin only)
  ✓ Require all CI checks to pass
  ✓ Only tagged releases can be promoted
```

---

## Communication Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    #platform-dev-changelog                  │
│                      (Slack Channel)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📦 [DEV MERGE] feature/auth-improvements                   │
│  👤 @developer-a merged at 2:30 PM                          │
│  📝 Changes: Added MFA support, updated session handling    │
│  ⚠️  Migration: Yes - new columns in users table            │
│                                                             │
│  📦 [DEV MERGE] feature/connector-pdl-fix                   │
│  👤 @developer-b merged at 3:15 PM                          │
│  📝 Changes: Fixed sync_config field name                   │
│  ⚠️  Migration: No                                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

All feature developers subscribe to this channel to stay aware of:
- Platform changes that may affect their work
- Migration updates requiring rebase
- Breaking changes requiring coordination

---

## Summary

| Principle | Implementation |
|-----------|----------------|
| **Isolation** | Feature branches for independent development |
| **Visibility** | Slack changelog keeps all developers informed |
| **Quality** | Agentic + human code review |
| **Security** | Automated secrets scanning |
| **Automation** | CI/CD for continuous deployment to dev |
| **Control** | Admin-gated releases to production |
| **Traceability** | Tagged releases, audit logs |

