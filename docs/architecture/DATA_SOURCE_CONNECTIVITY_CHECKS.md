# Data Source Connectivity Checks

## Overview

The BI question answering pipeline now includes robust connectivity checks for all data sources **before** invoking CrewAI agents. This ensures early failure detection and provides real-time feedback to users about data source availability.

---

## 🎯 Architecture

### Flow Integration

```
User Question Submission
    ↓
Task Enrichment Flow (CrewAI)
    ↓
✨ DATA SOURCE CONNECTIVITY CHECKS ✨  ← NEW
    ├─ Check HR Database (PostgreSQL)
    ├─ Check Vector Index (FAISS)
    └─ Send Telemetry Events
    ↓
Data Analysis Flow (CrewAI)
    ├─ Data Retrieval Agent
    └─ Data Analysis Agent
    ↓
Results Returned
```

### Integration Point

**Location**: `src/tasks/business_intelligence_tasks.py`  
**Line**: Between enrichment completion (~179) and analysis flow creation (~271)

The checks happen after:
- ✅ Question validation
- ✅ Task enrichment (intent analysis, context enrichment)

The checks happen before:
- ⏸️ Data Analysis Flow creation
- ⏸️ CrewAI agent invocation
- ⏸️ Tool calls to data sources

---

## 🔧 Components

### 1. Connectivity Service

**File**: `src/services/connectivity_service.py`

**Class**: `ConnectivityService`

#### Methods

##### `check_hr_database_connectivity(customer_id: str) -> Dict`

Checks PostgreSQL HR database connectivity:
- ✅ Database connection health
- ✅ Connection pool status
- ✅ Customer data availability
- ✅ Query execution capability

**Returns**:
```python
{
    "status": "healthy" | "unhealthy",
    "source": "hr_database",
    "message": "HR database connection successful",
    "available": True | False,
    "has_customer_data": True | False,
    "details": {
        "engine_pool_size": 5,
        "engine_pool_checked_in": 4,
        "engine_pool_checked_out": 1,
        "customer_id": "local-dev",
        "data_available": True
    }
}
```

##### `check_vector_index_connectivity(customer_id: str) -> Dict`

Checks FAISS vector index connectivity:
- ✅ Index file exists (`data/vectors/faiss_index.bin`)
- ✅ Mapping file exists (`data/vectors/chunk_mapping.json`)
- ✅ Index is readable
- ✅ Customer has indexed documents

**Returns**:
```python
{
    "status": "healthy" | "unhealthy",
    "source": "vector_index",
    "message": "Vector index connection successful",
    "available": True | False,
    "details": {
        "vector_dir": "./data/vectors",
        "index_exists": True,
        "mapping_exists": True,
        "total_vectors": 42,
        "total_chunks": 42,
        "index_type": "IndexFlatIP",
        "dimension": 384,
        "has_customer_data": True
    }
}
```

##### `check_all_data_sources(customer_id: str) -> Dict`

Runs all connectivity checks and returns aggregated results.

**Returns**:
```python
{
    "hr_database": { ... },
    "vector_index": { ... }
}
```

##### `get_connectivity_summary(results: Dict) -> str`

Generates human-readable summary:
- `"✓ All data sources ready (2 sources verified)"`
- `"Data source status: ✓ 1 healthy, ✗ 1 unavailable"`

#### Convenience Function

```python
from src.services.connectivity_service import check_data_source_connectivity

results = check_data_source_connectivity(customer_id="local-dev")
```

---

## 📊 Error Handling Strategy

### Critical vs. Non-Critical Failures

#### Vector Index (CRITICAL)

**Status**: ALWAYS REQUIRED  
**Reason**: DocumentSearchTool is marked as mandatory for every query

**Behavior**:
- ❌ **Unhealthy** → Fail immediately
- 📝 Update question status to `FAILED`
- 📢 Return error to user
- 🚫 **Do not** invoke CrewAI agents

**Error Message**:
```
"Vector index connectivity check failed: [details]. 
Document search is required for all queries."
```

#### HR Database (NON-CRITICAL)

**Status**: CONDITIONAL  
**Reason**: Some questions don't need HR data (e.g., document-only queries)

**Behavior**:
- ⚠️ **Unhealthy** → Log warning, continue
- 📝 Keep question status as `ANALYZING`
- 📢 Show warning in telemetry
- ✅ **Do** invoke CrewAI agents

**Warning Message**:
```
"HR database unavailable. Query will use document search only."
```

### Graceful Degradation

```
All Healthy → Full functionality
HR Down → Document search only
Vector Down → Fail fast with clear error
Both Down → Fail fast with actionable message
```

