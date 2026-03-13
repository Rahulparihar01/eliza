"""
Create a PDL connector for fetching Caylent employees through the API.

This script creates a proper connector configuration that can be used
to sync Caylent employee data from PDL.
"""
import requests
import json

# Configuration
API_BASE_URL = "http://localhost:5001"
EMAIL = "scott@eliza.com"
PASSWORD = "admin123"

PDL_API_KEY = "5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"

# PDL Search Query (simple key-value format - will be converted to Elasticsearch DSL internally)
PDL_QUERY = {
    "search_query": {
        "job_company_name": "Caylent"
    }
}

def main():
    """Create PDL connector via API."""
    print(f"\n{'='*70}")
    print("CREATING CAYLENT PDL CONNECTOR VIA API")
    print(f"{'='*70}\n")
    
    # Step 1: Login
    print("[1/4] Logging in...")
    login_response = requests.post(
        f"{API_BASE_URL}/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD}
    )
    
    if login_response.status_code != 200:
        print(f"   ❌ Login failed: {login_response.text}")
        return
    
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"   ✅ Logged in as {EMAIL}")
    
    # Step 2: Check if connector already exists
    print("\n[2/4] Checking for existing connector...")
    list_response = requests.get(
        f"{API_BASE_URL}/api/connectors/configurations",
        headers=headers
    )
    
    if list_response.status_code == 200:
        connectors = list_response.json().get("connectors", [])
        existing = next((c for c in connectors if c.get("connector_name") == "Caylent Employees"), None)
        
        if existing:
            print(f"   ⚠️  Connector already exists: {existing.get('connector_id')}")
            print(f"   Deleting existing connector...")
            
            delete_response = requests.delete(
                f"{API_BASE_URL}/api/connectors/configurations/{existing['connector_id']}",
                headers=headers
            )
            
            if delete_response.status_code in [200, 204]:
                print(f"   ✅ Deleted existing connector")
            else:
                print(f"   ⚠️  Could not delete: {delete_response.text}")
    
    # Step 3: Test connection
    print("\n[3/4] Testing PDL connection...")
    test_response = requests.post(
        f"{API_BASE_URL}/api/connectors/test-connection",
        headers=headers,
        json={
            "connector_type": "people_data_labs",
            "credentials": {
                "api_key": PDL_API_KEY
            }
        }
    )
    
    if test_response.status_code != 200:
        print(f"   ❌ Connection test failed: {test_response.text}")
        return
    
    test_result = test_response.json()
    print(f"   ✅ Connection test passed: {test_result.get('message')}")
    
    # Step 4: Estimate cost
    print("\n[4/4] Estimating cost...")
    estimate_response = requests.post(
        f"{API_BASE_URL}/api/connectors/estimate-cost",
        headers=headers,
        json={
            "connector_type": "people_data_labs",
            "credentials": {
                "api_key": PDL_API_KEY
            },
            "sync_config": PDL_QUERY
        }
    )
    
    if estimate_response.status_code == 200:
        estimate = estimate_response.json()
        estimated_records = estimate.get("estimated_records", 0)
        estimated_cost = estimate.get("estimated_cost") or 0
        
        print(f"   📊 Estimated records: {estimated_records}")
        print(f"   💰 Estimated cost: ${estimated_cost:.2f}")
        
        if estimated_records == 0:
            print("\n   ⚠️  No records found with this query!")
            print("   This might mean:")
            print("   - The company name 'Caylent' doesn't exist in PDL")
            print("   - The query format is incorrect")
            print("   - The API key doesn't have access to this data")
            
            response = input("\n   Continue anyway? [y/N]: ")
            if response.lower() != 'y':
                print("   ❌ Aborted")
                return
        elif estimated_records > 100:
            response = input(f"\n   ⚠️  This will cost ${estimated_cost:.2f}. Continue? [y/N]: ")
            if response.lower() != 'y':
                print("   ❌ Aborted")
                return
    else:
        print(f"   ⚠️  Could not estimate cost: {estimate_response.text}")
        response = input("\n   Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            print("   ❌ Aborted")
            return
    
    # Step 5: Create connector
    print("\n[5/5] Creating connector...")
    create_response = requests.post(
        f"{API_BASE_URL}/api/connectors/configurations",
        headers=headers,
        json={
            "connector_name": "Caylent Employees",
            "connector_type": "people_data_labs",
            "credentials": {
                "api_key": PDL_API_KEY
            },
            "sync_config": PDL_QUERY,
            "sync_mode": "full_refresh",
            "description": "PDL connector for fetching all Caylent employees"
        }
    )
    
    if create_response.status_code not in [200, 201]:
        print(f"   ❌ Failed to create connector: {create_response.text}")
        return
    
    connector = create_response.json()
    connector_id = connector.get("connector_id")
    
    print(f"   ✅ Connector created successfully!")
    print(f"   Connector ID: {connector_id}")
    print(f"   Name: {connector.get('connector_name')}")
    print(f"   Type: {connector.get('connector_type')}")
    print(f"   Status: {'Enabled' if connector.get('is_enabled') else 'Disabled'}")
    
    # Step 6: Trigger initial sync
    print("\n[6/6] Triggering initial sync...")
    sync_response = requests.post(
        f"{API_BASE_URL}/api/connectors/configurations/{connector_id}/trigger-sync",
        headers=headers
    )
    
    if sync_response.status_code in [200, 202]:
        sync_result = sync_response.json()
        print(f"   ✅ Sync triggered!")
        print(f"   Sync ID: {sync_result.get('sync_id')}")
        print(f"   Status: {sync_result.get('status')}")
        print(f"\n   Monitor sync progress in the Data Connections page")
    else:
        print(f"   ⚠️  Could not trigger sync: {sync_response.text}")
    
    print(f"\n{'='*70}")
    print("✅ CAYLENT PDL CONNECTOR CREATED!")
    print(f"{'='*70}\n")
    print(f"Connector ID: {connector_id}")
    print(f"View in UI: http://localhost:3000/data-connections")
    print()


if __name__ == '__main__':
    main()

