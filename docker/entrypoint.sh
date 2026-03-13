#!/bin/bash
set -e

echo "🚀 Starting AI Enablement Platform..."

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
python << END
import sys
import time
import psycopg2
from urllib.parse import urlparse

max_retries = 30
retry_interval = 2

db_url = "$DATABASE_URL"
parsed = urlparse(db_url)

for i in range(max_retries):
    try:
        conn = psycopg2.connect(
            dbname=parsed.path[1:],
            user=parsed.username,
            password=parsed.password,
            host=parsed.hostname,
            port=parsed.port or 5432
        )
        conn.close()
        print("✅ Database is ready!")
        sys.exit(0)
    except psycopg2.OperationalError:
        if i < max_retries - 1:
            print(f"⏳ Database not ready yet, retrying ({i+1}/{max_retries})...")
            time.sleep(retry_interval)
        else:
            print("❌ Database connection failed after maximum retries")
            sys.exit(1)
END

# Run Alembic migrations (only if RUN_MIGRATIONS is set to "true")
if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "📊 Running database migrations..."
    cd /app
    python scripts/run_migrations.py --applets "${APPLETS:-all}" --mode "${MIGRATION_MODE:-selective}"

    if [ $? -eq 0 ]; then
        echo "✅ Database migrations completed successfully"
    else
        echo "❌ Database migrations failed"
        exit 1
    fi
    
    # Run tenant initialization if INIT_TENANT is set to "true"
    if [ "$INIT_TENANT" = "true" ]; then
        echo "🏢 Initializing tenant and admin user..."
        python scripts/init_tenant.py
        
        if [ $? -eq 0 ]; then
            echo "✅ Tenant initialization completed successfully"
        else
            echo "⚠️  Tenant initialization failed (may already exist)"
        fi
    fi
else
    echo "⏭️  Skipping database migrations (RUN_MIGRATIONS not set)"
fi

# Execute the main command
echo "🎯 Starting application: $@"
exec "$@"
