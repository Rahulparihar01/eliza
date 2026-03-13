# Containerized Build Specification for AI Enablement Platform

## Executive Summary

This document provides comprehensive step-by-step instructions for building the AI Enablement Platform using a fully containerized approach with Docker and Kubernetes. The specification includes multi-platform Docker builds, service containerization, Kubernetes deployment, and development workflows.

**Key Principles:**
- **Fully Containerized**: All services run in containers for consistency and portability
- **Multi-Platform Support**: CPU, NVIDIA GPU, and AMD GPU container variants
- **Kubernetes-Native**: Designed for Kubernetes orchestration from the ground up
- **Development-Friendly**: Local development with Docker Compose
- **Production-Ready**: Helm charts and production deployment patterns

---

## 1. Step-by-Step Build Process

### Step 1: Environment & Repository Setup
*Duration: 1-2 days*
*References: [TECHNICAL_SPECIFICATION.md](TECHNICAL_SPECIFICATION.md) - Section 6.3*

#### 1.1 Initialize Project Structure
```bash
# Create main project directory
mkdir ai-enablement-platform
cd ai-enablement-platform

# Create containerized directory structure
mkdir -p {
  docker/{base,services,compose},
  k8s/{deployments,services,configmaps,secrets},
  helm/{charts,values},
  scripts/{build,deploy,dev},
  src/{api,agents,ingestion,analysis},
  config/{dev,staging,prod},
  docs/deployment,
  data/{samples,uploads,cache}
}
```

#### 1.2 Initialize Git and Container Registry
```bash
# Initialize Git repository
git init
git remote add origin <your-repo-url>

# Set up container registry configuration
echo "CONTAINER_REGISTRY=your-registry.com/ai-enablement" > .env
echo "IMAGE_TAG=latest" >> .env
echo "PLATFORM=cpu" >> .env
```

**Design References:**
- `TECHNICAL_SPECIFICATION.md` - Section 6.3 DevOps & Deployment
- `API_DESIGN_SPECIFICATION.md` - Section 1.1 Base URL Structure

### Step 2: Base Docker Images & Multi-Stage Builds
*Duration: 3-5 days*
*References: [TECHNICAL_SPECIFICATION.md](TECHNICAL_SPECIFICATION.md) - Section 1.3 Multi-Platform Docker Strategy*

#### 2.1 Create Base Dockerfile
```dockerfile
# docker/base/Dockerfile
ARG BASE_NAME=cpu
ARG AI_PLATFORM_BASE_IMAGE

# Base stage with common dependencies
FROM ${AI_PLATFORM_BASE_IMAGE} AS base
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app

# Platform-specific optimizations
FROM base AS cpu
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

FROM base AS nvidia
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

FROM base AS amd
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.6

# Final application stage
FROM ${BASE_NAME} AS final

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy and set up entrypoint
COPY docker/base/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Switch to non-root user
USER appuser

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001"]
```

#### 2.2 Create Docker Entrypoint Script
```bash
#!/bin/bash
# docker/base/docker-entrypoint.sh

set -e

# Function for logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Function for error handling
handle_error() {
    local exit_code=$?
    log "ERROR: Command failed with exit code $exit_code"
    log "ERROR: Line $1"
    exit $exit_code
}

# Set up error handling
trap 'handle_error $LINENO' ERR

# Environment validation
validate_environment() {
    log "Validating environment variables..."
    
    # Check required environment variables
    required_vars=("DATABASE_URL" "REDIS_URL")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            log "ERROR: Required environment variable $var is not set"
            exit 1
        fi
    done
    
    log "Environment validation completed"
}

# Wait for dependencies
wait_for_dependencies() {
    log "Waiting for dependencies..."
    
    # Wait for PostgreSQL
    while ! pg_isready -h $(echo $DATABASE_URL | cut -d'@' -f2 | cut -d':' -f1); do
        log "Waiting for PostgreSQL..."
        sleep 2
    done
    
    # Wait for Redis
    while ! redis-cli -h $(echo $REDIS_URL | cut -d'/' -f3 | cut -d':' -f1) ping; do
        log "Waiting for Redis..."
        sleep 2
    done
    
    log "Dependencies are ready"
}

# Main function
main() {
    log "Starting AI Enablement Platform container..."
    
    validate_environment
    wait_for_dependencies
    
    log "Executing command: $@"
    exec "$@"
}

# Run main function with all arguments
main "$@"
```

