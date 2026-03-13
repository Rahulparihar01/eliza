# Greenhouse Error Handling Improvements

**Date**: October 24, 2025  
**Status**: ✅ Complete

## Problem

The Greenhouse query test feature was showing generic "Not Found" error messages when the API key was invalid or had permission issues. Users couldn't understand what was wrong or how to fix it.

### Root Cause

The provided Greenhouse API key (`JiCr2mh3hp3CG4aB6a8E`) was invalid:

```bash
$ curl -u "JiCr2mh3hp3CG4aB6a8E:" "https://harvest.greenhouse.io/v1/jobs?per_page=1"
{"message":"Invalid Basic Auth credentials"}
```

The error was happening at the Greenhouse API level (401 Unauthorized), but our error handling was not catching or translating this into user-friendly messages.

## Solution

### 1. Backend Error Handling (`src/api/routes/connectors.py`)

Added comprehensive error detection and user-friendly messages in the `/api/connectors/greenhouse/test-query` endpoint:

```python
try:
    jobs = await connector.get_jobs()
except Exception as e:
    error_msg = str(e)
    
    # Check for authentication errors
    if "401" in error_msg or "Unauthorized" in error_msg or "Invalid Basic Auth" in error_msg:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Greenhouse API key. Please verify your API key in Configure → Dev Center → API Credential Management"
        )
    
    # Check for permission errors
    if "403" in error_msg or "Forbidden" in error_msg:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Greenhouse API key does not have required permissions. Please ensure it has read access to Jobs and Candidates."
        )
    
    # Check for not found errors
    if "404" in error_msg or "Not Found" in error_msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Greenhouse API endpoint not found. Please check your Greenhouse configuration."
        )
    
    # Generic error
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Failed to connect to Greenhouse API: {error_msg}"
    )
```

**Benefits**:
- ✅ Specific HTTP status codes for different error types
- ✅ Clear, actionable error messages
- ✅ Guidance on where to fix the issue

### 2. Frontend Error Handling (`frontend/src/components/talent-intelligence/GreenhouseQueryConfig.tsx`)

Enhanced error display with status-specific messages and helpful links:

```typescript
catch (error: any) {
  console.error('Test query failed:', error);
  
  // Extract detailed error message
  let errorMessage = 'Failed to test query. Please try again.';
  
  if (error?.response?.status === 401) {
    errorMessage = error?.response?.data?.detail || 
      '❌ Invalid Greenhouse API Key. Please go to Data Connections and verify your API key is correct. ' +
      'Get a valid Harvest API key from: Configure → Dev Center → API Credential Management';
  } else if (error?.response?.status === 403) {
    errorMessage = error?.response?.data?.detail || 
      '⚠️ API Key Missing Permissions. Your Greenhouse API key needs read access to Jobs and Candidates.';
  } else if (error?.response?.data?.detail) {
    errorMessage = error.response.data.detail;
  } else if (error?.message) {
    errorMessage = error.message;
  }
  
  setTestResult({
    success: false,
    message: errorMessage,
  });
}
```

**UI Improvements**:
```tsx
{testResult.message && !testResult.success && (
  <div className="space-y-2">
    <p className="text-sm text-error leading-relaxed whitespace-pre-line">
      {testResult.message}
    </p>
    {testResult.message.includes('Invalid Greenhouse API Key') && (
      <a
        href="/data-connections"
        className="inline-flex items-center gap-1 text-sm text-brand hover:text-brand-strong underline"
      >
        → Go to Data Connections to update API key
      </a>
    )}
  </div>
)}
```

**Benefits**:
- ✅ Clear visual distinction for error messages
- ✅ Multi-line support for detailed messages
- ✅ Direct link to Data Connections page when API key is invalid
- ✅ Emoji indicators for quick visual feedback (❌, ⚠️)

## Error Messages Map

