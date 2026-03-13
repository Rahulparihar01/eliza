# PDL Query Limit Made Configurable
**Date**: October 18, 2025, 9:37 PM PST

## Change Summary

Made PDL API query limit configurable via settings and parameters. Default is **1 record** for cost-controlled testing, easily changed to 50 for production.

## Files Modified

### 1. `src/core/config.py`
**Line 113**: Added new setting

```python
# ML Talent Intelligence Configuration
ml_talent_pdl_query_limit: int = Field(
    default=1, 
    alias="ML_TALENT_PDL_QUERY_LIMIT", 
    description="Number of candidates to retrieve from PDL market search (1 for testing, 50 for production)"
)
```

### 2. `src/services/talent/orchestrator.py`
**Constructor**: Added `pdl_query_limit` parameter

```python
def __init__(
    self,
    customer_id: str,
    user_id: int,
    neo4j_enabled: bool = True,
    pdl_query_limit: Optional[int] = None  # New parameter
):
    # Get PDL query limit from settings if not provided
    if pdl_query_limit is None:
        from src.core.config import settings
        self.pdl_query_limit = settings.ml_talent_pdl_query_limit
    else:
        self.pdl_query_limit = pdl_query_limit
```

**Market search**: Uses `self.pdl_query_limit`

```python
logger.info("calling_pdl_api", query_version=pdl_query.version, limit=self.pdl_query_limit)
results = await asyncio.to_thread(
    pdl_service.search_people,
    query=api_payload.get("search_query", {}),
    limit=self.pdl_query_limit
)
```

### 3. `src/services/talent/pdl_query_builder.py`
**Method signature**: Added `limit` parameter

```python
def build_initial_query(
    self,
    diagnostic: DiagnosticReport,
    baseline: BaselineProfile,
    role: str = "Machine Learning Engineer",
    limit: int = 50  # New parameter with default
) -> PDLQueryParams:
```

**Query building**: Uses `limit` parameter

```python
query_params = PDLQueryParams(
    # ... other fields ...
    limit=limit,  # Configurable limit (default 50, can be overridden)
    version=1,
    refinement_notes="Initial query based on diagnostic analysis"
)
```

## Impact

### Expected Behavior
- **Stage 5 (Market Search)**: PDL API will return only 1 candidate
- **Stage 6 (Score Market)**: Will score only 1 market candidate
- **Stage 7 (Synthesis)**: Will synthesize results with minimal market data
- **Cost**: Minimal PDL API credits consumed (1 record instead of 50)

### Testing Flow
1. ✅ Stage 1: Baseline (1 employee)
2. ✅ Stage 2: Diagnostic Analysis
3. ✅ Stage 3: Parse Resumes (0 resumes - no files)
4. ✅ Stage 4: Score Applicants (0 scores)
5. ⏳ **Stage 5: Market Search (will query PDL for 1 candidate)**
6. ⏳ Stage 6: Score Market Candidate (1 score)
7. ⏳ Stage 7: Synthesis
8. ⏳ Final Result

### How to Change the Limit

**Option 1: Environment Variable (Recommended)**
Add to `docker/.env`:
```bash
ML_TALENT_PDL_QUERY_LIMIT=50
```

**Option 2: API Parameter (Future Feature)**
Pass `pdl_query_limit` when creating the orchestrator:
```python
orchestrator = TalentIntelligenceOrchestrator(
    customer_id="eliza",
    user_id=2,
    pdl_query_limit=50  # Override setting
)
```

**Option 3: Settings File**
Modify `src/core/config.py` default:
```python
ml_talent_pdl_query_limit: int = Field(default=50, ...)
```

### Production Deployment
When ready for production:
1. Set `ML_TALENT_PDL_QUERY_LIMIT=50` in environment
2. Rebuild Docker container
3. (Optional) Add UI control for users to customize limit

## Verification

To verify the limit is being applied:
1. Check logs for: `calling_pdl_api ... limit=1`
2. Monitor PDL API usage in dashboard
3. Confirm only 1 market candidate in results

## Status

- ✅ Changes applied
- ✅ App rebuilt
- ✅ App restarted
- 🎯 **READY FOR TESTING**

Submit a new analysis to test the complete flow with PDL limit = 1! 🚀

