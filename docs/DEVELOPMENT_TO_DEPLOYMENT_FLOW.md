# Development to Deployment: End-to-End Flow

This document describes the complete flow from local development to production deployment.

---

## High-Level Overview

```mermaid
flowchart LR
    subgraph Local["🖥️ Local Development"]
        A[Write Code] --> B[Test Locally]
        B --> C[git commit]
    end
    
    subgraph GitHub["🐙 GitHub"]
        C --> D[git push]
        D --> E[GitHub Actions]
        E --> F[GHCR Registry]
    end
    
    subgraph Northflank["☁️ Northflank"]
        F --> G[Pull Image]
        G --> H[Deploy]
    end
    
    style E fill:#4a9,stroke:#333
    style F fill:#69b,stroke:#333
    style H fill:#f96,stroke:#333
```

---

## Phase 1: Local Development

### 1.1 Start Local Environment

```bash
cd /path/to/ElizaPlatform

# Start all services locally
docker-compose -f docker/docker-compose.yml up -d

# Or for development with hot reload:
docker-compose -f docker/docker-compose.yml up -d postgres redis neo4j elasticsearch
cd frontend && npm start  # React dev server
cd .. && uvicorn src.main:app --reload  # FastAPI dev server
```

### 1.2 Make Code Changes

Edit your code in:
- `src/` - Backend (FastAPI, Celery, etc.)
- `frontend/src/` - Frontend (React)
- `config/` - Configuration files

### 1.3 Test Locally

```bash
# Run backend tests
pytest tests/

# Run frontend tests
cd frontend && npm test

# Manual testing
# Frontend: http://localhost:3000
# Backend API: http://localhost:5001
# API Docs: http://localhost:5001/docs
```

```mermaid
flowchart TB
    subgraph LocalStack["Local Docker Compose Stack"]
        FE[Frontend :3000]
        API[Backend API :5001]
        CW[Celery Worker]
        PG[(PostgreSQL :5432)]
        RD[(Redis :6379)]
        ES[(Elasticsearch :9200)]
        
        FE -->|API Calls| API
        API --> PG
        API --> RD
        CW --> RD
        CW --> PG
        API --> ES
    end
```

---

## Phase 2: Commit and Push

### 2.1 Commit Your Changes

```bash
git add .
git commit -m "feat: add new feature XYZ"
```

### 2.2 Push to GitHub

```bash
# For development/testing
git push origin dev

# For release
git push origin main
```

```mermaid
flowchart LR
    A[Local Repo] -->|git push origin dev| B[GitHub dev branch]
    A -->|git push origin main| C[GitHub main branch]
    A -->|git push origin v1.0.0| D[GitHub Release Tag]
    
    B --> E[Triggers: build-backend.yml]
    B --> F[Triggers: build-frontend.yml]
    C --> E
    C --> F
    D --> E
    D --> F
```

---

## Phase 3: GitHub Actions Build

### 3.1 Workflow Triggers

When you push, GitHub Actions automatically runs:

| Branch/Tag | Workflows Triggered | Images Built |
|------------|---------------------|--------------|
| `dev` | `build-backend.yml`, `build-frontend.yml` | `:dev-<sha>`, `:dev-latest` |
| `main` | `build-backend.yml`, `build-frontend.yml` | `:main-<sha>`, `:main-latest` |
| `v*` tag | `build-backend.yml`, `build-frontend.yml` | `:release-<version>` |

### 3.2 Build Process

```mermaid
flowchart TB
    subgraph GitHubActions["GitHub Actions Runner"]
        A[Checkout Code] --> B[Setup Docker Buildx]
        B --> C[Login to GHCR]
        C --> D[Build Docker Image]
        D --> E[Push to GHCR]
        E --> F[Generate Summary]
    end
    
    subgraph BuildArgs["📦 Build Args Source"]
        G[".github/workflows/build-backend.yml"]
        H[".github/workflows/build-frontend.yml"]
    end
    
    BuildArgs -.->|Defines| D
    
    style D fill:#4a9,stroke:#333
```

### 3.3 Where Build Args Are Stored

**All build arguments are defined in the workflow files** (version controlled!):

#### Backend Build Args
📁 **File:** `.github/workflows/build-backend.yml`

```yaml
build-args: |
  BUILD_DATE=${{ github.event.head_commit.timestamp }}
  GIT_SHA=${{ github.sha }}
  GIT_REF=${{ github.ref_name }}
```

