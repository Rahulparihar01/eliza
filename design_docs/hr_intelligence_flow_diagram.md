# Eliza Platform: HR Intelligence Flow

This document provides process flow diagrams for the HR Intelligence (Talent Intelligence) system, highlighting the complete workflow, AI agents, and available integrations.

---

## High-Level Process Flow

```mermaid
flowchart TB
    subgraph Inputs["📥 INPUTS"]
        JD["Job Description<br/>(PDF/Text)"]
        ICD["Ideal Candidate<br/>Description"]
        Resumes["Applicant Resumes<br/>(PDF Upload)"]
        Baseline["Baseline Employees<br/>(Optional Selection)"]
    end

    subgraph ElizaPlatform["🏢 ELIZA PLATFORM"]
        direction TB
        
        subgraph Orchestrator["Flow Orchestrator"]
            API["REST API<br/>━━━━━━━━━━━━━━━<br/>• Start Analysis<br/>• Track Progress<br/>• Get Results"]
        end

        subgraph Stage1["Stage 1: Baseline Building"]
            BaselineBuilder["Baseline Profile Builder<br/>━━━━━━━━━━━━━━━<br/>Builds ideal candidate profile<br/>from current top performers"]
        end

        subgraph Stage2["Stage 2: Diagnostic Analysis"]
            DiagnosticAgent["🤖 Diagnostic Agent<br/>━━━━━━━━━━━━━━━<br/>• Analyzes job requirements<br/>• Prioritizes attributes<br/>• Assigns competency weights"]
        end

        subgraph Stage3["Stage 3: Resume Processing"]
            DoclingVLM["Docling VLM Parser<br/>━━━━━━━━━━━━━━━<br/>• Parses PDF resumes<br/>• Extracts structured data<br/>• Skills, experience, education"]
        end

        subgraph DualPipeline["Stage 4-6: Dual Pipeline Scoring"]
            direction LR
            
            subgraph ApplicantPipeline["Pipeline 1: Applicants"]
                ApplicantScore["Score Applicants<br/>━━━━━━━━━━━━━━━<br/>6-dimension scoring<br/>against baseline"]
            end
            
            subgraph MarketPipeline["Pipeline 2: Market"]
                PDLQuery["Build PDL Query<br/>━━━━━━━━━━━━━━━<br/>Skills, titles,<br/>experience filters"]
                MarketSearch["Search Market<br/>━━━━━━━━━━━━━━━<br/>Find passive<br/>candidates"]
                MarketScore["Score Market<br/>━━━━━━━━━━━━━━━<br/>Same 6-dimension<br/>scoring"]
            end
        end

        subgraph Stage7["Stage 7: Synthesis"]
            SynthesisAgent["🤖 Synthesis Agent<br/>━━━━━━━━━━━━━━━<br/>• Generates insights<br/>• Identifies patterns<br/>• Creates recommendations"]
        end

        subgraph Results["📊 Results"]
            TopCandidates["Top 3 Overall<br/>Candidates"]
            InsightsReport["Insights Report<br/>& Recommendations"]
            Provenance["Full Audit Trail<br/>(Provenance)"]
        end
    end

    subgraph Integrations["🔌 INTEGRATIONS"]
        direction TB
        
        subgraph ATSIntegrations["ATS Integrations"]
            Greenhouse["🌿 Greenhouse<br/>━━━━━━━━━━━━━━━<br/>Job postings<br/>Applicant data"]
            Lever["⚡ Lever<br/>━━━━━━━━━━━━━━━<br/>(Coming Soon)"]
            Workday["📊 Workday<br/>━━━━━━━━━━━━━━━<br/>(Coming Soon)"]
        end
        
        subgraph DataProviders["Data Providers"]
            PDL["👥 People Data Labs<br/>━━━━━━━━━━━━━━━<br/>200M+ profiles<br/>Market candidates"]
        end
        
        subgraph KnowledgeGraph["Knowledge Graph"]
            Neo4j["🔗 Neo4j<br/>━━━━━━━━━━━━━━━<br/>Employee relationships<br/>Career paths<br/>Skill networks"]
        end
    end

    %% Input flows
    JD --> API
    ICD --> API
    Resumes --> API
    Baseline --> API

    %% Main flow
    API --> BaselineBuilder
    BaselineBuilder --> DiagnosticAgent
    DiagnosticAgent --> DoclingVLM
    DoclingVLM --> ApplicantScore
    DiagnosticAgent --> PDLQuery
    PDLQuery --> MarketSearch
    MarketSearch --> MarketScore
    ApplicantScore --> SynthesisAgent
    MarketScore --> SynthesisAgent
    SynthesisAgent --> TopCandidates
    SynthesisAgent --> InsightsReport
    SynthesisAgent --> Provenance

    %% Integration connections
    Greenhouse -.->|"Applicants"| API
    PDL -.->|"Market Candidates"| MarketSearch
    Neo4j -.->|"Employee Data"| BaselineBuilder

    classDef input fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef platform fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef agent fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef integration fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    classDef result fill:#FFEBEE,stroke:#C62828,stroke-width:2px

    class JD,ICD,Resumes,Baseline input
    class API,BaselineBuilder,DoclingVLM,ApplicantScore,PDLQuery,MarketSearch,MarketScore platform
    class DiagnosticAgent,SynthesisAgent agent
    class Greenhouse,Lever,Workday,PDL,Neo4j integration
    class TopCandidates,InsightsReport,Provenance result
```

