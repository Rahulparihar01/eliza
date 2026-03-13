# Greenhouse Connector as Resume Source for Talent Analysis

**Date**: October 24, 2025  
**Status**: ✅ Complete

## Overview

Added support for using the Greenhouse Harvest API connector as a source of candidate resumes for the ML Talent Intelligence analysis workflow. Previously, only filesystem connectors were supported.

## Problem Statement

When users tried to run a talent analysis using the Greenhouse connector as the applicant data source, they received the error:

```
Connector type greenhouse not supported for resume analysis. Use 'filesystem' connector.
```

This prevented users from analyzing candidates already in their Greenhouse ATS system.

## Solution

### 1. Backend Changes

#### Updated `src/api/routes/ml_talent.py`

**Added Greenhouse Query Parameters to API Request:**
- Added `greenhouse_query_params` field to `StartAnalysisFromConnectorRequest`
- Allows frontend to pass Greenhouse-specific filters: `job_ids`, `application_status`, `created_after`, `max_candidates`

**Implemented Greenhouse Resume Fetching:**
```python
elif connector_config.connector_type == "greenhouse":
    # Get credentials
    credentials = connector_service.get_credentials(connector_config)
    
    # Merge sync_config with query params from request (request params override)
    sync_config = dict(connector_config.sync_config or {})
    if request.greenhouse_query_params:
        # Convert job_ids from comma-separated string to list
        # Merge other params: application_status, created_after, max_candidates
        ...
    
    # Initialize Greenhouse connector with merged config
    connector_instance = GreenhouseConnector(
        credentials=credentials,
        config=sync_config,
        customer_id=current_user.customer_id
    )
    
    # Sync candidates and download resumes (async operation)
    sync_results = loop.run_until_complete(connector_instance.sync())
    
    # Extract resume files from sync results
    resume_files = [(resume["file_bytes"], resume["filename"]) 
                    for resume in sync_results["resumes"]]
```

**Key Features:**
- Uses existing `GreenhouseConnector.sync()` method to fetch candidates and download resumes
- Supports all Greenhouse filtering options configured in the UI
- Limits to 50 resumes maximum (same as filesystem connector)
- Provides detailed logging of fetch results

### 2. Frontend Changes

#### Updated `frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx`

**Pass Greenhouse Query Params in Analysis Request:**
```typescript
startAnalysis({
  data: {
    job_description: config.jobDescription,
    ideal_candidate_description: config.idealCandidateDescription,
    data_source_connector_id: config.selectedConnectorId,
    baseline_employee_ids: employeeIds,
    role: "Machine Learning Engineer",
    greenhouse_query_params: config.greenhouseQueryParams || undefined  // ← NEW
  }
});
```

**Greenhouse Query Configuration Flow:**
1. User selects Greenhouse connector as data source
2. System redirects to `GreenhouseQueryConfig` step
3. User configures filters (jobs, status, date range, max candidates)
4. System tests query and shows candidate count
5. User continues to job description step
6. On "Run Analysis", query params are sent with the request

### 3. How It Works

**Full Workflow:**

1. **User Selects Greenhouse Connector**
   - In "Data Source" step, selects Greenhouse connector
   - System detects `connector_type === 'greenhouse'`

2. **Configure Search Filters**
   - User configures Greenhouse query parameters:
     - **Job IDs**: Comma-separated list of specific job IDs to filter by
     - **Application Status**: Filter by `active`, `rejected`, or `hired`
     - **Created After**: Only candidates created after this date (e.g., `2024-01-01`)
     - **Max Candidates**: Maximum number of candidates to analyze (1-50)

3. **Backend Fetches Resumes**
   - API receives query params in the request
   - Merges params with connector's `sync_config`
   - Initializes `GreenhouseConnector` with merged config
   - Calls `connector.sync()` which:
     - Fetches candidates from Greenhouse API with filters
     - Downloads resume attachments from S3 URLs
     - Returns list of `(file_bytes, filename)` tuples

4. **Analysis Proceeds Normally**
   - Resume files are passed to the talent analysis orchestrator
   - Standard ML Talent Intelligence pipeline runs:
     - Resume parsing with Docling VLM
     - Baseline profile creation
     - Market candidate search via PDL
     - Multi-dimensional scoring
     - Results synthesis

## Benefits

1. **Seamless ATS Integration**: Users can analyze candidates directly from Greenhouse without manual export/upload
2. **Powerful Filtering**: Supports job-specific, status-based, and date-range filtering
3. **Consistent UX**: Same workflow whether using filesystem or Greenhouse connectors
4. **Scalable**: Leverages existing Greenhouse connector infrastructure
5. **Maintains Limits**: Same 50-resume limit as filesystem for performance

## Technical Details

### Greenhouse API Integration

**Connector**: `src/services/ingestion/connectors/greenhouse.py`
- Uses Greenhouse Harvest API (`https://harvest.greenhouse.io/v1/`)
- Authenticates with Basic Auth (API key as username)
- Implements pagination for large candidate sets
- Downloads resume attachments from pre-signed S3 URLs

