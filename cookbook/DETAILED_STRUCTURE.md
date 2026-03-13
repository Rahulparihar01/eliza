# CrewAI Enterprise Cookbook: Detailed Structure

## Overview

This cookbook demonstrates how to build enterprise-grade AI applications using CrewAI flows and agents, using the Eliza Platform as a real-world example.

---

## Section 1: Introduction

### 1.1 What is CrewAI?
- Agent orchestration framework for production AI systems
- Key concepts: Agents, Flows, Tasks, Tools
- Why CrewAI over alternatives?

### 1.2 Enterprise Requirements
- Scalability: Handle thousands of concurrent requests
- Reliability: Graceful failures and retries
- Observability: Comprehensive logging and monitoring
- Security: Multi-tenant isolation and RBAC
- Cost Management: Token usage tracking and optimization

### 1.3 Architecture Overview
```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│                    - User Interface                      │
│                    - SSE Event Stream                   │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/SSE
┌────────────────────▼────────────────────────────────────┐
│              FastAPI Application                        │
│              - REST API Endpoints                       │
│              - Request Validation                       │
│              - Authentication/Authorization            │
└────────────────────┬────────────────────────────────────┘
                     │ Celery Task Queue
┌────────────────────▼────────────────────────────────────┐
│            Celery Workers (Multiple)                    │
│            - Async Task Execution                        │
│            - CrewAI Flow Invocation                      │
│            - Database Session Management                 │
└────────────────────┬────────────────────────────────────┘
                     │ Flow Execution
┌────────────────────▼────────────────────────────────────┐
│            CrewAI Flows                                  │
│            - TalentIntelligenceFlow                      │
│            - TaskEnrichmentFlow                         │
│            - DataAnalysisFlow                           │
│            - MLEngineerMatchingFlow                     │
└────────────────────┬────────────────────────────────────┘
                     │ Tool Execution
┌────────────────────▼────────────────────────────────────┐
│            Custom Tools & Services                      │
│            - DocumentSearchTool                         │
│            - HRDatabaseTool                             │
│            - PersonSearchTool                           │
│            - External APIs (PDL, etc.)                  │
└────────────────────┬────────────────────────────────────┘
                     │ Data Access
┌────────────────────▼────────────────────────────────────┐
│            Data Layer                                    │
│            - PostgreSQL (Primary DB)                    │
│            - Elasticsearch (Search)                     │
│            - Neo4j (Graph DB)                          │
│            - Redis (Cache)                              │
└─────────────────────────────────────────────────────────┘
```

---

## Section 2: Core Architecture Patterns

### 2.1 Flow-Based Orchestration

**Pattern:** Multi-step workflows with state management

**Example:** Talent Intelligence Flow

```python
# src/flows/talent_intelligence_flow.py

class TalentIntelligenceFlow(Flow[TalentAnalysisState]):
    """Orchestrates talent analysis through multiple stages"""
    
    @start()
    def analyze_job(self):
        """Step 1: Extract requirements from job description"""
        # Agent execution...
        self.state.ideal_persona = extracted_persona
    
    @listen(analyze_job)
    def search_applicants(self):
        """Step 2: Search internal applicants"""
        # Agent execution...
        self.state.applicant_results = scored_applicants
    
    @listen(search_applicants)
    def search_market_candidates(self):
        """Step 3: Search external market"""
        # Agent execution...
        self.state.market_results = scored_market_candidates
    
    @listen(search_market_candidates)
    def combine_and_rank(self):
        """Step 4: Combine and rank top candidates"""
        # Merge results...
        self.state.top_overall = ranked_candidates
```

**Key Points:**
- Use `@start()` for initial step
- Use `@listen()` for subsequent steps
- State is automatically managed by Flow
- Each step can have multiple agents

**Best Practices:**
- Keep state models serializable (no database sessions)
- Use Pydantic models for type safety
- Make steps idempotent when possible

### 2.2 Agent Specialization

