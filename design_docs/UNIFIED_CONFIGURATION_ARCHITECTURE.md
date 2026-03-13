# Unified Configuration Architecture
## Agent Configs + Model Configs = Complete Runtime State

---

## 🏗️ **Two-Layer System**

```
┌──────────────────────────────────────────────────────────┐
│                 LAYER 1: PROVIDER CONFIGS                │
│  (Who provides the LLM? What are the credentials?)      │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  CustomerAIProvider (Database)                 │    │
│  │  ─────────────────────────────────────────     │    │
│  │  id: 42                                        │    │
│  │  customer_id: "caylent"                        │    │
│  │  provider_name: "openai"                       │    │
│  │  api_key_encrypted: "..."                      │    │
│  │  config_data: {                                │    │
│  │    "models": ["gpt-4", "gpt-3.5-turbo"],      │    │
│  │    "base_url": "https://api.openai.com/v1"    │    │
│  │  }                                             │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Managed by: ProviderService                            │
└──────────────────────────────────────────────────────────┘
                         ↓ REFERENCED BY
┌──────────────────────────────────────────────────────────┐
│               LAYER 2: AGENT CONFIGS                     │
│  (How does this agent behave? What prompts? Tools?)     │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  AgentConfiguration (Database)                 │    │
│  │  ─────────────────────────────────────────     │    │
│  │  customer_id: "caylent"                        │    │
│  │  flow_identifier: "data_analysis_flow"         │    │
│  │  agent_identifier: "data_retrieval_agent"      │    │
│  │                                                │    │
│  │  role: "Expert Data Retriever"                 │    │
│  │  goal: "Find all relevant data..."             │    │
│  │  backstory: "You are an expert..."             │    │
│  │                                                │    │
│  │  provider_config_id: 42  ← LINKS TO LAYER 1   │    │
│  │  model_override: "gpt-4"                       │    │
│  │  temperature: 0.3                              │    │
│  │                                                │    │
│  │  enabled_tools: ["hr_database", "doc_search"] │    │
│  │  tool_configs: {...}                           │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Managed by: AgentConfigurationService                  │
└──────────────────────────────────────────────────────────┘
                         ↓ RESOLVED AT RUNTIME
┌──────────────────────────────────────────────────────────┐
│              RUNTIME: COMPLETE AGENT STATE               │
│  (Merged config used by CrewAI Flow)                    │
│                                                          │
│  Agent Properties:                                       │
│  ✓ role: "Expert Data Retriever"    (Layer 2)          │
│  ✓ goal: "Find all relevant..."     (Layer 2)          │
│  ✓ backstory: "You are..."          (Layer 2)          │
│  ✓ temperature: 0.3                  (Layer 2)          │
│  ✓ tools: [hr_tool, doc_tool]       (Layer 2)          │
│                                                          │
│  LLM Client:                                            │
│  ✓ provider: OpenAI                  (Layer 1)          │
│  ✓ api_key: "sk-..."                 (Layer 1)          │
│  ✓ base_url: "https://..."           (Layer 1)          │
│  ✓ model: "gpt-4"                    (Layer 2 override) │
│                                                          │
│  RESULT: Fully configured Agent ready to execute!       │
└──────────────────────────────────────────────────────────┘
```

---

## 🔗 **How They Connect**

### **Database Relationship:**
```sql
-- Layer 1: Provider Configurations
CREATE TABLE customer_ai_providers (
    id SERIAL PRIMARY KEY,
    customer_id VARCHAR(255) NOT NULL,
    provider_name VARCHAR(50) NOT NULL,  -- "openai", "anthropic", "bedrock"
    api_key_encrypted TEXT,
    config_data JSONB,  -- Models, base_url, etc.
    is_enabled BOOLEAN DEFAULT TRUE
);

-- Layer 2: Agent Configurations (references Layer 1)
CREATE TABLE agent_configurations (
    customer_id VARCHAR(255) NOT NULL,
    flow_identifier VARCHAR(255) NOT NULL,
    agent_identifier VARCHAR(255) NOT NULL,
    
    -- Agent behavior
    role TEXT,
    goal TEXT,
    backstory TEXT,
    
    -- LLM configuration (references Layer 1!)
    provider_config_id INTEGER REFERENCES customer_ai_providers(id),
    model_override VARCHAR(255),  -- Optional: Override default model
    temperature FLOAT,
    max_tokens INTEGER,
    
    -- Tools
    enabled_tools JSONB,
    
    UNIQUE (customer_id, flow_identifier, agent_identifier)
);
```

