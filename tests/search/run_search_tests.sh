#!/bin/bash
# Run search infrastructure tests

set -e

echo "🔍 Running Search Infrastructure Tests"
echo "========================================"
echo ""

# Set PYTHONPATH
export PYTHONPATH=/Users/scottgay/Documents/Eliza/eliza-platform:$PYTHONPATH

# Run tests with coverage
pytest tests/search/test_search_infrastructure.py \
    -v \
    --tb=short \
    --color=yes \
    --durations=10 \
    -m "not performance" \
    -W ignore::DeprecationWarning

echo ""
echo "✅ Search Infrastructure Tests Complete"
echo ""

# Run performance tests separately if requested
if [ "$1" = "--performance" ]; then
    echo "⚡ Running Performance Tests"
    echo "=============================="
    pytest tests/search/test_search_infrastructure.py \
        -v \
        -m "performance" \
        --tb=short \
        --color=yes
    echo ""
    echo "✅ Performance Tests Complete"
fi

