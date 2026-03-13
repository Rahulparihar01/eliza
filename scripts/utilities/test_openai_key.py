#!/usr/bin/env python3
"""
Test OpenAI API Key with GPT-4o and GPT-4o-mini
Validates that the API key can make inference requests to both models.
"""

import os
import sys
from openai import OpenAI

def test_model(client: OpenAI, model: str) -> tuple[bool, str]:
    """
    Test a specific OpenAI model.
    
    Returns:
        (success: bool, message: str)
    """
    try:
        print(f"\n{'='*60}")
        print(f"Testing {model}...")
        print(f"{'='*60}")
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello, I am working!' in exactly 5 words."}
            ],
            max_tokens=20,
            temperature=0
        )
        
        content = response.choices[0].message.content
        print(f"✓ Model: {model}")
        print(f"✓ Response: {content}")
        print(f"✓ Tokens used: {response.usage.total_tokens}")
        print(f"✓ Finish reason: {response.choices[0].finish_reason}")
        
        return True, f"Success: {content}"
        
    except Exception as e:
        error_msg = str(e)
        print(f"✗ Model: {model}")
        print(f"✗ Error: {error_msg}")
        
        # Check for specific error types
        if "quota" in error_msg.lower():
            return False, f"QUOTA EXCEEDED: {error_msg}"
        elif "invalid" in error_msg.lower() and "key" in error_msg.lower():
            return False, f"INVALID API KEY: {error_msg}"
        elif "permission" in error_msg.lower():
            return False, f"PERMISSION DENIED: {error_msg}"
        else:
            return False, f"ERROR: {error_msg}"


def main():
    """Main test function."""
    print("\n" + "="*60)
    print("OpenAI API Key Validation Test")
    print("="*60)
    
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("\n✗ ERROR: OPENAI_API_KEY environment variable not set")
        print("\nUsage:")
        print("  export OPENAI_API_KEY='your-key-here'")
        print("  python test_openai_key.py")
        sys.exit(1)
    
    print(f"\n✓ API Key found: {api_key[:20]}...{api_key[-10:]}")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)
    
    # Models to test
    models = [
        "gpt-4o-mini",  # Used for diagnostic agent (cost-effective)
        "gpt-4o"        # Used for synthesis agent (quality writing)
    ]
    
    # Test each model
    results = {}
    for model in models:
        success, message = test_model(client, model)
        results[model] = (success, message)
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}\n")
    
    all_success = True
    for model, (success, message) in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {model}")
        if not success:
            print(f"  └─ {message}")
            all_success = False
    
    print(f"\n{'='*60}")
    if all_success:
        print("✓ ALL TESTS PASSED - API key is valid and has quota")
        print("✓ Ready to run ML Talent Intelligence analysis")
        print(f"{'='*60}\n")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED - Check errors above")
        print("✗ Analysis will fail until API key issues are resolved")
        print(f"{'='*60}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()


