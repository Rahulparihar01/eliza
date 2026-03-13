"""
Test using the EXACT format from PDL documentation example.
"""

import json
import requests

def test_pdl_exact_example():
    """Test with exact PDL example format."""
    
    API_KEY = "6030715d29045c12f878622cd6c83f9a788ebaaaf7d1e7767f09024cc0147b99"
    PDL_URL = "https://api.peopledatalabs.com/v5/person/search"
    
    headers = {
        'Content-Type': "application/json",
        'X-api-key': API_KEY
    }
    
    print("\n" + "="*70)
    print("PDL Exact Example Format Test")
    print("="*70)
    
    # Test 1: Exact example from PDL docs (modified for our key)
    print("\n" + "-"*70)
    print("TEST 1: PDL Example - Engineering role")
    print("-"*70)
    
    query1 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "engineering"}},  # Note: lowercase "engineering"
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
        print(f"Response: {response1.text[:300]}")
    
    # Test 2: Try "software engineer" as job_title_role
    print("\n" + "-"*70)
    print("TEST 2: Job title role = 'software engineer'")
    print("-"*70)
    
    query2 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "software engineer"}},  # With space
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
        print(f"Response: {response2.text[:300]}")
    
    # Test 3: Use job_title instead
    print("\n" + "-"*70)
    print("TEST 3: Use job_title field (partial match)")
    print("-"*70)
    
    query3 = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"job_title": "software engineer"}},  # match allows partial
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
    else:
        print(f"Response: {response3.text[:300]}")
    
    # Test 4: Wildcard in job_title_role
    print("\n" + "-"*70)
    print("TEST 4: Job title role with wildcard")
    print("-"*70)
    
    query4 = {
        "query": {
            "bool": {
                "must": [
                    {"wildcard": {"job_title_role": "*engineer*"}},
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
            print(f"  Job title role: {sample.get('job_title_role', 'N/A')}")
    else:
        print(f"Response: {response4.text[:300]}")
    
    # Test 5: Check what job_title_role values exist
    print("\n" + "-"*70)
    print("TEST 5: Sample person to see job_title_role format")
    print("-"*70)
    
    query5 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"location_country": "united states"}},
                    {"term": {"skills": "python"}},
                ]
            }
        }
    }
    
    response5 = requests.post(
        PDL_URL,
        headers=headers,
        json={**query5, "size": 1},
        timeout=10
    )
    
    if response5.status_code == 200:
        data = response5.json()
        if data.get('data'):
            sample = data['data'][0]
            print(f"Sample Person:")
            print(f"  Name: {sample.get('full_name', 'N/A')}")
            print(f"  job_title: {sample.get('job_title', 'N/A')}")
            print(f"  job_title_role: {sample.get('job_title_role', 'N/A')}")
            print(f"  job_title_sub_role: {sample.get('job_title_sub_role', 'N/A')}")
            print(f"  job_title_levels: {sample.get('job_title_levels', 'N/A')}")
    
    print("\n" + "="*70)

if __name__ == "__main__":
    test_pdl_exact_example()


