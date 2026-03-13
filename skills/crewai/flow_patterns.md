# CrewAI Flow Patterns

> **Purpose:** Common patterns for implementing CrewAI flows in the Eliza Platform, including sequential processing, parallel execution, database integration, SSE streaming, error recovery, agent integration, and Langfuse observability.

---

## Quick Reference

```python
# ✅ CORRECT Sequential Flow Pattern
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional

class AnalysisState(BaseModel):
    input_data: str
    analysis_result: Optional[str] = None
    final_report: Optional[str] = None

class SequentialAnalysisFlow(Flow[AnalysisState]):
    @start()
    def parse_input(self):
        self.state.analysis_result = f"Analysis of: {self.state.input_data}"

    @listen(parse_input)
    def generate_report(self):
        self.state.final_report = f"Report: {self.state.analysis_result}"
        return self.state.final_report
```

---

## Overview

This skill catalogs the flow patterns used across the Eliza Platform. Each pattern solves a specific orchestration need. Choose the right pattern based on your use case.

| Pattern | Use Case | Example |
|---------|----------|---------|
| [Sequential Analysis](#sequential-analysis) | Multi-step data processing | Talent Intelligence Flow |
| [Parallel Execution](#parallel-execution) | Independent parallel tasks | Market + Resume analysis |
| [Database-Integrated Flow](#database-integrated-flow) | Flows needing persistence | BI Question answering |
| [SSE Event Emission](#sse-event-emission) | Real-time progress updates | Analysis progress |
| [Error Recovery](#error-recovery-flow) | Graceful failure handling | Retry with fallback |
| [Agent-Integrated Flow](#agent-integrated-flow) | CrewAI agents inside flows | Research + analysis agents |
| [Langfuse Observability](#langfuse-observability-pattern-agentmesh) | Traceability for agent runs | `agentmesh` + `retrieval.*` spans |

---

## Critical Rules

### Rule 1: Never Store Database Sessions in Flow State

**Context:** Flow state is serialized/pickled between steps. SQLAlchemy sessions cannot be pickled.

```python
# ❌ WRONG: Session in state breaks serialization
class DBFlowState(BaseModel):
    db: Session  # BREAKS!
    analysis_id: int

# ✅ CORRECT: Store only IDs, use helper to get sessions
class DBFlowState(BaseModel):
    analysis_id: int
    customer_id: str
    status: str = "pending"
    result: Optional[str] = None
```

### Rule 2: Use the `_get_db()` Helper Pattern

**Context:** Multiple flow steps need database access. A helper method centralizes session initialization and avoids duplication.

```python
# ❌ WRONG: Duplicating session init logic in every step
class MyFlow(Flow[MyState]):
    @start()
    def step_one(self):
        if database.SessionLocal is None:
            database.init_database()
        db = database.SessionLocal()
        # ...

# ✅ CORRECT: Centralized helper
class MyFlow(Flow[MyState]):
    def _get_db(self):
        if database.SessionLocal is None:
            database.init_database()
        return database.SessionLocal()

    @start()
    def step_one(self):
        db = self._get_db()
        try:
            # ...
        finally:
            db.close()
```

### Rule 3: Always Close Sessions in `finally` Blocks

**Context:** Unclosed sessions leak database connections and cause pool exhaustion.

```python
# ❌ WRONG: Session not closed on exception
db = self._get_db()
result = db.query(Analysis).first()
db.close()  # Never reached if query throws!

# ✅ CORRECT: Guaranteed cleanup
db = self._get_db()
try:
    result = db.query(Analysis).first()
finally:
    db.close()
```

### Rule 4: Filter by `customer_id` for Multi-Tenancy

**Context:** Database-integrated flows must scope all queries to the current tenant to prevent data leakage.

```python
# ❌ WRONG: No tenant filtering
analysis = db.query(Analysis).filter(
    Analysis.id == self.state.analysis_id
).first()

# ✅ CORRECT: Always include customer_id filter
analysis = db.query(Analysis).filter(
    Analysis.id == self.state.analysis_id,
    Analysis.customer_id == self.state.customer_id
).first()
```

---

## Patterns

### Sequential Analysis

Multi-step processing where each step depends on the previous.

```python
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional, List

class AnalysisState(BaseModel):
    input_data: str
    parsed_data: Optional[dict] = None
    analysis_result: Optional[str] = None
    final_report: Optional[str] = None

class SequentialAnalysisFlow(Flow[AnalysisState]):

    @start()
    def parse_input(self):
        """Step 1: Parse and validate input data."""
        self.state.parsed_data = {
            "content": self.state.input_data,
            "metadata": {"processed": True}
        }

    @listen(parse_input)
    def analyze_data(self):
        """Step 2: Run analysis on parsed data."""
        self.state.analysis_result = f"Analysis of: {self.state.parsed_data['content']}"

    @listen(analyze_data)
    def generate_report(self):
        """Step 3: Generate final report."""
        self.state.final_report = f"Report: {self.state.analysis_result}"
        return self.state.final_report
```

**Real Example:** `src/flows/talent_intelligence_flow.py`

### Parallel Execution

Run independent tasks simultaneously, then combine results.

```python
from crewai.flow.flow import Flow, start, listen, and_
from pydantic import BaseModel
from typing import Optional

class ParallelState(BaseModel):
    query: str
    market_data: Optional[dict] = None
    internal_data: Optional[dict] = None
    combined_result: Optional[str] = None

class ParallelAnalysisFlow(Flow[ParallelState]):

    @start()
    def initialize(self):
        """Kick off parallel branches."""
        pass

    @listen(initialize)
    def fetch_market_data(self):
        """Branch A: Fetch external market data."""
        self.state.market_data = {
            "source": "external",
            "results": ["data1", "data2"]
        }

    @listen(initialize)
    def fetch_internal_data(self):
        """Branch B: Query internal database."""
        self.state.internal_data = {
            "source": "internal",
            "results": ["record1", "record2"]
        }

    @listen(and_(fetch_market_data, fetch_internal_data))
    def combine_results(self):
        """Wait for both branches, then combine."""
        self.state.combined_result = {
            "market": self.state.market_data,
            "internal": self.state.internal_data
        }
        return self.state.combined_result
```

### Database-Integrated Flow

Flows that read/write to the database at various steps.

```python
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional
from src.models import database
from src.models.analysis import Analysis

class DBFlowState(BaseModel):
    analysis_id: int
    customer_id: str
    status: str = "pending"
    result: Optional[str] = None
    # NEVER store db session here!

class DatabaseIntegratedFlow(Flow[DBFlowState]):

    def _get_db(self):
        """Helper to get database session."""
        if database.SessionLocal is None:
            database.init_database()
        return database.SessionLocal()

    @start()
    def load_analysis(self):
        """Load analysis record from database."""
        db = self._get_db()
        try:
            analysis = db.query(Analysis).filter(
                Analysis.id == self.state.analysis_id,
                Analysis.customer_id == self.state.customer_id
            ).first()

            if not analysis:
                raise ValueError(f"Analysis {self.state.analysis_id} not found")

            self.state.status = "processing"
            analysis.status = "processing"
            db.commit()
        finally:
            db.close()

    @listen(load_analysis)
    def process_analysis(self):
        """Run the actual analysis logic."""
        self.state.result = "Analysis complete"
        self.state.status = "completed"

    @listen(process_analysis)
    def save_results(self):
        """Persist results to database."""
        db = self._get_db()
        try:
            analysis = db.query(Analysis).filter(
                Analysis.id == self.state.analysis_id
            ).first()

            analysis.result = self.state.result
            analysis.status = self.state.status
            db.commit()
        finally:
            db.close()

        return self.state.result
```

### SSE Event Emission

Real-time progress updates via Server-Sent Events.

```python
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional, Callable
import json

class SSEFlowState(BaseModel):
    task_id: str
    progress: int = 0
    status: str = "pending"
    result: Optional[str] = None

class SSEEnabledFlow(Flow[SSEFlowState]):

    def __init__(self, event_callback: Optional[Callable] = None):
        super().__init__()
        self.event_callback = event_callback

    def emit_event(self, event_type: str, data: dict):
        """Emit SSE event if callback is configured."""
        if self.event_callback:
            event = {
                "type": event_type,
                "task_id": self.state.task_id,
                "data": data
            }
            self.event_callback(json.dumps(event))

    @start()
    def step_one(self):
        self.state.status = "step_one"
        self.state.progress = 25
        self.emit_event("progress", {
            "step": "step_one",
            "progress": 25,
            "message": "Starting analysis..."
        })

    @listen(step_one)
    def step_two(self):
        self.state.status = "step_two"
        self.state.progress = 50
        self.emit_event("progress", {
            "step": "step_two",
            "progress": 50,
            "message": "Processing data..."
        })

    @listen(step_two)
    def step_three(self):
        self.state.status = "step_three"
        self.state.progress = 75
        self.emit_event("progress", {
            "step": "step_three",
            "progress": 75,
            "message": "Generating results..."
        })

    @listen(step_three)
    def complete(self):
        self.state.status = "completed"
        self.state.progress = 100
        self.state.result = "Final result"
        self.emit_event("complete", {
            "progress": 100,
            "result": self.state.result
        })
        return self.state.result
```

**Integration with Celery Task:**

```python
# In src/tasks/my_tasks.py
from src.celery_app import celery_app
from src.models import database

@celery_app.task(bind=True)
def run_analysis_with_sse(self, task_id: str, user_id: int, customer_id: str):
    """Celery task that runs flow with SSE events."""

    def emit_sse(event_json: str):
        # Store event in Redis for SSE endpoint to pick up
        # Or use your preferred event distribution mechanism
        pass

    state = SSEFlowState(task_id=task_id)
    flow = SSEEnabledFlow(event_callback=emit_sse)

    try:
        result = flow.kickoff(state)
        return {"status": "success", "result": result}
    except Exception as e:
        emit_sse(json.dumps({
            "type": "error",
            "task_id": task_id,
            "data": {"error": str(e)}
        }))
        raise
```

### Error Recovery Flow

Graceful handling of failures with retry and fallback logic.

```python
from crewai.flow.flow import Flow, start, listen, router
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class RecoveryState(BaseModel):
    input: str
    attempt: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    result: Optional[str] = None

class ErrorRecoveryFlow(Flow[RecoveryState]):

    @start()
    def attempt_process(self):
        """Try to process, may fail."""
        self.state.attempt += 1
        logger.info(f"Attempt {self.state.attempt} of {self.state.max_attempts}")

        try:
            # Simulated processing that might fail
            if self.state.attempt < 2:
                raise ValueError("Simulated failure")

            self.state.result = "Success!"
            self.state.error = None
        except Exception as e:
            self.state.error = str(e)
            logger.warning(f"Attempt {self.state.attempt} failed: {e}")

    @router(attempt_process)
    def route_result(self):
        """Route based on success/failure."""
        if self.state.result:
            return "success"
        elif self.state.attempt < self.state.max_attempts:
            return "retry"
        else:
            return "fallback"

    @listen("success")
    def handle_success(self):
        """Handle successful processing."""
        logger.info("Processing succeeded")
        return self.state.result

    @listen("retry")
    def handle_retry(self):
        """Retry the processing."""
        logger.info("Retrying...")
        return self.attempt_process()

    @listen("fallback")
    def handle_fallback(self):
        """Fallback when all retries exhausted."""
        logger.error(f"All attempts failed: {self.state.error}")
        return {"status": "failed", "error": self.state.error}
```

### Agent-Integrated Flow

Flow that uses CrewAI agents for specific steps.

```python
from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, start, listen
from pydantic import BaseModel
from typing import Optional

class AgentFlowState(BaseModel):
    topic: str
    research_result: Optional[str] = None
    analysis_result: Optional[str] = None

class AgentIntegratedFlow(Flow[AgentFlowState]):

    def _create_researcher(self) -> Agent:
        return Agent(
            role="Senior Researcher",
            goal=f"Research {self.state.topic} comprehensively",
            backstory="Expert researcher with 10 years experience",
            verbose=True
        )

    def _create_analyst(self) -> Agent:
        return Agent(
            role="Data Analyst",
            goal="Analyze research findings and extract insights",
            backstory="Expert at finding patterns in data",
            verbose=True
        )

    @start()
    def research_step(self):
        """Use agent to conduct research."""
        researcher = self._create_researcher()

        task = Task(
            description=f"Research the topic: {self.state.topic}",
            expected_output="Comprehensive research summary",
            agent=researcher
        )

        crew = Crew(agents=[researcher], tasks=[task])
        result = crew.kickoff()

        self.state.research_result = str(result)

    @listen(research_step)
    def analysis_step(self):
        """Use agent to analyze research."""
        analyst = self._create_analyst()

        task = Task(
            description=f"Analyze this research: {self.state.research_result}",
            expected_output="Key insights and recommendations",
            agent=analyst
        )

        crew = Crew(agents=[analyst], tasks=[task])
        result = crew.kickoff()

        self.state.analysis_result = str(result)
        return self.state.analysis_result
```

### Langfuse Observability Pattern (AgentMesh)

Use this for any flow that instantiates `Agent(...)` or orchestrates multi-stage LLM/tool execution.

**Goals:**
1. Make each run traceable end-to-end.
2. Keep root traces clean and user-centered.
3. Make partial failures obvious in Langfuse.

**Conventions (from current implementation):**
- Root trace name: `agentmesh`
- Flow spans: `retrieval.<stage>`
- Task spans: `retrieval.task.<stage>`
- Tool spans: `retrieval.execute.tool.<tool_name>`
- Errors: `level="ERROR"` + `status_message`

#### Flow Pattern

```python
from src.services.langfuse_service import get_langfuse_service

langfuse_service = get_langfuse_service()
trace_context = {"component": "agentmesh", "flow": "retrieval", "run_id": run_id}

root_scope = (
    langfuse_service.span_scope(name="retrieval.flow", input_data=query, metadata=trace_context)
    if langfuse_service.current_trace_id
    else langfuse_service.trace_scope(
        name="agentmesh",
        input_data=query,  # root input = user query
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
    ):
        plan = _plan(...)
```

#### Error Highlighting Pattern

```python
observation.update(
    output={"failed_tool_count": len(failures), "failed_tools": failures[:10]},
    level="ERROR",
    status_message=f"{len(failures)} tool call(s) failed during run",
)
```

#### Root Output Hygiene

For root task lifecycle traces, keep output concise:

```python
langfuse_service.end_trace_scope(
    trace_handle,
    output_data={"run_id": run_id, "status": "completed"},
)
```

Avoid large framework/internal payloads for root input/output.

#### File References

- `src/services/langfuse_service.py`
- `src/celery_app.py`
- `src/flows/retrieval_flow.py`
- `src/tasks/retrieval_tasks.py`

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Storing database session in flow state | Store only IDs; use `_get_db()` helper per step |
| Forgetting `finally: db.close()` | Always wrap DB access in `try/finally` |
| Missing `customer_id` filter in DB queries | Add tenant filter to all queries for multi-tenancy |
| SSE events not reaching frontend | Verify Redis pub/sub or event distribution mechanism is wired |
| Router returning unknown route name | Ensure `@listen` labels match all possible `@router` return values |
| Large payloads in Langfuse root trace | Keep root input/output concise; use stage spans for details |
| Agent flow missing Langfuse tracing | Add `get_langfuse_service()` and trace/span scopes per Rule 6 |

---

## Checklist

- [ ] Flow state contains only serializable types (no sessions, no file handles)
- [ ] Database access uses `_get_db()` helper with `try/finally` cleanup
- [ ] All DB queries include `customer_id` tenant filter
- [ ] SSE flows emit progress events at each major step
- [ ] Error recovery flows handle all router branches (`success`, `retry`, `fallback`)
- [ ] Agent-integrated flows include Langfuse tracing
- [ ] Root Langfuse trace input is user query, not raw kwargs
- [ ] Container rebuilt: `docker-compose build app celery-worker`

---

## References

- `src/flows/talent_intelligence_flow.py` — Production sequential flow example
- `src/flows/data_analyst_flow.py` — Database-integrated flow
- `src/flows/retrieval_flow.py` — AgentMesh tracing and error spans example
- `src/tasks/retrieval_tasks.py` — Task-level span instrumentation example
- `src/services/langfuse_service.py` — Shared tracing API
- `skills/crewai/CREWAI_DEVELOPMENT_RULES.md` — Core development rules
- `cookbook/02_CORE_ARCHITECTURE_PATTERNS.md` — Architecture patterns
