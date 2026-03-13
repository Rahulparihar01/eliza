# Sync Execution Layer - Architecture & Purpose

## 📋 Overview

The **Sync Execution Layer** is the core orchestration engine of the ingestion pipeline. It coordinates the entire data flow from external APIs through to transformed, queryable domain models.

## 🎯 Purpose

The sync execution layer serves as the **central orchestrator** that:

1. **Manages the complete ingestion lifecycle** from trigger to completion
2. **Coordinates multiple subsystems** (connectors, transformers, storage)
3. **Tracks progress and metrics** at every step
4. **Handles errors gracefully** with rollback and retry logic
5. **Provides observability** through telemetry and logging
6. **Ensures data quality** through validation and deduplication

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYNC EXECUTION LAYER                          │
│                  (ConnectorService.execute_sync)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   EXTRACT    │ ──> │   LOAD       │ ──> │  TRANSFORM   │   │
│  │  (Connector) │     │  (IngestedData)│   │ (Transformer)│   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                     │                     │           │
│         └─────────────────────┴─────────────────────┘           │
│                               │                                  │
│                               ▼                                  │
│                    ┌──────────────────┐                         │
│                    │   TELEMETRY      │                         │
│                    │   & TRACKING     │                         │
│                    └──────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 Pipeline Stages

### Stage 1: Trigger (trigger_sync)
**Purpose:** Initiate a sync operation  
**Location:** `ConnectorService.trigger_sync()`

**Steps:**
1. Validate connector configuration exists and is enabled
2. Check no active sync is already running
3. Create `ConnectorSyncRun` record with PENDING status
4. Generate unique sync_id
5. Dispatch Celery task for async execution
6. Return sync run record to caller

**Database Changes:**
- `INSERT` into `connector_sync_runs` (status: PENDING)

**Output:** `ConnectorSyncRun` object with task metadata

---

### Stage 2: Execute (execute_sync)
**Purpose:** Run the complete ingestion pipeline  
**Location:** `ConnectorService.execute_sync()`

**Steps:**
1. Load connector configuration and decrypt credentials
2. Initialize connector instance (e.g., PDLConnector)
3. Update sync status to RUNNING
4. Stream records in batches from external API
5. Save raw batches to staging (IngestedData)
6. Transform batches to domain models (PDLPerson)
7. Log telemetry for observability
8. Update final sync status (COMPLETED/FAILED)
9. Calculate and store metrics

**Database Changes:**
- `UPDATE connector_sync_runs` (status: RUNNING → COMPLETED)
- `INSERT` into `ingested_data` (raw staging records)
- `INSERT/UPSERT` into `pdl_persons` (transformed domain models)
- `INSERT` into `connector_telemetry` (events, metrics)

**Output:** Sync result dictionary with counts and status

---

### Stage 3: Transform (within execute_sync)
**Purpose:** Convert raw API data to queryable domain models  
**Location:** `PDLTransformer.transform_batch()`

**Steps:**
1. Validate raw record structure
2. Map API fields to domain model fields
3. Normalize data (e.g., lowercase, standardize formats)
4. Enrich with metadata (customer_id, sync_id)
5. Check for duplicates (by pdl_id)
6. UPSERT into domain table (PDLPerson)
7. Track first_seen and last_updated

**Deduplication Logic:**
- Primary key: `pdl_id` (from People Data Labs)
- On duplicate: UPDATE existing record
- Track: `sync_count`, `first_seen_sync_id`, `last_updated_sync_id`

---

## 📊 Data Flow

```
External API (PDL)
       │
       │ [1] API Call (with rate limiting)
       ▼
 ┌─────────────┐
 │  Connector  │ (people_data_labs.py)
 │  read_stream()│
 └─────────────┘
       │
       │ [2] Raw JSON batches
       ▼
 ┌─────────────┐
 │ IngestedData│ (staging table)
 │   (raw)     │
 └─────────────┘
       │
       │ [3] Transform batch
       ▼
 ┌─────────────┐
 │ Transformer │ (pdl_transformer.py)
 │ transform_batch()│
 └─────────────┘
       │
       │ [4] Normalized records
       ▼
 ┌─────────────┐
 │  PDLPerson  │ (domain model)
 │  (clean)    │
 └─────────────┘
       │
       │ [5] Queryable data
       ▼
   Application
   (Search, Analytics, etc.)
```

## 🔍 Key Components

### 1. ConnectorService
**File:** `src/services/ingestion/connector_service.py`

**Responsibilities:**
- Configuration management (CRUD)
- Sync orchestration (trigger, execute)
- Status tracking and updates
- Telemetry logging
- Error handling and recovery

**Key Methods:**
- `trigger_sync()` - Initiate sync
- `execute_sync()` - Run full pipeline
- `_log_telemetry()` - Track metrics
- `get_credentials()` - Decrypt secrets

---

### 2. Connector (e.g., PDLConnector)
**File:** `src/services/ingestion/connectors/people_data_labs.py`

**Responsibilities:**
- API authentication
- Query construction (Elasticsearch DSL)
- Rate limiting (token bucket algorithm)
- Streaming data extraction
- Connection health checks
- Cost estimation

