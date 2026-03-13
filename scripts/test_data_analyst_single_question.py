#!/usr/bin/env python3
"""
Test script for Data Analyst single question flow.

Tests the full CrewAI flow with a single question:
1. Submit question via API
2. Wait for processing
3. Display results

This creates real database entries that will appear in the UI.
"""
import os
import sys
import time
import requests
import json
from typing import Dict, Any, Optional

# API Configuration
API_BASE_URL = os.getenv("API_URL", "http://localhost:5001")
API_PREFIX = "/v1/data-analyst"

# Test user credentials (adjust as needed)
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL", "scott@eliza.com")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD", "admin123")


class DataAnalystTester:
    """Test client for Data Analyst API"""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token: Optional[str] = None
    
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
        data_source_type: str = "insurance"
    ) -> Optional[Dict[str, Any]]:
        """Submit a question"""
        try:
            response = self.session.post(
                f"{self.base_url}{API_PREFIX}/questions",
                json={
                    "data_source_type": data_source_type,
                    "question": question
                }
            )
            
            if response.status_code == 202:
                data = response.json()
                print(f"✅ Question submitted: {data.get('question_id')}")
                print(f"   Status: {data.get('status')}")
                print(f"   Message: {data.get('message')}")
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
            else:
                print(f"⚠️  Status check failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️  Status check error: {e}")
            return None
    
    def stream_question_status(self, question_id: str, max_duration: int = 120):
        """
        Stream question status updates using SSE.
        
        Args:
            question_id: Question ID to monitor
            max_duration: Maximum duration in seconds to stream (default: 120)
        """
        import sseclient
        import time
        
        try:
            # SSE endpoint requires token as query param
            stream_url = f"{self.base_url}{API_PREFIX}/questions/{question_id}/stream?token={self.auth_token}"
            
            print(f"📡 Connecting to SSE stream...")
            response = self.session.get(stream_url, stream=True, timeout=max_duration + 10)
            response.raise_for_status()
            
            client = sseclient.SSEClient(response)
            start_time = time.time()
            
            for event in client.events():
                if time.time() - start_time > max_duration:
                    print(f"⏱️  Max duration ({max_duration}s) reached")
                    break
                
                try:
                    data = json.loads(event.data)
                    event_type = data.get("event_type")
                    
                    if event_type == "connected":
                        print(f"✅ Connected to stream")
                    elif event_type == "status_update":
                        status = data.get("status", "unknown")
                        progress = data.get("progress_percentage", 0.0)
                        print(f"📊 Status: {status} ({progress:.1f}%)")
                    elif event_type == "completed":
                        print(f"✅ Processing completed!")
                        return data
                    elif event_type == "failed":
                        error_msg = data.get("message", "Unknown error")
                        print(f"❌ Processing failed: {error_msg}")
                        return data
                    elif event_type == "heartbeat":
                        # Silent heartbeat
                        pass
                    elif event_type == "error":
                        error_msg = data.get("message", "Unknown error")
                        print(f"❌ Stream error: {error_msg}")
                        return None
                except json.JSONDecodeError as e:
                    print(f"⚠️  Failed to parse event: {e}")
                    continue
            
            print(f"⏱️  Stream ended")
            return None
            
        except Exception as e:
            print(f"❌ Stream error: {e}")
            return None
    
    def get_question(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get full question details"""
        try:
            response = self.session.get(
                f"{self.base_url}{API_PREFIX}/questions/{question_id}"
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️  Get question failed: {response.status_code}")
                return None
        except Exception as e:
            print(f"⚠️  Get question error: {e}")
            return None
    
    def get_result(self, question_id: str) -> Optional[Dict[str, Any]]:
        """Get analysis result"""
        try:
            response = self.session.get(
                f"{self.base_url}{API_PREFIX}/questions/{question_id}/result"
            )
            
            if response.status_code == 200:
                return response.json()
            else:
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
                print(f"❌ Clarification failed: {response.status_code} - {response.text}")
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
                print(f"❌ Confirmation failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(f"❌ Confirmation error: {e}")
            return None
    
    def stream_question_status(self, question_id: str, max_duration: int = 120):
        """
        Stream question status updates using SSE.
        
        Args:
            question_id: Question ID to monitor
            max_duration: Maximum duration in seconds to stream (default: 120)
        """
        try:
            import sseclient
            
            # SSE endpoint requires token as query param
            stream_url = f"{self.base_url}{API_PREFIX}/questions/{question_id}/stream?token={self.auth_token}"
            
            print(f"📡 Connecting to SSE stream...")
            response = self.session.get(stream_url, stream=True, timeout=max_duration + 10)
            response.raise_for_status()
            
            client = sseclient.SSEClient(response)
            start_time = time.time()
            last_status = None
            
            for event in client.events():
                if time.time() - start_time > max_duration:
                    print(f"\n⏱️  Max duration ({max_duration}s) reached")
                    break
                
                try:
                    data = json.loads(event.data)
                    event_type = data.get("event_type")
                    
                    # Handle telemetry events (flow step events)
                    if event_type in ["flow_started", "intent_detection_started", "intent_detection_completed",
                                     "clarification_started", "clarification_completed",
                                     "confirmation_started", "confirmation_completed",
                                     "processing_started", "processing_completed",
                                     "sql_generation_started", "sql_generation_completed",
                                     "sql_execution_started", "sql_execution_completed",
                                     "insights_generation_started", "insights_generation_completed",
                                     "flow_completed", "flow_failed", "error", "info", "warning"]:
                        # Telemetry event - display with details
                        stage_name = data.get("stage_name", "")
                        agent_name = data.get("agent_name", "")
                        user_message = data.get("user_message", "")
                        tool_name = data.get("tool_name", "")
                        progress_pct = data.get("progress_percentage")
                        event_data = data.get("data", {})
                        error_details = data.get("error_details")
                        
                        # Format event display
                        event_display = f"📊 [{event_type.upper()}]"
                        if stage_name:
                            event_display += f" {stage_name}"
                        if agent_name:
                            event_display += f" | Agent: {agent_name}"
                        if tool_name:
                            event_display += f" | Tool: {tool_name}"
                        if progress_pct is not None:
                            event_display += f" | {progress_pct}%"
                        
                        print(f"\n{event_display}")
                        if user_message:
                            print(f"   💬 {user_message}")
                        if event_data and isinstance(event_data, dict) and len(str(event_data)) < 200:
                            print(f"   📋 {json.dumps(event_data, indent=2)}")
                        if error_details:
                            print(f"   ⚠️  Error: {json.dumps(error_details, indent=2)}")
                        
                        # Check for terminal events
                        if event_type in ["flow_completed", "completed"]:
                            print(f"\n✅ Flow completed successfully!")
                            return data
                        elif event_type in ["flow_failed", "failed"]:
                            error_msg = user_message or data.get("message", "Unknown error")
                            print(f"\n❌ Flow failed: {error_msg}")
                            return data
                    
                    elif event_type == "connected":
                        print(f"✅ Connected to stream")
                    elif event_type == "status_update":
                        status = data.get("status", "unknown")
                        progress = data.get("progress_percentage", 0.0)
                        if status != last_status:
                            print(f"\n📊 Status: {status} ({progress:.1f}%)")
                            last_status = status
                        
                        # Check for clarification needed
                        if status == "clarification_needed":
                            question = self.get_question(question_id)
                            clarification_prompt = question.get("clarification_prompt") if question else None
                            if clarification_prompt:
                                print(f"\n❓ Clarification needed:")
                                print(f"   {clarification_prompt}")
                                return {"status": "clarification_needed", "clarification_prompt": clarification_prompt}
                        
                        # Check for confirmation needed
                        if status == "intent_confirmed":
                            print(f"\n✅ Intent detected, waiting for confirmation...")
                            return {"status": "confirmation_needed"}
                    elif event_type == "completed":
                        print(f"\n✅ Processing completed!")
                        return data
                    elif event_type == "failed":
                        error_msg = data.get("message", "Unknown error")
                        print(f"\n❌ Processing failed: {error_msg}")
                        return data
                    elif event_type == "heartbeat":
                        # Silent heartbeat
                        pass
                    elif event_type == "error":
                        error_msg = data.get("message", "Unknown error")
                        print(f"\n❌ Stream error: {error_msg}")
                        return None
                except json.JSONDecodeError as e:
                    print(f"⚠️  Failed to parse event: {e}")
                    continue
            
            print(f"\n⏱️  Stream ended")
            return None
            
        except ImportError:
            print("⚠️  sseclient not installed, falling back to polling...")
            return self._wait_for_completion_polling(question_id, max_duration)
        except Exception as e:
            print(f"❌ Stream error: {e}, falling back to polling...")
            return self._wait_for_completion_polling(question_id, max_duration)
    
    def _wait_for_completion_polling(
        self,
        question_id: str,
        max_wait_seconds: int = 120,
        poll_interval: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """Fallback polling method for waiting for completion"""
        start_time = time.time()
        
        print(f"\n⏳ Polling for status (max {max_wait_seconds}s)...")
        
        while time.time() - start_time < max_wait_seconds:
            status = self.get_question_status(question_id)
            
            if not status:
                time.sleep(poll_interval)
                continue
            
            current_status = status.get("status")
            progress = status.get("progress_percentage", 0)
            
            # Check for clarification needed
            if current_status == "clarification_needed":
                question = self.get_question(question_id)
                clarification_prompt = question.get("clarification_prompt") if question else None
                
                if clarification_prompt:
                    print(f"\n❓ Clarification needed:")
                    print(f"   {clarification_prompt}")
                    return {"status": "clarification_needed", "clarification_prompt": clarification_prompt}
            
            # Check for confirmation needed
            if current_status == "intent_confirmed":
                print(f"\n✅ Intent detected, waiting for confirmation...")
                return {"status": "confirmation_needed"}
            
            # Check for completion
            if current_status == "completed":
                print(f"\n✅ Processing completed!")
                return status
            
            # Check for failure
            if current_status == "failed":
                error = status.get("error_message")
                print(f"\n❌ Processing failed: {error}")
                return status
            
            # Show progress
            print(f"   Status: {current_status} ({progress:.0f}%)", end="\r")
            
            time.sleep(poll_interval)
        
        print(f"\n⏱️  Timeout after {max_wait_seconds}s")
        return None
    
    def wait_for_completion(
        self,
        question_id: str,
        max_wait_seconds: int = 120,
        poll_interval: float = 2.0
    ) -> Optional[Dict[str, Any]]:
        """Wait for question processing to complete using SSE stream"""
        return self.stream_question_status(question_id, max_duration=max_wait_seconds)
    
    def display_results(self, question_id: str):
        """Display question results"""
        question = self.get_question(question_id)
        
        if not question:
            print("❌ Could not retrieve question")
            return
        
        print("\n" + "="*80)
        print("QUESTION RESULTS")
        print("="*80)
        
        print(f"\n📝 Question: {question.get('original_question')}")
        print(f"📊 Status: {question.get('status')}")
        print(f"🆔 Question ID: {question.get('question_id')}")
        
        if question.get('detected_intent'):
            print(f"🎯 Detected Intent: {question.get('detected_intent')}")
            print(f"📈 Confidence: {question.get('intent_confidence')}")
        
        if question.get('clarified_question'):
            print(f"✨ Clarified Question: {question.get('clarified_question')}")
        
        if question.get('generated_sql'):
            print(f"\n💾 Generated SQL:")
            print("-" * 80)
            print(question.get('generated_sql'))
            print("-" * 80)
        
        if question.get('sql_error'):
            print(f"\n❌ SQL Error: {question.get('sql_error')}")
        
        # Display results
        result_data = question.get('result_data')
        result_metadata = question.get('result_metadata')
        
        if result_data:
            print(f"\n📊 Result Data:")
            print(json.dumps(result_data, indent=2, default=str))
        
        if result_metadata:
            print(f"\n💡 Insights:")
            if isinstance(result_metadata, dict):
                if result_metadata.get('executive_summary'):
                    print(f"\n📋 Executive Summary:")
                    print(f"   {result_metadata.get('executive_summary')}")
                
                if result_metadata.get('key_findings'):
                    print(f"\n🔍 Key Findings:")
                    for finding in result_metadata.get('key_findings', []):
                        print(f"   • {finding}")
                
                if result_metadata.get('anomalies'):
                    print(f"\n⚠️  Anomalies:")
                    for anomaly in result_metadata.get('anomalies', []):
                        print(f"   • {anomaly}")
                
                if result_metadata.get('recommendations'):
                    print(f"\n💡 Recommendations:")
                    for rec in result_metadata.get('recommendations', []):
                        print(f"   • {rec}")
            else:
                print(json.dumps(result_metadata, indent=2, default=str))
        
        print("\n" + "="*80)


def test_single_question(question: str, data_source_type: str = "insurance"):
    """Test a single question through the full flow"""
    print("\n" + "="*80)
    print("DATA ANALYST SINGLE QUESTION TEST")
    print("="*80)
    
    tester = DataAnalystTester()
    
    # Authenticate
    if not tester.authenticate(TEST_USER_EMAIL, TEST_USER_PASSWORD):
        print("❌ Authentication failed. Exiting.")
        return False
    
    # Submit question
    print(f"\n📤 Submitting question: {question}")
    submit_result = tester.submit_question(question, data_source_type)
    
    if not submit_result:
        print("❌ Failed to submit question")
        return False
    
    question_id = submit_result.get("question_id")
    
    # Wait for completion
    completion_result = tester.wait_for_completion(question_id, max_wait_seconds=120)
    
    if not completion_result:
        print("❌ Processing did not complete")
        return False
    
    # Handle clarification if needed
    if completion_result.get("status") == "clarification_needed":
        clarification_prompt = completion_result.get("clarification_prompt")
        print(f"\n❓ System needs clarification:")
        print(f"   {clarification_prompt}")
        
        # Provide clarification (in real usage, user would provide this)
        clarification_response = input("\n💬 Your clarification: ").strip()
        
        if clarification_response:
            tester.clarify_question(question_id, clarification_response)
            
            # Wait again for completion
            completion_result = tester.wait_for_completion(question_id, max_wait_seconds=120)
    
    # Handle confirmation if needed
    if completion_result.get("status") == "confirmation_needed":
        print(f"\n✅ System detected intent and is ready to process")
        confirmation_response = input("💬 Confirm? (yes/no): ").strip() or "yes"
        
        tester.confirm_intent(question_id, confirmation_response)
        
        # Wait again for completion
        completion_result = tester.wait_for_completion(question_id, max_wait_seconds=120)
    
    # Display results
    tester.display_results(question_id)
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Data Analyst single question flow")
    parser.add_argument(
        "--question",
        type=str,
        default="What is the total premium collected in the last quarter?",
        help="Question to test"
    )
    parser.add_argument(
        "--data-source",
        type=str,
        default="insurance",
        choices=["insurance"],
        help="Data source type"
    )
    
    args = parser.parse_args()
    
    success = test_single_question(args.question, args.data_source)
    
    sys.exit(0 if success else 1)

