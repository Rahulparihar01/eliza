"""
Test to verify PDL API request format matches their documentation exactly.
Based on: https://docs.peopledatalabs.com/docs/examples-person-search-api
"""

import json
import requests
import os

def test_pdl_exact_format():
    """
    Test using the EXACT format from PDL documentation.
    This will help us verify if our format is correct.
    """
    print("\n" + "="*70)
    print("PDL API Format Verification Test")
    print("Based on: https://docs.peopledatalabs.com/docs/examples-person-search-api")
    print("="*70)
    
    # Get API key from environment
    api_key = os.getenv("PDL_API_KEY")
    if not api_key:
        print("\n⚠️  No PDL_API_KEY environment variable found")
        print("   This test will show the format but cannot call the API")
        api_key = "YOUR_API_KEY_HERE"
        can_call_api = False
    else:
        print(f"\n✓ API key found: {api_key[:20]}...")
        can_call_api = True
    
    # Set the Person Search API URL
    PDL_PERSON_SEARCH_URL = "https://api.peopledatalabs.com/v5/person/search"
    
    print("\n" + "-"*70)
    print("TEST 1: PDL Documentation Format (GET with params)")
    print("-"*70)
    
    # Create an Elasticsearch query EXACTLY as shown in PDL docs
    es_query = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "software engineer"}},
                ]
            }
        }
    }
    
    print("\nElasticsearch Query Structure:")
    print(json.dumps(es_query, indent=2))
    
    # Create parameters EXACTLY as shown in PDL docs
    params = {
        'query': json.dumps(es_query),  # PDL expects JSON string
        'size': 1
    }
    
    print("\nRequest Parameters:")
    print(f"  - query: {params['query'][:100]}...")
    print(f"  - size: {params['size']}")
    
    # Set headers
    headers = {
        'Content-Type': "application/json",
        'X-api-key': api_key
    }
    
    print("\nRequest Headers:")
    print(f"  - Content-Type: {headers['Content-Type']}")
    print(f"  - X-api-key: {api_key[:20]}...")
    
    if can_call_api:
        print("\nMaking GET request to PDL API...")
        try:
            response = requests.get(
                PDL_PERSON_SEARCH_URL,
                headers=headers,
                params=params,
                timeout=10
            )
            
            print(f"\n✓ Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                result_count = len(data.get('data', []))
                total = data.get('total', 0)
                print(f"✓ Results: {result_count} returned, {total} total matches")
                
                if result_count > 0:
                    print("\n✓ SUCCESS: Got results with PDL documentation format!")
                    print(f"  Sample result:")
                    sample = data['data'][0]
                    print(f"    - Name: {sample.get('full_name', 'N/A')}")
                    print(f"    - Title: {sample.get('job_title', 'N/A')}")
                    print(f"    - Company: {sample.get('job_company_name', 'N/A')}")
                else:
                    print("\n⚠️  No results returned (query may be too restrictive or API has limited data)")
            else:
                print(f"\n✗ Error Response:")
                print(f"  Status: {response.status_code}")
                print(f"  Body: {response.text[:500]}")
                
        except Exception as e:
            print(f"\n✗ Error: {type(e).__name__}: {e}")
    else:
        print("\n⚠️  Skipping API call (no API key)")
    
    print("\n" + "-"*70)
    print("TEST 2: Our Current Format (POST with JSON body)")
    print("-"*70)
    
    # Our current format
    our_query = {
        "bool": {
            "must": [
                {"term": {"job_title_role": "software engineer"}},
            ]
        }
    }
    
    print("\nOur Query Structure (inner part only):")
    print(json.dumps(our_query, indent=2))
    
    # Our request body
    our_request_body = {
        "query": our_query,
        "size": 1
    }
    
    print("\nOur Request Body:")
    print(json.dumps(our_request_body, indent=2))
    
    if can_call_api:
        print("\nMaking POST request to PDL API...")
        try:
            response = requests.post(
                PDL_PERSON_SEARCH_URL,
                headers=headers,
                json=our_request_body,
                timeout=10
            )
            
            print(f"\n✓ Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                result_count = len(data.get('data', []))
                total = data.get('total', 0)
                print(f"✓ Results: {result_count} returned, {total} total matches")
                
                if result_count > 0:
                    print("\n✓ SUCCESS: Got results with our format!")
                    print(f"  Sample result:")
                    sample = data['data'][0]
                    print(f"    - Name: {sample.get('full_name', 'N/A')}")
                    print(f"    - Title: {sample.get('job_title', 'N/A')}")
                    print(f"    - Company: {sample.get('job_company_name', 'N/A')}")
                else:
                    print("\n⚠️  No results returned (query may be too restrictive or API has limited data)")
            else:
                print(f"\n✗ Error Response:")
                print(f"  Status: {response.status_code}")
                print(f"  Body: {response.text[:500]}")
                
        except Exception as e:
            print(f"\n✗ Error: {type(e).__name__}: {e}")
    else:
        print("\n⚠️  Skipping API call (no API key)")
    
    print("\n" + "="*70)
    print("Format Comparison Summary")
    print("="*70)
    print("\nPDL Docs Format:")
    print("  Method: GET")
    print("  Params: query (JSON string), size")
    print("  Query: {\"query\": {\"bool\": {\"must\": [...]}}}")
    print("\nOur Format:")
    print("  Method: POST")
    print("  Body: JSON object with query and size")
    print("  Query: {\"bool\": {\"must\": [...]}}")
    print("\n⚠️  POTENTIAL ISSUE: We're missing the outer 'query' wrapper!")
    print("="*70)

if __name__ == "__main__":
    test_pdl_exact_format()


