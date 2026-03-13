"""
Test PDL API with working API key and various query formats.
"""

import json
import requests

def test_pdl_queries():
    """Test different query formats to find what works."""
    
    API_KEY = "6030715d29045c12f878622cd6c83f9a788ebaaaf7d1e7767f09024cc0147b99"
    PDL_URL = "https://api.peopledatalabs.com/v5/person/search"
    
    headers = {
        'Content-Type': "application/json",
        'X-api-key': API_KEY
    }
    
    print("\n" + "="*70)
    print("PDL API Query Tests with Working Key")
    print("="*70)
    
    # Test 1: Simple job title + location
    print("\n" + "-"*70)
    print("TEST 1: Job title + Location (United States)")
    print("-"*70)
    
    query1 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "software engineer"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query: {json.dumps(query1, indent=2)}")
    
    response1 = requests.post(
        PDL_URL,
        headers=headers,
        json={**query1, "size": 1},
        timeout=10
    )
    
    print(f"\nStatus: {response1.status_code}")
    if response1.status_code == 200:
        data = response1.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0)} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')} - {sample.get('job_title', 'N/A')}")
    else:
        print(f"Response: {response1.text[:200]}")
    
    # Test 2: Just location
    print("\n" + "-"*70)
    print("TEST 2: Location only (United States)")
    print("-"*70)
    
    query2 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query: {json.dumps(query2, indent=2)}")
    
    response2 = requests.post(
        PDL_URL,
        headers=headers,
        json={**query2, "size": 1},
        timeout=10
    )
    
    print(f"\nStatus: {response2.status_code}")
    if response2.status_code == 200:
        data = response2.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0)} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')} - {sample.get('job_title', 'N/A')}")
    else:
        print(f"Response: {response2.text[:200]}")
    
    # Test 3: Skills-based search
    print("\n" + "-"*70)
    print("TEST 3: Skills (Python) + Location")
    print("-"*70)
    
    query3 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"skills": "python"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query: {json.dumps(query3, indent=2)}")
    
    response3 = requests.post(
        PDL_URL,
        headers=headers,
        json={**query3, "size": 1},
        timeout=10
    )
    
    print(f"\nStatus: {response3.status_code}")
    if response3.status_code == 200:
        data = response3.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0)} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')} - {sample.get('job_title', 'N/A')}")
            print(f"  Skills: {sample.get('skills', [])[:5]}")
    else:
        print(f"Response: {response3.text[:200]}")
    
    # Test 4: Company-based search
    print("\n" + "-"*70)
    print("TEST 4: Company name (Google)")
    print("-"*70)
    
    query4 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_company_name": "google"}}
                ]
            }
        }
    }
    
    print(f"Query: {json.dumps(query4, indent=2)}")
    
    response4 = requests.post(
        PDL_URL,
        headers=headers,
        json={**query4, "size": 1},
        timeout=10
    )
    
    print(f"\nStatus: {response4.status_code}")
    if response4.status_code == 200:
        data = response4.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0)} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')} - {sample.get('job_title', 'N/A')}")
            print(f"  Company: {sample.get('job_company_name', 'N/A')}")
    else:
        print(f"Response: {response4.text[:200]}")
    
    print("\n" + "="*70)
    print("Test Complete")
    print("="*70)

if __name__ == "__main__":
    test_pdl_queries()


