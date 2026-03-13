#!/usr/bin/env python3
"""
End-to-End Tenant Connector Permission Test

This test:
1. Logs in as platform admin
2. Creates a new tenant "testing_tenant" with connectors feature
3. Accepts the admin invite to create tenant admin user
4. Logs in as the tenant admin
5. Tests that the tenant admin can access connector endpoints
6. Tests creating a connector configuration

All interactions are via API - no direct database access.

Usage:
    python3 test_tenant_connector_flow.py
"""

import requests
import json
import sys
import re
from typing import Optional, Tuple, Dict, Any

# Configuration
BASE_URL = "http://localhost:5001"

# Test data
PLATFORM_ADMIN_EMAIL = "scott@eliza.com"
PLATFORM_ADMIN_PASSWORD = "admin123"

TENANT_ID = "testing-tenant"
TENANT_NAME = "Testing Tenant"
TENANT_ADMIN_EMAIL = "test_tenant_admin@testing-tenant.com"
TENANT_ADMIN_NAME = "Test Tenant Admin"
TENANT_ADMIN_PASSWORD = "password123"

# Feature IDs (from platform-admin/features endpoint)
CONNECTORS_FEATURE_ID = 2
USERS_ROLES_FEATURE_ID = 8

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{BOLD}{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}{CYAN}{text}{RESET}")
    print(f"{BOLD}{CYAN}{'='*60}{RESET}")


def print_step(step: int, text: str):
    print(f"\n{BOLD}Step {step}: {text}{RESET}")


def print_success(text: str):
    print(f"  {GREEN}✓ {text}{RESET}")


def print_error(text: str):
    print(f"  {RED}✗ {text}{RESET}")


def print_info(text: str):
    print(f"  {YELLOW}ℹ {text}{RESET}")


def login(email: str, password: str) -> Tuple[bool, Optional[str], str]:
    """Login and return (success, token, message)."""
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            return True, token, "Login successful"
        return False, None, f"Login failed: {resp.status_code} - {resp.text[:100]}"
    except Exception as e:
        return False, None, f"Error: {e}"