#### 2.3 Create Build Scripts
```bash
#!/bin/bash
# scripts/build/build-images.sh

set -e

PLATFORMS=("cpu" "nvidia" "amd")
VERSION=${1:-latest}
REGISTRY=${2:-aiplatform}

get_base_image() {
    case $1 in
        "cpu")
            echo "python:3.10.6"
            ;;
        "nvidia")
            echo "nvcr.io/nvidia/pytorch:23.05-py3"
            ;;
        "amd")
            echo "rocm/pytorch:rocm6.1_ubuntu22.04_py3.10_pytorch_2.1.2"
            ;;
    esac
}

for platform in "${PLATFORMS[@]}"; do
    echo "Building $platform image..."
    docker build \
        --build-arg BASE_NAME=$platform \
        --build-arg AI_PLATFORM_BASE_IMAGE=$(get_base_image $platform) \
        -t $REGISTRY/ai-enablement-platform:$VERSION-$platform \
        -f docker/base/Dockerfile .
    
    echo "Built $REGISTRY/ai-enablement-platform:$VERSION-$platform"
done

echo "All platform images built successfully!"
```

**Design References:**
- `TECHNICAL_SPECIFICATION.md` - Section 1.3 Multi-Platform Docker Strategy
- `TECHNICAL_SPECIFICATION.md` - Section 1.2 Infrastructure Components

### Step 3: Core Services Containerization
*Duration: 1-2 weeks*
*References: [API_DESIGN_SPECIFICATION.md](API_DESIGN_SPECIFICATION.md) - Section 2, [TECHNICAL_SPECIFICATION.md](TECHNICAL_SPECIFICATION.md) - Section 2.1*

#### 3.1 Main API Service Container
```dockerfile
# docker/services/api/Dockerfile
FROM aiplatform/ai-enablement-platform:latest-cpu

# Install API-specific dependencies
RUN pip install \
    fastapi \
    uvicorn \
    sqlalchemy \
    alembic \
    psycopg2-binary \
    redis \
    pyjwt \
    python-multipart

# Copy API source code
COPY src/api /app/api
COPY config/api /app/config/api

# API-specific environment variables
ENV FASTAPI_ENV=production
ENV LOG_LEVEL=INFO

EXPOSE 5001

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "5001"]
```

#### 3.2 Docker Compose for Development
```yaml
# docker/compose/docker-compose.dev.yml
version: '3.8'

services:
  # Main API Service
  api:
    build:
      context: .
      dockerfile: docker/services/api/Dockerfile
    ports:
      - "5001:5001"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - REDIS_URL=redis://redis:6379
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      - JWT_SECRET_KEY=your-secret-key
      - LOG_LEVEL=DEBUG
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      neo4j:
        condition: service_healthy
    volumes:
      - ./src:/app/src:ro
      - ./config:/app/config:ro
      - api_logs:/app/logs
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # PostgreSQL Database
  postgres:
    image: postgres:15.7
    environment:
      POSTGRES_DB: ai_enablement
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8"
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d ai_enablement"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
      - ./docker/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    command: redis-server /usr/local/etc/redis/redis.conf
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3

  # Neo4j Knowledge Graph
  neo4j:
    image: neo4j:5.13
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
      NEO4J_dbms_security_procedures_unrestricted: "gds.*,apoc.*"
      NEO4J_dbms_memory_heap_initial__size: 1G
      NEO4J_dbms_memory_heap_max__size: 2G
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - ./docker/neo4j/init.cypher:/var/lib/neo4j/init.cypher:ro
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "password", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 3

  # RabbitMQ Message Queue
  rabbitmq:
    image: rabbitmq:3-management
    environment:
      RABBITMQ_DEFAULT_USER: user
      RABBITMQ_DEFAULT_PASS: pass
      RABBITMQ_DEFAULT_VHOST: ai_enablement
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./docker/rabbitmq/rabbitmq.conf:/etc/rabbitmq/rabbitmq.conf:ro
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  redis_data:
  neo4j_data:
  neo4j_logs:
  rabbitmq_data:
  api_logs:

networks:
  ai-platform:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

**Design References:**
- `API_DESIGN_SPECIFICATION.md` - Section 2 Authentication & Authorization
- `TECHNICAL_SPECIFICATION.md` - Section 2.1 FastAPI Microservices Design
- `LOGGING_SPECIFICATION.md` - Section 1.1 Structured Log Format

### Step 4: CrewAI Agent Containerization
*Duration: 2-3 weeks*
*References: [CREWAI_IMPLEMENTATION_SPECIFICATION.md](CREWAI_IMPLEMENTATION_SPECIFICATION.md) - Section 1.1, [AI_ENABLEMENT_PLATFORM_IMPLEMENTATION_PLAN.md](AI_ENABLEMENT_PLATFORM_IMPLEMENTATION_PLAN.md) - Section 3.1*

#### 4.1 CrewAI Agent Service Container
```dockerfile
# docker/services/agents/Dockerfile
FROM aiplatform/ai-enablement-platform:latest-cpu

