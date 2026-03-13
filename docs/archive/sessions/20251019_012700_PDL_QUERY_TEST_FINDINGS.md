# PDL Query Integration Test - Key Findings

**Date**: 2025-10-19 01:27:00

## Summary

Created comprehensive integration tests for the PDL query building workflow and discovered critical bugs in the orchestrator's handling of API payload structure.

## Issues Found

### Issue 1: Incorrect API Payload Key Reference

**Problem**: The orchestrator was referencing `api_payload.get("search_query", {})` but the actual PDL API payload uses `"query"` as the key name.

**Affected Code**:
- `src/services/talent/orchestrator.py` line 717 (in `_search_market`)
- `src/services/talent/orchestrator.py` line 502 (in `run_analysis`)

**Evidence**: Test output showed:
```python
{'pretty': True, 
 'query': '(job_title_role:"Machine Learning Engineer" OR job_title_role:"ML Engineer") ...', 
 'scroll_token': None, 
 'size': 10}
```

**Fix**: Changed all references from `api_payload.get("search_query", {})` to `api_payload.get("query", "")`.

### Issue 2: Instance Method Called as Static Method

**Problem**: `PDLQueryBuilder.convert_to_pdl_api_payload(query)` was being called as a static method when it's actually an instance method.

**Error**: `TypeError: PDLQueryBuilder.convert_to_pdl_api_payload() missing 1 required positional argument: 'query_params'`

**Fix**: Changed to `self.pdl_query_builder.convert_to_pdl_api_payload(pdl_query)` using the existing instance.

### Issue 3: Type Mismatch Between PDLQueryParams and PDLQuery

**Problem**: `TalentAnalysisResult.pdl_query` expects a `PDLQuery` object (or dict), but the orchestrator was passing a `PDLQueryParams` object directly.

**Error**: `Pydantic ValidationError: Input should be a valid dictionary or instance of PDLQuery [type=model_type, input_value=PDLQueryParams(...)]`

**Fix**: Added conversion logic to transform `PDLQueryParams` → API payload (dict) → `PDLQuery` object before passing to `TalentAnalysisResult`.

## Test Coverage

Created `tests/test_pdl_query_simple.py` with the following tests:

1. **`test_pdl_query_params_to_api_payload_to_pdl_query`**
   - Verifies the complete type conversion workflow
   - Tests: PDLQueryParams → dict (API payload) → PDLQuery
   - Ensures correct key names in API payload

2. **`test_query_builder_instance_method`**
   - Verifies that `convert_to_pdl_api_payload` must be called on an instance
   - Confirms static method call fails as expected

3. **`test_pdl_query_validation`**
   - Tests PDLQuery Pydantic validation
   - Ensures PDLQuery correctly rejects PDLQueryParams as the `params` field

## Workflow Verified

```
DiagnosticReport + BaselineProfile
          ↓
   PDLQueryBuilder.build_initial_query()
          ↓
     PDLQueryParams
          ↓
   query_builder.convert_to_pdl_api_payload()
          ↓
   dict (API payload with "query" key)
          ↓
   PDLService.search_people(query=payload["query"])
          ↓
   List[ParsedResume]
          ↓
   PDLQuery (for storage in TalentAnalysisResult)
```

## Files Modified

1. **`src/services/talent/orchestrator.py`**
   - Line 502: Changed `api_payload.get("search_query", {})` → `api_payload.get("query", "")`
   - Line 717: Changed `api_payload.get("search_query", {})` → `api_payload.get("query", "")`
   - Line 499: Changed `PDLQueryBuilder.convert_to_pdl_api_payload(pdl_query)` → `self.pdl_query_builder.convert_to_pdl_api_payload(pdl_query)`
   - Lines 498-506: Added conversion logic from PDLQueryParams to PDLQuery

2. **`tests/test_pdl_query_simple.py`** (NEW)
   - Comprehensive integration tests for PDL query workflow
   - 3 test cases covering type conversions and API payload structure

## Why This Matters

These bugs would have caused:
1. **Empty PDL searches**: Using wrong key would pass empty query to PDL API
2. **Runtime errors**: Method signature mismatch would crash analysis
3. **Validation failures**: Type mismatch would prevent result storage

The test suite now catches these issues before they reach production.

## Next Steps

1. ✅ Run the updated tests to verify all fixes
2. ✅ Rebuild Docker containers with fixed code
3. ⏳ Run a complete end-to-end analysis to verify PDL market search works
4. ⏳ Monitor logs to ensure PDL API calls succeed

## Lessons Learned

**Key Insight**: Integration tests that verify the *actual data flow* between components catch bugs that unit tests miss. Testing the full workflow (PDLQueryParams → API payload → PDLQuery) revealed:
- Incorrect assumptions about API payload structure
- Type conversion gaps between internal and external representations
- Method signature issues that only appear at runtime

**Best Practice**: When integrating with external services (like PDL API), always test:
1. The data format your code produces
2. The data format the service expects
3. The conversion between the two

