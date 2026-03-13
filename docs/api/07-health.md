# Health & Monitoring API

**Base Path:** `/health`, `/api/v1/bi/health`, `/api/v1/documents/health`, `/auth/health`

**Authentication:** Not required for basic health checks

## Overview

Health check endpoints provide system status information for:
- Service availability monitoring
- Deployment validation
- Dependency health checks
- Performance metrics
- Component status

## Endpoints

### GET /health

Basic application health check.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "timestamp": 1705315200.0,
  "version": "1.0.0",
  "customer_id": "eliza",
  "environment": "production",
  "uptime_seconds": 86400.5
}
```

**Status Values:**
- `healthy` - All systems operational
- `degraded` - Some components have issues
- `unhealthy` - Critical components down

**Use Cases:**
- Load balancer health checks
- Deployment smoke tests
- Uptime monitoring
- Quick status verification

---

### GET /health/ready

Readiness check for Kubernetes/container orchestration.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "ready",
  "timestamp": 1705315200.0,
  "version": "1.0.0",
  "customer_id": "eliza",
  "environment": "production",
  "uptime_seconds": 86400.5
}
```

**Response `503 Service Unavailable` if not ready:**
```json
{
  "status": "not_ready",
  "detail": "Service not ready: Database initialization failed"
}
```

**Checks Performed:**
- Database connectivity
- Customer configuration loaded
- Critical services initialized

**Use Cases:**
- Kubernetes readiness probes
- Wait for startup completion
- Deployment gate checks

---

### GET /health/detailed

Comprehensive health check with component details.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "timestamp": 1705315200.0,
  "version": "1.0.0",
  "customer_id": "eliza",
  "environment": "production",
  "uptime_seconds": 86400.5,
  "services": {
    "customer_configuration": {
      "status": "healthy",
      "message": "Customer configuration loaded successfully",
      "details": {
        "customer_name": "Eliza Platform",
        "data_sources_count": 5,
        "enabled_data_sources": 3,
        "default_provider": "anthropic",
        "config_file_exists": true
      }
    },
    "ai_providers": {
      "status": "healthy",
      "message": "2 AI provider(s) configured",
      "details": {
        "providers": {
          "openai": {
            "configured": true,
            "api_key_present": true,
            "status": "unknown"
          },
          "anthropic": {
            "configured": true,
            "api_key_present": true,
            "status": "unknown"
          },
          "groq": {
            "configured": false,
            "api_key_present": false,
            "status": "not_configured"
          }
        },
        "configured_count": 2
      }
    },
    "database": {
      "status": "healthy",
      "message": "Database connection established",
      "details": {
        "connection_pool_size": 10,
        "active_connections": 3,
        "idle_connections": 7
      }
    }
  },
  "configuration": {
    "environment": "production",
    "debug": false,
    "log_level": "INFO",
    "customer_id": "eliza",
    "database_configured": true,
    "redis_configured": true,
    "neo4j_configured": true,
    "ai_providers": {
      "openai": true,
      "anthropic": true,
      "groq": false,
      "together": false
    }
  }
}
```

**Service Status Details:**

Each service includes:
- `status`: "healthy", "degraded", or "unhealthy"
- `message`: Human-readable status description
- `details`: Service-specific metrics and information

**Use Cases:**
- Detailed system monitoring
- Debugging deployment issues
- Configuration validation
- Capacity planning

---

### GET /auth/health

Authentication service health check.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "service": "authentication",
  "timestamp": "2024-01-15T12:00:00Z",
  "features": {
    "jwt_auth": true,
    "session_management": true,
    "rbac": true,
    "audit_logging": true,
    "concurrent_session_limits": true,
    "device_fingerprinting": true
  }
}
```

**Features Explained:**
- `jwt_auth`: JWT token generation and validation
- `session_management`: User session tracking
- `rbac`: Role-Based Access Control
- `audit_logging`: Security audit logs
- `concurrent_session_limits`: Multi-device session management
- `device_fingerprinting`: Device identification for security

---

### GET /api/v1/bi/health

