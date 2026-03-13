# AWS Architecture: Data Analyst Flow with Eliza + CrewAI Platforms

This document provides AWS-specific architecture diagrams showing the Data Analyst Flow across two separate VPCs: the **Eliza Platform** (API orchestration) and the **CrewAI Platform** (flow execution with Amazon Bedrock).

## Architecture Overview

```mermaid
flowchart TB
    subgraph External["External Environment"]
        ExtApp["External Application<br/>(Client)"]
    end

    subgraph AWS["AWS Cloud"]
        subgraph ElizaVPC["Eliza Platform VPC"]
            subgraph ElizaPublic["Public Subnet"]
                ALB["Application Load Balancer<br/>(HTTPS/443)"]
            end

            subgraph ElizaPrivate["Private Subnet"]
                subgraph ElizaECS["Amazon ECS Cluster"]
                    API["FastAPI Service<br/>(ECS Fargate)"]
                    CeleryWorker["Celery Worker<br/>(ECS Fargate)"]
                end
                
                subgraph ElizaData["Data Layer"]
                    RDS["Amazon RDS<br/>(PostgreSQL)"]
                    Redis["Amazon ElastiCache<br/>(Redis)"]
                end
            end
        end

        subgraph CrewAIVPC["CrewAI Platform VPC"]
            subgraph CrewAIPrivate["Private Subnet"]
                subgraph CrewAICompute["Compute Layer"]
                    FlowRunner["Flow Execution Service<br/>(ECS Fargate)"]
                    DataAnalystFlow["Data Analyst Flow<br/>━━━━━━━━━━━━━━━<br/>• Intent Detection Agent<br/>• Clarification Agent<br/>• Processing Router Agent"]
                end
            end
            
            subgraph CrewAIEndpoints["VPC Endpoints"]
                BedrockEP["Bedrock Runtime<br/>VPC Endpoint<br/>(PrivateLink)"]
            end
        end

        subgraph BedrockService["Amazon Bedrock"]
            Bedrock["Bedrock Runtime"]
            Claude["Claude 3.5 Sonnet<br/>(Anthropic)"]
        end

        VPCPeering["VPC Peering<br/>Connection"]
    end

    ExtApp -->|"REST API Call<br/>(HTTPS)"| ALB
    ALB --> API
    API -->|"Task Queue"| Redis
    Redis -->|"Consume Tasks"| CeleryWorker
    CeleryWorker <-->|"API Call via<br/>VPC Peering"| VPCPeering
    VPCPeering <--> FlowRunner
    FlowRunner --> DataAnalystFlow
    DataAnalystFlow -->|"Model Inference<br/>(PrivateLink)"| BedrockEP
    BedrockEP --> Bedrock
    Bedrock --> Claude
    CeleryWorker --> RDS
    API --> RDS

    classDef external fill:#f9f,stroke:#333,stroke-width:2px
    classDef eliza fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef crewai fill:#6B5B95,stroke:#3D3259,stroke-width:2px,color:#fff
    classDef compute fill:#ED7100,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef database fill:#3B48CC,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef ai fill:#01A88D,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef peering fill:#FF6B6B,stroke:#CC5555,stroke-width:2px,color:#fff

    class ExtApp external
    class ALB eliza
    class API,CeleryWorker compute
    class RDS,Redis database
    class Bedrock,Claude,BedrockEP ai
    class FlowRunner,DataAnalystFlow crewai
    class VPCPeering peering
```

---

## Data Analyst Flow - Detailed Sequence (Cross-VPC)

