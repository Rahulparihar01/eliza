#!/usr/bin/env python3
"""
Quick Permission Test Script

A simple script to manually test connector permissions for a specific user.
Run this to quickly verify that a user has the correct permissions.

Usage:
    python quick_permission_test.py
    python quick_permission_test.py --email scott@eliza.com --password admin123
"""

import argparse
import requests
import sys
from typing import Optional, Tuple

# Configuration
BASE_URL = "http://localhost:5001"

# ANSI colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    """Print a header."""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{text}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")


def print_result(test_name: str, expected: int, actual: int, success: bool):
    """Print test result with color."""
    status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
    expected_str = f"expected {expected}"
    actual_str = f"got {actual}"
    print(f"  [{status}] {test_name}: {expected_str}, {actual_str}")


def login(email: str, password: str) -> Tuple[bool, Optional[str], str]:
    """
    Login and return (success, token, message).
    """
    try:
        response = requests.post(
            f"{BASE_URL}/v1/auth/login",
            json={"email": email, "password": password},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                return True, token, "Login successful"
            return False, None, "No access token in response"
        
        return False, None, f"Login failed: {response.status_code} - {response.text[:100]}"
        
    except requests.exceptions.ConnectionError:
        return False, None, f"Cannot connect to {BASE_URL}. Is the server running?"
    except Exception as e:
        return False, None, f"Error: {e}"


def get_user_info(token: str) -> dict:
    """Get current user info including roles and permissions."""
    try:
        response = requests.get(
            f"{BASE_URL}/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return {}
    except:
        return {}


def test_endpoint(token: str, method: str, endpoint: str, json_data: dict = None) -> int:
    """Test an endpoint and return status code."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        if method == "GET":
            response = requests.get(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{endpoint}", headers=headers, json=json_data or {}, timeout=10)
        elif method == "PUT":
            response = requests.put(f"{BASE_URL}{endpoint}", headers=headers, json=json_data or {}, timeout=10)
        elif method == "DELETE":
            response = requests.delete(f"{BASE_URL}{endpoint}", headers=headers, timeout=10)
        else:
            return -1
        
        return response.status_code
        
    except Exception as e:
        print(f"    {YELLOW}Error testing {endpoint}: {e}{RESET}")
        return -1


def run_permission_tests(token: str, is_admin: bool) -> Tuple[int, int]:
    """
    Run all connector permission tests.
    
    Returns (passed, total) counts.
    """
    passed = 0
    total = 0
    
    # Define tests: (name, method, endpoint, json_data, expected_for_admin, expected_for_non_admin)
    tests = [
        # connections:read tests
        ("GET connector types", "GET", "/api/connectors/types", None, 200, 403),
        ("GET configurations", "GET", "/api/connectors/configurations", None, 200, 403),
        ("GET sync runs", "GET", "/api/connectors/sync-runs", None, 200, 403),
        
        # connections:create test (will fail validation but shouldn't be 403 for admin)
        ("POST create configuration", "POST", "/api/connectors/configurations", {
            "connector_type": "greenhouse",
            "connector_name": "Test",
            "credentials": {"api_key": "test"},
            "sync_config": {}
        }, "not_403", 403),
        
        # connections:test test
        ("POST test connection", "POST", "/api/connectors/test-connection", {
            "connector_type": "greenhouse",
            "credentials": {"api_key": "test"},
            "sync_config": {}
        }, "not_403", 403),
        
        # Greenhouse-specific test endpoint
        ("POST test greenhouse", "POST", "/api/connectors/greenhouse/test-connection", {
            "credentials": {"api_key": "test"},
            "sync_config": {}
        }, "not_403", 403),
    ]
    
    for name, method, endpoint, json_data, admin_expected, non_admin_expected in tests:
        total += 1
        expected = admin_expected if is_admin else non_admin_expected
        actual = test_endpoint(token, method, endpoint, json_data)
        
        # Handle "not_403" expectation (admin should not get 403, but may get other errors)
        if expected == "not_403":
            success = actual != 403
            expected_str = "not 403"
        else:
            success = actual == expected
            expected_str = str(expected)
        
        if success:
            passed += 1
        
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {name}: expected {expected_str}, got {actual}")
    
    return passed, total


def main():
    parser = argparse.ArgumentParser(description="Quick connector permission test")
    parser.add_argument("--email", "-e", help="User email", default="scott@eliza.com")
    parser.add_argument("--password", "-p", help="User password", default="admin123")
    args = parser.parse_args()
    
    print_header("Connector Permission Test")
    print(f"Testing user: {args.email}")
    print(f"API URL: {BASE_URL}")
    
    # Check API health first
    print("\n1. Checking API health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print(f"   {GREEN}✓ API is healthy{RESET}")
        else:
            print(f"   {RED}✗ API returned {response.status_code}{RESET}")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"   {RED}✗ Cannot connect to {BASE_URL}{RESET}")
        print(f"   {YELLOW}Make sure the server is running: docker compose up -d{RESET}")
        sys.exit(1)
    
    # Login
    print("\n2. Logging in...")
    success, token, message = login(args.email, args.password)
    if not success:
        print(f"   {RED}✗ {message}{RESET}")
        sys.exit(1)
    print(f"   {GREEN}✓ {message}{RESET}")
    
    # Get user info
    print("\n3. Getting user info...")
    user_info = get_user_info(token)
    if user_info:
        roles = user_info.get("roles", [])
        permissions = user_info.get("permissions", [])
        is_superuser = user_info.get("is_superuser", False)
        customer_id = user_info.get("customer_id", "unknown")
        
        print(f"   Customer ID: {customer_id}")
        print(f"   Is Superuser: {is_superuser}")
        print(f"   Roles: {', '.join(roles) if roles else 'None'}")
        
        # Check for connection permissions
        conn_perms = [p for p in permissions if p.startswith("connections:")]
        if conn_perms:
            print(f"   {GREEN}Connection Permissions: {', '.join(conn_perms)}{RESET}")
        else:
            print(f"   {YELLOW}Connection Permissions: None{RESET}")
        
        # Determine if user should have admin access
        is_admin = is_superuser or "platform_admin" in roles or "admin" in roles or any(p.startswith("connections:") for p in permissions)
    else:
        print(f"   {YELLOW}Could not get user info{RESET}")
        is_admin = True  # Assume admin for testing
    
    # Run permission tests
    print("\n4. Testing connector endpoints...")
    print(f"   (Expecting {'admin' if is_admin else 'non-admin'} access)")
    passed, total = run_permission_tests(token, is_admin)
    
    # Summary
    print_header("Test Summary")
    if passed == total:
        print(f"{GREEN}All {total} tests passed!{RESET}")
        result = 0
    else:
        print(f"{RED}{total - passed} of {total} tests failed{RESET}")
        result = 1
    
    # Recommendations
    if not is_admin and passed < total:
        print(f"\n{YELLOW}Note: This user does not have admin permissions.{RESET}")
        print(f"{YELLOW}If they should have connector access, assign them the 'admin' role.{RESET}")
    
    return result


if __name__ == "__main__":
    sys.exit(main())

