# Claude/Anthropic API Setup Guide

## Quick Start

### Step 1: Add Your Anthropic API Key

You have **two options** for adding your API key:

#### Option A: Add to `.env` file (Recommended for Development)

Create or edit `/Users/scottgay/Documents/Eliza/eliza-platform/.env`:

```bash
# Add your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Change the default model to Claude
DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022
```

#### Option B: Add to `docker-compose.yml` (Production)

Edit `docker/docker-compose.yml` and add the environment variables to `app` and `celery-worker` services:

```yaml
services:
  app:
    environment:
      # Existing vars...
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022
  
  celery-worker:
    environment:
      # Existing vars...
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022
```

Then create `.env` file in project root:
```bash
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

---

## Available Claude Models

LiteLLM (used by CrewAI) supports these Claude models:

### Production Models
- `claude-3-5-sonnet-20241022` - **Recommended** - Latest Sonnet (best balance)
- `claude-3-5-haiku-20241022` - Fast and efficient (lower cost)
- `claude-3-opus-20240229` - Most powerful (highest cost)

### Legacy Models
- `claude-3-sonnet-20240229`
- `claude-3-haiku-20240307`

### Pricing Comparison
| Model | Input (per 1M tokens) | Output (per 1M tokens) | Speed |
|-------|----------------------|------------------------|-------|
| Claude 3.5 Sonnet | $3 | $15 | Fast |
| Claude 3.5 Haiku | $1 | $5 | Very Fast |
| Claude 3 Opus | $15 | $75 | Slower |

---

## Configuration Changes

### 1. Update `src/core/config.py`

**Already configured!** ✅ Your config already supports:
```python
anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
```

### 2. Update `src/crewai_flows/data_analysis_flow.py`

The LLM initialization needs a small update to properly support Anthropic:

**Current code** (lines 64-69):
```python
self.llm = LLM(
    model=settings.DEFAULT_LLM_MODEL,
    temperature=0.3,
    base_url=settings.OPENAI_API_BASE_URL,  # ❌ Not needed for Anthropic
    api_key=settings.OPENAI_API_KEY,        # ❌ Wrong key
)
```

**Updated code** (dynamic based on model):
```python
# Determine provider from model name
if settings.DEFAULT_LLM_MODEL.startswith("claude"):
    # Use Anthropic
    self.llm = LLM(
        model=settings.DEFAULT_LLM_MODEL,
        temperature=0.3,
        api_key=settings.anthropic_api_key,
    )
else:
    # Use OpenAI
    self.llm = LLM(
        model=settings.DEFAULT_LLM_MODEL,
        temperature=0.3,
        base_url=settings.OPENAI_API_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
    )
```

---

## Step-by-Step Setup

### 1. Get Your Anthropic API Key

1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to **API Keys** section
4. Click **Create Key**
5. Copy your key (starts with `sk-ant-api03-...`)

### 2. Add API Key to Your Environment

**Using `.env` file** (easiest):
```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform
echo "ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here" >> .env
echo "DEFAULT_LLM_MODEL=claude-3-5-sonnet-20241022" >> .env
```

### 3. Update the Flow Configuration

I'll update the `data_analysis_flow.py` to dynamically detect the provider.

### 4. Restart Containers

```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml up -d
```

### 5. Test the Configuration

```bash
docker exec docker-app-1 python test_crewai_data_analysis_production.py
```

---

## LiteLLM Configuration Details

### How LiteLLM Works

LiteLLM automatically detects the provider based on:
1. **Model name prefix** (e.g., `claude-*` → Anthropic, `gpt-*` → OpenAI)
2. **API key environment variable** (e.g., `ANTHROPIC_API_KEY`)

### Required Environment Variables

| Provider | Environment Variable | Model Prefix |
|----------|---------------------|--------------|
| OpenAI | `OPENAI_API_KEY` | `gpt-*` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-*` |
| Groq | `GROQ_API_KEY` | `groq/*` |
| Together AI | `TOGETHER_API_KEY` | `together_ai/*` |

### Example Configurations

**Using Claude 3.5 Sonnet:**
```python
LLM(
    model="claude-3-5-sonnet-20241022",
    temperature=0.3,
    api_key=settings.anthropic_api_key,
)
```

**Using GPT-4o-mini:**
```python
LLM(
    model="gpt-4o-mini",
    temperature=0.3,
    base_url="https://api.openai.com/v1",
    api_key=settings.openai_api_key,
)
```

---

## Comparison: OpenAI vs Claude

### When to Use Claude
✅ **Better for:**
- Code generation and analysis
- Long context understanding (200K tokens)
- Following complex instructions
- Structured output
- Lower cost for similar performance

### When to Use OpenAI
✅ **Better for:**
- Function calling (more mature)
- JSON mode
- Integration with OpenAI ecosystem
- Vision tasks (GPT-4 Vision)

### Recommended Setup
**Use Claude as default**, with OpenAI as fallback:

```python
# In customer config (config/customers/eliza/config.yml)
model_config:
  default_provider: "anthropic"
  fallback_providers:
    - "openai"
    - "groq"
  models:
    default: "claude-3-5-sonnet-20241022"
    fast: "claude-3-5-haiku-20241022"
    powerful: "claude-3-opus-20240229"
```

---

## Troubleshooting

### Issue: "Invalid API Key" Error

**Check:**
```bash
# Verify the key is set in the container
docker exec docker-app-1 printenv | grep ANTHROPIC
```

**Fix:**
```bash
# Make sure .env file is in the right location
ls -la /Users/scottgay/Documents/Eliza/eliza-platform/.env

# Restart containers to pick up changes
docker compose -f docker/docker-compose.yml restart
```

### Issue: "Model Not Found" Error

**Check your model name:**
```bash
# Valid format: claude-3-5-sonnet-20241022
# Invalid: claude-3.5-sonnet (dots instead of hyphens)
```

### Issue: Rate Limiting

Claude has different rate limits:
- **Tier 1** (new accounts): 50 requests/min, 40K tokens/min
- **Tier 2** (after $5 spend): 1,000 requests/min, 80K tokens/min
- **Tier 3** (after $40 spend): 2,000 requests/min, 160K tokens/min
- **Tier 4** (after $400 spend): 4,000 requests/min, 400K tokens/min

---

## Next Steps

1. ✅ Get your Anthropic API key
2. ⏳ Add it to `.env` file
3. ⏳ Update `data_analysis_flow.py` (I can do this for you)
4. ⏳ Restart containers
5. ⏳ Test with production flow

**Want me to update the code for you now?**

---

## Additional Resources

- [Anthropic API Docs](https://docs.anthropic.com/)
- [LiteLLM Anthropic Provider Docs](https://docs.litellm.ai/docs/providers/anthropic)
- [Claude Model Pricing](https://www.anthropic.com/pricing)
- [Claude Prompt Engineering](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)

---

**Current Status:**
- ✅ Config supports Anthropic API key
- ✅ LiteLLM library installed
- ⏳ Need to add your API key
- ⏳ Need to update LLM initialization logic
- ⏳ Need to restart containers

