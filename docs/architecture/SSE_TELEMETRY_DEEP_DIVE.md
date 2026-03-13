# SSE Telemetry & BI Logging Architecture - Deep Dive Analysis

**Date:** October 2, 2025  
**Status:** SSE Connection Failing with 403 Forbidden

---

## 🔍 PROBLEM STATEMENT

The frontend Business Intelligence Q&A page shows "Disconnected" telemetry status with SSE connection errors (403 Forbidden). Questions are processing successfully (status updates work), but real-time telemetry events are not streaming to the UI.

---

## 🏗️ CURRENT TELEMETRY CAPTURE ARCHITECTURE

### **1. Telemetry Data Model**

**Table:** `bi_agent_telemetry`

**Schema:**
```python
class BIAgentTelemetry(Base):
    id = Column(Integer, primary_key=True)
    telemetry_id = Column(String, unique=True, index=True)  # "t_{uuid}"
    session_id = Column(Integer, ForeignKey('bi_analysis_sessions.id'))
    event_type = Column(Enum(TelemetryEventType))  # AGENT_STARTED, AGENT_COMPLETED, etc.
    agent_name = Column(String)          # "Data Retrieval Agent", "Data Analysis Agent"
    tool_name = Column(String)           # Tool being used (if applicable)
    stage_name = Column(String)          # "Task Enrichment", "Data Analysis"
    message = Column(Text)               # Technical message
    user_message = Column(Text)          # User-friendly message
    progress_percentage = Column(Float)  # 0-100%
    data = Column(JSON)                  # Arbitrary event data
    error_details = Column(JSON)         # Error context
    duration_ms = Column(Integer)        # Operation duration
    timestamp = Column(DateTime)         # Event timestamp
```

**Event Types:**
- `AGENT_STARTED` - Agent begins execution
- `AGENT_COMPLETED` - Agent finishes successfully
- `AGENT_FAILED` - Agent encounters error
- `TOOL_STARTED` - Tool execution begins
- `TOOL_COMPLETED` - Tool execution completes
- `STAGE_STARTED` - Flow stage begins
- `STAGE_COMPLETED` - Flow stage completes
- `DATA_RETRIEVED` - Data fetched from source

### **2. Telemetry Capture Points**

**Location:** `src/tasks/business_intelligence_tasks.py`

**Telemetry is captured at these key points:**

#### **A. Task Enrichment Flow (0-25%)**
```python
# START: Question received
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.STAGE_STARTED,
    stage_name="Task Enrichment",
    user_message="Analyzing your question...",
    progress_percentage=0.0
)

# COMPLETE: Enrichment done
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.STAGE_COMPLETED,
    stage_name="Task Enrichment",
    user_message="Question analysis complete",
    progress_percentage=25.0
)
```

#### **B. Data Retrieval (25-50%)**
```python
# START: Data retrieval
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.AGENT_STARTED,
    agent_name="Data Retrieval Agent",
    user_message="Retrieving data from HR database and documents...",
    progress_percentage=25.0
)

# COMPLETE: Data retrieved
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.AGENT_COMPLETED,
    agent_name="Data Retrieval Agent",
    user_message="Data retrieval completed",
    progress_percentage=50.0
)
```

#### **C. Data Analysis (50-100%)**
```python
# START: Analysis
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.AGENT_STARTED,
    agent_name="Data Analysis Agent",
    user_message="Analyzing data and generating insights...",
    progress_percentage=75.0
)

# COMPLETE: Analysis done
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.STAGE_COMPLETED,
    stage_name="Data Analysis",
    user_message="Analysis complete",
    progress_percentage=100.0
)
```

### **3. Telemetry Storage Service**

**Location:** `src/services/business_intelligence_service.py`

