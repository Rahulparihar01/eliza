# Multiple Provider Configurations - Design Guide
## Supporting Multiple API Keys for the Same Provider

---

## 🎯 **Use Case**

**Customer needs multiple OpenAI API keys:**

1. **Development Key** - Low rate limit, testing
2. **Production Key** - High rate limit, production workloads
3. **Team-specific Keys** - Different billing accounts

**Or different models with different keys:**

1. **GPT-4 Key** - High-quality analysis
2. **GPT-3.5 Key** - Fast, cheap retrieval

---

## ✅ **Current Design Supports This!**

### **Database Schema:**
```sql
CREATE TABLE customer_ai_providers (
    id SERIAL PRIMARY KEY,              -- Unique config ID
    customer_id VARCHAR(100),           -- Customer
    provider_name VARCHAR(50),          -- "openai", "anthropic", etc.
    api_key_encrypted TEXT,             -- Different per config
    config_data JSONB,                  -- Stores name, models, etc.
    priority INTEGER DEFAULT 1,
    is_enabled BOOLEAN DEFAULT TRUE,
    ...
);

-- ✅ NO unique constraint on (customer_id, provider_name)
-- ✅ Customer can have MULTIPLE configs for same provider!
```

### **Example Data:**
```sql
-- Customer "caylent" has 3 OpenAI configs:

INSERT INTO customer_ai_providers VALUES
(1, 'caylent', 'openai', 'encrypted_key_1', 
    '{"name": "OpenAI Dev", "models": ["gpt-3.5-turbo"], "purpose": "development"}',
    3, true),
    
(2, 'caylent', 'openai', 'encrypted_key_2', 
    '{"name": "OpenAI Prod GPT-4", "models": ["gpt-4", "gpt-4-turbo"], "purpose": "production"}',
    1, true),
    
(3, 'caylent', 'openai', 'encrypted_key_3', 
    '{"name": "OpenAI Budget GPT-3.5", "models": ["gpt-3.5-turbo"], "purpose": "cost-optimization"}',
    2, true);

-- Each has:
-- ✅ Unique ID (1, 2, 3)
-- ✅ Same provider_name ("openai")
-- ✅ Different api_key_encrypted
-- ✅ Different name in config_data
-- ✅ Different priority (1=highest)
```

---

## 🔧 **Enhanced Schema with Name Field**

**Recommendation: Add a dedicated `name` column for better UX:**

```sql
ALTER TABLE customer_ai_providers 
ADD COLUMN name VARCHAR(255) DEFAULT NULL;

-- Migrate existing data:
UPDATE customer_ai_providers 
SET name = COALESCE(
    config_data->>'name', 
    provider_name || ' Config ' || id
);

-- Result:
-- id | customer_id | provider_name | name                    | api_key_encrypted
-- ---|-------------|---------------|-------------------------|-------------------
-- 1  | caylent     | openai        | OpenAI Dev              | encrypted_key_1
-- 2  | caylent     | openai        | OpenAI Prod GPT-4       | encrypted_key_2
-- 3  | caylent     | openai        | OpenAI Budget GPT-3.5   | encrypted_key_3
-- 4  | caylent     | anthropic     | Anthropic Claude        | encrypted_key_4
```

---

## 🎨 **UI Display: Provider Selection**

### **Current UI (Without Names) - Confusing:**
```
┌────────────────────────────────────┐
│ Provider:                          │
│ ┌────────────────────────────────┐ │
│ │ [▼] OpenAI (sk-...xyz)         │ │ ← Which one?
│ │     OpenAI (sk-...abc)         │ │ ← Which one?
│ │     OpenAI (sk-...def)         │ │ ← Which one?
│ │     Anthropic (sk-...ghi)      │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

### **Enhanced UI (With Names) - Clear:**
```
┌────────────────────────────────────┐
│ Provider:                          │
│ ┌────────────────────────────────┐ │
│ │ [▼] OpenAI Dev                 │ │ ← Clear!
│ │     (gpt-3.5-turbo)            │ │
│ │     API Key: sk-...xyz         │ │
│ │                                │ │
│ │     OpenAI Prod GPT-4          │ │ ← Clear!
│ │     (gpt-4, gpt-4-turbo)       │ │
│ │     API Key: sk-...abc         │ │
│ │                                │ │
│ │     OpenAI Budget GPT-3.5      │ │ ← Clear!
│ │     (gpt-3.5-turbo)            │ │
│ │     API Key: sk-...def         │ │
│ │                                │ │
│ │     Anthropic Claude           │ │
│ │     (claude-3-opus)            │ │
│ │     API Key: sk-...ghi         │ │
│ └────────────────────────────────┘ │
└────────────────────────────────────┘
```

---

## 🔌 **Agent Configuration: Provider Selection**

### **Agents Reference Specific Config by ID:**
```sql
-- Agent configuration references provider by ID (not by name)
CREATE TABLE agent_configurations (
    customer_id VARCHAR(255),
    flow_identifier VARCHAR(255),
    agent_identifier VARCHAR(255),
    
    provider_config_id INTEGER,  -- ← Points to specific config ID!
    model_override VARCHAR(255),
    ...
);

