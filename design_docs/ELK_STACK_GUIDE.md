# ELK Stack Integration Guide

**Version:** 1.0  
**Date:** October 1, 2025  
**Status:** Production Ready

---

## 🎯 **Overview**

The AI Enablement Platform now includes a fully integrated ELK (Elasticsearch, Logstash, Kibana) stack for centralized logging, monitoring, and analysis.

### **Components:**

- **Elasticsearch** - Distributed search and analytics engine for log storage
- **Logstash** - Log processing pipeline that ingests, transforms, and sends logs to Elasticsearch
- **Kibana** - Visualization platform for exploring and analyzing logs

---

## 🚀 **Quick Start**

### **1. Start the ELK Stack**

```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform

# Start all services (including ELK)
docker-compose -f docker/docker-compose.yml up -d

# Check ELK services status
docker-compose -f docker/docker-compose.yml ps elasticsearch logstash kibana
```

### **2. Wait for Services to Initialize**

ELK services take 1-2 minutes to start up:

```bash
# Watch logs
docker-compose -f docker/docker-compose.yml logs -f elasticsearch logstash kibana

# Wait for:
# - Elasticsearch: "Cluster health status changed from [RED] to [GREEN]"
# - Logstash: "Successfully started Logstash API endpoint"
# - Kibana: "http server running"
```

### **3. Access the Dashboards**

- **Kibana (Log UI)**: http://localhost:5601
- **Elasticsearch (API)**: http://localhost:9200
- **Logstash (Monitoring)**: http://localhost:9600

---

## 📊 **Using Kibana**

### **Initial Setup**

1. **Open Kibana**: http://localhost:5601
2. **Create Index Pattern**:
   - Navigate to: **Management** → **Stack Management** → **Index Patterns**
   - Click **Create index pattern**
   - Pattern: `ai-platform-logs-*`
   - Time field: `@timestamp`
   - Click **Create index pattern**

3. **View Logs**:
   - Navigate to: **Analytics** → **Discover**
   - Select `ai-platform-logs-*` index pattern
   - Logs will appear in real-time

### **Useful Queries**

#### **Find All Logs for a Request**
```
context.request_id: "abc123"
```

#### **Find Errors**
```
level: ERROR OR level: CRITICAL
```

#### **Find Slow Requests**
```
duration_ms >= 1000 AND category: "api"
```

#### **Find Document Processing Logs**
```
category: "data_processing" AND context.document_id: "42"
```

#### **Find User Actions**
```
category: "user_action" AND context.user_id: "user@example.com"
```

#### **Find Failed Celery Tasks**
```
component: "tasks.documents" AND level: ERROR
```

### **Creating Visualizations**

1. Navigate to **Analytics** → **Visualize Library**
2. Click **Create visualization**
3. Examples:
   - **Request Duration Over Time**: Line chart with `@timestamp` and `avg(duration_ms)`
   - **Error Rate**: Bar chart with `level` and `count()`
   - **Top 10 Slowest Endpoints**: Table with `context.path` and `avg(duration_ms)`
   - **Documents Processed**: Counter with `count()` where `operation: "document_processing"`

### **Creating Dashboards**

1. Navigate to **Analytics** → **Dashboard**
2. Click **Create dashboard**
3. Add visualizations created above
4. Save dashboard

---

## 🔍 **Log Structure**

All logs sent to Elasticsearch have this structure:

```json
{
  "@timestamp": "2025-10-01T12:34:56.789Z",
  "level": "INFO",
  "category": "data_processing",
  "message": "Document processed successfully",
  "component": "documents.processor",
  "operation": "process_document",
  "context": {
    "request_id": "abc123-def456",
    "user_id": "user@example.com",
    "task_id": "celery-task-789",
    "document_id": "42",
    "customer_id": "local-dev"
  },
  "duration_ms": 1234.56,
  "items_processed": 1,
  "metadata": {
    "document_type": "pdf",
    "pages": 10
  },
  "service": "ai-platform",
  "tags": []
}
```

### **Key Fields:**

- **@timestamp** - When the log was created (ISO 8601)
- **level** - Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **category** - Log category (system, api, data_processing, etc.)
- **message** - Human-readable message
- **component** - Source component (e.g., "documents.processor")
- **operation** - Operation name (e.g., "process_document")
- **context** - Request/task context (request_id, user_id, etc.)
- **duration_ms** - Operation duration in milliseconds
- **metadata** - Additional structured data
- **tags** - Automatically added tags (e.g., "slow_request", "error")

---

## ⚙️ **Configuration**

### **Environment Variables**

Set in `docker-compose.yml`:

```yaml
# Enable Logstash
- LOGSTASH_ENABLED=true
- LOGSTASH_HOST=logstash
- LOGSTASH_PORT=5000

# Enable file logging
- LOG_TO_FILE=true

# Use JSON format for logs
- LOG_JSON_FORMAT=true
```

### **Logstash Pipeline**

Located at: `docker/config/logstash/logstash.conf`

The pipeline:
1. **Receives logs** on TCP port 5000
2. **Parses timestamps** and converts to `@timestamp`
3. **Extracts context fields** for easier querying
4. **Tags** slow requests and errors
5. **Sends to Elasticsearch** with daily indices

### **Elasticsearch Indices**

Logs are stored in daily indices:
- Format: `ai-platform-logs-YYYY.MM.dd`
- Example: `ai-platform-logs-2025.10.01`

This enables:
- Easy cleanup of old logs
- Better query performance
- Automatic index lifecycle management

---

## 🔧 **Troubleshooting**

### **Logs Not Appearing in Kibana**

1. **Check Logstash health**:
   ```bash
   curl http://localhost:9600/_node/stats
   ```