Business Intelligence system health check.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "redis": "healthy",
    "celery_workers": "healthy",
    "vector_service": "healthy",
    "crewai": "healthy"
  },
  "details": {
    "redis": {
      "latency_ms": 2.5,
      "queue_depth": 3
    },
    "celery_workers": {
      "workers": ["celery@worker1", "celery@worker2"]
    }
  },
  "timestamp": "2024-01-15T12:00:00Z"
}
```

**Component Checks:**

**Database:**
- Connection pool status
- Query response time
- Active connections

**Redis:**
- Connectivity
- Latency
- Queue depth (pending tasks)

**Celery Workers:**
- Worker count
- Worker names
- Queue status

**Vector Service:**
- Index health
- Search performance
- Storage status

**CrewAI:**
- Library import check
- Agent framework status

**Status Interpretation:**
- `healthy`: All components operational
- `degraded`: Some components have issues but system functional
- `unhealthy`: Critical components down, system unavailable

---

### GET /api/v1/documents/health

Document processing service health check.

**No authentication required**

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "document_processor": {
    "status": "healthy"
  },
  "vector_service": {
    "status": "healthy",
    "stats": {
      "total_vectors": 8432,
      "index_size_mb": 102.5,
      "vector_dimension": 1536,
      "last_updated": "2024-01-15T10:00:00Z"
    }
  },
  "vector_index_stats": {
    "total_vectors": 8432,
    "index_size_mb": 102.5,
    "vector_dimension": 1536,
    "index_type": "FAISS_HNSW",
    "last_updated": "2024-01-15T10:00:00Z",
    "search_performance_ms": {
      "avg": 85,
      "p50": 75,
      "p95": 150,
      "p99": 200
    }
  }
}
```

**Vector Index Metrics:**
- `total_vectors`: Number of indexed embeddings
- `index_size_mb`: Memory/disk usage
- `vector_dimension`: Embedding size (1536 for OpenAI)
- `index_type`: FAISS index configuration
- `search_performance_ms`: Query latency percentiles

**Performance Baselines:**
- **Good**: p50 < 100ms, p95 < 200ms
- **Acceptable**: p50 < 200ms, p95 < 500ms
- **Slow**: p50 > 200ms or p95 > 500ms

---

## Health Check Patterns

### Kubernetes Probes

**Liveness Probe** (is the service running?):
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 5001
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

**Readiness Probe** (can it serve traffic?):
```yaml
readinessProbe:
  httpGet:
    path: /health/ready
    port: 5001
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
```

**Startup Probe** (has initialization completed?):
```yaml
startupProbe:
  httpGet:
    path: /health/ready
    port: 5001
  initialDelaySeconds: 0
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 30
```

---

### Load Balancer Health Checks

**AWS ALB/ELB:**
```
Health Check Path: /health
Healthy Threshold: 2
Unhealthy Threshold: 3
Timeout: 5 seconds
Interval: 30 seconds
Success Codes: 200
```

**NGINX:**
```nginx
upstream api_backend {
    server api1:5001 max_fails=3 fail_timeout=30s;
    server api2:5001 max_fails=3 fail_timeout=30s;
    
    check interval=10000 rise=2 fall=3 timeout=5000 type=http;
    check_http_send "GET /health HTTP/1.0\r\n\r\n";
    check_http_expect_alive http_2xx;
}
```

---

### Monitoring Tools

**Prometheus (Metrics Scraping):**
```yaml
scrape_configs:
  - job_name: 'eliza-api'
    scrape_interval: 30s
    metrics_path: /metrics
    static_configs:
      - targets: ['api:5001']
```

**Datadog (Synthetic Monitoring):**
```javascript
{
  "name": "Eliza API Health Check",
  "type": "api",
  "request": {
    "method": "GET",
    "url": "https://api.eliza.com/health/detailed"
  },
  "assertions": [
    {"type": "statusCode", "operator": "is", "target": 200},
    {"type": "body", "operator": "contains", "target": "healthy"},
    {"type": "responseTime", "operator": "lessThan", "target": 2000}
  ],
  "locations": ["aws:us-west-2", "aws:eu-west-1"],
  "options": {
    "tick_every": 60,
    "min_failure_duration": 120,
    "min_location_failed": 1
  }
}
```

