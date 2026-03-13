#!/bin/bash
# Run all HR Intelligence feature tests
#
# Tests cover:
# - Email Templates (section-based with AI generation)
# - PDL Caching (30-day TTL)
# - Greenhouse Department Filtering
# - Customer Settings (maildrop address)
# - AI Email Generation

set -e

echo "=========================================="
echo "Running HR Intelligence Feature Tests"
echo "=========================================="

# Navigate to project root
cd "$(dirname "$0")/.."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run tests with verbose output
echo ""
echo "1. Testing Email Templates..."
python -m pytest tests/test_email_templates.py -v --tb=short

echo ""
echo "2. Testing PDL Caching..."
python -m pytest tests/test_pdl_caching.py -v --tb=short

echo ""
echo "3. Testing Greenhouse Departments..."
python -m pytest tests/test_greenhouse_departments.py -v --tb=short

echo ""
echo "4. Testing Customer Settings..."
python -m pytest tests/test_customer_settings.py -v --tb=short

echo ""
echo "5. Testing AI Email Generation..."
python -m pytest tests/test_ai_email_generation.py -v --tb=short

echo ""
echo "=========================================="
echo "All HR Intelligence tests completed!"
echo "=========================================="

# Run all tests together for summary
echo ""
echo "Running full test suite for summary..."
python -m pytest tests/test_email_templates.py tests/test_pdl_caching.py tests/test_greenhouse_departments.py tests/test_customer_settings.py tests/test_ai_email_generation.py -v --tb=short --no-header -q


