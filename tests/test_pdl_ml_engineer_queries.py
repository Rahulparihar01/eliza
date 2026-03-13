"""
Test various query formats for finding Machine Learning Engineers.
"""

import json
import requests

def test_ml_engineer_queries():
    """Test different query combinations for ML engineer search."""
    
    API_KEY = "6030715d29045c12f878622cd6c83f9a788ebaaaf7d1e7767f09024cc0147b99"
    PDL_URL = "https://api.peopledatalabs.com/v5/person/search"
    
    headers = {
        'Content-Type': "application/json",
        'X-api-key': API_KEY
    }
    
    print("\n" + "="*70)
    print("ML Engineer Query Tests")
    print("="*70)
    
    # Test 1: Standardized role + ML skills
    print("\n" + "-"*70)
    print("TEST 1: job_title_role='engineering' + ML skills")
    print("-"*70)
    
    query1 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "engineering"}},
                    {"term": {"skills": "machine learning"}},
                    {"term": {"skills": "python"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query fields:")
    print(f"  - job_title_role: engineering")
    print(f"  - skills: machine learning, python")
    print(f"  - location: united states")
    
    response1 = requests.post(PDL_URL, headers=headers, json={**query1, "size": 1}, timeout=10)
    
    print(f"\nStatus: {response1.status_code}")
    if response1.status_code == 200:
        data = response1.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0):,} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')}")
            print(f"  Title: {sample.get('job_title', 'N/A')}")
            print(f"  Company: {sample.get('job_company_name', 'N/A')}")
            print(f"  Skills: {sample.get('skills', [])[:7]}")
    else:
        print(f"Response: {response1.text[:300]}")
    
    # Test 2: job_title with "machine learning engineer" (match query)
    print("\n" + "-"*70)
    print("TEST 2: job_title contains 'machine learning engineer'")
    print("-"*70)
    
    query2 = {
        "query": {
            "bool": {
                "must": [
                    {"match": {"job_title": "machine learning engineer"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query fields:")
    print(f"  - job_title (match): 'machine learning engineer'")
    print(f"  - location: united states")
    
    response2 = requests.post(PDL_URL, headers=headers, json={**query2, "size": 1}, timeout=10)
    
    print(f"\nStatus: {response2.status_code}")
    if response2.status_code == 200:
        data = response2.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0):,} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')}")
            print(f"  Title: {sample.get('job_title', 'N/A')}")
            print(f"  Company: {sample.get('job_company_name', 'N/A')}")
            print(f"  Role: {sample.get('job_title_role', 'N/A')}")
    else:
        print(f"Response: {response2.text[:300]}")
    
    # Test 3: Combine role + job_title match + skills
    print("\n" + "-"*70)
    print("TEST 3: Combined - role + title + skills")
    print("-"*70)
    
    query3 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "engineering"}},
                    {"match": {"job_title": "machine learning"}},
                    {"term": {"skills": "tensorflow"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query fields:")
    print(f"  - job_title_role: engineering")
    print(f"  - job_title (match): 'machine learning'")
    print(f"  - skills: tensorflow")
    print(f"  - location: united states")
    
    response3 = requests.post(PDL_URL, headers=headers, json={**query3, "size": 1}, timeout=10)
    
    print(f"\nStatus: {response3.status_code}")
    if response3.status_code == 200:
        data = response3.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0):,} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')}")
            print(f"  Title: {sample.get('job_title', 'N/A')}")
            print(f"  Company: {sample.get('job_company_name', 'N/A')}")
            print(f"  Skills: {sample.get('skills', [])[:7]}")
    else:
        print(f"Response: {response3.text[:300]}")
    
    # Test 4: Multiple ML skills (should clause for OR logic)
    print("\n" + "-"*70)
    print("TEST 4: Multiple ML frameworks (TensorFlow OR PyTorch)")
    print("-"*70)
    
    query4 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "engineering"}},
                    {"match": {"job_title": "machine learning"}},
                    {"term": {"location_country": "united states"}}
                ],
                "should": [
                    {"term": {"skills": "tensorflow"}},
                    {"term": {"skills": "pytorch"}},
                    {"term": {"skills": "scikit-learn"}}
                ],
                "minimum_should_match": 1
            }
        }
    }
    
    print(f"Query fields:")
    print(f"  - job_title_role: engineering")
    print(f"  - job_title (match): 'machine learning'")
    print(f"  - skills (any of): tensorflow, pytorch, scikit-learn")
    print(f"  - location: united states")
    
    response4 = requests.post(PDL_URL, headers=headers, json={**query4, "size": 1}, timeout=10)
    
    print(f"\nStatus: {response4.status_code}")
    if response4.status_code == 200:
        data = response4.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0):,} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')}")
            print(f"  Title: {sample.get('job_title', 'N/A')}")
            print(f"  Company: {sample.get('job_company_name', 'N/A')}")
            print(f"  Skills: {sample.get('skills', [])[:10]}")
    else:
        print(f"Response: {response4.text[:300]}")
    
    # Test 5: Senior level ML engineers
    print("\n" + "-"*70)
    print("TEST 5: Senior ML engineers (with job_title_levels)")
    print("-"*70)
    
    query5 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "engineering"}},
                    {"match": {"job_title": "machine learning"}},
                    {"terms": {"job_title_levels": ["senior", "lead", "principal"]}},
                    {"term": {"skills": "python"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query fields:")
    print(f"  - job_title_role: engineering")
    print(f"  - job_title (match): 'machine learning'")
    print(f"  - job_title_levels: senior, lead, principal")
    print(f"  - skills: python")
    print(f"  - location: united states")
    
    response5 = requests.post(PDL_URL, headers=headers, json={**query5, "size": 1}, timeout=10)
    
    print(f"\nStatus: {response5.status_code}")
    if response5.status_code == 200:
        data = response5.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0):,} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')}")
            print(f"  Title: {sample.get('job_title', 'N/A')}")
            print(f"  Levels: {sample.get('job_title_levels', 'N/A')}")
            print(f"  Company: {sample.get('job_company_name', 'N/A')}")
            print(f"  Skills: {sample.get('skills', [])[:7]}")
    else:
        print(f"Response: {response5.text[:300]}")
    
    # Test 6: Just "machine learning" as a skill
    print("\n" + "-"*70)
    print("TEST 6: Engineering role + 'machine learning' as skill")
    print("-"*70)
    
    query6 = {
        "query": {
            "bool": {
                "must": [
                    {"term": {"job_title_role": "engineering"}},
                    {"term": {"skills": "machine learning"}},
                    {"term": {"location_country": "united states"}}
                ]
            }
        }
    }
    
    print(f"Query fields:")
    print(f"  - job_title_role: engineering")
    print(f"  - skills: 'machine learning'")
    print(f"  - location: united states")
    
    response6 = requests.post(PDL_URL, headers=headers, json={**query6, "size": 1}, timeout=10)
    
    print(f"\nStatus: {response6.status_code}")
    if response6.status_code == 200:
        data = response6.json()
        print(f"✓ Results: {len(data.get('data', []))} returned, {data.get('total', 0):,} total")
        if data.get('data'):
            sample = data['data'][0]
            print(f"  Sample: {sample.get('full_name', 'N/A')}")
            print(f"  Title: {sample.get('job_title', 'N/A')}")
            print(f"  Company: {sample.get('job_company_name', 'N/A')}")
            print(f"  Skills (first 10): {sample.get('skills', [])[:10]}")
    else:
        print(f"Response: {response6.text[:300]}")
    
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    print("\nBest query patterns for ML Engineer search:")
    print("1. Broad: job_title_role='engineering' + skill='machine learning'")
    print("2. Specific: job_title (match) 'machine learning engineer'")
    print("3. Precise: role + title + multiple ML framework skills")
    print("4. Targeted: Add seniority levels for senior positions")
    print("="*70)

if __name__ == "__main__":
    test_ml_engineer_queries()


