# Agent Execution Timeline - Documentation

## Overview

The Agent Execution Timeline feature provides comprehensive visibility into what the AI agents are doing when processing Business Intelligence questions. This includes tool calls, agent responses, and real-time telemetry.

## Where Timeline Details Should Appear

### Location in UI
The timeline appears in the **Question History** tab when you select a completed question:

```
Business Intelligence Q&A
├── Ask Question tab
├── Question History tab (← Select a question here)
│   ├── Recent Questions (left panel)
│   │   └── Click on any question
│   └── Question Details (right panel)
│       ├── Processing Summary
│       │   ├── Status
│       │   ├── Started/Completed timestamps
│       │   └── Stage information
│       └── Agent Execution Timeline ⭐ (THIS IS WHERE IT APPEARS)
│           ├── Enriched Prompt Details
│           ├── Tool Executions (with expand/collapse)
│           ├── Agent Responses (with expand/collapse)
│           └── Telemetry Events (with expand/collapse)
└── Enriched Prompts tab
```

### What You Should See

When viewing a completed question, the "Agent Execution Timeline" section should display:

#### 1. **Enriched Prompt**
- Original user question
- Enhanced prompt with context
- Intent type, complexity, confidence scores
- Processing instructions

#### 2. **Tool Executions**
Each tool call shows:
- Tool name (e.g., "HR Database Query", "Document Semantic Search")
- Agent that called it
- Input parameters
- Output results
- Status (success/failed)
- Duration in milliseconds
- Number of results returned
- Expandable JSON viewer for detailed inputs/outputs

#### 3. **Agent Responses**
Each agent's response shows:
- Agent name (e.g., "Data Retrieval Agent", "Data Analysis Agent")
- Stage name (retrieval/analysis)
- Input prompt given to agent
- Response text
- Reasoning (if applicable)
- Tool calls summary
- Confidence score
- Duration
- Expandable metadata

#### 4. **Telemetry Events**
Real-time events showing:
- Event type (stage_started, tool_completed, agent_completed, etc.)
- Timestamps
- Progress indicators
- Error details (if any)

### Example Timeline Structure

```
┌─ Agent Execution Timeline ─────────────────────────────────┐
│                                                             │
│ 🌟 Oct 07, 02:38  Enriched Prompt Generated               │
│    ├─ Original: "Which departments have the highest..."    │
│    ├─ Intent: analytics                                    │
│    └─ Complexity: medium                                   │
│    [Show Details ▼]                                        │
│                                                             │
│ 🔧 Oct 07, 02:38  Tool Called: Document Semantic Search   │
│    ├─ Agent: Data Retrieval Agent                         │
│    ├─ Status: success • 50ms • 0 results                  │
│    └─ [Show Details ▼]                                    │
│                                                             │
│ 🔧 Oct 07, 02:38  Tool Called: HR Database Query          │
│    ├─ Agent: Data Retrieval Agent                         │
│    ├─ Status: success • 120ms • 5 results                 │
│    └─ [Show Details ▼]                                    │
│                                                             │
│ 💬 Oct 07, 02:39  Agent Response: Data Retrieval Agent    │
│    ├─ Stage: retrieval                                     │
│    ├─ Confidence: 90%                                      │
│    └─ [Show Details ▼]                                    │
│                                                             │
│ 💬 Oct 07, 02:39  Agent Response: Data Analysis Agent     │
│    ├─ Stage: analysis                                      │
│    ├─ Confidence: 85%                                      │
│    └─ [Show Details ▼]                                    │
│                                                             │
│ ✅ Oct 07, 02:39  Telemetry: agent_completed              │
│    └─ Analysis complete                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Current Issue (As of Oct 7, 2025)

### Problem
The timeline shows "No execution timeline available yet" even though:
- ✅ The question completed successfully
- ✅ Data exists in database (4 tool executions, 2 agent responses)
- ✅ Session is properly linked to the question

### Root Cause
**Authentication/Permission Error**: The frontend is calling the timeline API endpoint (`/v1/bi/questions/{question_id}/timeline`) but receiving **401 Unauthorized** or **403 Forbidden** responses.

**Evidence from logs:**
```
app-1  | 02:55:28 ERROR Request completed: GET /v1/bi/questions/q_e9e38c93f93f/timeline -> 401
app-1  | 02:58:25 ERROR Request completed: GET /v1/bi/questions/q_e9e38c93f93f/timeline -> 403
```

### Database Verification

For question `q_e9e38c93f93f`:
```sql
-- Question exists and completed successfully
SELECT * FROM bi_questions WHERE question_id = 'q_e9e38c93f93f';
-- Result: id=15, status='completed', session linked

-- Tool executions recorded
SELECT COUNT(*) FROM bi_tool_executions WHERE session_id = 13;
-- Result: 4 executions

-- Agent responses recorded
SELECT COUNT(*) FROM bi_agent_responses WHERE session_id = 13;
-- Result: 2 responses
```

## Technical Architecture

### Backend Components

#### 1. Database Models (`src/models/business_intelligence.py`)
- `BIToolExecution`: Records each tool call with inputs, outputs, timing
- `BIAgentResponse`: Records agent's reasoning and responses at each stage
- `BIAnalysisSession`: Links to question and contains all executions

#### 2. API Endpoint (`src/api/routes/business_intelligence.py`)
```python
@router.get("/questions/{question_id}/timeline")
async def get_execution_timeline(
    question_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.require_permission("bi:read"))
):
    # Returns comprehensive timeline with:
    # - enriched_prompt
    # - tool_executions[]
    # - agent_responses[]
    # - telemetry_events[]
