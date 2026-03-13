#!/bin/bash
# scripts/list-customers.sh

set -e

echo "👥 AI Enablement Platform - Customer Instances"
echo "=============================================="
echo ""

# Check if any customer configurations exist
if [ ! -d "config/customers" ] || [ -z "$(ls -A config/customers 2>/dev/null)" ]; then
    echo "No customer instances found."
    echo ""
    echo "To create a customer instance:"
    echo "  ./scripts/deploy-customer.sh <customer-id> '<Customer Name>'"
    exit 0
fi

# List all customer directories
for customer_dir in config/customers/*/; do
    if [ -d "$customer_dir" ]; then
        customer_id=$(basename "$customer_dir")
        
        # Skip template directory
        if [ "$customer_id" = "customer-template" ]; then
            continue
        fi
        
        echo "📋 Customer: $customer_id"
        
        # Check if config file exists
        if [ -f "$customer_dir/config.yml" ]; then
            # Extract customer name from config
            customer_name=$(grep "customer_name:" "$customer_dir/config.yml" | sed 's/customer_name: *"\?\([^"]*\)"\?/\1/' | tr -d '"')
            echo "   Name: $customer_name"
            
            # Check if environment file exists
            if [ -f ".env.$customer_id" ]; then
                echo "   Environment: ✅ .env.$customer_id"
                
                # Check if services are running
                if docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$customer_id" ps -q > /dev/null 2>&1; then
                    running_services=$(docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$customer_id" ps --services --filter "status=running" 2>/dev/null | wc -l)
                    total_services=$(docker-compose -f docker/docker-compose.customer.yml --env-file ".env.$customer_id" ps --services 2>/dev/null | wc -l)
                    
                    if [ "$running_services" -gt 0 ]; then
                        echo "   Status: 🟢 Running ($running_services/$total_services services)"
                        
                        # Get port information
                        app_port=$(grep "APP_PORT=" ".env.$customer_id" 2>/dev/null | cut -d'=' -f2 || echo "5001")
                        neo4j_port=$(grep "NEO4J_HTTP_PORT=" ".env.$customer_id" 2>/dev/null | cut -d'=' -f2 || echo "7474")
                        
                        echo "   URLs:"
                        echo "     • API: http://localhost:$app_port"
                        echo "     • API Docs: http://localhost:$app_port/docs"
                        echo "     • Neo4j: http://localhost:$neo4j_port"
                    else
                        echo "   Status: 🔴 Stopped"
                    fi
                else
                    echo "   Status: 🔴 Not deployed"
                fi
            else
                echo "   Environment: ❌ Missing .env.$customer_id"
                echo "   Status: 🔴 Not configured"
            fi
            
            # Check data directories
            if [ -d "data/$customer_id" ]; then
                data_size=$(du -sh "data/$customer_id" 2>/dev/null | cut -f1 || echo "0B")
                echo "   Data: 📁 $data_size"
            else
                echo "   Data: 📁 No data"
            fi
            
            # Check for recent backups
            if [ -d "backups/$customer_id" ]; then
                latest_backup=$(ls -t "backups/$customer_id"/*.tar.gz 2>/dev/null | head -1)
                if [ ! -z "$latest_backup" ]; then
                    backup_date=$(basename "$latest_backup" .tar.gz | sed 's/_/ /')
                    echo "   Backup: 💾 Latest: $backup_date"
                else
                    echo "   Backup: 💾 No backups"
                fi
            else
                echo "   Backup: 💾 No backups"
            fi
        else
            echo "   Status: ❌ Invalid configuration"
        fi
        
        echo ""
    fi
done

echo "📋 Management Commands:"
echo "  • Deploy new customer: ./scripts/deploy-customer.sh <id> '<name>'"
echo "  • View customer logs: docker-compose -f docker/docker-compose.customer.yml --env-file .env.<id> logs -f"
echo "  • Stop customer: docker-compose -f docker/docker-compose.customer.yml --env-file .env.<id> down"
echo "  • Backup customer: ./scripts/backup-customer.sh <id>"
echo ""
