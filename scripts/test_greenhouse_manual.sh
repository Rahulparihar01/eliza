#!/bin/bash
# Manual end-to-end test for Greenhouse Connector

API_BASE="http://localhost:5001"
GH_API_KEY="ada902b97b18f7131f1784ee99dbb4a5-4"

echo "🧪 Greenhouse Connector - End-to-End Test"
echo "=========================================="
echo ""

# Login
echo "📝 Step 1: Login..."
LOGIN_RESPONSE=$(curl -s -X POST "$API_BASE/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "scott@eliza.com",
    "password": "admin123"
  }')

TOKEN=$(echo $LOGIN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "❌ Login failed!"
  echo $LOGIN_RESPONSE | python3 -m json.tool
  exit 1
fi

echo "✅ Logged in successfully"
echo ""

# Test connection
echo "📝 Step 2: Test Greenhouse API connection..."
TEST_RESPONSE=$(curl -s -X POST "$API_BASE/api/connectors/greenhouse/test-connection" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"connector_type\": \"greenhouse\",
    \"credentials\": {\"api_key\": \"$GH_API_KEY\"},
    \"sync_config\": {}
  }")

SUCCESS=$(echo $TEST_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin)['success'])" 2>/dev/null)

if [ "$SUCCESS" = "True" ]; then
  echo "✅ Connection successful!"
else
  echo "❌ Connection failed:"
  echo $TEST_RESPONSE | python3 -m json.tool
  exit 1
fi
echo ""

# Get jobs
echo "📝 Step 3: Fetching Greenhouse jobs..."
JOBS_RESPONSE=$(curl -s -X GET "$API_BASE/api/connectors/greenhouse/jobs?api_key=$GH_API_KEY" \
  -H "Authorization: Bearer $TOKEN")

JOB_COUNT=$(echo $JOBS_RESPONSE | python3 -c "import sys, json; print(len(json.load(sys.stdin)))" 2>/dev/null)

if [ "$JOB_COUNT" -gt "0" ]; then
  echo "✅ Found $JOB_COUNT open jobs"
  echo ""
  echo "Sample jobs:"
  echo $JOBS_RESPONSE | python3 -m json.tool | head -30
else
  echo "❌ No jobs found"
  exit 1
fi
echo ""

echo "=========================================="
echo "✅ All Greenhouse Connector Tests Passed!"
echo ""
echo "Next Steps:"
echo "1. Create a Greenhouse connector configuration via UI or API"
echo "2. Select it in Talent Intelligence analysis"
echo "3. Run an analysis to fetch and score candidate resumes"
echo ""

