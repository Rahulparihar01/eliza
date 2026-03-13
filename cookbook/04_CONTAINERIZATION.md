# Section 4: Containerization and Deployment

## Overview

This section covers containerizing CrewAI applications for production deployment. We'll explore Docker architecture, multi-container setups, environment configuration, and deployment best practices.

## Pattern 1: Multi-Container Architecture

### High-Level Pattern

Separate your application into distinct containers with clear responsibilities:

- **App Container**: Handles HTTP requests and runs migrations
- **Celery Worker Container**: Executes async tasks and flows
- **Celery Beat Container**: Scheduled tasks
- **Infrastructure Containers**: Database, cache, search, etc.

```mermaid
graph TB
    subgraph "Application Layer"
        APP[App Container<br/>FastAPI + Migrations]
        CW[Celery Worker<br/>Flow Execution]
        CB[Celery Beat<br/>Scheduled Tasks]
    end
    
    subgraph "Infrastructure Layer"
        PG[(PostgreSQL)]
        RD[(Redis)]
        ES[(Elasticsearch)]
        N4[(Neo4j)]
    end
    
    APP -->|HTTP| External[External Clients]
    APP -->|Queue| RD
    CW -->|Queue| RD
    CB -->|Queue| RD
    
    APP -->|Read/Write| PG
    CW -->|Read/Write| PG
    
    APP -->|Search| ES
    CW -->|Search| ES
    
    APP -->|Graph| N4
    CW -->|Graph| N4
    
    style APP fill:#90EE90
    style CW fill:#87CEEB
    style CB fill:#DDA0DD
```

### Step-by-Step Tutorial

#### Step 1: Create Dockerfile

```dockerfile
# docker/Dockerfile

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set Python path
ENV PYTHONPATH=/app

# Default command (can be overridden)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5001"]
```

#### Step 2: Create Docker Compose Configuration

```yaml
# docker/docker-compose.yml

version: '3.8'

services:
  # Main Application
  app:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "5001:5001"
    environment:
      # Migration control - only app container runs migrations
      - RUN_MIGRATIONS=true
      
      # Database
      - DATABASE_URL=postgresql://user:password@postgres:5432/ai_enablement
      
      # Celery
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      
      # LLM Configuration
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DEFAULT_LLM_MODEL=gpt-4o-mini
      
      # Application
      - PYTHONPATH=/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - app_data:/app/data
      - app_logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Celery Worker
  celery-worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: celery -A src.celery_app worker --loglevel=info --concurrency=4
    environment:
      # NO RUN_MIGRATIONS - workers don't run migrations
      - RUN_MIGRATIONS=false
      
      # Same environment as app
      - DATABASE_URL=postgresql://user:password@postgres:5432/ai_enablement
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - DEFAULT_LLM_MODEL=gpt-4o-mini
      - PYTHONPATH=/app
    depends_on:
      - postgres
      - redis
      - app
    volumes:
      - app_data:/app/data
      - app_logs:/app/logs

  # Celery Beat (Scheduler)
  celery-beat:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: celery -A src.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/ai_enablement
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - PYTHONPATH=/app
    depends_on:
      - redis
      - app

  # PostgreSQL Database
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=ai_enablement
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache/Queue
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Elasticsearch
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    volumes:
      - es_data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

volumes:
  app_data:
  app_logs:
  postgres_data:
  redis_data:
  es_data:
```

#### Step 3: Migration Management

```python
# src/main.py

import os
from src.models import database

def run_migrations():
    """Run database migrations if enabled"""
    if os.getenv("RUN_MIGRATIONS", "false").lower() == "true":
        from alembic.config import Config
        from alembic import command
        
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("✅ Migrations completed")

if __name__ == "__main__":
    # Initialize database
    database.init_database()
    
    # Run migrations (only in app container)
    run_migrations()
    
    # Start application
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=5001)
```

### Real-World Example: Eliza Platform Docker Setup

```yaml
# docker/docker-compose.yml (excerpt)

services:
  app:
    environment:
      - RUN_MIGRATIONS=true  # ✅ Only app runs migrations
    depends_on:
      postgres:
        condition: service_healthy
  
  celery-worker:
    environment:
      # No RUN_MIGRATIONS - ✅ Workers skip migrations
      - RUN_MIGRATIONS=false
    command: celery -A src.celery_app worker --loglevel=info --concurrency=4
```

