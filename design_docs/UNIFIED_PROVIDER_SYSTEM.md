# Unified Provider Configuration System

## 🎯 Overview

The AI Enablement Platform now features a **unified, multi-tenant provider configuration system** that allows each customer to configure their own API keys and settings for **all supported AI providers**.

### ✨ Key Features

- ✅ **Multi-Tenant**: Each customer configures their own API keys
- ✅ **Unified API**: Single endpoint pattern for all providers
- ✅ **Secure**: Encrypted credential storage using Fernet
- ✅ **Extensible**: Easy to add new providers
- ✅ **Database-First**: Configurations stored in database, not environment
- ✅ **Backward Compatible**: Falls back to environment variables
- ✅ **Type-Safe**: Full Pydantic validation

---

## 🏗️ Architecture

### Before (Old System)

```python
# ❌ Single global API key shared across all customers
OPENAI_API_KEY=sk-...  # Environment variable only
ANTHROPIC_API_KEY=sk-ant-...  # Environment variable only

# Problem: All customers use the same API keys!
```

### After (New System)

```python
# ✅ Each customer has their own configurations
customer_123:
  - OpenAI config (their API key)
  - Anthropic config (their API key)
  - Groq config (their API key)
  - Bedrock config (their AWS credentials)

customer_456:
  - OpenAI config (different API key)
  - Anthropic config (different API key)
```

---

## 📊 Supported Providers

| Provider | Type | Authentication | Models |
|----------|------|----------------|--------|
| **OpenAI** | `openai` | API Key | GPT-4, GPT-3.5-turbo, etc. |
| **Anthropic** | `anthropic` | API Key | Claude 3 Opus, Sonnet, Haiku |
| **Groq** | `groq` | API Key | Llama 3.1, Mixtral, Gemma |
| **AWS Bedrock** | `bedrock` | API Keys or IAM Role | Claude, Llama, Titan |

---

## 🚀 Quick Start

### 1. Create OpenAI Configuration

```bash
curl -X POST "http://localhost:5001/v1/providers/configurations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "openai",
    "name": "My OpenAI Config",
    "is_enabled": true,
    "config": {
      "api_key": "sk-...",
      "available_models": ["gpt-4", "gpt-3.5-turbo"],
      "default_model": "gpt-4"
    }
  }'
```

### 2. Create Anthropic Configuration

```bash
curl -X POST "http://localhost:5001/v1/providers/configurations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "anthropic",
    "name": "My Claude Config",
    "is_enabled": true,
    "config": {
      "api_key": "sk-ant-...",
      "available_models": ["claude-3-opus-20240229", "claude-3-sonnet-20240229"],
      "default_model": "claude-3-opus-20240229"
    }
  }'
```

### 3. Create Groq Configuration

```bash
curl -X POST "http://localhost:5001/v1/providers/configurations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "groq",
    "name": "My Groq Config",
    "is_enabled": true,
    "config": {
      "api_key": "gsk_...",
      "available_models": ["llama-3.1-70b-versatile"],
      "default_model": "llama-3.1-70b-versatile"
    }
  }'
```

### 4. Create Bedrock Configuration

```bash
curl -X POST "http://localhost:5001/v1/providers/configurations" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "bedrock",
    "name": "My Bedrock Config",
    "is_enabled": true,
    "config": {
      "auth_method": "api_keys",
      "aws_region": "us-west-2",
      "aws_access_key_id": "AKIA...",
      "aws_secret_access_key": "...",
      "available_models": [],
      "default_model": null
    }
  }'
```

---

## 📚 API Reference

### Base URL
```
/v1/providers
```

### Endpoints

#### 1. List Available Provider Types

```http
GET /v1/providers/available
```

Returns metadata about all supported provider types.

**Response:**
```json
{
  "available_providers": [
    {
      "type": "openai",
      "name": "OpenAI",
      "description": "OpenAI GPT models (GPT-4, GPT-3.5-turbo, etc.)",
      "requires_api_key": true,
      "supports_models": ["gpt-4", "gpt-3.5-turbo"],
      "auth_methods": ["api_key"]
    },
    ...
  ]
}
```

#### 2. Create Provider Configuration

```http
POST /v1/providers/configurations
```

**Request Body:**
```json
{
  "provider_type": "openai",  // or "anthropic", "groq", "bedrock"
  "name": "My Configuration",
  "is_enabled": true,
  "config": {
    "api_key": "sk-...",
    "available_models": ["gpt-4"],
    "default_model": "gpt-4"
  }
}
```

**Response:**
```json
{
  "id": 1,
  "customer_id": "customer_123",
  "provider_type": "openai",
  "name": "My Configuration",
  "is_enabled": true,
  "is_healthy": false,
  "last_health_check": null,
  "config_summary": {
    "available_models": ["gpt-4"],
    "default_model": "gpt-4"
  },
  "created_at": "2025-01-08T12:00:00Z"
}
```

