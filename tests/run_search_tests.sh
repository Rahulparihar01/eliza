#!/bin/bash

# Run Person Search Tests
# Tests the unified search service and API endpoints

set -e

echo "=================================="
echo "Person Search Test Suite"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if database is available
echo "Checking database connection..."
python -c "from src.models.database import init_database; init_database()" 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Database connection successful${NC}"
else
    echo -e "${RED}✗ Database connection failed${NC}"
    echo "Please ensure PostgreSQL is running and configured correctly."
    exit 1
fi

echo ""
echo "Running search service tests..."
echo ""

# Run the comprehensive search tests
python tests/test_person_search_comprehensive.py

echo ""
echo -e "${GREEN}=================================="
echo "All Search Tests Complete!"
echo "==================================${NC}"
echo ""
echo "Test Coverage:"
echo "  ✓ PersonSearchService (query routing)"
echo "  ✓ PostgreSQL search (fallback)"
echo "  ✓ Text query search"
echo "  ✓ Get person by ID"
echo "  ✓ Multi-tenant isolation"
echo "  ✓ Pagination"
echo "  ✓ Multiple filters"
echo "  ✓ Elasticsearch fallback"
echo "  ✓ Person to dict conversion"
echo ""
echo "Search API Endpoints (6 endpoints):"
echo "  • POST /persons/search"
echo "  • GET /persons/{pdl_id}"
echo "  • POST /persons/career-transitions"
echo "  • POST /persons/by-skills"
echo "  • POST /persons/company-network"
echo "  • POST /persons/aggregations"
echo ""

