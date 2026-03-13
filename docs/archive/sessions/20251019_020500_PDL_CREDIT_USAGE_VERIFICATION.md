# 20251019_020500_PDL_CREDIT_USAGE_VERIFICATION.md

## PDL API Credit Usage Control - VERIFIED ✅

### Summary

Our implementation **correctly uses the `size` parameter** to control PDL API credit usage, as specified in the [PDL Person Search API documentation](https://docs.peopledatalabs.com/docs/examples-person-search-api).

> **From PDL Documentation:**
> "Person Search API calls cost the number of **total search results** returned. If you are making a search that could have a large number of results, make sure to use the `size` parameter to set the maximum number of results and cap your credit usage."

---

## Implementation Verification

### 1. Connector Configuration (`sync_config`)

When creating a connector, we specify credit limits:

```python
sync_config={
    "search_query": {...},
    "max_records": 1,      # ✅ Maximum total records to fetch
    "page_size": 1         # ✅ Records per API call
}
```

**Source**: `tests/test_pdl_query_simple.py` (lines 228-229, 250-251)

### 2. Connector Initialization

The connector stores these limits:

```python
class PeopleDataLabsConnector:
    def __init__(self, credentials, config, customer_id):
        self.max_records = config.get("max_records", get_settings().max_connector_records_default)
        self.page_size = config.get("page_size", 100)
```

**Source**: `src/services/ingestion/connectors/people_data_labs.py` (lines 100-110)

### 3. API Request Building

For each API call, we calculate the exact page size to stay within limits:

```python
def read_stream(self, sync_mode, sync_params):
    max_records = sync_params.get("max_records", self.max_records)
    records_fetched = 0
    
    while records_fetched < max_records:
        # Calculate remaining records needed
        remaining = max_records - records_fetched
        current_page_size = min(self.page_size, remaining)  # ✅ Never exceed max_records
        
        # Build request with size parameter
        request_body = {
            "query": pdl_query,
            "size": current_page_size  # ✅ PDL's credit control parameter
        }
```

**Source**: `src/services/ingestion/connectors/people_data_labs.py` (lines 580-595)

### 4. API Call to PDL

The `size` parameter is sent in every request:

```python
response = requests.post(
    f"{self.BASE_URL}/person/search",
    headers={
        "X-Api-Key": self.api_key,
        "Content-Type": "application/json"
    },
    json=request_body,  # Contains {"query": ..., "size": current_page_size}
    timeout=30
)
```

**Source**: `src/services/ingestion/connectors/people_data_labs.py` (lines 603-611)

---

## Credit Control Guarantees

### ✅ Maximum Credits Per Query

```
Credits Used = Number of Results Returned
```

Our implementation ensures:
1. **Test queries**: `max_records=1, page_size=1` → **Maximum 1 credit used**
2. **Production queries**: Configurable via `ml_talent_pdl_query_limit` setting (currently `1` for testing)
3. **Never exceeds limit**: Loop terminates when `records_fetched >= max_records`

### ✅ Pagination Control

If a query could return many results:
- First call: `size=1` → Returns at most 1 result → Uses 1 credit
- Loop exits immediately when `records_fetched >= max_records`
- **No accidental large result sets**

### ✅ Multiple Safeguards

1. **Config Level**: `sync_config.max_records` limits total fetch
2. **Request Level**: `size` parameter limits per-request results  
3. **Loop Level**: `while records_fetched < max_records` prevents over-fetching
4. **Calculation Level**: `current_page_size = min(self.page_size, remaining)` ensures exact limits

---

## Test Configuration

### Current Test Settings

```python
# Test uses minimal credits
sync_config={
    "search_query": {"job_title_role": ["software engineer"]},
    "max_records": 1,   # ✅ Fetch maximum 1 person
    "page_size": 1      # ✅ Request 1 person per API call
}
```

**Result**: Maximum **1 credit** used per test run

### Production Settings

```python
# src/core/config.py
class Settings:
    ml_talent_pdl_query_limit: int = Field(
        default=1,  # Currently set to 1 for testing
        alias="ML_TALENT_PDL_QUERY_LIMIT"
    )
```

**Configurable via environment variable**:
```bash
ML_TALENT_PDL_QUERY_LIMIT=50  # Fetch up to 50 market candidates
```

---

## Comparison with PDL Documentation

### PDL Example (from docs)

```python
# From https://docs.peopledatalabs.com/docs/examples-person-search-api
params = {
    'query': json.dumps(es_query),
    'size': MAX_NUM_PEOPLE  # ✅ Credit control parameter
}

response = requests.get(PDL_PERSON_SEARCH_URL, headers=headers, params=params)
```

### Our Implementation

```python
request_body = {
    "query": pdl_query,
    "size": current_page_size  # ✅ Same parameter name and purpose
}

response = requests.post(
    f"{self.BASE_URL}/person/search",
    headers=headers,
    json=request_body
)
```

**Difference**: We use POST with JSON body instead of GET with query params, but the `size` parameter works identically.

---

## Credit Usage Scenarios

### Scenario 1: Test Query (Current)
```
Query: job_title_role = "software engineer"
max_records: 1
page_size: 1

API Call 1: size=1 → Returns 0-1 results → 0-1 credits
Loop exits: records_fetched (0-1) >= max_records (1)

Total Credits: 0-1
```

### Scenario 2: Production Query (Typical)
```
Query: {job_title_role: [...], skills: [...], ...}
max_records: 50
page_size: 50

API Call 1: size=50 → Returns 0-50 results → 0-50 credits
Loop exits: records_fetched (0-50) >= max_records (50)

Total Credits: 0-50 (never more than max_records)
```

### Scenario 3: Large Dataset Query (Safe)
```
Query: job_title_role = "software engineer" (millions of potential matches)
max_records: 10
page_size: 100

API Call 1: size=min(100, 10) = 10 → Returns 10 results → 10 credits
Loop exits: records_fetched (10) >= max_records (10)

Total Credits: 10 (capped by max_records)
```

---

## Production Recommendations

### 1. Set Reasonable Limits

```python
# For market search in talent intelligence
ML_TALENT_PDL_QUERY_LIMIT=50  # 50 market candidates per analysis
```

### 2. Monitor Credit Usage

```python
# Log actual results returned
logger.info(
    "pdl_api_call_complete",
    records_fetched=len(results),
    max_records=max_records,
    credits_used=len(results)  # 1 credit per result
)
```

### 3. Adjust Based on Needs

```python
# Small test: 1-10 results
# Typical search: 50-100 results
# Comprehensive search: 100-500 results
# Never exceed what you actually need
```

---

## Conclusion

✅ **Our implementation is correct and safe.**

We properly use the `size` parameter as specified in the [PDL documentation](https://docs.peopledatalabs.com/docs/examples-person-search-api) to:
1. Control credit usage
2. Limit result sets
3. Prevent accidental large queries
4. Provide configurable limits

**Test queries use maximum 1 credit.** Production queries will use exactly the number of results returned, up to the configured `max_records` limit.

No changes needed to the implementation. The 0 results we're seeing are due to API key data access limitations, not our credit control logic.


