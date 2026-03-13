# Section 9: Troubleshooting Guide

## Overview

This section covers common issues you'll encounter when building CrewAI applications and how to resolve them. Each issue includes symptoms, root causes, and solutions.

## Issue 1: Database Session Pickle Errors

### Symptoms

```
TypeError: cannot pickle 'sqlalchemy.orm.session.Session' object
PicklingError: Can't pickle <class 'sqlalchemy.orm.session.Session'>
```

### Root Cause

Storing SQLAlchemy sessions in flow state causes pickle errors when Celery tries to serialize task state.

### Solution

**Never store sessions in flow state:**

```python
# ❌ BAD: Session in state
class FlowState(BaseModel):
    db_session: Session  # Causes pickle errors!

# ✅ GOOD: Store only IDs
class FlowState(BaseModel):
    customer_id: str
    analysis_id: str
    # No sessions!

# Create sessions locally in methods
def my_method(self):
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    try:
        # Use db
        pass
    finally:
        db.close()
```

### Prevention

- Always use Pydantic models for state
- Never include non-serializable objects (sessions, file handles, clients)
- Create database sessions locally in each method that needs them

## Issue 2: SessionLocal is None

### Symptoms

```
AttributeError: 'NoneType' object has no attribute 'SessionLocal'
TypeError: 'NoneType' object is not callable
```

### Root Cause

Database not initialized before use, or using direct import instead of module import.

### Solution

**Always check and initialize:**

```python
# ✅ GOOD: Check and initialize
from src.models import database  # Module import!

if database.SessionLocal is None:
    database.init_database()

db = database.SessionLocal()

# ❌ BAD: Direct import creates local binding
from src.models.database import SessionLocal  # May not update!
```

### Prevention

- Always use module imports: `from src.models import database`
- Check `if database.SessionLocal is None` before use
- Call `database.init_database()` if needed

## Issue 3: Module Import Doesn't Update

### Symptoms

- `SessionLocal` remains `None` even after `init_database()` is called
- Database initialization appears to work but sessions still fail

### Root Cause

Direct import (`from module import variable`) creates a local binding that doesn't update when the global variable changes.

### Solution

**Use module imports:**

```python
# ✅ GOOD: Module import maintains reference
from src.models import database

if database.SessionLocal is None:
    database.init_database()  # Sets database.SessionLocal = sessionmaker(...)

db = database.SessionLocal()  # ✅ Works! References actual global

# ❌ BAD: Direct import creates local binding
from src.models.database import SessionLocal, init_database

# At import time, SessionLocal is None
# This creates: SessionLocal = None (local binding)

if SessionLocal is None:
    init_database()  # Sets database.SessionLocal = sessionmaker(...)
    # But YOUR local SessionLocal is still None!

db = SessionLocal()  # ❌ FAILS! Local binding is still None
```

### Prevention

- Always use module imports for global variables
- Use `from src.models import database` not `from src.models.database import SessionLocal`
- Understand Python's import binding behavior

## Issue 4: Container Not Updating After Code Changes

### Symptoms

- Code changes don't appear in running container
- Old behavior persists after making changes
- Logs show old code executing

### Root Cause

Docker containers use cached images. `docker-compose restart` doesn't rebuild images.

### Solution

**Rebuild containers after code changes:**

```bash
# ✅ GOOD: Rebuild after changes
docker-compose build celery-worker
docker-compose up -d celery-worker

# Or rebuild all
docker-compose build --no-cache
docker-compose up -d

# ❌ BAD: Restart uses old image
docker-compose restart celery-worker  # Uses cached image!
```

### Prevention

- Always rebuild after code changes
- Use `--no-cache` when troubleshooting
- Verify code in container: `docker exec -it container_name cat /app/src/my_file.py`

## Issue 5: Multiple Containers Running Migrations

### Symptoms

- Migration race conditions
- Database locks
- Inconsistent schema state

### Root Cause

Multiple containers trying to run migrations simultaneously.

### Solution

**Only one container should run migrations:**

```yaml
# ✅ GOOD: Only app runs migrations
app:
  environment:
    - RUN_MIGRATIONS=true  # Only app

celery-worker:
  environment:
    - RUN_MIGRATIONS=false  # Workers skip migrations

# ❌ BAD: Both run migrations
app:
  environment:
    - RUN_MIGRATIONS=true

celery-worker:
  environment:
    - RUN_MIGRATIONS=true  # Race condition!
```

### Prevention

- Set `RUN_MIGRATIONS=true` only on app container
- Set `RUN_MIGRATIONS=false` on all worker containers
- Use health checks to ensure migrations complete before starting workers