---

## Detailed Stage-by-Stage Flow

```mermaid
flowchart TB
    subgraph Input["📥 Analysis Request"]
        Start([User Starts Analysis])
        InputData["• Job Description (PDF/Text)<br/>• Ideal Candidate Description<br/>• Uploaded Resumes (50 max)<br/>• Selected Baseline Employees"]
    end

    subgraph Stage1["🏗️ STAGE 1: Build Baseline Profile"]
        S1Start["Query Neo4j for<br/>Current Top Performers"]
        S1Process["Extract Common Patterns:<br/>• Skills distributions<br/>• Career paths<br/>• Company backgrounds<br/>• Education patterns"]
        S1Output["Baseline Profile<br/>━━━━━━━━━━━━━━━<br/>Prototype employee IDs<br/>Attribute weights<br/>Success patterns"]
    end

    subgraph Stage2["🤖 STAGE 2: Diagnostic Agent (AI)"]
        S2Input["Inputs:<br/>• Job Description<br/>• Ideal Candidate<br/>• Baseline Profile"]
        S2Agent["Diagnostic Agent<br/>━━━━━━━━━━━━━━━<br/>LLM: GPT-4o-mini"]
        S2Output["Diagnostic Report<br/>━━━━━━━━━━━━━━━<br/>• Competency list<br/>• Attribute weights<br/>• Must-haves vs Nice-to-haves<br/>• Confidence score"]
    end

    subgraph Stage3["📄 STAGE 3: Parse Applicant Resumes"]
        S3Input["Resume PDFs<br/>(up to 50)"]
        S3Parser["Docling VLM Parser<br/>━━━━━━━━━━━━━━━<br/>Model: granite-docling-258M"]
        S3Output["Parsed Resumes<br/>━━━━━━━━━━━━━━━<br/>• Name, Contact<br/>• Skills list<br/>• Work history<br/>• Education<br/>• Certifications"]
    end

    subgraph Stage4["📊 STAGE 4: Score Applicants"]
        S4Input["Parsed Resumes +<br/>Diagnostic Report +<br/>Baseline Profile"]
        S4Scoring["Multi-Dimensional<br/>Scoring Engine"]
        S4Dims["6 Scoring Dimensions:<br/>━━━━━━━━━━━━━━━<br/>1. Skills Match<br/>2. Experience Fit<br/>3. Career Trajectory<br/>4. Company Background<br/>5. Education<br/>6. Cultural Signals"]
        S4Output["Scored Applicants<br/>━━━━━━━━━━━━━━━<br/>Overall score (0-100)<br/>Per-dimension scores<br/>Reasoning"]
    end

    subgraph Stage5["🔍 STAGE 5: Market Search (PDL)"]
        S5Query["Build PDL Query<br/>━━━━━━━━━━━━━━━<br/>• Required skills<br/>• Job titles<br/>• Experience range<br/>• Location filters"]
        S5API["People Data Labs API<br/>━━━━━━━━━━━━━━━<br/>200M+ professional profiles"]
        S5Output["Market Candidates<br/>━━━━━━━━━━━━━━━<br/>Passive candidates<br/>not yet applied"]
    end

    subgraph Stage6["📊 STAGE 6: Score Market Candidates"]
        S6Input["Market Candidates +<br/>Same Scoring Criteria"]
        S6Scoring["Same Multi-Dimensional<br/>Scoring Engine"]
        S6Output["Scored Market<br/>Candidates"]
    end

    subgraph Stage7["🧠 STAGE 7: Synthesis Agent (AI)"]
        S7Input["All Scored Candidates:<br/>• Applicants<br/>• Market candidates"]
        S7Agent["Synthesis Agent<br/>━━━━━━━━━━━━━━━<br/>LLM: GPT-4o-mini"]
        S7Process["Generates:<br/>• Executive Summary<br/>• Pattern Analysis<br/>• Key Insights<br/>• Recommendations"]
        S7Output["Final Report<br/>━━━━━━━━━━━━━━━<br/>Top 3 Overall<br/>Insights & Patterns<br/>Next Steps"]
    end

    subgraph Output["📤 Analysis Complete"]
        Results["Complete Results:<br/>━━━━━━━━━━━━━━━<br/>✓ Top 3 candidates (ranked)<br/>✓ All applicant scores<br/>✓ All market scores<br/>✓ Diagnostic report<br/>✓ Synthesis insights<br/>✓ Full provenance trail"]
        End([Analysis Delivered])
    end

    Start --> InputData
    InputData --> S1Start
    S1Start --> S1Process
    S1Process --> S1Output
    S1Output --> S2Input
    S2Input --> S2Agent
    S2Agent --> S2Output
    S2Output --> S3Input
    S3Input --> S3Parser
    S3Parser --> S3Output
    S3Output --> S4Input
    S4Input --> S4Scoring
    S4Scoring --> S4Dims
    S4Dims --> S4Output
    S2Output --> S5Query
    S5Query --> S5API
    S5API --> S5Output
    S5Output --> S6Input
    S6Input --> S6Scoring
    S6Scoring --> S6Output
    S4Output --> S7Input
    S6Output --> S7Input
    S7Input --> S7Agent
    S7Agent --> S7Process
    S7Process --> S7Output
    S7Output --> Results
    Results --> End

    classDef stage fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef ai fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef external fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
```