**New Relic (Availability Monitoring):**
```javascript
const assert = require('assert');
const $http = require('http');

$http.get('https://api.eliza.com/health/detailed', (res) => {
  assert.equal(res.statusCode, 200, 'Expected 200 OK response');
  
  let body = '';
  res.on('data', chunk => body += chunk);
  res.on('end', () => {
    const health = JSON.parse(body);
    assert.equal(health.status, 'healthy', 'System should be healthy');
    assert.ok(health.services.database.status === 'healthy', 'Database should be healthy');
    assert.ok(health.services.redis.status === 'healthy', 'Redis should be healthy');
  });
});
```

---

## Monitoring Best Practices

### 1. Monitor Multiple Endpoints

Don't rely on a single health check:
- `/health` - Basic availability
- `/health/ready` - Application readiness
- `/api/v1/bi/health` - BI system health
- `/api/v1/documents/health` - Document system health
- `/auth/health` - Authentication system health

### 2. Set Appropriate Thresholds

**Liveness:**
- Should only fail if the process is unrecoverable
- Set higher failure threshold (3-5 failures)
- Longer timeout (5-10 seconds)

**Readiness:**
- Should fail if the service can't handle requests
- Lower failure threshold (2-3 failures)
- Shorter timeout (2-5 seconds)

### 3. Use Progressive Health Checks

```
Level 1: /health (basic)
  ↓ If healthy
Level 2: /health/ready (dependencies)
  ↓ If ready
Level 3: /health/detailed (comprehensive)
```

### 4. Implement Graceful Degradation

Don't fail health checks if:
- Non-critical features are down
- System can operate in degraded mode
- Fallback mechanisms are available

**Example:** Return `healthy` if Elasticsearch is down but PostgreSQL fallback works.

### 5. Monitor Metrics Over Time

Track trends, not just current status:
- Response time percentiles
- Error rates
- Queue depths
- Resource utilization

---

## Health Check Response Times

Expected response times for health endpoints:

| Endpoint | Expected | Acceptable | Slow |
|----------|----------|------------|------|
| `/health` | < 50ms | < 100ms | > 200ms |
| `/health/ready` | < 200ms | < 500ms | > 1s |
| `/health/detailed` | < 500ms | < 1s | > 2s |
| Service-specific | < 100ms | < 300ms | > 500ms |

---

## Alerting Rules

### Critical Alerts (Page Immediately)

**API Unavailable:**
```
Alert: API down
Condition: /health returns non-200 for > 2 minutes
Action: Page on-call engineer
```

**Database Connection Lost:**
```
Alert: Database unreachable
Condition: database.status = "unhealthy" for > 1 minute
Action: Page database team
```

**All Workers Down:**
```
Alert: No Celery workers
Condition: celery_workers.count = 0 for > 5 minutes
Action: Page DevOps team
```

### Warning Alerts (Notify but Don't Page)

**Degraded Performance:**
```
Alert: Slow API responses
Condition: p95 response time > 1s for > 10 minutes
Action: Slack notification
```

**High Queue Depth:**
```
Alert: Task backlog
Condition: redis.queue_depth > 100 for > 15 minutes
Action: Slack notification
```

**Component Unhealthy:**
```
Alert: Service degraded
Condition: Any component status = "unhealthy" for > 5 minutes
Action: Slack notification + ticket
```

---

## Troubleshooting

### Health Check Returns 503

**Possible Causes:**
1. Service still starting up
2. Database connection failed
3. Critical dependency unavailable
4. Configuration error

**Debug Steps:**
1. Check `/health/detailed` for specific component failures
2. Review application logs
3. Verify database connectivity
4. Check environment variables

---

### Intermittent Health Check Failures

**Possible Causes:**
1. Network instability
2. Resource exhaustion (CPU/memory)
3. Database connection pool exhausted
4. Timeouts too aggressive

