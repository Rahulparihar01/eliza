# Timeline Display Troubleshooting Guide

## Issue Summary

**Problem:** Agent Execution Timeline not displaying in the UI despite data existing in the database.

**Root Cause:** LocalStorage authentication token key mismatch between authentication system and timeline fetch logic.

---

## Diagnostic Process

### Step 1: Verify Data Exists
```sql
-- Check if question has a session
SELECT q.id, q.question_id, q.status, s.id as session_id 
FROM bi_questions q 
LEFT JOIN bi_analysis_sessions s ON q.id = s.question_id 
WHERE q.question_id = 'q_37f2a36b3247';

-- Check tool executions
SELECT COUNT(*) FROM bi_tool_executions WHERE session_id = 14;
-- Result: 4 tool executions

-- Check agent responses  
SELECT COUNT(*) FROM bi_agent_responses WHERE session_id = 14;
-- Result: 2 agent responses
```

✅ **Data exists** - The timeline tracking is working correctly on the backend.

### Step 2: Check API Endpoint
```bash
# Timeline endpoint returns 401
GET /v1/bi/questions/q_37f2a36b3247/timeline -> 401

# Other endpoints work fine
GET /v1/bi/questions/q_37f2a36b3247 -> 200
GET /v1/bi/questions/q_37f2a36b3247/result -> 200
```

❌ **Timeline endpoint fails with 401 Unauthorized**

### Step 3: Browser Console Analysis
```
Error: Failed to fetch timeline (401)
Error: Authentication failed. Token: missing
```

❌ **Token is missing** from the fetch request

### Step 4: Code Investigation

**Auth System (Correct):**
```typescript
// AuthContext.tsx line 100
localStorage.setItem('auth_token', response.access_token);

// api-client.ts line 22
const token = localStorage.getItem('auth_token');
```

**Timeline Fetch (Incorrect):**
```typescript
// BusinessIntelligenceQA.tsx line 106 (BEFORE FIX)
const token = localStorage.getItem('access_token'); // ❌ WRONG KEY!
```

---

## The Fix

### Change Made
```typescript
// BEFORE (incorrect):
const token = localStorage.getItem('access_token');

// AFTER (correct):
const token = localStorage.getItem('auth_token');
```

### Files Modified
1. **`frontend/src/pages/business-intelligence/BusinessIntelligenceQA.tsx`**
   - Line 106: Changed localStorage key from `'access_token'` to `'auth_token'`

---

## Why This Happened

**Timeline Feature Added After Auth System:**
The timeline fetch functionality was added as a new feature and used the generic key name `'access_token'`, not realizing the existing auth system uses `'auth_token'` as the key.

**Silent Failure:**
The original code silently swallowed 401 errors without logging details, making the issue hard to diagnose:

```typescript
// BEFORE (no error logging):
if (response.ok) {
  const data = await response.json();
  setTimelineData(data);
}
// Errors were silently ignored!

// AFTER (with error logging):
if (response.ok) {
  const data = await response.json();
  setTimelineData(data);
} else {
  const errorData = await response.json().catch(() => ({ message: 'Unknown error' }));
  console.error(`Failed to fetch timeline (${response.status}):`, errorData);
  if (response.status === 401) {
    console.error('Authentication failed. Token:', token ? 'present' : 'missing');
  }
}
```

---

## Testing the Fix

### 1. Hard Refresh the Browser
```
Mac: Cmd + Shift + R
Windows/Linux: Ctrl + Shift + R
```

### 2. Open Browser Console
```
Mac: Cmd + Option + J
Windows/Linux: Ctrl + Shift + J
```

### 3. Click on a Completed Question

**Expected Result:**
- ✅ No 401 errors in console
- ✅ Timeline loads successfully
- ✅ Shows enriched prompt, tool executions, agent responses, telemetry

**If Still Seeing Errors:**
- Check that you're logged in (token exists in localStorage)
- Verify container has latest code: `docker-compose ps frontend`
- Check frontend container was rebuilt: `docker-compose build frontend`

---

## Related Issues

### SSE Connection Errors (TelemetryViewer)

The browser console also shows SSE connection errors for real-time telemetry streaming:

```
SSE connection error: Event {isTrusted: true, ...}
```

**Status:** Not critical for viewing completed questions
- Real-time telemetry uses Server-Sent Events (SSE)
- Only needed for *live* question processing
- Completed questions display full timeline without SSE
- SSE errors can be safely ignored for now

**Future Enhancement:**
If real-time streaming is needed, investigate:
1. NGINX SSE proxy configuration
2. EventSource CORS settings
3. Token passing for SSE endpoints

---

## Prevention Guidelines

### For Future API Endpoints:

1. **Use Consistent Token Keys:**
   ```typescript
   // ✅ ALWAYS use 'auth_token'
   const token = localStorage.getItem('auth_token');
   
   // ❌ DON'T create new keys
   const token = localStorage.getItem('access_token'); // NO!
   const token = localStorage.getItem('jwt_token'); // NO!
   ```

2. **Add Error Logging:**
   ```typescript
   if (!response.ok) {
     console.error(`API Error (${response.status}):`, await response.json());
   }
   ```

3. **Use Axios Instance:**
   ```typescript
   // Prefer using the configured Axios instance
   // which automatically adds auth headers
   import { AXIOS_INSTANCE } from '../services/api-client';
   const response = await AXIOS_INSTANCE.get(`/v1/bi/questions/${id}/timeline`);
   ```

4. **Check Auth Setup:**
   - Review `AuthContext.tsx` for token storage keys
   - Review `api-client.ts` for interceptor logic
   - Search codebase: `grep -r "localStorage.*token" frontend/src/`

---

## Commits

1. **`46f4d3b5`** - fix: Use correct localStorage key 'auth_token' for timeline fetch
2. **`29120023`** - feat: Add detailed error logging for timeline fetch failures
3. **`ce39e245`** - fix: Pass database session to SettingsService in upload endpoint

---

## Summary

| Issue | Root Cause | Resolution | Status |
|-------|-----------|------------|--------|
| Timeline 401 errors | localStorage key mismatch (`access_token` vs `auth_token`) | Changed to use correct `auth_token` key | ✅ Fixed |
| Silent failures | No error logging in fetch handler | Added detailed console logging | ✅ Fixed |
| Document upload 500 | Missing `db` parameter in SettingsService | Pass db session to constructor | ✅ Fixed |
| SSE connection errors | EventSource connection issues | Non-critical for completed questions | ⚠️ Known Issue |

**All critical issues resolved. Timeline should now display correctly! 🎉**