-- Example: Different agents use different OpenAI keys
INSERT INTO agent_configurations VALUES
('caylent', 'data_analysis_flow', 'data_retrieval_agent',
    1,  -- ← OpenAI Dev (id=1)
    'gpt-3.5-turbo', ...),
    
('caylent', 'data_analysis_flow', 'bi_analyst_agent',
    2,  -- ← OpenAI Prod GPT-4 (id=2)
    'gpt-4', ...),
    
('caylent', 'task_enrichment_flow', 'task_analyzer_agent',
    3,  -- ← OpenAI Budget GPT-3.5 (id=3)
    'gpt-3.5-turbo', ...);

-- ✅ Each agent uses a DIFFERENT OpenAI API key!
```

---

## 🔄 **Runtime Resolution with Multiple Configs**

```python
# Agent config:
agent_config = {
    "customer_id": "caylent",
    "flow_identifier": "data_analysis_flow",
    "agent_identifier": "bi_analyst_agent",
    "provider_config_id": 2,  # ← OpenAI Prod GPT-4
    "model_override": "gpt-4",
    "temperature": 0.7
}

# Runtime resolution:
def get_complete_agent_config(customer_id, flow_id, agent_id):
    # 1. Load agent config (Layer 2)
    agent_config = db.query(AgentConfiguration).filter(...).first()
    # Returns: provider_config_id=2
    
    # 2. Resolve SPECIFIC provider config (Layer 1)
    provider_config = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.id == agent_config.provider_config_id  # id=2!
    ).first()
    # Returns: 
    # {
    #   id: 2,
    #   provider_name: "openai",
    #   name: "OpenAI Prod GPT-4",
    #   api_key_encrypted: "encrypted_key_2",  ← THIS key!
    #   config_data: {"models": ["gpt-4", "gpt-4-turbo"]}
    # }
    
    # 3. Decrypt API key
    api_key = decrypt(provider_config.api_key_encrypted)
    # Returns: "sk-prod-key-abc-xyz"  ← Production key!
    
    # 4. Build LLM client
    llm = LLM(
        model="gpt-4",
        api_key="sk-prod-key-abc-xyz",  # ← Specific key!
        base_url="https://api.openai.com/v1"
    )
    
    return llm

# ✅ Agent uses SPECIFIC OpenAI key (id=2), not just "any OpenAI key"
```

---

## 📊 **Use Case Examples**

### **Example 1: Different Keys for Different Agents**
```
Customer: Caylent

OpenAI Configs:
  - Dev Key (id=1): gpt-3.5-turbo, low rate limit
  - Prod Key (id=2): gpt-4, high rate limit

Agent Assignments:
  - Data Retrieval Agent → Dev Key (id=1)
    - Fast queries, not critical
    - Uses: sk-dev-key-123
    
  - BI Analyst Agent → Prod Key (id=2)
    - Important analysis, needs GPT-4
    - Uses: sk-prod-key-456

✅ Both are OpenAI, but different keys and rate limits!
```

### **Example 2: Budget Control with Multiple Keys**
```
Customer: Caylent

OpenAI Configs:
  - High-priority Key (id=1): $500/month budget
  - Budget Key (id=2): $50/month budget

Agent Assignments:
  - Critical Flow Agents → High-priority Key (id=1)
  - Experimental Flow Agents → Budget Key (id=2)

