# Business Intelligence Flow Architecture

This document provides architecture diagrams for the Business Intelligence (BI) flow, which processes natural language questions and generates data-driven insights using AI agents.

---

## High-Level Architecture Overview

```mermaid
flowchart TB
    subgraph Input["📥 USER INPUT"]
        User["User"]
        Question["Natural Language Question<br/>━━━━━━━━━━━━━━━<br/>'What are the top skills<br/>in the Engineering department?'"]
    end

    subgraph API["🔌 API LAYER"]
        BIEndpoint["POST /api/bi/questions<br/>━━━━━━━━━━━━━━━<br/>• Validate request<br/>• Create question record<br/>• Queue Celery task"]
    end

    subgraph TaskQueue["📬 TASK QUEUE"]
        Redis["Redis<br/>━━━━━━━━━━━━━━━<br/>Celery Broker"]
        CeleryWorker["Celery Worker<br/>━━━━━━━━━━━━━━━<br/>process_bi_question task"]
    end

    subgraph Flow1["🔄 FLOW 1: Task Enrichment"]
        direction TB
        TEFlow["Task Enrichment Flow<br/>(CrewAI)"]
        
        subgraph TEAgents["Enrichment Agents"]
            IntentAgent["🤖 Task Analyzer Agent<br/>━━━━━━━━━━━━━━━<br/>• Detect intent type<br/>• Assess complexity<br/>• Extract entities"]
            EnrichAgent["🤖 Enrichment Agent<br/>━━━━━━━━━━━━━━━<br/>• Add business context<br/>• Suggest refinements<br/>• Identify related topics"]
            PromptAgent["🤖 Prompt Generator<br/>━━━━━━━━━━━━━━━<br/>• Create optimized prompt<br/>• Define output format<br/>• Set validation criteria"]
        end
    end

    subgraph Connectivity["🔗 CONNECTIVITY CHECK"]
        ConnCheck["Data Source Connectivity<br/>━━━━━━━━━━━━━━━<br/>• Vector Index (required)<br/>• HR Database (optional)"]
    end

    subgraph Flow2["🔄 FLOW 2: Data Analysis"]
        direction TB
        DAFlow["Data Analysis Flow<br/>(CrewAI)"]
        
        subgraph DAAgents["Analysis Agents"]
            RetrievalAgent["🤖 Data Retrieval Agent<br/>━━━━━━━━━━━━━━━<br/>• Query HR database<br/>• Search documents<br/>• Aggregate data"]
            AnalysisAgent["🤖 BI Analyst Agent<br/>━━━━━━━━━━━━━━━<br/>• Analyze data<br/>• Generate insights<br/>• Create recommendations"]
        end

        subgraph Tools["🛠️ Agent Tools"]
            HRTool["HR Database Tool<br/>━━━━━━━━━━━━━━━<br/>• employees<br/>• departments<br/>• skills<br/>• performance<br/>• training"]
            DocTool["Document Search Tool<br/>━━━━━━━━━━━━━━━<br/>• FAISS vector search<br/>• Semantic similarity<br/>• Company documents"]
        end
    end

    subgraph DataSources["💾 DATA SOURCES"]
        HRDB["HR Database<br/>(PostgreSQL)<br/>━━━━━━━━━━━━━━━<br/>Structured employee data"]
        VectorDB["Vector Index<br/>(FAISS)<br/>━━━━━━━━━━━━━━━<br/>Document embeddings"]
    end

    subgraph Output["📤 OUTPUT"]
        Result["Analysis Result<br/>━━━━━━━━━━━━━━━<br/>• Executive Summary<br/>• Key Findings<br/>• Recommendations<br/>• Data Sources Used"]
    end

    User --> Question
    Question --> BIEndpoint
    BIEndpoint --> Redis
    Redis --> CeleryWorker
    
    CeleryWorker --> TEFlow
    TEFlow --> IntentAgent
    IntentAgent --> EnrichAgent
    EnrichAgent --> PromptAgent
    PromptAgent --> ConnCheck
    
    ConnCheck --> DAFlow
    DAFlow --> RetrievalAgent
    RetrievalAgent --> HRTool
    RetrievalAgent --> DocTool
    HRTool --> HRDB
    DocTool --> VectorDB
    RetrievalAgent --> AnalysisAgent
    AnalysisAgent --> Result

    classDef input fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef api fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef queue fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef flow fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    classDef agent fill:#E1F5FE,stroke:#0288D1,stroke-width:2px
    classDef tool fill:#FCE4EC,stroke:#C2185B,stroke-width:2px
    classDef data fill:#ECEFF1,stroke:#607D8B,stroke-width:2px
    classDef output fill:#C8E6C9,stroke:#388E3C,stroke-width:2px

    class User,Question input
    class BIEndpoint api
    class Redis,CeleryWorker queue
    class TEFlow,DAFlow flow
    class IntentAgent,EnrichAgent,PromptAgent,RetrievalAgent,AnalysisAgent agent
    class HRTool,DocTool tool
    class HRDB,VectorDB data
    class Result output
```

