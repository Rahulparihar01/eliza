# Eliza Platform - Development Process & Code Promotion

## Development Workflow Overview

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#2B1420', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#C96B75', 'secondaryColor': '#F8F5F0', 'tertiaryColor': '#FFF2ED', 'background': '#F8F5F0', 'mainBkg': '#F8F5F0', 'nodeBorder': '#8B3A52', 'clusterBkg': '#FFF8F5', 'clusterBorder': '#C96B75', 'titleColor': '#2B1420', 'edgeLabelBackground': '#F8F5F0'}}}%%

flowchart TB
    subgraph SPEC["📝 1. FEATURE SPECIFICATION"]
        direction LR
        GPT["🤖 Conversational AI<br/>(Custom GPT)"]
        ENRICH["📋 Rules-Based<br/>Enrichment"]
        SPEC_DOC["📄 Feature Spec<br/>Document"]
        
        GPT --> ENRICH --> SPEC_DOC
    end
    
    subgraph DEV["👩‍💻 2. DISTRIBUTED DEVELOPMENT"]
        direction TB
        
        DEV_BRANCH["<b>dev</b><br/>(Integration Branch)"]
        
        FEAT_A["feature/auth<br/>Developer A"]
        FEAT_B["feature/recruiter<br/>Developer B"]
        FEAT_C["feature/connectors<br/>Developer C"]
        FEAT_D["feature/analytics<br/>Developer D"]
        
        DEV_BRANCH --> FEAT_A
        DEV_BRANCH --> FEAT_B
        DEV_BRANCH --> FEAT_C
        DEV_BRANCH --> FEAT_D
        
        SLACK["📢 #platform-changelog<br/>(Slack Notifications)"]
        DEV_BRANCH -.-> SLACK
    end
    
    subgraph REVIEW["🔍 3. CODE REVIEW"]
        direction TB
        
        subgraph AUTOMATED["Agentic Review"]
            SECRETS["🔐 Secrets Scanner<br/>Keys, Passwords, Tokens"]
            MIGRATE["🔄 Migration Validator<br/>Alembic Sequencing"]
            HISTORY["📜 Branch History<br/>Rebased off dev"]
        end
        
        subgraph HUMAN["Human Review"]
            PR["Pull Request<br/>Required"]
            APPROVE["✅ Reviewer Approval<br/>Required"]
        end
        
        SECRETS --> PR
        MIGRATE --> PR
        HISTORY --> PR
        PR --> APPROVE
    end
    
    subgraph PROMOTE["🚀 4. CODE PROMOTION"]
        direction LR
        
        DEV_ENV["<b>DEV</b><br/>🔄 Continuous Deploy<br/>Auto on merge"]
        QA_ENV["<b>QA</b><br/>🧪 Manual Testing<br/>On-demand"]
        PROD_ENV["<b>PROD</b><br/>🎯 Tagged Release<br/>Admin-gated"]
        
        DEV_ENV --> QA_ENV --> PROD_ENV
    end
    
    SPEC_DOC --> DEV
    FEAT_A --> REVIEW
    FEAT_B --> REVIEW
    FEAT_C --> REVIEW
    FEAT_D --> REVIEW
    APPROVE --> DEV_ENV

    %% Eliza Brand Styling (Coral/Rose/Burgundy palette)
    classDef spec fill:#8B5CF6,stroke:#7C3AED,color:#fff,rx:10,ry:10
    classDef dev fill:#FF9580,stroke:#FF7B6B,color:#2B1420,rx:10,ry:10
    classDef review fill:#FFD4C4,stroke:#C96B75,color:#2B1420,rx:10,ry:10
    classDef env fill:#19C37D,stroke:#059669,color:#fff,rx:10,ry:10
    classDef prod fill:#8B3A52,stroke:#6B2742,color:#F8F5F0,rx:10,ry:10
    classDef slack fill:#FFF2ED,stroke:#C96B75,color:#8B3A52,rx:10,ry:10
    
    class GPT,ENRICH,SPEC_DOC spec
    class DEV_BRANCH dev
    class FEAT_A,FEAT_B,FEAT_C,FEAT_D dev
    class SECRETS,MIGRATE,HISTORY,PR,APPROVE review
    class DEV_ENV,QA_ENV env
    class PROD_ENV prod
    class SLACK slack