---

## 📡 Telemetry Integration

### Telemetry Events

The connectivity checks generate real-time user-facing messages via the telemetry system.

#### 1. Pre-Check Event

```python
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.INFO,
    user_message="Verifying data source connectivity...",
    progress_percentage=15.0,
)
```

#### 2. Per-Source Events (Healthy)

```python
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.INFO,
    user_message="✓ HR Database connected",
    progress_percentage=18.0,
)

bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.INFO,
    user_message="✓ Document Search connected",
    progress_percentage=18.0,
)
```

#### 3. Per-Source Events (Unhealthy)

```python
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.WARNING,
    user_message="⚠ HR Database unavailable: Connection timeout",
    progress_percentage=18.0,
)
```

#### 4. Data Availability Notes

```python
# When data source is healthy but empty
bi_service.add_telemetry_event(
    session_id=analysis_session.id,
    event_type=TelemetryEventType.INFO,
    user_message="✓ HR Database connected (no data available)",
    progress_percentage=18.0,
)
```

### User Experience

Users see real-time progress updates via Server-Sent Events (SSE):

```
[10%] Running task enrichment
[15%] Verifying data source connectivity...
[18%] ✓ HR Database connected
[18%] ✓ Document Search connected
[25%] Retrieving data from HR database and documents...
[50%] Data retrieval completed
[75%] Analyzing data and generating insights...
[100%] Analysis completed successfully
```

---

## 🔍 Logging

All connectivity checks emit structured logs with metadata.

### Log Events

#### Success Logs

```python
logger.info(
    "hr_database_connectivity_success",
    category=LogCategory.SYSTEM,
    metadata={
        "customer_id": "local-dev",
        "has_data": True
    }
)

logger.info(
    "vector_index_connectivity_success",
    category=LogCategory.SYSTEM,
    metadata={
        "customer_id": "local-dev",
        "total_vectors": 42,
        "has_customer_data": True
    }
)
```

#### Warning Logs

```python
logger.warning(
    "hr_database_connectivity_warning",
    question_id=question_id,
    message="Connection pool exhausted",
    details={"pool_size": 5, "checked_out": 5}
)
```

#### Error Logs

```python
logger.error(
    "vector_index_connectivity_failed",
    question_id=question_id,
    error="Index file not found",
    details={"path": "./data/vectors/faiss_index.bin"}
)
```

---

## 🧪 Testing

### Test Script

**File**: `test_connectivity_service.py`

#### Run Tests

```bash
# Test with default customer
python test_connectivity_service.py

# Test with specific customer (via environment)
export CUSTOMER_ID=local-dev
python test_connectivity_service.py
```

#### Expected Output

```
================================================================================
🔍 Testing Data Source Connectivity Service
================================================================================

Testing connectivity for customer: local-dev

📊 Checking HR Database connectivity...
   Status: healthy
   Message: HR database connection successful
   Available: True
   Has Customer Data: True

📚 Checking Vector Index connectivity...
   Status: healthy
   Message: Vector index connection successful
   Available: True
   Total Vectors: 42

🌐 Checking all data sources...

--------------------------------------------------------------------------------
Summary:
--------------------------------------------------------------------------------
✅ Hr Database: healthy
   HR database connection successful
✅ Vector Index: healthy
   Vector index connection successful

================================================================================
Overall: ✓ All data sources ready (2 sources verified)
================================================================================
```

### Manual Testing

```python
from src.services.connectivity_service import ConnectivityService

service = ConnectivityService()

# Test HR database
hr_result = service.check_hr_database_connectivity("local-dev")
print(hr_result)

# Test vector index
vector_result = service.check_vector_index_connectivity("local-dev")
print(vector_result)

# Test all sources
all_results = service.check_all_data_sources("local-dev")
print(service.get_connectivity_summary(all_results))
```

### Integration Testing

Test the full BI pipeline with connectivity checks:

```python
import requests

# Submit a BI question
response = requests.post(
    "http://localhost:8000/v1/bi/questions",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    json={"question": "How many employees do we have?"}
)

question_id = response.json()["question_id"]

# Stream telemetry events
import sseclient

events = sseclient.SSEClient(
    f"http://localhost:8000/v1/bi/questions/{question_id}/stream",
    headers={"Authorization": "Bearer YOUR_TOKEN"}
)

for event in events:
    print(event.data)  # Should see connectivity check messages
```

---

## 📈 Performance Characteristics

### Timing

- **HR Database Check**: ~10-50ms (fast connection test)
- **Vector Index Check**: ~50-200ms (file I/O + index loading)
- **Total Overhead**: ~100-300ms

### Impact