---

## Detailed Processing Flow (Sequence)

```mermaid
sequenceDiagram
    autonumber
    participant User as User
    participant API as BI API
    participant DB as PostgreSQL
    participant Redis as Redis Queue
    participant Worker as Celery Worker
    participant TEFlow as Task Enrichment Flow
    participant DAFlow as Data Analysis Flow
    participant HRDB as HR Database
    participant Vector as Vector Index
    participant LLM as LLM (OpenAI/Anthropic)

    rect rgb(232, 245, 233)
        Note over User,DB: Phase 1: Question Submission
        User->>+API: POST /api/bi/questions<br/>{question, company_hr_dataset}
        API->>DB: Create BIQuestion record<br/>(status: pending)
        API->>Redis: Queue task: process_bi_question
        API-->>-User: 202 Accepted<br/>{question_id}
    end

    rect rgb(255, 243, 224)
        Note over Worker,TEFlow: Phase 2: Task Enrichment Flow
        Redis->>+Worker: Consume task
        Worker->>DB: Update status: enriching
        Worker->>+TEFlow: Start Task Enrichment Flow

        Note over TEFlow,LLM: Stage 1: Intent Analysis
        TEFlow->>+LLM: Analyze intent, complexity, entities
        LLM-->>-TEFlow: TaskAnalysis result

        Note over TEFlow,LLM: Stage 2: Context Enrichment
        TEFlow->>+LLM: Add business context
        LLM-->>-TEFlow: RAG context

        Note over TEFlow,LLM: Stage 3: Prompt Generation
        TEFlow->>+LLM: Generate optimized prompt
        LLM-->>-TEFlow: EnrichedPrompt

        TEFlow-->>-Worker: Enriched prompt ready
        Worker->>DB: Save BIEnrichedPrompt
    end

    rect rgb(227, 242, 253)
        Note over Worker,Vector: Phase 3: Connectivity Check
        Worker->>Vector: Check vector index health
        Vector-->>Worker: ✓ Healthy
        Worker->>HRDB: Check HR database health
        HRDB-->>Worker: ✓ Healthy
    end

    rect rgb(243, 229, 245)
        Note over Worker,DAFlow: Phase 4: Data Analysis Flow
        Worker->>DB: Update status: analyzing
        Worker->>DB: Create BIAnalysisSession
        Worker->>+DAFlow: Start Data Analysis Flow

        Note over DAFlow,Vector: Stage 1: Data Retrieval
        DAFlow->>+HRDB: HR Database Tool query
        HRDB-->>-DAFlow: Employee/department data
        DAFlow->>+Vector: Document Search Tool query
        Vector-->>-DAFlow: Relevant document chunks

        Note over DAFlow,LLM: Stage 2: Data Analysis
        DAFlow->>+LLM: Analyze retrieved data
        LLM-->>-DAFlow: Structured analysis

        DAFlow-->>-Worker: AnalysisResult
    end

    rect rgb(200, 230, 201)
        Note over Worker,User: Phase 5: Result Delivery
        Worker->>DB: Save BIAnalysisResult
        Worker->>DB: Update status: completed
        Worker-->>-Redis: Task complete

        User->>+API: GET /api/bi/questions/{id}
        API->>DB: Fetch question + result
        API-->>-User: Complete analysis response
    end
```

---

## Task Enrichment Flow Detail

