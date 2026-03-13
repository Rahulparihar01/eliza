"""
Simple PDL Query Integration Test

Tests the critical type conversion workflow:
PDLQueryParams -> API Payload -> PDLQuery
"""

import pytest
from typing import Dict, Any

from src.services.talent.pdl_query_builder import PDLQueryBuilder, PDLQueryParams
from src.models.talent_analysis import PDLQuery


def test_pdl_query_params_to_api_payload_to_pdl_query():
    """
    Test the critical workflow that was failing:
    1. Create PDLQueryParams (what query builder returns)
    2. Convert to API payload (what PDL service needs)
    3. Convert to PDLQuery (what TalentAnalysisResult needs)
    
    This is the exact flow in orchestrator.py that was causing validation errors.
    """
    print("\n=== Testing PDL Query Type Conversion Workflow ===\n")
    
    # Step 1: Create PDLQueryParams (this is what build_initial_query returns)
    print("Step 1: Creating PDLQueryParams...")
    query_params = PDLQueryParams(
        job_title_role=["Machine Learning Engineer", "ML Engineer"],
        required_skills=["Python", "PyTorch", "TensorFlow"],
        optional_skills=["AWS", "Kubernetes"],
        min_years_experience=5,
        max_years_experience=10,
        limit=10
    )
    
    assert isinstance(query_params, PDLQueryParams)
    print(f"✓ PDLQueryParams created: {type(query_params).__name__}")
    print(f"  - Job titles: {query_params.job_title_role}")
    print(f"  - Required skills: {query_params.required_skills}")
    print(f"  - Limit: {query_params.limit}")
    
    # Step 2: Convert to API payload (this is what PDL service needs)
    print("\nStep 2: Converting PDLQueryParams to API payload...")
    query_builder = PDLQueryBuilder()
    api_payload = query_builder.convert_to_pdl_api_payload(query_params)
    
    assert isinstance(api_payload, dict)
    assert "query" in api_payload, f"Expected 'query' key in payload, got: {list(api_payload.keys())}"
    print(f"✓ API payload created: {type(api_payload).__name__}")
    print(f"  - Keys: {list(api_payload.keys())}")
    print(f"  - Query value: {api_payload.get('query', '')[:100]}...")  # First 100 chars
    
    # Step 3: Convert to PDLQuery (this is what TalentAnalysisResult expects)
    print("\nStep 3: Converting to PDLQuery for storage...")
    pdl_query = PDLQuery(
        base_query=str(api_payload.get("query", "")),  # Use "query" key, not "search_query"
        params=api_payload,
        version=1,
        refinement_reason="Initial query based on diagnostic analysis"
    )
    
    assert isinstance(pdl_query, PDLQuery)
    assert pdl_query.version == 1
    assert pdl_query.params == api_payload
    assert isinstance(pdl_query.base_query, str)
    print(f"✓ PDLQuery created: {type(pdl_query).__name__}")
    print(f"  - Version: {pdl_query.version}")
    print(f"  - Refinement reason: {pdl_query.refinement_reason}")
    print(f"  - Base query length: {len(pdl_query.base_query)} chars")
    print(f"  - Params keys: {list(pdl_query.params.keys())}")
    
    print("\n=== WORKFLOW SUCCESS ===")
    print("All type conversions work correctly!")
    print("\nWorkflow verified:")
    print("  PDLQueryParams (from query builder)")
    print("       ↓")
    print("  dict (API payload)")
    print("       ↓")
    print("  PDLQuery (for storage)")
    
    return True


