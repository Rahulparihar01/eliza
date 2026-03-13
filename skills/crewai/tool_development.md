# CrewAI Tool Development

> **Purpose:** Guidelines for building custom CrewAI tools in the Eliza Platform, covering database access, document search, external APIs, structured output, and execution tracking.

---

## Quick Reference

```python
# ✅ CORRECT Basic Tool Pattern
from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field

class MyToolInput(BaseModel):
    """Input schema - agents see these descriptions."""
    query: str = Field(..., description="The search query to execute")
    limit: int = Field(default=10, description="Maximum results to return")

class MyCustomTool(BaseTool):
    name: str = "my_tool_name"
    description: str = (
        "Clear description of what this tool does. "
        "Agents use this to decide when to use the tool. "
        "Be specific about inputs and outputs."
    )
    args_schema: Type[BaseModel] = MyToolInput

    def _run(self, query: str, limit: int = 10) -> str:
        """Execute the tool. Return string result."""
        return f"Results for: {query}"
```

---

## Overview

Tools extend agent capabilities by providing access to:
- External APIs (search, enrichment, etc.)
- Internal databases and services
- Document retrieval and search
- Data transformation and analysis

All custom tools inherit from `crewai.tools.BaseTool` and must implement `_run()`. Tools should return string results for agent consumption and follow database session rules from `CREWAI_DEVELOPMENT_RULES.md`.

---

## Critical Rules

### Rule 1: Create Database Sessions Inside `_run()`, Not in `__init__()`

**Context:** Storing a database session on the tool instance risks stale connections. Sessions must be created fresh per invocation and closed in a `finally` block.

```python
# ❌ WRONG: Session stored on tool instance
class MyTool(BaseTool):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db = database.SessionLocal()  # Stale session!

    def _run(self, query: str) -> str:
        return self.db.query(...)  # May fail

# ✅ CORRECT: Session created and closed inside _run()
class MyTool(BaseTool):
    def _run(self, query: str) -> str:
        if database.SessionLocal is None:
            database.init_database()
        db = database.SessionLocal()
        try:
            return db.query(...)
        finally:
            db.close()
```

### Rule 2: Use `company_hr_dataset` for Document Search Filtering

