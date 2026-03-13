# Data Analyst Agent - CrewAI Flow Architecture

## Overview

This document explains how CrewAI flows integrate with Vanna AI for the Data Analyst Agent feature, addressing the architecture, responsibilities, and best practices.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Submits Question                         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│              DataAnalystFlow (CrewAI Flow)                       │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 1: @start() - Intent Detection Agent                 │  │
│  │  - Uses LLM to detect intent (DATA vs CONVERSATIONAL)    │  │
│  │  - Determines if clarification needed                    │  │
│  │  - Returns: IntentResult                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 2: @listen() - Clarification Agent (if needed)      │  │
│  │  - Generates clarification prompt                        │  │
│  │  - Waits for user response                               │  │
│  │  - Clarifies question using LLM                          │  │
│  │  - Returns: ClarifiedQuestion                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 3: @listen() - Intent Confirmation Agent            │  │
│  │  - Generates confirmation message                        │  │
│  │  - Waits for user confirmation                           │  │
│  │  - Returns: ConfirmedIntent                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                     │
│                            ▼                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Step 4: @listen() - Processing Router                    │  │
│  │  ┌────────────────────┐  ┌──────────────────────────┐   │  │
│  │  │ DATA Query Path    │  │ CONVERSATIONAL Path     │   │  │
│  │  │                    │  │                         │   │  │
│  │  │ Uses:              │  │ Uses:                  │   │  │
│  │  │ - VannaTool        │  │ - ConversationalAgent   │   │  │
│  │  │ - SQLExecutorTool  │  │ - LLM directly          │   │  │
│  │  │ - InsightsTool     │  │                         │   │  │
│  │  └────────────────────┘  └──────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Results Stored in DB                         │
│              (Message + Conversation Updated)                   │
└─────────────────────────────────────────────────────────────────┘
```

## Key Architectural Decisions

### 1. CrewAI Flow Responsibilities

**CrewAI Flow handles:**
- ✅ Intent detection (using LLM)
- ✅ Question clarification (using LLM)
- ✅ Intent confirmation (using LLM)
- ✅ Orchestration of multi-step conversation flow
- ✅ State management across conversation steps
- ✅ Event-driven flow (waiting for user responses)

**CrewAI Flow does NOT handle:**
- ❌ SQL generation (Vanna's responsibility)
- ❌ SQL execution (Tool's responsibility)
- ❌ Database persistence (Service layer's responsibility)

### 2. Vanna AI Integration

**Vanna remains separate and is called via a CrewAI Tool:**

```python
class VannaSQLGenerationTool(BaseTool):
    """CrewAI tool that wraps Vanna for SQL generation"""
    
    name: str = "Generate SQL Query"
    description: str = "Generate SQL from natural language using Vanna AI"
    
    def _run(self, question: str, conversation_context: str = None) -> str:
        """Call Vanna to generate SQL"""
        vanna_service = VannaService(...)
        sql = vanna_service.generate_sql(question, context=conversation_context)
        return sql
```

**Why this works:**
- Vanna has its own LLM integration internally (for context retrieval and SQL generation)
- CrewAI agents call Vanna through the tool interface
- Vanna's vector store (ChromaDB) remains separate from CrewAI's context
- No interference - each system handles its domain

### 3. Separation of Concerns

| Component | Responsibility | LLM Usage |
|-----------|---------------|-----------|
| **CrewAI Flow** | Orchestration, intent detection, clarification | CrewAI LLM class |
| **CrewAI Agents** | Intent analysis, clarification generation | CrewAI LLM class |
| **CrewAI Tools** | Database ops, Vanna calls, SQL execution | None (service calls) |
| **Vanna Service** | SQL generation, schema context retrieval | Vanna's internal LLM |
| **DataAnalystService** | Business logic, result formatting | None (orchestration only) |

## Flow State Model

```python
class DataAnalystFlowState(BaseModel):
    """State maintained throughout the data analyst flow"""
    
    # Input
    message_id: str
    user_id: int
    customer_id: str
    conversation_id: Optional[str]
    original_question: str
    data_source_type: str
    
    # Step 1: Intent Detection
    detected_intent: Optional[str] = None  # "data_query" | "conversational"
    intent_confidence: Optional[str] = None  # "high" | "medium" | "low"
    clarification_needed: bool = False
    
    # Step 2: Clarification (if needed)
    clarification_prompt: Optional[str] = None
    clarification_response: Optional[str] = None
    clarified_question: Optional[str] = None
    
    # Step 3: Confirmation
    intent_confirmed: bool = False
    confirmation_message: Optional[str] = None
    
    # Step 4: Processing
    processing_result: Optional[Dict[str, Any]] = None
    
    # Error handling
    error: Optional[str] = None
