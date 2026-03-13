#!/bin/bash
# Helper script to properly rebuild Docker containers
# This ensures code changes are always reflected in containers

set -e  # Exit on error

echo "=========================================="
echo "REBUILDING DOCKER CONTAINERS"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "docker/docker-compose.yml" ]; then
    echo "❌ Error: Must run from project root directory"
    exit 1
fi

# Parse arguments
NO_CACHE=""
SERVICES="app celery-worker"

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --all)
            SERVICES=""
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--no-cache] [--all]"
            echo "  --no-cache: Force complete rebuild (slower but guaranteed fresh)"
            echo "  --all: Rebuild all services (default: only app and celery-worker)"
            exit 1
            ;;
    esac
done

echo "📦 Building containers..."
if [ -n "$NO_CACHE" ]; then
    echo "   (--no-cache enabled: complete rebuild)"
fi
echo ""

# Build containers
docker-compose -f docker/docker-compose.yml build $NO_CACHE $SERVICES

echo ""
echo "✅ Build complete!"
echo ""
echo "🚀 Restarting services..."

# Restart services
docker-compose -f docker/docker-compose.yml up -d $SERVICES

echo ""
echo "⏳ Waiting for health checks..."
sleep 15

# Check status
echo ""
docker-compose -f docker/docker-compose.yml ps | grep -E "app|celery-worker"

echo ""
echo "=========================================="
echo "✅ REBUILD COMPLETE!"
echo "=========================================="
echo ""
echo "Your code changes are now live in the containers."
echo ""
echo "Tip: Use --no-cache if you want to force a complete rebuild"
echo "     (useful after dependency changes in requirements.txt)"
echo ""

