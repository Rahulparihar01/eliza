# Agent Configuration System - Final Specification

Complete technical specification for the unified agent configuration system with runtime resolution and multi-provider support.

---

## 🎯 Overview

This system provides a **runtime configuration resolution** architecture that ensures:
- ✅ Zero state mismatch between UI and execution
- ✅ Immediate effect (no restart needed)
- ✅ Multiple API keys per provider fully supported
- ✅ Automatic provider selection when possible
- ✅ User-friendly names instead of technical IDs

---

## 📊 Architecture Layers

### Layer 1: Provider Configurations (Who/How)

**What it stores:**
- API provider type (OpenAI, Anthropic, Bedrock, Groq)
- API credentials (encrypted)
- Available models
- Rate limits and priorities

**Managed by:** `ProviderService` (already exists)

### Layer 2: Agent Configurations (What/When)

**What it stores:**
- Agent prompts (role, goal, backstory)
- Model selection
- Temperature and parameters
- Tool assignments
- Reference to provider config (Layer 1)

**Managed by:** `AgentConfigurationService` (to be created)

### Runtime: Complete Configuration Merge

At execution time, both layers are merged to create a complete agent configuration with all necessary information.

---

## 💾 Database Schema

### CustomerAIProvider (Layer 1 - Already Exists)

```sql
CREATE TABLE customer_ai_providers (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,
    
    -- Provider identification
    provider_name VARCHAR(50) NOT NULL,  -- "openai", "anthropic", "bedrock", "groq"
    name VARCHAR(255) NOT NULL,          -- User-friendly: "OpenAI Production Account"
    
    -- Credentials (encrypted)
    api_key_encrypted TEXT,
    
    -- Configuration
    config_data JSONB,  -- {"models": ["gpt-4", "gpt-3.5-turbo"], "base_url": "..."}
    priority INTEGER DEFAULT 1,  -- Lower = higher priority (for auto-selection)
    max_requests_per_minute INTEGER DEFAULT 60,
    max_tokens_per_request INTEGER DEFAULT 100000,
    
    -- Status
    is_enabled BOOLEAN DEFAULT TRUE,
    is_healthy BOOLEAN DEFAULT TRUE,
    last_health_check TIMESTAMP,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_provider_customer ON customer_ai_providers(customer_id);
CREATE INDEX idx_provider_enabled ON customer_ai_providers(customer_id, is_enabled);
```

### AgentConfiguration (Layer 2 - To Be Created)

```sql
CREATE TABLE agent_configurations (
    id SERIAL PRIMARY KEY,
    
    -- Composite unique key
    customer_id VARCHAR(255) NOT NULL,
    flow_identifier VARCHAR(255) NOT NULL,    -- "data_analysis_flow"
    agent_identifier VARCHAR(255) NOT NULL,   -- "data_retrieval_agent"
    
    UNIQUE (customer_id, flow_identifier, agent_identifier),
    
    -- Agent prompts (nullable = use code defaults)
    role TEXT,
    goal TEXT,
    backstory TEXT,
    
    -- Model configuration
    model_id VARCHAR(255),                    -- "gpt-4", "claude-3-opus-20240229"
    provider_config_id INTEGER REFERENCES customer_ai_providers(id),
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER DEFAULT 2000,
    
    -- Tool configuration
    enabled_tools JSONB,  -- ["hr_database", "document_search"]
    tool_configs JSONB,   -- Tool-specific settings
    
    -- Status
    is_enabled BOOLEAN DEFAULT TRUE,
    
    -- Audit trail
    version INTEGER DEFAULT 1,
    updated_by VARCHAR(50),  -- "ui", "code", "migration", "api"
    updated_by_user_id INTEGER REFERENCES users(id),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_configs_lookup 
    ON agent_configurations(customer_id, flow_identifier, agent_identifier);

CREATE INDEX idx_agent_configs_provider
    ON agent_configurations(provider_config_id);
```

---

## 🔧 Service Layer

### AgentConfigurationService

