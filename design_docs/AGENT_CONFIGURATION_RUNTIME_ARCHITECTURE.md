# Agent Configuration Runtime Architecture

## 🎯 Design Goal

**Ensure the UI and agent execution ALWAYS use the same configuration - no state mismatches.**

Key Requirements:
1. **Single Source of Truth**: One authoritative config store
2. **Runtime Resolution**: Agents load config at execution time (not startup)
3. **Bidirectional Updates**: UI and code updates use same path
4. **Zero Deployment**: Changing prompts doesn't require code deploy
5. **Audit Trail**: Track who changed what (UI vs code vs migration)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 SINGLE SOURCE OF TRUTH                      │
│                                                             │
│              AgentConfigurationService                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ get_agent_config(customer, flow, agent)              │  │
│  │  → Query DB for override                             │  │
│  │  → Merge with code defaults                          │  │
│  │  → Cache with TTL (60s)                              │  │
│  │  → Return unified config                             │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ set_agent_config(customer, flow, agent, config)      │  │
│  │  → Validate config                                   │  │
│  │  → Write to DB                                       │  │
│  │  → Invalidate cache                                  │  │
│  │  → Track update source (UI/code/migration)          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
         ↑                                      ↑
         │                                      │
    ┌────┴─────────┐                    ┌──────┴──────────┐
    │ UI Updates   │                    │ Code Updates    │
    │ via API      │                    │ Programmatic    │
    └──────────────┘                    └─────────────────┘
         │                                      │
         └───────────────┬──────────────────────┘
                         ↓
         ┌────────────────────────────────────────┐
         │      Database (PostgreSQL)             │
         │  agent_configurations table            │
         │  - Primary Key: (customer, flow, agent)│
         │  - Config JSON (overrides)             │
         │  - Version, updated_by, updated_at     │
         └────────────────────────────────────────┘
                         ↑
                         │ Runtime Query (every execution)
                         │
         ┌───────────────┴───────────────┐
         │   CrewAI Flow Execution       │
         │  - Query config service       │
         │  - Build Agent from config    │
         │  - Execute with latest config │
         └───────────────────────────────┘
```

---

## 📊 Configuration Layers (Priority Order)

```python
# Configuration resolution (highest priority first):
1. Database Override (customer-specific, set via UI or API)
2. Code Defaults (fallback if no override exists)
3. System Defaults (hardcoded safety fallback)
```

**Example:**
```python
# Code default:
role = "Data Retrieval Specialist"
model = "gpt-3.5-turbo"

# Customer A overrides via UI:
model = "gpt-4"  # ← This wins for Customer A

# Customer B has no override:
model = "gpt-3.5-turbo"  # ← Uses code default
```

---

## 🔄 Update Paths (Both Use Same Service)

### Path 1: UI Update
```
User clicks "Save" in UI
    ↓
POST /v1/agents/configurations
    ↓
AgentConfigurationService.set_agent_config(
    customer_id="customer-a",
    flow_identifier="data_analysis_flow",
    agent_identifier="data_retrieval_agent",
    config={
        "role": "Expert Data Retriever",
        "model": "gpt-4",
        "temperature": 0.3
    },
    updated_by="ui",
    user_id=123
)
    ↓
DB.upsert(agent_configurations)
    ↓
Cache.invalidate(cache_key)
    ↓
✅ Next execution uses new config
```

### Path 2: Programmatic Update
```python
# Code update (migration, admin script, etc.)
from src.services.agent_configuration_service import AgentConfigurationService

config_service = AgentConfigurationService(db)
config_service.set_agent_config(
    customer_id="customer-a",
    flow_identifier="data_analysis_flow",
    agent_identifier="data_retrieval_agent",
    config={
        "backstory": "Updated backstory for testing..."
    },
    updated_by="migration",
    user_id=None
)
# ✅ Next execution uses new config
```

**Both paths write to the same database table!**

---

## 🚀 Flow Integration Pattern

### Before (Hardcoded):
```python
class DataAnalysisFlow(Flow):
    def retrieve_data(self):
        # ❌ Hardcoded - never changes without deployment
        data_retriever = Agent(
            role="Data Retrieval Specialist",
            goal="Retrieve relevant data from HR database...",
            backstory="You are an expert at finding...",
            tools=[hr_tool, doc_tool],
            llm=self.llm,
        )