# Install CrewAI and agent dependencies
RUN pip install \
    crewai \
    crewai-tools \
    langchain \
    langchain-openai \
    openai \
    anthropic

# Copy agent configurations and code
COPY src/agents /app/agents
COPY config/crewai /app/config/crewai

# Agent-specific environment variables
ENV CREWAI_LOG_LEVEL=INFO
ENV CREWAI_SAVE_LOGS=true
ENV CREWAI_LOG_FORMAT=json
ENV PYTHONPATH=/app

EXPOSE 5002

CMD ["python", "-m", "agents.main"]
```

#### 4.2 Agent Services Configuration
```yaml
# docker/compose/agents.yml
version: '3.8'

services:
  # Department Analysis Agent
  dept-analyzer:
    build:
      context: .
      dockerfile: docker/services/agents/Dockerfile
    environment:
      - AGENT_TYPE=department_analyzer
      - CREWAI_CONFIG_PATH=/app/config/crewai/dept_analyzer.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - api
      - postgres
      - neo4j
    volumes:
      - agent_logs:/app/logs
    networks:
      - ai-platform
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 1G
          cpus: '0.5'

  # Skills Gap Analysis Agent  
  skills-analyzer:
    build:
      context: .
      dockerfile: docker/services/agents/Dockerfile
    environment:
      - AGENT_TYPE=skills_gap_analyst
      - CREWAI_CONFIG_PATH=/app/config/crewai/skills_analyzer.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - api
      - postgres
      - neo4j
    volumes:
      - agent_logs:/app/logs
    networks:
      - ai-platform
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'

  # ROI Calculator Agent
  roi-calculator:
    build:
      context: .
      dockerfile: docker/services/agents/Dockerfile
    environment:
      - AGENT_TYPE=roi_calculator
      - CREWAI_CONFIG_PATH=/app/config/crewai/roi_calculator.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - api
      - postgres
    volumes:
      - agent_logs:/app/logs
    networks:
      - ai-platform
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'

  # Personality Matcher Agent
  personality-matcher:
    build:
      context: .
      dockerfile: docker/services/agents/Dockerfile
    environment:
      - AGENT_TYPE=personality_matcher
      - CREWAI_CONFIG_PATH=/app/config/crewai/personality_matcher.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    depends_on:
      - api
      - postgres
      - neo4j
    volumes:
      - agent_logs:/app/logs
    networks:
      - ai-platform

volumes:
  agent_logs:

networks:
  ai-platform:
    external: true
```

**Design References:**
- `CREWAI_IMPLEMENTATION_SPECIFICATION.md` - Section 1.1 Core Components Mapping
- `AI_ENABLEMENT_PLATFORM_IMPLEMENTATION_PLAN.md` - Section 3.1 CrewAI Analysis Flow
- `USER_TASK_ENRICHMENT_SPECIFICATION.md` - Section 1.1 Core Components

### Step 5: Data Ingestion Pipeline Containerization
*Duration: 2-3 weeks*
*References: [DATA_INGESTION_PROCESSING_SPECIFICATION.md](DATA_INGESTION_PROCESSING_SPECIFICATION.md) - Section 1.1, [MEMORY_RAG_DEEP_DIVE.md](MEMORY_RAG_DEEP_DIVE.md)*

#### 5.1 Data Ingestion Service Container
```dockerfile
# docker/services/ingestion/Dockerfile
FROM aiplatform/ai-enablement-platform:latest-cpu

# Install data processing dependencies
RUN pip install \
    pandas \
    numpy \
    faiss-cpu \
    sentence-transformers \
    python-multipart \
    aiofiles \
    openpyxl \
    python-docx \
    PyPDF2 \
    beautifulsoup4 \
    lxml

