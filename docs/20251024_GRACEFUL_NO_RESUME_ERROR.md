# Graceful "No Resumes" Error Handling

**Date**: October 24, 2025  
**Status**: ✅ Complete

## Problem

When Greenhouse candidates don't have resume attachments, the system returned a generic 400 error:
```
"No resumes found in Greenhouse with current filters. Try adjusting your query parameters."
```

This was:
- ❌ Not helpful (no explanation of WHY)
- ❌ No context (how many candidates were checked?)
- ❌ No actionable solutions
- ❌ User frustrated

## Solution

Implemented detailed, actionable error message that explains:
1. **What happened**: How many candidates were checked
2. **Why it failed**: None had resume attachments
3. **What to do**: 3 specific solutions
4. **Context**: Why this is common with Greenhouse

## Implementation

**File**: `src/api/routes/ml_talent.py`

### Before:
```python
if not resume_files:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"No resumes found in Greenhouse with current filters. Try adjusting your query parameters."
    )
```

### After:
```python
if not resume_files:
    # Provide detailed, actionable error message
    candidates_fetched = sync_results.get("candidates_fetched", 0)
    candidates_filtered = sync_results.get("candidates_filtered", 0)
    
    error_message = f"No resume attachments found among {candidates_fetched} candidates from Greenhouse."
    
    if candidates_filtered > 0:
        error_message += f" ({candidates_filtered} candidates were filtered out based on your criteria)"
    
    error_message += "\n\n💡 Possible solutions:\n"
    error_message += "1. Use a different data source (Filesystem connector) for applicants with uploaded resumes\n"
    error_message += "2. Adjust your filters to include more candidates (remove status/date filters)\n"
    error_message += "3. Ask candidates to upload resumes in Greenhouse before running analysis\n"
    error_message += f"\nNote: Greenhouse returned {candidates_fetched} candidates, but none had resume attachments. "
    error_message += "This is common if candidates were added manually or applied through job boards without uploading files."
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_message
    )
```

## Error Message Examples

### Example 1: 100 candidates, 0 with resumes
```
No resume attachments found among 100 candidates from Greenhouse.

💡 Possible solutions:
1. Use a different data source (Filesystem connector) for applicants with uploaded resumes
2. Adjust your filters to include more candidates (remove status/date filters)
3. Ask candidates to upload resumes in Greenhouse before running analysis

Note: Greenhouse returned 100 candidates, but none had resume attachments. This is common if candidates were added manually or applied through job boards without uploading files.
```

### Example 2: 25 candidates, 75 filtered out
```
No resume attachments found among 25 candidates from Greenhouse. (75 candidates were filtered out based on your criteria)

💡 Possible solutions:
1. Use a different data source (Filesystem connector) for applicants with uploaded resumes
2. Adjust your filters to include more candidates (remove status/date filters)
3. Ask candidates to upload resumes in Greenhouse before running analysis

Note: Greenhouse returned 25 candidates, but none had resume attachments. This is common if candidates were added manually or applied through job boards without uploading files.
```

## User Experience

### Before:
```
User: *clicks Run Analysis*
System: 400 Bad Request - "No resumes found. Try adjusting your query parameters."
User: 😕 "What query parameters? How many candidates were there?"
```

### After:
```
User: *clicks Run Analysis*
System: 400 Bad Request with detailed message showing:
  - "100 candidates checked"
  - "None had resume attachments"
  - 3 specific solutions
  - Explanation of why this happens
User: 😊 "Oh, I'll use the Filesystem connector instead!"
```

## Query Parameter Verification

✅ **CONFIRMED**: Test query and analysis query use the **same parameters**

### Test Query:
```python
# src/api/routes/connectors.py
connector = GreenhouseConnector(
    credentials=credentials,
    config=query_params,  # ← User's query params
    customer_id=current_user.customer_id
)
```

### Analysis Query:
```python
# src/api/routes/ml_talent.py
sync_config = dict(connector_config.sync_config or {})
if request.greenhouse_query_params:
    # Merge in user's query params
    sync_config["job_ids"] = ...
    sync_config["application_status"] = ...
    sync_config["created_after"] = ...
    sync_config["max_candidates"] = ...

connector_instance = GreenhouseConnector(
    credentials=credentials,
    config=sync_config,  # ← Same params as test query!
    customer_id=current_user.customer_id
)
```

**Result**: Parameters match ✅

## Benefits

1. ✅ **Clear Communication**: User knows exactly what happened
2. ✅ **Actionable Solutions**: 3 specific next steps
3. ✅ **Context**: Understands why Greenhouse candidates often lack resumes
4. ✅ **Transparency**: Shows how many candidates were checked
5. ✅ **Better UX**: User doesn't feel stuck or confused

## Related Improvements

1. ✅ Test query returns actual candidate count
2. ✅ per_page respects max_candidates
3. ✅ Graceful error for no resumes
4. ⏳ Move resume fetching to background (future improvement)

## Testing

### Test Case: No Resumes Found
```
1. Configure Greenhouse with filters that return candidates without resumes
2. Click "Run Analysis"
3. Wait for fetch to complete
4. Should see detailed error message with:
   - Candidate count
   - Filter info (if any filtered out)
   - 3 solutions
   - Explanation
```

Expected error message format:
```
No resume attachments found among {N} candidates from Greenhouse. 
({M} candidates were filtered out based on your criteria)

💡 Possible solutions:
1. Use a different data source (Filesystem connector) for applicants with uploaded resumes
2. Adjust your filters to include more candidates (remove status/date filters)
3. Ask candidates to upload resumes in Greenhouse before running analysis

Note: Greenhouse returned {N} candidates, but none had resume attachments. 
This is common if candidates were added manually or applied through job boards without uploading files.
```

## Files Changed

- `src/api/routes/ml_talent.py` - Enhanced error message
- `docs/20251024_GRACEFUL_NO_RESUME_ERROR.md` - This documentation

## Next Steps

**Immediate**: ✅ Error message is now helpful and actionable

**Future**: Consider moving resume fetching to background task so errors appear on the progress page instead of blocking the API response.

