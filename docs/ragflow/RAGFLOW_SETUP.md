# RAGFlow Integration Guide

RAGFlow runs as a **sidecar deployment** alongside ElizaPlatform, sharing infrastructure (Elasticsearch, Redis) while maintaining its own MySQL database for metadata.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SHARED DOCKER NETWORK                                     │
│                        (docker_ai-platform)                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┴───────────────────────────┐
        │                                                       │
        ▼                                                       ▼
┌───────────────────────────────────┐       ┌───────────────────────────────────┐
│      ElizaPlatform                │       │      RAGFlow Sidecar              │
│      (docker-compose.yml)         │       │      (eliza-integration/)         │
│                                   │       │                                   │
│  ┌─────────┐  ┌─────────────────┐ │       │  ┌──────────────────────────────┐ │
│  │   App   │──│ RAGFlowService  │─┼───────┼──│  RAGFlow API (:9380)         │ │
│  │ :5001   │  │   (HTTP client) │ │       │  │  RAGFlow Web UI (:8080)      │ │
│  └─────────┘  └─────────────────┘ │       │  └──────────────────────────────┘ │
│                                   │       │               │                   │
│  ┌─────────────────────────────┐  │       │               │                   │
│  │     Shared Infrastructure   │  │       │  ┌────────────┴─────────────┐    │
│  │                             │  │       │  │   RAGFlow MySQL (:3307)  │    │
│  │  • Elasticsearch (:9200)  ◄─┼──┼───────┼──│   (metadata only)        │    │
│  │  • Redis (:6379)          ◄─┼──┼───────┼──┘                          │    │
│  │  • PostgreSQL (:5432)       │  │       └───────────────────────────────────┘
│  └─────────────────────────────┘  │
└───────────────────────────────────┘
```

## Data Flow

### 1. Document Upload
```
Frontend → App API → RAGFlowService → RAGFlow:9380 → Parse Document → Index to Elasticsearch
```

### 2. RAG Query (Chat)
```
Frontend → App API → RAGFlowService.chat()
                           │
                           ├─→ RAGFlow:9380/retrieval → Elasticsearch (hybrid BM25 + vector)
                           │                          → Returns relevant chunks
                           │
                           └─→ LiteLLM (OpenAI/Anthropic) → Generate answer with context
                                                          → Return to frontend
```

### 3. Domain Management
```
App creates domain in PostgreSQL + dataset in RAGFlow
RAGFlow stores vectors in shared Elasticsearch
Metadata synced: RAGFlow MySQL ↔ ElizaPlatform PostgreSQL (via API)
```

---

## Local Development Setup

### Prerequisites
- Docker & Docker Compose
- ElizaPlatform running (`docker_ai-platform` network must exist)

### 1. Clone RAGFlow (if not already done)
```bash
cd /home/azureuser
git clone https://github.com/infiniflow/ragflow.git
```

### 2. Create Eliza Integration Directory
```bash
mkdir -p /home/azureuser/ragflow/docker/eliza-integration
```

### 3. Create docker-compose.yml
```yaml
# /home/azureuser/ragflow/docker/eliza-integration/docker-compose.yml
version: '3.9'

