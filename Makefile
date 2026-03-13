# AI Enablement Platform - Makefile
# Convenience commands for development and deployment

.PHONY: help setup start stop restart logs health clean deploy-customer list-customers backup-customer
.PHONY: db-init db-migrate

# Default target
help:
	@echo "AI Enablement Platform - Available Commands"
	@echo "==========================================="
	@echo ""
	@echo "Development:"
	@echo "  make setup           - Set up local development environment"
	@echo "  make start           - Start local development services"
	@echo "  make stop            - Stop local development services"
	@echo "  make restart         - Restart local development services"
	@echo "  make logs            - View logs from all services"
	@echo "  make health          - Check health of all services"
	@echo "  make clean           - Clean up containers and volumes"
	@echo ""
	@echo "Customer Management:"
	@echo "  make deploy-customer ID=<id> NAME='<name>' - Deploy customer instance"
	@echo "  make list-customers  - List all customer instances"
	@echo "  make backup-customer ID=<id>               - Backup customer data"
	@echo ""
	@echo "Examples:"
	@echo "  make deploy-customer ID=acme-corp NAME='ACME Corporation'"
	@echo "  make backup-customer ID=acme-corp"
	@echo ""

# Development commands
setup:
	@echo "🚀 Setting up local development environment..."
	@./scripts/setup-local.sh

start:
	@echo "▶️  Starting local development services..."
	@docker-compose -f docker/docker-compose.yml up -d
	@echo "✅ Services started. Run 'make health' to check status."

stop:
	@echo "⏹️  Stopping local development services..."
	@./scripts/stop-local.sh

restart:
	@echo "🔄 Restarting local development services..."
	@docker-compose -f docker/docker-compose.yml restart
	@echo "✅ Services restarted."

logs:
	@echo "📋 Viewing logs from all services..."
	@docker-compose -f docker/docker-compose.yml logs -f

health:
	@echo "🔍 Checking service health..."
	@./scripts/health-check.sh

clean:
	@echo "🧹 Cleaning up containers and volumes..."
	@docker-compose -f docker/docker-compose.yml down -v --remove-orphans
	@docker system prune -f
	@echo "✅ Cleanup completed."

# Customer management commands
deploy-customer:
	@if [ -z "$(ID)" ] || [ -z "$(NAME)" ]; then \
		echo "❌ Error: ID and NAME are required"; \
		echo "Usage: make deploy-customer ID=<customer-id> NAME='<Customer Name>'"; \
		echo "Example: make deploy-customer ID=acme-corp NAME='ACME Corporation'"; \
		exit 1; \
	fi
	@echo "🚀 Deploying customer instance: $(NAME) ($(ID))"
	@./scripts/deploy-customer.sh "$(ID)" "$(NAME)"

list-customers:
	@./scripts/list-customers.sh

backup-customer:
	@if [ -z "$(ID)" ]; then \
		echo "❌ Error: ID is required"; \
		echo "Usage: make backup-customer ID=<customer-id>"; \
		echo "Example: make backup-customer ID=acme-corp"; \
		exit 1; \
	fi
	@echo "💾 Backing up customer: $(ID)"
	@./scripts/backup-customer.sh "$(ID)"

# Build commands
build:
	@echo "🔨 Building application image..."
	@docker-compose -f docker/docker-compose.yml build

rebuild:
	@echo "🔨 Rebuilding application image (no cache)..."
	@docker-compose -f docker/docker-compose.yml build --no-cache

# Database commands
db-shell:
	@echo "🗄️  Opening database shell..."
	@docker-compose -f docker/docker-compose.yml exec postgres psql -U user -d ai_enablement

db-init:
	@echo "🗄️  Creating/updating database tables via Alembic..."
	@./scripts/init-db.sh

db-migrate: db-init

redis-cli:
	@echo "🔄 Opening Redis CLI..."
	@docker-compose -f docker/docker-compose.yml exec redis redis-cli

neo4j-shell:
	@echo "🔗 Opening Neo4j shell..."
	@docker-compose -f docker/docker-compose.yml exec neo4j cypher-shell -u neo4j -p password

# Development utilities
shell:
	@echo "🐚 Opening application shell..."
	@docker-compose -f docker/docker-compose.yml exec app bash

test:
	@echo "🧪 Running tests..."
	@docker-compose -f docker/docker-compose.yml exec app python -m pytest

format:
	@echo "🎨 Formatting code..."
	@docker-compose -f docker/docker-compose.yml exec app black src/
	@docker-compose -f docker/docker-compose.yml exec app isort src/

lint:
	@echo "🔍 Linting code..."
	@docker-compose -f docker/docker-compose.yml exec app flake8 src/
	@docker-compose -f docker/docker-compose.yml exec app mypy src/
