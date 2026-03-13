# Agent Configuration System - Testing Guide

**Feature Branch:** `feature/agent-configuration-system`  
**Version:** 1.0  
**Last Updated:** January 8, 2025

---

## Overview

This guide provides comprehensive testing procedures for the Agent Configuration System. The system is **100% complete** and ready for testing.

**Status:** ✅ **All Phases Complete**

---

## Pre-Test Setup

### 1. Rebuild Containers

The migration needs to run and code changes need to be deployed:

```bash
# Stop all containers
docker-compose down

# Rebuild app and celery-worker (both use agent config)
docker-compose build --no-cache app celery-worker

# Rebuild frontend
docker-compose build --no-cache frontend

# Start all services
docker-compose up -d

# Verify migration ran
docker-compose logs app | grep "Running upgrade.*016_add_agent_configurations"

# Verify containers are healthy
docker-compose ps
```

### 2. Verify Database Schema

```bash
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
  SELECT table_name, column_name, data_type 
  FROM information_schema.columns 
  WHERE table_name IN ('agent_configurations', 'customer_ai_providers') 
  ORDER BY table_name, ordinal_position;
"
```

**Expected:** 
- `agent_configurations` table exists with all columns
- `customer_ai_providers.name` column exists

### 3. Configure at Least One Provider

Before testing agents, ensure you have at least one enabled AI provider configured:

```bash
# Check existing providers
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5001/v1/providers/configurations
```

If you don't have any, create one:

```bash
# Example: Create OpenAI provider
curl -X POST http://localhost:5001/v1/providers/configurations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "openai",
    "name": "OpenAI Production",
    "api_key": "sk-...",
    "models": ["gpt-3.5-turbo", "gpt-4"],
    "is_enabled": true,
    "priority": 1
  }'
```

---

## Phase 1: API Endpoint Testing

### Test 1.1: List Flows

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5001/v1/agents/flows
```

**Expected Response:**
```json
[
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
```

**✅ Success Criteria:**
- Returns 2 flows
- Each has identifier, name, agent_count

---

### Test 1.2: List Agents in Flow

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5001/v1/agents/flows/data_analysis_flow/agents
```

**Expected Response:**
```json
[
  {
    "agent_identifier": "data_retrieval_agent",
    "agent_name": "Data Retrieval Specialist",
    "current_model": "gpt-3.5-turbo",
    "current_provider": "OpenAI Production"
  },
  {
    "agent_identifier": "bi_analyst_agent",
    "agent_name": "Business Intelligence Analyst",
    "current_model": "gpt-4",
    "current_provider": "OpenAI Production"
  }
]
```

**✅ Success Criteria:**
- Returns 2 agents for data_analysis_flow
- Each has identifier, name, current model, current provider
- Displays code defaults if no override exists

---

### Test 1.3: Get Agent Configuration (Defaults)

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5001/v1/agents/configurations/data_analysis_flow/data_retrieval_agent
```

**Expected Response:**
```json
{
  "customer_id": "eliza",
  "flow_identifier": "data_analysis_flow",
  "agent_identifier": "data_retrieval_agent",
  "role": "Data Retrieval Specialist",
  "goal": "Retrieve relevant data from HR database and document embeddings",
  "backstory": "You are an expert at finding...",
  "model_id": "gpt-3.5-turbo",
  "provider_config_id": 1,
  "provider_name": "OpenAI Production",
  "temperature": 0.3,
  "max_tokens": 2000,
  "enabled_tools": ["hr_database", "document_search"],
  "is_enabled": true,
  "version": 1,
  "source": "default"
}
```

**✅ Success Criteria:**
- Returns complete configuration
- `source` is "default" (no override yet)
- Provider auto-selected based on model + priority

---

### Test 1.4: Update Agent Configuration

```bash
curl -X PUT http://localhost:5001/v1/agents/configurations/data_analysis_flow/data_retrieval_agent \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "gpt-4",
    "temperature": 0.5,
    "role": "Senior Data Retrieval Specialist",
    "max_tokens": 3000
  }'