```python
# src/services/agent_configuration_service.py

from typing import Dict, Any, Optional, List, Tuple
import time
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field

from src.services.base_service import BaseService
from src.services.provider_service import ProviderService
from src.models.customer import CustomerAIProvider
from src.core.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent configuration (Layer 2 only)."""
    agent_identifier: str
    flow_identifier: str
    role: str
    goal: str
    backstory: str
    model_id: str
    provider_config_id: Optional[int] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    enabled_tools: List[str] = []
    tool_configs: Dict[str, Any] = {}
    is_enabled: bool = True
    version: int = 1
    source: str = "default"  # "default", "override", "merged"


class CompleteAgentConfig(BaseModel):
    """Fully resolved agent configuration (Layer 1 + Layer 2)."""
    # Layer 2: Agent behavior
    agent_identifier: str
    flow_identifier: str
    role: str
    goal: str
    backstory: str
    model_id: str
    temperature: float
    max_tokens: int
    enabled_tools: List[str]
    tool_configs: Dict[str, Any]
    
    # Layer 1: Provider/LLM config
    provider_type: str          # "openai", "anthropic", etc.
    provider_name: str          # "OpenAI Production Account"
    provider_config_id: int
    api_key: Optional[str]      # Decrypted (internal use only!)
    base_url: Optional[str]
    
    # Metadata
    source: str
    version: int


class AgentConfigurationService(BaseService):
    """Manages agent configurations with runtime resolution."""
    
    # In-memory cache (60 second TTL)
    _cache: Dict[str, Tuple[CompleteAgentConfig, float]] = {}
    _cache_ttl: int = 60
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.provider_service = ProviderService(db)
        self.defaults = self._load_code_defaults()
    
    def get_complete_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str
    ) -> CompleteAgentConfig:
        """
        Get COMPLETE agent config (Layer 1 + Layer 2 merged).
        
        This is the single source of truth for runtime execution.
        Returns fully resolved config with provider credentials.
        
        Resolution order:
        1. Check cache
        2. Query database for customer override
        3. Merge with code defaults
        4. Resolve provider configuration
        5. Cache and return
        """
        cache_key = f"{customer_id}:{flow_identifier}:{agent_identifier}"
        
        # Check cache
        if cache_key in self._cache:
            config, cached_at = self._cache[cache_key]
            if time.time() - cached_at < self._cache_ttl:
                return config
        
        # Load agent config (Layer 2)
        agent_config = self._get_agent_config(customer_id, flow_identifier, agent_identifier)
        
        # Resolve provider config (Layer 1)
        if agent_config.provider_config_id:
            provider_config = self.provider_service.get_provider_by_id(
                config_id=agent_config.provider_config_id,
                customer_id=customer_id
            )
        else:
            # Auto-select provider for this model
            provider_config = self._resolve_provider_for_model(
                customer_id=customer_id,
                model_id=agent_config.model_id
            )
            agent_config.provider_config_id = provider_config.id
        
        if not provider_config:
            raise ConfigurationError(
                f"No provider configuration found for agent {agent_identifier}"
            )
        
        # Decrypt credentials
        api_key = None
        if provider_config.api_key_encrypted:
            api_key = self.provider_service._decrypt_api_key(
                provider_config.api_key_encrypted
            )
        
        # Build complete config
        complete_config = CompleteAgentConfig(
            # Layer 2: Agent behavior
            agent_identifier=agent_config.agent_identifier,
            flow_identifier=agent_config.flow_identifier,
            role=agent_config.role,
            goal=agent_config.goal,
            backstory=agent_config.backstory,
            model_id=agent_config.model_id,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            enabled_tools=agent_config.enabled_tools,
            tool_configs=agent_config.tool_configs,
            
            # Layer 1: Provider/LLM
            provider_type=provider_config.provider_name,
            provider_name=provider_config.name,
            provider_config_id=provider_config.id,
            api_key=api_key,
            base_url=provider_config.config_data.get("base_url"),
            
            # Metadata
            source=agent_config.source,
            version=agent_config.version
        )
        
        # Cache
        self._cache[cache_key] = (complete_config, time.time())
        
        return complete_config
    
    def set_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str,
        config: Dict[str, Any],
        updated_by: str = "api",
        user_id: Optional[int] = None
    ) -> "AgentConfiguration":
        """
        Update agent configuration.
        
        Provider resolution (in order of priority):
        1. config["provider_config_id"] - Explicit ID
        2. config["provider_name"] - Name lookup
        3. Auto-select based on model_id and priority
        
        Automatically invalidates cache.
        """
        # Ensure model_id is provided
        if "model_id" not in config:
            raise ValueError("model_id is required")
        
        model_id = config["model_id"]
        
        # Resolve provider (three options)
        if "provider_config_id" in config:
            # Option A: Explicit ID provided
            provider_config_id = config["provider_config_id"]
            logger.info(f"Using explicit provider_config_id: {provider_config_id}")
            
        elif "provider_name" in config:
            # Option B: Name provided, resolve to ID
            provider = self.db.query(CustomerAIProvider).filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.name == config["provider_name"]
            ).first()
            
            if not provider:
                raise ConfigurationError(
                    f"Provider '{config['provider_name']}' not found for customer {customer_id}"
                )
            
            provider_config_id = provider.id
            logger.info(f"Resolved provider name '{config['provider_name']}' to id: {provider_config_id}")
            
        else:
            # Option C: Auto-select based on model and priority
            provider = self._resolve_provider_for_model(customer_id, model_id)
            provider_config_id = provider.id
            logger.info(f"Auto-selected provider {provider_config_id} for model {model_id}")
        
        # Validate provider supports this model
        provider = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.id == provider_config_id
        ).first()
        
        if not provider:
            raise ConfigurationError(f"Provider config {provider_config_id} not found")
        
        available_models = provider.config_data.get("models", [])
        if model_id not in available_models:
            raise ConfigurationError(
                f"Model {model_id} not available in provider '{provider.name}'. "
                f"Available models: {', '.join(available_models)}"
            )
        
        # Import AgentConfiguration model here to avoid circular imports
        from src.models.agent_configuration import AgentConfiguration
        
        # Find or create agent config
        db_config = self.db.query(AgentConfiguration).filter(
            AgentConfiguration.customer_id == customer_id,
            AgentConfiguration.flow_identifier == flow_identifier,
            AgentConfiguration.agent_identifier == agent_identifier
        ).first()
        
        if db_config:
            # Update existing
            db_config.model_id = model_id
            db_config.provider_config_id = provider_config_id
            db_config.role = config.get("role", db_config.role)
            db_config.goal = config.get("goal", db_config.goal)
            db_config.backstory = config.get("backstory", db_config.backstory)
            db_config.temperature = config.get("temperature", db_config.temperature)
            db_config.max_tokens = config.get("max_tokens", db_config.max_tokens)
            db_config.enabled_tools = config.get("enabled_tools", db_config.enabled_tools)
            db_config.version += 1
            db_config.updated_by = updated_by
            db_config.updated_by_user_id = user_id
            db_config.updated_at = func.now()
        else:
            # Create new
            db_config = AgentConfiguration(
                customer_id=customer_id,
                flow_identifier=flow_identifier,
                agent_identifier=agent_identifier,
                model_id=model_id,
                provider_config_id=provider_config_id,
                role=config.get("role"),
                goal=config.get("goal"),
                backstory=config.get("backstory"),
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 2000),
                enabled_tools=config.get("enabled_tools", []),
                tool_configs=config.get("tool_configs", {}),
                version=1,
                updated_by=updated_by,
                updated_by_user_id=user_id
            )
            self.db.add(db_config)
        
        self.db.commit()
        self.db.refresh(db_config)
        
        # Invalidate cache
        cache_key = f"{customer_id}:{flow_identifier}:{agent_identifier}"
        if cache_key in self._cache:
            del self._cache[cache_key]
        
        logger.info(
            f"Updated agent config: {flow_identifier}.{agent_identifier} "
            f"for customer {customer_id} (model: {model_id}, provider: {provider.name}, "
            f"source: {updated_by}, version: {db_config.version})"
        )
        
        return db_config
    
    def _get_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str
    ) -> AgentConfig:
        """Get agent config (Layer 2), merging DB override with code defaults."""
        from src.models.agent_configuration import AgentConfiguration
        
        # Query database
        db_config = self.db.query(AgentConfiguration).filter(
            AgentConfiguration.customer_id == customer_id,
            AgentConfiguration.flow_identifier == flow_identifier,
            AgentConfiguration.agent_identifier == agent_identifier
        ).first()
        
        # Get code defaults
        default_key = f"{flow_identifier}.{agent_identifier}"
        default_config = self.defaults.get(default_key, self._get_system_default(agent_identifier))
        
        # Merge
        if db_config and db_config.is_enabled:
            merged = self._merge_configs(default_config, db_config)
            merged.source = "override"
            merged.version = db_config.version
            return merged
        else:
            default_config.source = "default"
            return default_config
    
    def _resolve_provider_for_model(
        self,
        customer_id: str,
        model_id: str
    ) -> CustomerAIProvider:
        """Auto-select provider for a model based on priority."""
        candidates = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == customer_id,
            CustomerAIProvider.is_enabled == True
        ).all()
        
        # Filter by model support
        matching = [
            p for p in candidates
            if model_id in p.config_data.get("models", [])
        ]
        
        if not matching:
            raise ConfigurationError(
                f"No enabled provider found that supports model '{model_id}'. "
                f"Please configure a provider in Admin Settings > AI Model Providers."
            )
        
        # Select highest priority (lowest number)
        provider = min(matching, key=lambda p: p.priority)
        logger.info(
            f"Auto-selected provider '{provider.name}' (id={provider.id}, priority={provider.priority}) "
            f"for model '{model_id}'"
        )
        return provider
    
    def _load_code_defaults(self) -> Dict[str, AgentConfig]:
        """Load hardcoded defaults for all agents."""
        return {
            "data_analysis_flow.data_retrieval_agent": AgentConfig(
                agent_identifier="data_retrieval_agent",
                flow_identifier="data_analysis_flow",
                role="Data Retrieval Specialist",
                goal="Retrieve relevant data from HR database and document embeddings",
                backstory=(
                    "You are an expert at finding and retrieving relevant data from multiple sources. "
                    "You know how to query databases effectively and search through documents to find "
                    "the most relevant information for analysis."
                ),
                model_id="gpt-3.5-turbo",
                enabled_tools=["hr_database", "document_search"],
                temperature=0.3,
                max_tokens=2000
            ),
            "data_analysis_flow.bi_analyst_agent": AgentConfig(
                agent_identifier="bi_analyst_agent",
                flow_identifier="data_analysis_flow",
                role="Business Intelligence Analyst",
                goal="Analyze data and generate actionable insights",
                backstory=(
                    "You are a seasoned business intelligence analyst with expertise in HR analytics. "
                    "You can identify patterns, trends, and insights from data that help organizations "
                    "make better decisions."
                ),
                model_id="gpt-4",
                enabled_tools=[],
                temperature=0.3,
                max_tokens=4000
            ),
            "task_enrichment_flow.task_analyzer_agent": AgentConfig(
                agent_identifier="task_analyzer_agent",
                flow_identifier="task_enrichment_flow",
                role="Intent Analyzer",
                goal="Analyze user questions to understand their intent, complexity, and requirements",
                backstory=(
                    "You are an expert at understanding user intent and extracting key information "
                    "from business questions. You can identify what type of analysis is needed, "
                    "what data sources are required, and how complex the task is."
                ),
                model_id="gpt-3.5-turbo",
                enabled_tools=[],
                temperature=0.3,
                max_tokens=2000
            ),
            "task_enrichment_flow.enrichment_agent": AgentConfig(
                agent_identifier="enrichment_agent",
                flow_identifier="task_enrichment_flow",
                role="Prompt Engineer",
                goal="Transform user questions into optimized prompts for analysis agents",
                backstory=(
                    "You are an expert prompt engineer who knows how to create clear, detailed prompts "
                    "that help AI agents produce high-quality analysis. You understand how to structure "
                    "prompts for maximum clarity and effectiveness."
                ),
                model_id="gpt-3.5-turbo",
                enabled_tools=[],
                temperature=0.5,
                max_tokens=3000
            ),
        }
    
    def _merge_configs(
        self,
        default: AgentConfig,
        override: "AgentConfiguration"
    ) -> AgentConfig:
        """Merge database override with code defaults."""
        merged = default.model_copy()
        
        if override.role:
            merged.role = override.role
        if override.goal:
            merged.goal = override.goal
        if override.backstory:
            merged.backstory = override.backstory
        if override.model_id:
            merged.model_id = override.model_id
        if override.provider_config_id:
            merged.provider_config_id = override.provider_config_id
        if override.temperature is not None:
            merged.temperature = override.temperature
        if override.max_tokens:
            merged.max_tokens = override.max_tokens
        if override.enabled_tools:
            merged.enabled_tools = override.enabled_tools
        if override.tool_configs:
            merged.tool_configs = override.tool_configs
        
        return merged
    
    def _get_system_default(self, agent_identifier: str) -> AgentConfig:
        """Get system-wide default for unknown agents."""
        return AgentConfig(
            agent_identifier=agent_identifier,
            flow_identifier="unknown",
            role="AI Assistant",
            goal="Help users with their questions",
            backstory="You are a helpful AI assistant.",
            model_id="gpt-3.5-turbo",
            enabled_tools=[],
            temperature=0.7,
            max_tokens=2000
        )
```