#### Frontend Build Args
📁 **File:** `.github/workflows/build-frontend.yml`

```yaml
build-args: |
  REACT_APP_API_URL=           # Empty! Uses relative URLs
  BUILD_DATE=${{ github.event.head_commit.timestamp }}
  GIT_SHA=${{ github.sha }}
  GIT_REF=${{ github.ref_name }}
```

### 3.4 API URL Strategy: Relative URLs + Nginx Proxy

**We use relative URLs so ONE frontend image works for ALL customers!**

```mermaid
flowchart LR
    subgraph Browser["User's Browser"]
        A["React App"]
    end
    
    subgraph Northflank["Any Customer's Northflank Project"]
        B["frontend (nginx)"]
        C["app (backend)"]
    end
    
    A -->|"fetch('/v1/users')"| B
    B -->|"proxy_pass http://app:5001"| C
    
    style B fill:#69b,stroke:#333
    style C fill:#4a9,stroke:#333
```

**How it works:**

| Step | What Happens |
|------|--------------|
| 1 | React calls `/v1/users` (relative URL, no domain) |
| 2 | Browser sends request to frontend's domain |
| 3 | nginx receives request at `/v1/users` |
| 4 | nginx proxies to `http://app:5001/v1/users` |
| 5 | Backend responds, nginx forwards to browser |

**Why this is powerful:**
- ✅ ONE frontend image for ALL customers
- ✅ No API URL baked into the build
- ✅ Works because each Northflank project has its own `app` service
- ✅ Customer isolation is automatic

```mermaid
flowchart TB
    subgraph GHCR["📦 GHCR (Single Image)"]
        IMG["elizaplatform-frontend:release-1.0.0"]
    end
    
    subgraph Caylent["Caylent Project"]
        C_FE["frontend"] --> C_APP["app :5001"]
    end
    
    subgraph Acme["Acme Project"]
        A_FE["frontend"] --> A_APP["app :5001"]
    end
    
    subgraph Dev["Dev Project"]
        D_FE["frontend"] --> D_APP["app :5001"]
    end
    
    IMG --> C_FE
    IMG --> A_FE
    IMG --> D_FE
    
    style IMG fill:#69b,stroke:#333
```

### 3.4 Images Pushed to GHCR

After build completes:

```
ghcr.io/eliza-hq/elizaplatform-backend:dev-abc1234
ghcr.io/eliza-hq/elizaplatform-backend:dev-latest
ghcr.io/eliza-hq/elizaplatform-frontend:dev-abc1234
ghcr.io/eliza-hq/elizaplatform-frontend:dev-latest
```

---

## Phase 4: Northflank Deployment

### 4.1 Northflank Architecture

```mermaid
flowchart TB
    subgraph GHCR["GitHub Container Registry"]
        IMG1["elizaplatform-backend:dev-latest"]
        IMG2["elizaplatform-frontend:dev-latest"]
    end
    
    subgraph NF["Northflank Project"]
        subgraph Services["Deployment Services"]
            APP[app]
            CW[celery-worker]
            CB[celery-beat]
            FL[flower]
            FE[frontend]
        end
        
        subgraph Addons["Managed Addons"]
            PG[(PostgreSQL)]
            RD[(Redis)]
        end
        
        subgraph External["External Services"]
            ES[(Elasticsearch)]
            KB[Kibana]
            NEO[(Neo4j)]
        end
    end
    
    IMG1 --> APP
    IMG1 --> CW
    IMG1 --> CB
    IMG1 --> FL
    IMG2 --> FE
    
    APP --> PG
    APP --> RD
    CW --> PG
    CW --> RD
    
    style IMG1 fill:#69b,stroke:#333
    style IMG2 fill:#69b,stroke:#333
```

### 4.2 Service Configuration

Each Northflank service pulls from GHCR:

| Service | Image | Tag Strategy |
|---------|-------|--------------|
| `app` | `ghcr.io/eliza-hq/elizaplatform-backend` | `:dev-latest` or pinned |
| `celery-worker` | `ghcr.io/eliza-hq/elizaplatform-backend` | `:dev-latest` or pinned |
| `celery-beat` | `ghcr.io/eliza-hq/elizaplatform-backend` | `:dev-latest` or pinned |
| `flower` | `ghcr.io/eliza-hq/elizaplatform-backend` | `:dev-latest` or pinned |
| `frontend` | `ghcr.io/eliza-hq/elizaplatform-frontend` | `:dev-latest` or pinned |