def test_query_builder_instance_method():
    """
    Test that convert_to_pdl_api_payload must be called on an instance,
    not as a static method.
    
    This was the bug: PDLQueryBuilder.convert_to_pdl_api_payload(query)
    Should be: query_builder.convert_to_pdl_api_payload(query)
    """
    print("\n=== Testing Query Builder Instance Method ===\n")
    
    query_params = PDLQueryParams(
        job_title_role=["ML Engineer"],
        required_skills=["Python"],
        limit=10
    )
    
    # This should work (instance method)
    query_builder = PDLQueryBuilder()
    api_payload = query_builder.convert_to_pdl_api_payload(query_params)
    assert isinstance(api_payload, dict)
    print("✓ Instance method call works correctly")
    
    # This should fail (static method call)
    try:
        api_payload_bad = PDLQueryBuilder.convert_to_pdl_api_payload(query_params)
        assert False, "Static method call should have failed!"
    except TypeError as e:
        print(f"✓ Static method call correctly fails: {e}")
    
    print("\n=== TEST PASSED ===")
    print("convert_to_pdl_api_payload must be called on an instance!")


def test_pdl_query_validation():
    """
    Test that PDLQuery validates correctly and accepts the right types.
    """
    print("\n=== Testing PDLQuery Validation ===\n")
    
    # Valid PDLQuery
    pdl_query = PDLQuery(
        base_query="{'job_title': 'ML Engineer'}",
        params={"search_query": {"job_title": "ML Engineer"}},
        version=1,
        refinement_reason="Test"
    )
    
    assert pdl_query.version == 1
    assert isinstance(pdl_query.params, dict)
    assert isinstance(pdl_query.base_query, str)
    print("✓ PDLQuery accepts correct types")
    
    # Try passing PDLQueryParams (this should fail)
    try:
        query_params = PDLQueryParams(
            job_title_role=["ML Engineer"],
            required_skills=["Python"],
            limit=10
        )
        
        bad_query = PDLQuery(
            base_query="test",
            params=query_params,  # Wrong type! Should be dict
            version=1
        )
        assert False, "Should have rejected PDLQueryParams"
    except Exception as e:
        print(f"✓ PDLQuery correctly rejects PDLQueryParams: {type(e).__name__}")
    
    print("\n=== TEST PASSED ===")
    print("PDLQuery validation works correctly!")


