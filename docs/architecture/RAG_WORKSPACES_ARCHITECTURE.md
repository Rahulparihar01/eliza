# RAG & Workspaces Architecture (ElizaPlatform)

Architecture diagram focused on **RAG**, **Workspaces**, **data source connections** (e.g. S3), and **Bedrock** as the inference service for embeddings and chat.

---

```mermaid
flowchart TB
    subgraph Users["Users"]
        UI["Frontend / API"]
    end

    subgraph Workspaces["Workspaces (RAGFlowDomain)"]
        WS["Workspace"]
        WS --> KB1["Knowledge Base 1"]
        WS --> KB2["Knowledge Base 2"]
        WS --> KBn["Knowledge Base n"]
    end

    subgraph DataSources["Data Source Connections"]
        S3["Amazon S3<br/>bucket/prefix"]
        ES_Legacy["Elasticsearch<br/>(legacy)"]
        LocalDir["Local Directory"]
    end

    subgraph Ingestion["Ingestion Pipeline"]
        S3Sync["KB S3 Sync Service"]
        ObjStore["Object Storage Service<br/>(S3 / MinIO)"]
        DocParser["Document Parser<br/>(docling, VLM, GPT-4o)"]
        Chunker["Chunking Service"]
    end

    subgraph RAG["RAG Model & Vector Store"]
        Embed["Embedding Service"]
        VecStore["Vector Store<br/>(OpenSearch / Elasticsearch)"]
    end

    subgraph Bedrock["Amazon Bedrock"]
        TitanEmbed["Titan Embeddings<br/>amazon.titan-embed-text-v1"]
        ClaudeGen["Claude / Foundation Models<br/>(chat completion)"]
    end

    subgraph Chat["RAG Chat"]
        Retrieval["Retrieval Service"]
        RAGChat["RAG Chat Service<br/>(LiteLLM)"]
    end

    %% Workspace & KB config
    UI --> Workspaces
    KB1 -.->|source_type: s3<br/>source_config: bucket, prefix| S3
    KB2 -.->|source_type: elasticsearch| ES_Legacy
    KBn -.->|source_type: local_directory| LocalDir

    %% S3 sync path
    S3 -->|list & download PDFs| S3Sync
    S3Sync -->|store raw blobs| ObjStore
    S3Sync -->|parse → chunk → embed → index| DocParser
    DocParser --> Chunker
    Chunker --> Embed
    Embed -->|Titan embeddings| TitanEmbed
    TitanEmbed -->|vectors| VecStore

    %% Upload path (non-S3)
    ObjStore --> DocParser

    %% Query path
    UI -->|question| RAGChat
    RAGChat --> Retrieval
    Retrieval -->|query embedding| Embed
    Embed -->|query vector| TitanEmbed
    Retrieval -->|k-NN search| VecStore
    VecStore -->|retrieved chunks| Retrieval
    Retrieval -->|context| RAGChat
    RAGChat -->|LiteLLM bedrock/...| ClaudeGen
    ClaudeGen -->|answer| RAGChat
    RAGChat -->|answer + citations| UI

    %% Styling
    style Bedrock fill:#232F3E,stroke:#FF9900,color:#fff
    style TitanEmbed fill:#01A88D,stroke:#232F3E,color:#fff
    style ClaudeGen fill:#01A88D,stroke:#232F3E,color:#fff
    style S3 fill:#3F8624,stroke:#232F3E,color:#fff
    style VecStore fill:#005EB8,stroke:#232F3E,color:#fff
    style Workspaces fill:#F2F2F2,stroke:#333,stroke-width:2px
```

---

## Legend

| Component | Description |
|-----------|-------------|
| **Workspace (RAGFlowDomain)** | Tenant workspace; can have multiple knowledge bases. |
| **Knowledge Base** | Holds documents for RAG. Source type: `s3`, `elasticsearch`, or `local_directory`. |
| **S3** | Data source: bucket + prefix; sync via `KnowledgeBaseS3SyncService`. |
| **Object Storage** | Tenant S3/MinIO for raw document blobs (after upload or S3 sync). |
| **Document Parser** | docling, VLM, or GPT-4o for extract; then chunking. |
| **Embedding Service** | Configurable (OpenAI, local, or **Bedrock Titan**). Diagram shows Bedrock path. |
| **Vector Store** | AWS OpenSearch (or local Elasticsearch); company/domain-scoped indices. |
| **Bedrock** | **Embeddings**: Titan (`amazon.titan-embed-text-v1`). **Chat**: Claude/foundation models via LiteLLM `bedrock/...`. |

---

## Data flow summary

1. **Data source connections**  
   Each knowledge base has `source_type` and `source_config`. For S3: `bucket` + `prefix` (and optional `file_extensions`). S3 sync runs on a schedule or on-demand.

2. **Ingestion**  
   S3 sync (or upload) → raw files in object storage → document parser → chunks → **Bedrock Titan** embeddings → vectors written to **OpenSearch/Elasticsearch**.

3. **RAG query**  
   User question → **RetrievalService** (query embedding via **Bedrock Titan**, k-NN on vector store) → context + question → **RAG Chat Service** (LiteLLM) → **Bedrock** (e.g. Claude) → answer and citations back to UI.

---

## Config (relevant env)

- **RAG embeddings (Bedrock):** `RAG_EMBEDDING_PROVIDER=bedrock`, `RAG_BEDROCK_EMBEDDING_REGION`, `ragflow_default_embedding_model` (e.g. `amazon.titan-embed-text-v1`).
- **Vector store:** `RAG_OPENSEARCH_HOST`, `RAG_OPENSEARCH_REGION`, `RAG_OPENSEARCH_INDEX_PREFIX`; or `ELASTICSEARCH_HOSTS` + `RAG_USE_LOCAL_ELASTICSEARCH` for local ES.
- **S3 KB sync:** `RAG_KB_S3_SYNC_ENABLED`, `RAG_KB_S3_SYNC_INTERVAL_SECONDS`, `RAG_KB_S3_SYNC_MAX_FILES_PER_RUN`.
- **Chat model:** Customer AI provider “Bedrock” and model id (e.g. `bedrock/anthropic.claude-3-sonnet-...`) via LiteLLM.
