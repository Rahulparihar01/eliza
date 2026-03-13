#!/bin/bash

# =============================================================================
# dev-stop.sh - Stop all services (Docker backend + local frontend)
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="$SCRIPT_DIR/docker"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Stopping All Services${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Stop local frontend (if running on port 3000)
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[1/2] Stopping local frontend...${NC}"

FRONTEND_PID=$(lsof -ti:3000 2>/dev/null)
if [ -n "$FRONTEND_PID" ]; then
    echo -e "${GREEN}  → Killing frontend process (PID: $FRONTEND_PID)...${NC}"
    kill -9 $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}  ✓ Frontend stopped${NC}"
else
    echo -e "${GREEN}  ✓ No frontend process running on port 3000${NC}"
fi
echo ""

# -----------------------------------------------------------------------------
# Step 2: Stop all Docker containers
# -----------------------------------------------------------------------------
echo -e "${YELLOW}[2/2] Stopping Docker containers...${NC}"

cd "$DOCKER_DIR"
docker compose down

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  ✓ All services stopped${NC}"
echo -e "${GREEN}============================================${NC}"