```mermaid
sequenceDiagram
    autonumber
    participant Client as External Application
    participant ALB as ALB<br/>(Eliza VPC)
    participant API as FastAPI<br/>(Eliza VPC)
    participant Redis as ElastiCache<br/>(Eliza VPC)
    participant Worker as Celery Worker<br/>(Eliza VPC)
    participant RDS as RDS PostgreSQL<br/>(Eliza VPC)
    participant FlowRunner as Flow Runner<br/>(CrewAI VPC)
    participant Flow as Data Analyst Flow<br/>(CrewAI VPC)
    participant Bedrock as Amazon Bedrock<br/>(Claude 3.5)

    rect rgb(255, 248, 230)
        Note over Client,RDS: Eliza Platform VPC - API Orchestration
        Client->>+ALB: POST /api/data-analyst/messages<br/>{"question": "What is our loss ratio by state?"}
        ALB->>+API: Forward Request
        API->>RDS: Create Message Record<br/>(status: pending)
        API->>Redis: Queue Celery Task<br/>(message_id, question)
        API-->>-ALB: 202 Accepted<br/>{message_id: "abc-123"}
        ALB-->>-Client: Response
    end

    rect rgb(240, 235, 255)
        Note over Worker,Bedrock: CrewAI Platform VPC - Flow Execution
        Redis->>+Worker: Consume Task
        Worker->>RDS: Update Status: "processing"
        
        Note over Worker,FlowRunner: Cross-VPC API Call (VPC Peering)
        Worker->>+FlowRunner: POST /flows/data-analyst/execute<br/>{message_id, question, context}
        FlowRunner->>+Flow: Initialize Data Analyst Flow
        
        Note over Flow,Bedrock: Step 1: Domain Validation
        Flow->>+Bedrock: Validate Question Relevance
        Bedrock-->>-Flow: {is_relevant: true}
        
        Note over Flow,Bedrock: Step 2: Intent Detection Agent
        Flow->>+Bedrock: Detect Intent<br/>(DATA_QUERY vs CONVERSATIONAL)
        Bedrock-->>-Flow: {intent: "data_query", confidence: "high"}
        
        Note over Flow,Bedrock: Step 3: SQL Generation (Vanna)
        Flow->>+Bedrock: Generate SQL Query
        Bedrock-->>-Flow: SQL: "SELECT state, loss_ratio FROM..."
        
        Note over Flow,Bedrock: Step 4: Insights Generation Agent
        Flow->>+Bedrock: Generate Insights<br/>(summary, findings, charts)
        Bedrock-->>-Flow: {summary: "...", key_findings: [...]}
        
        Flow-->>-FlowRunner: Flow Results
        FlowRunner-->>-Worker: {status: "completed", results: {...}}
    end

    rect rgb(255, 248, 230)
        Note over Worker,RDS: Eliza Platform VPC - Result Storage
        Worker->>RDS: Execute SQL Query
        RDS-->>Worker: Query Results
        Worker->>RDS: Save Results + Insights<br/>(status: completed)
        Worker-->>-Redis: Task Complete
    end

    rect rgb(240, 255, 240)
        Note over Client,API: Client Polls for Results
        Client->>+ALB: GET /api/data-analyst/messages/{id}
        ALB->>+API: Forward Request
        API->>RDS: Fetch Message + Results
        RDS-->>API: Message Data
        API-->>-ALB: 200 OK<br/>{status: "completed", results: {...}}
        ALB-->>-Client: Response with Insights
    end
```

---

## Data Analyst Flow - Agent Architecture (CrewAI Platform)