**Write API:**
```python
def add_telemetry_event(
    self,
    session_id: int,                          # DB session ID (not analysis_session_id string!)
    event_type: TelemetryEventType,
    agent_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    stage_name: Optional[str] = None,
    message: Optional[str] = None,
    user_message: Optional[str] = None,
    progress_percentage: Optional[float] = None,
    data: Optional[Dict[str, Any]] = None,
    error_details: Optional[Dict[str, Any]] = None,
    duration_ms: Optional[int] = None
) -> BIAgentTelemetry:
    telemetry_id = f"t_{uuid.uuid4().hex[:12]}"
    telemetry = BIAgentTelemetry(...)
    self.db.add(telemetry)
    self.db.commit()
    return telemetry
```

**Read API:**
```python
def get_telemetry_events(
    self,
    session_id: int,
    limit: int = 100
) -> List[BIAgentTelemetry]:
    return self.db.query(BIAgentTelemetry)\
        .filter(BIAgentTelemetry.session_id == session_id)\
        .order_by(BIAgentTelemetry.timestamp)\
        .limit(limit)\
        .all()
```

---

## 📡 CURRENT SSE STREAMING ARCHITECTURE

### **1. SSE Endpoint**

**Location:** `src/api/routes/business_intelligence.py`

**Endpoint:** `GET /v1/bi/questions/{question_id}/telemetry`