```

**Expected Response:**
```json
{
  "customer_id": "eliza",
  "flow_identifier": "data_analysis_flow",
  "agent_identifier": "data_retrieval_agent",
  "role": "Senior Data Retrieval Specialist",  // Updated
  "model_id": "gpt-4",                         // Updated
  "temperature": 0.5,                          // Updated
  "max_tokens": 3000,                          // Updated
  "source": "override",                        // Changed!
  "version": 2                                 // Incremented!
}
```

**✅ Success Criteria:**
- Fields updated successfully
- `source` changed to "override"
- `version` incremented
- Returns merged config (DB override + code defaults)

---

### Test 1.5: Verify Database Override

```bash
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "
  SELECT 
    agent_identifier,
    model_id,
    temperature,
    max_tokens,
    version,
    updated_by,
    source
  FROM agent_configurations
  WHERE flow_identifier = 'data_analysis_flow'
    AND agent_identifier = 'data_retrieval_agent';
"
```

**Expected:**
```
agent_identifier       | model_id | temperature | max_tokens | version | updated_by | source
-----------------------|----------|-------------|------------|---------|------------|----------
data_retrieval_agent   | gpt-4    | 0.5         | 3000       | 2       | ui         | override
```

**✅ Success Criteria:**
- Record exists in database
- Values match what was sent in PUT request
- `updated_by` is "ui"

---

### Test 1.6: Get Configuration (Now Shows Override)

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5001/v1/agents/configurations/data_analysis_flow/data_retrieval_agent
```

**Expected:**
- `source` is now "override"
- `version` is 2
- Updated fields show new values
- Non-updated fields show code defaults

---

### Test 1.7: Reset to Defaults

```bash
curl -X DELETE http://localhost:5001/v1/agents/configurations/data_analysis_flow/data_retrieval_agent \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected:** HTTP 204 No Content

**✅ Success Criteria:**
- Returns 204
- Database record deleted

Verify reset:
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:5001/v1/agents/configurations/data_analysis_flow/data_retrieval_agent
```

**Expected:**
- `source` is "default" again
- `version` is 1
- All values back to code defaults

---

## Phase 2: Flow Execution Testing

### Test 2.1: Verify Agent Uses Default Config

1. **Reset agent to defaults** (if not already):
   ```bash
   curl -X DELETE ... /data_analysis_flow/data_retrieval_agent
   ```

2. **Submit a BI question** via UI or API:
   ```bash
   curl -X POST http://localhost:5001/v1/bi/questions \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "How many employees work in engineering?",
       "company_hr_dataset": "caylent"
     }'
   ```

3. **Check celery logs** for agent config loading:
   ```bash
   docker-compose logs celery-worker --tail=100 | grep "Loaded config for data_retrieval_agent"
   ```

**Expected Log:**
```
Loaded config for data_retrieval_agent: model=gpt-3.5-turbo, provider=OpenAI Production, source=default
```

4. **Check agent creation log:**
   ```bash
   docker-compose logs celery-worker --tail=100 | grep "Built OpenAI LLM"
   ```

**Expected Log:**
```
Built OpenAI LLM for data_retrieval_agent: model=gpt-3.5-turbo, provider=OpenAI Production, temperature=0.3, source=default
```

**✅ Success Criteria:**
- Agent loads config from database at runtime
- Logs show "source=default"
- Question executes successfully

---

### Test 2.2: Update Config and Verify Immediate Effect

1. **Update agent config:**
   ```bash
   curl -X PUT ... -d '{"model_id": "gpt-4", "temperature": 0.7}'
   ```

2. **Submit ANOTHER BI question** (immediately, no restart):
   ```bash
   curl -X POST http://localhost:5001/v1/bi/questions \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "question": "What is the average tenure of engineers?",
       "company_hr_dataset": "caylent"
     }'
   ```

3. **Check logs again:**
   ```bash
   docker-compose logs celery-worker --tail=100 | grep "Loaded config for data_retrieval_agent"
   ```

**Expected Log:**
```
Loaded config for data_retrieval_agent: model=gpt-4, provider=OpenAI Production, source=override
```

**✅ Success Criteria:**
- **NO RESTART NEEDED!**
- New execution uses updated config
- Logs show "source=override" and "model=gpt-4"
- Temperature is 0.7 (check in LLM build log)