```mermaid
flowchart TB
    subgraph ElizaVPC["Eliza Platform VPC"]
        CeleryTask["Celery Worker<br/>━━━━━━━━━━━━━━━<br/>Orchestrates task execution<br/>Stores results to RDS"]
    end

    subgraph CrewAIVPC["CrewAI Platform VPC"]
        subgraph FlowExecution["Flow Execution Service"]
            FlowAPI["Flow Runner API<br/>━━━━━━━━━━━━━━━<br/>Receives flow requests<br/>Manages flow lifecycle"]
        end

        subgraph DataAnalystFlow["Data Analyst Flow"]
            direction TB
            
            subgraph StartPhase["Phase 1: Validation & Intent"]
                Start([Start Flow]) --> DomainVal["Domain Validation<br/>━━━━━━━━━━━━━━━<br/>Validates question is<br/>about insurance data"]
                DomainVal --> IntentAgent["Intent Detection Agent<br/>━━━━━━━━━━━━━━━<br/>Role: Intent Detection Specialist<br/>Goal: Classify DATA_QUERY vs CONVERSATIONAL"]
            end

            subgraph DecisionPhase["Phase 2: Routing"]
                IntentAgent --> ClarCheck{Clarification<br/>Needed?}
                ClarCheck -->|Yes| ClarAgent["Clarification Agent<br/>━━━━━━━━━━━━━━━<br/>Role: Question Clarification Specialist<br/>Goal: Generate clarification prompts"]
                ClarAgent --> WaitUser([Return to Eliza<br/>for User Response])
                ClarCheck -->|No| RouteDecision{Intent Type?}
            end

            subgraph DataPath["Phase 3A: DATA Query Path"]
                RouteDecision -->|DATA_QUERY| RouterAgent["Processing Router Agent<br/>━━━━━━━━━━━━━━━<br/>Role: Data Processing Router<br/>Tools: Vanna, SQL Executor, Insights"]
                
                RouterAgent --> VannaTool["🔧 Vanna SQL Tool<br/>━━━━━━━━━━━━━━━<br/>Generates SQL from<br/>natural language"]
                VannaTool --> SQLHint["SQL Query Hint<br/>(returned to Eliza)"]
            end

            subgraph ConvPath["Phase 3B: CONVERSATIONAL Path"]
                RouteDecision -->|CONVERSATIONAL| ConvTool["🔧 Conversational Tool<br/>━━━━━━━━━━━━━━━<br/>Generates helpful<br/>conversational response"]
            end

            subgraph InsightsPhase["Phase 4: Insights Generation"]
                SQLHint --> InsightsTool["🔧 Insights Generation Tool<br/>━━━━━━━━━━━━━━━<br/>Generates summary,<br/>findings, chart suggestions"]
                ConvTool --> Complete
                InsightsTool --> Complete([Return Results<br/>to Eliza])
            end
        end

        subgraph BedrockEndpoint["VPC Endpoint"]
            BedrockEP["Bedrock Runtime<br/>VPC Endpoint<br/>(PrivateLink)"]
        end
    end

    subgraph Bedrock["Amazon Bedrock"]
        BedrockAPI["Bedrock Runtime API"]
        ClaudeModel["Claude 3.5 Sonnet<br/>━━━━━━━━━━━━━━━<br/>Foundation Model"]
        BedrockAPI --> ClaudeModel
    end

    CeleryTask <-->|"VPC Peering"| FlowAPI
    FlowAPI --> Start

    DomainVal -.->|"Model Inference"| BedrockEP
    IntentAgent -.->|"Model Inference"| BedrockEP
    ClarAgent -.->|"Model Inference"| BedrockEP
    VannaTool -.->|"Model Inference"| BedrockEP
    InsightsTool -.->|"Model Inference"| BedrockEP
    ConvTool -.->|"Model Inference"| BedrockEP
    BedrockEP -.->|"PrivateLink"| BedrockAPI

    classDef eliza fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:#fff
    classDef crewai fill:#6B5B95,stroke:#3D3259,stroke-width:2px,color:#fff
    classDef agent fill:#4A90D9,stroke:#2E5C8A,stroke-width:2px,color:#fff
    classDef tool fill:#7B68EE,stroke:#483D8B,stroke-width:2px,color:#fff
    classDef decision fill:#FFD700,stroke:#B8860B,stroke-width:2px,color:#000
    classDef bedrock fill:#01A88D,stroke:#017A64,stroke-width:2px,color:#fff

    class CeleryTask eliza
    class FlowAPI crewai
    class IntentAgent,ClarAgent,RouterAgent agent
    class VannaTool,InsightsTool,ConvTool,DomainVal tool
    class ClarCheck,RouteDecision decision
    class BedrockEP,BedrockAPI,ClaudeModel bedrock
```

---

## AWS Network Architecture (Dual VPC)