# Copy ingestion code
COPY src/ingestion /app/ingestion
COPY config/ingestion /app/config/ingestion

# Create directories for data processing
RUN mkdir -p /app/data/{input,processed,cache} && \
    chown -R appuser:appuser /app/data

EXPOSE 5003

CMD ["python", "-m", "ingestion.main"]
```

#### 5.2 Data Processing Services
```yaml
# docker/compose/ingestion.yml
version: '3.8'

services:
  # HR Data Processor
  hr-processor:
    build:
      context: .
      dockerfile: docker/services/ingestion/Dockerfile
    environment:
      - PROCESSOR_TYPE=hr_data
      - DATA_SOURCE_CONFIG=/app/config/ingestion/hr_sources.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
    volumes:
      - ./data/hr:/app/data/hr:ro
      - hr_processed:/app/data/processed
      - ingestion_logs:/app/logs
    depends_on:
      - postgres
      - neo4j
    networks:
      - ai-platform

  # Financial Data Processor
  financial-processor:
    build:
      context: .
      dockerfile: docker/services/ingestion/Dockerfile
    environment:
      - PROCESSOR_TYPE=financial_data
      - DATA_SOURCE_CONFIG=/app/config/ingestion/financial_sources.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
    volumes:
      - ./data/financial:/app/data/financial:ro
      - financial_processed:/app/data/processed
      - ingestion_logs:/app/logs
    depends_on:
      - postgres
    networks:
      - ai-platform

  # Document Processor
  doc-processor:
    build:
      context: .
      dockerfile: docker/services/ingestion/Dockerfile
    environment:
      - PROCESSOR_TYPE=document
      - DATA_SOURCE_CONFIG=/app/config/ingestion/doc_sources.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./data/documents:/app/data/documents:ro
      - document_cache:/app/cache
      - doc_processed:/app/data/processed
      - ingestion_logs:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - ai-platform
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'

  # Memory RAG Indexer
  rag-indexer:
    build:
      context: .
      dockerfile: docker/services/ingestion/Dockerfile
    environment:
      - PROCESSOR_TYPE=rag_indexer
      - EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - REDIS_URL=redis://redis:6379
    volumes:
      - rag_indices:/app/indices
      - document_cache:/app/cache:ro
      - ingestion_logs:/app/logs
    depends_on:
      - postgres
      - redis
      - doc-processor
    networks:
      - ai-platform
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4.0'

  # CRM Data Processor
  crm-processor:
    build:
      context: .
      dockerfile: docker/services/ingestion/Dockerfile
    environment:
      - PROCESSOR_TYPE=crm_data
      - DATA_SOURCE_CONFIG=/app/config/ingestion/crm_sources.yml
      - DATABASE_URL=postgresql://user:pass@postgres:5432/ai_enablement
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
    volumes:
      - ./data/crm:/app/data/crm:ro
      - crm_processed:/app/data/processed
      - ingestion_logs:/app/logs
    depends_on:
      - postgres
      - neo4j
    networks:
      - ai-platform

volumes:
  hr_processed:
  financial_processed:
  doc_processed:
  crm_processed:
  document_cache:
  rag_indices:
  ingestion_logs:

networks:
  ai-platform:
    external: true
```

**Design References:**
- `DATA_INGESTION_PROCESSING_SPECIFICATION.md` - Section 1.1 Multi-Source Ingestion Pipeline
- `MEMORY_RAG_DEEP_DIVE.md` - Memory RAG patterns
- `QA_RAG_SPECIFICATION_ADDITION.md` - QA RAG processing

### Step 6: Kubernetes Deployment Configuration
*Duration: 1-2 weeks*
*References: [TECHNICAL_SPECIFICATION.md](TECHNICAL_SPECIFICATION.md) - Section 4.2 Container Orchestration*

#### 6.1 Kubernetes Namespace and ConfigMaps
```yaml
# k8s/namespace.yml
apiVersion: v1
kind: Namespace
metadata:
  name: ai-enablement
  labels:
    name: ai-enablement
---
# k8s/configmaps/app-config.yml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: ai-enablement
data:
  LOG_LEVEL: "INFO"
  CREWAI_LOG_LEVEL: "INFO"
  CREWAI_SAVE_LOGS: "true"
  CREWAI_LOG_FORMAT: "json"
  REDIS_URL: "redis://redis:6379"
  NEO4J_URI: "bolt://neo4j:7687"
  NEO4J_USER: "neo4j"
