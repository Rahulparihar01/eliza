# Talent Intelligence API

**Base Path:** `/api/v1/ml-talent`

**Required Permission:** `talent:read` (for reading), `talent:write` (for creating analyses)

## Overview

The Talent Intelligence system provides AI-powered talent analysis for hiring. It:
1. Parses resumes using Docling VLM
2. Builds baseline profiles from high-performing employees
3. Scores applicants against the baseline
4. Searches market for additional candidates via People Data Labs (PDL)
5. Generates comprehensive synthesis reports with recommendations

> **📊 For a detailed visual flow diagram with all 10 stages**, see [TALENT_INTELLIGENCE_FLOW.md](./TALENT_INTELLIGENCE_FLOW.md)

## Key Concepts

- **Analysis**: A complete talent analysis run
- **Diagnostic Report**: AI analysis of job requirements and competencies
- **Baseline Profile**: Statistical profile built from top performers
- **PDL Query**: Search query for market candidates
- **Candidate Score**: Multi-dimensional scoring of candidates

## Endpoints

### POST /api/v1/ml-talent/analyze

Start talent analysis with uploaded resumes.

**Requires Permission:** `talent:write`

**Request:** `multipart/form-data`
```
job_description: "Machine Learning Engineer role..."
ideal_candidate_description: "5+ years Python, ML experience..."
role: "Machine Learning Engineer"
applicant_resumes: [file1.pdf, file2.pdf, ...]  (max 50)
```

**Response:** `202 Accepted`
```json
{
  "analysis_id": "ml_ta_abc123def456",
  "status": "pending",
  "message": "Analysis started. Check status at /v1/ml-talent/analysis/ml_ta_abc123def456/status"
}
```

**Errors:**
- `400` - Too many files (>50) or invalid format
- `403` - Insufficient permissions

---

### POST /api/v1/ml-talent/analyze-from-connector

Start talent analysis from a data connector (e.g., filesystem with resumes).

**Requires Permission:** `talent:write`

**Request:**
```json
{
  "job_description": "Machine Learning Engineer...",
  "ideal_candidate_description": "5+ years Python...",
  "data_source_connector_id": "conn_fs_resumes",
  "baseline_employee_ids": [1, 2, 3],
  "role": "Machine Learning Engineer"
}
```

**Parameters:**
- `data_source_connector_id` (string, required) - Connector with resume files
- `baseline_employee_ids` (array, optional) - Employee IDs for baseline

**Response:** `202 Accepted`
```json
{
  "analysis_id": "ml_ta_xyz789",
  "status": "pending",
  "message": "Analysis started with 45 resumes."
}
```

**Errors:**
- `404` - Connector not found
- `403` - No access to connector
- `400` - No PDF files found or connector disabled

---

### GET /api/v1/ml-talent/analyses

List talent analyses with pagination and filtering.

**Requires Permission:** `talent:read`

**Query Parameters:**
- `page` (integer, default: 1)
- `page_size` (integer, default: 20, max: 100)
- `status` (string, optional) - Filter by status

**Response:** `200 OK`
```json
{
  "analyses": [
    {
      "analysis_id": "ml_ta_abc123",
      "status": "completed",
      "role": "Machine Learning Engineer",
      "candidate_count": 78,
      "applicant_count": 45,
      "market_count": 33,
      "created_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:15:00Z",
      "job_description_summary": "Senior ML Engineer with Python..."
    },
    ...
  ],
  "total": 50,
  "page": 1,
  "page_size": 20,
  "pages": 3
}
```

---

### GET /api/v1/ml-talent/analysis/{analysis_id}

Get complete analysis results.

**Requires Permission:** `talent:read`