---

## 🔌 API Routes

```python
# src/api/routes/agents.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field

from src.core.dependencies import get_db, get_current_user
from src.services.agent_configuration_service import AgentConfigurationService
from src.core.auth import require_permission

router = APIRouter(prefix="/v1/agents", tags=["Agent Configuration"])


# --- Schemas ---

class AgentConfigUpdateRequest(BaseModel):
    role: Optional[str] = None
    goal: Optional[str] = None
    backstory: Optional[str] = None
    model_id: Optional[str] = None
    provider_config_id: Optional[int] = None
    provider_name: Optional[str] = None  # Alternative to provider_config_id
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    enabled_tools: Optional[List[str]] = None
    tool_configs: Optional[dict] = None


class AgentConfigResponse(BaseModel):
    customer_id: str
    flow_identifier: str
    agent_identifier: str
    role: str
    goal: str
    backstory: str
    model_id: str
    provider_config_id: int
    provider_name: str  # Friendly name for display
    temperature: float
    max_tokens: int
    enabled_tools: List[str]
    is_enabled: bool
    version: int
    source: str  # "default", "override", "merged"


class FlowInfo(BaseModel):
    flow_identifier: str
    flow_name: str
    agent_count: int


class AgentInfo(BaseModel):
    agent_identifier: str
    agent_name: str
    current_model: str
    current_provider: str


# --- Endpoints ---

@router.get("/flows", response_model=List[FlowInfo])
async def list_flows(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all available flows."""
    # Hardcoded for now, could be dynamic in the future
    return [
        {
            "flow_identifier": "data_analysis_flow",
            "flow_name": "Data Analysis Flow",
            "agent_count": 2
        },
        {
            "flow_identifier": "task_enrichment_flow",
            "flow_name": "Task Enrichment Flow",
            "agent_count": 2
        }
    ]


@router.get("/flows/{flow_id}/agents", response_model=List[AgentInfo])
async def list_agents_in_flow(
    flow_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """List all agents in a specific flow."""
    config_service = AgentConfigurationService(db)
    
    # Get agent identifiers for this flow
    agent_ids = {
        "data_analysis_flow": ["data_retrieval_agent", "bi_analyst_agent"],
        "task_enrichment_flow": ["task_analyzer_agent", "enrichment_agent"]
    }.get(flow_id, [])
    
    agents = []
    for agent_id in agent_ids:
        config = config_service.get_complete_agent_config(
            customer_id=current_user.customer_id,
            flow_identifier=flow_id,
            agent_identifier=agent_id
        )
        agents.append({
            "agent_identifier": agent_id,
            "agent_name": config.role,
            "current_model": config.model_id,
            "current_provider": config.provider_name
        })
    
    return agents


@router.get(
    "/configurations/{flow_id}/{agent_id}",
    response_model=AgentConfigResponse
)
async def get_agent_configuration(
    flow_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get current agent configuration (merged: override + defaults)."""
    config_service = AgentConfigurationService(db)
    config = config_service.get_complete_agent_config(
        customer_id=current_user.customer_id,
        flow_identifier=flow_id,
        agent_identifier=agent_id
    )
    
    return {
        "customer_id": current_user.customer_id,
        "flow_identifier": flow_id,
        "agent_identifier": agent_id,
        "role": config.role,
        "goal": config.goal,
        "backstory": config.backstory,
        "model_id": config.model_id,
        "provider_config_id": config.provider_config_id,
        "provider_name": config.provider_name,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "enabled_tools": config.enabled_tools,
        "is_enabled": True,
        "version": config.version,
        "source": config.source
    }


@router.put(
    "/configurations/{flow_id}/{agent_id}",
    response_model=AgentConfigResponse
)
async def update_agent_configuration(
    flow_id: str,
    agent_id: str,
    request: AgentConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("agents:write"))
):
    """
    Update agent configuration.
    Invalidates cache. Next execution uses new config.
    """
    config_service = AgentConfigurationService(db)
    
    db_config = config_service.set_agent_config(
        customer_id=current_user.customer_id,
        flow_identifier=flow_id,
        agent_identifier=agent_id,
        config=request.dict(exclude_unset=True),
        updated_by="ui",
        user_id=current_user.user_id
    )
    
    # Return merged config (what will actually be used)
    merged_config = config_service.get_complete_agent_config(
        customer_id=current_user.customer_id,
        flow_identifier=flow_id,
        agent_identifier=agent_id
    )
    
    return {
        "customer_id": current_user.customer_id,
        "flow_identifier": flow_id,
        "agent_identifier": agent_id,
        "role": merged_config.role,
        "goal": merged_config.goal,
        "backstory": merged_config.backstory,
        "model_id": merged_config.model_id,
        "provider_config_id": merged_config.provider_config_id,
        "provider_name": merged_config.provider_name,
        "temperature": merged_config.temperature,
        "max_tokens": merged_config.max_tokens,
        "enabled_tools": merged_config.enabled_tools,
        "is_enabled": True,
        "version": merged_config.version,
        "source": merged_config.source
    }


@router.delete("/configurations/{flow_id}/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_agent_configuration(
    flow_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("agents:write"))
):
    """Reset agent configuration to code defaults."""
    from src.models.agent_configuration import AgentConfiguration
    
    config_service = AgentConfigurationService(db)
    
    # Delete override (falls back to code defaults)
    db_config = db.query(AgentConfiguration).filter(
        AgentConfiguration.customer_id == current_user.customer_id,
        AgentConfiguration.flow_identifier == flow_id,
        AgentConfiguration.agent_identifier == agent_id
    ).first()
    
    if db_config:
        db.delete(db_config)
        db.commit()
        
        # Invalidate cache
        cache_key = f"{current_user.customer_id}:{flow_id}:{agent_id}"
        if cache_key in config_service._cache:
            del config_service._cache[cache_key]
    
    return {"message": "Agent configuration reset to defaults"}
```

