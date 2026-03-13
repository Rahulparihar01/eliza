# SSE & Analysis Workflow - Comprehensive Diagnosis
*October 19, 2025 00:35 AM*

## Current Situation

User logged out, logged back in, submitted a new analysis (`ml_ta_899ac36a3b1e`), and observed the following errors in the browser console:

1. **GET** `/api/talent/analysis/ml_ta_899ac36a3b1e` → **403 Forbidden**
2. **SSE connection error**
3. **HEAD** `/api/talent/analysis/ml_ta_899ac36a3b1e/stream` → **405 Method Not Allowed**

## Root Cause Analysis

### Issue #1: OpenAI API Quota Exceeded ⚠️ PRIMARY ISSUE
**Status**: Analysis fails immediately, no SSE events to stream

**Evidence**:
```sql
SELECT event_type, message FROM talent_analysis_events 
WHERE analysis_id = 'ml_ta_899ac36a3b1e';

event_type              | message
analysis_started        | Analysis started - preparing to run AI agents
orchestrator_initialized| AI orchestrator initialized - starting analysis workflow
analysis_failed         | litellm.RateLimitError: OpenAIException - You exceeded your current quota
```

**Root Cause**: 
- The OpenAI API key in `docker/.env` is **valid** (can list models) but has **no credits/quota**
- Analysis fails at Stage 1 (Baseline Building) when first LLM call is made
- No stage events (stage_1_started, stage_1_completed, etc.) are ever emitted
- Only 3 events are created: `analysis_started`, `orchestrator_initialized`, `analysis_failed`

**Impact**: 
- Frontend SSE stream connects successfully
- But there are no meaningful progress events to stream
- UI shows "Initializing analysis..." indefinitely
- No stage progress is ever displayed

### Issue #2: SSE Authentication Flow (403 Forbidden)
**Status**: Working as designed, but confusing error message

**Flow**:
1. Frontend connects to SSE: `GET /api/talent/analysis/{id}/stream?token={jwt}`
2. Backend verifies token successfully
3. Backend sends initial events (`analysis_started`, `orchestrator_initialized`, `analysis_failed`)
4. SSE stream closes after sending `analysis_failed` event
5. Frontend `EventSource.onerror` fires (expected when stream closes)
6. Frontend attempts `HEAD` request to check if it was a 403 (auth error)
7. Backend returns **405 Method Not Allowed** (endpoint only accepts GET)
8. Frontend logs the 405 error but also tries GET request
9. GET request returns **403** because the JWT token was somehow invalidated

**Root Cause of 403**:
- After logout/login, a new JWT token is issued
- Old SSE connection may still be using the old token
- Or the token expired during the analysis
- Or localStorage wasn't fully cleared/reloaded

**Why HEAD returns 405**:
- The SSE endpoint is defined as `@router.get("/analysis/{analysis_id}/stream")`
- FastAPI only allows GET, not HEAD
- Frontend's auth-check logic uses HEAD, which fails

### Issue #3: Frontend Stuck on "Initializing..."
**Status**: Correct behavior given backend failure, but UX could be better

**Current Flow**:
1. Analysis fails immediately (OpenAI quota)
2. `analysis_failed` event IS created in database
3. SSE stream sends the `analysis_failed` event to frontend
4. Frontend `useAnalysisStream` hook receives event with `event_type: 'analysis_failed'`
5. Hook sets `isFailed: true` and `error: event.message`
6. **BUT** the UI may not be displaying this properly

**Potential Issues**:
- Frontend may not be handling `analysis_failed` event correctly
- Error state may not be updating the UI to show failure
- Progress component may not be checking `isFailed` state

## Solutions

### Solution 1: Fix OpenAI Quota (Immediate)
**Options**:
A. **Get a new OpenAI API key with credits**
B. **Switch to Anthropic Claude** (we already have Claude integration)
C. **Use local models** (Ollama, etc.)

