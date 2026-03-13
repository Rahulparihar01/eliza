# Data Analyst CrewAI Flow Implementation

## Overview

The Data Analyst conversation model has been fully implemented using CrewAI flows and tools, replacing direct LLM calls with a structured agent-based architecture.

## Architecture

### Flow Structure

```
User Question
    ↓
Step 1: Intent Detection Agent (CrewAI LLM)
    ├─ Detects: DATA_QUERY vs CONVERSATIONAL
    ├─ Determines: Clarification needed?
    └─ Returns: IntentResult
    ↓
Step 2: Clarification Agent (if needed) (CrewAI LLM)
    ├─ Generates clarification prompt (if needed)
    └─ Refines question (if clarification_response provided)
    ↓
Step 3: Confirmation Agent (CrewAI LLM)
    ├─ Generates confirmation message
    └─ Processes confirmation response (if provided)
    ↓
Step 4: Processing Router Agent
    ├─ DATA Query Path:
    │   ├─ VannaSQLGenerationTool → Vanna Service
    │   ├─ SQLExecutorTool → Execute SQL
    │   ├─ InsightsGenerationTool → Generate insights
    │   └─ DatabaseMessageTool → Save results
    └─ CONVERSATIONAL Path:
        ├─ ConversationalResponseTool → LLM response
        └─ DatabaseMessageTool → Save response
```

## Key Components

### 1. DataAnalystFlow (`src/flows/data_analyst_flow.py`)

**Flow Steps:**
- `@start()` - `detect_intent()`: Uses Intent Detection Agent
- `@listen(detect_intent)` - `clarify_if_needed()`: Uses Clarification Agent
- `@listen(clarify_if_needed)` - `confirm_intent()`: Uses Confirmation Agent
- `@listen(confirm_intent)` - `process_question()`: Uses Router Agent with tools

**Flow State:**
- Serializable Pydantic model (`DataAnalystFlowState`)
- Never stores database sessions
- Tracks intent, clarification, confirmation, and processing results

### 2. CrewAI Tools (`src/crewai_custom_tools/data_analyst_tools.py`)

**Tools:**
- `VannaSQLGenerationTool`: Wraps Vanna service for SQL generation
- `SQLExecutorTool`: Executes SQL queries via Vanna
- `InsightsGenerationTool`: Generates LLM-powered insights
- `ConversationalResponseTool`: Generates conversational responses
- `DatabaseMessageTool`: Database operations (CRUD, context retrieval)

**Tool Pattern:**
- Extend `BaseTool`
- Implement `_run()` method
- Return JSON strings for agent consumption
- Create database sessions locally (never store in tool)

### 3. CrewAI Agents

**Intent Detection Agent:**
- Role: Intent Detection Specialist
- Tools: None (pure LLM analysis)
- Output: Structured JSON with intent, confidence, clarification needs

**Clarification Agent:**
- Role: Question Clarification Specialist
- Tools: None
- Output: Clarified question or clarification prompt

**Confirmation Agent:**
- Role: Intent Confirmation Specialist
- Tools: None
- Output: Confirmation message

**Router Agent:**
- Role: Data Processing Router
- Tools: All tools (VannaSQLGenerationTool, SQLExecutorTool, InsightsGenerationTool, ConversationalResponseTool, DatabaseMessageTool)
- Output: Processing results summary

## How CrewAI Complements Vanna

### No Interference

1. **Different Responsibilities:**
   - CrewAI: Conversation orchestration, intent detection, clarification
   - Vanna: SQL generation (its own domain)
   - Tools: Bridge between CrewAI and Vanna

2. **Separate LLM Calls:**
   - CrewAI agents use CrewAI's LLM class for reasoning
   - Vanna uses its own internal LLM for SQL generation
   - They don't conflict because they serve different purposes

3. **Clean Integration:**
   - VannaSQLGenerationTool calls Vanna service
   - Vanna service handles its own LLM calls internally
   - CrewAI agent receives SQL string, doesn't need to know about Vanna's internals

## Multi-Turn Conversation Flow

### Flow Execution Pattern

CrewAI flows don't have built-in pause/resume. Instead, we use a **multi-step API orchestration** pattern:

