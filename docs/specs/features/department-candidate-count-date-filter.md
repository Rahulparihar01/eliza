# Department Candidate Count - Date Filter Spec

## Overview

When counting candidates per department from Greenhouse, we need to include both open and closed jobs. However, including ALL historical closed jobs could surface very old candidates (3-5+ years old) who are no longer relevant. This spec defines how to add a configurable lookback period for closed jobs.

## Current State

### Greenhouse API Fields Available on Jobs

```json
{
  "id": 12345,
  "name": "Senior Software Engineer",
  "status": "closed",  // "open", "closed", "draft"
  "opened_at": "2023-06-15T10:00:00.000Z",
  "closed_at": "2024-01-20T15:30:00.000Z",
  "created_at": "2023-06-01T09:00:00.000Z",
  "departments": [{"id": 100, "name": "Engineering"}],
  "offices": [{"id": 200, "name": "New York"}]
}
```

### Current Connector Methods

| Method | Purpose | Date Filters |
|--------|---------|--------------|
| `get_jobs(status_filter)` | Fetch jobs by status | None (returns all matching status) |
| `get_historical_jobs(closed_after)` | Fetch closed jobs | `closed_after`: Only jobs closed AFTER this date |
| `fetch_candidates(page, per_page)` | Fetch all candidates | `created_after` (from config) |
| `fetch_candidates_from_jobs(job_ids, applied_after)` | Fetch candidates for specific jobs | `applied_after`: Application date filter |

### Current Department Count Endpoint

```
GET /api/connectors/greenhouse/departments-with-counts?connector_id=xxx
```

Currently fetches ALL jobs (open + closed) and counts candidates. No date filter.

---

## Proposed Enhancement

### 1. API Endpoint Change

Add optional `closed_job_lookback_days` query parameter:

```
GET /api/connectors/greenhouse/departments-with-counts
    ?connector_id=xxx
    &closed_job_lookback_days=365
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connector_id` | string | required | Greenhouse connector ID |
| `closed_job_lookback_days` | int | 365 | Max age (in days) for closed jobs to include. Open jobs are always included. |

### 2. Counting Logic

```
FOR each department:
  candidates_count = 0
  
  // Always count candidates from OPEN jobs
  FOR each OPEN job in department:
    candidates_count += candidates_who_applied_to(job)
  
  // Only count candidates from RECENT closed jobs
  cutoff_date = today - closed_job_lookback_days
  FOR each CLOSED job in department WHERE closed_at >= cutoff_date:
    candidates_count += candidates_who_applied_to(job)
  
  RETURN candidates_count
```

### 3. Frontend UI Update

Add a simple selector in the New Analysis Modal's candidate source section:

```
[ ] Include candidates from closed jobs
    └── Look back: [▾ 1 year ▾] (6 months, 1 year, 2 years, 3 years)
```

**Default**: 1 year (365 days)  
**Options**: 6 months (180), 1 year (365), 2 years (730), 3 years (1095)

---

## Implementation Details

### Backend Changes

#### File: `src/api/routes/connectors.py`

```python
@router.get("/greenhouse/departments-with-counts")
async def list_greenhouse_departments_with_candidate_counts(
    connector_id: str = Query(..., description="Greenhouse connector ID"),
    closed_job_lookback_days: int = Query(
        365, 
        ge=30,  # Minimum 30 days
        le=1825,  # Maximum 5 years
        description="Max age in days for closed jobs to include (open jobs always included)"
    ),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # ... existing setup code ...
    
    # Calculate cutoff date for closed jobs
    from datetime import datetime, timezone, timedelta
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=closed_job_lookback_days)
    
    # Fetch OPEN jobs (always included)
    open_jobs = await connector.get_jobs(status_filter="open")
    
    # Fetch CLOSED jobs, filtered by closed_at date
    closed_jobs = await connector.get_historical_jobs(closed_after=cutoff_date)
    
    # Combine for counting
    all_relevant_jobs = open_jobs + closed_jobs
    
    # Build job_id -> department_ids mapping
    job_to_depts: Dict[int, List[int]] = {}
    for job in all_relevant_jobs:
        job_id = job.get("id")
        dept_ids = job.get("department_ids", [])
        if job_id:
            job_to_depts[job_id] = dept_ids
    
    # ... rest of candidate counting logic (unchanged) ...
```