---

## 🔄 Flow Integration

```python
# src/crewai_flows/data_analysis_flow.py (excerpt)

class DataAnalysisFlow(Flow[DataAnalysisFlowState]):
    def __init__(self):
        super().__init__()
    
    def retrieve_data(self):
        # Load COMPLETE config at runtime (Layer 1 + Layer 2)
        complete_config = self._get_complete_agent_config("data_retrieval_agent")
        
        # Build LLM from resolved config
        llm = self._build_llm_from_config(complete_config)
        
        # Build tools from config
        tools = self._resolve_tools(complete_config.enabled_tools)
        
        # Build agent with complete config
        data_retriever = Agent(
            role=complete_config.role,
            goal=complete_config.goal,
            backstory=complete_config.backstory,
            tools=tools,
            llm=llm,
            verbose=True
        )
        
        # Execute...
    
    def _get_complete_agent_config(self, agent_identifier: str):
        """Load complete config at runtime."""
        from src.models import database
        from src.services.agent_configuration_service import AgentConfigurationService
        
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        try:
            config_service = AgentConfigurationService(db)
            return config_service.get_complete_agent_config(
                customer_id=self.state.customer_id,
                flow_identifier="data_analysis_flow",
                agent_identifier=agent_identifier
            )
        finally:
            db.close()
    
    def _build_llm_from_config(self, config):
        """Build LLM client from complete config."""
        from crewai import LLM
        
        if config.provider_type == "openai":
            return LLM(
                model=config.model_id,
                api_key=config.api_key,
                base_url=config.base_url or "https://api.openai.com/v1",
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
        elif config.provider_type == "anthropic":
            return LLM(
                model=config.model_id,
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
        # Add other providers...
```