```mermaid
flowchart TB
    subgraph TaskEnrichmentFlow["🔄 TASK ENRICHMENT FLOW"]
        direction TB

        subgraph Input["Input"]
            OriginalQ["Original Question<br/>━━━━━━━━━━━━━━━<br/>'What are the top skills<br/>in Engineering?'"]
            UserCtx["User Context<br/>━━━━━━━━━━━━━━━<br/>• user_id<br/>• customer_id<br/>• role<br/>• department"]
        end

        subgraph Stage1["Stage 1: Intent Analysis"]
            IntentAgent["🤖 Task Analyzer Agent<br/>━━━━━━━━━━━━━━━<br/>Role: Business Task Analyst<br/>Goal: Understand user intent"]
            
            subgraph IntentOutput["TaskAnalysis Output"]
                Intent["intent_type:<br/>data_analysis"]
                Complexity["complexity:<br/>moderate"]
                Confidence["confidence_score:<br/>0.85"]
                Entities["entities:<br/>['Engineering', 'skills']"]
                Keywords["keywords:<br/>['top', 'skills', 'department']"]
                DataSources["data_sources_needed:<br/>['hr_database', 'documents']"]
            end
        end

        subgraph Stage2["Stage 2: Context Enrichment"]
            EnrichAgent["🤖 Enrichment Agent<br/>━━━━━━━━━━━━━━━<br/>Role: Context Enricher<br/>Goal: Add business context"]
            
            subgraph EnrichOutput["RAG Context Output"]
                EnrichedCtx["enriched_context:<br/>• Relevant metrics<br/>• Time periods<br/>• Benchmarks"]
                Refinements["suggested_refinements:<br/>• Consider skill levels<br/>• Include certifications"]
                Related["related_topics:<br/>• Training programs<br/>• Skill gaps"]
            end
        end

        subgraph Stage3["Stage 3: Prompt Generation"]
            PromptAgent["🤖 Prompt Generator<br/>━━━━━━━━━━━━━━━<br/>Role: Prompt Optimizer<br/>Goal: Create analysis prompt"]
            
            subgraph PromptOutput["EnrichedPrompt Output"]
                EnrichedP["enriched_prompt:<br/>'Analyze the Engineering<br/>department to identify top<br/>skills by frequency...'"]
                Instructions["processing_instructions:<br/>• Use HR database<br/>• Search documents"]
                Format["expected_output_format:<br/>• executive_summary<br/>• key_findings<br/>• recommendations"]
                Validation["validation_criteria:<br/>• completeness<br/>• accuracy<br/>• clarity"]
            end
        end

        subgraph Output["Output"]
            FinalPrompt["Enriched Prompt<br/>Ready for Analysis"]
        end
    end

    OriginalQ --> IntentAgent
    UserCtx --> IntentAgent
    IntentAgent --> Intent
    IntentAgent --> Complexity
    IntentAgent --> Confidence
    IntentAgent --> Entities
    IntentAgent --> Keywords
    IntentAgent --> DataSources
    
    IntentOutput --> EnrichAgent
    EnrichAgent --> EnrichedCtx
    EnrichAgent --> Refinements
    EnrichAgent --> Related
    
    EnrichOutput --> PromptAgent
    PromptAgent --> EnrichedP
    PromptAgent --> Instructions
    PromptAgent --> Format
    PromptAgent --> Validation
    
    PromptOutput --> FinalPrompt

    classDef input fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef agent fill:#E1F5FE,stroke:#0288D1,stroke-width:2px
    classDef output fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
    classDef final fill:#C8E6C9,stroke:#388E3C,stroke-width:2px

    class OriginalQ,UserCtx input
    class IntentAgent,EnrichAgent,PromptAgent agent
    class Intent,Complexity,Confidence,Entities,Keywords,DataSources,EnrichedCtx,Refinements,Related,EnrichedP,Instructions,Format,Validation output
    class FinalPrompt final
```

---

## Data Analysis Flow Detail