**Pattern:** Create focused agents with specific roles and tools

**Example:** Task Enrichment Flow Agents

```python
# src/crewai_flows/task_enrichment_flow.py

class TaskEnrichmentFlow(Flow[TaskEnrichmentFlowState]):
    
    def _create_intent_analyzer(self) -> Agent:
        """Agent specialized in understanding user intent"""
        return Agent(
            role="Intent Analysis Specialist",
            goal="Analyze user requests to determine intent and complexity",
            backstory="Expert at understanding user intentions...",
            llm=self.llm,
            verbose=True
        )
    
    def _create_context_enricher(self) -> Agent:
        """Agent specialized in enriching context"""
        return Agent(
            role="Context Enrichment Specialist",
            goal="Add relevant business context to user queries",
            backstory="Expert at contextualizing information...",
            tools=[self.document_search_tool, self.hr_database_tool],
            llm=self.llm,
            verbose=True
        )
```

**Key Points:**
- Each agent has a clear, focused role
- Tools are assigned based on agent needs
- Backstory shapes agent behavior
- LLM configuration can be per-agent

**Best Practices:**
- Keep agents focused on single responsibilities
- Use descriptive roles and goals
- Provide rich backstories for better behavior
- Reuse agents across flows when possible

### 2.3 State Management

**Pattern:** Serializable state models for flow persistence

**Example:** State Model Definition

```python
# src/flows/ml_engineer_matching_flow.py

class MLEngineerMatchingState(BaseModel):
    """State maintained throughout the matching flow"""
    # Input
    session_id: str
    customer_id: str
    job_description: str
    
    # Intermediate results
    ideal_profile: Optional[Dict[str, Any]] = None
    internal_candidates_scored: Optional[List[Dict]] = None
    external_candidates_scored: Optional[List[Dict]] = None
    
    # Final results
    final_matches: Optional[Dict] = None
    
    # Performance tracking
    start_time: datetime = datetime.now()
    total_cost_usd: float = 0.0
```

**CRITICAL RULE:** Never store database sessions in state!

```python
# ❌ BAD: Storing session in state
class FlowState(BaseModel):
    db_session: Session  # This will cause pickle errors!

# ✅ GOOD: Store only IDs, create sessions locally
class FlowState(BaseModel):
    session_id: int  # Only store the ID

# Create sessions locally in methods:
def my_method(self):
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    try:
        # Use db here
        pass
    finally:
        db.close()
```

### 2.4 Tool Integration

**Pattern:** Custom tools connecting agents to external systems

**Example:** Document Search Tool

```python
# src/crewai_custom_tools/document_search_tool.py

class DocumentSearchTool(BaseTool):
    """CrewAI tool for semantic document search"""
    
    name: str = "Document Semantic Search"
    description: str = "Search company documents for relevant information"
    
    customer_id: str = Field(description="Customer ID for data isolation")
    company_hr_dataset: Optional[str] = Field(None, description="Target company")
    limit: int = Field(default=10, description="Max results")
    
    def _run(self, query: str) -> str:
        """Execute semantic search"""
        # Initialize vector service
        vector_service = VectorService()
        
        # Perform search
        results = await vector_service.search_similar_chunks(
            query=query,
            company_hr_dataset=self.company_hr_dataset,
            limit=self.limit
        )
        
        # Return formatted results
        return json.dumps([r.dict() for r in results])
```

**Key Points:**
- Tools extend `BaseTool` from CrewAI
- Use Pydantic `Field` for parameter validation
- Always handle errors gracefully
- Return JSON strings for agent consumption

**Best Practices:**
- Use `company_hr_dataset` for multi-tenant filtering (NOT `customer_id`)
- Provide clear descriptions for agents
- Handle async operations properly
- Log tool usage for monitoring

---

## Section 3: Integration Patterns

### 3.1 API Integration

**Pattern:** REST endpoints that queue async flows

**Example:** Talent Analysis API Endpoint