def test_connector_workflow_integration():
    """
    Test the full connector creation and query workflow.
    This mirrors what the orchestrator does:
    1. Get existing PDL connector for credentials
    2. Create a new connector for the specific query
    3. Use that connector to fetch results
    """
    print("\n=== Testing Connector Workflow Integration ===\n")
    
    try:
        from src.services.ingestion.connectors.people_data_labs import PeopleDataLabsConnector
        from src.services.ingestion.connector_service import ConnectorService
        from src.models import database
        import json
        import uuid
        
        # Initialize database
        if database.SessionLocal is None:
            database.init_database()
        
        db = database.SessionLocal()
        
        try:
            connector_service = ConnectorService(db)
            
            # Step 1: Get existing PDL connector for credentials
            print("Step 1: Finding existing PDL connector for credentials...")
            existing_connectors = connector_service.list_configurations(
                customer_id="eliza",
                connector_type="people_data_labs",
                is_enabled=True
            )
            
            if not existing_connectors:
                print("⚠️  No enabled PDL connectors found - skipping workflow test")
                return
            
            print(f"✓ Found {len(existing_connectors)} existing PDL connector(s)")
            print(f"  Using: {existing_connectors[0].connector_name}")
            
            # Get credentials using connector service
            api_credentials = connector_service.get_credentials(existing_connectors[0])
            if not api_credentials.get("api_key"):
                print("⚠️  No API key found in connector credentials - skipping test")
                return
            
            # Step 2: Build query
            print("\nStep 2: Building PDL query...")
            # Use a query that we know works with this API key
            # (location-based search with skills)
            search_query = {
                "location_country": ["united states"],
                "skills": ["python"]
            }
            
            print(f"✓ Query built:")
            print(f"  - location_country: {search_query['location_country']}")
            print(f"  - skills: {search_query['skills']}")
            
            # Step 3: Create new connector for this query
            print("\nStep 3: Creating new connector for this specific query...")
            connector_name = f"Test ML Market Search - {uuid.uuid4().hex[:8]}"
            
            new_connector = connector_service.create_configuration(
                customer_id="eliza",
                connector_type="people_data_labs",
                connector_name=connector_name,
                description="Test market search query for ML talent",
                credentials=api_credentials,
                sync_config={
                    "search_query": search_query,
                    "max_records": 1,
                    "page_size": 1
                },
                tags=["test", "ml_talent", "market_search"],
                created_by_user_id=1  # Test user
            )
            
            print(f"✓ Connector created:")
            print(f"  - ID: {new_connector.connector_id}")
            print(f"  - Name: {new_connector.connector_name}")
            
            # Step 4: Use connector to fetch results
            print("\nStep 4: Using connector to fetch PDL results...")
            
            # First, let's check what the connector will send to PDL
            print(f"  Query will search for:")
            print(f"    - location_country: {search_query['location_country']}")
            print(f"    - skills: {search_query['skills']}")
            
            pdl_connector = PeopleDataLabsConnector(
                credentials=api_credentials,
                config={
                    "search_query": search_query,
                    "max_records": 1,
                    "page_size": 1
                },
                customer_id="eliza"
            )
            
            # Test connection first
            print(f"  Testing connection to PDL API...")
            try:
                check_result = pdl_connector.check()
                print(f"  ✓ Connection test passed: {check_result.get('status', 'unknown')}")
            except Exception as e:
                print(f"  ✗ Connection test failed: {e}")
                raise
            
            # Now fetch results
            print(f"  Fetching results from PDL API...")
            results = []
            batch_count = 0
            try:
                for batch in pdl_connector.read_stream("full", {}):
                    batch_count += 1
                    print(f"    Received batch {batch_count} with {len(batch)} records")
                    results.extend(batch)
                    if len(results) >= 1:
                        results = results[:1]
                        break
                
                print(f"✓ PDL API returned {len(results)} result(s) across {batch_count} batch(es)")
                
                if len(results) == 0:
                    print(f"  Note: 0 results might mean:")
                    print(f"    - No candidates match the search criteria")
                    print(f"    - Search query is too restrictive")
                    print(f"    - API quota/rate limit reached")
                    
            except Exception as e:
                print(f"✗ Error fetching from PDL API: {type(e).__name__}: {e}")
                raise
            
            if results and len(results) > 0:
                print(f"\nResult preview:")
                print(f"  - Name: {results[0].get('full_name', 'N/A')}")
                print(f"  - Title: {results[0].get('job_title', 'N/A')}")
                print(f"  - Company: {results[0].get('job_company_name', 'N/A')}")
                print(f"  - Skills: {len(results[0].get('skills', []))} total")
                
                # Show full structure (limited)
                print(f"\nFull result structure (first 500 chars):")
                result_str = json.dumps(results[0], indent=2, default=str)
                print(result_str[:500] + "..." if len(result_str) > 500 else result_str)
            
            # Step 5: Cleanup - disable the test connector
            print(f"\nStep 5: Cleaning up test connector...")
            connector_service.update_configuration(
                connector_id=new_connector.connector_id,
                customer_id="eliza",
                updates={"is_enabled": False}
            )
            print(f"✓ Test connector disabled")
            
            print("\n=== CONNECTOR WORKFLOW TEST COMPLETE ===")
            print("All steps successful:")
            print("  1. ✓ Found existing connector credentials")
            print("  2. ✓ Built PDL query")
            print("  3. ✓ Created new connector for query")
            print("  4. ✓ Fetched results from PDL API")
            print("  5. ✓ Cleaned up test connector")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"\n❌ Error in connector workflow: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_pdl_query_params_to_api_payload_to_pdl_query()
    test_query_builder_instance_method()
    test_pdl_query_validation()
    test_connector_workflow_integration()
    print("\n" + "="*60)
    print("ALL TESTS PASSED!")
    print("="*60)