---

### Test 2.3: Verify Cache Works

1. **Submit TWO questions quickly** (within 60 seconds):

2. **Check logs:**
   ```bash
   docker-compose logs celery-worker --tail=200 | grep -E "(Loaded config|Cache hit)"
   ```

**Expected:**
- First execution: "Resolving agent config for..."
- Second execution: "Cache hit for eliza:data_analysis_flow:data_retrieval_agent"

**✅ Success Criteria:**
- Cache reduces database queries
- Second execution faster (no DB lookup)

---

### Test 2.4: Verify Cache Invalidation

1. **Submit a question**, wait for it to start

2. **While it's running**, update the agent config

3. **Submit another question** (after first completes)

4. **Check logs:**
   ```bash
   docker-compose logs celery-worker --tail=300 | grep -E "(Invalidated cache|Resolving agent config)"
   ```

**Expected:**
- Log shows "Invalidated cache for eliza:data_analysis_flow:data_retrieval_agent"
- Second question loads fresh config from DB
- New config applied immediately

**✅ Success Criteria:**
- Cache invalidated on update
- Next execution uses new config

---

## Phase 3: Frontend UI Testing

### Test 3.1: Navigate to Agent Configuration

1. **Login** to the frontend: http://localhost:3000

2. **Navigate** to "Agent Configuration" in the left sidebar (Administration section)

**✅ Success Criteria:**
- Menu item visible (requires `agents:write` or `system:admin` permission)
- Page loads at `/admin/agents`
- No console errors

---

### Test 3.2: View Flows and Agents

1. **Verify flows list** (left pane)
   - Should show "Data Analysis Flow" and "Task Enrichment Flow"

2. **Click** "Data Analysis Flow"

3. **Verify agents list** (left pane)
   - Should show 2 agents:
     - Data Retrieval Specialist
     - Business Intelligence Analyst
   - Each shows current model and provider

**✅ Success Criteria:**
- Both panes load correctly
- Agent count matches (2 agents per flow)
- Current model/provider displayed

---

### Test 3.3: View Agent Configuration

1. **Click** "Data Retrieval Specialist"

2. **Verify configuration form** (center pane)
   - Role, goal, backstory fields populated
   - Provider dropdown populated from API
   - Model ID shows current value
   - Temperature and max_tokens show current values
   - Badge shows "Default" or "Custom"
   - Version number displayed

**✅ Success Criteria:**
- All fields populated correctly
- Provider dropdown has options
- No errors in console

---

### Test 3.4: Update Configuration

1. **Change model** from "gpt-3.5-turbo" to "gpt-4"

2. **Verify**:
   - "Unsaved changes" indicator appears
   - Save button becomes enabled

3. **Click "Save Changes"**

4. **Verify**:
   - Save button shows "Saving..."
   - Success (badge changes to "Custom", version increments)
   - Agent list updates to show "gpt-4"

**✅ Success Criteria:**
- Update successful
- UI reflects changes immediately
- Version incremented

---

### Test 3.5: Test Immediate Effect in Execution

1. **Navigate** to Business Intelligence page

2. **Submit a question**

3. **Check execution timeline** (right pane)
   - Look for agent execution details

4. **Verify** the agent used "gpt-4" (the model you just configured)

**✅ Success Criteria:**
- Execution uses updated config
- NO RESTART needed
- Timeline shows correct model

---

### Test 3.6: Reset to Defaults

1. **Navigate back** to Agent Configuration

2. **Select** the agent you modified

3. **Click "Reset to Defaults"**

4. **Confirm** dialog

5. **Verify**:
   - Badge changes back to "Default"
   - Model reverts to "gpt-3.5-turbo"
   - Version resets to 1
   - Agent list shows original model

**✅ Success Criteria:**
- Reset successful
- All fields show defaults
- Database record deleted (verified via SQL query)

---

## Phase 4: Provider Resolution Testing

### Test 4.1: Auto-Selection (Single Provider)

**Scenario:** You have ONE provider that supports "gpt-4"