```python
# src/api/routes/talent.py

@router.post("/analyze-from-connector")
async def analyze_from_connector(
    request: TalentAnalysisRequest,
    current_user: User = Depends(get_current_user)
):
    """Queue talent analysis flow"""
    
    # Generate analysis ID
    analysis_id = f"ml_ta_{uuid.uuid4().hex[:10]}"
    
    # Create database record
    db = get_db()
    analysis = TalentAnalysis(
        analysis_id=analysis_id,
        customer_id=current_user.customer_id,
        status=TalentAnalysisStatus.PENDING.value
    )
    db.add(analysis)
    db.commit()
    
    # Queue Celery task
    task = run_talent_analysis_task.delay(
        customer_id=current_user.customer_id,
        analysis_id=analysis_id,
        job_description=request.job_description,
        ideal_candidate_description=request.ideal_candidate_description
    )
    
    # Return immediately
    return {
        "analysis_id": analysis_id,
        "status": "pending",
        "task_id": task.id
    }
```

**Key Points:**
- Return immediately with task ID
- Store initial state in database
- Use Celery for async execution
- Track status via database queries

### 3.2 Task Queue Integration

**Pattern:** Celery tasks wrapping CrewAI flows

**Example:** Celery Task Wrapper

```python
# src/tasks/talent_tasks.py

@celery_app.task(
    base=TalentAnalysisTask,
    bind=True,
    name="talent.run_analysis",
    max_retries=3,
    default_retry_delay=60
)
def run_talent_analysis_task(
    self,
    customer_id: str,
    analysis_id: str,
    job_description: Optional[str] = None,
    ...
):
    """Execute talent analysis flow"""
    
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()
    
    try:
        # Update status
        analysis = db.query(TalentAnalysis).filter(...).first()
        analysis.status = TalentAnalysisStatus.PROCESSING.value
        db.commit()
        
        # Create and run flow
        flow = TalentIntelligenceFlow(
            customer_id=customer_id,
            analysis_id=analysis_id
        )
        
        results = flow.run(
            job_description=job_description,
            ...
        )
        
        # Store results
        analysis.status = TalentAnalysisStatus.COMPLETED.value
        analysis.results = results
        db.commit()
        
    except Exception as e:
        # Handle errors
        analysis.status = TalentAnalysisStatus.FAILED.value
        analysis.error_message = str(e)
        db.commit()
        raise
    finally:
        db.close()
```

**Key Points:**
- Always initialize database in task
- Use try/finally for cleanup
- Update status throughout execution
- Handle retries properly

**Best Practices:**
- Set appropriate `max_retries` and `default_retry_delay`
- Use `bind=True` for task state access
- Log all state transitions
- Handle database session cleanup

### 3.3 Database Session Management

**Pattern:** Create sessions locally, never in state

**CRITICAL RULES:**

1. **Never store sessions in flow state**
```python
# ❌ BAD
class FlowState(BaseModel):
    db_session: Session  # Will cause pickle errors!

# ✅ GOOD
class FlowState(BaseModel):
    customer_id: str
    analysis_id: str
```

2. **Always check and initialize SessionLocal**
```python
# ✅ GOOD: Check and initialize before use
from src.models import database

if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()
try:
    # Use db
    pass
finally:
    db.close()
```

3. **Use module imports for global variables**
```python
# ✅ GOOD: Module import maintains reference
from src.models import database

if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()

# ❌ BAD: Direct import creates local binding
from src.models.database import SessionLocal  # May not update!
```

### 3.4 Event-Driven Architecture

**Pattern:** SSE for real-time progress updates

**Example:** Event Logging

```python
# src/tasks/talent_tasks.py

def _log_event(
    db: Session,
    analysis_id: str,
    event_type: str,
    message: str,
    progress_percentage: int,
    data: Optional[Dict] = None
):
    """Log event for SSE streaming"""
    event = TalentAnalysisEvent(
        analysis_id=analysis_id,
        event_type=event_type,
        message=message,
        progress_percentage=progress_percentage,
        data=data or {}
    )
    db.add(event)
    db.commit()
```

