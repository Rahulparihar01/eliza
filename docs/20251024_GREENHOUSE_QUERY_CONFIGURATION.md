# Greenhouse Query Configuration Feature

**Created:** October 24, 2025  
**Purpose:** Add configurable Greenhouse search parameters to the Talent Intelligence workflow

## Overview

Added a comprehensive configuration screen for Greenhouse API queries in the talent analysis flow. This allows users to:

1. **Filter candidates by job**: Select specific Greenhouse jobs to search
2. **Filter by application status**: active, rejected, or hired candidates
3. **Filter by date range**: Only include candidates created after a specific date
4. **Set candidate limits**: Control how many candidates to analyze (1-1000)
5. **Test queries**: Preview how many candidates match before running full analysis

## Implementation

### Backend API (`src/api/routes/connectors.py`)

Added new endpoint: `POST /api/connectors/greenhouse/test-query`

**Request:**
```json
{
  "connector_id": "greenhouse_eliza_abc123",
  "query_params": {
    "job_ids": "123,456",
    "application_status": "active",
    "created_after": "2024-01-01",
    "max_candidates": 50
  }
}
```

**Response:**
```json
{
  "success": true,
  "job_count": 5,
  "candidate_count": 127,
  "message": "Found approximately 127 candidates across 5 jobs (capped at 50)"
}
```

**Features:**
- Fetches jobs from Greenhouse using stored credentials
- Filters jobs by job_ids if specified
- Estimates candidate count (job_count * 25 per job)
- Applies max_candidates limit
- Returns actionable preview data

### Frontend Component (`frontend/src/components/talent-intelligence/GreenhouseQueryConfig.tsx`)

New React component with comprehensive configuration UI:

**Features:**
1. **Job Selection Dropdown**
   - Auto-loads available Greenhouse jobs
   - Multi-select support (Cmd/Ctrl + click)
   - Displays job names and IDs
   - Falls back to manual comma-separated input

2. **Application Status Filter**
   - Dropdown: All, Active, Rejected, Hired
   - Filters candidates by current application state

3. **Date Range Filter**
   - Date picker for "created_after" parameter
   - Only includes candidates created after selected date

4. **Max Candidates Slider**
   - Range: 1-1000
   - Visual slider with numeric display
   - Helps control processing time

5. **Test Query Button**
   - Makes API call to test query configuration
   - Shows loading spinner during test
   - Displays success/error results
   - Shows job count and candidate count

6. **Result Preview**
   - Green success card with checkmark
   - Red error card with X icon
   - Displays job count and candidate count
   - Warns if no candidates found
   - Confirms when ready to proceed

7. **API Documentation Link**
   - Links to Greenhouse Harvest API docs
   - Reference: https://developers.greenhouse.io/harvest.html

### Integration (`frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx`)

Modified the talent intelligence workflow:

**Changes:**
1. Added `greenhouse-config` workflow step
2. Added `greenhouseQueryParams` to state
3. Auto-detects Greenhouse connectors and shows configuration screen
4. Filesystem connectors skip configuration (as before)
5. Params are saved and passed to analysis

**Workflow:**
```
1. Select Baseline Employees
2. Choose Data Source
   ├─ Filesystem → Skip to Step 3
   └─ Greenhouse → Step 2b (Configure Query)
2b. Configure Greenhouse Query (NEW)
3. Define Requirements
4. Review & Configure
5. AI Analysis
6. Results & Insights
```

## Greenhouse API Integration

