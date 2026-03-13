# SSE Telemetry Investigation & Resolution

## Problem Statement

**Issue:** TelemetryViewer shows SSE connection errors in browser console despite the backend SSE endpoint working correctly.

**Symptoms:**
```javascript
SSE connection error: Event {isTrusted: true, ...}
```

---

## Investigation Steps

### Step 1: Verify Backend SSE Endpoint ✅

**Test Command:**
```bash
curl -N "http://localhost:5001/v1/bi/questions/q_37f2a36b3247/telemetry?token=<valid_jwt>"
```

**Result:**
```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Transfer-Encoding: chunked
```

✅ **Backend is working correctly**

---

### Step 2: Verify NGINX Proxy ✅

**Test Command:**
```bash
curl -N "http://localhost:3000/v1/bi/questions/q_37f2a36b3247/telemetry?token=<valid_jwt>"
```

**Result:**
```
HTTP/1.1 200 OK
Server: nginx/1.29.1
Content-Type: text/event-stream; charset=utf-8
Transfer-Encoding: chunked
```

✅ **NGINX proxy is configured correctly for SSE**

**NGINX Configuration** (`frontend/nginx.conf` lines 29-56):
```nginx
location ~* ^/v1/bi/questions/.*/telemetry {
    proxy_pass http://app:5001;
    proxy_http_version 1.1;
    
    # Essential for SSE - disable buffering
    proxy_buffering off;
    proxy_cache off;
    
    # Chunked transfer encoding
    chunked_transfer_encoding on;
    
    # Keep connection alive
    proxy_read_timeout 3600s;
    proxy_connect_timeout 75s;
    
    # Headers
    proxy_set_header Connection '';
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # SSE-specific headers
    proxy_set_header Cache-Control 'no-cache';
    proxy_set_header X-Accel-Buffering 'no';
}
```

✅ **All SSE requirements met:**
- ✅ Buffering disabled (`proxy_buffering off`)
- ✅ Caching disabled (`proxy_cache off`)
- ✅ Long timeout for streaming (3600s)
- ✅ Chunked encoding enabled
- ✅ SSE-specific headers set

---

### Step 3: Verify Frontend EventSource Code ✅

**TelemetryViewer.tsx** (lines 67-102):
```typescript
const sseUrl = `${apiUrl}/v1/bi/questions/${questionId}/telemetry?token=${encodeURIComponent(token)}`;
const eventSource = new EventSource(sseUrl, { withCredentials: false });

eventSource.onopen = () => {
  console.log('[SSE] Connection opened successfully');
  setIsConnected(true);
};

eventSource.onmessage = (event) => {
  try {
    const telemetryEvent: TelemetryEvent = JSON.parse(event.data);
    setEvents((prev) => [...prev, telemetryEvent]);
  } catch (error) {
    console.error('[SSE] Failed to parse telemetry event:', error);
  }
};

eventSource.onerror = (error) => {
  console.error('[SSE] Connection error. ReadyState:', eventSource.readyState);
  setIsConnected(false);
  eventSource.close();
};
```

✅ **Frontend code looks correct**

---

## Root Cause Analysis

### Hypothesis 1: Completed Questions Close SSE Immediately ✅ LIKELY

**Backend SSE Logic** (`business_intelligence.py` lines 389-398):
```python
if question_status in [QuestionStatus.COMPLETED, QuestionStatus.FAILED]:
    final_event = {
        "event_id": f"terminal-{uuid.uuid4().hex}",
        "event_type": "completed" if question_status == QuestionStatus.COMPLETED else "failed",
        "status": question_status.value,
        "message": "Processing completed" if question_status == QuestionStatus.COMPLETED else question_error,
        "timestamp": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    }
    yield f"data: {json.dumps(final_event)}\n\n"
    break  # ← This closes the SSE stream
```

**What happens:**
1. Browser opens SSE connection
2. Backend checks question status
3. Question is already `COMPLETED`
4. Backend sends completion event
5. Backend closes stream (`break`)
6. Browser's EventSource fires `onerror` event (this is expected behavior!)
7. TelemetryViewer logs error and closes connection

**This is NOT a bug - it's expected behavior!** ✅

The EventSource API always fires an `onerror` event when the connection closes, even if it's a graceful close by the server. This is a limitation of the EventSource API.

---

### Hypothesis 2: CORS Issues ❌ UNLIKELY

- Same origin (`http://localhost:3000` → `/v1/bi/...`)
- No CORS preflight required
- curl tests work fine

---

### Hypothesis 3: Auth Token Issues ❌ RESOLVED

- Was an issue (wrong localStorage key)
- Fixed in commit `46f4d3b5`
- Now using correct `'auth_token'` key

