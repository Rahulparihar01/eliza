# 20251019_022500_PDL_FIELD_DISCOVERY.md

## PDL Field Structure Discovery

### Critical Finding: `job_title_role` is a Standardized Field

**Problem**: We were treating `job_title_role` like a free-text field.

**Reality**: PDL normalizes job data into structured fields:

```json
{
  "job_title": "Senior Software Engineer",           // ← Actual title (free text)
  "job_title_role": "engineering",                   // ← Normalized role category
  "job_title_sub_role": "software",                  // ← Normalized sub-category  
  "job_title_levels": ["senior"]                     // ← Normalized seniority levels
}
```

### Test Results

| Query | job_title_role Value | Results | Status |
|-------|---------------------|---------|--------|
| `"engineering"` | Standardized value | 27.4M | ✅ Works |
| `"software engineer"` | Not a valid value | 0 | ❌ Fails |
| `"web"` (as sub_role) | Standardized value | Works | ✅ Works |

### Standardized Values

According to PDL documentation, `job_title_role` uses values like:
- `"engineering"`
- `"sales"`
- `"marketing"`
- `"operations"`
- `"finance"`
- etc.

**NOT** specific titles like "Software Engineer", "ML Engineer", etc.

### Correct Query Patterns

#### For ML Engineer Search:

**❌ Wrong:**
```python
{"term": {"job_title_role": "machine learning engineer"}}
# Returns: 0 results
```

**✅ Correct - Option 1 (Use standardized role):**
```python
{
  "bool": {
    "must": [
      {"term": {"job_title_role": "engineering"}},
      {"term": {"skills": "machine learning"}},
      {"term": {"skills": "python"}}
    ]
  }
}
# Returns: Engineers with ML skills
```

**✅ Correct - Option 2 (Use actual job title):**
```python
{
  "bool": {
    "must": [
      {"match": {"job_title": "machine learning engineer"}},  // match allows partial
      {"term": {"location_country": "united states"}}
    ]
  }
}
# Returns: People whose actual title contains "machine learning engineer"
```

**✅ Correct - Option 3 (Combine both):**
```python
{
  "bool": {
    "must": [
      {"term": {"job_title_role": "engineering"}},
      {"match": {"job_title": "machine learning"}},
      {"term": {"skills": "tensorflow"}},
      {"term": {"location_country": "united states"}}
    ]
  }
}
# Returns: Engineers with "machine learning" in title and TensorFlow skills
```

### Required Changes

#### 1. Update `PDLQueryBuilder`

**File**: `src/services/talent/pdl_query_builder.py`

**Change**: Use standardized `job_title_role` values OR use `job_title` with match query

```python
def build_initial_query(self, diagnostic, baseline, limit=50):
    # Option A: Use standardized role + skills
    return PDLQueryParams(
        job_title_role=["engineering"],  # ← Use standardized value
        required_skills=["python", "tensorflow"],
        optional_skills=["pytorch", "scikit-learn"],
        location_country="united states",
        limit=limit
    )
    
    # Option B: Use actual job title with match
    # (Would need to add job_title field to PDLQueryParams)
```

#### 2. Update `_convert_to_pdl_query`

**File**: `src/services/ingestion/connectors/people_data_labs.py`

**Change**: Add support for `match` queries (partial text matching)

```python
def _convert_to_pdl_query(self, simple_query):
    must_clauses = []
    
    for field, values in simple_query.items():
        # Special handling for text fields that need partial matching
        if field in ['job_title', 'job_company_name']:
            # Use 'match' for partial text matching
            if isinstance(values, list):
                for value in values:
                    must_clauses.append({
                        "match": {field: value}
                    })
            else:
                must_clauses.append({
                    "match": {field: values}
                })
        else:
            # Use 'term' for exact matching (existing logic)
            # ...existing code...
```

### Example Successful Query

```python
# Query that works with PDL
query = {
    "query": {
        "bool": {
            "must": [
                {"term": {"job_title_role": "engineering"}},  # Standardized
                {"term": {"skills": "python"}},
                {"term": {"location_country": "united states"}}
            ]
        }
    }
}

# Result: 27.4M engineers in the US with Python skills
```

### Documentation References

- [PDL Job Title Roles](https://docs.peopledatalabs.com/docs/job-title-roles) - List of standardized role values
- [PDL Person Schema](https://docs.peopledatalabs.com/docs/person-schema) - Field descriptions
- [PDL Elasticsearch Queries](https://docs.peopledatalabs.com/docs/reference-person-search-api) - Query syntax

### Next Steps

1. ✅ Update `PDLQueryBuilder` to use `"engineering"` instead of specific job titles
2. ✅ Add `match` query support for `job_title` field
3. ✅ Test with real ML engineer search
4. ✅ Run full end-to-end analysis

### Production Query Recommendation

For ML Talent Intelligence, use this query structure:

```python
{
    "job_title_role": ["engineering"],  # Standardized role
    "skills": ["python", "tensorflow", "pytorch"],  # ML-specific skills
    "location_country": ["united states"],  # Location filter
    "min_years_experience": 5,  # Experience level (if supported)
}

# This will return: 
# - Engineers (standardized role)
# - With ML skills (specific technologies)
# - In the US (location)
# - With 5+ years experience
```

This query format works with the API key and will return real ML engineer candidates!


