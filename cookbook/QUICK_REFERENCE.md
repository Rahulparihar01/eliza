# CrewAI Enterprise Cookbook - Quick Reference

## Critical Rules

### Database Session Management
```python
# ✅ ALWAYS: Create sessions locally, never in state
class FlowState(BaseModel):
    customer_id: str  # ✅ OK
    # db_session: Session  # ❌ NEVER!

# In methods:
if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()
try:
    # Use db
    pass
finally:
    db.close()
```

### Module Imports
```python
# ✅ GOOD: Module import maintains reference
from src.models import database

# ❌ BAD: Direct import creates local binding
from src.models.database import SessionLocal
```

### Container Updates
```bash
# ✅ ALWAYS: Rebuild after code changes
docker-compose build celery-worker
docker-compose up -d celery-worker

# ❌ NEVER: Restart without rebuild
docker-compose restart celery-worker  # Uses old image!
```

### Migration Control
```yaml
# ✅ ONLY app container runs migrations
app:
  environment:
    - RUN_MIGRATIONS=true

celery-worker:
  environment:
    - RUN_MIGRATIONS=false
```

## Common Patterns

### Flow Structure
```python
class MyFlow(Flow[MyFlowState]):
    @start()
    def first_step(self):
        # Initial step
        pass
    
    @listen(first_step)
    def second_step(self):
        # Depends on first_step
        pass
```

### Agent Creation
```python
agent = Agent(
    role="Specific Role",
    goal="Clear Goal",
    backstory="Detailed context...",
    tools=[relevant_tools],
    llm=self.llm
)
```

### API → Celery → Flow
```python
# API Endpoint
@router.post("/endpoint")
async def endpoint(request: Request):
    task = run_flow_task.delay(request.dict())
    return {"task_id": task.id}

# Celery Task
@celery_app.task(bind=True)
def run_flow_task(self, request_data: dict):
    flow = MyFlow()
    results = flow.kickoff(request_data)
    return results
```

### Tool Integration
```python
class MyTool(BaseTool):
    name: str = "Tool Name"
    description: str = "Clear description"
    customer_id: str = Field(...)
    
    def _run(self, query: str) -> str:
        # Tool logic
        return json.dumps(results)
```

## Architecture Layers

```
Frontend → API → Celery Queue → Workers → Flows → Agents → Tools → Data
```

## Key Files Reference

- **Flows**: `src/flows/`, `src/crewai_flows/`
- **Tasks**: `src/tasks/`
- **Tools**: `src/crewai_custom_tools/`
- **Config**: `src/core/config.py`
- **Database**: `src/models/database.py`
- **Docker**: `docker/docker-compose.yml`

## Common Issues Quick Fix

| Issue | Fix |
|-------|-----|
| Pickle error | Remove sessions from state |
| SessionLocal None | Use module import, check before use |
| Container not updating | Rebuild with `docker-compose build` |
| Migrations fail | Only app container runs migrations |
| Tools not working | Initialize and assign to agent |
| Wrong data filtering | Use `company_hr_dataset`, not `customer_id` |

## Best Practices Checklist

- [ ] Use Pydantic models for flow state
- [ ] Never store non-serializable objects in state
- [ ] Create database sessions locally in methods
- [ ] Use module imports for global variables
- [ ] Rebuild containers after code changes
- [ ] Only app container runs migrations
- [ ] Use `company_hr_dataset` for data filtering
- [ ] Log at state transitions
- [ ] Handle errors gracefully with retries
- [ ] Use appropriate models for task complexity
- [ ] Keep prompts concise but complete
- [ ] Cache expensive operations

## Flow Examples

### Talent Intelligence Flow
- Multi-stage candidate analysis
- API → Celery → Flow execution
- State management across steps

### Task Enrichment Flow
- Question transformation pipeline
- Intent analysis → Context enrichment → Prompt generation
- Integrated with BI question processing

### ML Engineer Matching Flow
- Multi-source candidate matching
- Profile synthesis → Pattern analysis → Search → Ranking
- Sophisticated agent orchestration

## Monitoring

- **Logging**: Structured JSON logs with context
- **Metrics**: Token usage, costs, performance
- **Errors**: Capture and track for analysis
- **Tracing**: Correlate logs across services

## Optimization

- **Prompts**: Clear, structured, concise
- **Models**: Match to task complexity
- **Tokens**: Minimize usage, cache results
- **Tools**: Cache expensive operations

## Scaling

- **Horizontal**: Add more worker instances
- **Queues**: Separate by priority/type
- **Resources**: Set appropriate limits
- **Auto-scaling**: Adjust based on load

For detailed explanations, see the individual section documents.


