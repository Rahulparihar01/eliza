# Eliza Platform Multi-Deployment Architecture

**Version:** 1.0  
**Last Updated:** January 2026  
**Classification:** Internal Documentation

---

## Overview

The Eliza Platform leverages **Northflank** as its deployment orchestration layer, enabling flexible deployment options across multiple cloud providers and hosting models. This architecture supports diverse customer requirements—from cost-optimized SaaS to fully isolated instances for regulated industries.

---

## Deployment Architecture Diagram

```mermaid
flowchart TB
    subgraph ELIZA["🏢 Eliza Platform Codebase"]
        direction TB
        CODE["Source Code Repository"]
        CI["CI/CD Pipeline"]
    end

    subgraph NF["⚡ Northflank Orchestration Layer"]
        direction TB
        DEPLOY["Deployment Engine"]
        CONFIG["Configuration Management"]
        SECRETS["Secrets & Credentials"]
        MONITOR["Monitoring & Logging"]
    end

    CODE --> CI --> NF

    subgraph DEPLOY_OPTIONS["Deployment Models"]
        direction LR
        
        subgraph SAAS["☁️ SaaS<br/>(Northflank Hosted)"]
            direction TB
            MT["Multi-Tenant Instance"]
            MT_DB[("Shared Infrastructure<br/>with RLS Isolation")]
        end

        subgraph MANAGED["🔧 Managed Dedicated<br/>(Customer Cloud)"]
            direction TB
            subgraph AWS_D["AWS"]
                AWS_I["Dedicated Instance"]
            end
            subgraph AZURE_D["Azure"]
                AZURE_I["Dedicated Instance"]
            end
            subgraph GCP_D["GCP"]
                GCP_I["Dedicated Instance"]
            end
        end

        subgraph ISOLATED["🔒 Fully Isolated<br/>(Data Sovereignty)"]
            direction TB
            ISO_I["Single-Tenant Instance"]
            ISO_DB[("Isolated Database<br/>Customer-Controlled")]
        end
    end

    NF --> SAAS
    NF --> MANAGED
    NF --> ISOLATED

    subgraph CUSTOMERS["👥 Customer Segments"]
        direction TB
        C1["SMB Customers<br/><i>Cost-Optimized</i>"]
        C2["Enterprise Customers<br/><i>Cloud Flexibility</i>"]
        C3["Regulated Industries<br/><i>Data Isolation Required</i>"]
    end

    SAAS -.-> C1
    MANAGED -.-> C2
    ISOLATED -.-> C3

    %% Eliza Platform Colors
    classDef northflank fill:#FF9580,stroke:#FF7B6B,color:#2B1420,stroke-width:2px
    classDef saas fill:#19C37D,stroke:#059669,color:#F8F5F0
    classDef managed fill:#14B8A6,stroke:#0D9488,color:#F8F5F0
    classDef isolated fill:#8B5CF6,stroke:#7C3AED,color:#F8F5F0
    classDef customer fill:#F8F5F0,stroke:#8B3A52,color:#2B1420
    classDef code fill:#2B1420,stroke:#8B3A52,color:#F8F5F0
    classDef default fill:#F8F5F0,stroke:#C96B75,color:#2B1420

    class NF,DEPLOY,CONFIG,SECRETS,MONITOR northflank
    class SAAS,MT,MT_DB saas
    class MANAGED,AWS_D,AZURE_D,GCP_D,AWS_I,AZURE_I,GCP_I managed
    class ISOLATED,ISO_I,ISO_DB isolated
    class CUSTOMERS,C1,C2,C3 customer
    class ELIZA,CODE,CI code
```

---

## Simplified Deployment Flow