```mermaid
flowchart TB
    subgraph DataAnalysisFlow["🔄 DATA ANALYSIS FLOW"]
        direction TB

        subgraph Input["Input"]
            EnrichedPrompt["Enriched Prompt<br/>from Task Enrichment"]
            Config["Configuration<br/>━━━━━━━━━━━━━━━<br/>• customer_id<br/>• company_hr_dataset<br/>• data_sources_needed"]
        end

        subgraph Stage1["Stage 1: Data Retrieval"]
            RetrievalAgent["🤖 Data Retrieval Agent<br/>━━━━━━━━━━━━━━━<br/>Role: Data Specialist<br/>Goal: Gather relevant data"]
            
            subgraph Tools["Agent Tools"]
                HRTool["🛠️ HR Database Tool<br/>━━━━━━━━━━━━━━━<br/>Query Types:<br/>• employees<br/>• departments<br/>• skills<br/>• performance<br/>• training"]
                
                DocTool["🛠️ Document Search Tool<br/>━━━━━━━━━━━━━━━<br/>• FAISS vector search<br/>• Semantic similarity<br/>• Top-k results<br/>• Similarity threshold"]
            end

            subgraph DataSources["Data Sources"]
                HRDB["PostgreSQL<br/>━━━━━━━━━━━━━━━<br/>HR Schema Tables"]
                VectorDB["FAISS Index<br/>━━━━━━━━━━━━━━━<br/>Document Embeddings"]
            end

            subgraph RetrievalOutput["DataRetrievalResult"]
                HRData["hr_data:<br/>Employee records,<br/>department info"]
                DocData["document_data:<br/>Relevant document<br/>chunks"]
                Sources["data_sources_used:<br/>['hr_database', 'documents']"]
            end
        end

        subgraph Stage2["Stage 2: Data Analysis"]
            AnalysisAgent["🤖 BI Analyst Agent<br/>━━━━━━━━━━━━━━━<br/>Role: Business Intelligence Analyst<br/>Goal: Generate actionable insights"]
            
            subgraph AnalysisOutput["AnalysisResult"]
                ExecSummary["executive_summary:<br/>'The Engineering department<br/>has 45 employees with<br/>Python as the top skill...'"]
                Findings["key_findings:<br/>• Python: 78% of engineers<br/>• AWS: 65% certified<br/>• ML skills growing 25%"]
                Recommendations["recommendations:<br/>• Invest in ML training<br/>• Cross-train on cloud<br/>• Hire senior architects"]
                Confidence["confidence_score: 0.85"]
            end
        end

        subgraph Output["Output"]
            FinalResult["Complete Analysis<br/>━━━━━━━━━━━━━━━<br/>Ready for user"]
        end
    end

    EnrichedPrompt --> RetrievalAgent
    Config --> RetrievalAgent
    RetrievalAgent --> HRTool
    RetrievalAgent --> DocTool
    HRTool --> HRDB
    DocTool --> VectorDB
    HRDB --> HRData
    VectorDB --> DocData
    HRTool --> Sources
    DocTool --> Sources
    
    HRData --> AnalysisAgent
    DocData --> AnalysisAgent
    AnalysisAgent --> ExecSummary
    AnalysisAgent --> Findings
    AnalysisAgent --> Recommendations
    AnalysisAgent --> Confidence
    
    AnalysisOutput --> FinalResult

    classDef input fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef agent fill:#E1F5FE,stroke:#0288D1,stroke-width:2px
    classDef tool fill:#FCE4EC,stroke:#C2185B,stroke-width:2px
    classDef data fill:#ECEFF1,stroke:#607D8B,stroke-width:2px
    classDef output fill:#FFF3E0,stroke:#EF6C00,stroke-width:1px
    classDef final fill:#C8E6C9,stroke:#388E3C,stroke-width:2px

    class EnrichedPrompt,Config input
    class RetrievalAgent,AnalysisAgent agent
    class HRTool,DocTool tool
    class HRDB,VectorDB data
    class HRData,DocData,Sources,ExecSummary,Findings,Recommendations,Confidence output
    class FinalResult final
```

---

## Database Schema

```mermaid
erDiagram
    BIQuestion ||--o| BIEnrichedPrompt : has
    BIQuestion ||--o| BIAnalysisSession : has
    BIQuestion ||--o| BIAnalysisResult : has
    BIAnalysisSession ||--o{ BIAgentResponse : contains
    BIAnalysisSession ||--o{ BITelemetryEvent : tracks

    BIQuestion {
        int id PK
        string question_id UK
        int user_id FK
        string customer_id
        string company_hr_dataset
        string original_question
        enum status
        int enriched_prompt_id FK
        int analysis_session_id FK
        int result_id FK
        string error_message
        datetime created_at
        datetime completed_at
    }

    BIEnrichedPrompt {
        int id PK
        string prompt_id UK
        int question_id FK
        text original_input
        text enriched_prompt
        string intent_type
        string complexity
        float confidence_score
        json processing_instructions
        json expected_output_format
        json validation_criteria
        float quality_score
        json rag_context
        datetime created_at
    }

    BIAnalysisSession {
        int id PK
        string session_id UK
        int question_id FK
        int enriched_prompt_id FK
        enum status
        json agents_executed
        json tools_used
        json data_sources_queried
        string error_message
        datetime started_at
        datetime completed_at
    }

    BIAnalysisResult {
        int id PK
        string result_id UK
        int question_id FK
        int session_id FK
        text analysis_text
        text executive_summary
        json key_findings
        json data_sources_used
        float confidence_score
        json recommendations
        json visualizations
        json metadata
        datetime created_at
    }

    BIAgentResponse {
        int id PK
        int session_id FK
        string agent_name
        string stage_name
        text input_prompt
        text response_text
        text reasoning
        json tool_calls
        float confidence_score
        int tokens_used
        int duration_ms
        json response_metadata
        datetime created_at
    }

    BITelemetryEvent {
        int id PK
        int session_id FK
        string event_type
        string stage_name
        string agent_name
        string tool_name
        string user_message
        float progress_percentage
        json data
        json error_details
        int duration_ms
        datetime timestamp
    }
```

