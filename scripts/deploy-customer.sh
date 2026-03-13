#!/bin/bash
# scripts/deploy-customer.sh

set -e

CUSTOMER_ID=$1
CUSTOMER_NAME=$2

if [ -z "$CUSTOMER_ID" ] || [ -z "$CUSTOMER_NAME" ]; then
    echo "Usage: $0 <customer_id> <customer_name>"
    echo "Example: $0 acme-corp 'ACME Corporation'"
    exit 1
fi

echo "🚀 Deploying AI Enablement Platform for customer: $CUSTOMER_NAME ($CUSTOMER_ID)"

# Create customer configuration
create_customer_config() {
    echo "📝 Creating customer configuration..."
    
    CUSTOMER_DIR="config/customers/$CUSTOMER_ID"
    mkdir -p "$CUSTOMER_DIR"
    
    if [ ! -f "$CUSTOMER_DIR/config.yml" ]; then
        # Copy template and customize
        cp config/customers/customer-template/config.yml "$CUSTOMER_DIR/config.yml"
        
        # Replace placeholders
        sed -i "s/CUSTOMER_ID_PLACEHOLDER/$CUSTOMER_ID/g" "$CUSTOMER_DIR/config.yml"
        sed -i "s/Customer Name Placeholder/$CUSTOMER_NAME/g" "$CUSTOMER_DIR/config.yml"
        sed -i "s/CHANGE_THIS_SECRET_KEY/$(openssl rand -hex 32)/g" "$CUSTOMER_DIR/config.yml"
        
        # Update timestamps
        TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        sed -i "s/2024-01-01T00:00:00Z/$TIMESTAMP/g" "$CUSTOMER_DIR/config.yml"
        
        echo "✅ Customer configuration created at $CUSTOMER_DIR/config.yml"
        echo "⚠️  Please review and customize the configuration before proceeding"
        read -p "Press Enter to continue..."
    else
        echo "✅ Customer configuration already exists"
    fi
}

# Create customer environment file
create_customer_env() {
    echo "🔧 Creating customer environment file..."
    
    ENV_FILE=".env.$CUSTOMER_ID"
    
    if [ ! -f "$ENV_FILE" ]; then
        cat > "$ENV_FILE" << EOF
# Customer Configuration
CUSTOMER_ID=$CUSTOMER_ID
CUSTOMER_NAME=$CUSTOMER_NAME
ENVIRONMENT=production

# Port Configuration (adjust if running multiple instances)
APP_PORT=5001
DB_PORT=5432
REDIS_PORT=6379
NEO4J_HTTP_PORT=7474
NEO4J_BOLT_PORT=7687

# Database Configuration
DB_USER=user
DB_PASSWORD=$(openssl rand -hex 16)
DB_NAME=ai_enablement_${CUSTOMER_ID//-/_}

# Neo4j Configuration
NEO4J_USER=neo4j
NEO4J_PASSWORD=$(openssl rand -hex 16)
NEO4J_HEAP_INITIAL=512M
NEO4J_HEAP_MAX=2G

# AI API Keys (REQUIRED - Please update these)
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GROQ_API_KEY=your-groq-api-key-here

# Application Configuration
LOG_LEVEL=INFO
CREWAI_LOG_LEVEL=INFO
EOF
        
        echo "✅ Environment file created: $ENV_FILE"
        echo "⚠️  Please update the API keys in $ENV_FILE"
        read -p "Press Enter after updating API keys..."
    else
        echo "✅ Environment file already exists: $ENV_FILE"
    fi
}

# Create customer directories
create_customer_directories() {
    echo "📁 Creating customer directories..."
    
    mkdir -p "data/$CUSTOMER_ID"/{hr,financial,documents,crm,processed}
    mkdir -p "logs/$CUSTOMER_ID"
    mkdir -p "cache/$CUSTOMER_ID"
    
    echo "✅ Customer directories created"
}

# Create PostgreSQL init script for customer
create_customer_postgres_init() {
    echo "📊 Creating customer PostgreSQL initialization..."
    
    mkdir -p scripts/postgres
    
    cat > scripts/postgres/init.sql << EOF
-- Initialize AI Enablement Platform Database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create basic tables (will be expanded by application migrations)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    customer_id VARCHAR(100) UNIQUE NOT NULL,
    config_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_customer_configs_customer_id ON customer_configs(customer_id);

-- Insert customer-specific data
INSERT INTO customer_configs (customer_id, config_data) 
VALUES ('$CUSTOMER_ID', '{"initialized": true, "customer_name": "$CUSTOMER_NAME"}') 
ON CONFLICT (customer_id) DO NOTHING;
EOF
    
    echo "✅ Customer PostgreSQL init script created"
}

# Deploy customer instance
deploy_instance() {
    echo "🐳 Deploying customer instance..."
    
    # Load customer environment
    export $(cat ".env.$CUSTOMER_ID" | grep -v '^#' | xargs)
    
    # Deploy using customer compose file
    docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$CUSTOMER_ID" up -d
    
    echo "⏳ Waiting for services to be ready..."
    sleep 45
    
    # Health check
    if curl -f "http://localhost:${APP_PORT:-5001}/health" > /dev/null 2>&1; then
        echo "✅ Customer instance is healthy"
    else
        echo "⚠️  Instance may still be starting. Check logs with:"
        echo "   docker-compose -f docker/docker-compose.customer.yml --env-file .env.$CUSTOMER_ID logs -f"
    fi
}

# Main execution
main() {
    create_customer_config
    create_customer_env
    create_customer_directories
    create_customer_postgres_init
    deploy_instance
    
    echo ""
    echo "🎉 Customer instance deployed successfully!"
    echo ""
    echo "🌐 Services for $CUSTOMER_NAME:"
    echo "  • API: http://localhost:${APP_PORT:-5001}"
    echo "  • API Docs: http://localhost:${APP_PORT:-5001}/docs"
    echo "  • Neo4j Browser: http://localhost:${NEO4J_HTTP_PORT:-7474}"
    echo ""
    echo "📋 Management commands:"
    echo "  • View logs: docker-compose -f docker/docker-compose.customer.yml --env-file .env.$CUSTOMER_ID logs -f"
    echo "  • Stop instance: docker-compose -f docker/docker-compose.customer.yml --env-file .env.$CUSTOMER_ID down"
    echo ""
    echo "📁 Customer files:"
    echo "  • Configuration: config/customers/$CUSTOMER_ID/"
    echo "  • Data: data/$CUSTOMER_ID/"
    echo "  • Logs: logs/$CUSTOMER_ID/"
    echo "  • Environment: .env.$CUSTOMER_ID"
}

main "$@"