### Common Pitfalls

#### Pitfall: Multiple Containers Running Migrations

**Problem:**
```yaml
# ❌ BAD: Both containers run migrations
app:
  environment:
    - RUN_MIGRATIONS=true

celery-worker:
  environment:
    - RUN_MIGRATIONS=true  # Race condition!
```

**Solution:**
```yaml
# ✅ GOOD: Only app container runs migrations
app:
  environment:
    - RUN_MIGRATIONS=true

celery-worker:
  environment:
    - RUN_MIGRATIONS=false  # Skip migrations
```

#### Pitfall: Not Rebuilding After Code Changes

**Problem:**
```bash
# ❌ BAD: Restart uses old image
docker-compose restart celery-worker  # Uses cached image!
```

**Solution:**
```bash
# ✅ GOOD: Rebuild after code changes
docker-compose build celery-worker
docker-compose up -d celery-worker

# Or rebuild all
docker-compose build --no-cache
docker-compose up -d
```

## Pattern 2: Environment Configuration

### High-Level Pattern

Use environment variables for configuration, with validation and defaults.

```mermaid
graph LR
    ENV[Environment Variables] -->|Load| Config[Settings Class]
    Config -->|Validate| App[Application]
    Config -->|Validate| Worker[Worker]
    Config -->|Validate| Flow[Flow]
    
    style ENV fill:#FFE4B5
    style Config fill:#E1F5FF
```

### Step-by-Step Tutorial

#### Step 1: Define Settings Class

```python
# src/core/config.py

from pydantic import BaseSettings, Field
from typing import List, Optional

class Settings(BaseSettings):
    """Application settings with validation"""
    
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # Celery
    celery_broker_url: str = Field(..., env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(..., env="CELERY_RESULT_BACKEND")
    
    # LLM Configuration
    default_llm_model: str = Field(
        default="gpt-4o-mini",
        env="DEFAULT_LLM_MODEL"
    )
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    openai_api_base_url: str = Field(
        default="https://api.openai.com/v1",
        env="OPENAI_API_BASE_URL"
    )
    
    # List-type vars use Union for flexibility
    allowed_origins: List[str] | str = Field(
        default=["*"],
        env="ALLOWED_ORIGINS"
    )
    
    # Migration control
    run_migrations: bool = Field(
        default=False,
        env="RUN_MIGRATIONS"
    )
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

#### Step 2: Handle List-Type Environment Variables

```python
# src/main.py

from src.core.config import get_settings

settings = get_settings()

# Convert string to list if needed
allowed_origins = settings.allowed_origins
if isinstance(allowed_origins, str):
    allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]

# Use in application
app = FastAPI(
    cors={
        "allow_origins": allowed_origins
    }
)
```

#### Step 3: Use Settings in Flows

```python
# src/flows/my_flow.py

from src.core.config import get_settings

settings = get_settings()

class MyFlow(Flow[MyFlowState]):
    def __init__(self):
        super().__init__()
        self.llm = LLM(
            model=settings.default_llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base_url
        )
```

### Real-World Example: Eliza Platform Configuration

```python
# src/core/config.py

class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")
    
    # LLM
    default_llm_model: str = Field(
        default="gpt-4o-mini",
        env="DEFAULT_LLM_MODEL"
    )
    crewai_llm_model: str = Field(
        default="gpt-4o-mini",
        env="CREWAI_LLM_MODEL"
    )
    
    # Flexible list handling
    allowed_origins: List[str] | str = Field(
        default=["*"],
        env="ALLOWED_ORIGINS"
    )
```

### Common Pitfalls

#### Pitfall: Strict List Types Cause Parsing Errors

**Problem:**
```python
# ❌ BAD: Strict List type causes JSON parsing errors
class Settings(BaseSettings):
    allowed_origins: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")

# When .env has: ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5001
# Result: SettingsError: error parsing value for field "allowed_origins"
```

**Solution:**
```python
# ✅ GOOD: Union type accepts both formats
class Settings(BaseSettings):
    allowed_origins: List[str] | str = Field(
        default=["*"],
        env="ALLOWED_ORIGINS"
    )