1. **Update agent** without specifying provider:
   ```bash
   curl -X PUT ... -d '{"model_id": "gpt-4"}'
   ```

2. **Expected:**
   - Agent automatically uses the only provider that supports gpt-4
   - `provider_config_id` and `provider_name` set automatically

**✅ Success Criteria:**
- Provider auto-selected
- Config saved with provider_config_id

---

### Test 4.2: Auto-Selection (Multiple Providers)

**Scenario:** You have TWO providers that support "gpt-3.5-turbo" with different priorities

1. **Create second provider:**
   ```bash
   curl -X POST .../v1/providers/configurations \
     -d '{
       "provider_type": "openai",
       "name": "OpenAI Backup",
       "models": ["gpt-3.5-turbo"],
       "priority": 5
     }'
   ```

2. **Update agent** (no provider specified):
   ```bash
   curl -X PUT ... -d '{"model_id": "gpt-3.5-turbo"}'
   ```

3. **Expected:**
   - Selects provider with LOWER priority number (higher priority)
   - Check logs: "Auto-selected provider 'OpenAI Production' (priority=1)"

**✅ Success Criteria:**
- Highest priority provider selected
- Logged correctly

---

### Test 4.3: Manual Selection by ID

```bash
curl -X PUT ... -d '{"model_id": "gpt-4", "provider_config_id": 2}'
```

**✅ Success Criteria:**
- Uses explicitly specified provider (ID=2)
- Even if another provider has higher priority

---

### Test 4.4: Manual Selection by Name

```bash
curl -X PUT ... -d '{"model_id": "gpt-4", "provider_name": "OpenAI Backup"}'
```

**✅ Success Criteria:**
- Looks up provider by name
- Uses that provider's ID
- Saved correctly in database

---

## Phase 5: Error Handling Testing

### Test 5.1: Invalid Model

```bash
curl -X PUT ... -d '{"model_id": "invalid-model-999"}'
```

**Expected:** HTTP 400 Bad Request
```json
{
  "error": "...",
  "message": "No enabled provider found that supports model 'invalid-model-999'"
}
```

**✅ Success Criteria:**
- Clear error message
- No database change

---

### Test 5.2: Invalid Provider ID

```bash
curl -X PUT ... -d '{"provider_config_id": 9999}'
```

**Expected:** HTTP 400 Bad Request
```json
{
  "error": "...",
  "message": "Provider config 9999 not found"
}
```

**✅ Success Criteria:**
- Validation before database write
- Helpful error message

---

### Test 5.3: Model Not Available in Provider

```bash
curl -X PUT ... -d '{"model_id": "claude-3-opus-20240229", "provider_config_id": 1}'
```

