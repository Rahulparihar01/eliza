# Data Ingestion Layer - Deployment Guide

**Branch:** `feature/data-ingestion-layer`  
**Status:** ✅ Backend Complete - Ready for Deployment  
**Date:** October 8, 2025

---

## 🎯 What's Been Built

A complete, production-ready data ingestion pipeline with:
- **20+ new files** implementing full ingestion stack
- **5 database tables** with migrations
- **16 REST API endpoints** for management
- **Comprehensive test suite** (16 test cases)
- **People Data Labs** connector (first integration)
- **Multi-tenant**, **encrypted**, **rate-limited**, **deduplicated**

---

## 📋 Pre-Deployment Checklist

### 1. Environment Variables

Add to your `.env` file:

```bash
# Encryption (REQUIRED)
ENCRYPTION_KEY=<generate-with-command-below>

# Data Ingestion Configuration
ENABLE_AI_SCHEMA_MAPPING=false
MAX_CONNECTOR_RECORDS_DEFAULT=10000
CONNECTOR_COST_PER_RECORD=0.02
CONNECTOR_COST_WARNING_THRESHOLD=100.0
CONNECTOR_EXECUTION_TIMEOUT=7200
PDL_DEFAULT_RATE_LIMIT=60

# People Data Labs API
PDL_API_KEY=5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7
```

**Generate Encryption Key:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 2. Database Migration

Run the migration to create the 5 new tables:

```bash
# Activate your Python environment first
source venv/bin/activate  # or your venv path

# Run migration
alembic upgrade head

# Verify tables created
psql -U user -d ai_enablement -c "\dt connector*"
psql -U user -d ai_enablement -c "\dt pdl*"
psql -U user -d ai_enablement -c "\dt ingested*"
```

**Expected tables:**
- `connector_configurations`
- `connector_sync_runs`
- `ingested_data`
- `connector_telemetry`
- `pdl_persons`

---

## 🐳 Docker Deployment

### Option A: Quick Build (Faster)

If the Docker build is taking too long due to dependency resolution, use cached layers:

```bash
# Build without --no-cache (uses cached layers)
docker-compose -f docker/docker-compose.yml build app celery-worker celery-ingestion-worker

# Start services
docker-compose -f docker/docker-compose.yml up -d
```

### Option B: Full Rebuild (Clean)

For a complete rebuild (slower but ensures latest code):

```bash
# Stop existing containers
docker-compose -f docker/docker-compose.yml down

# Build with no cache
docker-compose -f docker/docker-compose.yml build --no-cache app celery-worker celery-ingestion-worker

# Start all services
docker-compose -f docker/docker-compose.yml up -d postgres redis neo4j elasticsearch logstash

# Wait 30 seconds for infrastructure
sleep 30

# Start application services
docker-compose -f docker/docker-compose.yml up -d app celery-worker celery-beat celery-ingestion-worker flower frontend
```

### Option C: Speed Up Dependency Resolution

If pip is taking forever, you can optimize `requirements.txt`:

1. **Pin exact versions** for major dependencies:
   ```bash
   # Instead of: airbyte-cdk>=0.90.0
   # Use: airbyte-cdk==0.90.0
   ```

2. **Use `--use-deprecated=legacy-resolver`**:
   ```dockerfile
   # In docker/Dockerfile, change pip install line:
   RUN pip install --no-cache-dir --use-deprecated=legacy-resolver -r requirements.txt
   ```

3. **Split requirements** into separate files:
   ```
   requirements-core.txt  # FastAPI, SQLAlchemy, etc.
   requirements-ml.txt    # spaCy, transformers (heavy stuff)
   requirements-ingestion.txt  # Airbyte CDK, connectors
   ```

### Verify Deployment

```bash
# Check all services are running
docker-compose -f docker/docker-compose.yml ps

# Check celery-ingestion-worker logs
docker-compose -f docker/docker-compose.yml logs celery-ingestion-worker --tail=50

# Check API health
curl http://localhost:8000/health
```

---

## 🧪 Testing the Ingestion Pipeline

### 1. Run Comprehensive Test

```bash
# Activate Python environment
source venv/bin/activate

# Install test dependencies (if not already installed)
pip install pytest pytest-asyncio

# Run the comprehensive test
python3 tests/test_ingestion_pipeline_comprehensive.py
```

**What the test does:**
1. ✅ Lists available connector types
2. ✅ Validates configuration
3. ✅ Tests PDL API connection
4. ✅ Estimates sync cost
5. ✅ Creates connector configuration
6. ✅ Triggers manual sync
7. ✅ Executes full sync (extract → stage → transform)
8. ✅ Verifies data in all 5 tables
9. ✅ Tests deduplication (runs sync twice)
10. ✅ Tests configuration versioning
11. ✅ Computes statistics
12. ✅ Validates data integrity