```

## CrewAI Agents

### Agent 1: Intent Detection Agent

```python
intent_agent = Agent(
    role="Intent Detection Specialist",
    goal="Analyze user questions to determine if they require SQL/data retrieval or general conversation",
    backstory="You are an expert at understanding user intent in data analysis contexts...",
    tools=[],  # No tools needed - pure LLM analysis
    llm=self.llm,
    verbose=True
)
```

**Task:** Analyze question and return structured intent result.

### Agent 2: Clarification Agent (Conditional)

```python
clarification_agent = Agent(
    role="Question Clarification Specialist",
    goal="Generate clarification prompts and refine ambiguous questions",
    backstory="You help users clarify their questions when they're ambiguous...",
    tools=[],  # No tools needed
    llm=self.llm,
    verbose=True
)
```

**Task:** Generate clarification prompt or refine question based on user response.

### Agent 3: Processing Router Agent

```python
router_agent = Agent(
    role="Data Processing Router",
    goal="Route confirmed questions to appropriate processing (SQL generation or conversational response)",
    backstory="You route questions to the right processing path...",
    tools=[
        vanna_sql_tool,      # For DATA queries
        sql_executor_tool,   # Execute SQL
        insights_tool,       # Generate insights
        conversational_tool  # For CONVERSATIONAL queries
    ],
    llm=self.llm,
    verbose=True
)
```

**Task:** Process confirmed questions using appropriate tools.

## CrewAI Tools

### Tool 1: VannaSQLGenerationTool

```python
class VannaSQLGenerationTool(BaseTool):
    """Wraps Vanna service for SQL generation"""
    
    name: str = "Generate SQL Query"
    description: str = """
    Generate SQL from natural language questions using Vanna AI.
    Use this tool when the user wants to query data.
    """
    
    def _run(self, question: str, conversation_context: str = None) -> str:
        """Generate SQL using Vanna"""
        # Get Vanna service (lazy initialization)
        vanna_service = self._get_vanna_service()
        
        # Build enhanced question with context
        enhanced_question = question
        if conversation_context:
            enhanced_question = f"{conversation_context}\n\nQuestion: {question}"
        
        # Generate SQL
        sql = vanna_service.generate_sql(enhanced_question)
        return json.dumps({"sql": sql, "status": "success"})
```

### Tool 2: SQLExecutorTool

```python
class SQLExecutorTool(BaseTool):
    """Execute SQL queries safely"""
    
    name: str = "Execute SQL Query"
    description: str = "Execute SQL queries and return results"
    
    def _run(self, sql: str) -> str:
        """Execute SQL using Vanna"""
        vanna_service = self._get_vanna_service()
        results = vanna_service.run_sql(sql)
        return json.dumps(results)
```

### Tool 3: DatabaseMessageTool

```python
class DatabaseMessageTool(BaseTool):
    """Save/retrieve messages from database"""
    
    name: str = "Database Message Operations"
    description: str = "Save messages and retrieve conversation context"
    
    def _run(self, operation: str, **kwargs) -> str:
        """Database operations"""
        # Create/update messages
        # Retrieve conversation context
        # etc.