```mermaid
flowchart TB
    subgraph Internet["Internet"]
        ExtClient["External Application"]
    end

    subgraph AWS["AWS Region (us-east-1)"]
        subgraph ElizaVPC["Eliza Platform VPC: 10.0.0.0/16"]
            subgraph ElizaAZ1["Availability Zone 1"]
                subgraph ElizaPub1["Public Subnet<br/>10.0.1.0/24"]
                    ALB1["ALB Node"]
                    NAT1["NAT Gateway"]
                end
                
                subgraph ElizaPriv1["Private Subnet<br/>10.0.10.0/24"]
                    ElizaECS1["ECS Tasks<br/>(FastAPI + Celery)"]
                end
                
                subgraph ElizaData1["Data Subnet<br/>10.0.20.0/24"]
                    RDS1["RDS Primary"]
                    Redis1["ElastiCache Node"]
                end
            end

            subgraph ElizaAZ2["Availability Zone 2"]
                subgraph ElizaPub2["Public Subnet<br/>10.0.2.0/24"]
                    ALB2["ALB Node"]
                    NAT2["NAT Gateway"]
                end
                
                subgraph ElizaPriv2["Private Subnet<br/>10.0.11.0/24"]
                    ElizaECS2["ECS Tasks<br/>(FastAPI + Celery)"]
                end
                
                subgraph ElizaData2["Data Subnet<br/>10.0.21.0/24"]
                    RDS2["RDS Standby"]
                    Redis2["ElastiCache Node"]
                end
            end
        end

        VPCPeering[["VPC Peering Connection<br/>━━━━━━━━━━━━━━━<br/>Eliza ↔ CrewAI<br/>Private routing"]]

        subgraph CrewAIVPC["CrewAI Platform VPC: 10.1.0.0/16"]
            subgraph CrewAZ1["Availability Zone 1"]
                subgraph CrewPriv1["Private Subnet<br/>10.1.10.0/24"]
                    CrewECS1["ECS Tasks<br/>(Flow Runner)"]
                end
            end

            subgraph CrewAZ2["Availability Zone 2"]
                subgraph CrewPriv2["Private Subnet<br/>10.1.11.0/24"]
                    CrewECS2["ECS Tasks<br/>(Flow Runner)"]
                end
            end

            subgraph CrewEndpoints["VPC Endpoints"]
                BedrockEP["Bedrock Runtime<br/>VPC Endpoint<br/>(PrivateLink)"]
                S3EP["S3 Gateway<br/>Endpoint"]
                ECREP["ECR<br/>VPC Endpoint"]
            end
        end

        subgraph BedrockService["Amazon Bedrock Service"]
            BedrockRuntime["Bedrock Runtime<br/>━━━━━━━━━━━━━━━<br/>Claude 3.5 Sonnet"]
        end
    end

    ExtClient -->|"HTTPS:443"| ALB1
    ExtClient -->|"HTTPS:443"| ALB2
    ALB1 --> ElizaECS1
    ALB2 --> ElizaECS2
    ElizaECS1 --> Redis1
    ElizaECS2 --> Redis2
    ElizaECS1 --> RDS1
    ElizaECS2 --> RDS1
    
    ElizaECS1 <-->|"Private Route"| VPCPeering
    ElizaECS2 <-->|"Private Route"| VPCPeering
    VPCPeering <-->|"Private Route"| CrewECS1
    VPCPeering <-->|"Private Route"| CrewECS2
    
    CrewECS1 -->|"Private"| BedrockEP
    CrewECS2 -->|"Private"| BedrockEP
    BedrockEP -->|"PrivateLink"| BedrockRuntime

    classDef public fill:#90EE90,stroke:#228B22,stroke-width:2px
    classDef elizaPrivate fill:#FFE4B5,stroke:#FF8C00,stroke-width:2px
    classDef elizaData fill:#FFDAB9,stroke:#FF6347,stroke-width:2px
    classDef crewPrivate fill:#E6E6FA,stroke:#6B5B95,stroke-width:2px
    classDef endpoint fill:#B0E0E6,stroke:#4682B4,stroke-width:2px
    classDef bedrock fill:#01A88D,stroke:#017A64,stroke-width:2px,color:#fff
    classDef peering fill:#FF6B6B,stroke:#CC5555,stroke-width:3px,color:#fff

    class ElizaPub1,ElizaPub2 public
    class ElizaPriv1,ElizaPriv2 elizaPrivate
    class ElizaData1,ElizaData2 elizaData
    class CrewPriv1,CrewPriv2 crewPrivate
    class BedrockEP,S3EP,ECREP endpoint
    class BedrockRuntime bedrock
    class VPCPeering peering
```

