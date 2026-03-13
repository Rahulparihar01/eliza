# Business Intelligence Flow - High Level Overview

A simplified architecture diagram showing the main components of the Business Intelligence system.

---

## Architecture Overview

```mermaid
flowchart TB
    subgraph Input["📥 INPUT"]
        User["User"]
        Question["Natural Language Question"]
    end

    subgraph Platform["🏢 ELIZA PLATFORM"]
        API["REST API<br/>/api/bi/questions"]
        Queue["Task Queue<br/>(Celery + Redis)"]
        
        subgraph Flows["AI Processing Flows"]
            Flow1["Task Enrichment Flow<br/>━━━━━━━━━━━━━━━<br/>• Intent Analysis<br/>• Context Enrichment<br/>• Prompt Generation"]
            Flow2["Data Analysis Flow<br/>━━━━━━━━━━━━━━━<br/>• Data Retrieval<br/>• Analysis & Insights"]
        end

        subgraph Tools["Agent Tools"]
            HRTool["HR Database Tool"]
            DocTool["Document Search Tool"]
        end
    end

    subgraph DataSources["💾 DATA SOURCES"]
        HRDB["HR Database<br/>(PostgreSQL)"]
        VectorDB["Vector Index<br/>(FAISS)"]
    end

    subgraph LLM["🤖 LLM PROVIDERS"]
        OpenAI["OpenAI"]
        Anthropic["Anthropic"]
        Bedrock["AWS Bedrock"]
    end

    subgraph Output["📤 OUTPUT"]
        Result["Analysis Result<br/>━━━━━━━━━━━━━━━<br/>• Executive Summary<br/>• Key Findings<br/>• Recommendations"]
    end

    User --> Question
    Question --> API
    API --> Queue
    Queue --> Flow1
    Flow1 --> Flow2
    Flow2 --> HRTool
    Flow2 --> DocTool
    HRTool --> HRDB
    DocTool --> VectorDB
    Flow1 -.-> LLM
    Flow2 -.-> LLM
    Flow2 --> Result

    classDef input fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef platform fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef data fill:#ECEFF1,stroke:#607D8B,stroke-width:2px
    classDef llm fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef output fill:#C8E6C9,stroke:#388E3C,stroke-width:2px

    class User,Question input
    class API,Queue,Flow1,Flow2,HRTool,DocTool platform
    class HRDB,VectorDB data
    class OpenAI,Anthropic,Bedrock llm
    class Result output
```

---

## Processing Pipeline

```mermaid
flowchart LR
    Q["Question"] --> E["Enrichment"] --> A["Analysis"] --> R["Result"]
    
    subgraph E["Task Enrichment"]
        E1["Intent Detection"]
        E2["Context Addition"]
        E3["Prompt Optimization"]
    end

    subgraph A["Data Analysis"]
        A1["Data Retrieval"]
        A2["Insight Generation"]
    end
```

---

## Key Components

| Component | Description |
|-----------|-------------|
| **REST API** | Receives questions, returns results |
| **Task Queue** | Async processing with Celery + Redis |
| **Task Enrichment Flow** | Transforms questions into optimized prompts |
| **Data Analysis Flow** | Retrieves data and generates insights |
| **HR Database Tool** | Queries structured employee data |
| **Document Search Tool** | Semantic search over company documents |
| **LLM Providers** | OpenAI, Anthropic, or AWS Bedrock |




