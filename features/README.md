# Features Directory

> **Purpose:** Structured feature development from Product Spec → Technical Spec → Implementation Plan

---

## 🔄 Feature Development Pipeline

Every feature follows a three-stage development pipeline:

```
┌──────────────┐      ┌──────────────┐      ┌──────────────────┐
│ PRODUCT SPEC │ ───► │ TECHNICAL    │ ───► │ IMPLEMENTATION   │
│    (PRD)     │      │    SPEC      │      │      PLAN        │
└──────────────┘      └──────────────┘      └──────────────────┘
       │                     │                       │
       ▼                     ▼                       ▼
 Business needs        Architecture &          Task breakdown
 User stories          API contracts           Execution order
 Success metrics       Data models             Time estimates
 Acceptance criteria   Integration points      Dependencies
                       Agent analysis          Checkpoints
```

---

## 📁 Directory Structure

```
features/
├── README.md                  # This file
├── _templates/                # Document templates
│   ├── 01_PRODUCT_SPEC_TEMPLATE.md
│   ├── 02_TECHNICAL_SPEC_TEMPLATE.md
│   └── 03_IMPLEMENTATION_PLAN_TEMPLATE.md
│
├── active/                    # Features currently in development
│   └── [feature-name]/
│       ├── 01_PRODUCT_SPEC.md
│       ├── 02_TECHNICAL_SPEC.md
│       ├── 03_IMPLEMENTATION_PLAN.md
│       └── assets/            # Diagrams, mockups
│
├── completed/                 # Shipped features (reference)
│   └── [feature-name]/
│
└── backlog/                   # Future features (PRDs only)
    └── [feature-name]/
```

---

## 🚀 Starting a New Feature

### 1. Create Feature Directory

```bash
mkdir -p features/backlog/my-new-feature
```

### 2. Copy Product Spec Template

```bash
cp features/_templates/01_PRODUCT_SPEC_TEMPLATE.md features/backlog/my-new-feature/01_PRODUCT_SPEC.md
```

### 3. Fill Out Product Spec

Edit `01_PRODUCT_SPEC.md` with:
- Executive summary
- Problem statement
- Goals and non-goals
- Target users
- User stories
- Acceptance criteria

### 4. Move to Active When Ready

```bash
mv features/backlog/my-new-feature features/active/
```

### 5. Generate Technical Spec

Use the development agent to:
1. Review the PRD and ask clarifying questions
2. Identify edge cases and risks
3. Propose architecture and data models
4. Output `02_TECHNICAL_SPEC.md`

### 6. Generate Implementation Plan

From the Technical Spec, create `03_IMPLEMENTATION_PLAN.md` with:
- Ordered task breakdown
- File-by-file changes
- Database migrations
- Time estimates

---

## 📋 Document Stages

### Stage 1: Product Spec (PRD)
**Input:** Business requirements, stakeholder needs  
**Output:** `01_PRODUCT_SPEC.md`  
**Owner:** Product owner / Business stakeholder

### Stage 2: Technical Spec
**Input:** Product Spec + Development Agent review  
**Output:** `02_TECHNICAL_SPEC.md`  
**Owner:** Engineering lead / Development agent

The development agent:
1. Reviews the PRD and asks clarifying questions
2. Identifies edge cases and risks
3. Proposes architecture and data models
4. Defines API contracts
5. Maps integration points with existing systems

### Stage 3: Implementation Plan
**Input:** Technical Spec  
**Output:** `03_IMPLEMENTATION_PLAN.md`  
**Owner:** Engineering lead / Development agent

---

## 🏷️ Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Feature folder | `kebab-case` | `portfolio-intelligence/` |
| Documents | Numbered prefix | `01_PRODUCT_SPEC.md` |
| Assets folder | `assets/` | Contains diagrams, mockups |

---

## 🔄 Feature Lifecycle

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

## 📚 Templates

| Template | Purpose |
|----------|---------|
| `01_PRODUCT_SPEC_TEMPLATE.md` | Business requirements document |
| `02_TECHNICAL_SPEC_TEMPLATE.md` | Architecture and API design |
| `03_IMPLEMENTATION_PLAN_TEMPLATE.md` | Task breakdown and execution |

---

## 🔗 Related Resources

- **`skills/`** - Domain-specific development guidelines
- **`AGENTS.md`** - Feature development overview
- **`cookbook/`** - CrewAI development patterns