✅ Cost tracking per API key!
```

### **Example 3: Team-specific Keys**
```
Customer: Caylent

OpenAI Configs:
  - HR Team Key (id=1): Billed to HR department
  - Finance Team Key (id=2): Billed to Finance department

Agent Assignments:
  - HR Analysis Flow → HR Team Key (id=1)
  - Finance Analysis Flow → Finance Team Key (id=2)

✅ Department-specific billing!
```

### **Example 4: Model-specific Keys**
```
Customer: Caylent

OpenAI Configs:
  - GPT-4 Only Key (id=1): Access to GPT-4
  - GPT-3.5 Only Key (id=2): Only GPT-3.5 (cheaper)

Agent Assignments:
  - Complex Analysis → GPT-4 Key (id=1)
  - Simple Retrieval → GPT-3.5 Key (id=2)

✅ Granular model access control!
```

---

## 🎯 **Key Design Guarantees**

### **1. Each Config is Fully Independent**
```sql
-- Config 1
id: 1
provider_name: "openai"
api_key_encrypted: "key_1"
config_data: {"name": "Dev", "models": ["gpt-3.5-turbo"]}

-- Config 2
id: 2
provider_name: "openai"
api_key_encrypted: "key_2"  ← Different key!
config_data: {"name": "Prod", "models": ["gpt-4"]}

-- ✅ Same provider, different everything else!
```

### **2. Agents Reference by ID (Not by Provider Name)**
```python
# ❌ BAD: Reference by provider name (ambiguous)
agent_config.provider_name = "openai"  # Which OpenAI config?

# ✅ GOOD: Reference by config ID (specific)
agent_config.provider_config_id = 2  # Exactly this one!
```

### **3. Runtime Resolution is Explicit**
```python
# Load provider config by ID
provider = db.query(CustomerAIProvider).filter(
    CustomerAIProvider.id == agent_config.provider_config_id
).first()

# ✅ Always gets the EXACT config, no ambiguity
```

---

## 🚀 **Implementation Requirements**

### **Phase 1: Database Enhancement (Optional but Recommended)**
```sql
-- Add name column for better UX
ALTER TABLE customer_ai_providers 
ADD COLUMN name VARCHAR(255);

-- Add index for faster lookups
CREATE INDEX idx_provider_configs_customer 
ON customer_ai_providers(customer_id, provider_name);
```

### **Phase 2: Service Layer (Already Correct!)**
```python
class ProviderService:
    def get_provider_by_id(self, config_id: int, customer_id: str):
        """Get SPECIFIC provider config by ID."""
        return self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.id == config_id,
            CustomerAIProvider.customer_id == customer_id
        ).first()
        # ✅ Returns exact config, even if multiple exist for same provider
    
    def list_providers(self, customer_id: str, provider_type: Optional[str] = None):
        """List all provider configs for a customer."""
        query = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == customer_id
        )
        if provider_type:
            query = query.filter(CustomerAIProvider.provider_name == provider_type)
        
        return query.all()
        # ✅ Returns ALL OpenAI configs if provider_type="openai"
```

### **Phase 3: UI Display**
```tsx
// Provider Config List (Admin Settings)
<div className="provider-configs">
  {providerConfigs.map(config => (
    <div key={config.id} className="provider-card">
      <div className="provider-name">
        {config.name || `${config.provider_name} Config ${config.id}`}
      </div>
      <div className="provider-details">
        <span>Provider: {config.provider_name}</span>
        <span>API Key: {config.api_key_masked}</span>  {/* sk-...xyz */}
        <span>Models: {config.available_models.join(', ')}</span>
      </div>
      <div className="provider-actions">
        <button>Edit</button>
        <button>Test Connection</button>
        <button>Delete</button>
      </div>
    </div>
  ))}
</div>

// Agent Config Form - Provider Selector
<select name="provider_config_id">
  {providerConfigs.map(config => (
    <option key={config.id} value={config.id}>
      {config.name || config.provider_name} 
      ({config.provider_name}) 
      - {config.api_key_masked}
    </option>
  ))}
</select>

