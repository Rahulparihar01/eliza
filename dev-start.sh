#!/bin/bash

# =============================================================================
# dev-start.sh - Start backend in Docker, frontend locally for hot reload
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/docker"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Starting Dev Environment (Local Frontend)${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Start core backend Docker services (excluding frontend and optional profiles)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/5] Starting backend Docker services...${NC}"

cd "$DOCKER_DIR"

# Stop frontend container if running (we'll run it locally)
docker compose stop frontend 2>/dev/null || true

# Start the default local stack only; optional Airflow and standalone
# RAG ingestion services remain behind Compose profiles.
# Infrastructure first
echo -e "${GREEN}  → Starting infrastructure (postgres, redis, neo4j, elasticsearch, logstash)...${NC}"
docker compose up -d postgres redis neo4j elasticsearch logstash

# Wait for infrastructure to be healthy
echo -e "${GREEN}  → Waiting for infrastructure health checks...${NC}"
sleep 10

# Start app services
echo -e "${GREEN}  → Starting app services (app, celery-worker, celery-beat, celery-ingestion-worker, flower, kibana)...${NC}"
docker compose up -d app celery-worker celery-beat celery-ingestion-worker flower kibana

echo -e "${GREEN}  ✓ Backend services started${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 2: Wait for app to be ready, then run migrations
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/5] Running database migrations...${NC}"

# Wait for app container to be healthy
echo -e "${GREEN}  → Waiting for app container to be ready...${NC}"
sleep 5

# Check if app is healthy
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec docker-app-1 curl -s http://localhost:5001/health/ready > /dev/null 2>&1; then
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "${YELLOW}  → Waiting for app to be ready... ($RETRY_COUNT/$MAX_RETRIES)${NC}"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}  ✗ App failed to become ready${NC}"
    exit 1
fi

# Run migrations
echo -e "${GREEN}  → Running alembic migrations...${NC}"
if ! docker exec docker-app-1 alembic upgrade head; then
    echo -e "${YELLOW}  ⚠ 'alembic upgrade head' failed. Retrying with all heads...${NC}"
    if ! docker exec docker-app-1 alembic upgrade heads; then
        echo -e "${RED}  ✗ Migration failed. Please resolve migration state before continuing.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}  ✓ Migrations complete${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 3: Initialize tenant if needed
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[3/5] Initializing tenant (if needed)...${NC}"

docker exec docker-app-1 python scripts/init_tenant.py || {
    echo -e "${YELLOW}  ⚠ Tenant may already be initialized${NC}"
}

echo -e "${GREEN}  ✓ Tenant initialization complete${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 4: Check if frontend dependencies are installed
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[4/5] Checking frontend dependencies...${NC}"

cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo -e "${GREEN}  → Installing frontend dependencies (npm install)...${NC}"
    npm install
else
    echo -e "${GREEN}  ✓ Frontend dependencies already installed${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# Step 5: Start frontend with hot reload
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[5/5] Starting frontend with hot reload...${NC}"
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  Backend API:     http://localhost:5001${NC}"
echo -e "${GREEN}  Frontend:        http://localhost:3000${NC}"
echo -e "${GREEN}  Flower:          http://localhost:5555${NC}"
echo -e "${GREEN}  Kibana:          http://localhost:5601${NC}"
echo -e "${GREEN}  Neo4j Browser:   http://localhost:7474${NC}"
echo -e "${GREEN}  Elasticsearch:   http://localhost:9200${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}Optional profiles not started: airflow, rag-ingestion${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the frontend. Backend will continue running.${NC}"
echo -e "${YELLOW}To stop everything: ./dev-stop.sh${NC}"
echo ""

# Check if frontend is already running
if lsof -iTCP:3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    FRONTEND_PID=$(lsof -iTCP:3000 -sTCP:LISTEN -t | head -n 1)
    echo -e "${YELLOW}  ⚠ Port 3000 is already in use (PID: ${FRONTEND_PID}).${NC}"
    echo -e "${GREEN}  ✓ Assuming frontend is already running. Skipping 'npm start'.${NC}"
    exit 0
fi

# Start frontend dev server (this will block and show output)
npm start