---

## 🔄 **Runtime Resolution Process**

### **Step-by-Step:**

```python
# User triggers BI question
POST /v1/bi/questions
{
  "question": "What is turnover rate?",
  "company_hr_dataset": "caylent"
}

# ↓ Backend starts DataAnalysisFlow

# STEP 1: Load Agent Config (Layer 2)
agent_config = AgentConfigurationService.get_agent_config(
    customer_id="caylent",
    flow_identifier="data_analysis_flow",
    agent_identifier="data_retrieval_agent"
)
# Returns:
# {
#   role: "Expert Data Retriever",
#   goal: "Find all relevant data...",
#   provider_config_id: 42,
#   model_override: "gpt-4",
#   temperature: 0.3,
#   enabled_tools: ["hr_database", "doc_search"]
# }

# STEP 2: Resolve Provider Config (Layer 1)
if agent_config.provider_config_id:
    provider_config = ProviderService.get_provider_config(
        config_id=agent_config.provider_config_id
    )
    # Returns:
    # {
    #   provider_name: "openai",
    #   api_key: "sk-...",  (decrypted)
    #   base_url: "https://api.openai.com/v1",
    #   available_models: ["gpt-4", "gpt-3.5-turbo"]
    # }
else:
    # Fallback to environment variables or default provider
    provider_config = ProviderService.get_default_provider(customer_id)

# STEP 3: Select Model
if agent_config.model_override:
    model = agent_config.model_override  # "gpt-4"
else:
    model = provider_config.default_model  # From provider config

# STEP 4: Build LLM Client
llm = LLM(
    model=model,                           # Layer 2 (or Layer 1 default)
    api_key=provider_config.api_key,      # Layer 1
    base_url=provider_config.base_url,    # Layer 1
    temperature=agent_config.temperature, # Layer 2
    max_tokens=agent_config.max_tokens    # Layer 2
)

# STEP 5: Build Agent
agent = Agent(
    role=agent_config.role,              # Layer 2
    goal=agent_config.goal,              # Layer 2
    backstory=agent_config.backstory,    # Layer 2
    tools=resolve_tools(agent_config.enabled_tools),  # Layer 2
    llm=llm                              # Layer 1 + Layer 2
)

# STEP 6: Execute
result = crew.kickoff()

# ✅ Agent executed with COMPLETE CONFIG from both layers!
```

---

## 🔧 **Enhanced AgentConfigurationService**

