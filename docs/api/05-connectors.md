# Connectors API

**Base Path:** `/api/connectors`

**Required Permission:** `system:admin` (all endpoints are admin-only)

## Overview

The Connectors API manages data source integrations. It provides:
- **Configuration**: Create and manage connector configurations
- **Sync Management**: Trigger and monitor data synchronization
- **Data Access**: Query ingested data from connectors
- **Telemetry**: Real-time sync progress tracking
- **Validation**: Test connections and validate configurations

## Supported Connector Types

| Type | Description | Status | Category |
|------|-------------|--------|----------|
| `people_data_labs` | People Data Labs API | ✅ Available | people_data |
| `filesystem` | Local filesystem | ✅ Available | hr_data |
| `greenhouse` | Greenhouse ATS | 🚧 Coming Soon | hr_data |
| `lever` | Lever ATS | 🚧 Coming Soon | hr_data |
| `workday` | Workday HRIS | 🚧 Coming Soon | hr_data |
| `bamboohr` | BambooHR | 🚧 Coming Soon | hr_data |

---

## Connector Types

### GET /api/connectors/types

Get all available connector types with metadata.

**Response:** `200 OK`
```json
{
  "connector_types": [
    {
      "type": "people_data_labs",
      "name": "People Data Labs",
      "description": "Ingest person and company data directly from PDL API.",
      "category": "people_data",
      "requires_credentials": true,
      "supported_sync_modes": ["full_refresh", "incremental"],
      "available": true
    },
    {
      "type": "filesystem",
      "name": "Local Filesystem",
      "description": "Read files from a local directory for testing and development.",
      "category": "hr_data",
      "requires_credentials": false,
      "supported_sync_modes": ["full_refresh"],
      "available": true
    },
    ...
  ]
}
```

**Sync Modes:**
- `full_refresh` - Sync all data from scratch
- `incremental` - Only sync new/changed data

---

## Configuration Management

### POST /api/connectors/configurations

Create a new connector configuration.

**Request:**
```json
{
  "connector_type": "people_data_labs",
  "connector_name": "PDL Production Connector",
  "credentials": {
    "api_key": "your_pdl_api_key_here"
  },
  "sync_config": {
    "job_title_role": ["software"],
    "location_country": ["united states"],
    "skills": ["python", "javascript"],
    "size": 100
  },
  "description": "Main PDL connector for ML engineer search",
  "tags": ["production", "ml_engineers"],
  "use_shared_credentials": false,
  "sync_schedule": "0 2 * * *"
}
```

**Parameters:**
- `connector_type` (enum, required) - Type of connector
- `connector_name` (string, required) - Human-readable name
- `credentials` (object, required if `requires_credentials=true`) - Authentication credentials
- `sync_config` (object, required) - Connector-specific configuration
- `description` (string, optional) - Connector description
- `tags` (array, optional) - Tags for organization
- `use_shared_credentials` (boolean, default: false) - Use shared credential pool
- `sync_schedule` (string, optional) - Cron expression for scheduled syncs

**Sync Config by Connector Type:**

**People Data Labs:**
```json
{
  "job_title": "Machine Learning Engineer",
  "job_title_role": ["software"],
  "skills": ["python", "tensorflow"],
  "location_country": ["united states"],
  "experience_years_min": 5,
  "size": 100
}
```

**Filesystem:**
```json
{
  "directory_path": "/data/resumes",
  "file_extensions": [".pdf", ".docx"],
  "recursive": true
}
```

**Response:** `201 Created`
```json
{
  "connector_id": "conn_abc123def456",
  "customer_id": "eliza",
  "connector_type": "people_data_labs",
  "connector_name": "PDL Production Connector",
  "description": "Main PDL connector for ML engineer search",
  "sync_config": {...},
  "is_enabled": true,
  "tags": ["production", "ml_engineers"],
  "last_sync_at": null,
  "last_sync_status": null,
  "created_by_user_id": 1,
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z"
}
```

**Notes:**
- Credentials are encrypted before storage
- Connection is tested before saving
- Cost estimation is performed for PDL connectors

**Errors:**
- `400` - Invalid configuration or connection test failed
- `403` - Insufficient permissions

---

### GET /api/connectors/configurations

List all connector configurations.

**Query Parameters:**
- `connector_type` (string, optional) - Filter by type
- `is_enabled` (boolean, optional) - Filter by enabled status