**Recommendation**: Use Claude (Anthropic) for now
- Already integrated in the system
- Proven to work for diagnostic and synthesis agents
- Higher quality outputs for complex reasoning

**Implementation**:
```python
# diagnostic_agent.py and synthesis_agent.py
# Already support provider switching via constructor

# orchestrator.py - update LLM configuration
self.diagnostic_agent = DiagnosticAgentService(
    llm_provider="anthropic",  # Changed from "openai"
    llm_model="claude-sonnet-4"  # or "claude-opus-4"
)

self.synthesis_agent = SynthesisAgentService(
    llm_provider="anthropic",
    llm_model="claude-sonnet-4"
)
```

### Solution 2: Fix HEAD 405 Error (Minor)
**Add HEAD support to SSE endpoint**:
```python
# src/api/routes/talent.py
@router.api_route("/analysis/{analysis_id}/stream", methods=["GET", "HEAD"])
async def stream_talent_analysis(...):
    if request.method == "HEAD":
        # Return 200 if auth succeeds, 403 if not
        return Response(status_code=200)
    
    # ... existing SSE logic for GET
```

**OR remove HEAD check from frontend** (simpler):
```typescript
// frontend/src/hooks/useAnalysisStream.ts
eventSource.onerror = (err) => {
  console.error('SSE connection error:', err);
  eventSource.close();
  
  // Remove the HEAD request check - just close gracefully
  if (!isComplete) {
    setError('Connection to server lost');
  }
};
```

### Solution 3: Improve Error Display (UX)
**Ensure `analysis_failed` event updates UI**:
```typescript
// AnalysisProgress.tsx - verify event handling
useEffect(() => {
  if (isFailed && error) {
    setCurrentMessage('Analysis failed');
    setErrorDetails(error);
    
    // Mark all pending stages as skipped/error
    setStages(prev => prev.map(stage => 
      stage.status === 'pending' || stage.status === 'running'
        ? { ...stage, status: 'error', message: 'Analysis failed' }
        : stage
    ));
  }
}, [isFailed, error]);
```

## Testing Plan

### Test 1: Switch to Claude
1. Update orchestrator to use Anthropic/Claude
2. Rebuild and restart containers
3. Submit new analysis
4. Verify stages progress successfully

### Test 2: Verify SSE Events
1. Monitor database: `SELECT * FROM talent_analysis_events WHERE analysis_id = '...' ORDER BY id;`
2. Monitor browser console for SSE events
3. Verify all 7 stages emit start/complete events
4. Verify frontend displays each stage transition

### Test 3: Error Handling
1. Introduce intentional failure (bad credentials)
2. Verify `analysis_failed` event is created
3. Verify frontend shows error state clearly
4. Verify user can "Start Over" and retry

## Recommended Next Steps

1. **Immediate**: Switch to Claude/Anthropic to unblock analysis
2. **Quick win**: Remove HEAD check from frontend SSE error handler
3. **Polish**: Ensure error states display clearly in UI
4. **Future**: Add retry logic for transient failures
5. **Future**: Add analysis cost estimation before running

## Key Insights

1. **SSE is working correctly** - events are being created and streamed
2. **Auth is working correctly** - tokens are verified, access is granted
3. **The issue is upstream** - analysis fails before any real work happens
4. **OpenAI quota is the blocker** - need a different LLM provider or valid key
5. **Frontend error handling exists but needs polish** - failed events reach the UI but may not display clearly

## Files Involved

- `src/services/talent/orchestrator.py` - Main workflow orchestrator
- `src/services/talent/diagnostic_agent.py` - Uses LLM for diagnostic analysis
- `src/services/talent/synthesis_agent.py` - Uses LLM for synthesis
- `src/api/routes/ml_talent.py` - Analysis background task and SSE routing
- `src/api/routes/talent.py` - SSE streaming endpoint
- `frontend/src/hooks/useAnalysisStream.ts` - SSE client
- `frontend/src/components/talent-intelligence/AnalysisProgress.tsx` - Progress UI
- `docker/.env` - Environment configuration including API keys