```

---

## Detailed Process Flow

### 1. Feature Specification

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#2B1420', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#C96B75', 'secondaryColor': '#F8F5F0', 'background': '#F8F5F0'}}}%%

flowchart LR
    A["💡 Feature Idea"] --> B["🤖 Custom GPT<br/>Conversation"]
    B --> C["📝 Draft Spec"]
    C --> D["⚙️ Rules Engine<br/>Enrichment"]
    D --> E["✅ Complete Spec"]
    
    D -.-> D1["Security Requirements"]
    D -.-> D2["Platform Standards"]
    D -.-> D3["Integration Patterns"]
    D -.-> D4["Testing Requirements"]

    classDef main fill:#FF9580,stroke:#FF7B6B,color:#2B1420,rx:10,ry:10
    classDef enrichment fill:#FFD4C4,stroke:#C96B75,color:#2B1420,rx:8,ry:8
    classDef complete fill:#19C37D,stroke:#059669,color:#fff,rx:10,ry:10
    
    class A,B,C main
    class D,D1,D2,D3,D4 enrichment
    class E complete
```

| Stage | Description |
|-------|-------------|
| **Ideation** | Product/engineering identifies feature need |
| **AI-Assisted Spec** | Conversational AI helps structure requirements, acceptance criteria, edge cases |
| **Rules Enrichment** | Automated enrichment adds security requirements, platform conventions, integration patterns |
| **Final Spec** | Complete specification ready for development |

---

### 2. Distributed Development

```mermaid
gitGraph
    commit id: "main (prod)"
    branch dev
    commit id: "dev baseline"
    
    branch feature/auth
    commit id: "Add MFA"
    commit id: "Session handling"
    
    checkout dev
    branch feature/recruiter
    commit id: "Candidate scoring"
    commit id: "Market search"
    
    checkout dev
    branch feature/connectors
    commit id: "PDL fix"
    
    checkout dev
    merge feature/connectors id: "PR #123"
    
    checkout feature/auth
    commit id: "Rebase dev"
    
    checkout dev
    merge feature/auth id: "PR #124"
    merge feature/recruiter id: "PR #125"
    
    checkout main
    merge dev tag: "v1.2.0"
```

| Practice | Description |
|----------|-------------|
| **Branch from dev** | All feature work branches from the `dev` integration branch |
| **Isolated work** | Each developer works in their own feature branch |
| **Stay informed** | Changelog notifications to Slack keep all developers aware of platform changes |
| **Short-lived branches** | Feature branches are focused and merged promptly |

---

### 3. Code Review

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#2B1420', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#C96B75', 'secondaryColor': '#F8F5F0', 'background': '#F8F5F0', 'clusterBkg': '#FFF8F5', 'clusterBorder': '#C96B75'}}}%%

flowchart TB
    subgraph PR_OPEN["Pull Request Opened"]
        CODE["Feature Code"]
    end
    
    subgraph AUTOMATED["Automated Checks (Agentic)"]
        direction TB
        A1["🔐 Secrets Scanner"]
        A2["🔄 Migration Validator"]
        A3["📜 Branch History Check"]
        A4["✨ Code Formatting"]
        A5["🧪 Unit Tests"]
        A6["🔗 Integration Tests"]
    end
    
    subgraph HUMAN_REVIEW["Human Review"]
        H1["👀 Code Review"]
        H2["✅ Approval"]
    end
    
    subgraph PROTECTION["Branch Protection"]
        P1["❌ No Direct Push"]
        P2["✅ PR Required"]
        P3["✅ Checks Must Pass"]
    end
    
    CODE --> AUTOMATED
    AUTOMATED --> |All Pass| HUMAN_REVIEW
    AUTOMATED --> |Fail| CODE
    HUMAN_REVIEW --> |Approved| MERGE["🔀 Merge to dev"]
    
    PROTECTION -.-> MERGE

    classDef code fill:#FF9580,stroke:#FF7B6B,color:#2B1420,rx:10,ry:10
    classDef automated fill:#FFD4C4,stroke:#C96B75,color:#2B1420,rx:8,ry:8
    classDef human fill:#8B5CF6,stroke:#7C3AED,color:#fff,rx:8,ry:8
    classDef protection fill:#8B3A52,stroke:#6B2742,color:#F8F5F0,rx:8,ry:8
    classDef merge fill:#19C37D,stroke:#059669,color:#fff,rx:10,ry:10
    
    class CODE code
    class A1,A2,A3,A4,A5,A6 automated
    class H1,H2 human
    class P1,P2,P3 protection
    class MERGE merge