### 4.3 Deployment Trigger

Northflank can be configured to:

**Option A: Manual Deploy**
- You manually click "Deploy" or update the image tag in Northflank UI

**Option B: Auto-Deploy on Image Push**
- Configure Northflank to watch for new `:dev-latest` tags
- Auto-deploys when GHCR receives new image

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant GH as GitHub
    participant GA as GitHub Actions
    participant GHCR as GHCR
    participant NF as Northflank

    Dev->>GH: git push origin dev
    GH->>GA: Trigger workflows
    GA->>GA: Build backend image
    GA->>GA: Build frontend image
    GA->>GHCR: Push :dev-latest
    
    alt Auto-Deploy Enabled
        GHCR-->>NF: Webhook: new image
        NF->>GHCR: Pull :dev-latest
        NF->>NF: Rolling deploy
    else Manual Deploy
        Dev->>NF: Click "Redeploy"
        NF->>GHCR: Pull :dev-latest
        NF->>NF: Rolling deploy
    end
    
    NF-->>Dev: Deployment complete
```

---

## Phase 5: Customer Releases

### 5.1 Release Flow

```mermaid
flowchart TB
    subgraph Testing["Testing Phase"]
        A[Dev Branch] -->|Test on| B[Dev Northflank]
        B -->|Verified| C{Ready?}
    end
    
    subgraph Release["Release Phase"]
        C -->|Yes| D[Merge to main]
        D --> E[Create git tag v1.0.0]
        E --> F[GitHub Actions builds]
        F --> G[":release-1.0.0 in GHCR"]
    end
    
    subgraph Promote["Customer Promotion"]
        G --> H[Run promote-release.yml]
        H --> I[":customer-caylent-2025-12-19"]
        I --> J[Update Caylent Northflank]
    end
    
    style G fill:#4a9,stroke:#333
    style I fill:#f96,stroke:#333
```

### 5.2 Promoting to Customers

```bash
# 1. Go to GitHub Actions
# 2. Run "Promote to Customer" workflow
# 3. Fill in:
#    - image_type: both
#    - source_tag: release-1.0.0
#    - customer_name: caylent

# Result: Creates customer-specific tags
# ghcr.io/eliza-hq/elizaplatform-backend:customer-caylent-2025-12-19
# ghcr.io/eliza-hq/elizaplatform-frontend:customer-caylent-2025-12-19
```

---

## Complete End-to-End Flow

```mermaid
flowchart TB
    subgraph Local["🖥️ LOCAL"]
        L1[Edit Code] --> L2[Test Locally]
        L2 --> L3[git commit]
        L3 --> L4[git push]
    end
    
    subgraph GitHub["🐙 GITHUB"]
        L4 --> G1[dev/main branch]
        G1 --> G2[GitHub Actions]
        
        subgraph Workflows["Workflow Files define Build Args"]
            W1["build-backend.yml<br/>- BUILD_DATE<br/>- GIT_SHA"]
            W2["build-frontend.yml<br/>- REACT_APP_API_URL<br/>- BUILD_DATE"]
        end
        
        G2 --> G3[Build Images]
        Workflows -.-> G3
        G3 --> G4[Push to GHCR]
    end
    
    subgraph GHCR["📦 GHCR"]
        G4 --> R1[":dev-latest"]
        G4 --> R2[":main-latest"]
        G4 --> R3[":release-x.x.x"]
    end
    
    subgraph Northflank["☁️ NORTHFLANK"]
        R1 --> N1[Dev Project]
        R3 --> N2[Promote Workflow]
        N2 --> N3[":customer-xxx"]
        N3 --> N4[Customer Project]
    end
    
    subgraph Users["👥 USERS"]
        N1 --> U1[Internal Testing]
        N4 --> U2[Customer Access]
    end
    
    style G2 fill:#4a9,stroke:#333
    style G4 fill:#69b,stroke:#333
    style Workflows fill:#f9f,stroke:#333
