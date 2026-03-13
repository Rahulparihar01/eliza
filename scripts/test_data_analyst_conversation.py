#!/usr/bin/env python3
"""
Test script for Data Analyst conversation flow.

Simulates a real analyst conversation with multiple messages:
1. Initial question
2. Follow-up questions
3. Clarifications
4. Confirmations

This creates real conversation entries that will appear in the UI.
"""
import os
import sys
import time
import requests
import json
from typing import Dict, Any, Optional, List

# API Configuration
API_BASE_URL = os.getenv("API_URL", "http://localhost:5001")
API_PREFIX = "/v1/data-analyst"

# Test user credentials
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "scott@eliza.com")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "admin123")


class ConversationTester:
    """Test client for Data Analyst conversation flow"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token: Optional[str] = None
        self.conversation_id: Optional[str] = None
        self.message_history: List[Dict[str, Any]] = []
    
    def authenticate(self, email: str, password: str) -> bool:
        """Authenticate and get access token"""
        try:
            response = self.session.post(
                f"{self.base_url}/v1/auth/login",
                json={"email": email, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
                print(f"✅ Authenticated as {email}")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False
    
    def submit_question(
        self,
        question: str,
        data_source_type: str = "insurance",
        conversation_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Submit a question"""
        try:
            payload = {
                "data_source_type": data_source_type,
                "question": question
            }
            
            if conversation_id:
                payload["conversation_id"] = conversation_id
            
            response = self.session.post(
                f"{self.base_url}{API_PREFIX}/questions",
                json=payload
            )
            
            if response.status_code == 202:
                data = response.json()
                question_id = data.get("question_id")
                
                # Store conversation_id if returned (for subsequent messages)
                if data.get("conversation_id"):
                    self.conversation_id = data.get("conversation_id")
                    print(f"💬 Conversation ID: {self.conversation_id}")
                
                print(f"✅ Question submitted: {question_id}")
                return data
            else:
                print(f"❌ Submit failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Submit error: {e}")
            return None
    
    def get_question_status(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get question status"""
        try:
            response = self.session.get(
                f"{self.base_url}{API_PREFIX}/questions/{question_id}/status"
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None
    
    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get full question details"""
        try:
            response = self.session.get(
                f"{self.base_url}{API_PREFIX}/questions/{question_id}"
            )
            
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            return None
    
    def clarify_question(
        self,
        question_id: str,
        clarification_response: str
    ) -> Optional[Dict[str, Any]]:
        """Provide clarification response"""
        try:
            response = self.session.post(
                f"{self.base_url}{API_PREFIX}/questions/{question_id}/clarify",
                json={"clarification_response": clarification_response}
            )
            
            if response.status_code == 200:
                print(f"✅ Clarification provided")
                return response.json()
            else:
                print(f"❌ Clarification failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Clarification error: {e}")
            return None
    
    def confirm_intent(
        self,
        question_id: str,
        confirmation_response: str
    ) -> Optional[Dict[str, Any]]:
        """Confirm or correct intent"""
        try:
            response = self.session.post(
                f"{self.base_url}{API_PREFIX}/questions/{question_id}/confirm",
                json={"confirmation_response": confirmation_response}
            )
            
            if response.status_code == 200:
                print(f"✅ Intent confirmed")
                return response.json()
            else:
                print(f"❌ Confirmation failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"❌ Confirmation error: {e}")
            return None
    
    def wait_for_completion(
        self,
        question_id: str,
        max_wait_seconds: int = 120,
        poll_interval: float = 2.0,
        auto_clarify: bool = False,
        auto_confirm: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Wait for question processing to complete"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            status = self.get_question_status(question_id)
            
            if not status:
                time.sleep(poll_interval)
                continue
            
            current_status = status.get("status")
            
            # Handle clarification needed
            if current_status == "clarification_needed":
                question = self.get_question(question_id)
                clarification_prompt = question.get("clarification_prompt") if question else None
                
                if clarification_prompt:
                    print(f"\n❓ Clarification needed:")
                    print(f"   {clarification_prompt}")
                    
                    if auto_clarify:
                        # Auto-clarify with a generic response
                        clarification_response = "Please proceed with the most common interpretation"
                        self.clarify_question(question_id, clarification_response)
                        time.sleep(2)  # Wait a bit before checking again
                        continue
                    else:
                        return {"status": "clarification_needed", "clarification_prompt": clarification_prompt}
            
            # Handle confirmation needed
            if current_status == "intent_confirmed":
                if auto_confirm:
                    # Auto-confirm
                    self.confirm_intent(question_id, "yes")
                    time.sleep(2)  # Wait a bit before checking again
                    continue
                else:
                    return {"status": "confirmation_needed"}
            
            # Check for completion
            if current_status == "completed":
                return status
            
            # Check for failure
            if current_status == "failed":
                error = status.get("error_message")
                print(f"\n❌ Processing failed: {error}")
                return status
            
            time.sleep(poll_interval)
        
        return None
    
    def process_message(
        self,
        question: str,
        data_source_type: str = "insurance",
        auto_clarify: bool = False,
        auto_confirm: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Process a message through the full flow"""
        print(f"\n📤 Question: {question}")
        
        # Submit question
        submit_result = self.submit_question(
            question,
            data_source_type,
            self.conversation_id
        )
        
        if not submit_result:
            return None
        
        question_id = submit_result.get("question_id")
        
        # Wait for completion
        completion_result = self.wait_for_completion(
            question_id,
            auto_clarify=auto_clarify,
            auto_confirm=auto_confirm
        )
        
        # Handle clarification if needed
        if completion_result and completion_result.get("status") == "clarification_needed":
            if not auto_clarify:
                clarification_response = input("💬 Your clarification: ").strip()
                if clarification_response:
                    self.clarify_question(question_id, clarification_response)
                    completion_result = self.wait_for_completion(question_id, auto_confirm=auto_confirm)
        
        # Handle confirmation if needed
        if completion_result and completion_result.get("status") == "confirmation_needed":
            if not auto_confirm:
                confirmation_response = input("💬 Confirm? (yes/no): ").strip() or "yes"
                self.confirm_intent(question_id, confirmation_response)
                completion_result = self.wait_for_completion(question_id)
        
        # Get final result
        question_result = self.get_question(question_id)
        
        if question_result:
            self.message_history.append({
                "question": question,
                "question_id": question_id,
                "result": question_result
            })
            
            # Display summary
            print(f"   ✅ Status: {question_result.get('status')}")
            if question_result.get('generated_sql'):
                print(f"   💾 SQL Generated: Yes")
            if question_result.get('result_data'):
                print(f"   📊 Results: Yes")
            if question_result.get('result_metadata'):
                print(f"   💡 Insights: Yes")
        
        return question_result


def test_analyst_conversation():
    """Test a realistic analyst conversation"""
    print("\n" + "="*80)
    print("DATA ANALYST CONVERSATION TEST")
    print("Simulating Real Analyst Usage")
    print("="*80)
    
    tester = ConversationTester()
    
    # Authenticate
    if not tester.authenticate(TEST_USER_EMAIL, TEST_USER_PASSWORD):
        print("❌ Authentication failed. Exiting.")
        return False
    
    # Conversation flow: Simulating a real analyst session
    conversation_steps = [
        {
            "question": "What is the total premium collected in the last quarter?",
            "description": "Initial question about premium data"
        },
        {
            "question": "Can you break that down by state?",
            "description": "Follow-up question referencing previous result"
        },
        {
            "question": "What about loss ratio by state?",
            "description": "Another follow-up with context"
        },
        {
            "question": "Show me the top 5 states by premium",
            "description": "Ranking query"
        },
        {
            "question": "What is our SOP for handling claims?",
            "description": "Conversational question (not data query)"
        }
    ]
    
    print(f"\n📋 Conversation Plan:")
    for i, step in enumerate(conversation_steps, 1):
        print(f"   {i}. {step['description']}")
        print(f"      Q: {step['question']}")
    
    print(f"\n🚀 Starting conversation...")
    print("-" * 80)
    
    # Process each message
    for i, step in enumerate(conversation_steps, 1):
        print(f"\n[Message {i}/{len(conversation_steps)}]")
        print(f"Description: {step['description']}")
        
        result = tester.process_message(
            step["question"],
            auto_clarify=True,  # Auto-clarify for testing
            auto_confirm=True   # Auto-confirm for testing
        )
        
        if not result:
            print(f"❌ Failed to process message {i}")
            continue
        
        # Small delay between messages
        if i < len(conversation_steps):
            print(f"\n⏳ Waiting 3 seconds before next message...")
            time.sleep(3)
    
    # Display conversation summary
    print("\n" + "="*80)
    print("CONVERSATION SUMMARY")
    print("="*80)
    
    print(f"\n📊 Total Messages: {len(tester.message_history)}")
    if tester.conversation_id:
        print(f"💬 Conversation ID: {tester.conversation_id}")
    
    print(f"\n📝 Message History:")
    for i, msg in enumerate(tester.message_history, 1):
        print(f"\n   Message {i}:")
        print(f"   Question: {msg['question']}")
        print(f"   Question ID: {msg['question_id']}")
        print(f"   Status: {msg['result'].get('status')}")
        
        if msg['result'].get('detected_intent'):
            print(f"   Intent: {msg['result'].get('detected_intent')}")
        
        if msg['result'].get('generated_sql'):
            sql_preview = msg['result'].get('generated_sql', '')[:100]
            print(f"   SQL: {sql_preview}...")
        
        if msg['result'].get('result_data'):
            result_data = msg['result'].get('result_data', {})
            row_count = result_data.get('row_count', 0)
            print(f"   Results: {row_count} rows")
    
    print("\n" + "="*80)
    print("✅ Conversation test completed!")
    print(f"💡 Check the UI to see these messages in the conversation view")
    print("="*80)
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Data Analyst conversation flow")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode (prompts for clarifications/confirmations)"
    )
    
    args = parser.parse_args()
    
    success = test_analyst_conversation()
    
    sys.exit(0 if success else 1)