**Response:** `200 OK`
```json
{
  "analysis_id": "ml_ta_abc123",
  "status": "completed",
  "job_description": "...",
  "ideal_candidate_description": "...",
  "diagnostic_report": {
    "ml_competencies": {
      "technical_skills": {
        "required_skills": ["Python", "TensorFlow"],
        "nice_to_have_skills": ["PyTorch", "Kubernetes"]
      },
      "experience_requirements": {
        "min_years": 5,
        "preferred_years": 7
      }
    },
    "attribute_weights": [
      {"name": "Python Proficiency", "weight": 0.25},
      {"name": "ML Experience", "weight": 0.20}
    ]
  },
  "baseline_profile": {
    "statistical_ranges": {...},
    "skill_frequencies": {"Python": 0.95, "TensorFlow": 0.78},
    "company_culture_markers": [...]
  },
  "applicant_results": [
    {
      "candidate_id": "candidate_001",
      "full_name": "John Smith",
      "overall_score": 0.85,
      "dimensions": [
        {"name": "Python Proficiency", "score": 0.92, "rationale": "10 years experience"},
        {"name": "ML Experience", "score": 0.78, "rationale": "Built 5 production models"}
      ]
    },
    ...
  ],
  "market_results": [...],
  "top_overall": [...],
  "synthesis": {
    "executive_summary": "Analysis of 45 applicants and 33 market candidates...",
    "top_candidate_insights": [...],
    "skill_gap_analysis": [...],
    "recommendations": [...]
  },
  "patterns": [],
  "provenance": [],
  "overall_confidence": 0.88,
  "created_at": "2024-01-15T10:00:00Z",
  "completed_at": "2024-01-15T10:15:00Z",
  "pdl_query": {
    "job_title": "Machine Learning Engineer",
    "required_skills": ["python", "tensorflow"],
    "location_country": ["united states"]
  }
}
```

**Notes:**
- `diagnostic_report`, `baseline_profile`, and `synthesis` may be `null` if analysis is still processing or failed
- Candidates are ranked by `overall_score`

---

### GET /api/v1/ml-talent/analysis/{analysis_id}/status

Get quick analysis status.

**Requires Permission:** `talent:read`

**Response:** `200 OK`
```json
{
  "analysis_id": "ml_ta_abc123",
  "status": "processing",
  "message": "Analyzing candidates...",
  "progress_percentage": 50
}
```

**Status Values:**
- `pending` (0%) - Queued
- `processing` (50%) - Running
- `completed` (100%) - Done
- `failed` (0%) - Error occurred

---

### POST /api/v1/ml-talent/analysis/{analysis_id}/refine

Refine PDL market search query based on feedback.

**Requires Permission:** `talent:write`

**Request:**
```json
{
  "analysis_id": "ml_ta_abc123",
  "refinement_feedback": {
    "add_skills": ["scikit-learn"],
    "remove_skills": ["java"],
    "adjust_experience": {"min_years": 3}
  }
}
```

**Response:** `202 Accepted`
```json
{
  "analysis_id": "ml_ta_abc123_v2",
  "status": "processing",
  "message": "Query refined. New analysis started."
}
```

---

### POST /api/v1/ml-talent/analysis/{analysis_id}/feedback

Submit feedback on analysis results.

**Requires Permission:** `talent:write`

**Request:**
```json
{
  "candidate_ratings": {
    "candidate_001": "great",
    "candidate_002": "good"
  },
  "attribute_adjustments": {
    "Python Proficiency": 0.30
  },
  "comments": "Great results, need more focus on Python"
}
```

**Response:** `204 No Content`

**Use Case:** Feedback is stored for future analysis improvements

---

## Analysis Workflow

```
1. Submit Analysis Request
   ↓
2. Parse Resumes (Docling VLM)
   ↓
3. Run Diagnostic Agent (analyze JD + ideal candidate)
   ↓
4. Build Baseline Profile (from high performers)
   ↓
5. Score Applicants (against baseline)
   ↓
6. Build PDL Query (from diagnostic)
   ↓
7. Search Market (via PDL connector)
   ↓
8. Score Market Candidates
   ↓
9. Generate Synthesis Report
   ↓
10. COMPLETED
```

## Real-Time Progress (SSE)

**Note:** Talent analysis uses telemetry events similar to BI system. Monitor via:

```javascript
// Using the analysis_id from URL query param
const urlParams = new URLSearchParams(window.location.search);
const analysisId = urlParams.get('analysis_id');

// Listen for events (implementation similar to BI SSE)
// Events are stored in talent_analysis_events table
```

