# CrewAI Development Rules

> **Purpose:** Rules and patterns for developing CrewAI-based AI agent systems in the Eliza Platform, covering flows, agents, tasks, tools, and Eliza-specific integration requirements.

---

## Quick Reference

```python
# ✅ CORRECT CrewAI Flow Pattern (Eliza Platform)
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional
from src.models import database

class MyFlowState(BaseModel):
    """State that persists across flow steps."""
    input_data: str
    result: Optional[str] = None
    # NEVER store database sessions or non-serializable objects!

class MyFlow(Flow[MyFlowState]):
    @start()
    def analyze_input(self):
        if database.SessionLocal is None:
            database.init_database()
        db = database.SessionLocal()
        try:
            self.state.result = "Analysis complete"
        finally:
            db.close()

    @listen(analyze_input)
    def process_results(self):
        return self.state.result
```

Scaffold a new flow with the CLI:

```bash
crewai create flow my_flow_name --skip_provider
```

---

## Overview

This skill covers rules and patterns for developing CrewAI-based AI agent systems in the Eliza Platform. It includes both general CrewAI best practices and Eliza-specific integration requirements.

**Primary Reference:** [CrewAI Documentation](https://docs.crewai.com/llms-full.txt)

### Core Principles

**Developer Profile:**
- Software Engineer specializing in GenAI and Python
- Expert on CrewAI
- Use Python 3 as the primary programming language
- Use type hints consistently

**Code Quality:**
- Optimize for readability over premature optimization
- Write modular code with separate files for models, services, and flows
- Follow PEP8 style guide
- Implement proper error handling and retry logic

**CrewAI Patterns:**
- Agents should have clear, single responsibilities
- Tasks should be atomic and well-defined
- Use delegation between agents when appropriate
- Prioritize classes over functions for better organization

---

## Critical Rules

### Rule 1: NEVER Store Database Sessions in Flow State

**Context:** Flow state is serialized/pickled between steps. SQLAlchemy sessions cannot be pickled.

```python
# ❌ WRONG: This will cause pickle errors
class FlowState(BaseModel):
    db_session: Session  # BREAKS SERIALIZATION!
    user_id: int

# ✅ CORRECT: Store IDs only, create sessions locally
class FlowState(BaseModel):
    user_id: int
    customer_id: str
```

### Rule 2: Use Module Imports for Database Access

**Context:** Direct imports create stale bindings. Module imports maintain live references.

```python
# ❌ WRONG: Direct import creates stale binding
from src.models.database import SessionLocal, init_database

if SessionLocal is None:
    init_database()
db = SessionLocal()  # Still None! Your local binding didn't update.

# ✅ CORRECT: Module import maintains live reference
from src.models import database

if database.SessionLocal is None:
    database.init_database()
db = database.SessionLocal()  # Works! References actual global.
```

### Rule 3: Always Check and Initialize SessionLocal

**Context:** `SessionLocal` starts as `None` and is only set when `init_database()` is called.

```python
# ✅ CORRECT: Always check before use
from src.models import database

class MyFlow(Flow[MyFlowState]):
    def my_method(self):
        if database.SessionLocal is None:
            database.init_database()

        db = database.SessionLocal()
        try:
            result = db.query(MyModel).filter(...).first()
        finally:
            db.close()  # ALWAYS close in finally block
```

### Rule 4: Import at Module Level, Not Inside Methods

**Context:** Dynamic imports inside async flow methods can fail due to execution context differences.

```python
# ✅ CORRECT: Import at top of file
from src.models import database
from src.services.my_service import MyService

class MyFlow(Flow[MyFlowState]):
    def my_method(self):
        if database.SessionLocal is None:
            database.init_database()
        db = database.SessionLocal()
        service = MyService(db)
        # ...

# ❌ WRONG: Dynamic import inside method
class MyFlow(Flow[MyFlowState]):
    def my_method(self):
        from src.models.database import SessionLocal  # May fail!
        db = SessionLocal()
```

### Rule 5: Rebuild Containers After Flow Changes

**Context:** `docker-compose restart` only restarts containers with old images. Code changes require a rebuild.

```bash
# ✅ CORRECT: Rebuild both app and celery-worker after changing flows/tools
docker-compose build app celery-worker
docker-compose up -d app celery-worker

# ❌ WRONG: Restart uses old image
docker-compose restart celery-worker
```

### Rule 6: Agent Modules MUST Use Langfuse Service

**Context:** Any file that instantiates `Agent(...)` (CrewAI or PydanticAI) must include Langfuse tracing for observability.

**Required:**
1. Use `get_langfuse_service()` in the module.
2. Create a root trace/span for the run.
3. Add stage spans for each major step.
4. Mark failures using `level="ERROR"` and `status_message`.
5. Keep root trace input/output clean and business-focused.

**Reference implementations:**
- `src/services/langfuse_service.py` (shared tracing API)
- `src/celery_app.py` (task lifecycle root traces)
- `src/flows/retrieval_flow.py` (flow spans + error highlighting)
- `src/tasks/retrieval_tasks.py` (task-level spans + failure events)

#### Naming Conventions (AgentMesh Pattern)

Use consistent, queryable names:
- Root trace name: `agentmesh` (for agentmesh retrieval-style runs)
- Flow spans: `retrieval.<stage>`
- Tool spans: `retrieval.execute.tool.<tool_name>`
- Task spans: `retrieval.task.<stage>`
- LLM spans: `retrieval.plan.llm`, `retrieval.evaluate.llm`, `retrieval.synthesize.llm`, etc.

#### Input/Output Hygiene

- Root trace input should be the user query string, not raw Celery args/kwargs blobs.
- Root output should be concise:
  - success: `{"run_id": "...", "status": "completed"}`
  - failure: `{"status": "failed", "error": "..."}`
- Detailed diagnostic payloads belong to stage spans, not root traces.

#### Error Surfacing Rules

When a stage fails or partially fails:
- update span with `level="ERROR"`
- set `status_message` with clear reason
- include compact failure details in `output` (`failed_tool_count`, `failed_tools`, etc.)

This makes failures obvious in Langfuse UI and API.

#### Example: Root Trace + Stage Spans in a Flow

```python
from src.services.langfuse_service import get_langfuse_service

langfuse_service = get_langfuse_service()
trace_context = {"component": "agentmesh", "flow": "retrieval", "run_id": run_id}

root_scope = (
    langfuse_service.span_scope(name="retrieval.flow", input_data=query, metadata=trace_context)
    if langfuse_service.current_trace_id
    else langfuse_service.trace_scope(
        name="agentmesh",
        input_data=query,  # clean user input
        metadata=trace_context,
        session_id=conversation_id or run_id,
        user_id=str(user_id),
    )
)

with root_scope as flow_span:
    with langfuse_service.span_scope(
        name="retrieval.plan",
        input_data={"query": query},
        metadata={**trace_context, "stage": "planning"},
    ) as planning_span:
        plan = _plan(...)
        if not plan:
            planning_span["observation"].update(
                output={"plan_step_count": 0},
                level="ERROR",
                status_message="Planner returned no executable tool calls",
            )
```

#### Example: Celery Lifecycle Root Trace

```python
langfuse_service = get_langfuse_service()
trace_handle = langfuse_service.begin_trace_scope(
    name="agentmesh",
    input_data=query,  # clean root input
    metadata={"task_id": task_id, "task_name": "run_retrieval"},
    session_id=run_id,
    user_id=str(user_id),
)

langfuse_service.end_trace_scope(
    trace_handle,
    output_data={"run_id": run_id, "status": "completed"},
)
```

#### Example: Tool Failure Highlighting

```python
observation.update(
    output={
        "tool_name": tool_name,
        "failed_tool_count": 1,
        "failed_tools": [error_message],
    },
    level="ERROR",
    status_message=error_message or "Tool call failed",
)
```

#### Where to View Traces

- Local Langfuse UI: `http://localhost:3060`
- Filter by `trace.name = agentmesh` and/or `sessionId = run_id`.

#### Guardrail Check (Required Before PR)

```bash
python scripts/validate_feature.py --check agents
```

This fails if any agent-bearing module lacks Langfuse service wiring or trace calls.

---

## Patterns

### Sequential Flow

```python
from crewai.flow.flow import Flow, start, listen

class SequentialFlow(Flow[MyState]):
    @start()
    def step_one(self):
        self.state.step_one_result = "First step complete"

    @listen(step_one)
    def step_two(self):
        self.state.step_two_result = "Second step complete"

    @listen(step_two)
    def step_three(self):
        return self.state.final_result
```

### Parallel Execution

```python
from crewai.flow.flow import Flow, start, listen, and_

class ParallelFlow(Flow[MyState]):
    @start()
    def kickoff(self):
        pass

    @listen(kickoff)
    def parallel_a(self):
        self.state.result_a = "A complete"

    @listen(kickoff)
    def parallel_b(self):
        self.state.result_b = "B complete"

    @listen(and_(parallel_a, parallel_b))
    def combine_results(self):
        return f"{self.state.result_a} + {self.state.result_b}"
```

### State Persistence

```python
from crewai.flow.flow import Flow, start, persist
from pydantic import BaseModel

class MyState(BaseModel):
    counter: int = 0
    results: list = []

class PersistentFlow(Flow[MyState]):
    @start()
    @persist  # State is saved after this method
    def increment(self):
        self.state.counter += 1
```

### What Can Be in State

| ✅ Safe to Store | ❌ Never Store |
|-----------------|---------------|
| Primitive types (str, int, float, bool) | Database sessions |
| Lists and dicts of primitives | File handles |
| Pydantic models | Network connections |
| IDs and references | Locks or mutexes |
| Serializable results | Lambda functions |

### Agent Definition (YAML)

```yaml
# config/agents.yaml
researcher:
  role: "Senior Research Analyst"
  goal: "Discover and analyze comprehensive data about {topic}"
  backstory: >
    You are a meticulous researcher with 15 years of experience
    in data analysis. You excel at finding patterns and insights
    that others miss.
  verbose: true  # Enable during development
  allow_delegation: false  # Only true when needed
  max_iter: 5
```

Follow the guide: [Crafting Effective Agents](https://docs.crewai.com/guides/agents/crafting-effective-agents)

Key principles:
- **Clear Role:** One sentence describing what the agent does
- **Specific Goal:** What the agent is trying to achieve
- **Rich Backstory:** Context that shapes the agent's behavior
- **Appropriate Tools:** Only tools the agent needs

### Task Creation (YAML)

```yaml
# config/tasks.yaml
research_task:
  description: >
    Research the topic '{topic}' and compile a comprehensive report
    including key findings, trends, and recommendations.
  expected_output: >
    A detailed report with:
    - Executive summary
    - Key findings (minimum 5)
    - Data sources cited
    - Recommendations
  agent: researcher
  context:
    - previous_analysis_task  # Use output from another task
```

Task best practices:
- Clear, actionable descriptions
- Specific expected output format
- Explicit agent assignment
- Use context from other tasks when needed
- Leverage Pydantic for structured outputs

### Using Built-in Tools

```python
from crewai_tools import SerperDevTool, WebsiteSearchTool
import os

search_tool = SerperDevTool(
    api_key=os.getenv("SERPER_API_KEY"),
    n_results=5
)
```

### Custom Tool Template

```python
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class MyCustomToolInput(BaseModel):
    """Input schema for MyCustomTool."""
    argument: str = Field(..., description="Description of the argument.")

class MyCustomTool(BaseTool):
    name: str = "Name of my tool"
    description: str = (
        "Clear description for what this tool is useful for. "
        "Your agent will need this information to use it."
    )
    args_schema: Type[BaseModel] = MyCustomToolInput

    def _run(self, argument: str) -> str:
        """Execute the tool logic."""
        return "Tool result"
```

### Eliza Platform Tool Pattern

```python
from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field
from src.models import database

class DocumentSearchInput(BaseModel):
    """Input for document search."""
    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, description="Max results")

class DocumentSearchTool(BaseTool):
    name: str = "document_search"
    description: str = "Search documents in the knowledge base"
    args_schema: Type[BaseModel] = DocumentSearchInput

    customer_id: str
    company_hr_dataset: str  # CRITICAL: Use for data filtering

    def __init__(self, customer_id: str, company_hr_dataset: str, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = customer_id
        self.company_hr_dataset = company_hr_dataset

    def _run(self, query: str, limit: int = 10) -> str:
        if database.SessionLocal is None:
            database.init_database()

        db = database.SessionLocal()
        try:
            results = self._search(db, query, self.company_hr_dataset, limit)
            return self._format_results(results)
        finally:
            db.close()
```

---

## Complete Template

```python
"""
CrewAI Flow with Database Access — Eliza Platform Pattern

Full template for a flow that reads/writes to the database,
creates agents with tools, and follows all Eliza Platform rules.
"""
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional
from src.models import database
from src.services.my_service import MyService

class MyFlowState(BaseModel):
    user_id: int
    customer_id: str
    result: Optional[str] = None
    # NEVER store db sessions here!

class MyFlow(Flow[MyFlowState]):
    @start()
    def analyze(self):
        if database.SessionLocal is None:
            database.init_database()

        db = database.SessionLocal()
        try:
            service = MyService(db)
            self.state.result = service.analyze(self.state.user_id)
        finally:
            db.close()

    @listen(analyze)
    def persist_results(self):
        if database.SessionLocal is None:
            database.init_database()

        db = database.SessionLocal()
        try:
            # Save results to database
            pass
        finally:
            db.close()
```

---

## File Locations

### Eliza Platform Flows

```
src/
└── flows/
    ├── data_analyst_flow.py
    ├── ml_engineer_matching_flow.py
    └── talent_intelligence_flow.py
```

### Eliza Platform Tools

```
src/
└── crewai_custom_tools/
    ├── __init__.py
    ├── document_search_tool.py
    ├── hr_database_tool.py
    ├── person_search_tools.py
    └── talent_matching_tools.py
```

### Standard CrewAI Crew Structure

```
my_crew/
├── .gitignore
├── knowledge/            # Knowledge base files (pdfs, docs, etc.)
├── pyproject.toml
├── README.md
├── .env                  # Environment variables (never commit!)
├── tests/
└── src/
    └── my_crew/
        ├── main.py       # Entry point
        ├── crew.py       # Crew definition using CrewBase
        ├── tools/
        │   └── custom_tool.py
        └── config/
            ├── agents.yaml
            └── tasks.yaml
```

### Standard CrewAI Flow Structure

```
my_flow/
├── .gitignore
├── pyproject.toml
├── README.md
├── .env
├── tests/
└── src/
    └── my_flow/
        ├── main.py       # Entry point and flow methods
        ├── crews/        # Crews used in the flow
        │   └── poem_crew/
        │       ├── config/
        │       │   ├── agents.yaml
        │       │   └── tasks.yaml
        │       └── poem_crew.py
        └── tools/
            └── custom_tool.py
```

---

## Testing

### Unit Testing Agents

```python
def test_agent_creation():
    agent = create_research_agent()
    assert agent.role == "Senior Research Analyst"
    assert agent.max_iter == 5
```

### Integration Testing Crews

```python
def test_crew_execution():
    crew = create_test_crew()
    result = crew.kickoff(inputs={"topic": "test"})
    assert result is not None
    assert "summary" in result
```

### Testing Flows with Database

```python
from src.models import database

def test_flow_with_db():
    database.init_database()

    state = MyFlowState(user_id=1, customer_id="test")

    flow = MyFlow()
    result = flow.kickoff(state)

    assert result is not None
```

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Storing sessions in state | Store IDs, create sessions locally |
| Direct imports of SessionLocal | Use module imports (`from src.models import database`) |
| Forgetting to close database | Use `try/finally` pattern |
| Not rebuilding containers | Always `docker-compose build` after changes |
| Overly complex prompts | Keep agent instructions clear and focused |
| Unexpected LLM responses | Implement validation and retry logic |
| Rate limits from LLM providers | Add exponential backoff |
| Long-running tasks blocking flow | Use Celery tasks for background processing |
| State serialization failures | Check for non-serializable objects |

### Debugging Strategies

```python
# Enable verbose mode during development
agent = Agent(
    role="Researcher",
    verbose=True,  # Shows agent thinking
)

# Add logging to flows
import logging
logger = logging.getLogger(__name__)

class MyFlow(Flow[MyState]):
    @start()
    def analyze(self):
        logger.info(f"Starting analysis for user {self.state.user_id}")
        # ...
```

---

## Checklist

- [ ] Flow state contains only serializable types (no sessions, no file handles)
- [ ] Database access uses module import pattern (`from src.models import database`)
- [ ] `SessionLocal` is checked and initialized before use
- [ ] All database sessions closed in `finally` blocks
- [ ] Imports at module level, not inside methods
- [ ] Agent modules include Langfuse tracing
- [ ] Langfuse guardrail check passes: `python scripts/validate_feature.py --check agents`
- [ ] Container rebuilt: `docker-compose build app celery-worker`

---

## References

### Eliza Platform
- `src/flows/*.py` — Existing flow implementations
- `src/crewai_custom_tools/*.py` — Existing tool implementations
- `src/services/langfuse_service.py` — Shared tracing API
- `cookbook/COOKBOOK.md` — CrewAI development cookbook
- `.cursorrules` — Critical development rules

### Dependencies

Check latest versions on [PyPi](https://pypi.org/project/crewai/):

```txt
crewai>=0.186.1
crewai-tools>=0.71.0
```

### CrewAI Documentation
- [CrewAI Docs](https://docs.crewai.com)
- [Crafting Effective Agents](https://docs.crewai.com/guides/agents/crafting-effective-agents)
- [Full LLM Reference](https://docs.crewai.com/llms-full.txt)