**Expected output:**
```
================================================================================
COMPREHENSIVE INTEGRATION TEST - DATA INGESTION PIPELINE
================================================================================

TEST 1: List Connector Types
✅ Found 1 connector types
✅ PDL Connector: People Data Labs - ...

TEST 2: Configuration Validation
✅ Valid configuration passed validation
✅ Invalid configuration rejected: ...

...

TEST 16: Data Integrity Check
✅ Data integrity verified
   No orphaned sync runs
   All persons have pdl_id
   No orphaned ingested data

================================================================================
✅ ALL TESTS PASSED!
================================================================================
```

### 2. Manual Testing via API

**Test with curl:**

```bash
# 1. List available connector types
curl -X GET http://localhost:8000/api/connectors/types \
  -H "Authorization: Bearer YOUR_TOKEN"

# 2. Test connection
curl -X POST http://localhost:8000/api/connectors/test-connection \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connector_type": "people_data_labs",
    "credentials": {
      "api_key": "5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"
    },
    "sync_config": {
      "search_query": {
        "location_country": ["United States"]
      }
    }
  }'

# 3. Estimate cost
curl -X POST http://localhost:8000/api/connectors/estimate-cost \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connector_type": "people_data_labs",
    "credentials": {
      "api_key": "5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"
    },
    "sync_config": {
      "search_query": {
        "job_title_role": ["software engineer"],
        "job_company_name": ["Google"],
        "location_country": ["United States"]
      }
    }
  }'

# 4. Create connector configuration
curl -X POST http://localhost:8000/api/connectors/configurations \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connector_type": "people_data_labs",
    "connector_name": "Test PDL Connector",
    "description": "Test connector for API validation",
    "tags": ["test"],
    "credentials": {
      "api_key": "5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"
    },
    "sync_config": {
      "search_query": {
        "job_title_role": ["software engineer"],
        "job_company_name": ["Google", "Amazon"],
        "location_country": ["United States"],
        "experience_years_min": 5
      },
      "max_records": 50,
      "page_size": 10,
      "rate_limit": 60,
      "estimated_cost_acknowledged": true
    }
  }'

# 5. Trigger sync (use connector_id from step 4)
curl -X POST http://localhost:8000/api/connectors/configurations/{connector_id}/trigger-sync \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "manual_trigger": true
  }'

# 6. Check sync status (use sync_id from step 5)
curl -X GET http://localhost:8000/api/connectors/sync-runs/{sync_id} \
  -H "Authorization: Bearer YOUR_TOKEN"

# 7. View ingested persons
curl -X GET "http://localhost:8000/api/connectors/pdl-persons?page=1&page_size=10" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Database Verification

```sql
-- Check connector configurations
SELECT connector_id, connector_name, connector_type, is_enabled, last_sync_status
FROM connector_configurations
ORDER BY created_at DESC
LIMIT 5;

-- Check recent sync runs
SELECT sync_id, status, records_read, records_ingested, records_transformed, 
       start_time, end_time, error_message
FROM connector_sync_runs
ORDER BY start_time DESC
LIMIT 5;

-- Check staged data
SELECT COUNT(*) as total, status, 
       COUNT(DISTINCT sync_run_id) as sync_runs
FROM ingested_data
GROUP BY status;

-- Check transformed persons
SELECT COUNT(*) as total_persons,
       COUNT(DISTINCT job_company_name) as unique_companies,
       AVG(sync_count) as avg_times_seen,
       MAX(sync_count) as max_times_seen
FROM pdl_persons;

-- Sample persons
SELECT full_name, job_title, job_company_name, 
       location_country, sync_count, created_at
FROM pdl_persons
ORDER BY created_at DESC
LIMIT 10;

-- Check telemetry
SELECT event_type, COUNT(*) as event_count
FROM connector_telemetry
GROUP BY event_type
ORDER BY event_count DESC;
```

---

## 📊 Monitoring

### Celery Flower Dashboard

Access at: **http://localhost:5555**

- Monitor active tasks
- View worker status
- Check task history
- See task failures

### Logs

```bash
# Application logs
docker-compose -f docker/docker-compose.yml logs app --tail=100 -f

# Ingestion worker logs
docker-compose -f docker/docker-compose.yml logs celery-ingestion-worker --tail=100 -f