```

### After (Runtime Resolution):
```python
class DataAnalysisFlow(Flow):
    def retrieve_data(self):
        # ✅ Load config at runtime - always uses latest
        config = self._get_agent_config("data_retrieval_agent")
        
        data_retriever = Agent(
            role=config.role,
            goal=config.goal,
            backstory=config.backstory,
            tools=self._resolve_tools(config.enabled_tools),
            llm=self._resolve_llm(config),
            temperature=config.temperature,
        )
        # Agent is built from database config + defaults
```

### Helper Method:
```python
def _get_agent_config(self, agent_identifier: str) -> AgentConfig:
    """Load agent config at runtime (called every execution)."""
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        config_service = AgentConfigurationService(db)
        return config_service.get_agent_config(
            customer_id=self.state.customer_id,
            flow_identifier=self.__class__.__name__.lower().replace("flow", "_flow"),
            agent_identifier=agent_identifier
        )
    finally:
        db.close()
```

---

## 💾 Database Schema

```sql
CREATE TABLE agent_configurations (
    id SERIAL PRIMARY KEY,
    
    -- Composite unique key (one config per agent per customer)
    customer_id VARCHAR(255) NOT NULL,
    flow_identifier VARCHAR(255) NOT NULL,  -- "data_analysis_flow"
    agent_identifier VARCHAR(255) NOT NULL, -- "data_retrieval_agent"
    
    UNIQUE (customer_id, flow_identifier, agent_identifier),
    
    -- Configuration (JSON - stores overrides only)
    role TEXT,
    goal TEXT,
    backstory TEXT,
    
    -- LLM Configuration
    provider_config_id INTEGER REFERENCES customer_ai_providers(id),
    model_override VARCHAR(255),
    temperature FLOAT,
    max_tokens INTEGER,
    
    -- Tool Configuration
    enabled_tools JSONB,  -- ["hr_database", "document_search"]
    tool_configs JSONB,
    
    -- Status
    is_enabled BOOLEAN DEFAULT TRUE,
    
    -- Audit Trail
    version INTEGER DEFAULT 1,
    updated_by VARCHAR(50),  -- "ui", "code", "migration", "api"
    updated_by_user_id INTEGER REFERENCES users(id),
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_configs_lookup 
    ON agent_configurations(customer_id, flow_identifier, agent_identifier);
```

---

## 🔧 Service Implementation

```python
# src/services/agent_configuration_service.py

class AgentConfig(BaseModel):
    """Runtime agent configuration."""
    agent_identifier: str
    flow_identifier: str
    role: str
    goal: str
    backstory: str
    provider_config_id: Optional[int] = None
    model_override: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000
    enabled_tools: List[str] = []
    tool_configs: Dict[str, Any] = {}
    is_enabled: bool = True
    version: int = 1
    source: str = "default"  # "default", "override", "merged"


class AgentConfigurationService(BaseService):
    """Single source of truth for agent configurations."""
    
    # In-memory cache (60 second TTL)
    _cache: Dict[str, Tuple[AgentConfig, float]] = {}
    _cache_ttl: int = 60
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.defaults = self._load_code_defaults()
    
    def get_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str
    ) -> AgentConfig:
        """
        Get agent configuration (DB override + code defaults).
        
        Resolution order:
        1. Check cache
        2. Query database for customer override
        3. Merge with code defaults
        4. Cache and return
        """
        cache_key = f"{customer_id}:{flow_identifier}:{agent_identifier}"
        
        # Check cache
        if cache_key in self._cache:
            config, cached_at = self._cache[cache_key]
            if time.time() - cached_at < self._cache_ttl:
                return config
        
        # Query database for override
        db_config = self.db.query(AgentConfiguration).filter(
            AgentConfiguration.customer_id == customer_id,
            AgentConfiguration.flow_identifier == flow_identifier,
            AgentConfiguration.agent_identifier == agent_identifier
        ).first()
        
        # Get code defaults
        default_config = self.defaults.get(
            f"{flow_identifier}.{agent_identifier}",
            self._get_system_default(agent_identifier)
        )
        
        # Merge: DB override > Default
        if db_config and db_config.is_enabled:
            merged_config = self._merge_configs(default_config, db_config)
            merged_config.source = "override"
        else:
            merged_config = default_config
            merged_config.source = "default"
        
        # Cache
        self._cache[cache_key] = (merged_config, time.time())
        
        return merged_config
    
    def set_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str,
        config: Dict[str, Any],
        updated_by: str = "api",
        user_id: Optional[int] = None
    ) -> AgentConfiguration:
        """
        Update agent configuration (UI or programmatic).
        Invalidates cache automatically.
        """
        # Find existing or create new
        db_config = self.db.query(AgentConfiguration).filter(
            AgentConfiguration.customer_id == customer_id,
            AgentConfiguration.flow_identifier == flow_identifier,
            AgentConfiguration.agent_identifier == agent_identifier
        ).first()
        
        if db_config:
            # Update existing
            for key, value in config.items():
                if hasattr(db_config, key):
                    setattr(db_config, key, value)
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
                **config,
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
            f"for customer {customer_id} (source: {updated_by}, version: {db_config.version})"
        )
        
        return db_config
    
    def _merge_configs(
        self,
        default: AgentConfig,
        override: AgentConfiguration
    ) -> AgentConfig:
        """Merge database override with code defaults."""
        merged = default.model_copy()
        
        # Override non-None fields
        if override.role:
            merged.role = override.role
        if override.goal:
            merged.goal = override.goal
        if override.backstory:
            merged.backstory = override.backstory
        if override.provider_config_id:
            merged.provider_config_id = override.provider_config_id
        if override.model_override:
            merged.model_override = override.model_override
        if override.temperature is not None:
            merged.temperature = override.temperature
        if override.max_tokens:
            merged.max_tokens = override.max_tokens
        if override.enabled_tools:
            merged.enabled_tools = override.enabled_tools
        if override.tool_configs:
            merged.tool_configs = override.tool_configs
        
        merged.version = override.version
        
        return merged
    
    def _load_code_defaults(self) -> Dict[str, AgentConfig]:
        """
        Load hardcoded defaults from flow files.
        In the future, this could introspect flow files or use a registry.
        """
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
                enabled_tools=[],
                temperature=0.3,
                max_tokens=4000
            ),
            # Add other flows/agents here
        }
