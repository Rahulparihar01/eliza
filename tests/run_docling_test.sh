#!/bin/bash
#
# Run Docling Parsing Test inside Docker container
#
# Usage:
#   ./tests/run_docling_test.sh [resume_file]
#
# If no resume file specified, uses first PDF in tests/resumes/

set -e

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Get container name
CONTAINER=$(docker-compose ps -q app 2>/dev/null | head -1)

if [ -z "$CONTAINER" ]; then
    echo "❌ App container not found. Is it running?"
    echo "Start it with: docker-compose up -d app"
    exit 1
fi

echo "✓ Found app container: $(docker ps --filter id=$CONTAINER --format '{{.Names}}')"
echo ""

# Build command
if [ -n "$1" ]; then
    # Use specified resume file
    CMD="python3 tests/test_docling_parsing_isolated.py $1"
    echo "Parsing resume: $1"
else:
    # Use first resume in tests/resumes/
    CMD="python3 tests/test_docling_parsing_isolated.py"
    echo "Parsing first resume in tests/resumes/"
fi

echo ""
echo "Running Docling parsing test..."
echo "================================================"

# Run test inside container
docker exec -it $CONTAINER $CMD

echo ""
echo "================================================"
echo "✓ Test complete"
echo ""
echo "Output files are in the container. To retrieve them:"
echo "  docker cp \$(docker-compose ps -q app):/app/full_markdown_output.txt ."
echo "  docker cp \$(docker-compose ps -q app):/app/docling_full_output.json ."
echo "  docker cp \$(docker-compose ps -q app):/app/parsed_resume_pdl_format.json ."

