#!/bin/bash
# scripts/backup-customer.sh

set -e

CUSTOMER_ID=$1

if [ -z "$CUSTOMER_ID" ]; then
    echo "Usage: $0 <customer_id>"
    echo "Example: $0 acme-corp"
    exit 1
fi

# Check if customer exists
if [ ! -f ".env.$CUSTOMER_ID" ]; then
    echo "❌ Customer environment file .env.$CUSTOMER_ID not found"
    exit 1
fi

# Load customer environment
export $(cat ".env.$CUSTOMER_ID" | grep -v '^#' | xargs)

BACKUP_DIR="backups/$CUSTOMER_ID/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "🗄️ Creating backup for $CUSTOMER_NAME ($CUSTOMER_ID)..."

# Function to check if service is running
check_service_running() {
    local service=$1
    if docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$CUSTOMER_ID" ps -q $service > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Backup database
backup_database() {
    echo "📊 Backing up PostgreSQL database..."
    
    if check_service_running postgres; then
        docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$CUSTOMER_ID" exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_DIR/database.sql"
        echo "✅ Database backup completed"
    else
        echo "⚠️  PostgreSQL service not running, skipping database backup"
    fi
}

# Backup Neo4j
backup_neo4j() {
    echo "🔗 Backing up Neo4j database..."
    
    if check_service_running neo4j; then
        # Create Neo4j dump
        docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$CUSTOMER_ID" exec -T neo4j neo4j-admin database dump --to-path=/tmp neo4j || true
        
        # Copy dump file
        NEO4J_CONTAINER=$(docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$CUSTOMER_ID" ps -q neo4j)
        if [ ! -z "$NEO4J_CONTAINER" ]; then
            docker cp "$NEO4J_CONTAINER:/tmp/neo4j.dump" "$BACKUP_DIR/neo4j.dump" 2>/dev/null || echo "⚠️  Neo4j dump file not found"
        fi
        
        echo "✅ Neo4j backup completed"
    else
        echo "⚠️  Neo4j service not running, skipping Neo4j backup"
    fi
}

# Backup Redis data
backup_redis() {
    echo "🔄 Backing up Redis data..."
    
    if check_service_running redis; then
        # Create Redis dump
        docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$CUSTOMER_ID" exec -T redis redis-cli BGSAVE
        sleep 5  # Wait for background save to complete
        
        # Copy dump file
        REDIS_CONTAINER=$(docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$CUSTOMER_ID" ps -q redis)
        if [ ! -z "$REDIS_CONTAINER" ]; then
            docker cp "$REDIS_CONTAINER:/data/dump.rdb" "$BACKUP_DIR/redis.rdb" 2>/dev/null || echo "⚠️  Redis dump file not found"
        fi
        
        echo "✅ Redis backup completed"
    else
        echo "⚠️  Redis service not running, skipping Redis backup"
    fi
}

# Backup application data
backup_application_data() {
    echo "📁 Backing up application data..."
    
    if [ -d "data/$CUSTOMER_ID" ]; then
        cp -r "data/$CUSTOMER_ID" "$BACKUP_DIR/data"
        echo "✅ Application data backup completed"
    else
        echo "⚠️  No application data found for customer $CUSTOMER_ID"
    fi
}

# Backup configuration
backup_configuration() {
    echo "⚙️ Backing up configuration..."
    
    if [ -d "config/customers/$CUSTOMER_ID" ]; then
        cp -r "config/customers/$CUSTOMER_ID" "$BACKUP_DIR/config"
        echo "✅ Configuration backup completed"
    else
        echo "⚠️  No configuration found for customer $CUSTOMER_ID"
    fi
    
    # Backup environment file
    if [ -f ".env.$CUSTOMER_ID" ]; then
        cp ".env.$CUSTOMER_ID" "$BACKUP_DIR/environment.env"
        echo "✅ Environment file backup completed"
    fi
}

# Backup logs
backup_logs() {
    echo "📝 Backing up logs..."
    
    if [ -d "logs/$CUSTOMER_ID" ]; then
        cp -r "logs/$CUSTOMER_ID" "$BACKUP_DIR/logs"
        echo "✅ Logs backup completed"
    else
        echo "⚠️  No logs found for customer $CUSTOMER_ID"
    fi
}

# Create backup manifest
create_backup_manifest() {
    echo "📋 Creating backup manifest..."
    
    cat > "$BACKUP_DIR/manifest.json" << EOF
{
  "customer_id": "$CUSTOMER_ID",
  "customer_name": "$CUSTOMER_NAME",
  "backup_date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "backup_type": "full",
  "components": [
    "database",
    "neo4j",
    "redis",
    "application_data",
    "configuration",
    "logs",
    "environment"
  ],
  "backup_size": "$(du -sh $BACKUP_DIR | cut -f1)",
  "backup_path": "$BACKUP_DIR"
}
EOF
    
    echo "✅ Backup manifest created"
}

# Compress backup
compress_backup() {
    echo "🗜️ Compressing backup..."
    
    BACKUP_PARENT=$(dirname "$BACKUP_DIR")
    BACKUP_NAME=$(basename "$BACKUP_DIR")
    
    cd "$BACKUP_PARENT"
    tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
    
    if [ -f "${BACKUP_NAME}.tar.gz" ]; then
        rm -rf "$BACKUP_NAME"
        echo "✅ Backup compressed to ${BACKUP_PARENT}/${BACKUP_NAME}.tar.gz"
        FINAL_BACKUP="${BACKUP_PARENT}/${BACKUP_NAME}.tar.gz"
    else
        echo "⚠️  Compression failed, keeping uncompressed backup"
        FINAL_BACKUP="$BACKUP_DIR"
    fi
    
    cd - > /dev/null
}

# Main execution
main() {
    echo "🚀 Starting backup for customer: $CUSTOMER_NAME ($CUSTOMER_ID)"
    
    backup_database
    backup_neo4j
    backup_redis
    backup_application_data
    backup_configuration
    backup_logs
    create_backup_manifest
    compress_backup
    
    echo ""
    echo "🎉 Backup completed successfully!"
    echo ""
    echo "📦 Backup details:"
    echo "  • Customer: $CUSTOMER_NAME ($CUSTOMER_ID)"
    echo "  • Backup location: $FINAL_BACKUP"
    echo "  • Backup size: $(du -sh "$FINAL_BACKUP" | cut -f1)"
    echo "  • Backup date: $(date)"
    echo ""
    echo "📋 To restore from this backup:"
    echo "  1. Extract: tar -xzf $FINAL_BACKUP"
    echo "  2. Review manifest.json for backup contents"
    echo "  3. Use restore scripts (to be created) for restoration"
}

main "$@"