---

## Integration Architecture

```mermaid
flowchart LR
    subgraph ElizaPlatform["Eliza Platform"]
        ConnectorFramework["Connector Framework<br/>━━━━━━━━━━━━━━━<br/>Unified interface for<br/>all data sources"]
        
        subgraph Connectors["Available Connectors"]
            direction TB
            PDLConn["People Data Labs<br/>Connector"]
            GHConn["Greenhouse<br/>Connector"]
            FSConn["Filesystem<br/>Connector"]
            FutureConn["Future Connectors<br/>━━━━━━━━━━━━━━━<br/>• Lever<br/>• Workday<br/>• BambooHR<br/>• LinkedIn"]
        end
    end

    subgraph ExternalSystems["External Systems"]
        direction TB
        
        subgraph ATS["Applicant Tracking Systems"]
            Greenhouse["🌿 Greenhouse ATS<br/>━━━━━━━━━━━━━━━<br/>• Job Postings<br/>• Applicants<br/>• Resumes<br/>• Interview Data"]
            Lever["⚡ Lever ATS"]
            Workday["📊 Workday HCM"]
        end
        
        subgraph DataEnrichment["Data Enrichment"]
            PDL["👥 People Data Labs<br/>━━━━━━━━━━━━━━━<br/>• 200M+ profiles<br/>• Skills data<br/>• Work history<br/>• Education<br/>• Contact info"]
        end
        
        subgraph GraphDB["Graph Database"]
            Neo4j["🔗 Neo4j<br/>━━━━━━━━━━━━━━━<br/>• Employee network<br/>• Career paths<br/>• Skill relationships<br/>• Company clusters"]
        end
    end

    ConnectorFramework --> PDLConn
    ConnectorFramework --> GHConn
    ConnectorFramework --> FSConn
    ConnectorFramework --> FutureConn

    PDLConn <-->|"REST API"| PDL
    GHConn <-->|"Harvest API"| Greenhouse
    FSConn <-->|"Local Files"| LocalFS["Local Storage<br/>(Dev/Testing)"]

    ElizaPlatform <-->|"Bolt Protocol"| Neo4j

    classDef platform fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef connector fill:#C8E6C9,stroke:#388E3C,stroke-width:2px
    classDef external fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px
    classDef available fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
    classDef coming fill:#FFF9C4,stroke:#F9A825,stroke-width:2px

    class ConnectorFramework platform
    class PDLConn,GHConn,FSConn connector
    class FutureConn coming
    class Greenhouse,PDL,Neo4j available
    class Lever,Workday coming
```