**Frontend Integration:**
```typescript
// frontend/src/hooks/useTalentAnalysis.ts

const eventSource = new EventSource(
  `/api/v1/ml-talent/analyses/${analysisId}/events`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  setProgress(data.progress_percentage);
  setStatus(data.event_type);
  addEvent(data);
};
```

---

## Section 4: Containerization and Deployment

### 4.1 Docker Architecture

**Pattern:** Multi-container setup with clear separation

```yaml
# docker/docker-compose.yml

services:
  app:
    build: .
    ports:
      - "5001:5001"
    environment:
      - RUN_MIGRATIONS=true  # Only app runs migrations
    depends_on:
      - postgres
      - redis
  
  celery-worker:
    build: .
    command: celery -A src.celery_app worker --loglevel=info
    environment:
      # No RUN_MIGRATIONS - skips migrations
    depends_on:
      - postgres
      - redis
      - app
  
  celery-beat:
    build: .
    command: celery -A src.celery_app beat --loglevel=info
    depends_on:
      - redis
  
  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
  
  elasticsearch:
    image: elasticsearch:8.11.0
  
  neo4j:
    image: neo4j:5.15.0
```

**Key Points:**
- Separate containers for app, workers, and infrastructure
- Only one container runs migrations (`RUN_MIGRATIONS=true`)
- Use volumes for persistent data
- Configure health checks

**Best Practices:**
- Rebuild containers after code changes: `docker-compose build --no-cache`
- Use environment variables for configuration
- Separate concerns: app handles HTTP, workers handle tasks
- Use health checks for orchestration

### 4.2 Environment Configuration

**Pattern:** Environment-specific settings with validation

```python
# src/core/config.py

class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # LLM Configuration
    default_llm_model: str = Field(default="gpt-4o-mini", env="DEFAULT_LLM_MODEL")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_api_base_url: str = Field(..., env="OPENAI_API_BASE_URL")
    
    # Celery
    celery_broker_url: str = Field(..., env="CELERY_BROKER_URL")
    
    # List-type vars use Union for flexibility
    allowed_origins: List[str] | str = Field(
        default=["*"], 
        env="ALLOWED_ORIGINS"
    )
```

**Key Points:**
- Use Pydantic Settings for validation
- Use `List[str] | str` for comma-separated env vars
- Provide defaults where appropriate
- Validate required fields

---

## Section 5: Scalability Strategies

### 5.1 Horizontal Scaling

**Pattern:** Multiple worker instances processing tasks

```yaml
# Scale workers
docker-compose up -d --scale celery-worker=4
```

**Key Points:**
- Celery automatically distributes tasks
- Each worker processes tasks independently
- Use queue priorities for important tasks
- Monitor worker health

### 5.2 Queue Management

**Pattern:** Separate queues for different task types

```python
# src/celery_app.py

celery_app.conf.task_routes = {
    'talent.run_analysis': {'queue': 'talent'},
    'process_bi_question': {'queue': 'bi'},
    'default': {'queue': 'default'}
}
```

**Best Practices:**
- Separate queues by priority/type
- Use dedicated workers for critical queues
- Monitor queue depth
- Set appropriate task timeouts

---

## Section 6: Monitoring and Observability

### 6.1 Structured Logging

**Pattern:** Consistent logging format across all components

```python
# src/core/logging.py

logger.info(
    "talent_analysis_starting",
    analysis_id=analysis_id,
    customer_id=customer_id,
    task_id=task_id,
    extra={
        "component": "talent_flow",
        "operation": "analyze_job"
    }
)
```

**Key Points:**
- Use structured logging (JSON)
- Include context: IDs, timestamps, user info
- Log at state transitions
- Use consistent log levels

### 6.2 Metrics Collection

**Pattern:** Track performance and costs