---

## Question Status Flow

```mermaid
stateDiagram-v2
    [*] --> pending: Question submitted

    pending --> enriching: Task picked up
    
    enriching --> analyzing: Enrichment complete
    enriching --> failed: Enrichment error

    analyzing --> completed: Analysis complete
    analyzing --> failed: Analysis error
    analyzing --> failed: Timeout

    completed --> [*]: Success
    failed --> [*]: Error

    note right of pending
        Question created,
        waiting in queue
    end note

    note right of enriching
        Task Enrichment Flow
        running (3 agents)
    end note

    note right of analyzing
        Data Analysis Flow
        running (2 agents)
    end note

    note right of completed
        Results available
        for user
    end note

    note right of failed
        Error message
        stored
    end note
```

---

## Agent Configuration

```mermaid
flowchart TB
    subgraph AgentConfig["🔧 AGENT CONFIGURATION SYSTEM"]
        direction TB

        subgraph Layer1["Layer 1: Code Defaults"]
            Default["Default Agent Configs<br/>━━━━━━━━━━━━━━━<br/>Hardcoded in flow code<br/>as fallback"]
        end

        subgraph Layer2["Layer 2: Database Config"]
            DBConfig["Customer Agent Configs<br/>━━━━━━━━━━━━━━━<br/>Stored in database<br/>per customer"]
        end

        subgraph Merge["Configuration Merge"]
            MergeLogic["AgentConfigurationService<br/>━━━━━━━━━━━━━━━<br/>Layer 2 overrides Layer 1<br/>Returns complete config"]
        end

        subgraph Providers["🔌 LLM Providers"]
            OpenAI["OpenAI<br/>gpt-4o-mini"]
            Anthropic["Anthropic<br/>claude-3-sonnet"]
            Bedrock["AWS Bedrock<br/>claude-3"]
            Groq["Groq<br/>llama-3"]
        end

        subgraph Agents["Configured Agents"]
            TaskAnalyzer["task_analyzer_agent"]
            Enrichment["enrichment_agent"]
            DataRetrieval["data_retrieval_agent"]
            BIAnalyst["bi_analyst_agent"]
        end
    end

    Default --> MergeLogic
    DBConfig --> MergeLogic
    MergeLogic --> TaskAnalyzer
    MergeLogic --> Enrichment
    MergeLogic --> DataRetrieval
    MergeLogic --> BIAnalyst
    
    TaskAnalyzer --> OpenAI
    Enrichment --> OpenAI
    DataRetrieval --> Anthropic
    BIAnalyst --> Anthropic

    classDef layer fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef merge fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef provider fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef agent fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px

    class Default,DBConfig layer
    class MergeLogic merge
    class OpenAI,Anthropic,Bedrock,Groq provider
    class TaskAnalyzer,Enrichment,DataRetrieval,BIAnalyst agent
```

---

## Component Summary

| Component | Purpose | Technology |
|-----------|---------|------------|
| **BI API** | REST endpoints for questions | FastAPI |
| **Task Queue** | Async task processing | Celery + Redis |
| **Task Enrichment Flow** | Transform questions to prompts | CrewAI Flow |
| **Data Analysis Flow** | Retrieve & analyze data | CrewAI Flow |
| **HR Database Tool** | Query structured HR data | PostgreSQL |
| **Document Search Tool** | Semantic document search | FAISS + OpenAI Embeddings |
| **Agent Config Service** | Runtime agent configuration | Database + Code defaults |
| **Telemetry System** | Track execution & progress | PostgreSQL |

---

## Key Features

1. **Two-Phase Processing**
   - Phase 1: Enrich raw question into optimized prompt
   - Phase 2: Retrieve data and generate analysis

2. **Multi-Agent Architecture**
   - 5 specialized agents with distinct roles
   - Runtime-configurable LLM providers
   - Tool-equipped data retrieval agents

3. **Dual Data Sources**
   - Structured HR data (PostgreSQL)
   - Unstructured documents (FAISS vector search)

4. **Real-Time Telemetry**
   - Progress tracking per stage
   - Agent response logging
   - Tool execution tracking

5. **Configurable Agents**
   - Per-customer LLM configuration
   - Multiple provider support (OpenAI, Anthropic, Bedrock, Groq)
   - Layered configuration (code defaults + database overrides)




