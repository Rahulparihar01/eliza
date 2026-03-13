"""
Comprehensive Integration Tests for Greenhouse Connector

Tests the full Greenhouse connector integration:
1. API connection testing
2. Job listing
3. Candidate fetching
4. Resume downloading
"""
import pytest
import asyncio
import os
from src.services.ingestion.connectors.greenhouse import GreenhouseConnector


# Skip tests if no API key provided
GH_API_KEY = os.getenv("GREENHOUSE_API_KEY", "ada902b97b18f7131f1784ee99dbb4a5-4")
SKIP_INTEGRATION = not GH_API_KEY


@pytest.mark.skipif(SKIP_INTEGRATION, reason="GREENHOUSE_API_KEY not set")
@pytest.mark.asyncio
async def test_greenhouse_connection():
    """Test Greenhouse API connection."""
    connector = GreenhouseConnector(
        credentials={"api_key": GH_API_KEY},
        sync_config={},
        customer_id="test_customer"
    )
    
    # Test connection
    is_connected = await connector.check()
    assert is_connected is True, "Should connect to Greenhouse API successfully"


@pytest.mark.skipif(SKIP_INTEGRATION, reason="GREENHOUSE_API_KEY not set")
@pytest.mark.asyncio
async def test_greenhouse_fetch_jobs():
    """Test fetching jobs from Greenhouse."""
    connector = GreenhouseConnector(
        credentials={"api_key": GH_API_KEY},
        sync_config={},
        customer_id="test_customer"
    )
    
    # Fetch jobs
    jobs = await connector.get_jobs()
    
    assert isinstance(jobs, list), "Should return a list of jobs"
    assert len(jobs) > 0, "Should have at least one open job"
    
    # Verify job structure
    job = jobs[0]
    assert "id" in job
    assert "name" in job
    assert "status" in job
    assert job["status"] == "open", "Should only return open jobs"
    assert "departments" in job
    assert "offices" in job
    
    print(f"\n✅ Found {len(jobs)} open jobs in Greenhouse")
    print(f"Sample job: {job['name']} (ID: {job['id']})")


@pytest.mark.skipif(SKIP_INTEGRATION, reason="GREENHOUSE_API_KEY not set")
@pytest.mark.asyncio
async def test_greenhouse_fetch_candidates():
    """Test fetching candidates from Greenhouse."""
    connector = GreenhouseConnector(
        credentials={"api_key": GH_API_KEY},
        sync_config={
            "max_candidates": 5  # Limit for testing
        },
        customer_id="test_customer"
    )
    
    # Fetch first page of candidates
    response = await connector.fetch_candidates(page=1, per_page=5)
    
    assert "candidates" in response
    assert "page" in response
    assert isinstance(response["candidates"], list)
    
    candidates = response["candidates"]
    print(f"\n✅ Fetched {len(candidates)} candidates from Greenhouse")
    
    if candidates:
        candidate = candidates[0]
        assert "id" in candidate
        assert "first_name" in candidate or "last_name" in candidate
        print(f"Sample candidate ID: {candidate.get('id')}")


@pytest.mark.skipif(SKIP_INTEGRATION, reason="GREENHOUSE_API_KEY not set")
@pytest.mark.asyncio
async def test_greenhouse_sync_with_filtering():
    """Test full sync with filtering."""
    connector = GreenhouseConnector(
        credentials={"api_key": GH_API_KEY},
        sync_config={
            "application_status": "active",
            "max_candidates": 10
        },
        customer_id="test_customer"
    )
    
    # Run sync
    results = await connector.sync()
    
    assert "candidates_fetched" in results
    assert "resumes_downloaded" in results
    assert "errors" in results
    
    print(f"\n✅ Sync complete:")
    print(f"   Candidates fetched: {results['candidates_fetched']}")
    print(f"   Resumes downloaded: {results['resumes_downloaded']}")
    print(f"   Candidates filtered: {results['candidates_filtered']}")
    print(f"   Errors: {len(results['errors'])}")


@pytest.mark.skipif(SKIP_INTEGRATION, reason="GREENHOUSE_API_KEY not set")
def test_greenhouse_validate_config():
    """Test configuration validation."""
    # Valid config
    connector = GreenhouseConnector(
        credentials={"api_key": GH_API_KEY},
        sync_config={"max_candidates": 100},
        customer_id="test_customer"
    )
    
    result = connector.validate_config()
    assert result["status"] == "valid"
    assert len(result["errors"]) == 0
    
    # Invalid config - max_candidates too high
    connector_invalid = GreenhouseConnector(
        credentials={"api_key": GH_API_KEY},
        sync_config={"max_candidates": 2000},
        customer_id="test_customer"
    )
    
    result_invalid = connector_invalid.validate_config()
    assert result_invalid["status"] == "invalid"
    assert len(result_invalid["errors"]) > 0
    
    print("\n✅ Config validation working correctly")


@pytest.mark.skipif(SKIP_INTEGRATION, reason="GREENHOUSE_API_KEY not set")
def test_greenhouse_discover():
    """Test stream discovery."""
    connector = GreenhouseConnector(
        credentials={"api_key": GH_API_KEY},
        sync_config={},
        customer_id="test_customer"
    )
    
    schema = connector.discover()
    
    assert "streams" in schema
    assert len(schema["streams"]) > 0
    
    stream = schema["streams"][0]
    assert stream["name"] == "candidates"
    assert "json_schema" in stream
    assert "supported_sync_modes" in stream
    
    print("\n✅ Stream discovery working correctly")


if __name__ == "__main__":
    """Run tests directly."""
    print("🧪 Running Greenhouse Connector Integration Tests\n")
    print("=" * 60)
    
    # Run each test
    asyncio.run(test_greenhouse_connection())
    asyncio.run(test_greenhouse_fetch_jobs())
    asyncio.run(test_greenhouse_fetch_candidates())
    asyncio.run(test_greenhouse_sync_with_filtering())
    test_greenhouse_validate_config()
    test_greenhouse_discover()
    
    print("\n" + "=" * 60)
    print("✅ All Greenhouse Integration Tests Passed!")

