#!/bin/bash
# Create insurance_demo_db database and schemas

set -e

echo "🚀 Setting up insurance_demo_db database..."

# Database connection details
DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-user}"
DB_PASSWORD="${DB_PASSWORD:-password}"
DB_NAME="insurance_demo_db"

# Export password for psql
export PGPASSWORD="$DB_PASSWORD"

# Create database
echo "📦 Creating database: $DB_NAME"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres <<EOF
SELECT 'CREATE DATABASE $DB_NAME'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_NAME')\gexec
EOF

# Run DDL scripts
echo "📋 Creating schemas and tables..."

DDL_DIR="design_docs/analytics_insurance/insurance_demo_ddl"

# List of DDL files in order
DDL_FILES=(
    "core_party.sql"
    "core_agent.sql"
    "auto_auto_exposure.sql"
    "auto_policy_auto.sql"
    "auto_claim_auto.sql"
    "auto_claim_transaction.sql"
    "auto_premium_transaction.sql"
    "property_property_exposure.sql"
    "property_policy_property.sql"
    "property_claim_property.sql"
    "property_claim_transaction.sql"
    "property_premium_transaction.sql"
    "analytics_customer_360_view.sql"
)

for ddl_file in "${DDL_FILES[@]}"; do
    ddl_path="$DDL_DIR/$ddl_file"
    if [ -f "$ddl_path" ]; then
        echo "  ✅ Running $ddl_file"
        psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$ddl_path"
    else
        echo "  ⚠️  File not found: $ddl_path"
    fi
done

echo "✅ Insurance demo database setup complete!"
echo "📊 Database: $DB_NAME"
echo "🔗 Connection: postgresql://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$DB_NAME"

