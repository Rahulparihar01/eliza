# Simple Local Docker Setup for AI Enablement Platform

## Executive Summary

This document provides a simplified Docker setup for local development of the AI Enablement Platform. The approach focuses on simplicity, using API-based AI models (OpenAI, Anthropic, etc.) instead of local inference, and a single application container with standard database services.

**Key Principles:**
- **Simple & Fast**: Get up and running quickly with `docker-compose up`
- **API-Based Models**: No GPU/CPU complexity, use external AI APIs
- **Single App Container**: All application logic in one FastAPI container
- **Standard Databases**: PostgreSQL, Redis, Neo4j in separate containers
- **Development-Focused**: Live code reloading and easy debugging

---

## 1. Quick Start Guide

### Prerequisites
- Docker and Docker Compose installed
- OpenAI API key (or other AI provider keys)
- Git repository cloned

### One-Command Setup
```bash
# Clone and start the platform
git clone <your-repo>
cd ai-enablement-platform
cp .env.example .env
# Edit .env with your API keys
docker-compose up -d
```

---

## 2. Docker Compose Configuration

### 2.1 Main Docker Compose File
```yaml
# docker-compose.yml
version: '3.8'

services:
  # Main Application
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "5001:5001"
    environment:
      # Database connections
      - DATABASE_URL=postgresql://user:password@postgres:5432/ai_enablement
      - REDIS_URL=redis://redis:6379
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      
      # AI API Keys (from .env file)
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      
      # Application settings
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
      - PYTHONPATH=/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      neo4j:
        condition: service_healthy
    volumes:
      # Live code reloading
      - ./src:/app/src
      - ./config:/app/config
      - ./data:/app/data
      # Logs
      - app_logs:/app/logs
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # PostgreSQL Database
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ai_enablement
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user -d ai_enablement"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    restart: unless-stopped

  # Neo4j Knowledge Graph
  neo4j:
    image: neo4j:5.13
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc"]'
    ports:
      - "7474:7474"  # Web interface
      - "7687:7687"  # Bolt protocol
    volumes:
      - neo4j_data:/data
      - ./scripts/neo4j/init.cypher:/var/lib/neo4j/init.cypher
    networks:
      - ai-platform
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "password", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
  neo4j_data:
  app_logs:

networks:
  ai-platform:
    driver: bridge
```

### 2.2 Simple Dockerfile
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Start application
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5001", "--reload"]
```

### 2.3 Environment Configuration
```bash
# .env.example
# Copy to .env and fill in your values

# AI API Keys
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here

# Application Settings
ENVIRONMENT=development
LOG_LEVEL=DEBUG

# Optional: Other AI providers
GROQ_API_KEY=your_groq_key_here
TOGETHER_API_KEY=your_together_key_here
```

---

## 3. Application Structure

### 3.1 Project Directory Structure
```
ai-enablement-platform/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .env
├── src/
│   ├── main.py                 # FastAPI application entry point
│   ├── api/                    # API routes and endpoints
│   ├── agents/                 # CrewAI agents
│   ├── ingestion/              # Data ingestion modules
│   ├── analysis/               # AI analysis modules
│   ├── models/                 # Database models
│   └── utils/                  # Utility functions
├── config/
│   ├── crewai/                 # CrewAI configurations
│   ├── database/               # Database configurations
│   └── logging/                # Logging configurations
├── data/
│   ├── samples/                # Sample data for testing
│   ├── uploads/                # User uploaded files
│   └── processed/              # Processed data
├── scripts/
│   ├── postgres/
│   │   └── init.sql           # Database initialization
│   ├── neo4j/
│   │   └── init.cypher        # Neo4j initialization
│   └── dev/
│       ├── setup.sh           # Development setup script
│       └── reset.sh           # Reset development environment
└── docs/
    └── api/                   # API documentation
```

### 3.2 Main Application Entry Point
```python
# src/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

# Import your modules
from api.routes import router as api_router
from agents.manager import AgentManager
from ingestion.manager import IngestionManager

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AI Enablement Platform",
    description="Enterprise AI enablement analysis platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize managers
agent_manager = AgentManager()
ingestion_manager = IngestionManager()

# Include API routes
app.include_router(api_router, prefix="/v1")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting AI Enablement Platform...")
    
    # Initialize database connections
    # Initialize CrewAI agents
    # Set up data ingestion pipelines
    
    logger.info("Platform started successfully")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, reload=True)
```

---

## 4. Development Workflow

### 4.1 Quick Commands
```bash
# Start everything
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop everything
docker-compose down

# Rebuild and restart
docker-compose up -d --build

# Reset everything (careful - deletes data!)
docker-compose down -v
docker-compose up -d
```

### 4.2 Development Setup Script
```bash
#!/bin/bash
# scripts/dev/setup.sh

set -e

echo "🚀 Setting up AI Enablement Platform for local development..."

# Check prerequisites
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed"
    exit 1
fi

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API keys before continuing"
    exit 1
fi

# Start services
echo "🐳 Starting Docker services..."
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Check health
echo "🔍 Checking service health..."
if curl -f http://localhost:5001/health > /dev/null 2>&1; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
    docker-compose logs app
    exit 1
fi

echo "🎉 Development environment is ready!"
echo ""
echo "🌐 Available services:"
echo "  API: http://localhost:5001"
echo "  API Docs: http://localhost:5001/docs"
echo "  Neo4j Browser: http://localhost:7474 (neo4j/password)"
echo ""
echo "📋 Useful commands:"
echo "  View logs: docker-compose logs -f app"
echo "  Stop services: docker-compose down"
echo "  Restart: docker-compose restart app"
```

### 4.3 Requirements File
```txt
# requirements.txt
# Core framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0