```python
# Track metrics in flow
class TalentIntelligenceFlow(Flow[TalentAnalysisState]):
    def __init__(self):
        self.start_time = datetime.now()
        self.token_count = 0
        self.cost_usd = 0.0
    
    def analyze_job(self):
        result = crew.kickoff()
        # Track metrics
        self.token_count += result.usage.total_tokens
        self.cost_usd += calculate_cost(result.usage)
```

**Metrics to Track:**
- Token usage per agent
- Cost per flow execution
- Execution time per step
- Success/failure rates
- Queue depth and processing time

---

## Section 7: Agent Optimization

### 7.1 Prompt Engineering

**Pattern:** Clear, focused prompts with examples

```python
# Good prompt structure
task = Task(
    description=f"""
    Analyze the following job description and extract key requirements:
    
    Job Description:
    {job_description}
    
    Provide:
    1. Required skills (must-have vs nice-to-have)
    2. Experience requirements
    3. Education requirements
    4. Cultural fit indicators
    
    Return as JSON with these fields:
    - required_skills: List[str]
    - experience_years: int
    - education_level: str
    - culture_fit: List[str]
    """,
    expected_output="JSON object with extracted requirements",
    agent=self.job_analyst
)
```

**Best Practices:**
- Be specific about format
- Include examples when possible
- Use structured output expectations
- Iterate based on results

### 7.2 Model Selection

**Pattern:** Choose models based on task requirements

```python
# Use smaller models for simple tasks
simple_llm = LLM(
    model="gpt-4o-mini",  # Fast, cheap
    temperature=0.2
)

# Use larger models for complex reasoning
complex_llm = LLM(
    model="gpt-4o",  # More capable
    temperature=0.3
)
```

**Guidelines:**
- Use `gpt-4o-mini` for simple extraction/classification
- Use `gpt-4o` for complex reasoning/synthesis
- Adjust temperature based on need for creativity
- Track costs per model choice

---

## Section 8: Real-World Examples

### 8.1 Talent Intelligence Flow

**Complete flow with multiple stages:**

See `src/flows/talent_intelligence_flow.py` for full implementation.

**Key Features:**
- Multi-stage pipeline
- Dual search (internal + external)
- State management across steps
- Error handling and retries

### 8.2 Task Enrichment Flow

**Example of intent analysis and context enrichment:**

See `src/crewai_flows/task_enrichment_flow.py` for full implementation.

**Key Features:**
- Intent classification
- RAG-based context retrieval
- Prompt optimization
- Quality validation

---

## Section 9: Troubleshooting Guide

### Common Issues

1. **Database Session Errors**
   - Symptom: `ModuleNotFoundError` or pickle errors
   - Solution: Use module imports, create sessions locally

2. **Container Not Updating**
   - Symptom: Old code running after changes
   - Solution: Rebuild with `--no-cache`

3. **Flow State Not Persisting**
   - Symptom: State lost between steps
   - Solution: Ensure state model is serializable

4. **Tool Execution Failures**
   - Symptom: Agents can't use tools
   - Solution: Check tool initialization, verify async handling

---

## Section 10: Best Practices Summary

### Architecture
- ✅ Use flows for multi-step workflows
- ✅ Keep agents focused on single responsibilities
- ✅ Never store database sessions in state
- ✅ Use Pydantic models for type safety

### Integration
- ✅ Queue flows via Celery for async execution
- ✅ Return immediately from API endpoints
- ✅ Use SSE for real-time updates
- ✅ Handle errors gracefully with retries

### Deployment
- ✅ Separate app and worker containers
- ✅ Only one container runs migrations
- ✅ Use environment variables for config
- ✅ Rebuild containers after code changes

### Monitoring
- ✅ Log at state transitions
- ✅ Track token usage and costs
- ✅ Monitor queue depth
- ✅ Use structured logging

### Optimization
- ✅ Choose models based on task complexity
- ✅ Use focused prompts with examples
- ✅ Cache expensive operations
- ✅ Monitor and optimize token usage