---

## 🎯 Key Features Summary

### 1. Multiple API Keys Per Provider
- ✅ Customer can have unlimited provider configs for same provider
- ✅ Each has unique ID and user-friendly name
- ✅ Agents reference specific config by ID

### 2. Automatic Provider Selection
- ✅ If only one provider supports model → Auto-selected
- ✅ If multiple providers → Uses highest priority
- ✅ User can override auto-selection if needed

### 3. User-Friendly Names
- ✅ Admin provides name when creating provider: "OpenAI Production Account"
- ✅ UI shows names, not IDs
- ✅ Backend stores ID for referential integrity

### 4. Runtime Resolution
- ✅ Config loaded at execution time (not startup)
- ✅ Changes take effect immediately
- ✅ Cache with 60s TTL for performance

### 5. Zero State Mismatch
- ✅ UI and execution both query same service
- ✅ Single source of truth
- ✅ Always in sync

### 6. Programmatic Access
- ✅ Pass ID directly (explicit)
- ✅ Pass name (readable)
- ✅ Let service auto-select (simplest)

---

## 📋 Implementation Checklist

### Phase 1: Database & Models
- [ ] Create `AgentConfiguration` SQLAlchemy model
- [ ] Create Alembic migration for `agent_configurations` table
- [ ] Add `name` column to `customer_ai_providers` (optional but recommended)
- [ ] Run migration

