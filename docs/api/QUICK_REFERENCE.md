# API Quick Reference

Quick reference guide for common API operations.

## Authentication

```bash
# Login
curl -X POST http://localhost:5001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Get current user
curl http://localhost:5001/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Refresh token
curl -X POST http://localhost:5001/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "$REFRESH_TOKEN"}'
```

## Business Intelligence

```bash
# Submit question
curl -X POST http://localhost:5001/api/v1/bi/questions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the top skills?", "company_hr_dataset": "caylent"}'

# Get question status
curl http://localhost:5001/api/v1/bi/questions/$QUESTION_ID/status \
  -H "Authorization: Bearer $TOKEN"

# Get results
curl http://localhost:5001/api/v1/bi/questions/$QUESTION_ID/result \
  -H "Authorization: Bearer $TOKEN"

# List questions
curl "http://localhost:5001/api/v1/bi/questions?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

## Talent Intelligence

```bash
# Start analysis from connector
curl -X POST http://localhost:5001/api/v1/ml-talent/analyze-from-connector \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "ML Engineer role...",
    "ideal_candidate_description": "5+ years...",
    "data_source_connector_id": "conn_fs_resumes",
    "role": "Machine Learning Engineer"
  }'

# Get analysis status
curl http://localhost:5001/api/v1/ml-talent/analysis/$ANALYSIS_ID/status \
  -H "Authorization: Bearer $TOKEN"

# Get results
curl http://localhost:5001/api/v1/ml-talent/analysis/$ANALYSIS_ID \
  -H "Authorization: Bearer $TOKEN"

# List analyses
curl "http://localhost:5001/api/v1/ml-talent/analyses?page=1" \
  -H "Authorization: Bearer $TOKEN"
```

## Documents

```bash
# Upload documents
curl -X POST http://localhost:5001/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "files=@document.pdf" \
  -F "company_hr_dataset=caylent" \
  -F "chunking_strategy=semantic"

# List documents
curl "http://localhost:5001/api/v1/documents?limit=20&sort=-created_at" \
  -H "Authorization: Bearer $TOKEN"

# Search documents
curl -X POST http://localhost:5001/api/v1/documents/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "employee benefits", "limit": 10, "similarity_threshold": 0.7}'

# Download document
curl http://localhost:5001/api/v1/documents/$DOC_ID/download \
  -H "Authorization: Bearer $TOKEN" \
  -o document.pdf

# Get document stats
curl "http://localhost:5001/api/v1/documents/stats?range=7d" \
  -H "Authorization: Bearer $TOKEN"
```

## Connectors

```bash
# List connector types
curl http://localhost:5001/api/connectors/types \
  -H "Authorization: Bearer $TOKEN"

# Create connector
curl -X POST http://localhost:5001/api/connectors/configurations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "connector_type": "people_data_labs",
    "connector_name": "PDL Connector",
    "credentials": {"api_key": "your_key"},
    "sync_config": {
      "job_title_role": ["software"],
      "skills": ["python"],
      "size": 100
    }
  }'

# List connectors
curl http://localhost:5001/api/connectors/configurations \
  -H "Authorization: Bearer $TOKEN"

# Trigger sync
curl -X POST http://localhost:5001/api/connectors/configurations/$CONNECTOR_ID/trigger-sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"manual_trigger": true}'

# List PDL persons
curl "http://localhost:5001/api/connectors/pdl-persons?page=1&page_size=50" \
  -H "Authorization: Bearer $TOKEN"
```

## Search

```bash
# Search persons
curl -X POST http://localhost:5001/search/persons \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning engineer", "size": 20}'

# Search by skills
curl -X POST http://localhost:5001/search/persons/by-skills \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"skills": ["python", "tensorflow"], "min_match": 2, "size": 50}'

# Career transitions
curl -X POST http://localhost:5001/search/persons/career-transitions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"from_company": "Google", "to_company": "Meta", "limit": 100}'

# Company network
curl -X POST http://localhost:5001/search/companies/network \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Google", "max_hops": 2, "limit": 50}'

# Skill co-occurrence
curl -X POST http://localhost:5001/search/skills/cooccurrence \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"skill": "python", "top_n": 20}'

# Aggregations
curl -X POST http://localhost:5001/search/aggregate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"field": "job_company_name", "size": 50}'
```

## Health Checks

```bash
# Basic health
curl http://localhost:5001/health

# Readiness
curl http://localhost:5001/health/ready

# Detailed health
curl http://localhost:5001/health/detailed

# BI system health
curl http://localhost:5001/api/v1/bi/health

# Document service health
curl http://localhost:5001/api/v1/documents/health

# Auth service health
curl http://localhost:5001/auth/health
```

## Common Patterns

### Pagination

```bash
# First page
curl "http://localhost:5001/api/endpoint?page=1&page_size=20" \
  -H "Authorization: Bearer $TOKEN"

# Next page
curl "http://localhost:5001/api/endpoint?page=2&page_size=20" \
  -H "Authorization: Bearer $TOKEN"
```

### Filtering

```bash
# Filter by status
curl "http://localhost:5001/api/endpoint?status=completed" \
  -H "Authorization: Bearer $TOKEN"

# Filter by date range
curl "http://localhost:5001/api/endpoint?created_after=2024-01-01T00:00:00Z&created_before=2024-12-31T23:59:59Z" \
  -H "Authorization: Bearer $TOKEN"

# Multiple filters
curl "http://localhost:5001/api/endpoint?status=completed&company_hr_dataset=caylent&limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

### Sorting

```bash
# Sort ascending
curl "http://localhost:5001/api/endpoint?sort=created_at" \
  -H "Authorization: Bearer $TOKEN"

# Sort descending (prefix with -)
curl "http://localhost:5001/api/endpoint?sort=-created_at" \
  -H "Authorization: Bearer $TOKEN"
```

## Environment Variables

Set these for easier testing:

```bash
export API_BASE="http://localhost:5001"
export TOKEN="your_jwt_token_here"

# Then use:
curl "$API_BASE/auth/me" -H "Authorization: Bearer $TOKEN"
```

## HTTP Status Codes

- `200` - Success
- `201` - Created
- `202` - Accepted (async operation started)
- `204` - No Content (successful deletion)
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `409` - Conflict
- `422` - Validation Error
- `500` - Internal Server Error
- `503` - Service Unavailable

## Response Formats

### Success
```json
{
  "data": {...},
  "status": "success"
}
```

### Error
```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### Pagination
```json
{
  "items": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

## Rate Limits

Currently no rate limits enforced. Future implementation may include:
- 100 requests/minute per user
- 1000 requests/hour per customer
- Higher limits for admin users

## Tips

1. **Always include Authorization header** for authenticated endpoints
2. **Check status codes** to determine success/failure
3. **Use pagination** for large result sets
4. **Monitor SSE connections** for real-time updates
5. **Handle token expiry** with refresh token logic
6. **Validate inputs** before sending requests
7. **Cache frequently used data** to reduce API calls
8. **Implement retry logic** for transient failures
9. **Use appropriate Content-Type** headers
10. **Test in development** before production use