```python
# src/services/agent_configuration_service.py

class CompleteAgentConfig(BaseModel):
    """Fully resolved agent configuration (Layer 1 + Layer 2)."""
    # Layer 2: Agent behavior
    agent_identifier: str
    flow_identifier: str
    role: str
    goal: str
    backstory: str
    temperature: float
    max_tokens: int
    enabled_tools: List[str]
    tool_configs: Dict[str, Any]
    
    # Layer 1: Provider/LLM config
    provider_type: str          # "openai", "anthropic", "bedrock"
    provider_config_id: int
    model: str                  # Resolved model name
    api_key: Optional[str]      # Decrypted (for internal use only!)
    base_url: Optional[str]
    
    # Metadata
    source: str  # "default", "override", "merged"
    version: int


class AgentConfigurationService(BaseService):
    """Manages agent configurations (Layer 2)."""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.provider_service = ProviderService(db)
    
    def get_complete_agent_config(
        self,
        customer_id: str,
        flow_identifier: str,
        agent_identifier: str
    ) -> CompleteAgentConfig:
        """
        Get COMPLETE agent config (Layer 1 + Layer 2 merged).
        
        This is the SINGLE source of truth for runtime execution.
        Returns fully resolved config with provider credentials.
        """
        # STEP 1: Get agent config (Layer 2)
        agent_config = self.get_agent_config(
            customer_id, flow_identifier, agent_identifier
        )
        
        # STEP 2: Resolve provider config (Layer 1)
        if agent_config.provider_config_id:
            # Customer specified a provider
            provider_config = self.provider_service.get_provider_by_id(
                config_id=agent_config.provider_config_id,
                customer_id=customer_id
            )
        else:
            # Use customer's default provider (first enabled)
            provider_config = self.provider_service.get_default_provider(
                customer_id=customer_id
            )
        
        if not provider_config:
            raise ConfigurationError(
                f"No provider configuration found for customer {customer_id}"
            )
        
        # STEP 3: Resolve model
        if agent_config.model_override:
            # Agent config explicitly sets model
            model = agent_config.model_override
        else:
            # Use provider's default model
            model = provider_config.get_default_model()
        
        # STEP 4: Decrypt credentials (internal use only!)
        api_key = None
        if provider_config.api_key_encrypted:
            api_key = self.provider_service._decrypt_api_key(
                provider_config.api_key_encrypted
            )
        
        # STEP 5: Build complete config
        complete_config = CompleteAgentConfig(
            # Layer 2: Agent behavior
            agent_identifier=agent_config.agent_identifier,
            flow_identifier=agent_config.flow_identifier,
            role=agent_config.role,
            goal=agent_config.goal,
            backstory=agent_config.backstory,
            temperature=agent_config.temperature,
            max_tokens=agent_config.max_tokens,
            enabled_tools=agent_config.enabled_tools,
            tool_configs=agent_config.tool_configs,
            
            # Layer 1: Provider/LLM
            provider_type=provider_config.provider_name,
            provider_config_id=provider_config.id,
            model=model,
            api_key=api_key,
            base_url=provider_config.config_data.get("base_url"),
            
            # Metadata
            source=agent_config.source,
            version=agent_config.version
        )
        
        return complete_config
```

---

## 🔌 **Flow Integration**

```python
# src/crewai_flows/data_analysis_flow.py

class DataAnalysisFlow(Flow[DataAnalysisFlowState]):
    def __init__(self):
        # No longer initialize LLM in __init__!
        # LLM will be resolved per-agent at runtime
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
    
    def _get_complete_agent_config(self, agent_identifier: str) -> CompleteAgentConfig:
        """Get complete agent config (Layer 1 + Layer 2 merged)."""
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
    
    def _build_llm_from_config(self, config: CompleteAgentConfig) -> LLM:
        """Build LLM client from complete config."""
        if config.provider_type == "openai":
            return LLM(
                model=config.model,
                api_key=config.api_key,
                base_url=config.base_url or "https://api.openai.com/v1",
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
        elif config.provider_type == "anthropic":
            return LLM(
                model=config.model,
                api_key=config.api_key,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
        elif config.provider_type == "bedrock":
            # Bedrock uses OpenAI-compatible endpoint
            return LLM(
                model=config.model,
                api_key="bedrock",  # Placeholder, uses AWS credentials
                base_url=config.base_url,
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
        else:
            raise ConfigurationError(f"Unsupported provider: {config.provider_type}")
```

---

## 🎨 **UI Implications**

