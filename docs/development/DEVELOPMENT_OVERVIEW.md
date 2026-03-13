# Eliza Platform - Development Workflow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#2B1420', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#8B3A52', 'secondaryColor': '#F8F5F0', 'background': '#F8F5F0', 'clusterBkg': '#FFF8F5', 'clusterBorder': '#C96B75'}}}%%

flowchart TB
    subgraph SPECIFICATION["1️⃣ FEATURE SPECIFICATION"]
        direction LR
        GPT["🤖 <b>Custom GPT</b><br/>Interactive spec building<br/>through conversation"]
        RULES["📋 <b>Rules Enrichment</b><br/>Security requirements<br/>Platform standards<br/>Integration patterns"]
        SPEC["📄 <b>Feature Spec</b><br/>Complete specification<br/>ready for development"]
        
        GPT --> RULES --> SPEC
    end
    
    subgraph DEVELOPMENT["2️⃣ DISTRIBUTED DEVELOPMENT"]
        direction LR
        DEV_BRANCH["🔀 <b>dev branch</b><br/>Platform integration<br/>Source of truth"]
        
        subgraph PARALLEL["Parallel Feature Work"]
            F1["<b>feature/auth</b><br/>Developer A"]
            F2["<b>feature/recruiter</b><br/>Developer B"]
            F3["<b>feature/analytics</b><br/>Developer C"]
        end
    end
    
    subgraph REVIEW["3️⃣ CODE REVIEW"]
        direction LR
        subgraph AGENTIC["Agentic Checks"]
            A1["🔐 Secrets Scanner<br/>API keys, passwords"]
            A2["🔄 Migration Validator<br/>Alembic sequencing"]
            A3["✨ Format & Lint<br/>Pre-commit hooks"]
            A4["🧪 Automated Tests<br/>Unit + Integration"]
        end
        
        subgraph HUMAN["Human Gates"]
            PR["<b>Pull Request</b><br/>Branch protection<br/>No direct merges"]
            APPROVAL["✅ <b>Approval</b><br/>Reviewer sign-off<br/>required"]
        end
        
        AGENTIC --> HUMAN
    end
    
    subgraph NOTIFY["4️⃣ VISIBILITY"]
        SLACK["📢 <b>#platform-changelog</b><br/>All merges posted<br/>Migration alerts<br/>Breaking changes"]
    end
    
    subgraph PROMOTION["5️⃣ ENVIRONMENT PROMOTION"]
        direction LR
        DEV_ENV["<b>DEV</b><br/>🔄 Continuous deploy<br/>Auto on merge to dev"]
        QA_ENV["<b>QA</b><br/>🧪 Manual validation<br/>On-demand deploy"]
        PROD_ENV["<b>PROD</b><br/>🎯 Tagged releases<br/>Admin approval (1-2)"]
        
        DEV_ENV --> QA_ENV --> PROD_ENV
    end

    %% Flow connections
    SPEC --> DEV_BRANCH
    DEV_BRANCH --> PARALLEL
    PARALLEL --> REVIEW
    APPROVAL --> DEV_BRANCH
    DEV_BRANCH --> NOTIFY
    DEV_BRANCH --> DEV_ENV

    %% Styling
    classDef specNode fill:#8B5CF6,stroke:#7C3AED,color:#fff,rx:10,ry:10
    classDef devBranch fill:#8B3A52,stroke:#6B2742,color:#F8F5F0,rx:10,ry:10
    classDef feature fill:#FF9580,stroke:#FF7B6B,color:#2B1420,rx:8,ry:8
    classDef agentic fill:#FFD4C4,stroke:#C96B75,color:#2B1420,rx:8,ry:8
    classDef human fill:#FF9580,stroke:#FF7B6B,color:#2B1420,rx:8,ry:8
    classDef slack fill:#19C37D,stroke:#059669,color:#fff,rx:10,ry:10
    classDef env fill:#FFD4C4,stroke:#C96B75,color:#2B1420,rx:8,ry:8
    classDef prod fill:#8B3A52,stroke:#6B2742,color:#F8F5F0,rx:8,ry:8
    
    class GPT,RULES,SPEC specNode
    class DEV_BRANCH devBranch
    class F1,F2,F3 feature
    class A1,A2,A3,A4 agentic
    class PR,APPROVAL human
    class SLACK slack
    class DEV_ENV,QA_ENV env
    class PROD_ENV prod
```

## Process Summary

### 1️⃣ Feature Specification
- **Custom GPT**: Interactive conversation to build requirements, acceptance criteria, edge cases
- **Rules Enrichment**: Automatic addition of security requirements, platform conventions, API patterns
- **Output**: Complete spec document ready for development

### 2️⃣ Distributed Development
- **dev branch**: The platform integration branch - single source of truth
- **Feature branches**: Each developer works in isolation (`feature/my-feature`)
- **Parallel work**: Multiple features developed simultaneously without conflicts

### 3️⃣ Code Review
**Agentic (Automated):**
- Secrets scanner catches API keys, passwords, tokens before they hit the repo
- Migration validator ensures Alembic migrations are properly sequenced
- Pre-commit hooks enforce consistent code formatting
- Full test suite runs on every PR

**Human (Required):**
- Branch protection prevents direct pushes to `dev`
- All changes require PR with reviewer approval
- CI checks must pass before merge is allowed

### 4️⃣ Visibility
- Every merge to `dev` posts to **#platform-changelog** in Slack
- Developers stay informed of platform changes affecting their work
- Migration alerts help teams know when to rebase

### 5️⃣ Environment Promotion
| Environment | Deployment | Control |
|-------------|------------|---------|
| **DEV** | Continuous (auto on merge) | Development team |
| **QA** | On-demand (manual trigger) | QA + Development |
| **PROD** | Tagged releases only | Repo admins (1-2 approvers) |