```

#### Automated Review Checks

| Check | Tool | Description |
|-------|------|-------------|
| **Secrets Scanner** | AI Agent | Scans for API keys, passwords, tokens, credentials |
| **Migration Validator** | Alembic | Ensures migrations are properly chained and merged |
| **Branch History** | Git | Validates branch is rebased off current `dev` |
| **Code Formatting** | Pre-commit | Black, isort, Prettier enforce consistent style |
| **Tests** | pytest | Unit and integration tests must pass |

#### Branch Protection Rules

- **dev branch**: PR required, 1 approval, all checks pass
- **main branch**: PR required, 2 admin approvals, all checks pass, tagged releases only

---

### 4. Code Promotion

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#2B1420', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#C96B75', 'secondaryColor': '#F8F5F0', 'background': '#F8F5F0', 'clusterBkg': '#FFF8F5', 'clusterBorder': '#C96B75'}}}%%

flowchart LR
    subgraph DEV["DEV Environment"]
        D1["🔄 Auto-deploy on merge"]
        D2["Continuous Integration"]
        D3["Feature testing"]
    end
    
    subgraph QA["QA Environment"]
        Q1["🧪 Manual validation"]
        Q2["On-demand deploy"]
        Q3["Regression testing"]
    end
    
    subgraph PROD["PROD Environment"]
        P1["🎯 Tagged releases only"]
        P2["Admin approval (1-2)"]
        P3["Production traffic"]
    end
    
    DEV --> |"Promote"| QA
    QA --> |"Release Tag"| PROD

    classDef dev fill:#FF9580,stroke:#FF7B6B,color:#2B1420,rx:8,ry:8
    classDef qa fill:#FFD4C4,stroke:#C96B75,color:#2B1420,rx:8,ry:8
    classDef prod fill:#8B3A52,stroke:#6B2742,color:#F8F5F0,rx:8,ry:8
    
    class D1,D2,D3 dev
    class Q1,Q2,Q3 qa
    class P1,P2,P3 prod
```

| Environment | Deployment | Access Control | Purpose |
|-------------|------------|----------------|---------|
| **DEV** | Continuous (auto on merge) | Development team | Integration testing, feature validation |
| **QA** | On-demand | QA + Development | Manual testing, regression validation |
| **PROD** | Tagged releases only | Repo admins (1-2 approvers) | Production users |

---

## CI/CD Pipeline

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#FF9580', 'primaryTextColor': '#2B1420', 'primaryBorderColor': '#FF7B6B', 'lineColor': '#C96B75', 'secondaryColor': '#F8F5F0', 'background': '#F8F5F0', 'clusterBkg': '#FFF8F5', 'clusterBorder': '#C96B75'}}}%%

flowchart TB
    subgraph TRIGGER["Triggers"]
        T1["Push to feature/*"]
        T2["PR to dev"]
        T3["Merge to dev"]
        T4["Tag on main"]
    end
    
    subgraph BUILD["Build Stage"]
        B1["📦 Install deps"]
        B2["🔍 Lint & Format"]
        B3["🧪 Run Tests"]
        B4["🔐 Security Scan"]
        B5["🏗️ Build Artifacts"]
    end
    
    subgraph DEPLOY["Deploy Stage"]
        DEV_DEPLOY["Deploy to DEV"]
        QA_DEPLOY["Deploy to QA"]
        PROD_DEPLOY["Deploy to PROD"]
    end
    
    T1 --> B1
    T2 --> B1
    B1 --> B2 --> B3 --> B4 --> B5
    
    T3 --> B5 --> DEV_DEPLOY
    
    DEV_DEPLOY -.-> |"Manual trigger"| QA_DEPLOY
    T4 --> PROD_DEPLOY

    classDef trigger fill:#8B5CF6,stroke:#7C3AED,color:#fff,rx:8,ry:8
    classDef build fill:#FFD4C4,stroke:#C96B75,color:#2B1420,rx:8,ry:8
    classDef devDeploy fill:#FF9580,stroke:#FF7B6B,color:#2B1420,rx:8,ry:8
    classDef qaDeploy fill:#19C37D,stroke:#059669,color:#fff,rx:8,ry:8
    classDef prodDeploy fill:#8B3A52,stroke:#6B2742,color:#F8F5F0,rx:8,ry:8
    
    class T1,T2,T3,T4 trigger
    class B1,B2,B3,B4,B5 build
    class DEV_DEPLOY devDeploy
    class QA_DEPLOY qaDeploy
    class PROD_DEPLOY prodDeploy
```

---

## Communication & Visibility

### Slack Integration

All merges to `dev` are posted to **#platform-changelog**:

```
📦 [DEV MERGE] feature/auth-improvements
👤 @developer-a merged at 2:30 PM
📝 Changes: Added MFA support, updated session handling
⚠️  Migration: Yes - new columns in users table
🔗 PR: #124

📦 [DEV MERGE] feature/connector-pdl-fix  
👤 @developer-b merged at 3:15 PM
📝 Changes: Fixed sync_config field name for PDL
⚠️  Migration: No
🔗 PR: #125
```

This keeps all feature developers informed of:
- Platform changes that may affect their work
- Migration updates requiring rebase
- Breaking changes requiring coordination