**Response:** `200 OK`
```json
{
  "total": 5,
  "connectors": [
    {
      "connector_id": "conn_abc123",
      "connector_name": "PDL Production",
      "connector_type": "people_data_labs",
      "is_enabled": true,
      "last_sync_at": "2024-01-15T02:00:00Z",
      "last_sync_status": "completed",
      "created_at": "2024-01-10T10:00:00Z"
    },
    ...
  ]
}
```

---

### GET /api/connectors/configurations/{connector_id}

Get a specific connector configuration.

**Response:** `200 OK`
```json
{
  "connector_id": "conn_abc123",
  "customer_id": "eliza",
  "connector_type": "people_data_labs",
  "connector_name": "PDL Production Connector",
  "description": "Main PDL connector",
  "sync_config": {
    "job_title_role": ["software"],
    "skills": ["python"],
    "size": 100
  },
  "is_enabled": true,
  "tags": ["production"],
  "sync_schedule": "0 2 * * *",
  "last_sync_at": "2024-01-15T02:00:00Z",
  "last_sync_status": "completed",
  "created_by_user_id": 1,
  "created_at": "2024-01-10T10:00:00Z",
  "updated_at": "2024-01-15T02:00:00Z"
}
```

**Note:** Credentials are never returned in API responses

---

### GET /api/connectors/configurations/{connector_id}/preview

Get preview data from a connector.

**Use Cases:**
- Preview files before syncing (filesystem)
- Sample data from API (PDL)
- Verify configuration

**Response for Filesystem:** `200 OK`
```json
{
  "type": "filesystem",
  "directory": "/data/resumes",
  "total_files": 50,
  "files": [
    {
      "name": "resume_001.pdf",
      "size": 524288,
      "modified": 1705315200.0
    },
    ...
  ]
}
```

**Response for PDL:** `200 OK`
```json
{
  "type": "people_data_labs",
  "query": {
    "job_title_role": ["software"],
    "skills": ["python"]
  },
  "sample_count": 5,
  "sample_data": [
    {
      "full_name": "John Smith",
      "job_title": "Software Engineer",
      "job_company_name": "Tech Corp",
      "skills": ["python", "javascript"],
      "location_country": "united states"
    },
    ...
  ]
}
```

---

### PUT /api/connectors/configurations/{connector_id}

Update a connector configuration.

**Request:**
```json
{
  "connector_name": "PDL Updated Name",
  "is_enabled": false,
  "sync_config": {
    "size": 200
  },
  "tags": ["production", "high_priority"]
}
```

**Response:** `200 OK`
```json
{
  "connector_id": "conn_abc123",
  ...updated fields...
}
```

**Notes:**
- Configuration changes are versioned
- Old config saved to history
- Connection tested with new config
- Partial updates supported (only provided fields updated)

---

### DELETE /api/connectors/configurations/{connector_id}

Delete (disable) a connector configuration.

**Response:** `204 No Content`

**Notes:**
- Soft delete (marks as disabled)
- Sync history preserved
- Cannot be permanently deleted (data retention)

---

## Sync Management

### POST /api/connectors/configurations/{connector_id}/trigger-sync

Manually trigger a connector sync.

**Request:**
```json
{
  "manual_trigger": true
}
```

**Response:** `202 Accepted`
```json
{
  "sync_id": "sync_xyz789abc",
  "connector_id": "conn_abc123",
  "status": "pending",
  "start_time": "2024-01-15T10:30:00Z",
  "triggered_by": "manual",
  "estimated_records": 100
}
```

**Sync Process:**
1. `pending` - Queued for execution
2. `running` - Actively syncing data
3. `completed` - Sync finished successfully
4. `failed` - Error occurred

**Errors:**
- `400` - Connector disabled or invalid state
- `404` - Connector not found

---

### GET /api/connectors/sync-runs

List sync runs with filtering and pagination.

**Query Parameters:**
- `connector_id` (string, optional) - Filter by connector
- `status` (string, optional) - Filter by status
- `limit` (integer, default: 50, max: 100)
- `offset` (integer, default: 0)

**Response:** `200 OK`
```json
{
  "total": 150,
  "sync_runs": [
    {
      "sync_id": "sync_xyz789",
      "connector_id": "conn_abc123",
      "status": "completed",
      "start_time": "2024-01-15T02:00:00Z",
      "end_time": "2024-01-15T02:05:30Z",
      "duration_seconds": 330,
      "records_read": 100,
      "records_transformed": 100,
      "records_loaded": 100,
      "records_failed": 0,
      "triggered_by": "schedule",
      "error_message": null
    },
    ...
  ]
}
```