```

## Benefits of This Architecture

### 1. **Clear Separation of Concerns**
- CrewAI handles conversation orchestration
- Vanna handles SQL generation
- Tools bridge the gap

### 2. **No Interference**
- Vanna's LLM calls are internal to Vanna
- CrewAI's LLM calls are for intent/clarification
- They don't conflict because they serve different purposes

### 3. **Better State Management**
- Flow state is serializable (Pydantic models)
- Can pause/resume flows (e.g., waiting for user clarification)
- Event-driven architecture (user responds → flow continues)

### 4. **Observability**
- CrewAI provides built-in logging and tracing
- Can see exactly which agent/tool was called
- Better debugging and monitoring

### 5. **Flexibility**
- Easy to add new agents (e.g., "Question Refinement Agent")
- Easy to add new tools (e.g., "Data Validation Tool")
- Can swap LLM models per agent

## Flow Execution Pattern

```python
# 1. User submits question
# 2. API creates message record (status: PENDING)
# 3. Celery task queues flow execution
# 4. Flow starts:

@start()
def detect_intent(self):
    """Step 1: Detect intent"""
    # Agent analyzes question
    # Returns: IntentResult
    
@listen(detect_intent)
def clarify_if_needed(self):
    """Step 2: Clarify if needed"""
    if self.state.clarification_needed:
        # Generate clarification prompt
        # Wait for user response (flow pauses)
        # Clarify question
    else:
        # Skip to confirmation
    
@listen(clarify_if_needed)
def confirm_intent(self):
    """Step 3: Confirm intent"""
    # Generate confirmation message
    # Wait for user confirmation (flow pauses)
    # Mark as confirmed
    
@listen(confirm_intent)
def process_question(self):
    """Step 4: Process question"""
    if self.state.detected_intent == "data_query":
        # Use VannaSQLGenerationTool
        # Use SQLExecutorTool
        # Use InsightsTool
    else:
        # Use ConversationalAgent
```

## Comparison: Current vs. CrewAI Flow Approach

| Aspect | Current (Direct LLM Calls) | CrewAI Flow Approach |
|--------|---------------------------|---------------------|
| **Intent Detection** | `litellm.completion()` in service | CrewAI Agent with LLM |
| **Clarification** | `litellm.completion()` in service | CrewAI Agent with LLM |
| **State Management** | Database records | Flow state (Pydantic) |
| **Orchestration** | Service methods | Flow steps (`@start`, `@listen`) |
| **Vanna Integration** | Direct service call | CrewAI Tool wrapper |
| **Observability** | Custom logging | Built-in CrewAI logging |
| **Pause/Resume** | Manual (status flags) | Built-in (event-driven) |
| **Error Handling** | Try/except blocks | Flow-level error handling |

## Migration Strategy

### Phase 1: Create Flow Structure
- Define `DataAnalystFlowState`
- Create `DataAnalystFlow` class
- Implement `@start()` step for intent detection

### Phase 2: Create Tools
- `VannaSQLGenerationTool`
- `SQLExecutorTool`
- `DatabaseMessageTool`
- `InsightsGenerationTool`

### Phase 3: Create Agents
- Intent Detection Agent
- Clarification Agent
- Processing Router Agent

### Phase 4: Integrate with API
- Update Celery task to use flow
- Update API endpoints to trigger flow
- Maintain backward compatibility

### Phase 5: Remove Old Code
- Remove `IntentRouterService` (replaced by agents)
- Remove direct LLM calls from `DataAnalystService`
- Keep Vanna service (used by tools)

## Best Practices

1. **Never store database sessions in flow state** - Create sessions locally in each step
2. **Use tools for external operations** - Database, Vanna, etc.
3. **Use agents for LLM reasoning** - Intent detection, clarification
4. **Keep flow state serializable** - Only Pydantic models, no DB sessions
5. **Handle errors gracefully** - Set `state.error` and log appropriately
6. **Use appropriate LLM models** - `gpt-4o-mini` for simple tasks, larger models for complex reasoning

## Conclusion

CrewAI flows complement Vanna perfectly:
- **CrewAI**: Handles conversation orchestration, intent detection, clarification
- **Vanna**: Handles SQL generation (its own domain)
- **Tools**: Bridge CrewAI agents to Vanna and other services

This architecture provides:
- Better state management
- Event-driven conversation flow
- Clear separation of concerns
- Better observability
- No interference between systems