**Key Methods:**
- `check()` - Test connection
- `estimate_record_count()` - Cost estimation
- `read_stream()` - Stream batches
- `get_sample_record()` - Schema discovery

---

### 3. Transformer (PDLTransformer)
**File:** `src/services/ingestion/transformers/pdl_transformer.py`

**Responsibilities:**
- Schema mapping (API → Domain)
- Data validation and normalization
- Deduplication logic
- Enrichment (metadata, timestamps)
- Error handling for bad records

**Key Methods:**
- `transform_batch()` - Process batch
- `_upsert_person()` - Save with dedup
- `_normalize_record()` - Clean data

---

### 4. Models

**ConnectorSyncRun:** Tracks each sync execution  
**IngestedData:** Staging for raw API responses  
**PDLPerson:** Clean, queryable domain model  
**ConnectorTelemetry:** Observability events

---

## 📈 Metrics & Telemetry

### Sync Run Metrics
Stored in `connector_sync_runs`:

| Metric | Description | Usage |
|--------|-------------|-------|
| `records_extracted` | Total records fetched from API | Billing, performance |
| `records_loaded` | Records saved to staging | Data validation |
| `records_skipped` | Duplicates detected | Dedup effectiveness |
| `records_failed` | Transform errors | Data quality |
| `duration_seconds` | Total sync time | Performance tuning |
| `api_calls_made` | API requests count | Rate limit tracking |
| `bytes_transferred` | Data volume | Bandwidth monitoring |
| `cost_incurred` | Estimated API cost | Budget tracking |

### Telemetry Events
Stored in `connector_telemetry`:

| Event Type | When | Purpose |
|------------|------|---------|
| `SYNC_STARTED` | Sync begins | Audit trail |
| `RECORDS_FETCHED` | After API call | Progress tracking |
| `RECORDS_TRANSFORMED` | After transform | Quality metrics |
| `SYNC_COMPLETED` | Success | Success rate |
| `SYNC_FAILED` | Error | Error tracking |
| `RATE_LIMIT_HIT` | 429 response | Throttling alerts |

---

## 🛡️ Error Handling

### Failure Scenarios

1. **API Connection Failure**
   - Status: `FAILED`
   - Retry: Yes (with exponential backoff)
   - Rollback: None (no data written yet)

2. **Transform Error**
   - Status: `COMPLETED` (partial)
   - Retry: No (skip bad records)
   - Rollback: None (keep good records)
   - Tracking: `records_failed` count

3. **Rate Limit Hit**
   - Status: `RUNNING` (paused)
   - Retry: Yes (after backoff)
   - Rollback: None (resume from checkpoint)

4. **Database Error**
   - Status: `FAILED`
   - Retry: Depends on error type
   - Rollback: Transaction-level

---

## 🎯 Design Principles

### 1. **Idempotency**
- Same sync can be re-run safely
- Deduplication prevents data corruption
- Checksums track already-processed batches

### 2. **Observability**
- Every step logged with context
- Metrics tracked at batch level
- Telemetry events for monitoring

### 3. **Resilience**
- Graceful error handling
- Partial success supported
- Automatic retries with backoff

### 4. **Scalability**
- Streaming architecture (not bulk load)
- Batch processing (not record-by-record)
- Async execution (Celery tasks)

### 5. **Separation of Concerns**
- Connector: API interaction only
- Transformer: Business logic only
- Service: Orchestration only

---

## 🔧 Configuration

### Sync Configuration Structure
```json
{
  "search_query": {
    "job_title_role": ["software engineer"],
    "location_country": ["United States"]
  },
  "max_records": 1000,
  "page_size": 100,
  "rate_limit": 60,
  "estimated_cost_acknowledged": true
}
```

### Credentials (Encrypted)
```json
{
  "api_key": "encrypted_with_fernet"
}
```

---

## 📊 Current Status

### ✅ Implemented
- Connector layer (PDL)
- Transformer layer
- Sync orchestration
- Configuration management
- Telemetry logging
- Rate limiting
- Deduplication
- Error handling

### ⚠️ Known Issues
1. **Field Name Mismatch:** Code uses `records_read` but model has `records_extracted`
2. **Missing Telemetry Fields:** Some ConnectorTelemetry fields not in model
3. **IngestedData Schema:** Missing `sync_run_id` field

### 🔄 In Progress
- Test suite fixes (7/16 passing)
- Model field alignment
- Search integration (Elasticsearch, Neo4j)

---

## 🚀 Next Steps

1. **Fix Model Field Alignment**
   - Align service field names with model definitions
   - Update migration if needed

2. **Complete Test Suite**
   - Fix test_07 (trigger_sync)
   - Fix test_08 (execute_sync)
   - Unlock tests 9-16

3. **Add Search Layer**
   - Elasticsearch for full-text search
   - Neo4j for graph queries
   - Unified search service

4. **Production Hardening**
   - Add circuit breakers
   - Implement dead letter queue
   - Add monitoring dashboards

---

**Last Updated:** October 9, 2025  
**Status:** 🔧 Active Development (Bug Fixes in Progress)

