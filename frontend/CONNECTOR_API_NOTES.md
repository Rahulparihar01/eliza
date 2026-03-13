# Connector API - Actual Backend Routes

**Note:** The TypeScript client in `src/generated/connectors/connectors.ts` was **manually created** instead of using orval. This should be regenerated properly.

## Correct Backend Routes

Base prefix: `/api/connectors`

### Configuration Management
- `POST /api/connectors/configurations` - Create connector
- `GET /api/connectors/configurations` - List connectors  
- `GET /api/connectors/configurations/{connector_id}` - Get one connector
- `PUT /api/connectors/configurations/{connector_id}` - Update connector
- `DELETE /api/connectors/configurations/{connector_id}` - Delete connector

### Sync Operations
- `POST /api/connectors/configurations/{connector_id}/trigger-sync` - Trigger sync
- `GET /api/connectors/sync-runs` - List sync runs
- `GET /api/connectors/sync-runs/{sync_id}` - Get sync run details
- `GET /api/connectors/sync-runs/{sync_id}/telemetry` - Get telemetry

### Statistics & Health
- `GET /api/connectors/configurations/{connector_id}/statistics` - Get stats

### Discovery & Validation
- `GET /api/connectors/types` - List available connector types
- `POST /api/connectors/validate-config` - Validate configuration
- `POST /api/connectors/test-connection` - Test connection
- `POST /api/connectors/estimate-cost` - Estimate sync cost

### PDL Person Data
- `GET /api/connectors/pdl-persons` - List PDL persons
- `GET /api/connectors/pdl-persons/{person_id}` - Get PDL person

### Person Search (from search.py, different router)
- `POST /v1/search/persons` - Search persons
- `GET /v1/search/persons/{pdl_id}` - Get person by PDL ID
- `POST /v1/search/persons/career-transitions` - Career transitions
- `POST /v1/search/persons/by-skills` - Search by skills
- `POST /v1/search/persons/company-network` - Company network
- `POST /v1/search/persons/aggregations` - Aggregations

## To Regenerate Properly with Orval

1. Start backend:
   ```bash
   cd /Users/scottgay/Documents/Eliza/eliza-platform
   docker-compose up app
   ```

2. Generate types:
   ```bash
   cd frontend
   npm run generate:api
   ```

3. Orval will create types in `frontend/src/generated/` based on OpenAPI spec

4. Delete manual `connectors.ts` and use orval-generated files instead

## Current Issue

The manually created `frontend/src/generated/connectors/connectors.ts` has:
- ❌ Wrong URL prefix (`/v1/connectors` instead of `/api/connectors`)
- ❌ Wrong endpoint paths (doesn't match backend)
- ❌ Not auto-generated from OpenAPI spec
- ❌ Won't update when backend changes

## Resolution

✅ **FULLY RESOLVED!** (Orval Generation Complete - Oct 10, 2025)

The connector types have been properly generated using orval from the live OpenAPI specification.

### Final Status:
- ✅ Orval generation completed successfully
- ✅ Types generated from http://localhost:5001/openapi.json
- ✅ 11 API functions auto-generated
- ✅ 14 React Query hooks auto-generated
- ✅ Zero linting errors
- ✅ Guaranteed to match backend exactly

### Generation Command Used:
```bash
cd frontend && npm run generate:api
```

### Future Updates:
Whenever backend APIs change, simply re-run:
```bash
# Ensure backend is running
docker-compose -f docker/docker-compose.yml up -d app

# Regenerate types
cd frontend && npm run generate:api
```

### Note:
This issue is now completely resolved. Types are auto-generated and will stay in sync with backend changes through orval.

