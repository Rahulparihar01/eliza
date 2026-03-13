# PDL Query Construction Guide

**Date**: 2025-10-19 02:30:00

## Overview

This guide defines the rules and strategies for dynamically constructing People Data Labs (PDL) search queries. These rules are used by the Diagnostic Agent and PDL Query Builder to create optimized queries based on job requirements and baseline analysis.

## Core Philosophy

**DO NOT** hardcode specific queries. Instead, use rules and strategies to dynamically construct queries based on:
- Job description analysis
- Required vs. optional skills
- Baseline employee patterns
- Expected result pool size

## Key Rules Reference

The system uses rules defined in `src/services/talent/pdl_query_rules.py`. All rules are empirically validated through testing.

### Critical Rules (Must Follow)

1. **Credit Control**
   - Always set `size` parameter to control costs
   - Typical value: 50-100 for initial search, 1 for testing

2. **Field Standardization**
   - Fields like `job_title_role`, `job_title_levels`, `location_country` use standardized values
   - Check `PDL_FIELD_RULES[field].is_standardized` before use
   - Example: Use `"engineering"` not `"software engineer"` for `job_title_role`

3. **Query Type Selection**
   - `term`: Exact match (e.g., skills, location)
   - `match`: Partial text match (e.g., job_title)
   - `terms`: Multiple values (e.g., multiple companies)
   - Check `PDL_FIELD_RULES[field].field_type` for correct type

4. **Lowercase Values**
   - PDL stores all values in lowercase
   - Always apply `.lower()` to string values

5. **No `minimum_should_match`**
   - PDL API returns 400 error for this clause
   - Use `must` clauses only, or `terms` for OR logic

### Recommended Rules (Best Practices)

1. **Include Location Filter**
   - Reduces result set from 193M to manageable size
   - Use `location_country: "united states"` or target region

2. **Skill Balance**
   - Use 2-5 required skills
   - Too many skills → 0 results
   - Too few skills → too broad

3. **Avoid Over-Filtering**
   - Start with 2-3 filters
   - Check result count
   - Add more filters only if needed

## Field-Specific Guidance