# CrewAI and AI
crewai==0.22.5
crewai-tools==0.4.26
openai==1.3.0
anthropic==0.7.0

# Database
sqlalchemy==2.0.23
alembic==1.12.1
psycopg2-binary==2.9.9
redis==5.0.1
neo4j==5.14.1

# Data processing
pandas==2.1.3
numpy==1.25.2
sentence-transformers==2.2.2
faiss-cpu==1.7.4

# Utilities
python-multipart==0.0.6
aiofiles==23.2.1
python-dotenv==1.0.0
pyjwt==2.8.0

# Development
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.11.0
flake8==6.1.0
```

---

## 5. Database Initialization

### 5.1 PostgreSQL Setup
```sql
-- scripts/postgres/init.sql
-- Initialize AI Enablement Platform database

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Create main tables
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    organization_id UUID REFERENCES organizations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending',
    results JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user_id ON analysis_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_status ON analysis_sessions(status);
```

### 5.2 Neo4j Setup
```cypher
// scripts/neo4j/init.cypher
// Initialize Neo4j constraints and indexes

// Create constraints
CREATE CONSTRAINT employee_id IF NOT EXISTS FOR (e:Employee) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT department_name IF NOT EXISTS FOR (d:Department) REQUIRE d.name IS UNIQUE;
CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE;

// Create indexes
CREATE INDEX employee_email IF NOT EXISTS FOR (e:Employee) ON (e.email);
CREATE INDEX department_type IF NOT EXISTS FOR (d:Department) ON (d.type);
CREATE INDEX skill_category IF NOT EXISTS FOR (s:Skill) ON (s.category);
```

---

## 6. API-Based AI Integration

### 6.1 AI Client Configuration
```python
# src/utils/ai_clients.py
import openai
import anthropic
import os
from typing import Dict, Any, Optional

class AIClientManager:
    """Manage connections to various AI APIs"""
    
    def __init__(self):
        self.openai_client = None
        self.anthropic_client = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize AI API clients"""
        
        # OpenAI
        if os.getenv("OPENAI_API_KEY"):
            self.openai_client = openai.OpenAI(
                api_key=os.getenv("OPENAI_API_KEY")
            )
        
        # Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
    
    async def chat_completion(
        self, 
        messages: list, 
        model: str = "gpt-4",
        provider: str = "openai"
    ) -> Dict[str, Any]:
        """Get chat completion from specified provider"""
        
        if provider == "openai" and self.openai_client:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages
            )
            return {
                "content": response.choices[0].message.content,
                "usage": response.usage.dict() if response.usage else None
            }
        
        elif provider == "anthropic" and self.anthropic_client:
            response = await self.anthropic_client.messages.create(
                model=model,
                messages=messages,
                max_tokens=1024
            )
            return {
                "content": response.content[0].text,
                "usage": response.usage.dict() if hasattr(response, 'usage') else None
            }
        
        else:
            raise ValueError(f"Provider {provider} not available or not configured")

# Global instance
ai_clients = AIClientManager()
```

---

## 7. Monitoring and Debugging

### 7.1 Logging Configuration
```python
# src/utils/logging.py
import logging
import sys
import os
from datetime import datetime

def setup_logging():
    """Configure application logging"""
    
    log_level = os.getenv("LOG_LEVEL", "INFO")
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # File handler
    file_handler = logging.FileHandler(
        f"/app/logs/app_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger
```

### 7.2 Health Check Endpoint
```python
# src/api/health.py
from fastapi import APIRouter
import psycopg2
import redis
import neo4j
import os

router = APIRouter()

@router.get("/health")
async def health_check():
    """Comprehensive health check"""
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {}
    }
    
    # Check PostgreSQL
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        conn.close()
        health_status["services"]["postgresql"] = "healthy"
    except Exception as e:
        health_status["services"]["postgresql"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        r = redis.from_url(os.getenv("REDIS_URL"))
        r.ping()
        health_status["services"]["redis"] = "healthy"
    except Exception as e:
        health_status["services"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check Neo4j
    try:
        driver = neo4j.GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        )
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        health_status["services"]["neo4j"] = "healthy"
    except Exception as e:
        health_status["services"]["neo4j"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    return health_status
```

---

## 8. Next Steps

### 8.1 Getting Started Checklist
- [ ] Install Docker and Docker Compose
- [ ] Clone the repository
- [ ] Copy `.env.example` to `.env` and add API keys
- [ ] Run `./scripts/dev/setup.sh`
- [ ] Access the API at http://localhost:5001/docs
- [ ] Start building your CrewAI agents and data ingestion

### 8.2 Development Workflow
1. **Code Changes**: Edit files in `src/` directory
2. **Live Reload**: FastAPI automatically reloads on changes
3. **Database Changes**: Use Alembic migrations
4. **Testing**: Run tests with `docker-compose exec app pytest`
5. **Debugging**: Use `docker-compose logs -f app` to view logs

### 8.3 When Ready to Scale
- Migrate to Kubernetes using the full `CONTAINERIZED_BUILD_SPECIFICATION.md`
- Add separate containers for different services
- Implement proper CI/CD pipelines
- Add monitoring and alerting

This simplified setup gets you up and running quickly while maintaining the flexibility to scale later!
