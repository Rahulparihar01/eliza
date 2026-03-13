#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/docker/docker-compose.yml}"

echo "🗄️  Initializing database schema (Alembic migrations)..."
echo "Using compose file: ${COMPOSE_FILE}"

echo "🐳 Ensuring Postgres is running..."
docker-compose -f "$COMPOSE_FILE" up -d postgres

echo "⏳ Waiting for Postgres to accept connections..."
max_retries=30
retry_interval=2

for ((i=1; i<=max_retries; i++)); do
  if docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U user -d ai_enablement >/dev/null 2>&1; then
    echo "✅ Postgres is ready"
    break
  fi

  if [ "$i" -eq "$max_retries" ]; then
    echo "❌ Postgres did not become ready after $((max_retries * retry_interval))s"
    echo "Recent Postgres logs:"
    docker-compose -f "$COMPOSE_FILE" logs --tail=200 postgres || true
    exit 1
  fi

  sleep "$retry_interval"
done

echo "📊 Running Alembic migrations (creates/updates all tables)..."
docker-compose -f "$COMPOSE_FILE" run --rm app alembic upgrade head

echo "✅ Database schema is up to date"