// Example rendering:
// <option value="1">OpenAI Dev (openai) - sk-...xyz</option>
// <option value="2">OpenAI Prod GPT-4 (openai) - sk-...abc</option>
// <option value="3">OpenAI Budget (openai) - sk-...def</option>
// <option value="4">Anthropic Claude (anthropic) - sk-...ghi</option>
```

---

## 🧪 **Testing Scenarios**

### **Test 1: Create Multiple OpenAI Configs**
```bash
# Create first OpenAI config
POST /v1/providers/configurations
{
  "provider_type": "openai",
  "name": "OpenAI Dev",
  "api_key": "sk-dev-key-123",
  "config": {
    "models": ["gpt-3.5-turbo"]
  }
}
# Response: { "id": 1, ... }

# Create second OpenAI config
POST /v1/providers/configurations
{
  "provider_type": "openai",
  "name": "OpenAI Prod",
  "api_key": "sk-prod-key-456",  # ← Different key!
  "config": {
    "models": ["gpt-4", "gpt-4-turbo"]
  }
}
# Response: { "id": 2, ... }

# List configs
GET /v1/providers/configurations
# Response: [
#   { "id": 1, "name": "OpenAI Dev", "provider_name": "openai" },
#   { "id": 2, "name": "OpenAI Prod", "provider_name": "openai" }
# ]

# ✅ Both exist, distinguishable by name and ID
```

### **Test 2: Assign Different Agents to Different Keys**
```bash
# Agent 1 uses Dev key
PUT /v1/agents/configurations
{
  "customer_id": "caylent",
  "flow_identifier": "data_analysis_flow",
  "agent_identifier": "data_retrieval_agent",
  "provider_config_id": 1,  # ← Dev key
  "model_override": "gpt-3.5-turbo"
}

# Agent 2 uses Prod key
PUT /v1/agents/configurations
{
  "customer_id": "caylent",
  "flow_identifier": "data_analysis_flow",
  "agent_identifier": "bi_analyst_agent",
  "provider_config_id": 2,  # ← Prod key
  "model_override": "gpt-4"
}

# Trigger flow
POST /v1/bi/questions
{ "question": "What is turnover?" }

# Check execution
GET /v1/bi/questions/{id}/timeline
# ✅ Verify:
#   - Data Retrieval Agent used sk-dev-key-123
#   - BI Analyst Agent used sk-prod-key-456
```

### **Test 3: Update One Key, Others Unaffected**
```bash
# Update Dev key
PUT /v1/providers/configurations/1
{
  "api_key": "sk-new-dev-key-789"
}

# Trigger flow
POST /v1/bi/questions
{ "question": "Another question" }

# ✅ Verify:
#   - Data Retrieval Agent uses NEW dev key (sk-new-dev-key-789)
#   - BI Analyst Agent still uses OLD prod key (sk-prod-key-456)
```

---

## ✅ **Summary: Full Support for Multiple Keys**

### **Database:**
✅ No unique constraint on (customer_id, provider_name)
✅ Each config has unique ID
✅ Each config has independent api_key_encrypted
✅ (Recommended) Add `name` column for UX

### **Service Layer:**
✅ `get_provider_by_id()` - Gets SPECIFIC config
✅ `list_providers()` - Lists ALL configs (including duplicates)
✅ Agents reference by `provider_config_id` (not name)

### **Runtime Resolution:**
✅ Queries exact provider config by ID
✅ No ambiguity when multiple OpenAI configs exist
✅ Each agent uses EXACTLY the specified key

### **UI:**
✅ List all provider configs with names
✅ Agent config form shows dropdown of ALL configs
✅ Clear labeling (name + provider + masked key)

---

## 🎯 **Recommendation: Add Name Column**

```sql
-- Migration: Add name column
ALTER TABLE customer_ai_providers 
ADD COLUMN name VARCHAR(255);

-- Update SQLAlchemy model:
class CustomerAIProvider(BaseModel):
    # ... existing columns ...
    name = Column(String(255), nullable=True)  # ← Add this
```

**Benefits:**
- Better UX (show "OpenAI Dev" instead of "openai")
- Easier to distinguish multiple configs
- No breaking changes (nullable)

---

**Yes, the current plan fully supports multiple API keys for the same provider!** 

Each config is independent, referenced by unique ID, and agents can pick exactly which one to use. 🎉