**Supported Filters:**
- `job_ids`: List of job IDs (e.g., `[123, 456]`)
- `application_status`: `"active"`, `"rejected"`, or `"hired"`
- `created_after`: ISO date string (e.g., `"2024-01-01"`)
- `max_candidates`: Integer (1-1000, limited to 50 for analysis)
- `include_prospects`: Boolean (default: `false`)
- `candidate_tags`: List of tags to filter by

### Configuration Precedence

**Request params override connector config:**
```python
sync_config = dict(connector_config.sync_config or {})  # Base config from DB
if request.greenhouse_query_params:  # Override with request params
    sync_config.update(request.greenhouse_query_params)
```

This allows:
- **Persistent config**: Store default filters in connector's `sync_config`
- **Per-analysis config**: Override filters for specific analysis runs
- **UI flexibility**: Configure filters per analysis without modifying connector

## Error Handling

**No Resumes Found:**
```
HTTPException(400, "No resumes found in Greenhouse with current filters. 
Try adjusting your query parameters.")
```

**Greenhouse API Errors:**
```
HTTPException(400, "Greenhouse sync failed: {error_messages}")
```

**Too Many Resumes:**
```
logger.warning(f"Found {len(resume_files)} resumes from Greenhouse, limiting to first 50")
resume_files = resume_files[:50]
```

## Logging

**Fetch Start:**
```
logger.info("fetching_resumes_from_greenhouse",
    analysis_id=analysis_id,
    connector_id=connector_config.connector_id,
    max_candidates=sync_config.get("max_candidates", 100),
    job_ids=sync_config.get("job_ids"),
    application_status=sync_config.get("application_status"),
    created_after=sync_config.get("created_after")
)
```

**Fetch Complete:**
```
logger.info("resumes_fetched_from_greenhouse",
    analysis_id=analysis_id,
    resume_count=len(resume_files),
    candidates_fetched=sync_results.get("candidates_fetched", 0),
    candidates_filtered=sync_results.get("candidates_filtered", 0)
)
```

## Testing

### Manual Test Steps

1. **Setup:**
   - Ensure Greenhouse connector is configured with valid API key
   - Verify connector is enabled: `is_enabled=true`

2. **Run Analysis:**
   ```bash
   # Navigate to Talent Intelligence page
   # Select baseline employees
   # Choose Greenhouse connector as data source
   # Configure query parameters (e.g., job_ids="12345", status="active")
   # Test query to verify candidate count
   # Provide job description
   # Click "Run Analysis"
   ```

3. **Verify:**
   ```bash
   # Check app logs for successful fetch
   docker logs docker-app-1 --tail=50 | grep "fetching_resumes_from_greenhouse"
   
   # Verify analysis started
   docker logs docker-celery-worker-1 --tail=50 | grep "ml_ta_"
   
   # Check database for new analysis
   docker exec docker-postgres-1 psql -U user -d ai_enablement -c \
     "SELECT id, status, created_at FROM talent_analyses ORDER BY created_at DESC LIMIT 5;"
   ```

## Files Modified

### Backend
- `src/api/routes/ml_talent.py` - Added Greenhouse support and query param handling

### Frontend
- `frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx` - Pass query params in request
- `frontend/src/generated/ml-talent-intelligence/ml-talent-intelligence.ts` - Regenerated API client

## Configuration Example

**Database Connector Config:**
```json
{
  "connector_id": "greenhouse_eliza_ee543205",
  "connector_type": "greenhouse",
  "credentials_encrypted": "...",
  "sync_config": {
    "application_status": "active",
    "max_candidates": 100,
    "include_prospects": false
  }
}
```

**Analysis Request:**
```json
{
  "job_description": "Senior ML Engineer...",
  "ideal_candidate_description": "Strong background in PyTorch...",
  "data_source_connector_id": "greenhouse_eliza_ee543205",
  "baseline_employee_ids": [1, 2, 3],
  "role": "Machine Learning Engineer",
  "greenhouse_query_params": {
    "job_ids": "12345,67890",
    "application_status": "active",
    "created_after": "2024-01-01",
    "max_candidates": 50
  }
}
```

## Future Enhancements

1. **Save Query Configs**: Allow users to save/load query configurations for reuse
2. **Bulk Analysis**: Support analyzing multiple jobs in a single run
3. **Incremental Sync**: Only fetch new candidates since last analysis
4. **Resume Quality Filter**: Filter candidates by resume completeness/quality
5. **Application Stage**: Filter by specific application stage (not just status)

## Related Documentation

- [Greenhouse Connector](../services/ingestion/connectors/greenhouse.py)
- [Talent Intelligence Flow](./api/TALENT_INTELLIGENCE_FLOW.md)
- [Greenhouse API Docs](https://developers.greenhouse.io/harvest.html)

## Impact

This feature enables a **seamless ATS integration** for the ML Talent Intelligence system. Users can now:
- Run analyses on candidates already in their ATS
- Filter by specific jobs, statuses, and date ranges
- Avoid manual resume exports and uploads
- Maintain a single source of truth (Greenhouse)

The implementation is **backwards compatible** - filesystem connectors continue to work exactly as before, and Greenhouse is simply added as an additional option.

