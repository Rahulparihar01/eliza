# Eliza Platform API Documentation

**Version:** 1.0.0  
**Base URL:** `http://localhost:5001` (development) | `https://api.yourdomain.com` (production)  
**API Prefix:** `/api` (for most endpoints)

## Overview

The Eliza Platform is an AI-powered enablement system that provides:
- **Business Intelligence**: AI-driven Q&A over company data
- **Talent Intelligence**: ML-powered talent analysis and candidate matching
- **Document Management**: Vector-based document ingestion and search
- **Data Connectors**: Integration with external data sources (PDL, filesystem, ATS)
- **Authentication & RBAC**: JWT-based auth with fine-grained permissions

## Documentation Structure

1. **[Authentication](./01-authentication.md)** - User authentication, sessions, and permissions
2. **[Business Intelligence](./02-business-intelligence.md)** - AI Q&A system for business data
3. **[Talent Intelligence](./03-talent-intelligence.md)** - ML talent analysis and matching
4. **[Documents](./04-documents.md)** - Document upload, processing, and search
5. **[Connectors](./05-connectors.md)** - Data source connectors and sync management
6. **[Search](./06-search.md)** - Person and skill search across data stores
7. **[Health & Monitoring](./07-health.md)** - Health checks and system status

## Quick Start

### Authentication

All API requests (except `/health` and `/auth/login`) require a JWT access token:

```bash
# Login
curl -X POST http://localhost:5001/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your_password"
  }'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {...}
}
```

### Using the Access Token

Include the token in the `Authorization` header:

```bash
curl -X GET http://localhost:5001/api/v1/bi/questions \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

## API Response Format

### Success Response

```json
{
  "data": {...},
  "status": "success"
}
```

### Error Response

```json
{
  "detail": "Error message",
  "status_code": 400
}
```

### Common HTTP Status Codes

- `200` - OK (successful GET, PUT, PATCH)
- `201` - Created (successful POST)
- `202` - Accepted (async operation started)
- `204` - No Content (successful DELETE)
- `400` - Bad Request (validation error)
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (resource conflict)
- `422` - Unprocessable Entity (validation error)
- `500` - Internal Server Error
- `503` - Service Unavailable

## Rate Limiting

Currently, there are no rate limits enforced. This may change in production.

## Pagination

List endpoints support pagination:

```bash
GET /api/v1/bi/questions?page=1&page_size=20
```

Response includes pagination metadata:

```json
{
  "questions": [...],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

## Filtering and Sorting

Many endpoints support filtering and sorting:

```bash
# Filter by status
GET /api/v1/bi/questions?status=completed

# Sort by creation date (descending)
GET /api/v1/documents?sort=-created_at

# Date range filtering
GET /api/v1/documents?created_after=2024-01-01T00:00:00Z&created_before=2024-12-31T23:59:59Z
```

## Real-Time Updates (Server-Sent Events)

Several endpoints support SSE for real-time progress tracking:

```javascript
// JavaScript example
const token = "your_jwt_token";
const eventSource = new EventSource(
  `http://localhost:5001/api/v1/bi/questions/${question_id}/telemetry?token=${token}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Progress update:', data);
};

eventSource.onerror = (error) => {
  console.error('SSE error:', error);
  eventSource.close();
};
```

## Multi-Tenancy

The API is multi-tenant. Each request is scoped to the authenticated user's `customer_id`. Users can only access data belonging to their organization.

Some resources (like documents) can be further scoped by `company_hr_dataset` to segregate data by company within a customer organization.

## Permissions

The system uses a Role-Based Access Control (RBAC) model with fine-grained permissions:

### Permission Format

Permissions follow the format: `resource:action`

Examples:
- `bi:read` - Read business intelligence data
- `bi:write` - Create business intelligence questions
- `talent:read` - View talent analysis results
- `talent:write` - Create talent analyses
- `documents:read` - View documents
- `documents:write` - Upload documents
- `system:admin` - System administration access

### Checking Permissions

```bash
POST /auth/check-permissions
{
  "permissions": ["bi:write", "documents:read"],
  "require_all": true
}
```

## Error Handling Best Practices

1. **Always check status codes** - Don't rely solely on HTTP 200
2. **Handle async operations** - Use 202 responses with status polling or SSE
3. **Implement retries** - For 5xx errors, implement exponential backoff
4. **Validate inputs** - Check 400/422 responses for validation errors
5. **Handle auth expiry** - Refresh tokens when you receive 401 errors

## Development Tools

### OpenAPI/Swagger

Interactive API documentation is available at:
- http://localhost:5001/docs (Swagger UI)
- http://localhost:5001/redoc (ReDoc)

### Postman Collection

A Postman collection is available at: `docs/api/postman/eliza-platform.json`

## Support

For questions or issues:
- **Documentation**: https://docs.eliza-platform.com
- **GitHub Issues**: https://github.com/your-org/eliza-platform/issues
- **Email**: support@eliza-platform.com

## Changelog

See [CHANGELOG.md](../../CHANGELOG.md) for version history and breaking changes.