# Then convert in application code:
allowed_origins = settings.allowed_origins
if isinstance(allowed_origins, str):
    allowed_origins = [origin.strip() for origin in allowed_origins.split(",")]
```

## Pattern 3: Health Checks and Graceful Shutdowns

### High-Level Pattern

Implement health checks for container orchestration and graceful shutdowns for cleanup.

```mermaid
graph LR
    Orchestrator[Orchestrator] -->|Check| Health[Health Endpoint]
    Health -->|200 OK| Healthy[Container Healthy]
    Health -->|503| Unhealthy[Container Unhealthy]
    
    Shutdown[Shutdown Signal] -->|SIGTERM| Graceful[Graceful Shutdown]
    Graceful -->|Cleanup| Close[Close Connections]
    Close -->|Wait| Complete[Shutdown Complete]
    
    style Healthy fill:#90EE90
    style Unhealthy fill:#FFB6C1
```

### Step-by-Step Tutorial

#### Step 1: Create Health Check Endpoints

```python
# src/api/routes/health.py

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/ready")
async def readiness_check():
    """Kubernetes/Docker readiness probe"""
    try:
        # Check database connection
        from src.models import database
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Check Redis connection
        import redis
        r = redis.from_url(settings.celery_broker_url)
        r.ping()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "error": str(e)}
        )

@router.get("/live")
async def liveness_check():
    """Kubernetes/Docker liveness probe"""
    return {"status": "alive"}
```

#### Step 2: Implement Graceful Shutdown

```python
# src/main.py

import signal
import sys
from contextlib import asynccontextmanager

shutdown_event = asyncio.Event()

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    print("Received shutdown signal, shutting down gracefully...")
    shutdown_event.set()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    yield
    
    # Shutdown
    print("Shutting down...")
    # Close database connections
    # Close Redis connections
    # Wait for active tasks to complete
    await shutdown_event.wait()

app = FastAPI(lifespan=lifespan)
```

### Real-World Example: Docker Health Checks

```yaml
# docker/docker-compose.yml

services:
  app:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
  
  celery-worker:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://app:5001/health/ready"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Pattern 4: Volume Management

### High-Level Pattern

Use Docker volumes for persistent data and avoid mounting code in production.

```mermaid
graph TB
    Container[Container] -->|Mount| Volumes[Volumes]
    Volumes -->|Persist| Data[Persistent Data]
    
    subgraph "Volume Types"
        V1[app_data<br/>User uploads]
        V2[app_logs<br/>Application logs]
        V3[app_cache<br/>Cache files]
        V4[postgres_data<br/>Database]
    end
    
    Container --> V1
    Container --> V2
    Container --> V3
    Container --> V4
    
    style Container fill:#E1F5FF
    style Volumes fill:#FFE4B5
```

### Step-by-Step Tutorial

#### Step 1: Define Volumes

```yaml
# docker/docker-compose.yml

services:
  app:
    volumes:
      # Persistent data only - no code mounting for production
      - app_data:/app/data
      - app_logs:/app/logs
      - app_cache:/app/cache
      
      # Development only: mount code for hot reload
      # - ../src:/app/src:ro  # Uncomment for development

volumes:
  app_data:
  app_logs:
  app_cache:
```

#### Step 2: Use Volumes in Application

```python
# src/core/storage.py

import os
from pathlib import Path

# Use environment variable or default
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
LOGS_DIR = Path(os.getenv("LOGS_DIR", "/app/logs"))
CACHE_DIR = Path(os.getenv("CACHE_DIR", "/app/cache"))

# Create directories if they don't exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
```

### Common Pitfalls

#### Pitfall: Mounting Code in Production

**Problem:**
```yaml
# ❌ BAD: Code mounted in production
volumes:
  - ../src:/app/src  # Allows code changes without rebuild
```

**Solution:**
```yaml
# ✅ GOOD: Code baked into image, only data mounted
volumes:
  - app_data:/app/data  # Only persistent data
```

## Summary

Containerization best practices:

1. **Multi-Container Architecture**: Separate app, workers, and infrastructure
2. **Migration Management**: Only app container runs migrations
3. **Environment Configuration**: Use Pydantic Settings with validation
4. **Health Checks**: Implement readiness and liveness probes
5. **Volume Management**: Persistent data only, no code mounting in production

Next, we'll cover scalability strategies.


