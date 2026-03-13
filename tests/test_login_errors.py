#!/usr/bin/env python3
"""
Test script for login error message improvements
Tests various login scenarios and verifies error messages
"""

import requests
import json
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:5001"
LOGIN_ENDPOINT = f"{BASE_URL}/v1/auth/login"

# ANSI color codes for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_test_header(test_name: str):
    """Print a formatted test header"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}TEST: {test_name}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")


def print_result(success: bool, message: str):
    """Print test result with color coding"""
    if success:
        print(f"{GREEN}✓ PASS:{RESET} {message}")
    else:
        print(f"{RED}✗ FAIL:{RESET} {message}")


def test_login(email: str, password: str, test_name: str, expected_status: int, expected_message_contains: str = None):
    """
    Test a login attempt and verify the response
    
    Args:
        email: Email to test
        password: Password to test
        test_name: Name of the test
        expected_status: Expected HTTP status code
        expected_message_contains: String that should be in the error message
    """
    print_test_header(test_name)
    
    payload = {
        "email": email,
        "password": password,
        "remember_me": False
    }
    
    print(f"{YELLOW}Request:{RESET}")
    print(f"  Email: {email}")
    print(f"  Password: {'*' * len(password)}")
    
    try:
        response = requests.post(LOGIN_ENDPOINT, json=payload)
        
        print(f"\n{YELLOW}Response:{RESET}")
        print(f"  Status Code: {response.status_code}")
        
        if response.status_code == expected_status:
            print_result(True, f"Status code matches expected: {expected_status}")
        else:
            print_result(False, f"Expected {expected_status}, got {response.status_code}")
        
        # Parse response
        try:
            response_data = response.json()
            
            if response.status_code == 200:
                print(f"  Success: Login successful!")
                print(f"  User: {response_data.get('user', {}).get('email', 'N/A')}")
                return True
            else:
                # Error response - check both 'message' and 'detail' fields
                error_message = response_data.get('message') or response_data.get('detail', 'No error message')
                print(f"  Error Message: {error_message}")
                
                if expected_message_contains:
                    if expected_message_contains.lower() in error_message.lower():
                        print_result(True, f"Error message contains expected text: '{expected_message_contains}'")
                        return True
                    else:
                        print_result(False, f"Error message doesn't contain: '{expected_message_contains}'")
                        return False
                
                return response.status_code == expected_status
                
        except json.JSONDecodeError:
            print_result(False, "Failed to parse JSON response")
            print(f"  Raw response: {response.text[:200]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print_result(False, "Failed to connect to the server. Is it running?")
        return False
    except Exception as e:
        print_result(False, f"Unexpected error: {str(e)}")
        return False


def main():
    """Run all login error tests"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}LOGIN ERROR MESSAGE TESTS{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")
    print(f"Testing against: {BASE_URL}")
    
    results = []
    
    # Test 1: User Not Found
    results.append(
        test_login(
            email="nonexistent@example.com",
            password="anypassword",
            test_name="Test 1: User Not Found",
            expected_status=401,
            expected_message_contains="couldn't find an account"
        )
    )
    
    # Test 2: Wrong Password (First Attempt)
    results.append(
        test_login(
            email="scott@eliza.com",
            password="wrongpassword123",
            test_name="Test 2: Wrong Password (First Attempt)",
            expected_status=401,
            expected_message_contains="password"
        )
    )
    
    # Test 3: Wrong Password (Second Attempt - should show warning after a few attempts)
    results.append(
        test_login(
            email="scott@eliza.com",
            password="wrongpassword456",
            test_name="Test 3: Wrong Password (Multiple Attempts)",
            expected_status=401,
            expected_message_contains="password"
        )
    )
    
    # Test 4: Successful Login (to reset failed attempts)
    results.append(
        test_login(
            email="scott@eliza.com",
            password="admin123",
            test_name="Test 4: Successful Login",
            expected_status=200
        )
    )
    
    # Test 5: Invalid Email Format (should be caught by frontend validation)
    results.append(
        test_login(
            email="not-an-email",
            password="somepassword",
            test_name="Test 5: Invalid Email Format",
            expected_status=422  # Validation error
        )
    )
    
    # Summary
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print(f"{BLUE}{'='*80}{RESET}")
    
    passed = sum(results)
    total = len(results)
    
    print(f"\nTotal Tests: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {total - passed}{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}✓ All tests passed!{RESET}")
    else:
        print(f"\n{RED}✗ Some tests failed. Please review the output above.{RESET}")
    
    print(f"\n{YELLOW}Note:{RESET} Frontend-specific features (auto-clear on typing, contextual tips)")
    print(f"      should be tested manually in the browser.")
    
    return passed == total


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)