The connectivity checks add minimal overhead (~0.3 seconds) to the overall BI pipeline:

```
Total Pipeline Time: 30-60 seconds
Connectivity Checks: 0.1-0.3 seconds (~0.5% overhead)
```

### Benefits vs. Cost

**Benefits**:
- ✅ Early failure detection (saves 30-60 seconds on errors)
- ✅ Clear error messages (improved UX)
- ✅ Real-time feedback (better observability)

**Cost**:
- ⚠️ +0.3 seconds latency (negligible)
- ⚠️ +2 log events per source (acceptable)

---

## 🚀 Future Enhancements

### Optional Features (Not Yet Implemented)

#### 1. Health Check Endpoint

Expose connectivity status via REST API:

```python
# src/api/routes/business_intelligence.py

@router.get("/health/data-sources")
async def check_data_sources_health(
    customer_id: str = Depends(get_customer_id)
):
    """Check connectivity to all data sources."""
    from src.services.connectivity_service import check_data_source_connectivity
    
    results = check_data_source_connectivity(customer_id)
    return {
        "customer_id": customer_id,
        "data_sources": results,
        "timestamp": datetime.utcnow().isoformat()
    }
```

#### 2. Retry Logic

Auto-retry failed connectivity checks:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def check_hr_database_connectivity(customer_id: str) -> Dict:
    # ... existing logic ...
```

#### 3. Connectivity Cache

Cache connectivity status for 30 seconds:

```python
from functools import lru_cache
from time import time

@lru_cache(maxsize=128)
def _cached_connectivity_check(customer_id: str, cache_key: int) -> Dict:
    # cache_key = int(time() / 30)  # 30-second buckets
    return check_data_source_connectivity(customer_id)
```

#### 4. Metrics Collection

Track connectivity success/failure rates:

```python
from prometheus_client import Counter, Histogram

connectivity_checks = Counter(
    'bi_connectivity_checks_total',
    'Total connectivity checks',
    ['customer_id', 'source', 'status']
)

connectivity_duration = Histogram(
    'bi_connectivity_check_duration_seconds',
    'Connectivity check duration',
    ['source']
)
```

---

## 📝 Summary

### What Was Implemented

✅ **ConnectivityService** - Robust connectivity checking service  
✅ **HR Database Checks** - Connection health + customer data availability  
✅ **Vector Index Checks** - File existence + index readability  
✅ **Pipeline Integration** - Added to BI task flow before CrewAI agents  
✅ **Telemetry Events** - Real-time user feedback via SSE  
✅ **Error Handling** - Graceful degradation with clear error messages  
✅ **Structured Logging** - Observable connectivity checks with metadata  
✅ **Test Script** - Standalone testing utility  
✅ **Documentation** - Comprehensive guide (this file)

### Key Design Decisions

1. **Early Checks**: Run connectivity checks **before** CrewAI agents to fail fast
2. **Differential Treatment**: Vector index is critical, HR database is optional
3. **User Feedback**: Real-time telemetry events show connectivity status
4. **Graceful Degradation**: Continue with partial functionality when possible
5. **Observability**: Structured logs with customer_id and metadata throughout

---

## 🎓 Usage Examples

### Example 1: All Systems Healthy

```
User submits: "How many engineers do we have?"

[Logs]
✓ hr_database_connectivity_success (has_data=True)
✓ vector_index_connectivity_success (vectors=42)

[Telemetry]
"Verifying data source connectivity..."
"✓ HR Database connected"
"✓ Document Search connected"
"Retrieving data from HR database and documents..."

[Result]
Analysis proceeds normally
```

### Example 2: HR Database Down (Non-Critical)

```
User submits: "What's in our latest engineering document?"

[Logs]
⚠ hr_database_connectivity_warning (connection_timeout)
✓ vector_index_connectivity_success (vectors=42)

[Telemetry]
"Verifying data source connectivity..."
"⚠ HR Database unavailable: Connection timeout"
"✓ Document Search connected"
"Retrieving data from documents..."

[Result]
Analysis proceeds with documents only
```

### Example 3: Vector Index Down (Critical)

```
User submits: "Analyze our hiring trends"

[Logs]
✓ hr_database_connectivity_success (has_data=True)
❌ vector_index_connectivity_failed (index_file_missing)

[Telemetry]
"Verifying data source connectivity..."
"✓ HR Database connected"
"❌ Vector index unavailable"

[Result]
Question status → FAILED
Error: "Vector index connectivity check failed: Index files missing. 
        Document search is required for all queries."
```

---

**Status**: ✅ Production Ready  
**Version**: 1.0  
**Last Updated**: October 4, 2025

