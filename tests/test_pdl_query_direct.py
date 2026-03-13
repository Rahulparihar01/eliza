#!/usr/bin/env python3
"""
Direct PDL Query Test Script

Tests the PDL query builder and API without running the full analysis pipeline.
Skips the diagnostic agent and uses a mock diagnostic to test PDL queries directly.
"""

import asyncio
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import database
from src.services.talent.pdl_query_builder import PDLQueryBuilder, PDLQueryParams
from src.services.ingestion.connector_service import ConnectorService
from src.services.ingestion.connectors.people_data_labs import PeopleDataLabsConnector


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


async def test_pdl_query_builder():
    """Test the PDL query builder with manual parameters."""
    print_section("Testing PDL Query Builder")
    
    # Initialize
    query_builder = PDLQueryBuilder()
    
    # Create a PDLQueryParams directly (bypassing diagnostic)
    pdl_query = PDLQueryParams(
        version=1,
        job_title="machine learning engineer",
        job_title_role=["engineering"],
        required_skills=["python", "machine learning", "tensorflow"],
        optional_skills=["pytorch", "aws", "kubernetes"],
        min_years_experience=3,
        max_years_experience=10,
        limit=5
    )
    
    print(f"✅ PDL Query Created!")
    print(f"   Version: {pdl_query.version}")
    print(f"   Job Title: {pdl_query.job_title}")
    print(f"   Job Title Roles: {pdl_query.job_title_role}")
    print(f"   Required Skills: {pdl_query.required_skills}")
    print(f"   Optional Skills: {pdl_query.optional_skills}")
    print(f"   Min Experience: {pdl_query.min_years_experience}")
    print(f"   Max Experience: {pdl_query.max_years_experience}")
    print(f"   Limit: {pdl_query.limit}")
    
    # Convert to API payload
    print("\nConverting to PDL API payload...")
    api_payload = query_builder.convert_to_pdl_api_payload(pdl_query)
    
    print(f"\n✅ API Payload Created!")
    print(f"   Query: {api_payload.get('query', '')[:300]}...")
    print(f"   Size: {api_payload.get('size', 'N/A')}")
    
    return pdl_query, api_payload


async def test_pdl_api_call(pdl_query: PDLQueryParams):
    """Actually call the PDL API to verify the query works."""
    print_section("Testing PDL API Call")
    
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        connector_service = ConnectorService(db)
        
        # Find existing PDL connector
        pdl_connectors = connector_service.list_configurations(
            customer_id='eliza',
            connector_type='people_data_labs',
            is_enabled=True
        )
        
        if not pdl_connectors:
            print("❌ No enabled PDL connector found!")
            print("   Please configure a PDL connector with API credentials.")
            return None
        
        print(f"✅ Found PDL connector: {pdl_connectors[0].connector_name}")
        
        # Get credentials
        api_credentials = connector_service.get_credentials(pdl_connectors[0])
        
        if not api_credentials or 'api_key' not in api_credentials:
            print("❌ No API key found in PDL connector!")
            return None
        
        print(f"✅ API key found (length: {len(api_credentials.get('api_key', ''))})")
        
        # Build simple query that matches our orchestrator logic
        simple_query = {}
        
        # Add job_title for specific role matching
        if pdl_query.job_title:
            simple_query["job_title"] = [pdl_query.job_title.lower()]
        
        # Add skills (limit to 5 max)
        all_skills = (pdl_query.required_skills + pdl_query.optional_skills)[:5]
        if all_skills:
            simple_query["skills"] = [s.lower() for s in all_skills]
        
        # Add location
        simple_query["location_country"] = ["united states"]
        
        print(f"\n📋 Query to send to PDL:")
        print(json.dumps(simple_query, indent=2))
        
        # Initialize PDL connector
        pdl_connector = PeopleDataLabsConnector(
            credentials=api_credentials,
            config={
                "search_query": simple_query,
                "max_records": 5,
                "page_size": 5
            },
            customer_id='eliza'
        )
        
        print("\n🔍 Calling PDL API...")
        
        # Read results
        results = []
        for batch in pdl_connector.read_stream("full", {}):
            results.extend(batch)
            if len(results) >= 5:
                results = results[:5]
                break
        
        print(f"\n✅ PDL API Response: {len(results)} candidates found!")
        
        if results:
            print("\n📊 Sample Candidates:")
            for i, person in enumerate(results[:5], 1):
                print(f"\n   Candidate {i}:")
                print(f"      Name: {person.get('full_name', 'N/A')}")
                print(f"      Title: {person.get('job_title', 'N/A')}")
                print(f"      Company: {person.get('job_company_name', 'N/A')}")
                print(f"      Location: {person.get('location_name', 'N/A')}")
                print(f"      Experience: {person.get('inferred_years_experience', 'N/A')} years")
                skills = person.get('skills', [])[:8]
                print(f"      Skills: {', '.join(skills) if skills else 'N/A'}")
                linkedin = person.get('linkedin_url', 'N/A')
                print(f"      LinkedIn: {linkedin}")
        else:
            print("\n⚠️  No candidates found! Let's try a simpler query...")
            return await test_simple_pdl_query(api_credentials)
        
        return results
        
    finally:
        db.close()


async def test_simple_pdl_query(api_credentials: dict):
    """Try a very simple PDL query to verify the API is working."""
    print_section("Testing Simple PDL Query (Fallback)")
    
    # Very simple query - just looking for ML engineers in the US
    simple_query = {
        "job_title": ["machine learning engineer"],
        "location_country": ["united states"]
    }
    
    print(f"📋 Simple query:")
    print(json.dumps(simple_query, indent=2))
    
    pdl_connector = PeopleDataLabsConnector(
        credentials=api_credentials,
        config={
            "search_query": simple_query,
            "max_records": 5,
            "page_size": 5
        },
        customer_id='eliza'
    )
    
    print("\n🔍 Calling PDL API with simple query...")
    
    results = []
    for batch in pdl_connector.read_stream("full", {}):
        results.extend(batch)
        if len(results) >= 5:
            results = results[:5]
            break
    
    print(f"\n✅ PDL API Response: {len(results)} candidates found!")
    
    if results:
        print("\n📊 Sample Candidates:")
        for i, person in enumerate(results[:3], 1):
            print(f"\n   Candidate {i}:")
            print(f"      Name: {person.get('full_name', 'N/A')}")
            print(f"      Title: {person.get('job_title', 'N/A')}")
            print(f"      Company: {person.get('job_company_name', 'N/A')}")
    
    return results


async def main():
    print("\n" + "="*60)
    print("  PDL Query Pipeline Test (Fast)")
    print("="*60)
    
    try:
        # Test 1: PDL Query Builder
        pdl_query, api_payload = await test_pdl_query_builder()
        
        # Test 2: Actual PDL API Call
        results = await test_pdl_api_call(pdl_query)
        
        # Summary
        print_section("Test Summary")
        print("✅ PDL Query Builder: Working")
        if results and len(results) > 0:
            print(f"✅ PDL API Call: Working ({len(results)} candidates found)")
        else:
            print("⚠️  PDL API Call: No candidates returned")
        
        print("\n🎉 Pipeline test complete!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