services:
  ragflow-mysql:
    image: mysql:8.0.39
    container_name: ragflow-mysql
    environment:
      - MYSQL_ROOT_PASSWORD=${RAGFLOW_MYSQL_PASSWORD:-ragflow_secret_2024}
      - MYSQL_DATABASE=rag_flow
    command:
      --max_connections=1000
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
      --default-authentication-plugin=mysql_native_password
    ports:
      - "3307:3306"
    volumes:
      - ragflow_mysql_data:/var/lib/mysql
    networks:
      - docker_ai-platform
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-uroot", "-p${RAGFLOW_MYSQL_PASSWORD:-ragflow_secret_2024}"]
      interval: 10s
      timeout: 10s
      retries: 120
    restart: unless-stopped

  ragflow:
    image: infiniflow/ragflow:v0.18.0
    container_name: ragflow
    command: ["--workers=4"]
    depends_on:
      ragflow-mysql:
        condition: service_healthy
    ports:
      - "9380:9380"   # API
      - "9381:9381"   # Admin/Tasks
      - "8080:80"     # Web UI
    volumes:
      - ./service_conf.yaml.template:/ragflow/conf/service_conf.yaml.template
      - ./ragflow-logs:/ragflow/logs
      - ragflow_data:/ragflow/data
    environment:
      - MYSQL_HOST=ragflow-mysql
      - MYSQL_PORT=3306
      - MYSQL_PASSWORD=${RAGFLOW_MYSQL_PASSWORD:-ragflow_secret_2024}
      - ES_HOST=${ELASTICSEARCH_HOST:-docker-elasticsearch-1}
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD:-elastic}
      - REDIS_HOST=${REDIS_HOST:-docker-redis-1}
      # Storage (S3 or local)
      - STORAGE_IMPL=${STORAGE_IMPL:-LOCAL}
      # LLM Configuration
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      # Performance tuning
      - MAX_CONCURRENT_TASKS=20
      - MAX_CONCURRENT_CHUNK_BUILDERS=10
      - EMBEDDING_BATCH_SIZE=64
    networks:
      - docker_ai-platform
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:9380/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 120s

volumes:
  ragflow_mysql_data:
  ragflow_data:

networks:
  docker_ai-platform:
    external: true
```

### 4. Create service_conf.yaml.template
```yaml
# /home/azureuser/ragflow/docker/eliza-integration/service_conf.yaml.template
ragflow:
  host: 0.0.0.0
  http_port: 9380

admin:
  host: 0.0.0.0
  http_port: 9381

mysql:
  name: 'rag_flow'
  user: 'root'
  password: '${MYSQL_PASSWORD}'
  host: '${MYSQL_HOST}'
  port: 3306
  max_connections: 900
  stale_timeout: 300

es:
  hosts: 'http://${ES_HOST}:9200'
  username: 'elastic'
  password: '${ELASTIC_PASSWORD}'

redis:
  db: 2
  username: ''
  password: ''
  host: '${REDIS_HOST}:6379'

# For local dev, use LOCAL storage
# For production, configure S3
storage:
  impl: '${STORAGE_IMPL}'

# S3 config (only used if STORAGE_IMPL=AWS_S3)
s3:
  access_key: '${AWS_ACCESS_KEY_ID}'
  secret_key: '${AWS_SECRET_ACCESS_KEY}'
  region: '${AWS_DEFAULT_REGION}'
  bucket: '${S3_BUCKET}'
  prefix_path: 'ragflow'

user_default_llm:
  factory: 'OpenAI'
  api_key: '${OPENAI_API_KEY}'
  base_url: 'https://api.openai.com/v1'
  default_models:
    chat_model: 'gpt-4o'
    embedding_model: 'text-embedding-3-large'
    image2text_model: 'gpt-4o'
```

### 5. Create .env file
```bash
# /home/azureuser/ragflow/docker/eliza-integration/.env
RAGFLOW_MYSQL_PASSWORD=your_secure_password_here
ELASTICSEARCH_HOST=docker-elasticsearch-1
ELASTIC_PASSWORD=elastic
REDIS_HOST=docker-redis-1
STORAGE_IMPL=LOCAL
OPENAI_API_KEY=sk-your-key-here
```

### 6. Start RAGFlow
```bash
# First, ensure ElizaPlatform is running (creates the network)
cd /home/azureuser/ElizaPlatform/docker
docker-compose up -d

# Then start RAGFlow sidecar
cd /home/azureuser/ragflow/docker/eliza-integration
docker-compose up -d
```

### 7. Verify
```bash
# Check containers
docker ps | grep ragflow

# Check health
curl http://localhost:9380/v1/health

# Access Web UI
open http://localhost:8080
```

---

## Production Deployment

### Option 1: Kubernetes (Recommended)

Deploy RAGFlow as a separate Helm chart that connects to your existing infrastructure.

```yaml
# ragflow-values.yaml
image:
  repository: infiniflow/ragflow
  tag: v0.18.0