**Solutions:**
1. Increase health check timeout
2. Scale up resources
3. Increase connection pool size
4. Adjust failure thresholds

---

### "Healthy" but Service Not Working

**Possible Causes:**
1. Health check too basic
2. Checking wrong endpoints
3. Caching issues
4. Not checking actual functionality

**Solutions:**
1. Implement deeper health checks
2. Add functional tests to health checks
3. Monitor actual request success rates
4. Use synthetic transactions

---

### Slow Health Check Responses

**Possible Causes:**
1. Checking too many dependencies
2. Performing expensive operations
3. Database queries in health check
4. External API calls

**Solutions:**
1. Cache health check results (5-10 seconds)
2. Check dependencies asynchronously
3. Use connection pool health, not test queries
4. Avoid external calls in health checks

---

## Security Considerations

### 1. Limit Information Exposure

**Public Health Checks:**
- Return minimal information
- Don't expose versions, internal IPs, or detailed errors
- Use generic status messages

**Authenticated Detailed Checks:**
- Detailed diagnostics for authenticated users only
- Log access to detailed health endpoints
- Rate limit to prevent information gathering

### 2. Prevent Health Check Abuse

```python
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/health/detailed")
@limiter.limit("10/minute")
async def detailed_health(request: Request):
    ...
```

### 3. Use Separate Monitoring Credentials

Don't use production API keys for health checks. Create dedicated monitoring accounts with limited permissions.

---

## Health Check Development Guidelines

### DO:
✅ Keep health checks fast (< 100ms for basic)
✅ Return consistent JSON format
✅ Include timestamp and version
✅ Check actual connectivity, not configuration
✅ Implement caching for expensive checks
✅ Use appropriate status codes (200, 503)

### DON'T:
❌ Make external API calls in health checks
❌ Expose sensitive configuration details
❌ Perform expensive computations
❌ Return 500 errors (use 503 for unavailable)
❌ Depend on other services' health checks
❌ Include authentication in basic health checks

---

## Example: Custom Health Check

```python
from fastapi import APIRouter, Response
from datetime import datetime
import asyncio

router = APIRouter()

# Cache health check results
_health_cache = {
    'status': 'unknown',
    'last_check': None,
    'details': {}
}
_cache_ttl = 10  # seconds

@router.get("/health/custom")
async def custom_health_check():
    """Custom health check with caching."""
    
    # Return cached result if fresh
    if (_health_cache['last_check'] and 
        (datetime.utcnow() - _health_cache['last_check']).seconds < _cache_ttl):
        return _health_cache
    
    # Perform checks
    checks = await asyncio.gather(
        check_database(),
        check_redis(),
        check_api_gateway(),
        return_exceptions=True
    )
    
    # Aggregate results
    all_healthy = all(check['status'] == 'healthy' for check in checks if isinstance(check, dict))
    
    result = {
        'status': 'healthy' if all_healthy else 'degraded',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': {
            'database': checks[0] if not isinstance(checks[0], Exception) else {'status': 'unhealthy'},
            'redis': checks[1] if not isinstance(checks[1], Exception) else {'status': 'unhealthy'},
            'api_gateway': checks[2] if not isinstance(checks[2], Exception) else {'status': 'unhealthy'}
        }
    }
    
    # Update cache
    _health_cache.update(result)
    _health_cache['last_check'] = datetime.utcnow()
    
    return result

async def check_database():
    """Check database connectivity."""
    try:
        # Quick connectivity check, not a full query
        await db.execute("SELECT 1")
        return {'status': 'healthy', 'latency_ms': 5}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}

async def check_redis():
    """Check Redis connectivity."""
    try:
        await redis.ping()
        return {'status': 'healthy', 'latency_ms': 2}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}

async def check_api_gateway():
    """Check internal API gateway."""
    try:
        # Use HEAD request for efficiency
        response = await http_client.head(gateway_url, timeout=2)
        return {'status': 'healthy' if response.status == 200 else 'degraded'}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}
```

This comprehensive health check system ensures robust monitoring and quick issue detection across all Eliza Platform services.


