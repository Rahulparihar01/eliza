# Orchestrator PDL Query Update - Using Empirical Rules

**Date**: 2025-10-19 02:34:00

## Summary

Updated the PDL Query Builder and Orchestrator to use empirically validated query formats from our testing. The system now constructs PDL queries using the **optimal patterns** discovered through comprehensive testing.

## Changes Made

### 1. PDL Query Builder (`src/services/talent/pdl_query_builder.py`)

#### Added Imports
```python
from src.services.talent.pdl_query_rules import (
    PDL_FIELD_RULES,
    validate_field_value,
    recommend_query_strategy
)
```

#### Updated `PDLQueryParams` Model
Added `job_title` field for specific job title matching:
```python
class PDLQueryParams(BaseModel):
    # Core filters
    job_title_role: List[str] = Field(
        default_factory=list, 
        description="Standardized role (e.g., 'engineering', 'sales')"
    )
    job_title: Optional[str] = Field(
        default=None, 
        description="Specific job title for matching (e.g., 'machine learning engineer')"
    )
    required_skills: List[str] = Field(...)
    # ... rest of fields
```

#### Fixed `build_initial_query` Method
**BEFORE** (Incorrect):
```python
query_params = PDLQueryParams(
    job_title_role=[role, "ml engineer", "machine learning engineer"],  # ❌ Wrong!
    required_skills=required_skills,
    # ...
)
```

**AFTER** (Correct):
```python
query_params = PDLQueryParams(
    job_title_role=["engineering"],  # ✅ Standardized category
    job_title=role.lower(),  # ✅ Specific job title: "machine learning engineer"
    required_skills=required_skills[:5],  # ✅ Limit to 5 max (empirical rule)
    # ...
)
```

### 2. Orchestrator (`src/services/talent/orchestrator.py`)

#### Updated `_search_market` Method
Complete rewrite of the simple_query construction using empirical rules:

**BEFORE** (Incorrect):
```python
simple_query = {
    "job_title_role": pdl_query.job_title_role,  # ❌ Used specific titles in standardized field
    "skills": pdl_query.required_skills + pdl_query.optional_skills  # ❌ No limit
}
```

**AFTER** (Correct - Using Empirical Rules):
```python
simple_query = {}

# Use job_title for specific role matching (preferred for ML engineers)
if pdl_query.job_title:
    simple_query["job_title"] = [pdl_query.job_title.lower()]

# Use job_title_role only for broad categorization (only if job_title not used)
if pdl_query.job_title_role and not pdl_query.job_title:
    simple_query["job_title_role"] = [r.lower() for r in pdl_query.job_title_role]

# Limit to 5 skills max per empirical rules
all_skills = (pdl_query.required_skills + pdl_query.optional_skills)[:5]
if all_skills:
    simple_query["skills"] = [s.lower() for s in all_skills]

# Always add location (recommended for credit control)
simple_query["location_country"] = ["united states"]
```

## Empirical Rules Applied

### Rule 1: Use `job_title` for Specific Roles ✅
- **Field**: `job_title` with `match` query type
- **Use**: Specific job titles like "machine learning engineer"
- **Result**: 8,590 ML engineers (optimal)
- **Applied**: Now using `job_title` field for role matching

### Rule 2: `job_title_role` is Standardized ✅
- **Field**: `job_title_role` with `term` query type
- **Use**: Broad categories only ("engineering", "sales", "marketing")
- **Don't use**: Specific titles like "machine learning engineer" (returns 0 results)
- **Applied**: Now using `["engineering"]` as standardized value

### Rule 3: Limit Skills to 2-5 ✅
- **Rule**: Too many skills = 0 results, too few = too broad
- **Optimal**: 2-5 required skills
- **Applied**: Now using `[:5]` to limit skills

### Rule 4: Always Include Location ✅
- **Rule**: Reduces result set from 193M to manageable size
- **Field**: `location_country` with standardized values
- **Applied**: Now always adding `["united states"]`

### Rule 5: Lowercase All Values ✅
- **Rule**: PDL stores all values in lowercase
- **Applied**: Using `.lower()` on all string values

### Rule 6: PDL Query Limit = 1 (for testing) ✅
- **Setting**: `ML_TALENT_PDL_QUERY_LIMIT=1` in `src/core/config.py`
- **Status**: Already configured
- **Production**: Change to 50 when ready

## Expected Query Format

With these changes, the orchestrator will now generate queries like:

```python
{
    "search_query": {
        "job_title": ["machine learning engineer"],  # Specific title matching
        "skills": ["python", "tensorflow", "pytorch"],  # Limited to 2-5
        "location_country": ["united states"]  # Credit control
    },
    "max_records": 1,  # For testing (50 for production)
    "page_size": 1
}
```