```

---

## Quick Reference

### File Locations

| What | Where |
|------|-------|
| Backend Dockerfile | `docker/Dockerfile` |
| Frontend Dockerfile | `frontend/Dockerfile` |
| Logstash Dockerfile | `docker/logstash/Dockerfile` |
| Backend build workflow | `.github/workflows/build-backend.yml` |
| Frontend build workflow | `.github/workflows/build-frontend.yml` |
| Logstash build workflow | `.github/workflows/build-logstash.yml` |
| Local dev compose | `docker/docker-compose.yml` |
| CI/CD docs | `docs/CICD_GHCR_SETUP.md` |

### Image Tags

| Tag Pattern | When Created | Use Case |
|-------------|--------------|----------|
| `:dev-<sha>` | Push to dev | Immutable dev builds |
| `:dev-latest` | Push to dev | Auto-updating dev |
| `:main-<sha>` | Push to main | Immutable main builds |
| `:main-latest` | Push to main | Pre-release testing |
| `:release-x.x.x` | Git tag v* | Releases |
| `:customer-<name>-<date>` | Manual promote | Customer deployments |

### Workflow Trigger Summary

| Workflow | Auto on dev/main | Path Filter | Auto on v* tags | Manual |
|----------|------------------|-------------|-----------------|--------|
| build-backend | ✅ Yes | `src/**`, `config/**`, `alembic/**`, `docker/Dockerfile`, `requirements*.txt` | ✅ Yes | ✅ Yes |
| build-frontend | ✅ Yes | `frontend/**` | ✅ Yes | ✅ Yes |
| build-logstash | ❌ No | N/A | ✅ Yes | ✅ Yes |
| promote-release | ❌ No | N/A | ❌ No | ✅ Yes |

**What this means:**
- 📝 Docs-only commits → No builds triggered
- 🐍 Backend code changes → Only backend builds
- ⚛️ Frontend code changes → Only frontend builds
- 🏷️ Release tags (v*) → All images build
- 🔧 Manual trigger → Always available

### Commands

```bash
# Local development
docker-compose -f docker/docker-compose.yml up -d

# Push to dev (triggers build)
git push origin dev

# Create release
git tag v1.0.0
git push origin v1.0.0

# View builds
open https://github.com/eliza-hq/ElizaPlatform/actions

# View images
open https://github.com/orgs/eliza-hq/packages
```

---

## Troubleshooting

### Build Failed in GitHub Actions

1. Check Actions tab: https://github.com/eliza-hq/ElizaPlatform/actions
2. Click on failed run
3. Expand failed step to see error

### Image Not Found in Northflank

1. Verify image exists in GHCR
2. Check Northflank registry credentials
3. Verify image tag is correct

### Wrong API URL in Frontend

1. Check `.github/workflows/build-frontend.yml`
2. Update the `Determine API URL` step
3. Push change to trigger new build

---

## Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     BUILD ARGS LOCATION                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  📁 .github/workflows/build-backend.yml                         │
│     └── BUILD_DATE, GIT_SHA, GIT_REF                            │
│                                                                  │
│  📁 .github/workflows/build-frontend.yml                        │
│     └── REACT_APP_API_URL="" (empty - uses relative URLs!)     │
│     └── BUILD_DATE, GIT_SHA, GIT_REF                            │
│                                                                  │
│  ⚠️  NOT in Northflank UI (Northflank doesn't build!)           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    API URL STRATEGY                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Frontend uses RELATIVE URLs: /v1/users, /v1/auth/login, etc.  │
│                                                                  │
│  nginx.conf proxies /v1/* to http://app:5001                    │
│                                                                  │
│  Result: ONE image works for ALL customers!                     │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   Caylent   │    │    Acme     │    │     Dev     │         │
│  │   Project   │    │   Project   │    │   Project   │         │
│  │             │    │             │    │             │         │
│  │  frontend ──┼───►│  frontend ──┼───►│  frontend ──│         │
│  │     │       │    │     │       │    │     │       │         │
│  │     ▼       │    │     ▼       │    │     ▼       │         │
│  │    app      │    │    app      │    │    app      │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│        ▲                  ▲                  ▲                  │
│        │                  │                  │                  │
│        └──────────────────┴──────────────────┘                  │
│                    SAME IMAGE!                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        FLOW SUMMARY                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Local Dev    →  Edit & test code locally                    │
│  2. Git Push     →  Push to dev/main branch                     │
│  3. GH Actions   →  Builds images with args from workflow files │
│  4. GHCR         →  Stores images with tags                     │
│  5. Northflank   →  Pulls images, deploys (no building!)        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