---

### GET /api/connectors/sync-runs/{sync_id}

Get detailed sync run information.

**Response:** `200 OK`
```json
{
  "sync_id": "sync_xyz789",
  "connector_id": "conn_abc123",
  "status": "completed",
  "start_time": "2024-01-15T02:00:00Z",
  "end_time": "2024-01-15T02:05:30Z",
  "duration_seconds": 330,
  "records_read": 100,
  "records_transformed": 100,
  "records_loaded": 100,
  "records_failed": 0,
  "bytes_transferred": 5242880,
  "triggered_by": "schedule",
  "error_message": null,
  "sync_config_snapshot": {...},
  "performance_metrics": {
    "avg_read_rate_per_sec": 0.3,
    "avg_transform_rate_per_sec": 0.3,
    "avg_load_rate_per_sec": 0.3
  }
}
```

---

### GET /api/connectors/sync-runs/{sync_id}/telemetry

Get real-time telemetry events for a sync run.

**Query Parameters:**
- `event_type` (string, optional) - Filter by event type
- `limit` (integer, default: 100, max: 500)

**Response:** `200 OK`
```json
{
  "total": 45,
  "events": [
    {
      "telemetry_id": "telem_001",
      "sync_id": "sync_xyz789",
      "event_type": "sync_started",
      "event_timestamp": "2024-01-15T02:00:00Z",
      "message": "Starting PDL sync",
      "data": {
        "estimated_records": 100
      },
      "severity": "info"
    },
    {
      "telemetry_id": "telem_002",
      "event_type": "batch_processed",
      "event_timestamp": "2024-01-15T02:00:30Z",
      "message": "Processed batch 1 of 10",
      "data": {
        "batch_number": 1,
        "records_in_batch": 10,
        "total_batches": 10
      },
      "severity": "info"
    },
    ...
  ]
}
```

**Event Types:**
- `sync_started` - Sync began
- `connection_established` - Connected to source
- `batch_processed` - Data batch completed
- `transform_completed` - Data transformation done
- `load_completed` - Data loaded to destination
- `sync_completed` - Sync finished
- `sync_failed` - Error occurred
- `rate_limit_hit` - API rate limit reached

---

## Data Access

### GET /api/connectors/pdl-persons

List People Data Labs person records.

**Query Parameters:**
- `search` (string, optional) - Search by name, email, company
- `job_title_role` (string, optional) - Filter by role
- `job_company_name` (string, optional) - Filter by company
- `location_country` (string, optional) - Filter by country
- `page` (integer, default: 1)
- `page_size` (integer, default: 50, max: 1000)

**Response:** `200 OK`
```json
{
  "total": 500,
  "persons": [
    {
      "id": 1,
      "pdl_id": "qEnOZ5Oh0poWnQ1luFBfVw_0000",
      "full_name": "Jane Doe",
      "first_name": "Jane",
      "last_name": "Doe",
      "primary_email": "jane.doe@techcorp.com",
      "job_title": "Senior Software Engineer",
      "job_title_role": "software engineer",
      "job_company_name": "Tech Corp",
      "job_company_website": "techcorp.com",
      "location_country": "united states",
      "location_locality": "San Francisco",
      "location_region": "California",
      "skills": ["python", "javascript", "react", "aws"],
      "experience_years": 8,
      "education_level": "bachelor",
      "linkedin_url": "https://linkedin.com/in/janedoe",
      "github_url": "https://github.com/janedoe",
      "raw_data": {...},
      "created_at": "2024-01-15T02:05:00Z",
      "updated_at": "2024-01-15T02:05:00Z"
    },
    ...
  ],
  "page": 1,
  "page_size": 50
}
```

---

### GET /api/connectors/pdl-persons/{person_id}

Get a single PDL person record by ID.

**Response:** `200 OK`
```json
{
  "id": 1,
  "pdl_id": "qEnOZ5Oh0poWnQ1luFBfVw_0000",
  "full_name": "Jane Doe",
  ...complete person data...
}
```

---

### POST /api/connectors/persons/search

Search persons with advanced filters.

**Request:**
```json
{
  "query": "machine learning engineer",
  "filters": {
    "skills": ["python", "tensorflow"],
    "location_country": "united states",
    "experience_years_min": 5
  },
  "page": 1,
  "page_size": 20,
  "use_elasticsearch": true
}
```