**Authentication:** Token passed as query parameter (EventSource doesn't support headers)

**Flow:**
```python
async def stream_telemetry(
    question_id: str,
    token: str = Query(...),  # JWT from query param
    db: Session = Depends(get_db)
):
    # 1. Verify token
    payload = await auth_service.verify_token(token)
    user_id = int(payload.get("sub"))
    user = auth_service.get_user_by_id(user_id)
    
    # 2. Build user context
    current_user = CurrentUserContext(...)
    
    # 3. Get question & check authorization
    question = bi_service.get_question(question_id)
    if question.user_id != current_user.user_id:
        raise HTTPException(403)
    
    # 4. Stream events
    async def event_generator():
        last_event_id = 0
        while True:
            # Get new events
            events = bi_service.get_telemetry_events(
                session_id=question.analysis_session_id,
                limit=100
            )
            
            # Filter & send new events
            new_events = [e for e in events if e.id > last_event_id]
            for event in new_events:
                yield f"data: {json.dumps(event_data)}\n\n"
                last_event_id = event.id
            
            # Check if done
            if question.status in [COMPLETED, FAILED]:
                yield final_event
                break
            
            await asyncio.sleep(1)  # Poll every 1 second
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )
```

### **2. Frontend SSE Client**

**Location:** `frontend/src/components/business-intelligence/TelemetryViewer.tsx`

**Connection Logic:**
```typescript
useEffect(() => {
  if (!questionId) return;
  
  const apiUrl = window.location.origin;  // Use same origin (nginx proxy)
  const token = localStorage.getItem('auth_token');
  
  const eventSource = new EventSource(
    `${apiUrl}/v1/bi/questions/${questionId}/telemetry?token=${encodeURIComponent(token)}`,
    { withCredentials: false }
  );
  
  eventSource.onopen = () => setIsConnected(true);
  eventSource.onmessage = (event) => {
    const telemetryEvent = JSON.parse(event.data);
    setEvents(prev => [...prev, telemetryEvent]);
  };
  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
    setIsConnected(false);
    eventSource.close();
  };
  
  return () => eventSource.close();
}, [questionId]);
```

---

## 📊 CURRENT BI LOGGING ARCHITECTURE

### **1. Structured Logging System**

**Location:** `src/core/logging.py`

**Key Features:**
- **JSON Format**: All logs are structured JSON for machine parsing
- **ELK Integration**: Logs sent to Logstash → Elasticsearch → Kibana
- **Context Propagation**: Request ID, user ID, customer ID tracked across requests
- **Categories**: API, DATA_PROCESSING, BUSINESS, SECURITY, PERFORMANCE, SYSTEM

**Log Structure:**
```python
@dataclass
class LogEntry:
    timestamp: str
    level: str                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
    category: str                 # LogCategory enum
    message: str
    component: str               # Module/service name
    operation: Optional[str]     # Operation being performed
    context: Dict[str, Any]      # request_id, user_id, customer_id
    duration_ms: Optional[float]
    memory_mb: Optional[float]
    error_type: Optional[str]
    error_code: Optional[str]
    stack_trace: Optional[str]
    items_processed: Optional[int]
    success_count: Optional[int]
    error_count: Optional[int]
    metadata: Dict[str, Any]     # Additional structured data
    user_message: Optional[str]  # User-facing message
    user_action: Optional[str]   # Suggested action
    progress_percent: Optional[float]
```

### **2. BI Endpoint Logging**

**Location:** `src/api/routes/business_intelligence.py`

**Logger Configuration:**
```python
logger = get_logger(__name__, LogCategory.API)
```

**Logging Points:**

#### **A. Question Submission**
```python
@router.post("/questions")
async def submit_question(...):
    logger.info(
        "bi_question_submitted",
        category=LogCategory.BUSINESS,
        metadata={
            "question_id": question.question_id,
            "user_id": current_user.user_id,
            "customer_id": current_user.customer_id
        },
        user_message="Question submitted for analysis"
    )
```

#### **B. Status Polling**
```python
@router.get("/questions/{question_id}/status")
async def get_question_status(...):
    # No explicit logging - relies on middleware logging
    # middleware.logging logs all incoming/outgoing requests
```

#### **C. SSE Authentication Failure**
```python
@router.get("/questions/{question_id}/telemetry")
async def stream_telemetry(...):
    try:
        payload = await auth_service.verify_token(token)
        # ...
    except Exception as e:
        logger.error("SSE auth failed", error=str(e))
        raise HTTPException(403, detail="Invalid or expired token")
```

### **3. Middleware Logging**

**Location:** `src/middleware/logging.py`

**Automatic Request/Response Logging:**
- **Incoming**: Method, path, query params, client host, user agent
- **Outgoing**: Status code, response time, duration
- **Slow Requests**: Warnings for requests > 1000ms
- **Errors**: Full context for 4xx/5xx responses

**Example Log:**
```json
{
  "timestamp": "2025-10-02T20:20:33.994618+00:00",
  "level": "INFO",
  "category": "api",
  "message": "Request completed: GET /v1/bi/questions/q_070e748fac8f/status -> 200",
  "component": "middleware.logging",
  "operation": "http_request",
  "context": {
    "request_id": "c8331d40-719e-403d-b57b-0e105879d848"
  },
  "duration_ms": 96.52,
  "metadata": {
    "method": "GET",
    "path": "/v1/bi/questions/q_070e748fac8f/status",
    "status_code": 200,
    "response_time_ms": 96.52
  }
}
```

### **4. Task Execution Logging**

**Location:** `src/tasks/business_intelligence_tasks.py`

**Logger Configuration:**
```python
logger = get_logger(__name__, LogCategory.BUSINESS)
```

**Key Logging Points:**
- Task start/completion
- Flow transitions
- Agent execution
- Data retrieval
- Error handling

**Operation Tracking:**
```python
op_id = logger.start_operation(
    "bi_question_processing",
    category=LogCategory.BUSINESS,
    user_message="Processing your question...",
    metadata={"question_id": question_id}
)

# ... processing ...

logger.end_operation(
    op_id,
    success=True,
    items_processed=1,
    user_message="Analysis complete"
)
```

---

## 🐛 ROOT CAUSE ANALYSIS: SSE 403 ERRORS

### **Current Symptoms:**
1. ✅ Status API calls succeed (200 OK)
2. ✅ Question processing completes successfully
3. ❌ SSE telemetry connection fails (403 Forbidden)
4. ❌ NO "SSE auth failed" logs in backend
5. ❌ NO "Session cache HIT/MISS" logs
6. ✅ Telemetry requests DO reach backend (seen in logs)

### **Critical Observations:**

**Backend Logs Show:**
```
20:12:48 Incoming request: GET /v1/bi/questions/q_070e748fac8f/telemetry
20:12:48 Request completed: GET /v1/bi/questions/q_070e748fac8f/telemetry -> 403
```

**What's Missing:**
- NO `logger.error("SSE auth failed", error=str(e))` logs
- NO cache-related logs from `auth_service.verify_token()`
- NO exception details logged

### **Hypothesis:**

The 403 error is happening BEFORE the `stream_telemetry` function body executes. Possible causes:

1. **Middleware Interception**: Authorization middleware may be intercepting the request
2. **FastAPI Dependency Issue**: `Depends(get_db)` or other dependencies failing
3. **CORS/Security**: Browser blocking the connection (but curl tests also fail)
4. **Session Cache Not Initialized**: `auth_service` singleton missing `session_cache` attribute

### **Next Steps for Diagnosis:**

1. **Test auth_service directly in container:**
   ```bash
   docker exec docker-app-1 python3 -c "
   from src.services.auth_service import auth_service
   print('Has cache:', hasattr(auth_service, 'session_cache'))
   print('Cache type:', type(auth_service.session_cache) if hasattr(auth_service, 'session_cache') else 'N/A')
   "
   ```

2. **Add explicit logging at function entry:**
   ```python
   async def stream_telemetry(...):
       logger.info("SSE endpoint called", question_id=question_id)
       # ... rest of function
   ```

3. **Test with valid JWT token:**
   ```bash
   TOKEN=$(docker exec docker-app-1 python3 -c "from src.services.auth_service import auth_service; import json; user = auth_service.get_user_by_email('scott@eliza.com'); print(auth_service._create_access_token(user, 'test-session'))")
   curl "http://localhost:5001/v1/bi/questions/q_070e748fac8f/telemetry?token=$TOKEN"
   ```

---

## 📝 RECOMMENDATIONS

### **Immediate Actions:**

1. **Verify Session Cache Initialization**
   - Check if `auth_service.session_cache` exists
   - Confirm TTLCache is properly imported and instantiated

2. **Add Debug Logging to SSE Endpoint**
   - Log at function entry before any processing
   - Log token validation step-by-step
   - Log authorization checks

3. **Test Token Validation Separately**
   - Extract JWT from browser localStorage
   - Test with curl/httpie
   - Verify token hasn't expired

### **Long-Term Improvements:**

1. **Telemetry Enhancements:**
   - Add CrewAI agent-level telemetry hooks
   - Capture tool execution details
   - Track LLM API latency

2. **Logging Improvements:**
   - Add correlation IDs between frontend/backend
   - Implement distributed tracing (OpenTelemetry)
   - Add performance metrics (Prometheus)

3. **SSE Reliability:**
   - Implement reconnection logic with exponential backoff
   - Add heartbeat/keepalive messages
   - Handle network interruptions gracefully

---

## 🔗 KEY FILES REFERENCE

### **Backend:**
- `src/api/routes/business_intelligence.py` - SSE endpoint
- `src/services/business_intelligence_service.py` - Telemetry storage
- `src/services/auth_service.py` - Token validation & caching
- `src/tasks/business_intelligence_tasks.py` - Telemetry capture points
- `src/core/logging.py` - Structured logging system
- `src/middleware/logging.py` - Request/response logging

### **Frontend:**
- `frontend/src/components/business-intelligence/TelemetryViewer.tsx` - SSE client
- `frontend/src/pages/business-intelligence/QuestionDetailPage.tsx` - Main UI

### **Database:**
- `src/models/business_intelligence.py` - BIAgentTelemetry model
- Table: `bi_agent_telemetry`

---

**Status:** Investigation ongoing - SSE auth failure needs deeper diagnosis