def api_get(token: str, endpoint: str) -> requests.Response:
    """Make authenticated GET request."""
    return requests.get(
        f"{BASE_URL}{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )


def api_post(token: str, endpoint: str, data: dict) -> requests.Response:
    """Make authenticated POST request."""
    return requests.post(
        f"{BASE_URL}{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        json=data,
        timeout=30
    )


def check_tenant_exists(token: str, tenant_id: str) -> bool:
    """Check if tenant already exists."""
    resp = api_get(token, f"/api/v1/platform-admin/tenants/{tenant_id}")
    return resp.status_code == 200


def delete_tenant_if_exists(token: str, tenant_id: str) -> bool:
    """Delete tenant if it exists (for clean test runs)."""
    if not check_tenant_exists(token, tenant_id):
        return True
    
    # Deactivate first
    resp = api_post(token, f"/api/v1/platform-admin/tenants/{tenant_id}/deactivate", {
        "reason": "Test cleanup",
        "confirm_name": TENANT_NAME
    })
    return resp.status_code in [200, 404]


def create_tenant(token: str) -> Tuple[bool, Optional[str], str]:
    """Create the test tenant with connectors feature."""
    data = {
        "customer_id": TENANT_ID,
        "name": TENANT_NAME,
        "display_name": TENANT_NAME,
        "admin_email": TENANT_ADMIN_EMAIL,
        "admin_name": TENANT_ADMIN_NAME,
        "feature_ids": [CONNECTORS_FEATURE_ID, USERS_ROLES_FEATURE_ID],
        "subscription_tier": "enterprise"
    }
    
    resp = api_post(token, "/api/v1/platform-admin/tenants", data)
    
    if resp.status_code == 201:
        result = resp.json()
        invite_url = result.get("admin_invite_url", "")
        # Extract token from URL
        match = re.search(r'token=([^&]+)', invite_url)
        invite_token = match.group(1) if match else None
        return True, invite_token, f"Tenant created, invite URL: {invite_url}"
    
    return False, None, f"Failed: {resp.status_code} - {resp.text[:200]}"


def accept_invite(invite_token: str, password: str) -> Tuple[bool, str]:
    """Accept the admin invite to complete registration."""
    resp = requests.post(
        f"{BASE_URL}/v1/auth/invite/accept",
        json={
            "token": invite_token,
            "password": password,
            "confirm_password": password
        },
        timeout=10
    )
    
    if resp.status_code in [200, 201]:
        return True, "Admin registration completed"
    
    return False, f"Failed: {resp.status_code} - {resp.text[:200]}"


def test_connector_read_access(token: str) -> Tuple[bool, str]:
    """Test that user can read connector types and configurations."""
    # Test GET /api/connectors/types
    resp = api_get(token, "/api/connectors/types")
    if resp.status_code == 403:
        return False, "Cannot read connector types (403 Forbidden)"
    if resp.status_code != 200:
        return False, f"Unexpected status on /types: {resp.status_code}"
    
    # Test GET /api/connectors/configurations
    resp = api_get(token, "/api/connectors/configurations")
    if resp.status_code == 403:
        return False, "Cannot read configurations (403 Forbidden)"
    if resp.status_code != 200:
        return False, f"Unexpected status on /configurations: {resp.status_code}"
    
    return True, "Can read connector types and configurations"


def test_connector_create_access(token: str) -> Tuple[bool, str]:
    """Test that user can create a connector configuration."""
    data = {
        "connector_type": "greenhouse",
        "connector_name": "Test Greenhouse Connector",
        "description": "Created by permission test",
        "credentials": {
            "api_key": "test_api_key_for_permission_test"
        },
        "sync_config": {
            "max_candidates": 100
        },
        "sync_mode": "full_refresh"
    }
    
    resp = api_post(token, "/api/connectors/configurations", data)
    
    if resp.status_code == 403:
        return False, "Cannot create connector (403 Forbidden) - MISSING connections:create permission"
    
    # 400 = validation error (expected with fake API key)
    # 500 = connection test failed (expected with fake API key)
    # 201 = success (unlikely with fake key)
    if resp.status_code in [201, 400, 500]:
        return True, f"Create endpoint accessible (status {resp.status_code} - permission granted)"
    
    return False, f"Unexpected status: {resp.status_code} - {resp.text[:100]}"


def get_user_permissions(token: str) -> Dict[str, Any]:
    """Get current user's permissions."""
    resp = api_get(token, "/v1/auth/me")
    if resp.status_code == 200:
        return resp.json()
    return {}


def main():
    print_header("End-to-End Tenant Connector Permission Test")
    print(f"API URL: {BASE_URL}")
    print(f"Tenant: {TENANT_ID}")
    print(f"Admin: {TENANT_ADMIN_EMAIL}")
    
    # Track results
    results = []
    
    # =========================================================================
    # Step 1: Login as Platform Admin
    # =========================================================================
    print_step(1, "Login as Platform Admin")
    success, platform_token, msg = login(PLATFORM_ADMIN_EMAIL, PLATFORM_ADMIN_PASSWORD)
    if not success:
        print_error(msg)
        print_error("Cannot continue without platform admin access")
        return 1
    print_success(msg)
    
    # =========================================================================
    # Step 2: Check/Clean existing tenant
    # =========================================================================
    print_step(2, "Check for existing tenant")
    if check_tenant_exists(platform_token, TENANT_ID):
        print_info(f"Tenant '{TENANT_ID}' already exists")
        # Try to login as the existing admin
        print_info("Attempting to login as existing admin...")
        success, tenant_token, msg = login(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        if success:
            print_success("Existing admin login successful, skipping to permission tests")
            # Jump to permission tests
            goto_permission_tests = True
        else:
            print_info("Could not login as existing admin, will recreate tenant")
            print_info("Deactivating existing tenant...")
            delete_tenant_if_exists(platform_token, TENANT_ID)
            goto_permission_tests = False
    else:
        print_success(f"Tenant '{TENANT_ID}' does not exist")
        goto_permission_tests = False
    
    if not goto_permission_tests:
        # =========================================================================
        # Step 3: Create Tenant with Connectors Feature
        # =========================================================================
        print_step(3, "Create Tenant with Connectors Feature")
        success, invite_token, msg = create_tenant(platform_token)
        if not success:
            print_error(msg)
            print_error("Cannot continue without tenant")
            return 1
        print_success(msg)
        
        if not invite_token:
            print_error("No invite token found in response")
            print_info("Check if invite URL was returned")
            return 1
        
        print_info(f"Invite token: {invite_token[:20]}...")
        
        # =========================================================================
        # Step 4: Accept Invite (Create Admin User)
        # =========================================================================
        print_step(4, "Accept Admin Invite")
        success, msg = accept_invite(invite_token, TENANT_ADMIN_PASSWORD)
        if not success:
            print_error(msg)
            return 1
        print_success(msg)
        
        # =========================================================================
        # Step 5: Login as Tenant Admin
        # =========================================================================
        print_step(5, "Login as Tenant Admin")
        success, tenant_token, msg = login(TENANT_ADMIN_EMAIL, TENANT_ADMIN_PASSWORD)
        if not success:
            print_error(msg)
            return 1
        print_success(msg)
    
    # =========================================================================
    # Step 6: Verify User Permissions
    # =========================================================================
    print_step(6, "Verify User Permissions")
    user_info = get_user_permissions(tenant_token)
    
    roles = user_info.get("roles", [])
    permissions = user_info.get("permissions", [])
    customer_id = user_info.get("customer_id", "unknown")
    
    print_info(f"Customer ID: {customer_id}")
    print_info(f"Roles: {', '.join(roles) if roles else 'None'}")
    
    conn_perms = [p for p in permissions if p.startswith("connections:")]
    if conn_perms:
        print_success(f"Has connection permissions: {', '.join(conn_perms)}")
        results.append(("Connection permissions exist", True))
    else:
        print_error("NO connection permissions found!")
        print_info(f"All permissions: {permissions}")
        results.append(("Connection permissions exist", False))
    
    # =========================================================================
    # Step 7: Test Connector Read Access
    # =========================================================================
    print_step(7, "Test Connector Read Access (connections:read)")
    success, msg = test_connector_read_access(tenant_token)
    if success:
        print_success(msg)
    else:
        print_error(msg)
    results.append(("Connector read access", success))
    
    # =========================================================================
    # Step 8: Test Connector Create Access
    # =========================================================================
    print_step(8, "Test Connector Create Access (connections:create)")
    success, msg = test_connector_create_access(tenant_token)
    if success:
        print_success(msg)
    else:
        print_error(msg)
    results.append(("Connector create access", success))
    
    # =========================================================================
    # Summary
    # =========================================================================
    print_header("Test Results Summary")
    
    all_passed = True
    for test_name, passed in results:
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {test_name}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print(f"{GREEN}{BOLD}All tests passed!{RESET}")
        print(f"\nTenant admin '{TENANT_ADMIN_EMAIL}' can successfully access connector features.")
        return 0
    else:
        print(f"{RED}{BOLD}Some tests failed!{RESET}")
        print(f"\nCheck the permission assignments for the tenant admin role.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

