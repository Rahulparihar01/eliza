# Agent Configuration Management System - Implementation Plan

## 🎯 Executive Summary

This document outlines a comprehensive plan for building a **UI-driven agent configuration management system** for CrewAI agents and flows. Users will be able to configure agent prompts, select models from configured providers, attach mandatory documents, and manage agent behavior through an intuitive admin interface.

---

## 📋 Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [System Architecture](#system-architecture)
3. [Database Schema](#database-schema)
4. [Backend API](#backend-api)
5. [Frontend Design](#frontend-design)
6. [Integration Strategy](#integration-strategy)
7. [Implementation Phases](#implementation-phases)
8. [Testing Strategy](#testing-strategy)

---

## 1. Current State Analysis

### Existing Flows & Agents

**Flows:**
1. **DataAnalysisFlow** (`src/crewai_flows/data_analysis_flow.py`)
   - **Data Retrieval Agent**: Queries HR database and document embeddings
   - **Business Intelligence Analyst**: Analyzes data and generates insights
   
2. **TaskEnrichmentFlow** (`src/crewai_flows/task_enrichment_flow.py`)
   - **Task Analysis Agent**: Analyzes user intent and complexity
   - **Enrichment Agent**: Creates enriched prompts

**Current Agent Configuration:**
- Hardcoded in flow files
- LLM selection via environment variables
- Fixed prompts (role, goal, backstory)
- Static tool assignments
- No UI configuration capability

**Problems:**
- ❌ Cannot change agent behavior without code deployment
- ❌ Cannot A/B test different prompts
- ❌ Cannot easily switch models per agent
- ❌ Cannot add/remove tools dynamically
- ❌ No visibility into agent configurations for non-technical users

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    FRONTEND LAYER                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Admin Settings > Agent Configuration            │   │
│  │  - List Agents/Flows                             │   │
│  │  - Edit Agent Config                             │   │
│  │  - Test Agent                                    │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                         ↕ REST API
┌─────────────────────────────────────────────────────────┐
│                     BACKEND LAYER                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  API Routes (/v1/agents)                         │   │
│  │  - CRUD operations for agent configs             │   │
│  │  - Discovery of available agents/flows           │   │
│  │  - Test agent endpoint                           │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Agent Configuration Service                     │   │
│  │  - Validate configurations                       │   │
│  │  - Merge with defaults                           │   │
│  │  - Provide to flows at runtime                   │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Agent Registry                                  │   │
│  │  - Discover agents/flows via introspection      │   │
│  │  - Extract default configs                       │   │
│  │  - Track available tools                         │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│                   DATABASE LAYER                         │
│  - agent_configurations                                  │
│  - agent_document_attachments                            │
│  - agent_execution_history                               │
└─────────────────────────────────────────────────────────┘
                         ↕
┌─────────────────────────────────────────────────────────┐
│                  CrewAI FLOW LAYER                       │
│  Flows consume configurations at runtime                 │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Database Schema

### 3.1 Agent Configurations Table

```sql
CREATE TABLE agent_configurations (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,  -- Multi-tenancy
    
    -- Agent Identity
    agent_identifier VARCHAR(255) NOT NULL,  -- e.g., "data_retrieval_agent"
    flow_identifier VARCHAR(255) NOT NULL,   -- e.g., "data_analysis_flow"
    agent_name VARCHAR(255) NOT NULL,        -- Display name
    agent_type VARCHAR(50) NOT NULL,         -- "crewai_agent", "custom"
    
    -- Agent Configuration (JSON)
    role TEXT NOT NULL,                      -- Agent's role description
    goal TEXT NOT NULL,                      -- Agent's goal
    backstory TEXT,                          -- Agent's backstory
    
    -- LLM Configuration
    provider_config_id INTEGER,              -- FK to customer_ai_providers
    model_override VARCHAR(255),             -- Specific model if not using provider default
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2000,
    llm_config JSONB,                        -- Additional LLM parameters
    
    -- Tool Configuration
    enabled_tools JSONB,                     -- ["hr_database_tool", "document_search_tool"]
    tool_configs JSONB,                      -- Tool-specific configurations
    
    -- Processing Configuration
    processing_config JSONB,                 -- Custom processing parameters
    
    -- Status & Metadata
    is_enabled BOOLEAN DEFAULT true,
    is_default BOOLEAN DEFAULT false,        -- Use as default if no custom config
    version INTEGER DEFAULT 1,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by INTEGER,  -- FK to users
    updated_by INTEGER,
    
    -- Indexes
    CONSTRAINT fk_provider_config 
        FOREIGN KEY (provider_config_id) 
        REFERENCES customer_ai_providers(id) 
        ON DELETE SET NULL,
    CONSTRAINT unique_agent_per_customer 
        UNIQUE(customer_id, flow_identifier, agent_identifier)
);

CREATE INDEX idx_agent_configs_customer ON agent_configurations(customer_id);
CREATE INDEX idx_agent_configs_flow ON agent_configurations(flow_identifier);
CREATE INDEX idx_agent_configs_enabled ON agent_configurations(is_enabled);
```

### 3.2 Agent Document Attachments

```sql
CREATE TABLE agent_document_attachments (
    id SERIAL PRIMARY KEY,
    agent_config_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    
    -- Attachment Configuration
    attachment_type VARCHAR(50) NOT NULL,    -- "mandatory", "reference", "context"
    priority INTEGER DEFAULT 0,               -- Order of inclusion
    
    -- Processing Instructions
    processing_instructions JSONB,            -- How to use this document
    
    -- Metadata
    attached_at TIMESTAMP DEFAULT NOW(),
    attached_by INTEGER,  -- FK to users
    
    CONSTRAINT fk_agent_config 
        FOREIGN KEY (agent_config_id) 
        REFERENCES agent_configurations(id) 
        ON DELETE CASCADE,
    CONSTRAINT fk_document 
        FOREIGN KEY (document_id) 
        REFERENCES documents(id) 
        ON DELETE CASCADE
);

CREATE INDEX idx_agent_docs_config ON agent_document_attachments(agent_config_id);
CREATE INDEX idx_agent_docs_document ON agent_document_attachments(document_id);
```

### 3.3 Agent Execution History (Analytics)

```sql
CREATE TABLE agent_execution_history (
    id SERIAL PRIMARY KEY,
    agent_config_id INTEGER NOT NULL,
    
    -- Execution Context
    flow_execution_id VARCHAR(255),
    session_id INTEGER,  -- FK to bi_analysis_sessions
    
    -- Execution Metrics
    execution_start TIMESTAMP NOT NULL,
    execution_end TIMESTAMP,
    duration_ms INTEGER,
    tokens_used INTEGER,
    cost_usd DECIMAL(10, 6),
    
    -- Configuration Snapshot
    config_snapshot JSONB,  -- Config used at execution time
    
    -- Results
    status VARCHAR(50) NOT NULL,  -- "success", "failed", "timeout"
    error_message TEXT,
    
    -- Performance Metrics
    response_quality_score FLOAT,
    tool_calls_count INTEGER,
    
    CONSTRAINT fk_agent_config_history 
        FOREIGN KEY (agent_config_id) 
        REFERENCES agent_configurations(id) 
        ON DELETE CASCADE
);

CREATE INDEX idx_agent_history_config ON agent_execution_history(agent_config_id);
CREATE INDEX idx_agent_history_session ON agent_execution_history(session_id);
CREATE INDEX idx_agent_history_execution ON agent_execution_history(flow_execution_id);
```

---

## 4. Backend API

### 4.1 Agent Discovery & Registry

**Purpose**: Discover available agents and flows in the system via code introspection.

```python
# src/services/agent_registry.py

from typing import Dict, List, Any
from pathlib import Path
import importlib
import inspect

class AgentRegistry:
    """
    Discovers and catalogs all CrewAI agents and flows in the system.
    Extracts default configurations for UI display.
    """
    
    def __init__(self):
        self.flows: Dict[str, Any] = {}
        self.agents: Dict[str, Any] = {}
        self._discover_flows()
    
    def _discover_flows(self):
        """Scan crewai_flows directory for Flow classes."""
        flows_dir = Path("src/crewai_flows")
        for py_file in flows_dir.glob("*.py"):
            if py_file.name.startswith("__"):
                continue
            
            module_name = f"src.crewai_flows.{py_file.stem}"
            module = importlib.import_module(module_name)
            
            # Find Flow classes
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if hasattr(obj, "__mro__") and any("Flow" in c.__name__ for c in obj.__mro__):
                    self.flows[obj.__name__] = {
                        "class": obj,
                        "module": module_name,
                        "agents": self._extract_agents_from_flow(obj)
                    }
    
    def _extract_agents_from_flow(self, flow_class):
        """Extract agent definitions from a flow class."""
        # Parse flow source to find agent creation
        # This is simplified - real implementation would be more robust
        agents = []
        source = inspect.getsource(flow_class)
        
        # Look for Agent() instantiations
        # Extract role, goal, backstory
        # This requires parsing the source code
        
        return agents
    
    def get_available_flows(self) -> List[Dict[str, Any]]:
        """Return list of available flows with their agents."""
        return [
            {
                "flow_identifier": flow_id,
                "flow_name": flow_id.replace("Flow", "").replace("_", " ").title(),
                "module": info["module"],
                "agents": info["agents"]
            }
            for flow_id, info in self.flows.items()
        ]
    
    def get_flow_default_config(self, flow_identifier: str) -> Dict[str, Any]:
        """Get default configuration for a specific flow."""
        if flow_identifier not in self.flows:
            raise ValueError(f"Flow {flow_identifier} not found")
        
        return self.flows[flow_identifier]
```

### 4.2 Agent Configuration Service

```python
# src/services/agent_configuration_service.py

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.models.agent_configuration import (
    AgentConfiguration, 
    AgentDocumentAttachment,
    AgentExecutionHistory
)
from src.services.base_service import BaseService

class AgentConfigurationService(BaseService):
    """Service for managing agent configurations."""
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    def create_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str,
        config_data: Dict[str, Any],
        created_by: int
    ) -> AgentConfiguration:
        """Create a new agent configuration."""
        config = AgentConfiguration(
            customer_id=customer_id,
            flow_identifier=flow_identifier,
            agent_identifier=agent_identifier,
            agent_name=config_data.get("agent_name"),
            agent_type=config_data.get("agent_type", "crewai_agent"),
            role=config_data.get("role"),
            goal=config_data.get("goal"),
            backstory=config_data.get("backstory"),
            provider_config_id=config_data.get("provider_config_id"),
            model_override=config_data.get("model_override"),
            temperature=config_data.get("temperature", 0.7),
            max_tokens=config_data.get("max_tokens", 2000),
            llm_config=config_data.get("llm_config", {}),
            enabled_tools=config_data.get("enabled_tools", []),
            tool_configs=config_data.get("tool_configs", {}),
            processing_config=config_data.get("processing_config", {}),
            is_enabled=config_data.get("is_enabled", True),
            created_by=created_by
        )
        
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        
        return config
    
    def get_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str
    ) -> Optional[AgentConfiguration]:
        """Get agent configuration for a specific agent."""
        return self.db.query(AgentConfiguration).filter(
            and_(
                AgentConfiguration.customer_id == customer_id,
                AgentConfiguration.flow_identifier == flow_identifier,
                AgentConfiguration.agent_identifier == agent_identifier,
                AgentConfiguration.is_enabled == True
            )
        ).first()
    
    def get_all_agent_configs(
        self,
        customer_id: str,
        flow_identifier: Optional[str] = None
    ) -> List[AgentConfiguration]:
        """Get all agent configurations for a customer."""
        query = self.db.query(AgentConfiguration).filter(
            AgentConfiguration.customer_id == customer_id
        )
        
        if flow_identifier:
            query = query.filter(AgentConfiguration.flow_identifier == flow_identifier)
        
        return query.all()
    
    def update_agent_config(
        self,
        config_id: int,
        customer_id: str,
        update_data: Dict[str, Any],
        updated_by: int
    ) -> Optional[AgentConfiguration]:
        """Update an existing agent configuration."""
        config = self.db.query(AgentConfiguration).filter(
            and_(
                AgentConfiguration.id == config_id,
                AgentConfiguration.customer_id == customer_id
            )
        ).first()
        
        if not config:
            return None
        
        # Update fields
        for key, value in update_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_by = updated_by
        config.version += 1
        
        self.db.commit()
        self.db.refresh(config)
        
        return config
    
    def attach_document(
        self,
        config_id: int,
        document_id: int,
        attachment_type: str,
        processing_instructions: Dict[str, Any],
        attached_by: int
    ) -> AgentDocumentAttachment:
        """Attach a document to an agent configuration."""
        attachment = AgentDocumentAttachment(
            agent_config_id=config_id,
            document_id=document_id,
            attachment_type=attachment_type,
            processing_instructions=processing_instructions,
            attached_by=attached_by
        )
        
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        
        return attachment
    
    def get_agent_documents(self, config_id: int) -> List[AgentDocumentAttachment]:
        """Get all documents attached to an agent configuration."""
        return self.db.query(AgentDocumentAttachment).filter(
            AgentDocumentAttachment.agent_config_id == config_id
        ).all()
    
    def record_execution(
        self,
        config_id: int,
        execution_data: Dict[str, Any]
    ) -> AgentExecutionHistory:
        """Record an agent execution for analytics."""
        history = AgentExecutionHistory(
            agent_config_id=config_id,
            **execution_data
        )
        
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        
        return history
```

### 4.3 API Routes

```python
# src/api/routes/agents.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from pydantic import BaseModel, Field

from src.services.agent_configuration_service import AgentConfigurationService
from src.services.agent_registry import AgentRegistry
from src.core.dependencies import get_db, get_current_user
from src.models.auth import User

router = APIRouter(prefix="/v1/agents", tags=["Agent Configuration"])

# --- Schemas ---

class AgentConfigCreate(BaseModel):
    flow_identifier: str
    agent_identifier: str
    agent_name: str
    role: str
    goal: str
    backstory: Optional[str] = None
    provider_config_id: Optional[int] = None
    model_override: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    enabled_tools: List[str] = []
    tool_configs: dict = {}
    processing_config: dict = {}

class AgentConfigUpdate(BaseModel):
    agent_name: Optional[str] = None
    role: Optional[str] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    provider_config_id: Optional[int] = None
    model_override: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    enabled_tools: Optional[List[str]] = None
    tool_configs: Optional[dict] = None
    processing_config: Optional[dict] = None
    is_enabled: Optional[bool] = None

class DocumentAttachment(BaseModel):
    document_id: int
    attachment_type: str  # "mandatory", "reference", "context"
    processing_instructions: dict = {}

# --- Endpoints ---

@router.get("/flows")
async def list_available_flows(
    current_user: User = Depends(get_current_user)
):
    """List all available CrewAI flows in the system."""
    registry = AgentRegistry()
    return {
        "flows": registry.get_available_flows()
    }

@router.get("/configurations")
async def list_agent_configurations(
    flow_identifier: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all agent configurations for the current user's organization."""
    service = AgentConfigurationService(db)
    configs = service.get_all_agent_configs(
        customer_id=current_user.customer_id,
        flow_identifier=flow_identifier
    )
    return {"configurations": configs}

@router.post("/configurations", status_code=status.HTTP_201_CREATED)
async def create_agent_configuration(
    config_data: AgentConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new agent configuration."""
    service = AgentConfigurationService(db)
    config = service.create_agent_config(
        customer_id=current_user.customer_id,
        flow_identifier=config_data.flow_identifier,
        agent_identifier=config_data.agent_identifier,
        config_data=config_data.dict(),
        created_by=current_user.user_id
    )
    return config

@router.get("/configurations/{config_id}")
async def get_agent_configuration(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific agent configuration."""
    service = AgentConfigurationService(db)
    config = service.db.query(AgentConfiguration).filter(
        AgentConfiguration.id == config_id,
        AgentConfiguration.customer_id == current_user.customer_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return config

@router.put("/configurations/{config_id}")
async def update_agent_configuration(
    config_id: int,
    update_data: AgentConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an agent configuration."""
    service = AgentConfigurationService(db)
    config = service.update_agent_config(
        config_id=config_id,
        customer_id=current_user.customer_id,
        update_data=update_data.dict(exclude_unset=True),
        updated_by=current_user.user_id
    )
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    return config

@router.delete("/configurations/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_configuration(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an agent configuration."""
    service = AgentConfigurationService(db)
    config = service.db.query(AgentConfiguration).filter(
        AgentConfiguration.id == config_id,
        AgentConfiguration.customer_id == current_user.customer_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    service.db.delete(config)
    service.db.commit()

@router.post("/configurations/{config_id}/documents")
async def attach_document_to_agent(
    config_id: int,
    attachment: DocumentAttachment,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Attach a document to an agent configuration."""
    service = AgentConfigurationService(db)
    
    # Verify ownership
    config = service.db.query(AgentConfiguration).filter(
        AgentConfiguration.id == config_id,
        AgentConfiguration.customer_id == current_user.customer_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    attachment_record = service.attach_document(
        config_id=config_id,
        document_id=attachment.document_id,
        attachment_type=attachment.attachment_type,
        processing_instructions=attachment.processing_instructions,
        attached_by=current_user.user_id
    )
    
    return attachment_record

@router.get("/configurations/{config_id}/documents")
async def list_agent_documents(
    config_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all documents attached to an agent configuration."""
    service = AgentConfigurationService(db)
    
    # Verify ownership
    config = service.db.query(AgentConfiguration).filter(
        AgentConfiguration.id == config_id,
        AgentConfiguration.customer_id == current_user.customer_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    documents = service.get_agent_documents(config_id)
    return {"documents": documents}

@router.post("/configurations/{config_id}/test")
async def test_agent_configuration(
    config_id: int,
    test_input: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test an agent configuration with a sample input."""
    # This would create a test execution of the agent
    # Returns the agent's output for validation
    raise HTTPException(status_code=501, detail="Not implemented yet")
```

---

## 5. Frontend Design

### 5.1 Navigation Structure

```
Admin Settings
├── Default Company
├── Vector Search
├── AI Providers
└── Agent Configuration ⭐ NEW
    ├── Overview (List of Flows)
    ├── Flow Detail
    │   ├── Agent 1 Config
    │   ├── Agent 2 Config
    │   └── ...
    └── Agent Edit Page
        ├── Basic Info
        ├── Prompts (Role/Goal/Backstory)
        ├── Model Selection
        ├── Tool Configuration
        └── Document Attachments
```

### 5.2 Page Designs

#### **Agent Configuration Overview**
`/admin/agent-configuration`

```
┌────────────────────────────────────────────────┐
│ 🤖 Agent Configuration                         │
├────────────────────────────────────────────────┤
│                                                │
│ CrewAI Flows & Agents                          │
│                                                │
│ ┌─────────────────────────────────────────┐  │
│ │ 📊 Data Analysis Flow                    │  │
│ │ 2 agents configured                      │  │
│ │                                           │  │
│ │ • Data Retrieval Agent        [Edit]     │  │
│ │   Model: GPT-4 (OpenAI)       ✓ Active   │  │
│ │                                           │  │
│ │ • BI Analyst Agent            [Edit]     │  │
│ │   Model: Claude 3 (Anthropic) ✓ Active   │  │
│ └─────────────────────────────────────────┘  │
│                                                │
│ ┌─────────────────────────────────────────┐  │
│ │ 📝 Task Enrichment Flow                  │  │
│ │ 2 agents configured                      │  │
│ │                                           │  │
│ │ • Task Analysis Agent         [Edit]     │  │
│ │   Model: GPT-4 (OpenAI)       ✓ Active   │  │
│ │                                           │  │
│ │ • Enrichment Agent            [Edit]     │  │
│ │   Model: GPT-4 (OpenAI)       ✓ Active   │  │
│ └─────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

#### **Agent Edit Page**
`/admin/agent-configuration/data_analysis_flow/data_retrieval_agent`

```
┌────────────────────────────────────────────────┐
│ 🤖 Data Retrieval Agent                        │
│ Data Analysis Flow                             │
├────────────────────────────────────────────────┤
│                                                │
│ Basic Information                              │
│ ┌──────────────────────────────────────────┐ │
│ │ Agent Name:                              │ │
│ │ [Data Retrieval Agent              ]     │ │
│ │                                           │ │
│ │ Status: [✓] Enabled                      │ │
│ └──────────────────────────────────────────┘ │
│                                                │
│ Agent Prompts                                  │
│ ┌──────────────────────────────────────────┐ │
│ │ Role:                                     │ │
│ │ [Data Retrieval Specialist          ]    │ │
│ │                                           │ │
│ │ Goal:                                     │ │
│ │ [Retrieve relevant HR and document   ]   │ │
│ │ [data based on the user's question   ]   │ │
│ │                                           │ │
│ │ Backstory:                                │ │
│ │ [You are an expert at finding the    ]   │ │
│ │ [right data sources to answer        ]   │ │
│ │ [business questions...               ]   │ │
│ └──────────────────────────────────────────┘ │
│                                                │
│ Model Configuration                            │
│ ┌──────────────────────────────────────────┐ │
│ │ Provider:                                 │ │
│ │ [OpenAI - My OpenAI Config        ▼]     │ │
│ │                                           │ │
│ │ Model:                                    │ │
│ │ [gpt-4                            ▼]     │ │
│ │                                           │ │
│ │ Temperature: [0.7    ] (0.0 - 2.0)       │ │
│ │ Max Tokens:  [2000   ] (1 - 4096)        │ │
│ └──────────────────────────────────────────┘ │
│                                                │
│ Tools                                          │
│ ┌──────────────────────────────────────────┐ │
│ │ [✓] HR Database Tool                      │ │
│ │     Query customer HR data                │ │
│ │                                           │ │
│ │ [✓] Document Search Tool                  │ │
│ │     Search uploaded documents             │ │
│ └──────────────────────────────────────────┘ │
│                                                │
│ Mandatory Documents                            │
│ ┌──────────────────────────────────────────┐ │
│ │ [Add Document ▼]                          │ │
│ │                                           │ │
│ │ 📄 Company Policies.pdf    [Remove]      │ │
│ │    Type: Mandatory Context                │ │
│ │                                           │ │
│ │ 📄 HR Guidelines.pdf       [Remove]      │ │
│ │    Type: Reference                        │ │
│ └──────────────────────────────────────────┘ │
│                                                │
│ [Test Agent]  [Save Changes]  [Cancel]        │
└────────────────────────────────────────────────┘
```

### 5.3 React Components

**File Structure:**
```
frontend/src/
├── pages/
│   └── admin/
│       ├── agent-configuration/
│       │   ├── AgentConfigurationOverview.tsx
│       │   ├── FlowDetailPage.tsx
│       │   └── AgentEditPage.tsx
└── components/
    └── agent-configuration/
        ├── FlowCard.tsx
        ├── AgentCard.tsx
        ├── AgentPromptEditor.tsx
        ├── ModelSelector.tsx
        ├── ToolConfiguration.tsx
        └── DocumentAttachment.tsx
```

---

## 6. Integration Strategy

### 6.1 Flow Runtime Integration

Flows need to load configurations at runtime:

```python
# src/crewai_flows/data_analysis_flow.py

class DataAnalysisFlow(Flow[DataAnalysisFlowState]):
    def __init__(self, customer_id: Optional[str] = None):
        # Load agent configurations if available
        if customer_id:
            self._load_agent_configs(customer_id)
        else:
            self._use_default_configs()
        
        super().__init__()
    
    def _load_agent_configs(self, customer_id: str):
        """Load agent configurations from database."""
        # Initialize database
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        try:
            service = AgentConfigurationService(db)
            
            # Load Data Retrieval Agent config
            retrieval_config = service.get_agent_config(
                customer_id=customer_id,
                flow_identifier="data_analysis_flow",
                agent_identifier="data_retrieval_agent"
            )
            
            if retrieval_config:
                self.retrieval_agent_config = retrieval_config
                self.llm = self._create_llm_from_config(retrieval_config)
            else:
                self._use_default_configs()
        finally:
            db.close()
    
    def _create_llm_from_config(self, config: AgentConfiguration) -> LLM:
        """Create LLM instance from agent configuration."""
        # Get provider configuration
        if config.provider_config_id:
            provider_config = get_provider_config(config.provider_config_id)
            
            return LLM(
                model=config.model_override or provider_config.default_model,
                temperature=config.temperature,
                api_key=provider_config.decrypted_api_key,
                base_url=provider_config.base_url,
                max_tokens=config.max_tokens
            )
        else:
            # Fallback to environment config
            return self._create_default_llm()
    
    def retrieve_data(self):
        """Stage 1: Retrieve data using configured agent."""
        # Use configuration if available
        if hasattr(self, 'retrieval_agent_config'):
            config = self.retrieval_agent_config
            
            agent = Agent(
                role=config.role,
                goal=config.goal,
                backstory=config.backstory or "",
                tools=self._get_tools_for_agent(config),
                llm=self.llm
            )
        else:
            # Use default hardcoded agent
            agent = self._create_default_retrieval_agent()
        
        # Continue with existing logic...
```

### 6.2 Document Injection

For mandatory documents:

```python
def _inject_mandatory_documents(self, config: AgentConfiguration) -> str:
    """Inject mandatory document content into agent context."""
    if not config.agent_document_attachments:
        return ""
    
    service = DocumentService(self.db)
    context_parts = []
    
    for attachment in config.agent_document_attachments:
        if attachment.attachment_type == "mandatory":
            # Fetch document content
            document = service.get_document(attachment.document_id)
            content = service.get_document_content(document)
            
            context_parts.append(f"""
            MANDATORY CONTEXT FROM: {document.filename}
            {content}
            ---
            """)
    
    return "\n\n".join(context_parts)
```

---

## 7. Implementation Phases

### Phase 1: Database & Backend Foundation (Week 1)
- [ ] Create database migration for agent_configurations table
- [ ] Create database migration for agent_document_attachments table
- [ ] Create AgentConfiguration SQLAlchemy model
- [ ] Create AgentConfigurationService
- [ ] Create AgentRegistry for discovery
- [ ] Create basic API routes (CRUD)

### Phase 2: Flow Integration (Week 1-2)
- [ ] Modify DataAnalysisFlow to load configurations
- [ ] Modify TaskEnrichmentFlow to load configurations
- [ ] Implement LLM creation from provider configs
- [ ] Implement document injection
- [ ] Test configuration loading
- [ ] Add fallback to defaults if no config exists

### Phase 3: Frontend - Overview Page (Week 2)
- [ ] Create AgentConfigurationOverview page
- [ ] Create FlowCard component
- [ ] Create AgentCard component
- [ ] Implement list flows API integration
- [ ] Implement list agent configs API integration
- [ ] Add navigation from Admin Settings

### Phase 4: Frontend - Edit Page (Week 2-3)
- [ ] Create AgentEditPage
- [ ] Create AgentPromptEditor component
- [ ] Create ModelSelector component (use provider configs)
- [ ] Create ToolConfiguration component
- [ ] Create DocumentAttachment component
- [ ] Implement save/update functionality

### Phase 5: Testing & Validation (Week 3)
- [ ] Add "Test Agent" functionality
- [ ] Add configuration validation
- [ ] Test with real flows
- [ ] Performance testing
- [ ] UI/UX refinement

### Phase 6: Analytics & Monitoring (Week 4)
- [ ] Implement agent_execution_history tracking
- [ ] Add performance metrics
- [ ] Add cost tracking
- [ ] Create analytics dashboard
- [ ] A/B testing support

---

## 8. Testing Strategy

### 8.1 Backend Tests

```python
# tests/test_agent_configuration_service.py

def test_create_agent_config():
    """Test creating an agent configuration."""
    service = AgentConfigurationService(db)
    config = service.create_agent_config(
        customer_id="test_customer",
        flow_identifier="data_analysis_flow",
        agent_identifier="test_agent",
        config_data={
            "agent_name": "Test Agent",
            "role": "Test Role",
            "goal": "Test Goal",
            "temperature": 0.5
        },
        created_by=1
    )
    
    assert config.id is not None
    assert config.temperature == 0.5

def test_load_config_in_flow():
    """Test loading configuration in a flow."""
    # Create test config
    # Initialize flow with customer_id
    # Verify flow uses configured values
    pass
```

### 8.2 Integration Tests

```python
def test_end_to_end_configured_agent():
    """Test entire flow with custom agent configuration."""
    # 1. Create provider config
    # 2. Create agent config pointing to provider
    # 3. Run flow
    # 4. Verify agent used correct model
    # 5. Verify agent used correct prompts
    pass
```

### 8.3 Frontend Tests

```typescript
// Test agent configuration form
// Test model selection
// Test document attachment
// Test save/update flows
```

---

## 9. Security Considerations

1. **Multi-tenancy**: Ensure users can only access their own agent configs
2. **API Key Access**: Only show provider names, not keys
3. **Document Access**: Verify document ownership before attachment
4. **Audit Trail**: Track who created/modified configurations
5. **Validation**: Validate all configuration inputs

---

## 10. Future Enhancements

### Phase 2 Features
- **A/B Testing**: Run multiple agent configurations simultaneously
- **Version History**: Track changes to agent configurations over time
- **Templates**: Save and share agent configuration templates
- **Analytics**: Track performance metrics per configuration
- **Cost Optimization**: Recommend model selections based on cost/performance
- **Batch Testing**: Test multiple configurations at once

### Advanced Features
- **Dynamic Tool Loading**: Add new tools without code changes
- **Custom Agent Types**: Support for non-CrewAI agents
- **Agent Marketplace**: Share and discover agent configurations
- **Auto-tuning**: Automatically optimize agent parameters
- **Multi-agent Orchestration**: Configure agent-to-agent communication

---

## 11. Success Metrics

- ✅ Users can configure agents without code deployment
- ✅ Agent configurations load correctly at runtime
- ✅ Document attachments work as expected
- ✅ Model selection integrates with provider system
- ✅ Configuration changes take effect immediately
- ✅ No performance degradation from configuration loading
- ✅ Comprehensive audit trail of all changes

---

## 12. Questions to Resolve

1. **Default Behavior**: What happens if no custom config exists? (Use hardcoded defaults)
2. **Version Control**: How do we handle configuration versioning? (Increment version on each update)
3. **Rollback**: Can users rollback to previous configurations? (Phase 2 feature)
4. **Testing**: How do users test configurations without affecting production? (Test endpoint)
5. **Performance**: What's the performance impact of loading configs? (Cache configurations)

---

## Summary

This plan provides a comprehensive approach to building a UI-driven agent configuration management system. The implementation is phased to deliver value incrementally:

1. **Week 1**: Database + Backend API
2. **Week 2**: Flow Integration + Frontend Overview
3. **Week 3**: Frontend Edit Page + Testing
4. **Week 4**: Analytics + Polish

**Key Benefits:**
- ✅ No code deployment needed for agent changes
- ✅ Integrates with existing provider system
- ✅ Supports document attachments
- ✅ Full audit trail
- ✅ Multi-tenant secure
- ✅ Extensible for future enhancements

**Ready to start implementation!** 🚀