(Assuming provider 1 is OpenAI and doesn't have Claude models)

**Expected:** HTTP 400 Bad Request
```json
{
  "error": "...",
  "message": "Model claude-3-opus-20240229 not available in provider 'OpenAI Production'. Available models: gpt-3.5-turbo, gpt-4"
}
```

**✅ Success Criteria:**
- Validation checks provider's available models
- Lists what IS available

---

## Phase 6: Programmatic Update Testing

### Test 6.1: Update via Service Layer

Create a test script:

```python
# test_agent_config_programmatic.py
from src.models import database
from src.services.agent_configuration_service import AgentConfigurationService

if database.SessionLocal is None:
    database.init_database()

db = database.SessionLocal()
try:
    service = AgentConfigurationService(db)
    
    # Update via service (not UI)
    config = service.set_agent_config(
        customer_id="eliza",
        flow_identifier="data_analysis_flow",
        agent_identifier="bi_analyst_agent",
        config={
            "model_id": "gpt-4",
            "temperature": 0.8
        },
        updated_by="script",
        user_id=None
    )
    
    print(f"✅ Updated: {config.agent_identifier}")
    print(f"   Model: {config.model_id}")
    print(f"   Temperature: {config.temperature}")
    print(f"   Updated by: {config.updated_by}")
    print(f"   Version: {config.version}")
    
finally:
    db.close()
```

Run:
```bash
docker exec docker-app-1 python test_agent_config_programmatic.py
```

**✅ Success Criteria:**
- Update successful
- `updated_by` is "script" (not "ui")
- Next execution uses new config

---

## Phase 7: Audit Trail Testing

### Test 7.1: Verify Version Tracking

1. **Check initial version:**
   ```sql
   SELECT version, updated_by FROM agent_configurations 
   WHERE agent_identifier = 'data_retrieval_agent';
   ```
   Expected: `version=1, updated_by=NULL` (default)

2. **Update via UI**

3. **Check version:**
   Expected: `version=2, updated_by='ui'`

4. **Update via API**

5. **Check version:**
   Expected: `version=3, updated_by='api'`

**✅ Success Criteria:**
- Version increments on each update
- `updated_by` tracks source

---

### Test 7.2: Verify `updated_by_user_id`

Update via UI (authenticated as user):

```sql
SELECT updated_by_user_id FROM agent_configurations 
WHERE agent_identifier = 'data_retrieval_agent';
```

**✅ Success Criteria:**
- `updated_by_user_id` matches current user's ID

---

## Final Verification Checklist

### Backend ✅
- [ ] All API endpoints work
- [ ] Database tables created
- [ ] Migrations ran successfully
- [ ] Service layer functions correctly
- [ ] Provider resolution works (3 methods)
- [ ] Cache works and invalidates

### Flow Integration ✅
- [ ] Flows load config at runtime
- [ ] LLMs built from config
- [ ] Execution uses correct model
- [ ] Updates apply immediately (no restart)
- [ ] Logs show config source

### Frontend ✅
- [ ] Page loads without errors
- [ ] Flows and agents list correctly
- [ ] Configuration form works
- [ ] Save updates database
- [ ] Reset works
- [ ] Provider dropdown populated
- [ ] UI reflects changes immediately

### End-to-End ✅
- [ ] UI update → Database → Flow execution
- [ ] Zero state mismatch
- [ ] Immediate effect (no restart)
- [ ] Multiple API keys supported
- [ ] User-friendly names displayed
- [ ] Audit trail complete

---

## Troubleshooting

### Issue: "No enabled provider found"

**Solution:**
1. Check provider configurations: `GET /v1/providers/configurations`
2. Ensure at least one provider is `is_enabled: true`
3. Verify provider's `models` list includes the model you're trying to use

### Issue: Agent still using old config

**Solution:**
1. Check cache TTL hasn't expired yet (60s)
2. Verify database was actually updated (SQL query)
3. Check celery logs for cache invalidation message
4. Restart celery worker if cache seems stuck

### Issue: Frontend doesn't show changes

**Solution:**
1. Hard refresh browser (Ctrl+Shift+R / Cmd+Shift+R)
2. Check browser console for API errors
3. Verify API responses in Network tab
4. Check authentication token is valid

### Issue: Migration didn't run

**Solution:**
```bash
# Check migration status
docker exec docker-app-1 alembic current

# Run migrations manually
docker exec docker-app-1 alembic upgrade head

# Verify table exists
docker exec docker-postgres-1 psql -U user -d ai_enablement -c "\dt agent_configurations"
```

---

## Performance Benchmarks

### Expected Performance

**API Response Times:**
- List flows: < 50ms
- List agents: < 100ms
- Get config (cache miss): < 200ms
- Get config (cache hit): < 10ms
- Update config: < 300ms

**Flow Execution:**
- Config load (cache miss): < 200ms
- Config load (cache hit): < 10ms
- LLM build: < 50ms

**Cache Effectiveness:**
- Hit rate: > 80% (assuming typical usage)
- TTL: 60 seconds

---

## Success Metrics

### Functional
- ✅ All API endpoints return expected data
- ✅ Database updates persist correctly
- ✅ Flows execute with runtime config
- ✅ UI reflects all changes immediately
- ✅ No restart required for updates

### Non-Functional
- ✅ Response times < 300ms
- ✅ Zero state mismatches
- ✅ Complete audit trail
- ✅ Cache reduces DB load
- ✅ Error messages are helpful

---

**Testing Status:** Ready for execution  
**Last Updated:** January 8, 2025  
**Feature Branch:** `feature/agent-configuration-system`

