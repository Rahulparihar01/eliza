# Talent Intelligence API Mismatch - Resolution Plan
**Date**: October 14, 2025, 09:15 AM PST

## Issue Discovered

The frontend is calling the wrong API and there's a design mismatch:

### Current State
- **Frontend**: Using `/api/talent/analyze` (old API)
- **Backend**: ML Talent API is at `/v1/ml-talent/analyze`
- **Design Mismatch**: 
  - Backend expects `multipart/form-data` with file uploads
  - Frontend workflow uses data connector ID (no file upload UI)

## Resolution Steps

### 1. ✅ Regenerated Orval Types
- Ran `npx orval` to get latest ML Talent API types
- Confirmed `/v1/ml-talent/analyze` is in OpenAPI spec

### 2. ✅ Updated Frontend Imports  
- Changed from `useStartTalentAnalysis` (old API)
- To `useStartMlTalentAnalysisV1MlTalentAnalyzePost` (new ML API)

### 3. ⏳ Backend Needs Update
**Problem**: ML Talent API requires file uploads:
```typescript
{
  job_description: string,
  ideal_candidate_description: string,
  role: string,
  applicant_resumes: File[]  // ← Requires actual files
}
```

**But Frontend Has**: Data source connector ID (not files)

### 4. Two Options

#### Option A: Add Connector-Based Endpoint (Recommended)
Create new endpoint: `POST /v1/ml-talent/analyze-from-connector`

```python
@router.post("/analyze-from-connector")
async def start_ml_talent_analysis_from_connector(
    job_description: str,
    ideal_candidate_description: str,
    data_source_connector_id: str,  # ← Use connector instead of files
    baseline_employee_ids: List[int],
    role: str = "Machine Learning Engineer",
    ...
):
    # 1. Fetch resume files from connector
    # 2. Pass to existing TalentIntelligenceOrchestrator
    # 3. Return analysis_id
```

**Benefits**:
- Keeps existing file upload endpoint
- Adds connector-based workflow
- Matches our UI design

#### Option B: Modify Frontend to Upload Files
Add file upload UI in Step 2 instead of connector selection.

**Drawbacks**:
- Breaks our connector-based architecture
- User has to manually upload instead of using existing connections
- Less elegant workflow

## Recommendation: Implement Option A

### Implementation Plan

1. **Add new endpoint** in `src/api/routes/ml_talent.py`:
   ```python
   @router.post("/analyze-from-connector")
   async def start_ml_talent_analysis_from_connector(...)
   ```

2. **Fetch resumes from connector**:
   ```python
   connector_service = ConnectorService(db)
   connector = connector_service.get_configuration(data_source_connector_id)
   
   # Get connector instance
   from src.services.ingestion.connectors.filesystem_connector import FileSystemConnector
   fs_connector = FileSystemConnector(connector.sync_config)
   
   # List and read resume files
   files = await fs_connector.list_files()
   resume_files = [(await fs_connector.read_file(f), f) for f in files]
   ```

3. **Create request and run analysis** (same as existing endpoint)

4. **Update frontend** to use new endpoint

5. **Regenerate Orval types** and update imports

## Current Status

- [x] Identified the issue
- [x] Updated frontend to use correct import path
- [ ] Backend endpoint needs connector support
- [ ] Frontend needs to call correct endpoint with connector_id
- [ ] End-to-end test

## Next Steps

1. Implement `/analyze-from-connector` endpoint
2. Update frontend to use it
3. Test full workflow
4. Monitor backend logs

## Files to Modify

1. `src/api/routes/ml_talent.py` - Add new endpoint
2. `frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx` - Update API call
3. Regenerate Orval types after backend changes

## Expected Timeline

- Backend changes: 30 minutes
- Frontend updates: 15 minutes
- Testing: 15 minutes
- **Total: ~1 hour**

## Why This Happened

The ML Talent system was built to accept direct file uploads (like the original spec), but our UI evolved to use the connector-based architecture (which is better for production). Now we need to bridge the gap.

This is actually a **good architectural improvement** - separating data ingestion (connectors) from analysis (ML Talent) is cleaner!