```

#### 6.2 API Service Deployment
```yaml
# k8s/deployments/api-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-enablement-api
  namespace: ai-enablement
  labels:
    app: ai-enablement-api
    component: api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-enablement-api
  template:
    metadata:
      labels:
        app: ai-enablement-api
        component: api
    spec:
      containers:
      - name: api
        image: aiplatform/ai-enablement-platform:latest-cpu
        ports:
        - containerPort: 5001
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret-key
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        envFrom:
        - configMapRef:
            name: app-config
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5001
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 5001
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        volumeMounts:
        - name: api-logs
          mountPath: /app/logs
      volumes:
      - name: api-logs
        emptyDir: {}
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
---
apiVersion: v1
kind: Service
metadata:
  name: ai-enablement-api
  namespace: ai-enablement
  labels:
    app: ai-enablement-api
spec:
  selector:
    app: ai-enablement-api
  ports:
  - port: 5001
    targetPort: 5001
    name: http
  type: ClusterIP
```

#### 6.3 Helm Chart Structure
```yaml
# helm/charts/ai-enablement-platform/Chart.yaml
apiVersion: v2
name: ai-enablement-platform
description: AI Enablement Platform Helm Chart
type: application
version: 1.0.0
appVersion: "1.0.0"

dependencies:
- name: postgresql
  version: 12.x.x
  repository: https://charts.bitnami.com/bitnami
- name: redis
  version: 17.x.x
  repository: https://charts.bitnami.com/bitnami
```

```yaml
# helm/values/values.yaml
global:
  image:
    repository: aiplatform/ai-enablement-platform
    tag: latest
    pullPolicy: IfNotPresent
  
  storageClass: "standard"

api:
  replicaCount: 3
  service:
    type: ClusterIP
    port: 5001
  resources:
    requests:
      memory: 2Gi
      cpu: 1000m
    limits:
      memory: 4Gi
      cpu: 2000m
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
    targetMemoryUtilizationPercentage: 80

agents:
  departmentAnalyzer:
    enabled: true
    replicaCount: 2
    resources:
      requests:
        memory: 1Gi
        cpu: 500m
      limits:
        memory: 2Gi
        cpu: 1000m
  
  skillsAnalyzer:
    enabled: true
    replicaCount: 2
    resources:
      requests:
        memory: 1Gi
        cpu: 500m
      limits:
        memory: 2Gi
        cpu: 1000m
  
  roiCalculator:
    enabled: true
    replicaCount: 1
    resources:
      requests:
        memory: 512Mi
        cpu: 250m
      limits:
        memory: 1Gi
        cpu: 500m

ingestion:
  hrProcessor:
    enabled: true
    replicaCount: 1
  docProcessor:
    enabled: true
    replicaCount: 2
  ragIndexer:
    enabled: true
    replicaCount: 1

postgresql:
  enabled: true
  auth:
    database: ai_enablement
    username: user
    password: password
  primary:
    persistence:
      enabled: true
      size: 100Gi
      storageClass: "standard"
    resources:
      requests:
        memory: 4Gi
        cpu: 2000m
      limits:
        memory: 8Gi
        cpu: 4000m

redis:
  enabled: true
  auth:
    enabled: false
  master:
    persistence:
      enabled: true
      size: 10Gi
      storageClass: "standard"
    resources:
      requests:
        memory: 1Gi
        cpu: 500m
      limits:
        memory: 2Gi
        cpu: 1000m

neo4j:
  enabled: true
  auth:
    password: password
  persistence:
    size: 50Gi
    storageClass: "standard"
  resources:
    requests:
      memory: 2Gi
      cpu: 1000m
    limits:
      memory: 4Gi
      cpu: 2000m

ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
  hosts:
  - host: ai-enablement.local
    paths:
    - path: /
      pathType: Prefix
  tls: []

monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
```

**Design References:**
- `TECHNICAL_SPECIFICATION.md` - Section 4.2 Container Orchestration
- `TECHNICAL_SPECIFICATION.md` - Section 4.3 Configuration Management
- `API_DESIGN_SPECIFICATION.md` - Section 1.1 Base URL Structure

### Step 7: Development & Deployment Scripts
*Duration: 3-5 days*
*References: [TECHNICAL_SPECIFICATION.md](TECHNICAL_SPECIFICATION.md) - Section 6.3*

#### 7.1 Development Setup Script
```bash
#!/bin/bash
# scripts/dev/setup-dev.sh