---

## Component Summary

### Eliza Platform VPC

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| **API Gateway** | Application Load Balancer | HTTPS ingress, SSL termination |
| **API Service** | ECS Fargate (FastAPI) | REST API, request validation, response handling |
| **Task Orchestration** | ECS Fargate (Celery) | Task queuing, cross-VPC flow invocation |
| **Task Queue** | ElastiCache (Redis) | Celery broker and result backend |
| **Database** | RDS PostgreSQL | Message storage, results, telemetry |

### CrewAI Platform VPC

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| **Flow Runner** | ECS Fargate | Hosts and executes CrewAI flows |
| **Data Analyst Flow** | CrewAI Framework | Agent orchestration, tool execution |
| **AI/ML** | Amazon Bedrock | Foundation model inference (Claude 3.5 Sonnet) |
| **Networking** | VPC Endpoint (PrivateLink) | Secure private connectivity to Bedrock |

### Cross-VPC Communication

| Component | AWS Service | Purpose |
|-----------|-------------|---------|
| **VPC Peering** | VPC Peering Connection | Private network path between Eliza and CrewAI VPCs |

---

## Security Considerations

1. **Network Isolation**: 
   - Eliza Platform handles external traffic via ALB
   - CrewAI Platform has NO internet-facing endpoints
   - Cross-VPC communication via private VPC Peering only

2. **VPC Peering Security**:
   - Non-transitive (only Eliza ↔ CrewAI, not through to Bedrock)
   - Security groups restrict traffic to specific ports/protocols
   - Route tables limit accessible CIDR ranges

3. **Bedrock Access**:
   - CrewAI VPC accesses Bedrock via PrivateLink (traffic never leaves AWS network)
   - IAM roles for ECS tasks (no API keys stored)
   - VPC Endpoint policies restrict Bedrock model access

4. **Data Security**:
   - All data stored in Eliza VPC (RDS, Redis)
   - CrewAI Platform is stateless - only processes, doesn't store
   - TLS encryption in transit between all components

5. **Additional Controls**:
   - AWS WAF on ALB for API protection
   - VPC Flow Logs for network monitoring
   - CloudTrail for API audit logging

---

## Data Flow Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL                                        │
│  External App ──► ALB                                                       │
└─────────────────────┬───────────────────────────────────────────────────────┘
                      │ HTTPS
┌─────────────────────▼───────────────────────────────────────────────────────┐
│                         ELIZA PLATFORM VPC                                   │
│  ALB ──► FastAPI ──► Redis Queue ──► Celery Worker ──► RDS                  │
│                                            │                                 │
│                                            │ Results saved                   │
└────────────────────────────────────────────┼────────────────────────────────┘
                                             │ VPC Peering (API Call)
┌────────────────────────────────────────────▼────────────────────────────────┐
│                         CREWAI PLATFORM VPC                                  │
│  Flow Runner ──► Data Analyst Flow ──► Agents ──► Bedrock (Claude)          │
│       │                                                                      │
│       └──────────────────────────────────────────────────────────────────►  │
│                              Flow Results returned                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

1. **External Application** sends question via REST API to Eliza Platform
2. **Eliza Platform** (FastAPI) validates, queues task, returns message_id
3. **Celery Worker** (Eliza) invokes CrewAI Platform via VPC Peering
4. **CrewAI Platform** executes Data Analyst Flow with multiple Bedrock calls
5. **Flow Results** returned to Eliza via VPC Peering
6. **Eliza Platform** executes SQL, stores results in RDS
7. **Client** polls Eliza Platform for completed results
