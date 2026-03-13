#!/bin/bash
# scripts/stop-local.sh

set -e

echo "🛑 Stopping AI Enablement Platform local development environment..."

# Stop all services
echo "📦 Stopping Docker services..."
docker-compose -f docker/docker-compose.yml down

# Optional: Remove volumes (uncomment if you want to clean up data)
# echo "🗑️  Removing volumes..."
# docker-compose -f docker/docker-compose.yml down -v

# Optional: Remove images (uncomment if you want to clean up images)
# echo "🗑️  Removing images..."
# docker-compose -f docker/docker-compose.yml down --rmi all

echo "✅ Local development environment stopped"
echo ""
echo "📋 To restart:"
echo "  ./scripts/setup-local.sh"
echo ""
echo "🗑️  To clean up all data (WARNING: This will delete all data):"
echo "  docker-compose -f docker/docker-compose.yml down -v"