#### 3. List Configurations

```http
GET /v1/providers/configurations?provider_type=openai
```

**Query Parameters:**
- `provider_type` (optional): Filter by provider type

**Response:**
```json
{
  "providers": [...],
  "total_count": 3,
  "by_type": {
    "openai": 1,
    "anthropic": 1,
    "bedrock": 1
  }
}
```

#### 4. Get Configuration

```http
GET /v1/providers/configurations/{id}
```

#### 5. Update Configuration

```http
PUT /v1/providers/configurations/{id}
```

**Request Body:**
```json
{
  "is_enabled": false,
  "config": {
    "api_key": "new-key"
  }
}
```

#### 6. Delete Configuration

```http
DELETE /v1/providers/configurations/{id}
```

#### 7. Test Connection

```http
POST /v1/providers/configurations/{id}/test
```

**Request Body:**
```json
{
  "test_prompt": "Hello, this is a test."
}
```

**Response:**
```json
{
  "success": true,
  "provider_type": "openai",
  "message": "openai connection successful",
  "response_time_ms": 234.5,
  "test_output": "Hello! I'm working correctly...",
  "model_tested": "gpt-3.5-turbo",
  "tested_at": "2025-01-08T12:05:00Z"
}
```

---

## 🔐 Security

### Credential Encryption

All sensitive credentials are encrypted before storage:

```python
# Encrypted using Fernet (AES-128)
api_key_encrypted = encrypt_value(json.dumps({
    "api_key": "sk-..."
}))

# Stored in database
CustomerAIProvider.api_key_encrypted = api_key_encrypted
```

### What's Encrypted

- OpenAI/Anthropic/Groq: `api_key`
- Bedrock: `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`

### What's NOT Encrypted

- Provider type
- Model lists
- Base URLs
- Timeouts and settings

---

## 💾 Database Schema

Uses existing `CustomerAIProvider` model:

```python
class CustomerAIProvider(BaseModel):
    id = Column(Integer, primary_key=True)
    customer_id = Column(String(100))  # Multi-tenant key
    provider_name = Column(String(50))  # "openai", "anthropic", etc.
    
    # Encrypted credentials
    api_key_encrypted = Column(Text)  # JSON with encrypted keys
    
    # Non-sensitive config
    config_data = Column(JSON)  # Models, URLs, settings
    
    # Status
    is_enabled = Column(Boolean)
    is_healthy = Column(Boolean)
    last_health_check = Column(DateTime)
    error_count = Column(Integer)
```

---

## 🔄 Migration Guide

### From Environment Variables to Database

#### Step 1: Check Current Configuration

```bash
# See what environment variables are set
echo $OPENAI_API_KEY
echo $ANTHROPIC_API_KEY
```

#### Step 2: Create Database Configurations

```python
# Use API or admin interface to create configs
POST /v1/providers/configurations
{
  "provider_type": "openai",
  "config": {
    "api_key": "$OPENAI_API_KEY"  # Copy from env
  }
}
```

#### Step 3: Test Configuration

```bash
curl -X POST "/v1/providers/configurations/1/test"
```

#### Step 4: Remove Environment Variables (Optional)

```bash
# Once database configs work, you can remove env vars
# unset OPENAI_API_KEY
# unset ANTHROPIC_API_KEY
```

### Backward Compatibility

**The system automatically falls back to environment variables** if no database configuration exists:

```python
# Priority order:
1. Database configuration (per-customer)
2. Environment variables (global fallback)
```

---

## 🎨 Using Configured Providers

### In CrewAI Flows

```python
from crewai import Agent

# Use database-configured provider
agent = Agent(
    role="Analyst",
    llm="openai_1:gpt-4"  # Format: {provider_key}:{model}
)

# Provider key is: {type}_{config_id}
# Examples:
# - openai_1:gpt-4
# - anthropic_2:claude-3-opus-20240229
# - groq_3:llama-3.1-70b-versatile
# - bedrock_us-west-2_4:anthropic.claude-v2
```

### In Python Code

```python
from src.services.model_service import ModelService

model_service = ModelService(settings, customer_config)

# List all available providers (includes database configs)
providers = model_service.providers
# {
#   "openai_1": <OpenAIProvider>,
#   "anthropic_2": <AnthropicProvider>,
#   "groq_3": <GroqProvider>,
#   "bedrock_us-west-2_4": <BedrockProvider>
# }

# Generate text
response = await model_service.generate_text(
    provider="openai_1",
    model="gpt-4",
    prompt="Hello!"
)
```

---

## 🛠️ Provider Configuration Templates