### `job_title_role` (Standardized)
```python
{
    "term": {"job_title_role": "engineering"}
}
```
- **Use for**: Broad role categorization
- **Values**: `engineering`, `sales`, `marketing`, `operations`, `finance`, `education`, `health`, `legal`, `media`
- **Impact**: Broad (27.4M results for "engineering")
- **Best practices**:
  - NOT for specific job titles (e.g., don't use "software engineer")
  - Combine with skills for better targeting
  - Verified: "engineering" returns 27.4M results

### `job_title` (Free-text, use with `match`)
```python
{
    "match": {"job_title": "machine learning engineer"}
}
```
- **Use for**: Specific job title matching
- **Values**: Any job title text (e.g., "machine learning engineer", "data scientist")
- **Impact**: Moderate (8,590 results for "machine learning engineer")
- **Best practices**:
  - Use `match` query type for partial matching
  - Include key terms from job description
  - Verified: "machine learning engineer" returns 8,590 results

### `skills` (Free-text)
```python
{
    "term": {"skills": "tensorflow"}
}
```
- **Use for**: Technical skill requirements
- **Values**: Specific technology names (lowercase)
- **Impact**: Moderate to narrow (depends on skill popularity)
- **Best practices**:
  - Each skill is an AND condition
  - Use 2-5 skills for optimal results
  - Verified: "python" + US returns 1.6M results
  - Verified: "machine learning" + "python" + US returns 156K results

### `location_country` (Standardized)
```python
{
    "term": {"location_country": "united states"}
}
```
- **Use for**: Geographic filtering
- **Values**: Full country names (lowercase)
- **Impact**: Broad but essential filter
- **Best practices**:
  - Highly recommended for credit control
  - Verified: "united states" returns 193M results
  - Always combine with other filters

### `job_company_name` (Free-text)
```python
{
    "term": {"job_company_name": "google"}
}
```
- **Use for**: Targeting candidates from specific companies
- **Values**: Company names (lowercase)
- **Impact**: Narrow (348K results for "google")
- **Best practices**:
  - Use for "look-alike" searches
  - Can use multiple with `terms` query
  - Verified: "google" returns 348K results

### `job_title_levels` (Standardized)
```python
{
    "terms": {"job_title_levels": ["senior", "lead", "principal"]}
}
```
- **Use for**: Seniority filtering
- **Values**: `entry`, `senior`, `lead`, `principal`, `manager`, `director`, `vp`, `c-level`
- **Impact**: Narrow (can over-constrain)
- **Best practices**:
  - Use with caution
  - May reduce results to 0
  - Consider omitting for broader searches

## Query Strategies

### 1. Broad Exploration
**Use when**: Initial market sizing, common roles

**Fields**: `job_title_role`, `location_country`

**Expected results**: 10K - 1M+ candidates

**Example**:
```python
{
    "query": {
        "bool": {
            "must": [
                {"term": {"job_title_role": "engineering"}},
                {"term": {"location_country": "united states"}}
            ]
        }
    },
    "size": 50
}
```

### 2. Targeted Search (Recommended for ML Talent)
**Use when**: Specific role with clear skill requirements

**Fields**: `job_title`, `skills`, `location_country`

**Expected results**: 1K - 50K candidates

**Example**:
```python
{
    "query": {
        "bool": {
            "must": [
                {"match": {"job_title": "machine learning engineer"}},
                {"term": {"skills": "tensorflow"}},
                {"term": {"location_country": "united states"}}
            ]
        }
    },
    "size": 50
}
```

### 3. Precision Search
**Use when**: Very specific technical requirements, niche area

**Fields**: `job_title`, `skills` (multiple), `location_country`, `job_company_name`

**Expected results**: 10 - 1K candidates

**Example**:
```python
{
    "query": {
        "bool": {
            "must": [
                {"match": {"job_title": "machine learning"}},
                {"term": {"job_title_role": "engineering"}},
                {"term": {"skills": "tensorflow"}},
                {"term": {"skills": "pytorch"}},
                {"term": {"location_country": "united states"}}
            ]
        }
    },
    "size": 50
}
```

### 4. Company Cluster Search
**Use when**: Baseline shows patterns from specific companies

**Fields**: `job_company_name`, `job_title`, `skills`

**Expected results**: 100 - 10K candidates

**Example**:
```python
{
    "query": {
        "bool": {
            "must": [
                {"terms": {"job_company_name": ["google", "microsoft", "amazon"]}},
                {"match": {"job_title": "machine learning"}}
            ]
        }
    },
    "size": 50
}
```

## How the System Should Use These Rules

### Diagnostic Agent

The diagnostic agent should:

1. **Analyze job description** to extract:
   - Role type (maps to `job_title_role` or `job_title`)
   - Required skills (maps to `skills`)
   - Seniority level (maps to `job_title_levels`)

2. **Analyze baseline** to identify:
   - Common companies (maps to `job_company_name`)
   - Skill distributions (maps to `skills`)
   - Average experience level

3. **Recommend strategy** based on:
   - How specific the role is
   - Number of required skills
   - Whether baseline shows company patterns

4. **Output structured recommendations**:
   ```python
   {
       "recommended_strategy": "targeted_search",
       "field_mappings": {
           "job_title": "machine learning engineer",
           "skills": ["tensorflow", "python", "deep learning"],
           "location_country": "united states"
       },
       "rationale": "Job description specifies ML engineer role with 3 key skills"
   }
   ```

### PDL Query Builder

The query builder should:

1. **Accept structured input** from diagnostic agent

2. **Apply rules**:
   - Validate field values using `validate_field_value()`
   - Check field compatibility
   - Ensure lowercase conversion
   - Select correct query type (`term`, `match`, `terms`)

3. **Construct query** following strategy template

4. **Add safeguards**:
   - Always include `size` parameter
   - Include location filter unless omitted
   - Limit to 2-5 skills

5. **Return both**:
   - Simple key-value format (for connector config)
   - Elasticsearch DSL format (for provenance)

## Verified Query Performance

From empirical testing:

| Query Description | Result Count | Status |
|------------------|--------------|--------|
| US location only | 193,892,946 | ✅ Works |
| Python + US | 1,648,307 | ✅ Works |
| Engineering + ML + Python + US | 156,833 | ✅ Works |
| ML Engineer title + US | 8,590 | ✅ Works (Best for ML!) |
| Google employees | 348,872 | ✅ Works |
| Engineering role only | 27,453,611 | ✅ Works |
| "Software engineer" as role | 0 | ❌ Fails (not standardized) |

## Common Pitfalls to Avoid

### ❌ Don't hardcode specific queries
```python
# BAD
query = {"term": {"job_title_role": "engineering"}}
```

### ✅ Do use rules to construct dynamically
```python
# GOOD
field_rules = get_field_rules("job_title_role")
if field_rules.is_standardized:
    query = {field_rules.field_type: {"job_title_role": role_value.lower()}}
```

### ❌ Don't use non-standardized values for standardized fields
```python
# BAD
{"term": {"job_title_role": "software engineer"}}  # Returns 0 results
```

### ✅ Do use standardized values
```python
# GOOD
{"term": {"job_title_role": "engineering"}}  # Returns 27M results
```

### ❌ Don't over-constrain with too many filters
```python
# BAD - Returns 0 results
{
    "must": [
        {"term": {"job_title_role": "engineering"}},
        {"match": {"job_title": "machine learning"}},
        {"terms": {"job_title_levels": ["senior", "lead"]}},
        {"term": {"skills": "tensorflow"}},
        {"term": {"skills": "pytorch"}},
        {"term": {"skills": "scikit-learn"}},
        {"term": {"skills": "kubernetes"}},
        {"term": {"location_country": "united states"}}
    ]
}
```

### ✅ Do start broad and narrow based on results
```python
# GOOD - Returns 8,590 results
{
    "must": [
        {"match": {"job_title": "machine learning engineer"}},
        {"term": {"location_country": "united states"}}
    ]
}
```

## Integration Points

### For Diagnostic Agent
- Import: `from src.services.talent.pdl_query_rules import *`
- Use: `get_field_rules()`, `get_query_strategy()`, `recommend_query_strategy()`
- Output: Structured field mappings and strategy recommendation

### For PDL Query Builder
- Import: `from src.services.talent.pdl_query_rules import *`
- Use: `validate_field_value()`, `get_field_rules()`, `get_rule()`
- Input: Structured field mappings from diagnostic
- Output: PDL Elasticsearch DSL query

## Testing and Validation

All rules in this guide are validated through:
- `tests/test_pdl_exact_example.py` - Format verification
- `tests/test_pdl_working_key.py` - Key validation and query discovery
- `tests/test_pdl_ml_engineer_queries.py` - ML-specific query testing
- `tests/test_pdl_query_simple.py` - End-to-end connector workflow

## Future Enhancements

1. **Query Refinement Loop**: User feedback → adjust query parameters → re-run
2. **Result Count Prediction**: Estimate result count before API call
3. **Skill Synonyms**: Map similar skills (e.g., "ML" → "machine learning")
4. **Company Clustering**: Auto-detect similar companies from baseline
5. **Adaptive Filtering**: Automatically adjust filters based on result count

## References

- PDL Documentation: https://docs.peopledatalabs.com/docs/person-search-api
- PDL Elasticsearch Examples: https://docs.peopledatalabs.com/docs/examples-person-search-api
- Internal Rules Module: `src/services/talent/pdl_query_rules.py`