---

## Scoring Dimensions Detail

```mermaid
flowchart TB
    subgraph ScoringEngine["Multi-Dimensional Scoring Engine"]
        Candidate["Candidate Profile<br/>(Parsed Resume or PDL Data)"]
        
        subgraph Dimensions["6 Scoring Dimensions"]
            D1["🛠️ Skills Match<br/>━━━━━━━━━━━━━━━<br/>Required skills coverage<br/>Optional skills bonus<br/>Skill proficiency levels"]
            
            D2["📅 Experience Fit<br/>━━━━━━━━━━━━━━━<br/>Years of experience<br/>Seniority alignment<br/>Role relevance"]
            
            D3["📈 Career Trajectory<br/>━━━━━━━━━━━━━━━<br/>Progression patterns<br/>Promotion velocity<br/>Growth indicators"]
            
            D4["🏢 Company Background<br/>━━━━━━━━━━━━━━━<br/>Target company match<br/>Industry alignment<br/>Company size fit"]
            
            D5["🎓 Education<br/>━━━━━━━━━━━━━━━<br/>Degree requirements<br/>Field of study<br/>Institution quality"]
            
            D6["🎯 Cultural Signals<br/>━━━━━━━━━━━━━━━<br/>Work style indicators<br/>Leadership signals<br/>Team collaboration"]
        end

        subgraph Weighting["Dynamic Weighting"]
            Weights["Attribute Weights<br/>from Diagnostic Agent<br/>━━━━━━━━━━━━━━━<br/>Customized per role<br/>Based on job requirements"]
        end

        subgraph Output["Scoring Output"]
            OverallScore["Overall Score<br/>(0-100)"]
            DimScores["Per-Dimension<br/>Scores"]
            Reasoning["AI-Generated<br/>Reasoning"]
        end
    end

    Candidate --> D1
    Candidate --> D2
    Candidate --> D3
    Candidate --> D4
    Candidate --> D5
    Candidate --> D6

    D1 --> Weights
    D2 --> Weights
    D3 --> Weights
    D4 --> Weights
    D5 --> Weights
    D6 --> Weights

    Weights --> OverallScore
    Weights --> DimScores
    Weights --> Reasoning

    classDef candidate fill:#E3F2FD,stroke:#1565C0,stroke-width:2px
    classDef dimension fill:#FFF3E0,stroke:#EF6C00,stroke-width:2px
    classDef output fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px
```

---

## Real-Time Progress Tracking (SSE Events)

