# RAG System - AWS Architecture

AWS infrastructure for the secure, compliant RAG system with Okta-based access control.

---

```mermaid
flowchart TB
    subgraph External["EXTERNAL"]
        Users["👤 Firm Users"]
        Okta["🔐 Okta IDP"]
        SharePoint["📁 SharePoint Online"]
    end

    subgraph AWS["☁️ AWS CLOUD"]
        subgraph Public["Public Subnet"]
            ALB["Application<br/>Load Balancer"]
        end

        subgraph Private["Private Subnet"]
            subgraph Connect["Amazon Connect"]
                ConnectFlow["Connect Flow"]
                Lex["Amazon Lex<br/>Intent Recognition"]
                Lambda["Lambda<br/>Query Handler"]
            end

            subgraph Compute["ECS Fargate"]
                API["RAG API<br/>Service"]
                Ingest["Ingestion<br/>Service"]
                Sync["Okta Sync<br/>Service"]
            end

            subgraph Data["Data Layer"]
                RDS["RDS PostgreSQL<br/>━━━━━━━━━━<br/>• Documents<br/>• Chunks<br/>• Audit Logs"]
                Redis["ElastiCache<br/>Redis<br/>━━━━━━━━━━<br/>• Access Cache<br/>• Sessions"]
                OpenSearch["OpenSearch<br/>━━━━━━━━━━<br/>• Vector Store<br/>• k-NN Search"]
            end
        end

        subgraph Storage["Storage"]
            S3Docs["S3<br/>Document Storage"]
            S3Index["S3<br/>Index Snapshots"]
        end

        subgraph AI["AI Services"]
            Bedrock["Amazon Bedrock<br/>━━━━━━━━━━<br/>• Claude 3.5<br/>• Titan Embeddings"]
        end

        subgraph Security["Security & Compliance"]
            KMS["KMS<br/>Encryption Keys"]
            Secrets["Secrets Manager<br/>API Keys"]
            CloudTrail["CloudTrail<br/>API Logging"]
            CloudWatch["CloudWatch<br/>Logs & Metrics"]
        end
    end

    Users --> Okta
    Users --> ALB
    Okta -.->|JWT Validation| ALB
    ALB --> ConnectFlow
    ConnectFlow --> Lex
    Lex --> Lambda
    Lambda --> API

    ALB --> API
    API --> RDS
    API --> Redis
    API --> OpenSearch
    API --> Bedrock

    Ingest --> S3Docs
    Ingest --> SharePoint
    Ingest --> OpenSearch
    Ingest --> RDS
    Ingest --> Bedrock

    Sync --> Okta
    Sync --> RDS
    Sync --> Redis

    OpenSearch --> S3Index

    RDS --> KMS
    S3Docs --> KMS
    OpenSearch --> KMS
    API --> Secrets
    API --> CloudWatch
    CloudTrail --> S3Docs

    style Users fill:#FFF2ED,stroke:#FF9580,stroke-width:2px
    style Okta fill:#FFE4DC,stroke:#FF7B6B,stroke-width:2px
    style SharePoint fill:#F8F5F0,stroke:#8B3A52,stroke-width:1px
    style ALB fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#232F3E
    style ConnectFlow fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#232F3E
    style Lex fill:#FF9900,stroke:#232F3E,stroke-width:1px,color:#232F3E
    style Lambda fill:#FF9900,stroke:#232F3E,stroke-width:1px,color:#232F3E
    style API fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#232F3E
    style Ingest fill:#FF9900,stroke:#232F3E,stroke-width:1px,color:#232F3E
    style Sync fill:#FF9900,stroke:#232F3E,stroke-width:1px,color:#232F3E
    style RDS fill:#3B48CC,stroke:#232F3E,stroke-width:2px,color:#FFFFFF
    style Redis fill:#C925D1,stroke:#232F3E,stroke-width:1px,color:#FFFFFF
    style OpenSearch fill:#005EB8,stroke:#232F3E,stroke-width:2px,color:#FFFFFF
    style S3Docs fill:#3F8624,stroke:#232F3E,stroke-width:1px,color:#FFFFFF
    style S3Index fill:#3F8624,stroke:#232F3E,stroke-width:1px,color:#FFFFFF
    style Bedrock fill:#01A88D,stroke:#232F3E,stroke-width:2px,color:#FFFFFF
    style KMS fill:#DD344C,stroke:#232F3E,stroke-width:1px,color:#FFFFFF
    style Secrets fill:#DD344C,stroke:#232F3E,stroke-width:1px,color:#FFFFFF
    style CloudTrail fill:#DD344C,stroke:#232F3E,stroke-width:1px,color:#FFFFFF
    style CloudWatch fill:#DD344C,stroke:#232F3E,stroke-width:1px,color:#FFFFFF
```

---

## Component Summary

| Layer | AWS Service | Purpose |
|-------|-------------|---------|
| **User Interface** | Amazon Connect + Lex | Voice/chat interface with intent recognition |
| **API Gateway** | Application Load Balancer | HTTPS termination, routing |
| **Compute** | ECS Fargate + Lambda | Serverless RAG API, ingestion, sync |
| **Vector Search** | OpenSearch (k-NN) | Semantic search over document embeddings |
| **Database** | RDS PostgreSQL | Documents, chunks, audit logs |
| **Cache** | ElastiCache Redis | Access permissions, session state |
| **Storage** | S3 | Document storage, index snapshots |
| **AI/ML** | Amazon Bedrock | Claude 3.5 (generation), Titan (embeddings) |
| **Auth** | Okta (external) | Identity, group-based access control |
| **Security** | KMS, Secrets Manager | Encryption, credential management |
| **Compliance** | CloudTrail, CloudWatch | Audit logging, 7-year retention |

---

## Security Controls

| Control | Implementation |
|---------|----------------|
| 🔐 **Encryption at Rest** | KMS-managed keys for RDS, S3, OpenSearch |
| 🔒 **Encryption in Transit** | TLS 1.2+ on all connections |
| 👤 **Authentication** | Okta JWT validation at ALB |
| 🚫 **Authorization** | Client-based collection isolation in OpenSearch |
| 📋 **Audit Trail** | CloudTrail + CloudWatch Logs (7-year retention) |
| 🔑 **Secrets** | Secrets Manager for API keys, DB credentials |

---

## Data Flow

1. **User Query** → Connect/Lex recognizes intent → Lambda invokes RAG API
2. **Access Check** → Redis cache validates user's client permissions (from Okta sync)
3. **Vector Search** → OpenSearch k-NN searches ONLY authorized collections
4. **Generation** → Bedrock Claude generates response with context
5. **Audit** → Query logged to RDS + CloudWatch for compliance