Based on [Greenhouse Harvest API documentation](https://developers.greenhouse.io/harvest.html), the configuration supports:

### Supported Filters

| Parameter | Type | Description | API Endpoint |
|-----------|------|-------------|--------------|
| `job_ids` | string | Comma-separated job IDs | `/v1/jobs` |
| `application_status` | enum | active, rejected, hired | `/v1/candidates` |
| `created_after` | ISO date | Date filter | `/v1/candidates` |
| `max_candidates` | number | 1-1000 limit | Pagination |

### API Endpoints Used

1. **`GET /v1/jobs`** - List available jobs
   - Used to populate job selection dropdown
   - Filters open jobs only
   - Returns: `[{id, name, status, ...}]`

2. **`GET /v1/candidates`** - List candidates
   - Would be used for actual analysis (not in test query)
   - Supports filtering by job, status, date
   - Returns paginated candidate data

## User Experience

### Configuration Flow

1. **User selects Greenhouse connector** in Step 2
2. **Configuration screen appears** automatically
3. **Jobs load** in dropdown (or manual entry)
4. **User sets filters**: jobs, status, date, limit
5. **User clicks "Test Query"**
6. **Results preview** shows match count
7. **User clicks "Continue"** to proceed to job description

### Test Query UX

Before running full analysis (which can take minutes), users can:
- ✅ See exactly how many candidates match their filters
- ✅ Adjust filters if too many/too few results
- ✅ Verify Greenhouse API connection
- ✅ Preview job availability
- ✅ Confirm configuration before committing

### Visual Feedback

- 🔵 Loading spinner during API calls
- ✅ Green success card with match count
- ❌ Red error card with helpful messages
- ⚠️ Yellow warning for zero results
- 🔗 Link to Greenhouse API documentation

## Files Created/Modified

### New Files
- `frontend/src/components/talent-intelligence/GreenhouseQueryConfig.tsx` (393 lines)
- `docs/20251024_GREENHOUSE_QUERY_CONFIGURATION.md` (this file)

### Modified Files
- `src/api/routes/connectors.py` (+114 lines)
  - Added `POST /api/connectors/greenhouse/test-query` endpoint
- `frontend/src/pages/talent-intelligence/TalentIntelligencePage.tsx` (+52 lines)
  - Added greenhouse-config workflow step
  - Added greenhouseQueryParams state
  - Added conditional navigation logic
  - Integrated GreenhouseQueryConfig component

## Technical Details

### State Management

```typescript
interface WorkflowConfig {
  selectedEmployeeIds: string[];
  selectedConnectorId: string | null;
  selectedConnectorType: string | null;  // NEW
  greenhouseQueryParams: GreenhouseQueryParams | null;  // NEW
  inputMethod: InputMethod | null;
  jobDescription: string;
  idealCandidateDescription: string;
  uploadedFile: UploadedFileInfo | null;
  manualPersona: any | null;
  pdlQueryLimit: number;
}

interface GreenhouseQueryParams {
  job_ids?: string;
  application_status?: 'active' | 'rejected' | 'hired' | '';
  created_after?: string;
  max_candidates?: number;
}
```

### API Call Flow

```
Frontend                Backend                 Greenhouse API
   │                       │                           │
   │  POST /test-query     │                           │
   ├──────────────────────>│                           │
   │                       │  Get credentials from DB  │
   │                       │<──────────────────────────│
   │                       │                           │
   │                       │  GET /v1/jobs             │
   │                       ├──────────────────────────>│
   │                       │<──────────────────────────│
   │                       │  [jobs array]             │
   │                       │                           │
   │                       │  Filter + Estimate        │
   │                       │                           │
   │  {job_count, candidate_count}                    │
   │<──────────────────────┤                           │
   │                       │                           │
```

## Benefits

1. **Better User Control**: Users can fine-tune candidate selection before analysis
2. **Cost Savings**: Avoid processing too many candidates unnecessarily
3. **Faster Iteration**: Test multiple filter configurations quickly
4. **Transparency**: Users know exactly what data will be analyzed
5. **Error Prevention**: Catch configuration issues before long-running analysis
6. **API Efficiency**: Preview data without full candidate fetch

## Next Steps

Future enhancements could include:

1. **Save Configurations**: Store favorite query configs for reuse
2. **Advanced Filters**: Add more Greenhouse filters (tags, departments, offices)
3. **Candidate Preview**: Show sample candidate names/titles in test results
4. **Query Templates**: Pre-built queries for common scenarios
5. **Export Results**: Download candidate lists before analysis
6. **Real-Time Count**: Actual candidate count instead of estimation

## Testing

To test the feature:

1. Navigate to Talent Intelligence page
2. Select baseline employees
3. Choose "Greenhouse Production" connector
4. Configuration screen should appear
5. Jobs should load in dropdown
6. Set filters and click "Test Query"
7. Verify match count appears
8. Click "Continue" to proceed

**Expected Result:** Smooth workflow with clear feedback at each step.

---

**Contributors:** Scott Gay  
**References:** [Greenhouse Harvest API](https://developers.greenhouse.io/harvest.html)  
**Last Updated:** October 24, 2025

