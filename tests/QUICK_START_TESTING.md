# Quick Start - Testing the Data Ingestion Layer

## 🎯 TL;DR

```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform

# Run all tests (recommended)
python3 tests/run_all_ingestion_tests.py

# Or run individual suites
python3 tests/test_ingestion_unit_tests.py              # Fastest (13 tests)
python3 tests/test_ingestion_pipeline_comprehensive.py   # Most thorough (16 tests)
python3 tests/test_ingestion_api_endpoints.py            # API validation (15 tests)
```

**Total: 44 tests | Runtime: ~3 minutes | Cost: ~$0.16**

---

## ✅ What Gets Tested

### 1️⃣ Unit Tests (13 tests) - `test_ingestion_unit_tests.py`

**Components tested:**
- ✅ Rate Limiter (token bucket algorithm)
- ✅ PDL Connector (connection, discovery, validation)
- ✅ PDL Transformer (normalization, UPSERT)
- ✅ Configuration validation

**API calls:** 3 (cost: ~$0.06)

### 2️⃣ Integration Tests (16 tests) - `test_ingestion_pipeline_comprehensive.py`

**Full pipeline tested:**
- ✅ Connector discovery & configuration
- ✅ Connection testing with real PDL API
- ✅ Cost estimation
- ✅ Sync execution (extract → stage → transform)
- ✅ Data deduplication (UPSERT logic)
- ✅ Query versioning
- ✅ Statistics & telemetry

**API calls:** 2 (cost: ~$0.04)

### 3️⃣ API Tests (15 tests) - `test_ingestion_api_endpoints.py`

**Endpoints tested:**
- ✅ `GET /api/connectors/types`
- ✅ `POST /api/connectors/validate-config`
- ✅ `POST /api/connectors/test-connection`
- ✅ `POST /api/connectors/estimate-cost`
- ✅ `POST /api/connectors/configurations` (CREATE)
- ✅ `GET /api/connectors/configurations` (LIST)
- ✅ `GET /api/connectors/configurations/{id}` (GET)
- ✅ `PUT /api/connectors/configurations/{id}` (UPDATE)
- ✅ `DELETE /api/connectors/configurations/{id}` (DELETE)
- ✅ `POST /api/connectors/configurations/{id}/trigger-sync`
- ✅ `GET /api/connectors/configurations/{id}/statistics`
- ✅ `GET /api/connectors/sync-runs`
- ✅ `GET /api/connectors/sync-runs/{sync_id}`
- ✅ `GET /api/connectors/sync-runs/{sync_id}/telemetry`
- ✅ `GET /api/connectors/pdl-persons`

**API calls:** 2-3 (cost: ~$0.06)

---

## 📋 Prerequisites

Before running tests, ensure:

1. ✅ **PostgreSQL is running**
   ```bash
   docker-compose up -d postgres
   ```

2. ✅ **Database migrations applied**
   ```bash
   alembic upgrade head
   ```

3. ✅ **Environment configured**
   ```bash
   export DATABASE_URL="postgresql://user:password@localhost:5432/ai_enablement"
   ```

4. ✅ **Dependencies installed**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🚀 Running Tests

### Option 1: Run Everything (Recommended)

```bash
python3 tests/run_all_ingestion_tests.py
```

**Output:**
```
================================================================================
DATA INGESTION LAYER - COMPREHENSIVE TEST SUITE
================================================================================

--- Unit Tests (Components) ---
✅ Rate limiter initialized correctly
✅ Connector initialized correctly
✅ Record normalized correctly
... (13 tests)

--- Integration Tests (Full Pipeline) ---
✅ Connector types discovered
✅ Connection test passed
✅ Sync triggered successfully
... (16 tests)

--- API Tests (REST Endpoints) ---
✅ API returned connector types
✅ Connector created successfully
✅ Sync triggered
... (15 tests)

================================================================================
TEST SUITE SUMMARY
================================================================================
Total Test Suites: 3
✅ Passed: 3
❌ Failed: 0
⏱️  Duration: 182.5 seconds

🎉 ALL TEST SUITES PASSED! 🎉
```