---

## The Fix

### Option 1: Graceful SSE Closure (Recommended) ✅

**Problem:** EventSource fires `onerror` when server closes connection, even gracefully.

**Solution:** Check for `completion` or `failed` events before treating errors as failures.

**Implementation:**
```typescript
eventSource.onmessage = (event) => {
  try {
    const telemetryEvent: TelemetryEvent = JSON.parse(event.data);
    setEvents((prev) => [...prev, telemetryEvent]);
    
    // Check if this is a terminal event
    if (telemetryEvent.event_type === 'completed' || telemetryEvent.event_type === 'failed') {
      console.log('[SSE] Stream completed gracefully:', telemetryEvent.event_type);
      setTimeout(() => {
        if (eventSourceRef.current) {
          eventSourceRef.current.close();
        }
      }, 100); // Give time for final events to process
    }
  } catch (error) {
    console.error('[SSE] Failed to parse telemetry event:', error);
  }
};

eventSource.onerror = (error) => {
  // Check if we received a completion event first
  const hasCompletion = events.some(e => e.event_type === 'completed' || e.event_type === 'failed');
  
  if (hasCompletion) {
    console.log('[SSE] Connection closed after completion (expected)');
  } else {
    console.error('[SSE] Connection error:', error);
  }
  
  setIsConnected(false);
  if (eventSourceRef.current) {
    eventSourceRef.current.close();
  }
};
```

---

### Option 2: Hide SSE for Completed Questions ✅

**Problem:** SSE is only useful for *in-progress* questions.

**Solution:** Don't create SSE connection if question is already completed.

**Implementation:**
```typescript
useEffect(() => {
  if (!questionId) {
    setEvents([]);
    setIsConnected(false);
    return;
  }

  // Don't connect SSE for completed questions
  if (questionStatus === QuestionStatus.COMPLETED || questionStatus === QuestionStatus.FAILED) {
    console.log('[SSE] Question already completed, skipping SSE connection');
    return;
  }

  // ... rest of SSE connection code
}, [questionId, questionStatus]);
```

---

## Recommended Solution: Combination Approach

**Use both fixes:**

1. ✅ **Don't connect SSE for completed questions** - Avoids unnecessary connections
2. ✅ **Handle completion events gracefully** - Prevents error logs for in-progress → completed transitions

---

## Enhanced Debugging

**Added comprehensive logging** (commit `f1073086`):
```typescript
console.log(`[SSE] Connecting to: ${sseUrl.replace(/token=[^&]+/, 'token=***')}`);
console.log('[SSE] Connection opened successfully');
console.log('[SSE] Received event:', event.data.substring(0, 100) + '...');
console.error('[SSE] Connection error. ReadyState:', eventSource.readyState);
console.error('[SSE] Error type:', error.type);
```

**Debugging in Browser:**
1. Open console (`Cmd+Option+J`)
2. Look for `[SSE]` prefixed logs
3. Check `ReadyState`: 0=CONNECTING, 1=OPEN, 2=CLOSED

---

## Testing Steps

### Test Case 1: Completed Question (Current Issue)

**Steps:**
1. Navigate to question `q_37f2a36b3247` (completed)
2. Open browser console
3. Observe logs

**Expected Before Fix:**
```
[SSE] Connecting to: http://localhost:3000/v1/bi/questions/q_37f2a36b3247/telemetry?token=***
[SSE] Connection error. ReadyState: 2
```

**Expected After Fix:**
```
[SSE] Question already completed, skipping SSE connection
```

---

### Test Case 2: New Question (In Progress)

**Steps:**
1. Submit a new question
2. Observe SSE connection in real-time
3. Watch for status updates

**Expected:**
```
[SSE] Connecting to: http://localhost:3000/v1/bi/questions/q_xxx/telemetry?token=***
[SSE] Connection opened successfully
[SSE] Received event: {"event_type":"agent_started",...
[SSE] Received event: {"event_type":"tool_started",...
[SSE] Received event: {"event_type":"completed",...
[SSE] Stream completed gracefully: completed
```

---

## Summary

| Component | Status | Notes |
|-----------|--------|-------|
| Backend SSE endpoint | ✅ Working | Returns 200, text/event-stream |
| NGINX proxy | ✅ Configured | Buffering disabled, long timeout |
| Frontend EventSource | ✅ Correct | Uses proper API |
| Auth token | ✅ Fixed | Now uses `'auth_token'` key |
| **Issue** | ⚠️ **Expected Behavior** | SSE closes for completed questions |

**Root Cause:** EventSource API always fires `onerror` when connection closes, even gracefully.

**Fix:** Check question status before connecting + handle completion events gracefully.

**Status:** Ready to implement fixes.