### OpenAI

```json
{
  "provider_type": "openai",
  "config": {
    "api_key": "sk-...",
    "organization_id": "org-...",  // Optional
    "base_url": "https://api.openai.com/v1",  // Optional
    "available_models": ["gpt-4", "gpt-3.5-turbo"],
    "default_model": "gpt-4",
    "max_retries": 3,
    "timeout": 60
  }
}
```

### Anthropic

```json
{
  "provider_type": "anthropic",
  "config": {
    "api_key": "sk-ant-...",
    "base_url": "https://api.anthropic.com",  // Optional
    "available_models": [
      "claude-3-opus-20240229",
      "claude-3-sonnet-20240229"
    ],
    "default_model": "claude-3-opus-20240229",
    "max_retries": 3,
    "timeout": 60
  }
}
```

### Groq

```json
{
  "provider_type": "groq",
  "config": {
    "api_key": "gsk_...",
    "base_url": "https://api.groq.com/openai/v1",  // Optional
    "available_models": [
      "llama-3.1-70b-versatile",
      "mixtral-8x7b-32768"
    ],
    "default_model": "llama-3.1-70b-versatile",
    "max_retries": 3,
    "timeout": 60
  }
}
```

### AWS Bedrock (API Keys)

```json
{
  "provider_type": "bedrock",
  "config": {
    "auth_method": "api_keys",
    "aws_region": "us-west-2",
    "aws_access_key_id": "AKIA...",
    "aws_secret_access_key": "...",
    "aws_session_token": "...",  // Optional
    "available_models": [],
    "default_model": null
  }
}
```

### AWS Bedrock (IAM Role)

```json
{
  "provider_type": "bedrock",
  "config": {
    "auth_method": "iam_role",
    "aws_region": "us-west-2",
    "available_models": [],
    "default_model": null
  }
}
```

---

## 🧪 Testing

### Test Provider Connection

```bash
# Test OpenAI
curl -X POST "/v1/providers/configurations/1/test" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"test_prompt": "Say hello"}'

# Test Anthropic
curl -X POST "/v1/providers/configurations/2/test" \
  -H "Authorization: Bearer $TOKEN"

# Test Groq
curl -X POST "/v1/providers/configurations/3/test" \
  -H "Authorization: Bearer $TOKEN"
```

### Verify Providers Loaded

```python
# Check ModelService
model_service = ModelService(settings, customer_config)
print(f"Loaded providers: {list(model_service.providers.keys())}")

# Expected output:
# ['openai_1', 'anthropic_2', 'groq_3', 'bedrock_us-west-2_4']
```

---

## 📈 Benefits Over Old System

### Multi-Tenancy
- ✅ Each customer has their own API keys
- ✅ Costs tracked per customer
- ✅ Rate limits per customer
- ❌ Old: All customers shared one API key

### Security
- ✅ Credentials encrypted in database
- ✅ No API keys in environment variables
- ✅ Per-customer access control
- ❌ Old: API keys in plaintext env files

### Flexibility
- ✅ Configure multiple providers per customer
- ✅ Enable/disable providers per customer
- ✅ Different models per customer
- ❌ Old: Global configuration only

### Auditing
- ✅ Track who configured what
- ✅ Health monitoring per configuration
- ✅ Error tracking per configuration
- ❌ Old: No audit trail

---

## 🐛 Troubleshooting

### Provider Not Loading

**Problem**: Configured provider doesn't appear in `model_service.providers`

**Solution**:
1. Check `is_enabled = true` in database
2. Verify credentials are encrypted correctly
3. Check logs for initialization errors
4. Test connection via API

### Connection Test Fails

**Problem**: `/test` endpoint returns `success: false`

**Solution**:
1. Verify API key is correct
2. Check provider's API status
3. Ensure network connectivity
4. Review error_details in response

### Models Not Available

**Problem**: Models don't appear when using provider

**Solution**:
1. Ensure `available_models` is set in config
2. Add models via API or database
3. Set `default_model` if needed

---

## 🚀 Future Enhancements

- [ ] UI for provider configuration
- [ ] Model marketplace/discovery
- [ ] Usage analytics per provider
- [ ] Cost tracking per provider
- [ ] Automatic failover between providers
- [ ] Provider health monitoring dashboard
- [ ] Bulk import from environment variables

---

## 📝 Summary

The unified provider configuration system provides:

✅ **Per-Customer Configuration**: Each customer configures their own API keys  
✅ **Unified API**: Single endpoint pattern for all providers  
✅ **Secure**: Encrypted credential storage  
✅ **Extensible**: Easy to add new providers  
✅ **Backward Compatible**: Falls back to environment variables  

**All providers (OpenAI, Anthropic, Groq, Bedrock) now work the same way!**