mysql:
  enabled: true
  auth:
    rootPassword: "${RAGFLOW_MYSQL_PASSWORD}"
    database: rag_flow

elasticsearch:
  enabled: false  # Use existing
  externalHost: "elasticsearch.eliza-platform.svc.cluster.local"
  externalPort: 9200

redis:
  enabled: false  # Use existing
  externalHost: "redis.eliza-platform.svc.cluster.local"
  externalPort: 6379

env:
  - name: OPENAI_API_KEY
    valueFrom:
      secretKeyRef:
        name: ragflow-secrets
        key: openai-api-key
  - name: STORAGE_IMPL
    value: "AWS_S3"
  - name: AWS_ACCESS_KEY_ID
    valueFrom:
      secretKeyRef:
        name: ragflow-secrets
        key: aws-access-key
  - name: AWS_SECRET_ACCESS_KEY
    valueFrom:
      secretKeyRef:
        name: ragflow-secrets
        key: aws-secret-key
  - name: S3_BUCKET
    value: "your-prod-bucket"

service:
  type: ClusterIP
  port: 9380

ingress:
  enabled: true
  hosts:
    - host: ragflow.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
```

### Option 2: Docker Compose (Simpler deployments)

Use the same docker-compose.yml but with production .env:

```bash
# production.env
RAGFLOW_MYSQL_PASSWORD=<strong-generated-password>
ELASTICSEARCH_HOST=your-es-host
ELASTIC_PASSWORD=<es-password>
REDIS_HOST=your-redis-host

# S3 for document storage
STORAGE_IMPL=AWS_S3
AWS_ACCESS_KEY_ID=<from-iam-role-or-secret>
AWS_SECRET_ACCESS_KEY=<from-iam-role-or-secret>
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=your-production-bucket

# LLM
OPENAI_API_KEY=<from-secrets-manager>
```

### Option 3: Northflank/Railway/Render

1. Create a new service from Docker image `infiniflow/ragflow:v0.18.0`
2. Set environment variables (use secrets for sensitive values)
3. Create a MySQL addon or connect to existing
4. Configure networking to reach existing Elasticsearch/Redis
5. Set the entry command: `--workers=4`

---

## ElizaPlatform Configuration

Add these to your ElizaPlatform `.env`:

```bash
# RAGFlow connection
RAGFLOW_API_KEY=<api-key-from-ragflow-admin>
RAGFLOW_BASE_URL=http://ragflow:9380  # Docker internal
# Or for external: https://ragflow.yourdomain.com
```

The App and Celery workers use these to communicate with RAGFlow.

---

## API Endpoints

### ElizaPlatform RAGFlow Routes (`/v1/ragflow/`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/domains` | GET | List all RAG domains |
| `/domains` | POST | Create new domain (creates RAGFlow dataset) |
| `/domains/{id}` | GET | Get domain details |
| `/domains/{id}` | DELETE | Delete domain + RAGFlow dataset |
| `/domains/{id}/documents` | GET | List documents in domain |
| `/domains/{id}/documents` | POST | Upload document (multipart) |
| `/domains/{id}/documents/{doc_id}` | DELETE | Delete document |
| `/domains/{id}/parse` | POST | Start parsing pending documents |
| `/domains/{id}/conversations` | GET/POST | Manage conversations |
| `/domains/{id}/conversations/{conv_id}/messages` | POST | Send message (triggers RAG) |

### RAGFlow Direct API (`:9380`)