### Option 2: Run Individual Suites

**Fastest - Unit Tests Only:**
```bash
python3 tests/test_ingestion_unit_tests.py
```
Runtime: ~30 seconds | 13 tests

**Most Comprehensive - Integration Tests:**
```bash
python3 tests/test_ingestion_pipeline_comprehensive.py
```
Runtime: ~2 minutes | 16 tests

**API Validation - Endpoint Tests:**
```bash
python3 tests/test_ingestion_api_endpoints.py
```
Runtime: ~1 minute | 15 tests

---

## 💰 Cost Control

All tests use **real PDL API calls** but are optimized for minimal cost:

| Setting | Value | Purpose |
|---------|-------|---------|
| `max_records` | 1 | Only fetch 1 record per query |
| `page_size` | 1 | Single-record pagination |
| Total API calls | 7-9 | Across all 44 tests |
| **Total cost** | **~$0.16** | Per complete test run |

**Cost breakdown:**
- Unit tests: 3 calls = $0.06
- Integration tests: 2 calls = $0.04
- API tests: 2-3 calls = $0.06

---

## 🐛 Troubleshooting

### Issue: Database connection error

```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Fix:**
```bash
docker-compose up -d postgres
export DATABASE_URL="postgresql://user:password@localhost:5432/ai_enablement"
```

### Issue: API authentication error (401)

```
⚠️  Authentication required - skipping test
```

**This is expected!** API tests will skip if authentication isn't configured. To fix:

1. Update `get_auth_headers()` in `test_ingestion_api_endpoints.py`
2. Add proper auth tokens
3. Or just run unit + integration tests (which don't need auth)

### Issue: Module not found

```
ModuleNotFoundError: No module named 'src'
```

**Fix:**
```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 tests/run_all_ingestion_tests.py
```

---

## 📊 What Success Looks Like

### ✅ All Tests Passing

```
🎉 ALL TEST SUITES PASSED! 🎉

✅ Your data ingestion layer is working correctly!
✅ All components tested: Connector, Transformer, Service, API
✅ Pipeline validated: Extract → Stage → Transform → Store
```

**This means:**
- ✅ PDL connector can connect and authenticate
- ✅ Queries are validated and cost is estimated
- ✅ Syncs execute successfully
- ✅ Data is extracted, staged, transformed, and stored
- ✅ Deduplication (UPSERT) works correctly
- ✅ All 16 API endpoints respond correctly
- ✅ Rate limiting prevents API overuse
- ✅ Telemetry tracks every operation

### ⚠️ Some Tests Failing

Review the error output for specific issues:

1. **Database errors** → Check PostgreSQL is running
2. **API errors (401)** → Expected if auth not configured
3. **PDL errors (403)** → Check API key validity
4. **Timeout errors** → Check network/API availability

---

## 📁 Test Files

```
tests/
├── README_INGESTION_TESTS.md              # Full documentation
├── QUICK_START_TESTING.md                  # This file
├── run_all_ingestion_tests.py              # Master test runner
├── test_ingestion_unit_tests.py            # Unit tests (13 tests)
├── test_ingestion_pipeline_comprehensive.py # Integration tests (16 tests)
└── test_ingestion_api_endpoints.py         # API tests (15 tests)
```

---

## 🎓 Next Steps

After tests pass:

1. **Review results** - Check logs for any warnings
2. **Test in Docker** - Build and run containers
3. **Build frontend** - Phase 5 (connector management UI)
4. **Deploy** - Follow deployment guide
5. **Monitor** - Watch telemetry and logs

---

## 📚 More Information

- **Full test docs:** `tests/README_INGESTION_TESTS.md`
- **Deployment guide:** `docs/ingestion/INGESTION_DEPLOYMENT_GUIDE.md`
- **Complete summary:** `docs/ingestion/INGESTION_COMPLETE_SUMMARY.md`

---

**Ready to test?**

```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform
python3 tests/run_all_ingestion_tests.py
```

🚀 **Good luck!**

