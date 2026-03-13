# ML Talent Intelligence - Complete Flow Implementation
**Date**: October 14, 2025, 09:05 AM PST

## Overview
Successfully implemented the complete connector-based analysis flow with baseline employee selection.

## Complete Flow

### Step 1: Select Baseline Employees
- User selects "look-alike" employees from existing team
- Employee IDs stored: `config.selectedEmployeeIds` (array of numbers)

### Step 2: Select Data Source
- User selects connector containing candidate resumes
- Connector ID stored: `config.selectedConnectorId` (string)

### Step 3: Define Requirements
- User uploads/pastes job description
- User provides ideal candidate description
- Data stored: `config.jobDescription` and `config.idealCandidateDescription`

### Step 4: Submit Analysis
Frontend calls: `POST /v1/ml-talent/analyze-from-connector`

Request payload:
```typescript
{
  job_description: string,
  ideal_candidate_description: string,
  data_source_connector_id: string,  // From Step 2
  baseline_employee_ids: number[],   // From Step 1
  role: "Machine Learning Engineer"
}
```

### Step 5: Backend Processing

#### 5.1 Fetch Resumes from Connector
```python
# Get connector config
connector = connector_service.get_configuration(data_source_connector_id)

# Fetch PDF files from filesystem
resume_files = []
for filename in os.listdir(directory_path):
    if filename.endswith('.pdf'):
        content = read_file(filename)
        resume_files.append((content, filename))
```

#### 5.2 Create Analysis Request
```python
TalentAnalysisRequest(
    job_description=job_description,
    ideal_candidate_description=ideal_candidate_description,
    applicant_resume_files=resume_files,  // PDFs from connector
    role=role,
    customer_id=customer_id,
    user_id=user_id,
    baseline_employee_ids=[123, 456, 789]  // From Step 1
)
```

#### 5.3 Build Baseline Profile
```python
# If employee_ids provided, query PDL persons table
if employee_ids:
    employees = db.query(PDLPerson).filter(
        PDLPerson.id.in_(employee_ids)
    ).all()
    
    # Convert to baseline format
    ml_engineers = [{
        "full_name": emp.full_name,
        "current_title": emp.job_title,
        "skills": emp.skills,
        "years_experience": emp.inferred_years_experience,
        ...
    }]
else:
    # Fall back to Neo4j query for all ML Engineers
    ml_engineers = neo4j.query(...)

# Build baseline profile from selected employees
baseline = analyze_skills_experience_patterns(ml_engineers)
```

#### 5.4 Parse Resumes
- Fast parser (PyPDF2) for now
- Docling VLM available for future rich parsing

#### 5.5 Run Analysis
- Diagnostic agent analyzes requirements
- Score applicants against baseline
- Build PDL query from patterns
- Search market candidates
- Synthesis agent creates report

## Changes Made

### Backend

1. **`src/api/routes/ml_talent.py`**
   - Added `StartAnalysisFromConnectorRequest` schema
   - Added `POST /v1/ml-talent/analyze-from-connector` endpoint
   - Fetches resumes from filesystem connector
   - Passes baseline_employee_ids to orchestrator

2. **`src/services/talent/orchestrator.py`**
   - Added `baseline_employee_ids` to `TalentAnalysisRequest`
   - Updated `_build_baseline()` to accept and pass employee_ids
   - Passes employee_ids to baseline builder

3. **`src/services/talent/ml_engineer_baseline_builder.py`**
   - Added `employee_ids` parameter to `build()` method
   - Updated `_query_ml_engineers()` to:
     - Query PDL persons table if employee_ids provided
     - Fall back to Neo4j for all ML Engineers if not

### Frontend (TODO)
- Update `TalentIntelligencePage` to use new endpoint
- Pass `baseline_employee_ids` and `data_source_connector_id` in request

## API Endpoints

### File Upload (Original)
```
POST /v1/ml-talent/analyze
Content-Type: multipart/form-data

- job_description (form field)
- ideal_candidate_description (form field)
- applicant_resumes (files[])
- role (form field)
```

### Connector-Based (New)
```
POST /v1/ml-talent/analyze-from-connector
Content-Type: application/json

{
  "job_description": "string",
  "ideal_candidate_description": "string",
  "data_source_connector_id": "filesystem_eliza_e963e2a5",
  "baseline_employee_ids": [123, 456, 789],
  "role": "Machine Learning Engineer"
}
```

## Data Flow

```
User Input (Frontend)
  ↓
  ├─ Step 1: Select 3 baseline employees → [123, 456, 789]
  ├─ Step 2: Select filesystem connector → "filesystem_eliza_e963e2a5"
  └─ Step 3: Upload job description → "Senior ML Engineer..."
  
Backend Processing
  ↓
  ├─ Fetch PDFs from connector → [(pdf_bytes, "resume1.pdf"), ...]
  ├─ Query baseline employees → [{name, title, skills, ...}, ...]
  ├─ Build baseline profile → {common_skills: ["Python", "PyTorch"], ...}
  ├─ Parse resumes → [{name, skills, experience}, ...]
  ├─ Diagnostic agent → {attribute_priorities, patterns}
  ├─ Score applicants → [{candidate_id, scores}, ...]
  ├─ Search market → [{candidate_id, scores}, ...]
  └─ Synthesis → {top_3_overall, executive_summary}
  
Results
  ↓
  └─ Frontend displays ranked candidates with explanations
```

## Benefits

1. **Flexible Data Sources**: Resumes from connectors (filesystem, future: Greenhouse, Lever)
2. **Targeted Baselines**: Use specific employees vs. all ML Engineers
3. **Fast Processing**: Parse PDFs on-demand, no pre-ingestion required
4. **Rich Metadata**: Future Docling VLM integration for deep resume parsing
5. **Scalable**: Handles up to 50 resumes per analysis

## Testing Checklist

- [ ] Select 3 baseline employees from Step 1
- [ ] Select filesystem connector from Step 2
- [ ] Upload/paste job description in Step 3
- [ ] Click "Analyze with AI"
- [ ] Backend fetches 50 PDFs from `/app/tests/resumes`
- [ ] Backend queries 3 selected employees from `pdl_persons` table
- [ ] Baseline profile built from those 3 employees
- [ ] Resumes parsed and scored
- [ ] Market search runs
- [ ] Results returned with provenance
- [ ] Frontend displays ranked candidates

## Next Steps

1. ✅ Backend complete
2. ⏳ Update frontend to call new endpoint
3. ⏳ Test end-to-end flow
4. ⏳ Monitor logs during analysis
5. ⏳ Verify results display correctly

## Files Modified

- `src/api/routes/ml_talent.py` - New connector endpoint
- `src/services/talent/orchestrator.py` - Pass employee_ids
- `src/services/talent/ml_engineer_baseline_builder.py` - Query specific employees
- Frontend Orval types regenerated
- Docker containers rebuilt and restarted

**Status**: Backend complete, ready for frontend integration! 🚀