```

**Required Permission**: `bi:read`

#### 3. Service Layer (`src/services/business_intelligence_service.py`)
Methods that create timeline data:
- `create_tool_execution()`: Records tool calls
- `create_agent_response()`: Records agent outputs
- `get_tool_executions()`: Retrieves tool execution history
- `get_agent_responses()`: Retrieves agent response history

#### 4. Flow Integration (`src/crewai_flows/data_analysis_flow.py`)
- Wraps tools with `ToolExecutionTracker` to automatically record executions
- Captures agent responses after each stage (retrieval, analysis)
- Stores session_id in flow state (NOT db_session to avoid pickle errors)

### Frontend Components

#### 1. ExecutionTimeline Component (`frontend/src/components/business-intelligence/ExecutionTimeline.tsx`)
Renders the timeline with:
- Chronological event list
- Icon-coded event types
- Expandable detail sections
- JSON viewers for complex data

#### 2. BusinessIntelligenceQA Page (`frontend/src/pages/business-intelligence/BusinessIntelligenceQA.tsx`)
- Fetches timeline data from API
- Passes data to ExecutionTimeline component
- Auto-refreshes every 5 seconds for incomplete questions

```typescript
React.useEffect(() => {
  const fetchTimeline = async () => {
    const response = await fetch(`/v1/bi/questions/${selectedQuestionId}/timeline`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    if (response.ok) {
      const data = await response.json();
      setTimelineData(data);
    }
  };
  fetchTimeline();
  // Refetch every 5s if not completed
}, [selectedQuestionId]);
```

## How to Fix the Current Issue

### Solution 1: Check Frontend Authentication
Verify the access token is being sent correctly:

1. Open browser DevTools → Network tab
2. Select the timeline API call
3. Check Request Headers for `Authorization: Bearer <token>`
4. Verify the token is not expired

### Solution 2: Check User Permissions
Ensure the current user has the `bi:read` permission:

```sql
-- Check user's permissions
SELECT p.name 
FROM users u
JOIN user_roles ur ON u.id = ur.user_id
JOIN roles r ON ur.role_id = r.id
JOIN role_permissions rp ON r.id = rp.role_id
JOIN permissions p ON rp.permission_id = p.id
WHERE u.id = 2;
```

### Solution 3: Verify API Route Registration
Ensure the timeline endpoint is properly registered in the FastAPI router.

### Solution 4: Check Authorization Logic
The endpoint checks:
```python
if question.customer_id != current_user.customer_id and not auth_middleware.has_role(current_user, "admin"):
    raise HTTPException(status_code=403, detail="Not authorized")
```

Verify the user's `customer_id` matches the question's `customer_id`.

## Testing the Feature

### Test with a New Question

1. **Submit a BI question**: "Which departments have the highest performance ratings?"
2. **Wait for completion**: Status should show "Completed"
3. **Click on the question** in the Question History
4. **Scroll to "Agent Execution Timeline"**
5. **Verify timeline shows**:
   - Enriched prompt event
   - Multiple tool execution events
   - Agent response events
6. **Click "Show Details"** on any event to see expanded information

### Expected Data Flow

```
User asks question
    ↓
Backend creates BIQuestion record
    ↓
Celery task starts processing
    ↓
PromptEnrichmentFlow enriches question
    ↓
DataAnalysisFlow starts
    ↓
    ├─ Creates BIAnalysisSession
    ├─ Wraps tools with ToolExecutionTracker
    ├─ Tool calls → BIToolExecution records
    ├─ Agent completes → BIAgentResponse records
    └─ Flow completes
    ↓
Frontend fetches `/timeline` endpoint
    ↓
ExecutionTimeline component displays events
```

## Files Modified for This Feature

### Backend
- `src/models/business_intelligence.py` - Added BIToolExecution, BIAgentResponse models
- `alembic/versions/015_bi_tool_executions.py` - Database migration
- `src/services/business_intelligence_service.py` - Added tracking methods
- `src/crewai_custom_tools/tool_execution_tracker.py` - Tool wrapper
- `src/crewai_flows/data_analysis_flow.py` - Integrated tracking
- `src/api/routes/business_intelligence.py` - Added timeline endpoint

### Frontend
- `frontend/src/components/business-intelligence/ExecutionTimeline.tsx` - New component
- `frontend/src/pages/business-intelligence/BusinessIntelligenceQA.tsx` - Integrated timeline
- `frontend/package.json` - Added date-fns dependency

## Debugging Checklist

If timeline doesn't appear:

- [ ] Question status is "completed"
- [ ] Question has an `analysis_session` linked
- [ ] Session has tool_executions records
- [ ] Session has agent_responses records
- [ ] API endpoint `/timeline` returns 200 (not 401/403)
- [ ] Frontend console shows no errors
- [ ] Network tab shows timeline data received
- [ ] ExecutionTimeline component is rendering
- [ ] Browser cache cleared (Cmd+Shift+R)

## Next Steps

1. Fix the authentication/permission issue preventing timeline API access
2. Test with a new question to verify the full flow works
3. Document the specific permission requirements for the timeline endpoint
4. Consider adding a retry mechanism if timeline fetch fails
5. Add user-friendly error message if timeline unavailable