2. **Check application logs**:
   ```bash
   docker-compose -f docker/docker-compose.yml logs app | grep -i logstash
   ```
   Should see: "✅ Logstash handler enabled: logstash:5000"

3. **Check Elasticsearch indices**:
   ```bash
   curl http://localhost:9200/_cat/indices?v
   ```
   Should see: `ai-platform-logs-*` indices

4. **Check Logstash pipeline**:
   ```bash
   docker-compose -f docker/docker-compose.yml logs logstash | tail -50
   ```
   Should see: "Successfully started Logstash API endpoint"

### **Elasticsearch Out of Memory**

If Elasticsearch crashes:

1. **Increase heap size** in `docker-compose.yml`:
   ```yaml
   environment:
     - "ES_JAVA_OPTS=-Xms1g -Xmx1g"
   ```

2. **Increase Docker memory** in Docker Desktop settings (minimum 4GB)

### **Kibana Not Loading**

1. **Wait longer** - First startup takes 2-3 minutes
2. **Check Elasticsearch** - Kibana needs ES to be healthy
3. **Clear browser cache** and reload
4. **Check logs**:
   ```bash
   docker-compose -f docker/docker-compose.yml logs kibana
   ```

### **Slow Query Performance**

1. **Add more fields to extraction** in Logstash config
2. **Create index patterns** with smaller time ranges
3. **Use aggregations** instead of raw queries
4. **Close old indices**:
   ```bash
   curl -X POST "localhost:9200/ai-platform-logs-2025.09.*/_close"
   ```

---

## 📈 **Performance Considerations**

### **Resource Usage**

Default configuration:
- **Elasticsearch**: 512MB-1GB RAM, 1 CPU
- **Logstash**: 256MB-512MB RAM, 0.5 CPU
- **Kibana**: 512MB-1GB RAM, 1 CPU
- **Total**: ~2-3GB RAM, 2 CPUs

### **Scaling**

For production with high log volume:

1. **Increase Elasticsearch heap**:
   ```yaml
   environment:
     - "ES_JAVA_OPTS=-Xms2g -Xmx2g"
   ```

2. **Add Elasticsearch nodes**:
   - Change `discovery.type=single-node` to cluster mode
   - Add additional ES containers

3. **Increase Logstash workers**:
   ```yaml
   environment:
     - pipeline.workers=4
   ```

4. **Use multiple Logstash instances** for high throughput

### **Data Retention**

Logs are stored indefinitely by default. To limit storage:

1. **Create ILM policy** in Kibana:
   - Navigate to **Management** → **Stack Management** → **Index Lifecycle Policies**
   - Create policy to delete indices after N days

2. **Or manually delete old indices**:
   ```bash
   # Delete indices older than 30 days
   curl -X DELETE "localhost:9200/ai-platform-logs-2025.09.*"
   ```

---

## 🛡️ **Security**

The default configuration has **security disabled** for development.

For production:

1. **Enable Elasticsearch security**:
   ```yaml
   environment:
     - xpack.security.enabled=true
   ```

2. **Set up authentication**:
   - Generate passwords: `elasticsearch-setup-passwords auto`
   - Update Logstash config with credentials
   - Update Kibana config with credentials

3. **Enable HTTPS**:
   - Generate certificates
   - Configure TLS in all services

4. **Restrict network access**:
   - Remove port mappings for ES/Logstash
   - Only expose Kibana

---

## 📚 **Additional Resources**

- **Elasticsearch Docs**: https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html
- **Logstash Docs**: https://www.elastic.co/guide/en/logstash/current/index.html
- **Kibana Docs**: https://www.elastic.co/guide/en/kibana/current/index.html
- **Query DSL**: https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl.html

---

## ✅ **Health Check Commands**

```bash
# Check all ELK services
docker-compose -f docker/docker-compose.yml ps | grep -E "elasticsearch|logstash|kibana"

# Elasticsearch health
curl http://localhost:9200/_cluster/health?pretty

# Logstash stats
curl http://localhost:9600/_node/stats?pretty

# Kibana status
curl http://localhost:5601/api/status

# Check log indices
curl http://localhost:9200/_cat/indices/ai-platform-logs-*?v

# Count logs in today's index
curl http://localhost:9200/ai-platform-logs-$(date +%Y.%m.%d)/_count

# Sample recent logs
curl -X GET "http://localhost:9200/ai-platform-logs-*/_search?pretty" -H 'Content-Type: application/json' -d'
{
  "size": 5,
  "sort": [{"@timestamp": "desc"}],
  "query": {"match_all": {}}
}
'
```

---

## 🎓 **Common Use Cases**

### **Debug a Failed Document**

1. Get document ID from UI
2. In Kibana, search:
   ```
   context.document_id: "42"
   ```
3. Review all logs in timeline
4. Look for ERROR logs with stack traces

### **Monitor API Performance**

1. Create visualization:
   - Type: Line chart
   - X-axis: `@timestamp`
   - Y-axis: `avg(duration_ms)`
   - Filter: `category: "api"`

2. Add to dashboard
3. Set auto-refresh: 30 seconds

### **Track User Activity**

1. Search:
   ```
   context.user_id: "user@example.com" AND category: "user_action"
   ```

2. Create table visualization showing:
   - `@timestamp`
   - `user_action`
   - `metadata`

### **Find Performance Bottlenecks**

1. Search:
   ```
   duration_ms >= 1000
   ```

2. Create table showing:
   - `component`
   - `operation`
   - `avg(duration_ms)`
   - `count()`

3. Sort by `avg(duration_ms)` descending

---

**Version History:**
- 1.0 (Oct 1, 2025) - Initial ELK stack integration guide