**Event Types:**
- `analysis_started`
- `orchestrator_initialized`
- `diagnostic_started`
- `diagnostic_completed`
- `baseline_started`
- `baseline_completed`
- `applicant_scoring_started`
- `applicant_scoring_completed`
- `market_search_started`
- `market_search_completed`
- `market_scoring_started`
- `market_scoring_completed`
- `synthesis_started`
- `synthesis_completed`
- `analysis_completed`
- `analysis_failed`

## Multi-Dimensional Scoring

Each candidate is scored across multiple dimensions defined in the diagnostic report.

**Example Dimensions:**
- Technical Skills (Python, ML frameworks)
- Experience Level
- Domain Knowledge
- Communication Skills
- Cultural Fit

**Score Calculation:**
```
Overall Score = Σ (dimension_score × attribute_weight)
```

## People Data Labs (PDL) Integration

### Query Format

The system builds PDL queries based on the diagnostic report:

```json
{
  "job_title": "Machine Learning Engineer",
  "required_skills": ["python", "tensorflow"],
  "optional_skills": ["pytorch", "kubernetes"],
  "min_experience_years": 5,
  "location_country": ["united states"]
}
```

### Cost Control

- PDL charges per record returned
- Use `size` parameter to limit results (default: 10)
- Estimate cost before running large queries
- Check connector configuration for credit limits

### Best Practices

1. **Use specific job titles**: "Machine Learning Engineer" > "Engineer"
2. **Limit skills**: Top 3-5 most important skills
3. **Use standardized fields**: `job_title_role` for categories, `job_title` for exact matches
4. **Set location filters**: Reduces irrelevant results
5. **Start small**: Test with size=1-5 before scaling up

## Provenance & Audit Trail

Every analysis includes complete provenance tracking:

```json
{
  "provenance": [
    {
      "step_name": "resume_parsing",
      "timestamp": "2024-01-15T10:00:30Z",
      "input": {"file_count": 45},
      "output": {"parsed_count": 45},
      "confidence": 0.95
    },
    ...
  ]
}
```

## Error Handling

### Common Errors

**"Connector not found"**
- Ensure connector exists and is enabled
- Check connector permissions

**"No PDF files found in directory"**
- Verify filesystem connector path
- Check file extensions configuration

**"Analysis failed: 'MultiDimensionalScoringEngine' object has no attribute 'score'"**
- Internal error, check Celery logs
- Contact support

**"Analysis stuck in processing"**
- Check Celery worker health
- View worker logs: `docker-compose logs celery-worker`

## Limits

- **Max Resumes per Analysis**: 50
- **PDL Market Search**: Default 10 (configurable)
- **Analysis Timeout**: 30 minutes
- **Concurrent Analyses**: No hard limit (resource-dependent)

## Example: Complete Analysis Flow

```python
import requests
import time

API_BASE = 'http://localhost:5001/api/v1/ml-talent'
TOKEN = 'your_jwt_token'
HEADERS = {'Authorization': f'Bearer {TOKEN}'}

# 1. Start analysis from connector
response = requests.post(
    f'{API_BASE}/analyze-from-connector',
    headers=HEADERS,
    json={
        'job_description': 'Senior ML Engineer...',
        'ideal_candidate_description': '5+ years Python...',
        'data_source_connector_id': 'conn_fs_resumes',
        'role': 'Machine Learning Engineer'
    }
)

analysis_id = response.json()['analysis_id']
print(f'Analysis started: {analysis_id}')

# 2. Poll status
while True:
    status = requests.get(
        f'{API_BASE}/analysis/{analysis_id}/status',
        headers=HEADERS
    ).json()
    
    print(f"{status['status']}: {status['progress_percentage']}%")
    
    if status['status'] in ['completed', 'failed']:
        break
    
    time.sleep(5)

# 3. Get results
if status['status'] == 'completed':
    results = requests.get(
        f'{API_BASE}/analysis/{analysis_id}',
        headers=HEADERS
    ).json()
    
    print(f"\nTop 3 Candidates:")
    for candidate in results['top_overall'][:3]:
        print(f"- {candidate['full_name']}: {candidate['overall_score']:.2f}")
```