**Context:** Documents have both `customer_id` (who owns it) and `company_hr_dataset` (what company it's about). Searches must filter by `company_hr_dataset` to return the correct results.

```python
# ❌ WRONG: Filtering by customer_id returns wrong tenant's data
results = vector_service.search_similar_chunks(
    query=query,
    customer_id=self.customer_id,
    limit=limit
)

# ✅ CORRECT: Filter by company_hr_dataset for data filtering
results = vector_service.search_similar_chunks(
    query=query,
    company_hr_dataset=self.company_hr_dataset,
    limit=limit,
    similarity_threshold=self.similarity_threshold
)
```

### Rule 3: Access Pydantic Model Attributes Directly

**Context:** Search results are `DocumentSearchResult` Pydantic models. Using `.get()` (dict method) on them raises `AttributeError`.

```python
# ❌ WRONG: Using .get() on Pydantic models
for result in results:
    doc_name = result.get("document_name")  # AttributeError!
    full_text = result.get("text")          # Won't work!

# ✅ CORRECT: Access Pydantic model attributes directly
for result in results:
    doc_name = result.document_filename
    full_text = result.text
    score = result.similarity_score
```

### Rule 4: Rebuild BOTH Containers After Tool Changes

**Context:** Both `app` and `celery-worker` containers use the same tools. Code changes must be deployed to both.

```bash
# ❌ WRONG: Only rebuilding one container
docker-compose build celery-worker
docker-compose up -d celery-worker

# ✅ CORRECT: Rebuild both containers
docker-compose build app celery-worker
docker-compose up -d app celery-worker
```

---

## Patterns

### Tool with Database Access

```python
from crewai.tools import BaseTool
from typing import Type, Optional, List
from pydantic import BaseModel, Field
from src.models import database

class DatabaseToolInput(BaseModel):
    """Input for database query tool."""
    entity_id: int = Field(..., description="ID of the entity to fetch")

class DatabaseQueryTool(BaseTool):
    name: str = "database_query"
    description: str = "Query the database for entity information"
    args_schema: Type[BaseModel] = DatabaseToolInput

    customer_id: str

    def __init__(self, customer_id: str, **kwargs):
        super().__init__(**kwargs)
        self.customer_id = customer_id

    def _run(self, entity_id: int) -> str:
        """Query database with proper session management."""
        if database.SessionLocal is None:
            database.init_database()

        db = database.SessionLocal()
        try:
            result = db.query(MyModel).filter(
                MyModel.id == entity_id,
                MyModel.customer_id == self.customer_id
            ).first()

            if not result:
                return f"No entity found with ID {entity_id}"

            return self._format_result(result)
        finally:
            db.close()

    def _format_result(self, result) -> str:
        """Format result as string for agent."""
        return f"Entity: {result.name}, Status: {result.status}"
```

### External API Tool

For integrating third-party APIs:

```python
from crewai.tools import BaseTool
from typing import Type, Optional
from pydantic import BaseModel, Field
import httpx
import os
import logging

logger = logging.getLogger(__name__)

class ExternalAPIInput(BaseModel):
    """Input for external API call."""
    query: str = Field(..., description="Search query")

class ExternalAPITool(BaseTool):
    name: str = "external_search"
    description: str = "Search external data source for information"
    args_schema: Type[BaseModel] = ExternalAPIInput

    api_key: Optional[str] = None
    base_url: str = "https://api.example.com"
    timeout: int = 30

    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key or os.getenv("EXTERNAL_API_KEY")

        if not self.api_key:
            logger.warning("External API key not configured")

    def _run(self, query: str) -> str:
        """Call external API with error handling."""
        if not self.api_key:
            return "Error: API key not configured"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(
                    f"{self.base_url}/search",
                    params={"q": query},
                    headers={"Authorization": f"Bearer {self.api_key}"}
                )
                response.raise_for_status()

                data = response.json()
                return self._format_response(data)

        except httpx.TimeoutException:
            logger.error(f"API timeout for query: {query}")
            return "Error: API request timed out"
        except httpx.HTTPStatusError as e:
            logger.error(f"API error: {e.response.status_code}")
            return f"Error: API returned status {e.response.status_code}"
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return f"Error: {str(e)}"

    def _format_response(self, data: dict) -> str:
        """Format API response for agent."""
        results = data.get("results", [])
        if not results:
            return "No results found"

        return "\n".join([
            f"- {r.get('title')}: {r.get('description')}"
            for r in results[:5]
        ])
```

### Tool with Structured Output

For tools that return complex structured data:

```python
from crewai.tools import BaseTool
from typing import Type, List
from pydantic import BaseModel, Field
import json

class AnalysisResult(BaseModel):
    """Structured result from analysis."""
    score: float
    confidence: float
    categories: List[str]
    summary: str

class AnalysisInput(BaseModel):
    """Input for analysis tool."""
    text: str = Field(..., description="Text to analyze")

class StructuredAnalysisTool(BaseTool):
    name: str = "analyze_text"
    description: str = (
        "Analyze text and return structured results including "
        "score, confidence, categories, and summary."
    )
    args_schema: Type[BaseModel] = AnalysisInput

    def _run(self, text: str) -> str:
        """Perform analysis and return structured result."""
        result = AnalysisResult(
            score=0.85,
            confidence=0.92,
            categories=["technical", "documentation"],
            summary="Text appears to be technical documentation."
        )

        # Return as JSON string for agent parsing
        return json.dumps(result.model_dump(), indent=2)
```

### Tool Execution Tracking

Log tool executions for debugging and monitoring:

```python
from crewai.tools import BaseTool
from typing import Type, Callable
from pydantic import BaseModel
from functools import wraps
import time
import logging

logger = logging.getLogger(__name__)

def track_execution(func: Callable) -> Callable:
    """Decorator to track tool execution."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        tool_name = self.name

        logger.info(f"Tool '{tool_name}' started with args: {args}, kwargs: {kwargs}")

        try:
            result = func(self, *args, **kwargs)
            duration = time.time() - start_time

            logger.info(f"Tool '{tool_name}' completed in {duration:.2f}s")
            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Tool '{tool_name}' failed after {duration:.2f}s: {e}")
            raise

    return wrapper

class TrackedTool(BaseTool):
    name: str = "tracked_tool"
    description: str = "A tool with execution tracking"
    args_schema: Type[BaseModel] = MyToolInput

    @track_execution
    def _run(self, query: str) -> str:
        return f"Result for: {query}"
```

---

## Complete Template

```python
"""
Document Search Tool — RAG-based document retrieval for Eliza Platform

Searches the vector knowledge base using semantic search and returns
relevant document chunks with source information.
"""
from crewai.tools import BaseTool
from typing import Type, Optional, List
from pydantic import BaseModel, Field
from src.models import database
from src.services.vector_service import VectorService

class DocumentSearchInput(BaseModel):
    """Input for document search."""
    query: str = Field(..., description="Natural language search query")
    limit: int = Field(default=5, description="Number of documents to return")

class DocumentSearchTool(BaseTool):
    name: str = "document_search"
    description: str = (
        "Search the document knowledge base using semantic search. "
        "Returns relevant document chunks with source information. "
        "Use this to find information about company policies, procedures, etc."
    )
    args_schema: Type[BaseModel] = DocumentSearchInput

    customer_id: str
    company_hr_dataset: str  # CRITICAL: Use for data filtering
    similarity_threshold: float = 0.7

    def __init__(
        self,
        customer_id: str,
        company_hr_dataset: str,
        similarity_threshold: float = 0.7,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.customer_id = customer_id
        self.company_hr_dataset = company_hr_dataset
        self.similarity_threshold = similarity_threshold

    def _run(self, query: str, limit: int = 5) -> str:
        """Execute semantic search."""
        if database.SessionLocal is None:
            database.init_database()

        db = database.SessionLocal()
        try:
            vector_service = VectorService(db)

            # CRITICAL: Filter by company_hr_dataset, NOT customer_id
            results = vector_service.search_similar_chunks(
                query=query,
                company_hr_dataset=self.company_hr_dataset,
                limit=limit,
                similarity_threshold=self.similarity_threshold
            )

            return self._format_results(results)
        finally:
            db.close()

    def _format_results(self, results: List) -> str:
        """Format search results for agent consumption."""
        if not results:
            return "No relevant documents found."

        formatted = []
        for i, result in enumerate(results, 1):
            # Access Pydantic model attributes directly
            formatted.append(
                f"[{i}] {result.document_filename}\n"
                f"    Score: {result.similarity_score:.2f}\n"
                f"    Content: {result.text[:500]}...\n"
            )

        return "\n".join(formatted)
```

**Critical rules for document search:**
1. Use `company_hr_dataset` for filtering (what company the data is about)
2. `customer_id` is for ownership/audit (who uploaded it)
3. Access Pydantic attributes (`.text`), not dict methods (`.get()`)

---

## File Locations

```
src/
└── crewai_custom_tools/
    ├── __init__.py
    ├── document_search_tool.py    # RAG document search
    ├── hr_database_tool.py        # HR data queries
    ├── person_search_tools.py     # PDL person search
    ├── talent_matching_tools.py   # Candidate matching
    └── tool_execution_tracker.py  # Execution logging
```

---

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Storing db session in tool instance | Create session in `_run()`, close in `finally` |
| Not closing database sessions | Use `try/finally` pattern |
| Using `customer_id` for document search filtering | Use `company_hr_dataset` instead |
| Using `.get()` on Pydantic models | Use direct attribute access (`.text`, `.similarity_score`) |
| No error handling in external API calls | Wrap in `try/except` with specific exception types |
| Overly complex tool descriptions | Keep descriptions clear so agents know when to use the tool |

---

## Checklist

- [ ] Clear, specific `name` and `description`
- [ ] Input schema with field descriptions
- [ ] Proper database session management (if applicable)
- [ ] Multi-tenant filtering with correct field (`company_hr_dataset`)
- [ ] Error handling with user-friendly messages
- [ ] Logging for debugging
- [ ] Unit tests
- [ ] Container rebuilt: `docker-compose build app celery-worker`

---

## References

- `src/crewai_custom_tools/document_search_tool.py` — RAG search example
- `src/crewai_custom_tools/person_search_tools.py` — API integration example
- `src/crewai_custom_tools/hr_database_tool.py` — Database query example
- `src/crewai_custom_tools/tool_execution_tracker.py` — Execution logging
- `skills/crewai/CREWAI_DEVELOPMENT_RULES.md` — Database session and import rules
- [CrewAI Tools Documentation](https://docs.crewai.com/core-concepts/tools)