## Issue 6: Flow State Not Persisting

### Symptoms

- State lost between flow steps
- Intermediate results disappear
- Flow restarts from beginning

### Root Cause

State model not properly serializable or state not being updated correctly.

### Solution

**Ensure state is serializable:**

```python
# ✅ GOOD: Serializable state
class FlowState(BaseModel):
    customer_id: str
    analysis_id: str
    step1_result: Optional[Dict[str, Any]] = None
    # All fields are JSON-serializable

# ❌ BAD: Non-serializable state
class FlowState(BaseModel):
    db_session: Session  # Not serializable!
    file_handle: File    # Not serializable!
```

**Update state correctly:**

```python
# ✅ GOOD: Update state properly
self.state.step1_result = {"data": "value"}

# State persists automatically between steps
```

### Prevention

- Use only JSON-serializable types in state
- Use Pydantic models for validation
- Avoid storing complex objects (sessions, files, clients)

## Issue 7: Agent Not Using Tools

### Symptoms

- Agent doesn't call tools
- Tool execution errors
- Agent ignores tool descriptions

### Root Cause

Tools not properly initialized or assigned to agent.

### Solution

**Initialize tools correctly:**

```python
# ✅ GOOD: Initialize tool with required parameters
self.document_tool = DocumentSearchTool(
    customer_id=self.customer_id,
    company_hr_dataset=self.company_id,
    limit=10
)

# Assign to agent
agent = Agent(
    role="Search Specialist",
    tools=[self.document_tool],  # Agent can use tool
    llm=self.llm
)

# ❌ BAD: Tool not initialized or not assigned
agent = Agent(
    role="Search Specialist",
    # Missing tools parameter!
    llm=self.llm
)
```

**Ensure tool description is clear:**

```python
# ✅ GOOD: Clear tool description
class DocumentSearchTool(BaseTool):
    name: str = "Document Semantic Search"
    description: str = """
    ALWAYS USE THIS TOOL to search company documents.
    
    Performs semantic search and returns relevant chunks.
    """
```

### Prevention

- Always assign tools to agents that need them
- Provide clear, descriptive tool descriptions
- Initialize tools with required parameters
- Test tools independently before using in agents

## Issue 8: Wrong Filtering Field in Tools

### Symptoms

- Documents from other companies not appearing
- Cross-company searches returning no results
- Data isolation issues

### Root Cause

Using `customer_id` for data filtering instead of `company_hr_dataset`.

### Solution

**Use company_hr_dataset for filtering:**

```python
# ✅ GOOD: Use company_hr_dataset
results = await vector_service.search_similar_chunks(
    query=query,
    company_hr_dataset=self.company_hr_dataset,  # Correct!
    limit=self.limit
)

# ❌ BAD: Using customer_id filters out cross-company docs
results = await vector_service.search_similar_chunks(
    query=query,
    customer_id=self.customer_id,  # Wrong!
    limit=self.limit
)
```

### Prevention

- Understand difference: `customer_id` = ownership, `company_hr_dataset` = data filtering
- Always use `company_hr_dataset` for searches
- Use `customer_id` only for audit/ownership tracking

## Issue 9: List-Type Environment Variable Parsing Errors

### Symptoms

```
SettingsError: error parsing value for field "allowed_origins"
ValueError: Invalid JSON format
```

### Root Cause

Strict `List[str]` type doesn't accept comma-separated strings from `.env` files.

### Solution

**Use Union type:**

```python
# ✅ GOOD: Union type accepts both formats
class Settings(BaseSettings):
    allowed_origins: List[str] | str = Field(
        default=["*"],
        env="ALLOWED_ORIGINS"
    )

# Convert in application code
allowed_origins = settings.allowed_origins
if isinstance(allowed_origins, str):
    allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]

# ❌ BAD: Strict List type causes parsing errors
class Settings(BaseSettings):
    allowed_origins: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    # Fails when .env has: ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5001
```

### Prevention

- Use `List[str] | str` for list-type environment variables
- Handle conversion in application code
- Test with both comma-separated and JSON array formats

## Issue 10: Flow Steps Not Executing in Order

### Symptoms

- Steps execute out of order
- Steps run before dependencies complete
- Race conditions

### Root Cause

Incorrect use of `@listen()` decorator or missing dependencies.

### Solution

**Use @listen() correctly:**