set -e

echo "🚀 Setting up AI Enablement Platform development environment..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Build base images
echo "📦 Building base images..."
./scripts/build/build-images.sh latest

# Create development network
echo "🌐 Creating development network..."
docker network create ai-platform 2>/dev/null || true

# Start core services
echo "🔧 Starting core services..."
docker-compose -f docker/compose/docker-compose.dev.yml up -d postgres redis neo4j rabbitmq

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Start API service
echo "🚀 Starting API service..."
docker-compose -f docker/compose/docker-compose.dev.yml up -d api

# Run database migrations
echo "📊 Running database migrations..."
sleep 10
docker-compose -f docker/compose/docker-compose.dev.yml exec api python -m alembic upgrade head

# Initialize Neo4j constraints and indices
echo "🔗 Initializing Neo4j..."
docker-compose -f docker/compose/docker-compose.dev.yml exec neo4j cypher-shell -u neo4j -p password < scripts/neo4j/init-constraints.cypher

# Start agent services
echo "🤖 Starting agent services..."
docker-compose -f docker/compose/agents.yml up -d

# Start ingestion services
echo "📥 Starting ingestion services..."
docker-compose -f docker/compose/ingestion.yml up -d

echo "✅ Development environment ready!"
echo ""
echo "🌐 Services available at:"
echo "  API: http://localhost:5001"
echo "  API Docs: http://localhost:5001/docs"
echo "  Neo4j Browser: http://localhost:7474"
echo "  RabbitMQ Management: http://localhost:15672"
echo ""
echo "📋 To view logs:"
echo "  docker-compose -f docker/compose/docker-compose.dev.yml logs -f"
echo ""
echo "🛑 To stop all services:"
echo "  ./scripts/dev/stop-dev.sh"
```

#### 7.2 Production Deployment Script
```bash
#!/bin/bash
# scripts/deploy/deploy-prod.sh

set -e

ENVIRONMENT=${1:-production}
VERSION=${2:-latest}
NAMESPACE=${3:-ai-enablement}

echo "🚀 Deploying AI Enablement Platform to $ENVIRONMENT..."

# Validate inputs
if [[ ! "$ENVIRONMENT" =~ ^(staging|production)$ ]]; then
    echo "❌ Error: Environment must be 'staging' or 'production'"
    exit 1
fi

# Build and push images
echo "📦 Building and pushing images..."
./scripts/build/build-and-push.sh $VERSION

# Create namespace if it doesn't exist
echo "🏗️ Creating namespace..."
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Apply secrets
echo "🔐 Applying secrets..."
kubectl apply -f k8s/secrets/ -n $NAMESPACE

# Deploy with Helm
echo "⚙️ Deploying with Helm..."
helm upgrade --install ai-enablement-platform \
  ./helm/charts/ai-enablement-platform \
  -f ./helm/values/values-$ENVIRONMENT.yaml \
  --set global.image.tag=$VERSION \
  --namespace $NAMESPACE \
  --timeout 10m \
  --wait

# Verify deployment
echo "✅ Verifying deployment..."
kubectl rollout status deployment/ai-enablement-api -n $NAMESPACE
kubectl get pods -n $NAMESPACE

# Run post-deployment checks
echo "🔍 Running post-deployment checks..."
./scripts/deploy/health-check.sh $NAMESPACE

echo "🎉 Deployment to $ENVIRONMENT completed successfully!"
echo ""
echo "📋 Useful commands:"
echo "  kubectl get pods -n $NAMESPACE"
echo "  kubectl logs -f deployment/ai-enablement-api -n $NAMESPACE"
echo "  helm status ai-enablement-platform -n $NAMESPACE"
```

#### 7.3 Health Check Script
```bash
#!/bin/bash
# scripts/deploy/health-check.sh

set -e

NAMESPACE=${1:-ai-enablement}
MAX_RETRIES=30
RETRY_INTERVAL=10

echo "🔍 Running health checks for AI Enablement Platform..."