Only use directly for admin/debugging:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/health` | GET | Health check |
| `/v1/datasets` | GET/POST | Dataset management |
| `/v1/datasets/{id}/documents` | GET/POST | Document management |
| `/v1/retrieval` | POST | Semantic search |

---

## Frontend Integration

The frontend is fully integrated and NOT waste code:

| Component | Path | Purpose |
|-----------|------|---------|
| `DomainsPage` | `/domains` | List/create domains |
| `DomainDetailPage` | `/domains/:id` | Manage documents, upload |
| `CreateDomainModal` | Modal | Create new domain with parser config |
| `RAGFlowConversationView` | `/data-analyst?domain=X` | Chat with domain |
| `DataSourceSelector` | Data Analyst landing | Choose built-in or RAG domain |
| `DomainContextPill` | Header dropdown | Switch domains mid-chat |

### User Flow
1. User goes to `/domains` → Creates domain (GPT-4o/DeepDoc/Naive parser)
2. Goes to `/domains/:id` → Uploads documents
3. Documents parse automatically (polling shows progress)
4. When ready, clicks "Chat" → `/data-analyst?domain=X`
5. Uses `RAGFlowConversationView` for RAG chat

---

## Security Considerations

### Secrets Management

**NEVER commit these to git:**
- `OPENAI_API_KEY`
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`
- `RAGFLOW_MYSQL_PASSWORD`
- `RAGFLOW_API_KEY`

Use:
- Docker secrets
- Kubernetes secrets
- AWS Secrets Manager
- Vault
- Environment variables from CI/CD

### Network Security

1. **Internal only**: RAGFlow should NOT be publicly exposed in production
2. **Use internal DNS**: `http://ragflow:9380` within Docker network
3. **API Gateway**: If external access needed, route through your API gateway with auth

### Data at Rest

1. **Elasticsearch**: Enable encryption at rest
2. **S3**: Use server-side encryption (SSE-S3 or SSE-KMS)
3. **MySQL**: Use encrypted volumes

---

## Troubleshooting

### RAGFlow not connecting to Elasticsearch

```bash
# Check Elasticsearch is healthy
curl http://localhost:9200/_cluster/health

# Check RAGFlow can reach ES
docker exec ragflow curl http://docker-elasticsearch-1:9200/_cluster/health

# Check logs
docker logs ragflow 2>&1 | grep -i elastic
```

### Documents stuck in "parsing"

```bash
# Check RAGFlow task workers
docker logs ragflow 2>&1 | grep -i task

# Check if OpenAI API is working (for GPT-4o parser)
docker exec ragflow env | grep OPENAI

# Restart parsing
curl -X POST http://localhost:9380/v1/datasets/{dataset_id}/chunks \
  -H "Authorization: Bearer $RAGFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": ["doc-id-here"]}'
```

### Connection refused errors

```bash
# Verify network
docker network inspect docker_ai-platform

# Check if containers are on same network
docker inspect ragflow | grep -A 20 Networks
docker inspect docker-elasticsearch-1 | grep -A 20 Networks
```

---

## Monitoring

### Health Checks

```bash
# RAGFlow health
curl http://localhost:9380/v1/health

# MySQL
docker exec ragflow-mysql mysqladmin ping -uroot -p

# Check document processing
curl http://localhost:9380/v1/datasets \
  -H "Authorization: Bearer $RAGFLOW_API_KEY"
```

### Logs

```bash
# RAGFlow logs
docker logs -f ragflow

# MySQL logs  
docker logs -f ragflow-mysql

# All RAGFlow-related
docker-compose -f /path/to/eliza-integration/docker-compose.yml logs -f
```

---

## Upgrading RAGFlow

1. Check release notes: https://github.com/infiniflow/ragflow/releases
2. Update image tag in docker-compose.yml
3. Backup MySQL data
4. Pull new image and restart:

```bash
cd /home/azureuser/ragflow/docker/eliza-integration
docker-compose pull ragflow
docker-compose up -d ragflow
```

---

## Ports Summary

| Service | Port | Purpose |
|---------|------|---------|
| RAGFlow API | 9380 | Main API endpoint |
| RAGFlow Admin | 9381 | Task management |
| RAGFlow Web UI | 8080 | Browser interface |
| RAGFlow MySQL | 3307 | Metadata storage |
| Elasticsearch | 9200 | Vector + BM25 search (shared) |
| Redis | 6379 | Caching (shared) |
