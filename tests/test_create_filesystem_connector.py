"""
Test script to create filesystem connector via API.

This ensures all proper validation, testing, and setup happens.
"""
import requests
import json

# Configuration
API_BASE = "http://localhost:5001"
EMAIL = "scott@eliza.com"
PASSWORD = "admin123"

def main():
    # 1. Login to get token
    print("1. Logging in...")
    login_response = requests.post(
        f"{API_BASE}/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD}
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(login_response.text)
        return
    
    token = login_response.json()["access_token"]
    print(f"✅ Login successful")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # 2. Create connector configuration
    print("\n2. Creating filesystem connector...")
    connector_data = {
        "connector_type": "filesystem",
        "connector_name": "ML Engineer Resumes (Local)",
        "description": "Local filesystem connector for test ML Engineer resumes - 50 PDFs",
        "credentials": {},  # No credentials needed for local filesystem
        "sync_config": {
            "directory_path": "/app/tests/resumes",
            "file_extensions": [".pdf"],
            "recursive": False
        },
        "tags": ["ml-engineer", "test-resumes", "local"],
        "sync_schedule": None
    }
    
    create_response = requests.post(
        f"{API_BASE}/api/connectors/configurations",
        headers=headers,
        json=connector_data
    )
    
    if create_response.status_code not in [200, 201]:
        print(f"❌ Connector creation failed: {create_response.status_code}")
        print(create_response.text)
        return
    
    connector = create_response.json()
    print(f"✅ Connector created successfully!")
    print(f"   Connector ID: {connector['connector_id']}")
    print(f"   Name: {connector['connector_name']}")
    print(f"   Type: {connector['connector_type']}")
    print(f"   Enabled: {connector['is_enabled']}")
    print(f"   Healthy: {connector.get('is_healthy', 'N/A')}")
    
    # 3. List connectors to verify
    print("\n3. Verifying connector in list...")
    list_response = requests.get(
        f"{API_BASE}/api/connectors/configurations",
        headers=headers
    )
    
    if list_response.status_code == 200:
        connectors = list_response.json()["connectors"]
        print(f"✅ Total connectors: {len(connectors)}")
        for conn in connectors:
            print(f"   - {conn['connector_name']} ({conn['connector_type']})")
    
    # 4. Test connection
    print("\n4. Testing connector connection...")
    test_response = requests.post(
        f"{API_BASE}/api/connectors/configurations/{connector['connector_id']}/test",
        headers=headers
    )
    
    if test_response.status_code == 200:
        test_result = test_response.json()
        print(f"✅ Connection test: {test_result.get('status')}")
        if 'message' in test_result:
            print(f"   {test_result['message']}")
        if 'details' in test_result:
            print(f"   Details: {json.dumps(test_result['details'], indent=2)}")
    
    print("\n✅ Filesystem connector setup complete!")
    print(f"\n📊 Connector Summary:")
    print(f"   ID: {connector['connector_id']}")
    print(f"   Path: /app/tests/resumes")
    print(f"   Ready for ML Talent Intelligence testing")


if __name__ == "__main__":
    main()