**Response:** `200 OK`
```json
{
  "total": 150,
  "results": [...],
  "page": 1,
  "page_size": 20,
  "took_ms": 85,
  "fallback": false
}
```

**Notes:**
- Uses Elasticsearch if available, falls back to PostgreSQL
- Supports full-text search and faceted filtering
- Fast performance for large datasets

---

### POST /api/connectors/persons/career-transitions

Find people who moved between companies.

**Request:**
```json
{
  "from_company": "Google",
  "to_company": "Meta",
  "limit": 50
}
```

**Response:** `200 OK`
```json
{
  "from_company": "Google",
  "to_company": "Meta",
  "transitions": [
    {
      "pdl_id": "...",
      "full_name": "John Smith",
      "previous_job_title": "Software Engineer",
      "current_job_title": "Senior Software Engineer",
      "transition_date": "2023-06-01",
      "skills": ["python", "distributed systems"]
    },
    ...
  ],
  "total": 15
}
```

**Use Cases:**
- Talent pipeline analysis
- Company network mapping
- Recruitment targeting

---

### POST /api/connectors/persons/by-skills

Find people with specific skill combinations.

**Request:**
```json
{
  "skills": ["python", "machine learning", "aws"],
  "require_all": false,
  "limit": 100
}
```

**Response:** `200 OK`
```json
{
  "results": [
    {
      "pdl_id": "...",
      "full_name": "Jane Doe",
      "matched_skills": ["python", "machine learning", "aws"],
      "match_count": 3,
      "total_skills": 15
    },
    ...
  ],
  "total": 85
}
```

---

### POST /api/connectors/persons/company-network

Get network of companies connected through people.

**Request:**
```json
{
  "company_name": "Google",
  "depth": 2
}
```

**Response:** `200 OK`
```json
{
  "source_company": "Google",
  "connected_companies": [
    {
      "company_name": "Meta",
      "connection_count": 45,
      "connection_type": "employee_transition"
    },
    {
      "company_name": "Apple",
      "connection_count": 32,
      "connection_type": "employee_transition"
    },
    ...
  ],
  "total": 150
}
```

---

## Statistics

### GET /api/connectors/configurations/{connector_id}/statistics

Get aggregate statistics for a connector.

**Response:** `200 OK`
```json
{
  "connector_id": "conn_abc123",
  "connector_name": "PDL Production",
  "connector_type": "people_data_labs",
  "total_syncs": 50,
  "successful_syncs": 48,
  "failed_syncs": 2,
  "total_records_synced": 5000,
  "total_records_transformed": 5000,
  "total_records_failed": 0,
  "last_sync_at": "2024-01-15T02:00:00Z",
  "last_sync_status": "completed",
  "average_sync_duration_seconds": 330.5,
  "average_records_per_sync": 100.0
}
```

---

## Validation & Testing

### POST /api/connectors/validate-config

Validate a connector configuration without saving.

**Request:**
```json
{
  "connector_type": "people_data_labs",
  "sync_config": {
    "job_title_role": ["software"],
    "skills": ["python"]
  }
}
```

**Response:** `200 OK`
```json
{
  "is_valid": true,
  "error_message": null
}
```

Or if invalid:
```json
{
  "is_valid": false,
  "error_message": "Invalid field 'job_title_role'. Valid values: software, sales, marketing..."
}
```

---

### POST /api/connectors/test-connection

Test connection with provided credentials.

**Request:**
```json
{
  "connector_type": "people_data_labs",
  "credentials": {
    "api_key": "test_key"
  },
  "sync_config": {
    "job_title_role": ["software"]
  }
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "status": "healthy",
  "message": "Connection successful. API key valid.",
  "metadata": {
    "api_version": "v5",
    "rate_limit_remaining": 9500
  }
}
```

Or if failed:
```json
{
  "success": false,
  "status": "unhealthy",
  "message": "Connection test failed: Invalid API key"
}
```

---

### POST /api/connectors/estimate-cost

Estimate cost for a connector sync.

**Request:**
```json
{
  "connector_type": "people_data_labs",
  "credentials": {
    "api_key": "your_key"
  },
  "sync_config": {
    "job_title_role": ["software"],
    "location_country": ["united states"]
  }
}
```

