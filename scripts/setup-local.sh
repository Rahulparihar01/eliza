#!/bin/bash
# scripts/setup-local.sh

set -e

echo "🚀 Setting up AI Enablement Platform for local development..."

# Check prerequisites
check_prerequisites() {
    echo "📋 Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo "❌ Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    echo "✅ Prerequisites check passed"
}

# Setup environment file
setup_environment() {
    echo "🔧 Setting up environment..."
    
    if [ ! -f .env ]; then
        echo "Creating .env file from template..."
        cat > .env << EOF
# AI API Keys (Required)
OPENAI_API_KEY=your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-api-key-here
GROQ_API_KEY=your-groq-api-key-here

# Customer Configuration
CUSTOMER_ID=local-dev
CUSTOMER_NAME=Local Development

# Database Configuration
DB_USER=user
DB_PASSWORD=password
DB_NAME=ai_enablement

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=DEBUG
EOF
        echo "⚠️  Please edit .env file and add your API keys"
        echo "   You can get API keys from:"
        echo "   - OpenAI: https://platform.openai.com/api-keys"
        echo "   - Anthropic: https://console.anthropic.com/"
        echo "   - Groq: https://console.groq.com/keys"
        read -p "Press Enter after updating .env file..."
    fi
    
    # Load environment variables
    export $(cat .env | grep -v '^#' | xargs)
    
    echo "✅ Environment setup complete"
}

# Create necessary directories
create_directories() {
    echo "📁 Creating directories..."
    
    mkdir -p {data,logs,cache}/{local-dev,samples}
    mkdir -p config/customers/local-dev
    mkdir -p scripts/postgres
    
    # Copy template configuration for local development
    if [ ! -f config/customers/local-dev/config.yml ]; then
        cp config/customers/customer-template/config.yml config/customers/local-dev/config.yml
        sed -i '' 's/CUSTOMER_ID_PLACEHOLDER/local-dev/g' config/customers/local-dev/config.yml
        sed -i '' 's/Customer Name Placeholder/Local Development/g' config/customers/local-dev/config.yml
    fi
    
    echo "✅ Directories created"
}

# Create PostgreSQL init script
create_postgres_init() {
    echo "📊 Creating PostgreSQL initialization script..."
    
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

-- Insert default data
INSERT INTO customer_configs (customer_id, config_data) 
VALUES ('local-dev', '{"initialized": true}') 
ON CONFLICT (customer_id) DO NOTHING;
EOF
    
    echo "✅ PostgreSQL init script created"
}

# Build and start services
start_services() {
    echo "🐳 Building and starting services..."
    
    # Build the application image
    docker-compose -f docker/docker-compose.yml build
    
    # Start services
    docker-compose -f docker/docker-compose.yml up -d
    
    echo "⏳ Waiting for services to be ready..."
    sleep 30
    
    # Check service health
    if docker-compose -f docker/docker-compose.yml exec app curl -f http://localhost:5001/health > /dev/null 2>&1; then
        echo "✅ Services are healthy"
    else
        echo "⚠️  Services may still be starting up. Check logs with:"
        echo "   docker-compose -f docker/docker-compose.yml logs -f"
    fi
}

# Main execution
main() {
    check_prerequisites
    setup_environment
    create_directories
    create_postgres_init
    start_services
    
    echo ""
    echo "🎉 AI Enablement Platform is ready for local development!"
    echo ""
    echo "🌐 Services available at:"
    echo "  • API: http://localhost:5001"
    echo "  • API Docs: http://localhost:5001/docs"
    echo "  • Neo4j Browser: http://localhost:7474 (neo4j/password)"
    echo ""
    echo "📋 Useful commands:"
    echo "  • View logs: docker-compose -f docker/docker-compose.yml logs -f"
    echo "  • Stop services: docker-compose -f docker/docker-compose.yml down"
    echo "  • Restart services: docker-compose -f docker/docker-compose.yml restart"
    echo ""
    echo "📁 Data directories:"
    echo "  • Application data: ./data/local-dev/"
    echo "  • Logs: ./logs/local-dev/"
    echo "  • Configuration: ./config/customers/local-dev/"
}

main "$@"
