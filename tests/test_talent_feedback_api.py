"""
Test Talent Feedback API

Tests the feedback submission and retrieval endpoints.
"""

import requests
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:5001"
TEST_USER_EMAIL = "laura.sullivan@caylent.com"
TEST_USER_PASSWORD = "admin123"


def test_feedback_workflow():
    """Test complete feedback workflow: submit and retrieve"""
    
    print("="*80)
    print("TESTING TALENT FEEDBACK API")
    print("="*80)
    
    # Step 1: Login to get auth token
    print("\n1. Logging in as test user...")
    login_response = requests.post(
        f"{API_BASE_URL}/v1/auth/login",
        json={
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        }
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return False
    
    auth_data = login_response.json()
    token = auth_data.get("access_token")
    print(f"✅ Login successful")
    print(f"   User: {auth_data.get('user', {}).get('email')}")
    print(f"   Customer ID: {auth_data.get('user', {}).get('customer_id')}")
    
    # Headers for authenticated requests
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Step 2: Submit feature request feedback
    print("\n2. Submitting feature request feedback...")
    feature_feedback = {
        "feedback_type": "feature_request",
        "category": "ui_ux",
        "title": "Add bulk candidate export feature",
        "description": "It would be great to have a button to export all candidates from an analysis to CSV or Excel format. This would help us share results with stakeholders who don't have system access.",
        "rating": None,
        "metadata": {
            "user_agent": "Test Script",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    submit_response = requests.post(
        f"{API_BASE_URL}/api/v1/talent/feedback/submit",
        headers=headers,
        json=feature_feedback
    )
    
    if submit_response.status_code != 201:
        print(f"❌ Feature request submission failed: {submit_response.status_code}")
        print(f"Response: {submit_response.text}")
        return False
    
    feature_result = submit_response.json()
    print(f"✅ Feature request submitted successfully")
    print(f"   Feedback ID: {feature_result['id']}")
    print(f"   Status: {feature_result['status']}")
    print(f"   Priority: {feature_result['priority']}")
    
    # Step 3: Submit bug report feedback
    print("\n3. Submitting bug report feedback...")
    bug_feedback = {
        "feedback_type": "bug_report",
        "category": "resume_parsing",
        "title": "Resume parser missing work experience dates",
        "description": "When I uploaded John Doe's resume, the parser extracted the company names but missed the employment dates. The dates are clearly visible in the original PDF under the 'Professional Experience' section.",
        "rating": None,
        "metadata": {
            "user_agent": "Test Script",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    submit_response = requests.post(
        f"{API_BASE_URL}/api/v1/talent/feedback/submit",
        headers=headers,
        json=bug_feedback
    )
    
    if submit_response.status_code != 201:
        print(f"❌ Bug report submission failed: {submit_response.status_code}")
        print(f"Response: {submit_response.text}")
        return False
    
    bug_result = submit_response.json()
    print(f"✅ Bug report submitted successfully")
    print(f"   Feedback ID: {bug_result['id']}")
    print(f"   Status: {bug_result['status']}")
    
    # Step 4: Submit model improvement feedback
    print("\n4. Submitting model improvement feedback...")
    model_feedback = {
        "feedback_type": "model_improvement",
        "category": "scoring",
        "title": "Candidate scoring should weight recent experience more heavily",
        "description": "The AI seems to give equal weight to all years of experience. For our use case, experience from the last 3-5 years is much more relevant than older experience, especially in fast-moving tech roles. Could the model be adjusted to prioritize recent work history?",
        "rating": None,
        "metadata": {
            "user_agent": "Test Script",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    submit_response = requests.post(
        f"{API_BASE_URL}/api/v1/talent/feedback/submit",
        headers=headers,
        json=model_feedback
    )
    
    if submit_response.status_code != 201:
        print(f"❌ Model improvement submission failed: {submit_response.status_code}")
        print(f"Response: {submit_response.text}")
        return False
    
    model_result = submit_response.json()
    print(f"✅ Model improvement feedback submitted successfully")
    print(f"   Feedback ID: {model_result['id']}")
    print(f"   Status: {model_result['status']}")
    
    # Step 5: Submit general feedback with rating
    print("\n5. Submitting general feedback with rating...")
    general_feedback = {
        "feedback_type": "general_feedback",
        "category": "other",
        "title": "Overall system experience",
        "description": "The Talent Intelligence system has been incredibly helpful for our hiring process. The AI-powered candidate matching saves us hours of manual resume screening. The only suggestion would be to add keyboard shortcuts for common actions.",
        "rating": 5,
        "metadata": {
            "user_agent": "Test Script",
            "timestamp": datetime.utcnow().isoformat()
        }
    }
    
    submit_response = requests.post(
        f"{API_BASE_URL}/api/v1/talent/feedback/submit",
        headers=headers,
        json=general_feedback
    )
    
    if submit_response.status_code != 201:
        print(f"❌ General feedback submission failed: {submit_response.status_code}")
        print(f"Response: {submit_response.text}")
        return False
    
    general_result = submit_response.json()
    print(f"✅ General feedback submitted successfully")
    print(f"   Feedback ID: {general_result['id']}")
    print(f"   Rating: {general_result['rating']}/5 stars")
    
    # Step 6: Retrieve all feedback for current user
    print("\n6. Retrieving all feedback for current user...")
    get_response = requests.get(
        f"{API_BASE_URL}/api/v1/talent/feedback/my-feedback",
        headers=headers,
        params={"page": 1, "page_size": 10}
    )
    
    if get_response.status_code != 200:
        print(f"❌ Feedback retrieval failed: {get_response.status_code}")
        print(f"Response: {get_response.text}")
        return False
    
    feedback_list = get_response.json()
    print(f"✅ Feedback retrieved successfully")
    print(f"   Total feedback items: {feedback_list['total']}")
    print(f"   Current page: {feedback_list['page']}/{feedback_list['pages']}")
    
    # Step 7: Display summary of all feedback
    print("\n7. Summary of submitted feedback:")
    print("-" * 80)
    for idx, item in enumerate(feedback_list['feedback'], 1):
        print(f"\n   [{idx}] {item['title']}")
        print(f"       Type: {item['feedback_type']}")
        print(f"       Category: {item['category']}")
        print(f"       Status: {item['status']}")
        print(f"       Priority: {item['priority']}")
        if item.get('rating'):
            print(f"       Rating: {item['rating']}/5 stars")
        print(f"       Created: {item['created_at']}")
    
    # Step 8: Filter by feedback type
    print("\n8. Testing filtered retrieval (feature_request only)...")
    filter_response = requests.get(
        f"{API_BASE_URL}/api/v1/talent/feedback/my-feedback",
        headers=headers,
        params={"page": 1, "page_size": 10, "feedback_type": "feature_request"}
    )
    
    if filter_response.status_code != 200:
        print(f"❌ Filtered retrieval failed: {filter_response.status_code}")
        return False
    
    filtered_list = filter_response.json()
    print(f"✅ Filtered retrieval successful")
    print(f"   Feature requests found: {filtered_list['total']}")
    
    print("\n" + "="*80)
    print("✅ ALL TESTS PASSED!")
    print("="*80)
    print("\nThe Talent Feedback system is working correctly:")
    print("  ✅ Users can submit different types of feedback")
    print("  ✅ Feedback is stored in the database")
    print("  ✅ Users can retrieve their feedback history")
    print("  ✅ Filtering by feedback type works")
    print("  ✅ Rating system works for general feedback")
    print("\n💡 Next steps:")
    print("  - Log into the UI at https://caylent-hr-intel.lhr.rocks")
    print("  - Navigate to TALENT → Feedback")
    print("  - Submit feedback through the web interface")
    print("  - Admin users can view all feedback via /api/v1/talent/feedback/all")
    
    return True


if __name__ == "__main__":
    try:
        success = test_feedback_workflow()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {str(e)}")
        import traceback
        traceback.print_exc()
        exit(1)