**Response:** `200 OK`
```json
{
  "estimated_record_count": 10000,
  "estimated_cost": 100.00,
  "cost_per_record": 0.01,
  "requires_acknowledgment": true,
  "warning_message": "This sync will fetch approximately 10,000 records (estimated cost: $100.00). Please acknowledge by setting 'estimated_cost_acknowledged': true in config."
}
```

**Cost Thresholds:**
- **< $10**: No acknowledgment required
- **$10 - $100**: Warning shown
- **> $100**: Explicit acknowledgment required in config

---

## Connector-Specific Documentation

### People Data Labs Connector

**Authentication:**
```json
{
  "credentials": {
    "api_key": "your_pdl_api_key"
  }
}
```

**Configuration:**
```json
{
  "sync_config": {
    // Exact title match
    "job_title": "Machine Learning Engineer",
    
    // Standardized role categories
    "job_title_role": ["software", "data_science"],
    
    // Skills (exact match, lowercase)
    "skills": ["python", "tensorflow", "aws"],
    
    // Location
    "location_country": ["united states"],
    "location_region": ["california"],
    "location_locality": ["san francisco"],
    
    // Experience
    "experience_years_min": 5,
    "experience_years_max": 10,
    
    // Education
    "education_level": ["bachelor", "master", "phd"],
    
    // Company filters
    "job_company_name": ["google", "meta"],
    "job_company_size": ["1001-5000", "5001+"],
    
    // Result limit (controls cost)
    "size": 100
  }
}
```

**Field Guidelines:**
- Use `job_title` for exact matches ("Machine Learning Engineer")
- Use `job_title_role` for categories ("software", "engineering")
- All skills must be lowercase
- `size` parameter controls API credit usage (1 credit per record)

**Rate Limits:**
- 100 requests/minute
- 10,000 credits/month (default tier)

---

### Filesystem Connector

**Configuration:**
```json
{
  "sync_config": {
    "directory_path": "/data/resumes",
    "file_extensions": [".pdf", ".docx", ".txt"],
    "recursive": true,
    "ignore_patterns": ["**/archive/**", "**/.DS_Store"]
  }
}
```

**Notes:**
- No credentials required
- Directory must be accessible by application
- Supports recursive directory scanning
- Can filter by file extensions
- Use glob patterns for exclusions

---

## Best Practices

### Configuration

1. **Use descriptive names**: "PDL ML Engineers - US West" > "Connector 1"
2. **Tag appropriately**: Use tags for filtering and organization
3. **Test before saving**: Use validation and connection test endpoints
4. **Estimate costs**: Always check cost before large PDL queries
5. **Version control**: Document configuration changes

### Scheduling

1. **Off-peak hours**: Schedule syncs during low-traffic periods (2-4 AM)
2. **Reasonable frequency**: Don't sync more than necessary
   - PDL: Once daily or less
   - Filesystem: On-demand or when files change
3. **Avoid conflicts**: Stagger multiple connector schedules

### Cost Management

1. **Start small**: Test with `size=1-10` before scaling
2. **Use filters**: Narrow results to reduce cost
3. **Monitor usage**: Check statistics regularly
4. **Set budgets**: Configure cost acknowledgment thresholds
5. **Incremental syncs**: Use when supported to avoid re-fetching

### Error Handling

1. **Monitor telemetry**: Watch for patterns in failures
2. **Retry strategy**: Implement exponential backoff for transient errors
3. **Alert on failures**: Set up monitoring for failed syncs
4. **Check logs**: Review Celery worker logs for detailed errors

## Troubleshooting

### Sync Stuck in "Pending"

**Cause:** Celery worker not running

**Solution:** Check worker status: `docker-compose ps celery-worker`

### PDL Queries Return No Results

**Causes:**
1. Filters too restrictive
2. Invalid field values
3. No matching data

**Solutions:**
1. Broaden filters (remove some constraints)
2. Validate config: `POST /api/connectors/validate-config`
3. Test with preview: `GET /api/connectors/configurations/{id}/preview`

### "Rate Limit Exceeded"

**Cause:** Hit PDL API rate limit

**Solution:**
1. Slow down sync rate
2. Upgrade PDL plan
3. Schedule syncs more sparsely

### Filesystem Connector Finds No Files

**Causes:**
1. Incorrect directory path
2. No matching file extensions
3. Permission issues

**Solutions:**
1. Verify path exists and is accessible
2. Check file extensions in configuration
3. Ensure application has read permissions