### Phase 2: Service Layer
- [ ] Create `AgentConfigurationService` with all methods
- [ ] Implement cache with TTL
- [ ] Add code defaults for existing agents
- [ ] Add auto-selection logic for providers

### Phase 3: API Routes
- [ ] Create `/v1/agents/*` endpoints
- [ ] Add request/response schemas
- [ ] Add permission checks (`agents:read`, `agents:write`)

### Phase 4: Flow Integration
- [ ] Modify `DataAnalysisFlow` to use runtime config
- [ ] Modify `TaskEnrichmentFlow` to use runtime config
- [ ] Add `_get_complete_agent_config()` helper
- [ ] Add `_build_llm_from_config()` helper

### Phase 5: Frontend UI
- [ ] Build flows/agents list (clean list design, no cards)
- [ ] Build agent configuration form
- [ ] Add provider selector (when multiple match)
- [ ] Add model selector (filtered by provider)
- [ ] Wire up to API endpoints

### Phase 6: Testing
- [ ] Test UI updates → Execution uses new config
- [ ] Test programmatic updates via service
- [ ] Test auto-selection with one provider
- [ ] Test manual selection with multiple providers
- [ ] Test cache invalidation

---

## 🚀 Success Criteria

- ✅ User can configure agent prompts via UI
- ✅ User can select AI model via UI
- ✅ User can assign specific API account (if multiple exist)
- ✅ Changes take effect on next execution (no restart)
- ✅ Developer can update configs programmatically
- ✅ System auto-selects provider when possible
- ✅ Audit trail tracks all changes
- ✅ Zero state mismatch between UI and execution

---

**This is the complete technical specification for implementation!** 🎯