```mermaid
graph LR
    subgraph Source["📦 Eliza Platform"]
        A["Code"] --> B["Build"]
    end

    B --> NF{{"⚡ Northflank"}}

    NF -->|"SaaS Model"| D["☁️ Northflank Cloud<br/>Multi-Tenant"]
    NF -->|"BYOC"| E["🔧 Customer Cloud<br/>AWS / Azure / GCP"]
    NF -->|"Air-Gapped"| F["🔒 Isolated Instance<br/>Single-Tenant"]

    D --> G[("🗄️ Shared DB<br/>RLS Isolation")]
    E --> H[("🗄️ Dedicated DB<br/>Customer VPC")]
    F --> I[("🗄️ Private DB<br/>Customer Controlled")]

    %% Eliza Platform Colors
    style NF fill:#FF9580,stroke:#FF7B6B,color:#2B1420,stroke-width:3px
    style Source fill:#2B1420,stroke:#8B3A52,color:#F8F5F0
    style A fill:#2B1420,stroke:#8B3A52,color:#F8F5F0
    style B fill:#2B1420,stroke:#8B3A52,color:#F8F5F0
    style D fill:#19C37D,stroke:#059669,color:#F8F5F0
    style E fill:#14B8A6,stroke:#0D9488,color:#F8F5F0
    style F fill:#8B5CF6,stroke:#7C3AED,color:#F8F5F0
    style G fill:#19C37D,stroke:#059669,color:#F8F5F0
    style H fill:#14B8A6,stroke:#0D9488,color:#F8F5F0
    style I fill:#8B5CF6,stroke:#7C3AED,color:#F8F5F0
```

---

## Deployment Models

### ☁️ SaaS (Northflank Hosted)

| Aspect | Details |
|--------|---------|
| **Hosting** | Northflank managed infrastructure |
| **Isolation** | PostgreSQL Row-Level Security (RLS) |
| **Best For** | SMB customers, rapid onboarding |
| **Advantages** | Cost-effective, automatic updates, zero ops |
| **Data Residency** | Northflank data centers |

### 🔧 Managed Dedicated (Customer Cloud)

| Aspect | Details |
|--------|---------|
| **Hosting** | Customer's cloud account (AWS/Azure/GCP) |
| **Isolation** | Dedicated infrastructure per customer |
| **Best For** | Enterprise customers with cloud preferences |
| **Advantages** | Cloud flexibility, VPC integration, compliance |
| **Data Residency** | Customer-controlled region |

### 🔒 Fully Isolated (Data Sovereignty)

| Aspect | Details |
|--------|---------|
| **Hosting** | Single-tenant, customer-controlled |
| **Isolation** | Complete infrastructure isolation |
| **Best For** | Regulated industries (healthcare, finance, government) |
| **Advantages** | Full data sovereignty, air-gapped option |
| **Data Residency** | Customer-specified location |

---

## Northflank Capabilities

Northflank serves as our universal deployment orchestration layer, providing:

- **🚀 Multi-Cloud Deployment** — Deploy to AWS, Azure, GCP, or Northflank's own infrastructure
- **🔄 GitOps Workflow** — Automatic deployments triggered by code changes
- **🔐 Secrets Management** — Secure credential storage and injection
- **📊 Observability** — Built-in logging, metrics, and monitoring
- **🌐 Networking** — Automatic TLS, load balancing, and DNS management
- **📦 Container Registry** — Built-in image storage and versioning

---

## Color Legend

| Color | Meaning |
|-------|---------|
| 🟠 Coral (`#FF9580`) | Northflank / Orchestration |
| 🟢 Green (`#19C37D`) | SaaS / Multi-Tenant |
| 🔵 Teal (`#14B8A6`) | Managed / Customer Cloud |
| 🟣 Purple (`#8B5CF6`) | Isolated / Data Sovereignty |
| ⚫ Dark (`#2B1420`) | Source / Codebase |
| ⚪ Cream (`#F8F5F0`) | Customer Segments |

---

## Related Documentation

- [Platform Architecture](./PLATFORM_ARCHITECTURE.md)
- [Security Overview](../specs/security/security_quick_start.md)
- [Development Workflow](./DEVELOPMENT_WORKFLOW.md)