```python
# ✅ GOOD: Correct dependency chain
class MyFlow(Flow[MyFlowState]):
    @start()
    def first_step(self):
        # Runs first
        pass
    
    @listen(first_step)  # Waits for first_step
    def second_step(self):
        # Runs after first_step completes
        pass
    
    @listen(second_step)  # Waits for second_step
    def third_step(self):
        # Runs after second_step completes
        pass

# ❌ BAD: Missing dependencies
class MyFlow(Flow[MyFlowState]):
    @start()
    def first_step(self):
        pass
    
    @listen(first_step)
    def second_step(self):
        pass
    
    def third_step(self):  # Missing @listen()!
        # May run before second_step completes
        pass
```

### Prevention

- Always use `@listen()` for dependent steps
- Chain dependencies correctly
- Use `@start()` only for initial step

## Issue 11: Celery Task Not Picking Up Flow

### Symptoms

- Task queued but not executing
- Worker idle but tasks pending
- No errors in logs

### Root Cause

Task not registered, worker not listening to correct queue, or import errors.

### Solution

**Ensure task is registered:**

```python
# ✅ GOOD: Import task to register it
from src.tasks.talent_tasks import run_talent_analysis_task
# Task is now registered with Celery

# Check registered tasks
celery -A src.celery_app inspect registered
```

**Ensure worker listens to correct queue:**

```bash
# ✅ GOOD: Worker listens to correct queue
celery -A src.celery_app worker --queues=talent

# ❌ BAD: Worker listening to wrong queue
celery -A src.celery_app worker --queues=default  # Tasks go to 'talent' queue!
```

### Prevention

- Import tasks to register them
- Verify task registration: `celery inspect registered`
- Ensure workers listen to correct queues
- Check for import errors in task modules

## Issue 12: Token Usage Higher Than Expected

### Symptoms

- High API costs
- Slower execution times
- Token limits exceeded

### Root Cause

Verbose prompts, unnecessary context, or inefficient agent usage.

### Solution

**Optimize prompts:**

```python
# ✅ GOOD: Concise prompt
task = Task(
    description=f"""
    Extract from: {input}
    Fields: skills, experience
    Format: JSON
    """,
    agent=agent
)

# ❌ BAD: Verbose prompt
task = Task(
    description=f"""
    Please carefully analyze the following information...
    [200 words of instructions]
    {input}
    [More verbose instructions]
    """
)
```

**Use appropriate models:**

```python
# ✅ GOOD: Use mini for simple tasks
agent = Agent(
    role="Extractor",
    llm=LLM(model="gpt-4o-mini")  # Fast, cheap
)

# ❌ BAD: Using large model for simple tasks
agent = Agent(
    role="Extractor",
    llm=LLM(model="gpt-4o")  # Expensive!
)
```

### Prevention

- Keep prompts concise but complete
- Use `gpt-4o-mini` for simple tasks
- Cache expensive operations
- Monitor token usage

## Debugging Checklist

When troubleshooting issues:

1. **Check Logs**
   ```bash
   docker-compose logs celery-worker --tail=100
   docker-compose logs app --tail=100
   ```

2. **Verify Database Connection**
   ```bash
   docker exec -it docker-postgres-1 psql -U user -d ai_enablement -c "SELECT 1;"
   ```

3. **Check Celery Status**
   ```bash
   celery -A src.celery_app inspect active
   celery -A src.celery_app inspect stats
   ```

4. **Verify Container Health**
   ```bash
   docker-compose ps
   curl http://localhost:5001/health/ready
   ```

5. **Check Queue Depths**
   ```bash
   redis-cli LLEN celery
   ```

6. **Verify Environment Variables**
   ```bash
   docker exec docker-app-1 env | grep DATABASE_URL
   ```

7. **Check Code in Container**
   ```bash
   docker exec docker-celery-worker-1 cat /app/src/flows/my_flow.py
   ```

## Summary

Common issues and solutions:

1. **Database Session Errors**: Never store sessions in state
2. **SessionLocal None**: Always check and initialize
3. **Module Import Issues**: Use module imports, not direct imports
4. **Container Updates**: Rebuild after code changes
5. **Migration Conflicts**: Only app container runs migrations
6. **State Persistence**: Ensure state is serializable
7. **Tool Issues**: Initialize and assign tools correctly
8. **Filtering Errors**: Use company_hr_dataset, not customer_id
9. **Config Parsing**: Use Union types for list env vars
10. **Flow Order**: Use @listen() for dependencies
11. **Task Execution**: Ensure tasks registered and queues match
12. **Token Usage**: Optimize prompts and use appropriate models

When in doubt, check logs, verify configuration, and ensure containers are rebuilt after changes.


