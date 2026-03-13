"""
Script to capture actual PDL API response format.
Run once to save real API responses for testing.
"""

import json
import requests
import sys

PDL_API_KEY = "5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"
BASE_URL = "https://api.peopledatalabs.com/v5"

def capture_search_response():
    """Capture a real search response with 1 record."""
    print("📡 Calling PDL API to capture real response format...")
    
    response = requests.post(
        f"{BASE_URL}/person/search",
        headers={
            "X-Api-Key": PDL_API_KEY,
            "Content-Type": "application/json"
        },
        json={
            "query": {
                "bool": {
                    "must": [
                        {"term": {"location_country": "united states"}},
                        {"term": {"job_title_role": "engineer"}}
                    ]
                }
            },
            "size": 1  # Just get 1 record to see format
        },
        timeout=30
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✅ Success! Got {len(data.get('data', []))} records")
        print(f"Total available: {data.get('total', 0)}")
        
        # Save to file
        with open("tests/fixtures/pdl_real_response.json", "w") as f:
            json.dump(data, f, indent=2)
        
        print("✅ Saved to tests/fixtures/pdl_real_response.json")
        
        # Show structure
        print("\nResponse structure:")
        print(f"  Keys: {list(data.keys())}")
        if data.get('data'):
            print(f"  First record keys: {list(data['data'][0].keys())}")
        
        return data
    elif response.status_code == 404:
        print("⚠️  No records found (404)")
        data = response.json()
        with open("tests/fixtures/pdl_404_response.json", "w") as f:
            json.dump(data, f, indent=2)
        print("✅ Saved 404 response to tests/fixtures/pdl_404_response.json")
        return data
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return None

if __name__ == "__main__":
    try:
        capture_search_response()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

