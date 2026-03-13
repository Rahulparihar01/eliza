# Candidate Outreach Search Improvements

**Date**: October 24, 2025  
**Status**: ✅ Complete  
**Issue**: Job search not working well in candidate outreach section

## Problem

The Greenhouse job dropdown on the Candidate Outreach page (`/talent/outreach`) was:
1. Not loading jobs (500 error from backend)
2. Search only looked at job titles
3. No visual feedback for search results
4. No way to clear search
5. Generic error messages

## Root Cause

**Backend Issue**: The connector had `use_shared_credentials=True` which triggered a `NotImplementedError`:
```python
NotImplementedError: Shared credentials not yet implemented
```

This prevented the API from retrieving credentials and listing jobs.

## Solutions Implemented

### 1. Backend Fix
**File**: `connector_configurations` table

**Change**:
```sql
UPDATE connector_configurations 
SET use_shared_credentials = false 
WHERE connector_id = 'greenhouse_job_board_eliza';
```

**Result**: ✅ Connector can now retrieve credentials and list jobs

### 2. Enhanced Search Filtering
**File**: `frontend/src/pages/talent-intelligence/CandidateOutreachPage.tsx`

**Before**: Only searched job titles
```typescript
greenhouseJobs.filter((job) =>
  job.title.toLowerCase().includes(searchQuery.toLowerCase())
)
```

**After**: Searches titles, locations, AND departments
```typescript
const query = searchQuery.toLowerCase().trim();
const filteredJobs = greenhouseJobs.filter((job) => {
  if (!query) return true;
  
  const titleMatch = job.title?.toLowerCase().includes(query);
  const locationMatch = job.location?.toLowerCase().includes(query);
  const departmentMatch = job.departments?.some((dept: string) =>
    dept.toLowerCase().includes(query)
  );
  
  return titleMatch || locationMatch || departmentMatch;
});
```

**Examples**:
- Search "engineering" → Matches "Engineering Manager" + all jobs in "Engineering" dept
- Search "san francisco" → Matches all jobs in SF
- Search "remote" → Matches all remote positions

### 3. Clear Button
Added an "X" button to clear search and reset selection:

```typescript
{searchQuery && (
  <button
    onClick={() => {
      setSearchQuery('');
      setSelectedJobId(null);
    }}
    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-text transition-colors"
    title="Clear search"
  >
    <XMarkIcon className="w-4 h-4" />
  </button>
)}
```

### 4. Job Count Indicator
Shows how many jobs are available:

```typescript
{!loadingJobs && greenhouseJobs.length > 0 && (
  <span className="text-xs text-muted">
    {greenhouseJobs.length} {greenhouseJobs.length === 1 ? 'job' : 'jobs'} available
  </span>
)}
```

### 5. "No Results" Message
When search yields no matches:

```typescript
if (filteredJobs.length === 0) {
  return (
    <div className="p-4 text-center text-sm text-muted">
      <p>No jobs match "{searchQuery}"</p>
      <p className="text-xs mt-1">
        Try searching by job title, location, or department
      </p>
    </div>
  );
}
```

### 6. Better Error Messages
**Before**:
```
No jobs available. Check your Greenhouse connector.
```

**After**:
```
No jobs available
Check your Greenhouse Job Board connector configuration.
Connector ID: greenhouse_job_board_eliza
```

### 7. Enhanced Logging
Added console logging for debugging:

```typescript
console.log('Loading Greenhouse jobs from connector:', greenhouseConnectorId);
console.log('Greenhouse jobs loaded:', response.data);
console.error('Error details:', {
  message: error?.message,
  status: error?.response?.status,
  data: error?.response?.data
});
```

### 8. Improved Placeholder Text
**Before**: "Search jobs by title..."

**After**: "Search jobs by title, location, or department..."

## UI/UX Improvements

| Feature | Before | After |
|---------|--------|-------|
| **Search Scope** | Title only | Title + Location + Department |
| **Clear Search** | ❌ Not available | ✅ X button clears search |
| **Job Count** | ❌ Not shown | ✅ "X jobs available" |
| **No Results** | Generic message | ✅ Helpful message with tips |
| **Error Details** | Generic | ✅ Shows connector ID |
| **Loading State** | Basic | ✅ Clear "Loading jobs..." |

## Visual Examples

### Search Flow:

1. **Initial State**:
   ```
   Search: [                                ] 
   50 jobs available
   ↓
   [Engineering Manager]
   [Senior Software Engineer]
   [Product Manager]
   ...
   ```

2. **Typing "engineer"**:
   ```
   Search: [engineering                 [x]]
   ↓
   [Engineering Manager] ← Title match
   [Senior Software Engineer] ← Title match  
   [DevOps Engineer] ← Title match
   [Product Manager] ← Dept: "Engineering"
   ```

3. **Typing "san francisco"**:
   ```
   Search: [san francisco              [x]]
   ↓
   [Engineering Manager] 
   📍 San Francisco, CA • Engineering
   
   [Product Manager]
   📍 San Francisco, CA • Product
   ```

4. **No Matches**:
   ```
   Search: [xyz                        [x]]
   ↓
   No jobs match "xyz"
   Try searching by job title, location, or department
   ```

## Testing

### Manual Test Steps:

1. ✅ **Load Jobs**:
   - Go to `/talent/outreach`
   - Select a market candidate
   - Jobs should load automatically
   - Should see "X jobs available"

2. ✅ **Search by Title**:
   - Type "engineering"
   - Should see all engineering roles

3. ✅ **Search by Location**:
   - Type "san francisco" or "remote"
   - Should see matching locations

4. ✅ **Search by Department**:
   - Type department name
   - Should see all jobs in that department

5. ✅ **Clear Search**:
   - Type something
   - Click X button
   - Search should clear and show all jobs

6. ✅ **No Results**:
   - Type nonsense: "xyz123"
   - Should see helpful "No jobs match" message

## Files Modified

### Frontend:
- ✅ `frontend/src/pages/talent-intelligence/CandidateOutreachPage.tsx`
  - Enhanced search filtering (+30 lines)
  - Added clear button
  - Added job count
  - Improved error messages
  - Better logging

### Backend:
- ✅ Database: Fixed `use_shared_credentials` flag
- ✅ `scripts/update_greenhouse_connectors.py`: Updated to set correct flag

### Documentation:
- ✅ `docs/20251024_CANDIDATE_OUTREACH_SEARCH_IMPROVEMENTS.md` (this file)

## Success Criteria

- ✅ Jobs load successfully (no 500 error)
- ✅ Search works across title, location, department
- ✅ Clear button resets search
- ✅ Job count displays correctly
- ✅ "No results" message shows when needed
- ✅ Error messages are helpful with connector ID
- ✅ Console logging aids debugging
- ⏳ User can successfully find and select jobs
- ⏳ User can submit candidates to Greenhouse

## Next Steps

1. **Test Job Submission**:
   - Select a job
   - Click "Add to Greenhouse"
   - Verify candidate is submitted

2. **Verify in Greenhouse**:
   - Log into Greenhouse ATS
   - Check job applications
   - Confirm candidate appears

---

**The search functionality is now much more powerful and user-friendly!** Users can search by job title, location, or department, see clear results, and easily reset their search. 🎉

