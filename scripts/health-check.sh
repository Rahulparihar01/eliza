#!/bin/bash
# scripts/health-check.sh

set -e

CUSTOMER_ID=${1:-"local-dev"}
COMPOSE_FILE="docker/docker-compose.yml"
ENV_FILE=""

# Determine which compose file and env file to use
if [ "$CUSTOMER_ID" != "local-dev" ]; then
    COMPOSE_FILE="docker/docker-compose.customer.yml"
    ENV_FILE=".env.$CUSTOMER_ID"
    
    if [ ! -f "$ENV_FILE" ]; then
        echo "❌ Environment file $ENV_FILE not found"
        exit 1
    fi
fi

echo "🔍 Health Check for: $CUSTOMER_ID"
echo "=================================="
echo ""

# Function to check service health
check_service_health() {
    local service=$1
    local expected_status=$2
    
    echo -n "Checking $service... "
    
    # Get service status
    if [ -n "$ENV_FILE" ]; then
        status=$(docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q "$service" 2>/dev/null)
    else
        status=$(docker-compose -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null)
    fi
    
    if [ -z "$status" ]; then
        echo "❌ Not running"
        return 1
    fi
    
    # Check if container is healthy
    health=$(docker inspect --format='{{.State.Health.Status}}' "$status" 2>/dev/null || echo "unknown")
    
    case $health in
        "healthy")
            echo "✅ Healthy"
            return 0
            ;;
        "unhealthy")
            echo "❌ Unhealthy"
            return 1
            ;;
        "starting")
            echo "⏳ Starting"
            return 1
            ;;
        *)
            # For services without health checks, just check if running
            state=$(docker inspect --format='{{.State.Status}}' "$status" 2>/dev/null || echo "unknown")
            if [ "$state" = "running" ]; then
                echo "✅ Running"
                return 0
            else
                echo "❌ $state"
                return 1
            fi
            ;;
    esac
}

# Function to check API endpoint
check_api_endpoint() {
    local port=${1:-5001}
    local endpoint=${2:-"/health"}
    
    echo -n "Checking API endpoint... "
    
    if curl -f -s "http://localhost:$port$endpoint" > /dev/null 2>&1; then
        echo "✅ Responding"
        return 0
    else
        echo "❌ Not responding"
        return 1
    fi
}

# Function to check database connectivity
check_database_connectivity() {
    echo -n "Checking database connectivity... "
    
    # Get database connection info
    if [ -n "$ENV_FILE" ]; then
        db_container=$(docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q postgres 2>/dev/null)
    else
        db_container=$(docker-compose -f "$COMPOSE_FILE" ps -q postgres 2>/dev/null)
    fi
    
    if [ -z "$db_container" ]; then
        echo "❌ Database container not found"
        return 1
    fi
    
    if docker exec "$db_container" pg_isready > /dev/null 2>&1; then
        echo "✅ Connected"
        return 0
    else
        echo "❌ Connection failed"
        return 1
    fi
}

# Function to check Redis connectivity
check_redis_connectivity() {
    echo -n "Checking Redis connectivity... "
    
    # Get Redis container
    if [ -n "$ENV_FILE" ]; then
        redis_container=$(docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q redis 2>/dev/null)
    else
        redis_container=$(docker-compose -f "$COMPOSE_FILE" ps -q redis 2>/dev/null)
    fi
    
    if [ -z "$redis_container" ]; then
        echo "❌ Redis container not found"
        return 1
    fi
    
    if docker exec "$redis_container" redis-cli ping > /dev/null 2>&1; then
        echo "✅ Connected"
        return 0
    else
        echo "❌ Connection failed"
        return 1
    fi
}

# Function to check Neo4j connectivity
check_neo4j_connectivity() {
    echo -n "Checking Neo4j connectivity... "
    
    # Get Neo4j container
    if [ -n "$ENV_FILE" ]; then
        neo4j_container=$(docker-compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps -q neo4j 2>/dev/null)
    else
        neo4j_container=$(docker-compose -f "$COMPOSE_FILE" ps -q neo4j 2>/dev/null)
    fi
    
    if [ -z "$neo4j_container" ]; then
        echo "❌ Neo4j container not found"
        return 1
    fi
    
    # Get Neo4j credentials
    if [ -n "$ENV_FILE" ]; then
        neo4j_user=$(grep "NEO4J_USER=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 || echo "neo4j")
        neo4j_pass=$(grep "NEO4J_PASSWORD=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 || echo "password")
    else
        neo4j_user="neo4j"
        neo4j_pass="password"
    fi
    
    if docker exec "$neo4j_container" cypher-shell -u "$neo4j_user" -p "$neo4j_pass" "RETURN 1" > /dev/null 2>&1; then
        echo "✅ Connected"
        return 0
    else
        echo "❌ Connection failed"
        return 1
    fi
}

# Main health check
main() {
    local overall_health=0
    
    echo "🔍 Service Health:"
    check_service_health "app" || overall_health=1
    check_service_health "postgres" || overall_health=1
    check_service_health "redis" || overall_health=1
    check_service_health "neo4j" || overall_health=1
    
    echo ""
    echo "🌐 Connectivity:"
    
    # Get API port
    if [ -n "$ENV_FILE" ]; then
        api_port=$(grep "APP_PORT=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 || echo "5001")
    else
        api_port="5001"
    fi
    
    check_api_endpoint "$api_port" "/health" || overall_health=1
    check_database_connectivity || overall_health=1
    check_redis_connectivity || overall_health=1
    check_neo4j_connectivity || overall_health=1
    
    echo ""
    
    if [ $overall_health -eq 0 ]; then
        echo "🎉 Overall Status: ✅ All systems healthy"
        
        echo ""
        echo "🌐 Access URLs:"
        echo "  • API: http://localhost:$api_port"
        echo "  • API Docs: http://localhost:$api_port/docs"
        
        if [ -n "$ENV_FILE" ]; then
            neo4j_port=$(grep "NEO4J_HTTP_PORT=" "$ENV_FILE" 2>/dev/null | cut -d'=' -f2 || echo "7474")
        else
            neo4j_port="7474"
        fi
        echo "  • Neo4j Browser: http://localhost:$neo4j_port"
        
    else
        echo "❌ Overall Status: Some services are unhealthy"
        echo ""
        echo "🔧 Troubleshooting:"
        echo "  • Check logs: docker-compose -f $COMPOSE_FILE $([ -n "$ENV_FILE" ] && echo "--env-file $ENV_FILE") logs -f"
        echo "  • Restart services: docker-compose -f $COMPOSE_FILE $([ -n "$ENV_FILE" ] && echo "--env-file $ENV_FILE") restart"
        echo "  • Check service status: docker-compose -f $COMPOSE_FILE $([ -n "$ENV_FILE" ] && echo "--env-file $ENV_FILE") ps"
        
        exit 1
    fi
}

# Show usage if help requested
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Usage: $0 [customer_id]"
    echo ""
    echo "Examples:"
    echo "  $0                    # Check local development instance"
    echo "  $0 local-dev         # Check local development instance"
    echo "  $0 acme-corp         # Check customer instance"
    echo ""
    exit 0
fi

main "$@"