### **Agent Configuration Form:**
```tsx
// Agent Config Editor shows BOTH layers:

┌────────────────────────────────────────┐
│ AGENT CONFIGURATION                    │
├────────────────────────────────────────┤
│                                        │
│ Agent Identity                         │
│ Flow: Data Analysis Flow               │
│ Agent: Data Retrieval Agent            │
│                                        │
│ ━━ PROMPTS (Layer 2) ━━━━━━━━━━━━━━━  │
│                                        │
│ Role:                                  │
│ ┌────────────────────────────────────┐ │
│ │ Expert Data Retriever              │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Goal:                                  │
│ ┌────────────────────────────────────┐ │
│ │ Find all relevant data...          │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Backstory:                             │
│ ┌────────────────────────────────────┐ │
│ │ You are an expert at...            │ │
│ └────────────────────────────────────┘ │
│                                        │
│ ━━ MODEL CONFIG (Layer 1 + 2) ━━━━━━  │
│                                        │
│ Provider:                              │
│ ┌────────────────────────────────────┐ │
│ │ [▼] OpenAI (API Key: sk-...xyz)    │ │ ← Layer 1
│ │     Anthropic (API Key: sk-...abc) │ │
│ │     Bedrock (us-west-2)            │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Model:                                 │
│ ┌────────────────────────────────────┐ │
│ │ [▼] gpt-4                          │ │ ← Layer 2 override
│ │     gpt-3.5-turbo                  │ │    (or Layer 1 default)
│ │     gpt-4-turbo                    │ │
│ └────────────────────────────────────┘ │
│                                        │
│ Temperature: [0.3    ]                 │ ← Layer 2
│ Max Tokens:  [2000   ]                 │ ← Layer 2
│                                        │
│ ━━ TOOLS (Layer 2) ━━━━━━━━━━━━━━━━━  │
│                                        │
│ ☑ HR Database Tool                     │
│ ☑ Document Search Tool                 │
│ ☐ Web Search Tool                      │
│                                        │
│         [Test Agent]  [Save]           │
└────────────────────────────────────────┘
```

### **Key UX Features:**

1. **Provider Dropdown** (Layer 1)
   - Shows all configured providers for this customer
   - Displays provider type + identifier (API key last 4 chars, region, etc.)
   - User selects which provider this agent should use

2. **Model Dropdown** (Layer 2 Override)
   - Shows available models from selected provider
   - Can override the provider's default model
   - If blank, uses provider's default

3. **Temperature/Tokens** (Layer 2)
   - Agent-specific overrides
   - Can differ per agent even if using same provider

---

## 📊 **Example Scenarios**

### **Scenario 1: Different Agents, Same Provider, Different Models**
```
Customer: Caylent
Provider Config: OpenAI (id=42, models: [gpt-4, gpt-3.5-turbo])

Agent 1: Data Retrieval Agent
  - provider_config_id: 42
  - model_override: "gpt-3.5-turbo"  ← Fast, cheap for retrieval
  - temperature: 0.3

Agent 2: BI Analyst Agent
  - provider_config_id: 42
  - model_override: "gpt-4"  ← Smarter for analysis
  - temperature: 0.7

✅ Both use same OpenAI account, different models!
```

### **Scenario 2: Different Agents, Different Providers**
```
Customer: Caylent
Provider Config 1: OpenAI (id=42)
Provider Config 2: Anthropic (id=43)

Agent 1: Data Retrieval Agent
  - provider_config_id: 42  ← OpenAI
  - model_override: "gpt-4"

Agent 2: BI Analyst Agent
  - provider_config_id: 43  ← Anthropic
  - model_override: "claude-3-opus-20240229"

✅ Each agent uses different provider!
```

### **Scenario 3: Update Provider, All Agents Update**
```
Customer updates OpenAI API key via Provider Config UI:
  - OpenAI config id=42
  - New API key: "sk-NEW-KEY-123"

All agents using provider_config_id=42 automatically:
  ✅ Use new API key on next execution
  ✅ No agent config changes needed!

Why? Runtime resolution queries BOTH layers fresh every time!
```

---

## 🔄 **Update Workflows**

### **Workflow 1: Change Agent Prompt (Layer 2 Only)**
```
1. User navigates to Agent Config UI
2. Edits "Role" field: "Expert Data Retriever"
3. Clicks "Save"
   → PUT /v1/agents/configurations/{id}
   → Updates agent_configurations table
   → Cache invalidated
4. Next execution:
   → Queries agent_configurations (Layer 2)
   → Queries customer_ai_providers (Layer 1)
   → Merges both
   → ✅ Uses new role, same provider/model
```