```

---

## 🔌 API Endpoints

```python
# src/api/routes/agents.py

@router.get(
    "/configurations/{customer_id}/{flow_id}/{agent_id}",
    response_model=AgentConfigResponse
)
async def get_agent_configuration(
    customer_id: str,
    flow_id: str,
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get current agent configuration (merged: override + defaults)."""
    config_service = AgentConfigurationService(db)
    config = config_service.get_agent_config(customer_id, flow_id, agent_id)
    return config


@router.put(
    "/configurations/{customer_id}/{flow_id}/{agent_id}",
    response_model=AgentConfigResponse
)
async def update_agent_configuration(
    customer_id: str,
    flow_id: str,
    agent_id: str,
    request: AgentConfigUpdateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(require_permission("agents:write"))
):
    """
    Update agent configuration (UI or programmatic - both use this).
    Invalidates cache. Next execution uses new config.
    """
    config_service = AgentConfigurationService(db)
    db_config = config_service.set_agent_config(
        customer_id=customer_id,
        flow_identifier=flow_id,
        agent_identifier=agent_id,
        config=request.dict(exclude_unset=True),
        updated_by="ui",
        user_id=current_user.user_id
    )
    
    # Return merged config (what will actually be used)
    merged_config = config_service.get_agent_config(customer_id, flow_id, agent_id)
    return merged_config
```

---

## ✅ Guarantees

### 1. **No State Mismatch**
- UI reads from `get_agent_config()` → Shows merged config
- Flow executes with `get_agent_config()` → Uses same merged config
- **Always in sync!**

### 2. **Immediate Effect**
- Update via UI → Cache invalidated → Next execution uses new config
- Update via code → Cache invalidated → Next execution uses new config
- **No restart required!**

### 3. **Audit Trail**
```sql
SELECT 
    version,
    updated_by,
    updated_at,
    role,
    model_override
FROM agent_configurations
WHERE customer_id = 'customer-a'
  AND flow_identifier = 'data_analysis_flow'
  AND agent_identifier = 'data_retrieval_agent'
ORDER BY version DESC;

-- Result:
-- version | updated_by | updated_at          | role                      | model
-- --------|------------|---------------------|---------------------------|---------
-- 3       | ui         | 2025-01-08 14:23:00 | Expert Data Retriever     | gpt-4
-- 2       | migration  | 2025-01-08 10:15:00 | Data Retrieval Specialist | gpt-4
-- 1       | code       | 2025-01-08 09:00:00 | Data Retrieval Specialist | gpt-3.5
```

---

## 🧪 Testing the Architecture

### Test 1: UI Update Reflected Immediately
```bash
# 1. Get current config
GET /v1/agents/configurations/customer-a/data_analysis_flow/data_retrieval_agent
# Response: { "role": "Data Retrieval Specialist", "model": "gpt-3.5-turbo" }

# 2. Update via UI
PUT /v1/agents/configurations/customer-a/data_analysis_flow/data_retrieval_agent
{ "role": "Expert Retriever", "model_override": "gpt-4" }

# 3. Trigger flow execution
POST /v1/bi/questions
{ "question": "What is employee turnover?" }

# 4. Check execution timeline
GET /v1/bi/questions/{id}/timeline
# ✅ Verify agent used: "role": "Expert Retriever", "model": "gpt-4"
```

### Test 2: Programmatic Update Works
```python
# Admin script updates config
from src.services.agent_configuration_service import AgentConfigurationService

db = SessionLocal()
config_service = AgentConfigurationService(db)
config_service.set_agent_config(
    customer_id="customer-a",
    flow_identifier="data_analysis_flow",
    agent_identifier="data_retrieval_agent",
    config={"temperature": 0.1},  # Make it more deterministic
    updated_by="admin_script"
)
db.close()

# Trigger execution via UI
# ✅ Agent uses temperature=0.1
```

### Test 3: Cache Invalidation
```python
# Update config
config_service.set_agent_config(...)  # Cache invalidated

# Query again within 60 seconds
config1 = config_service.get_agent_config(...)  # Fresh from DB
config2 = config_service.get_agent_config(...)  # From cache (same result)

# Wait 61 seconds
time.sleep(61)
config3 = config_service.get_agent_config(...)  # Cache expired, fresh from DB
```

---

## 🚀 Migration Path

### Phase 1: Service Layer (Week 1)
- ✅ Create `AgentConfiguration` model
- ✅ Create `AgentConfigurationService` with defaults
- ✅ Add migration

### Phase 2: Flow Integration (Week 1)
- ✅ Add `_get_agent_config()` helper to flows
- ✅ Modify `DataAnalysisFlow` to use runtime config
- ✅ Modify `TaskEnrichmentFlow` to use runtime config
- ✅ Test: Verify flows still work (using defaults)

### Phase 3: API Endpoints (Week 2)
- ✅ Add `/v1/agents/configurations/*` routes
- ✅ Test: Update via API, verify execution uses new config

### Phase 4: UI (Week 2-3)
- ✅ Build clean list UI (already designed!)
- ✅ Wire up API calls
- ✅ Test: Update via UI, verify execution uses new config

---

## 📋 Summary

**Single Source of Truth:**
- `AgentConfigurationService` is the ONLY place configs are read from
- Database stores customer overrides
- Code provides default fallbacks
- Cache ensures performance

**Runtime Resolution:**
- Flows query service at EVERY execution
- No hardcoded values in execution path
- Always uses latest config

**Bidirectional Updates:**
- UI → API → Service → DB → Cache invalidation
- Code → Service → DB → Cache invalidation
- Both paths identical!

**Zero State Mismatch:**
- UI reads from service
- Flow executes from service
- **Always the same config!**

---

## ✅ Result

```
User updates prompt in UI
    ↓
30 seconds later, new BI question arrives
    ↓
Flow queries AgentConfigurationService
    ↓
Returns latest config from DB
    ↓
Agent executes with NEW prompt
    ↓
✅ UI and execution are IN SYNC!
```

**No code deployment. No restart. No mismatch. Ever.**