```mermaid
sequenceDiagram
    autonumber
    participant Client as Client Application
    participant API as Eliza API
    participant Orchestrator as Flow Orchestrator
    participant AI as AI Agents
    participant PDL as People Data Labs

    Client->>+API: POST /talent/analyze<br/>{job_desc, resumes, ...}
    API->>API: Create Analysis Record
    API-->>Client: 202 Accepted<br/>{analysis_id}
    
    Client->>API: GET /talent/{id}/events (SSE)
    
    rect rgb(240, 248, 255)
        Note over API,Orchestrator: Stage 1: Baseline Building
        Orchestrator-->>API: stage_1_started
        API-->>Client: SSE: "Building baseline profile..."
        Orchestrator-->>API: stage_1_completed
        API-->>Client: SSE: "Baseline built from 15 employees"
    end

    rect rgb(255, 248, 240)
        Note over API,AI: Stage 2: Diagnostic Analysis
        Orchestrator-->>API: stage_2_started
        API-->>Client: SSE: "Analyzing job requirements..."
        Orchestrator->>AI: Run Diagnostic Agent
        AI-->>Orchestrator: Diagnostic Report
        Orchestrator-->>API: stage_2_completed
        API-->>Client: SSE: "12 key attributes identified"
    end

    rect rgb(240, 255, 240)
        Note over API,Orchestrator: Stage 3: Resume Parsing
        Orchestrator-->>API: stage_3_started
        API-->>Client: SSE: "Parsing 25 resumes..."
        Orchestrator-->>API: stage_3_completed
        API-->>Client: SSE: "25 resumes parsed"
    end

    rect rgb(248, 240, 255)
        Note over API,Orchestrator: Stage 4: Score Applicants
        Orchestrator-->>API: stage_4_started
        API-->>Client: SSE: "Scoring applicants..."
        Orchestrator-->>API: stage_4_completed
        API-->>Client: SSE: "25 applicants scored"
    end

    rect rgb(255, 240, 248)
        Note over API,PDL: Stage 5: Market Search
        Orchestrator-->>API: stage_5_started
        API-->>Client: SSE: "Searching PDL..."
        Orchestrator->>PDL: Search Query
        PDL-->>Orchestrator: 50 Candidates
        Orchestrator-->>API: stage_5_completed
        API-->>Client: SSE: "50 market candidates found"
    end

    rect rgb(240, 255, 248)
        Note over API,Orchestrator: Stage 6: Score Market
        Orchestrator-->>API: stage_6_started
        API-->>Client: SSE: "Scoring market candidates..."
        Orchestrator-->>API: stage_6_completed
        API-->>Client: SSE: "50 market candidates scored"
    end

    rect rgb(255, 255, 240)
        Note over API,AI: Stage 7: Synthesis
        Orchestrator-->>API: stage_7_started
        API-->>Client: SSE: "Generating insights..."
        Orchestrator->>AI: Run Synthesis Agent
        AI-->>Orchestrator: Synthesis Report
        Orchestrator-->>API: stage_7_completed
        API-->>Client: SSE: "Analysis complete!"
    end

    Client->>+API: GET /talent/{id}/results
    API-->>-Client: Complete Results JSON
```

---

## Summary

### Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Flow Orchestrator** | Coordinates all stages | Python async |
| **Diagnostic Agent** | Analyzes job requirements | GPT-4o-mini |
| **Docling VLM Parser** | Parses PDF resumes | granite-docling-258M |
| **Scoring Engine** | Multi-dimensional scoring | Custom algorithm |
| **PDL Query Builder** | Builds market search queries | PDL Elasticsearch DSL |
| **Synthesis Agent** | Generates insights | GPT-4o-mini |

### Available Integrations

| Integration | Status | Data Provided |
|-------------|--------|---------------|
| **Greenhouse ATS** | ✅ Available | Job postings, applicants, resumes |
| **People Data Labs** | ✅ Available | 200M+ professional profiles |
| **Neo4j** | ✅ Available | Employee graph, career paths |
| **Lever ATS** | 🔜 Coming Soon | Job postings, applicants |
| **Workday HCM** | 🔜 Coming Soon | Employee data, org structure |
| **BambooHR** | 🔜 Coming Soon | HR data, employee profiles |

### Output Deliverables

1. **Top 3 Overall Candidates** - Ranked by composite score
2. **All Applicant Scores** - With per-dimension breakdown
3. **All Market Scores** - Passive candidates from PDL
4. **Diagnostic Report** - Competencies and weights
5. **Synthesis Report** - Insights, patterns, recommendations
6. **Full Provenance** - Audit trail of every step