1. **User submits question** → API creates message → Triggers flow
2. **Flow Step 1** (Intent Detection) → Returns state with `clarification_prompt` if needed
3. **API checks state** → If `clarification_needed`, returns `clarification_prompt` to user
4. **User provides clarification** → API calls `/clarify` endpoint → Updates message → Re-triggers flow
5. **Flow Step 2** (Clarification) → Processes clarification → Continues to Step 3
6. **Flow Step 3** (Confirmation) → Returns state with `confirmation_message` if needed
7. **API checks state** → If `confirmation_message` exists, returns to user
8. **User confirms** → API calls `/confirm` endpoint → Updates message → Re-triggers flow
9. **Flow Step 4** (Processing) → Generates SQL → Executes → Saves results

### API Endpoints

**New Endpoints:**
- `POST /v1/data-analyst/questions/{question_id}/clarify` - Provide clarification response
- `POST /v1/data-analyst/questions/{question_id}/confirm` - Confirm or correct intent

**Updated Endpoints:**
- `POST /v1/data-analyst/questions` - Now uses `create_message()` with smart intent detection

## Best Practices Followed

### 1. Database Session Management
- ✅ Never store sessions in flow state
- ✅ Create sessions locally in tools/methods
- ✅ Use try/finally for cleanup
- ✅ Check `SessionLocal is None` before use

### 2. Flow State
- ✅ Serializable Pydantic models only
- ✅ No database sessions
- ✅ No non-serializable objects
- ✅ Clear state transitions

### 3. Tool Design
- ✅ Clear descriptions for agents
- ✅ JSON string outputs
- ✅ Error handling
- ✅ Lazy initialization

### 4. Agent Design
- ✅ Specialized roles
- ✅ Clear goals and backstories
- ✅ Appropriate tools assigned
- ✅ No delegation (explicit control)

## Integration Points

### Celery Task (`src/tasks/data_analyst_tasks.py`)

```python
@celery_app.task(name="data_analyst.process_message")
def process_data_analyst_message(message_id: str):
    # 1. Get message from database
    # 2. Get conversation context
    # 3. Create flow state
    # 4. Run flow
    # 5. Update message with flow state results
```

### API Routes (`src/api/routes/data_analyst.py`)

- `POST /questions` - Submit question (triggers flow)
- `POST /questions/{id}/clarify` - Provide clarification (re-triggers flow)
- `POST /questions/{id}/confirm` - Confirm intent (re-triggers flow)

## Benefits

1. **Better State Management**: Flow state is serializable, can pause/resume
2. **Clear Separation**: CrewAI handles orchestration, Vanna handles SQL
3. **Observability**: Built-in CrewAI logging and tracing
4. **Flexibility**: Easy to add new agents/tools
5. **No Interference**: CrewAI and Vanna operate independently

## Migration Notes

### Replaced Components

- ❌ `IntentRouterService` (direct LLM calls) → ✅ CrewAI Intent Detection Agent
- ❌ Direct `litellm.completion()` calls → ✅ CrewAI agents with LLM class
- ❌ Service-level orchestration → ✅ CrewAI flow orchestration

### Kept Components

- ✅ `VannaService` - Still used by `VannaSQLGenerationTool`
- ✅ `DataAnalystService` - Still used for insights generation
- ✅ `ConversationService` - Still used for conversation management
- ✅ `ConversationContextManager` - Still used for context building

## Testing Checklist

- [ ] Flow executes end-to-end for DATA queries
- [ ] Flow executes end-to-end for CONVERSATIONAL queries
- [ ] Clarification flow works (question → clarification prompt → clarification response → processing)
- [ ] Confirmation flow works (intent detected → confirmation message → confirmation response → processing)
- [ ] Vanna SQL generation works through tool
- [ ] SQL execution works through tool
- [ ] Results are saved to database via tool
- [ ] Conversation context is passed correctly
- [ ] Error handling works (flow state.error set on failures)

## Next Steps

1. Test flow integration end-to-end
2. Add conversation endpoints (create, list, get conversations)
3. Update frontend to handle clarification/confirmation flow
4. Add conversation list sidebar
5. Implement message display with conversation context