### **Workflow 2: Change Provider Credentials (Layer 1 Only)**
```
1. User navigates to Provider Config UI
2. Updates OpenAI API key
3. Clicks "Save"
   → PUT /v1/providers/configurations/{id}
   → Updates customer_ai_providers table
4. Next execution:
   → Queries agent_configurations (Layer 2)
   → Queries customer_ai_providers (Layer 1) ← NEW KEY!
   → Merges both
   → ✅ Uses same prompts, new API key
```

### **Workflow 3: Switch Agent to Different Provider**
```
1. User navigates to Agent Config UI
2. Changes "Provider" dropdown: OpenAI → Anthropic
3. Changes "Model" dropdown: gpt-4 → claude-3-opus
4. Clicks "Save"
   → PUT /v1/agents/configurations/{id}
   → Updates provider_config_id and model_override
5. Next execution:
   → Queries agent_configurations (Layer 2) ← NEW PROVIDER REF!
   → Queries customer_ai_providers (Layer 1) ← ANTHROPIC!
   → Merges both
   → ✅ Same prompts, different provider!
```

---

## ✅ **State Management Summary**

### **What AgentConfigurationService Manages:**
✅ **Layer 2: Agent Behavior**
- Prompts (role, goal, backstory)
- Temperature, max_tokens
- Tools enabled
- Provider reference (provider_config_id)
- Model override

✅ **Layer 1: Provider Resolution**
- Queries `ProviderService` to get credentials
- Decrypts API keys
- Resolves base URLs
- Gets available models

✅ **Complete Config Merge**
- Returns `CompleteAgentConfig` (Layer 1 + Layer 2)
- Single method: `get_complete_agent_config()`
- Used by flows at runtime

### **What ProviderService Manages:**
✅ **Provider Configurations**
- API keys (encrypted)
- Provider type (openai, anthropic, bedrock)
- Available models
- Base URLs, regions
- Health status

### **Integration Points:**
```python
# Agent config references provider config
agent_configurations.provider_config_id → customer_ai_providers.id

# Runtime resolution
CompleteAgentConfig = merge(
    AgentConfiguration,      # Layer 2
    CustomerAIProvider       # Layer 1
)
```

---

## 🎯 **Single Source of Truth**

```
User updates via UI (either layer)
    ↓
Database updated (agent_configurations OR customer_ai_providers)
    ↓
Cache invalidated
    ↓
Next flow execution:
    ↓
AgentConfigurationService.get_complete_agent_config()
    ↓
Queries BOTH tables (Layer 1 + Layer 2)
    ↓
Merges into CompleteAgentConfig
    ↓
Flow builds Agent with complete config
    ↓
✅ ALWAYS IN SYNC!
```

**Both model configs AND agent configs are part of the same runtime resolution system!**

---

## 📋 **Updated Implementation Checklist**

### Phase 1: Database & Services
- [ ] ✅ `CustomerAIProvider` model (already exists)
- [ ] ✅ `ProviderService` (already exists)
- [ ] Create `AgentConfiguration` model
- [ ] Create `AgentConfigurationService` with:
  - [ ] `get_agent_config()` - Layer 2 only
  - [ ] `get_complete_agent_config()` - Layer 1 + Layer 2 merged
  - [ ] Integration with `ProviderService`

### Phase 2: Flow Integration
- [ ] Modify flows to use `get_complete_agent_config()`
- [ ] Remove hardcoded provider/model selection
- [ ] Build LLM dynamically from complete config

### Phase 3: UI
- [ ] Agent Config form with provider dropdown (Layer 1)
- [ ] Model selection from chosen provider
- [ ] Prompt editing (Layer 2)
- [ ] Tool selection (Layer 2)

---

**Yes, the state management handles BOTH model configs and agent configs!**

They're integrated via `provider_config_id` reference and resolved together at runtime.

Ready to implement this unified system?