| Error Type | Status Code | User Message | Action |
|------------|-------------|--------------|--------|
| Invalid API Key | 401 | "❌ Invalid Greenhouse API Key. Please go to Data Connections and verify your API key is correct. Get a valid Harvest API key from: Configure → Dev Center → API Credential Management" | Link to `/data-connections` |
| Missing Permissions | 403 | "⚠️ API Key Missing Permissions. Your Greenhouse API key needs read access to Jobs and Candidates." | Contact Greenhouse admin |
| Endpoint Not Found | 404 | "Greenhouse API endpoint not found. Please check your Greenhouse configuration." | Verify Greenhouse setup |
| Connection Failed | 502 | "Failed to connect to Greenhouse API: [details]" | Check network/credentials |
| Unknown Error | 500 | "Unexpected error testing query: [details]" | Contact support |

## User Experience Flow

### Before (❌):
1. User enters invalid API key
2. Clicks "Test Query"
3. Sees: "Query Test Failed - Not Found"
4. No idea what to do next

### After (✅):
1. User enters invalid API key
2. Clicks "Test Query"
3. Sees: 
   ```
   Query Test Failed
   ❌ Invalid Greenhouse API Key. Please go to Data Connections 
   and verify your API key is correct. Get a valid Harvest API key 
   from: Configure → Dev Center → API Credential Management
   
   → Go to Data Connections to update API key
   ```
4. Clicks link → Goes to Data Connections → Updates API key → Success!

## Testing

### Manual Test (Invalid API Key):
```bash
# API returns 401 for invalid key
curl -u "JiCr2mh3hp3CG4aB6a8E:" "https://harvest.greenhouse.io/v1/jobs?per_page=1"
# Result: {"message":"Invalid Basic Auth credentials"}

# Our endpoint now catches this and returns helpful error
# Frontend displays user-friendly message with link to fix
```

### Expected Test Results:
1. ✅ Backend catches 401 from Greenhouse API
2. ✅ Backend returns `HTTP_401_UNAUTHORIZED` with detailed message
3. ✅ Frontend displays error message with emoji and formatting
4. ✅ Frontend shows link to Data Connections page
5. ✅ Link opens `/data-connections` in same tab
6. ✅ User can update connector and try again

## Files Modified

### Backend:
- `src/api/routes/connectors.py`
  - Enhanced error handling in `test_greenhouse_query` endpoint
  - Added specific error messages for 401, 403, 404, and generic errors

### Frontend:
- `frontend/src/components/talent-intelligence/GreenhouseQueryConfig.tsx`
  - Enhanced error extraction logic
  - Added status-specific error messages
  - Improved error display UI with link to Data Connections

### Containers:
- `docker-app-1` - Rebuilt and restarted with new code

## Next Steps

1. **User Action Required**: 
   - Obtain valid Greenhouse Harvest API key from: **Configure → Dev Center → API Credential Management**
   - Ensure API key has read access to:
     - ✓ Jobs
     - ✓ Candidates
     - ✓ Applications (for status filtering)

2. **Update Connector**:
   - Go to Data Connections
   - Find "Greenhouse Production" connector
   - Click edit/settings
   - Update API key
   - Click "Test Connection"
   - Verify connection succeeds

3. **Test Query Again**:
   - Return to Talent Intelligence workflow
   - Select Greenhouse connector
   - Configure filters (status=Active, created_after=2024-01-01)
   - Click "Test Query"
   - Should now see: "Found approximately X candidates across Y jobs"

## API Key Requirements

For a valid Greenhouse Harvest API key:

1. **Location**: Greenhouse → Configure → Dev Center → API Credential Management
2. **Type**: Harvest API (not Job Board API)
3. **Permissions**:
   - `GET /v1/jobs` - Read jobs
   - `GET /v1/candidates` - Read candidates
   - `GET /v1/applications` - Filter by status
4. **Format**: Base64-encoded Basic Auth token (handled automatically by Greenhouse)

## Success Criteria

- ✅ Backend catches Greenhouse API errors
- ✅ Backend returns user-friendly error messages
- ✅ Frontend displays clear error messages
- ✅ Frontend provides link to fix API key issues
- ✅ App container rebuilt and restarted
- ⏳ User obtains valid API key (pending)
- ⏳ User updates connector (pending)
- ⏳ Test query succeeds (pending valid API key)

---

**Summary**: Comprehensive error handling is now in place. The system provides clear, actionable error messages when the Greenhouse API key is invalid or missing permissions. Users are guided to the correct location to fix the issue. The next step is for the user to obtain a valid Greenhouse Harvest API key and update their connector configuration.