# Function to check service health
check_service_health() {
    local service=$1
    local port=$2
    local path=${3:-/health}
    
    echo "Checking $service health..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        if kubectl exec -n $NAMESPACE deployment/$service -- curl -f http://localhost:$port$path >/dev/null 2>&1; then
            echo "✅ $service is healthy"
            return 0
        fi
        
        echo "⏳ Waiting for $service to be healthy (attempt $i/$MAX_RETRIES)..."
        sleep $RETRY_INTERVAL
    done
    
    echo "❌ $service failed health check"
    return 1
}

# Check API service
check_service_health "ai-enablement-api" "5001" "/health"

# Check database connectivity
echo "🔍 Checking database connectivity..."
if kubectl exec -n $NAMESPACE deployment/ai-enablement-api -- python -c "
import psycopg2
import os
try:
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.close()
    print('Database connection successful')
except Exception as e:
    print(f'Database connection failed: {e}')
    exit(1)
"; then
    echo "✅ Database connectivity verified"
else
    echo "❌ Database connectivity failed"
    exit 1
fi

# Check Redis connectivity
echo "🔍 Checking Redis connectivity..."
if kubectl exec -n $NAMESPACE deployment/ai-enablement-api -- python -c "
import redis
import os
try:
    r = redis.from_url(os.environ['REDIS_URL'])
    r.ping()
    print('Redis connection successful')
except Exception as e:
    print(f'Redis connection failed: {e}')
    exit(1)
"; then
    echo "✅ Redis connectivity verified"
else
    echo "❌ Redis connectivity failed"
    exit 1
fi

echo "🎉 All health checks passed!"
```

**Design References:**
- `TECHNICAL_SPECIFICATION.md` - Section 6.3 DevOps & Deployment
- `LOGGING_SPECIFICATION.md` - Section 1.1 Structured Log Format
- `API_DESIGN_SPECIFICATION.md` - Section 12 Health & Monitoring

---

## 2. Container Build Order & Dependencies

### 2.1 Build Sequence
```
1. Base Images (Multi-platform) → 
2. Core Services (API, Database) → 
3. AI Services (CrewAI Agents) → 
4. Data Services (Ingestion, Processing) → 
5. Supporting Services (Monitoring, Logging) → 
6. Integration Testing → 
7. Kubernetes Deployment
```

### 2.2 Dependency Graph
```
PostgreSQL ←─┐
Redis ←──────┼─── API Service ←─── CrewAI Agents
Neo4j ←──────┘                ←─── Data Ingestion
RabbitMQ ←───────────────────────── Background Jobs
```

### 2.3 Service Startup Order
1. **Infrastructure Services**: PostgreSQL, Redis, Neo4j, RabbitMQ
2. **Core API Service**: Main FastAPI application
3. **Agent Services**: CrewAI agents for AI analysis
4. **Ingestion Services**: Data processing and indexing
5. **Monitoring Services**: Logging, metrics, health checks

---

## 3. Development Workflow

### 3.1 Local Development
```bash
# Start development environment
./scripts/dev/setup-dev.sh

# View logs
docker-compose -f docker/compose/docker-compose.dev.yml logs -f

# Run tests
docker-compose -f docker/compose/docker-compose.dev.yml exec api python -m pytest

# Stop environment
./scripts/dev/stop-dev.sh
```

### 3.2 Building for Production
```bash
# Build all platform images
./scripts/build/build-images.sh v1.0.0

# Push to registry
./scripts/build/push-images.sh v1.0.0

# Deploy to staging
./scripts/deploy/deploy-prod.sh staging v1.0.0

# Deploy to production
./scripts/deploy/deploy-prod.sh production v1.0.0
```

---

## 4. Monitoring & Observability

### 4.1 Container Health Checks
- **API Service**: HTTP health endpoint at `/health`
- **Database Services**: Connection validation
- **Agent Services**: CrewAI agent status checks
- **Ingestion Services**: Processing pipeline status

### 4.2 Logging Strategy
- **Structured JSON Logs**: All services use consistent log format
- **Centralized Logging**: Logs aggregated via volume mounts
- **Log Rotation**: Automatic log rotation and cleanup
- **Real-time Monitoring**: Log streaming for development

### 4.3 Metrics Collection
- **Container Metrics**: CPU, memory, network usage
- **Application Metrics**: Request rates, response times, error rates
- **Business Metrics**: Analysis completion rates, user satisfaction
- **Infrastructure Metrics**: Database performance, queue depths

---

This containerized build specification provides a complete guide for building, deploying, and managing the AI Enablement Platform using Docker and Kubernetes, with comprehensive references to the existing design specifications.