### Frontend Changes

#### File: `frontend/src/components/talent-intelligence/NewAnalysisModal.tsx`

Add state and UI for the lookback selector in the candidate source section:

```typescript
// State
const [closedJobLookbackDays, setClosedJobLookbackDays] = useState<number>(365);

// In loadDepartmentsWithCounts:
const response = await AXIOS_INSTANCE.get(
  `/api/connectors/greenhouse/departments-with-counts?connector_id=${connectorId}&closed_job_lookback_days=${closedJobLookbackDays}`
);

// UI (in candidate source section, after department selection)
<div className="mt-3 pt-3 border-t border-border">
  <label className="flex items-center gap-2 text-sm">
    <input
      type="checkbox"
      checked={includeClosedJobs}
      onChange={(e) => setIncludeClosedJobs(e.target.checked)}
      className="..."
    />
    Include candidates from closed positions
  </label>
  
  {includeClosedJobs && (
    <div className="mt-2 ml-6 flex items-center gap-2">
      <span className="text-xs text-muted">Look back:</span>
      <select
        value={closedJobLookbackDays}
        onChange={(e) => setClosedJobLookbackDays(Number(e.target.value))}
        className="..."
      >
        <option value={180}>6 months</option>
        <option value={365}>1 year</option>
        <option value={730}>2 years</option>
        <option value={1095}>3 years</option>
      </select>
    </div>
  )}
</div>
```

---

## Edge Cases & Considerations

### 1. Jobs Without `closed_at` Date
Some closed jobs might not have a `closed_at` timestamp (data quality issue in Greenhouse).

**Decision**: Include these jobs by default (err on the side of showing more candidates)

```python
# In get_historical_jobs()
if closed_at_str:
    closed_at = parse_date(closed_at_str)
    if closed_at >= cutoff_date:
        include_job()
else:
    # No closed_at date - include by default
    include_job()
```

### 2. Performance with Large Lookback
Longer lookback periods = more jobs = more candidates to count = slower API response.

**Mitigations**:
- Keep max_pages limit (currently 50 = 5000 candidates)
- Add response header with actual counts for transparency
- Consider caching department counts (refresh on connector sync)

### 3. "Include Historical Candidates" Toggle Already Exists
The modal already has a toggle for "Include previous candidates" with a lookback days input. 

**Decision**: 
- The existing toggle controls whether to include candidates from **closed jobs for analysis**
- This new filter controls which **departments show accurate candidate counts** in the selection UI
- These are complementary, not redundant

---

## API Response Enhancement

Add metadata to help users understand what they're seeing:

```json
{
  "departments": [
    {
      "id": 100,
      "name": "Engineering",
      "candidate_count": 247,
      "open_job_count": 5,
      "closed_job_count": 12
    }
  ],
  "meta": {
    "closed_job_lookback_days": 365,
    "cutoff_date": "2024-01-08T00:00:00Z",
    "total_open_jobs": 15,
    "total_closed_jobs_included": 38,
    "total_candidates_counted": 892
  }
}
```

---

## Testing Checklist

- [ ] Verify `closed_at` field is present in Greenhouse job responses
- [ ] Test with 0 closed jobs (only open)
- [ ] Test with only closed jobs (no open)
- [ ] Test lookback boundary (job closed exactly at cutoff)
- [ ] Test jobs missing `closed_at` field
- [ ] Verify performance with large lookback (3 years)
- [ ] Frontend correctly passes lookback parameter
- [ ] Candidate counts match manual verification

---

## Timeline

| Phase | Task | Estimate |
|-------|------|----------|
| 1 | Backend: Add query param + filtering logic | 1 hour |
| 2 | Backend: Enhanced response with metadata | 30 min |
| 3 | Frontend: Add lookback selector UI | 1 hour |
| 4 | Testing with real Greenhouse data | 1 hour |
| **Total** | | **3.5 hours** |