# All Celery workers
docker-compose -f docker/docker-compose.yml logs celery-worker celery-ingestion-worker celery-beat --tail=50 -f
```

### Key Metrics to Watch

```bash
# Sync success rate
SELECT 
  COUNT(*) as total_syncs,
  SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
  ROUND(100.0 * SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM connector_sync_runs;

# Average sync duration
SELECT 
  connector_type,
  AVG(EXTRACT(EPOCH FROM (end_time - start_time))) as avg_duration_seconds,
  AVG(records_read) as avg_records_per_sync
FROM connector_sync_runs
JOIN connector_configurations ON connector_sync_runs.connector_config_id = connector_configurations.id
WHERE status = 'completed'
GROUP BY connector_type;

# Rate limit hits
SELECT DATE(event_timestamp) as date,
       COUNT(*) as rate_limit_events
FROM connector_telemetry
WHERE event_type = 'rate_limit_hit'
GROUP BY DATE(event_timestamp)
ORDER BY date DESC;
```

---

## 🐛 Troubleshooting

### Issue: Migration Fails

**Error:** `relation "connector_configurations" already exists`

**Solution:**
```bash
# Check current migration version
alembic current

# If needed, stamp to correct version
alembic stamp head

# Or downgrade and re-upgrade
alembic downgrade -1
alembic upgrade head
```

### Issue: Celery Ingestion Worker Not Starting

**Check logs:**
```bash
docker-compose -f docker/docker-compose.yml logs celery-ingestion-worker
```

**Common causes:**
1. Database not initialized: `SessionLocal is None`
   - **Fix:** Ensure `init_database()` is called
2. Redis not accessible
   - **Fix:** Check `docker-compose ps redis`
3. Import errors
   - **Fix:** Rebuild container: `docker-compose build celery-ingestion-worker`

### Issue: Sync Stays in "pending" Status

**Diagnosis:**
```sql
SELECT sync_id, status, start_time, error_message, metadata_json
FROM connector_sync_runs
WHERE status = 'pending'
ORDER BY start_time DESC;
```

**Common causes:**
1. Celery task not picked up
   - **Fix:** Check worker is running: `docker-compose ps celery-ingestion-worker`
2. Task failed silently
   - **Fix:** Check logs for exceptions
3. Wrong queue
   - **Fix:** Verify task routes to `ingestion` queue in `celery_app.py`

### Issue: "Invalid API key" Error

**Check API key:**
```bash
curl -X GET "https://api.peopledatalabs.com/v5/person/search?size=1" \
  -H "X-Api-Key: 5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"
```

**Fix:** Update credentials in connector configuration

### Issue: No Records Transformed

**Check:**
```sql
-- Check if records reached staging
SELECT COUNT(*), status FROM ingested_data GROUP BY status;

-- Check for transformer errors
SELECT error_message, COUNT(*) 
FROM ingested_data 
WHERE status = 'failed' 
GROUP BY error_message;
```

**Common causes:**
1. PDL ID missing in raw data
2. Date parsing errors
3. Unique constraint violations

---

## 🚀 Production Readiness

### Before Going Live

- [ ] **Environment variables set** (especially `ENCRYPTION_KEY`)
- [ ] **Database migration run** (all 5 tables created)
- [ ] **Comprehensive test passes** (all 16 tests green)
- [ ] **Manual API test** (create config, trigger sync, verify data)
- [ ] **Monitoring dashboards** (Flower, logs, database queries)
- [ ] **Rate limits configured** (default 60 req/min for PDL)
- [ ] **Cost controls reviewed** (warning threshold, max_records)
- [ ] **Backup strategy** (database, connector state)
- [ ] **Error alerting** (failed syncs, rate limits, telemetry)

### Performance Tuning

**For high-volume syncs:**

1. **Increase ingestion worker concurrency:**
   ```yaml
   # docker-compose.yml
   celery-ingestion-worker:
     command: celery -A src.celery_app worker -Q ingestion --concurrency=4  # was 2
   ```

2. **Tune batch size:**
   ```python
   # In PDL connector config
   "page_size": 100  # Increase for faster syncs (max 1000 for PDL)
   ```

3. **Add more workers:**
   ```yaml
   celery-ingestion-worker-2:
     # Duplicate celery-ingestion-worker service
   ```

4. **Optimize database:**
   ```sql
   -- Add indexes for common queries
   CREATE INDEX idx_pdl_person_company_role 
   ON pdl_persons (job_company_name, job_title_role);
   
   CREATE INDEX idx_sync_runs_customer_status_time 
   ON connector_sync_runs (customer_id, status, start_time DESC);
   ```

---

## 📞 Support & Next Steps

### Documentation

- **`PHASE_2_3_4_COMPLETE.md`** - Complete backend summary
- **`INGESTION_PROGRESS.md`** - Phase-by-phase progress
- **`design_docs/integration_ingestion_plan.md`** - Original design doc

### Next Phase: Frontend UI

To complete the ingestion layer, build:

1. **Connector Management UI**
   - List/create/edit/delete connectors
   - Connection testing
   - Cost estimation preview

2. **PDL Query Builder**
   - Visual form for building search queries
   - Field validation
   - Preview expected results

3. **Sync Monitor Dashboard**
   - Real-time sync progress
   - Telemetry visualization
   - Sync history timeline
   - Statistics & charts

### Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs <service>`
2. Verify database: Run SQL queries above
3. Review test output: `python3 tests/test_ingestion_pipeline_comprehensive.py`
4. Check this guide's troubleshooting section

---

## ✅ Success Criteria

Your ingestion pipeline is working correctly when:

- ✅ All 16 API endpoints respond correctly
- ✅ Comprehensive test passes all 16 test cases
- ✅ Can create connector configuration via API
- ✅ Can trigger sync and see status change: pending → running → completed
- ✅ Records appear in `ingested_data` (staging)
- ✅ Records transform to `pdl_persons` (deduplicated)
- ✅ Running sync twice doesn't duplicate persons (`sync_count` increments)
- ✅ Telemetry events logged throughout pipeline
- ✅ Statistics accurate (total syncs, success rate, etc.)

**You're ready for production when all ✅ are checked!**