This will be converted to Elasticsearch DSL by the PDL connector:

```python
{
    "query": {
        "bool": {
            "must": [
                {"match": {"job_title": "machine learning engineer"}},
                {"term": {"skills": "python"}},
                {"term": {"skills": "tensorflow"}},
                {"term": {"skills": "pytorch"}},
                {"term": {"location_country": "united states"}}
            ]
        }
    },
    "size": 1
}
```

## Validation

### Pre-Deployment Checks ✅
- [x] Linting passed (no errors)
- [x] Containers rebuilt with `--no-cache`
- [x] Containers restarted successfully
- [x] App container healthy
- [x] Celery worker container healthy

### Post-Deployment Verification
Ready to test the full analysis flow:

1. **Expected Behavior**:
   - Diagnostic agent will output skills and role type
   - Query builder will construct optimal PDL query
   - Orchestrator will create PDL connector with correct format
   - PDL API will return 1 result (due to limit=1)
   - Result will be an actual ML engineer profile

2. **Query Preview**:
   - job_title: "machine learning engineer" (specific matching)
   - skills: Top 2-5 from diagnostic
   - location: "united states" (credit control)
   - Expected results: 1 of ~8,590 ML engineers

3. **Monitoring Points**:
   - Check `pdl_connector_created` log for query preview
   - Check `calling_pdl_api` log for limit verification
   - Check `pdl_api_response` log for result count and sample data
   - Verify 1 result returned with valid ML engineer profile

## Files Changed

1. **`src/services/talent/pdl_query_builder.py`**
   - Added PDL rules imports
   - Added `job_title` field to `PDLQueryParams`
   - Fixed `build_initial_query` to use empirical patterns
   - Added skill limit ([:5])

2. **`src/services/talent/orchestrator.py`**
   - Rewrote `simple_query` construction
   - Added conditional logic for job_title vs job_title_role
   - Added skill limiting
   - Added location_country
   - Added lowercase conversion

3. **Docker containers**
   - Rebuilt `app` and `celery-worker` with `--no-cache`
   - Deployed new code

## Next Steps

### Ready to Run Full Analysis Flow

The system is now ready to run a complete end-to-end analysis:

1. Upload job description
2. Select baseline employees
3. Select applicant data source
4. Run analysis

**Expected outcome**:
- Stage 1: Job description parsed ✅
- Stage 2: Diagnostic analysis ✅
- Stage 3: Baseline built ✅
- Stage 4: Applicants parsed ✅
- Stage 5: Applicants scored ✅
- **Stage 6: PDL market search** ✅ (Using new optimal query)
  - Query: job_title="machine learning engineer" + skills + location
  - Expected: 1 result returned
  - Profile: Actual ML engineer from PDL database
- Stage 7: Synthesis ✅

### Production Readiness

To switch to production (50 results):

1. Update `.env`:
   ```bash
   ML_TALENT_PDL_QUERY_LIMIT=50
   ```

2. Restart containers:
   ```bash
   docker-compose -f docker/docker-compose.yml restart app celery-worker
   ```

3. Run analysis:
   - Will now return 50 ML engineers instead of 1

## Key Improvements

### Before
- ❌ Used specific job titles in `job_title_role` field
- ❌ No skill limiting (could request 20+ skills)
- ❌ No location filter (credit control issue)
- ❌ Potential for 0 results due to over-constraining
- ❌ Not using empirical best practices

### After
- ✅ Uses `job_title` field for specific role matching
- ✅ Uses `job_title_role` only for standardized categories
- ✅ Limits skills to 5 maximum
- ✅ Always includes location filter
- ✅ All values lowercase
- ✅ Follows empirically validated patterns
- ✅ Expected to return ~8,590 ML engineers (or 1 for testing)

## References

- **PDL Query Rules**: `src/services/talent/pdl_query_rules.py`
- **PDL Query Guide**: `docs/talent/PDL_QUERY_CONSTRUCTION_GUIDE.md`
- **Test Results**: `tests/test_pdl_ml_engineer_queries.py`
- **Empirical Findings**: `20251019_023000_PDL_QUERY_RULES_COMPLETE.md`

## Status

🎯 **READY FOR TESTING**

The orchestrator is now using optimal, empirically validated PDL query formats. Ready to run the full analysis flow with:
- `ML_TALENT_PDL_QUERY_LIMIT=1` for testing
- Query format matching our successful tests
- Expected to retrieve actual ML engineer profiles from PDL


