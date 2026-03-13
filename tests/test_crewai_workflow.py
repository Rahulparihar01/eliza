#!/usr/bin/env python3
"""
Test script for CrewAI workflow with OpenAI integration.
Tests the task enrichment flow end-to-end.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import get_settings
from src.crewai_flows.task_enrichment_flow import TaskEnrichmentFlow
from src.core.logging import get_logger, setup_logging

logger = get_logger(__name__, component="test_crewai")


async def test_task_enrichment():
    """Test the task enrichment CrewAI flow with OpenAI."""
    
    print("\n" + "="*80)
    print("🚀 CrewAI + OpenAI Integration Test")
    print("="*80 + "\n")
    
    # Setup
    settings = get_settings()
    setup_logging(settings)
    
    # Verify OpenAI configuration
    print(f"📋 Configuration:")
    print(f"   - LLM Model: {settings.DEFAULT_LLM_MODEL}")
    print(f"   - OpenAI API Key: {'✓ Set' if settings.OPENAI_API_KEY else '✗ Missing'}")
    print(f"   - API Base URL: {settings.OPENAI_API_BASE_URL}")
    print()
    
    if not settings.OPENAI_API_KEY:
        print("❌ ERROR: OPENAI_API_KEY is not set!")
        print("   Please set it in your .env file or environment variables.")
        return False
    
    # Test input
    test_task = {
        "title": "Improve customer onboarding experience",
        "description": "We need to reduce the time it takes for new customers to complete their first purchase. Currently taking 7 days on average.",
        "context": "E-commerce platform with 10k monthly active users",
        "priority": "high"
    }
    
    print("📝 Test Input:")
    print(f"   Title: {test_task['title']}")
    print(f"   Description: {test_task['description']}")
    print(f"   Context: {test_task['context']}")
    print(f"   Priority: {test_task['priority']}")
    print()
    
    # Initialize the flow with required state
    print("🔧 Initializing TaskEnrichmentFlow...")
    try:
        # Create initial state
        initial_state = {
            "original_question": test_task['title'],
            "user_context": {
                "user_id": "test_user",
                "customer_id": "test_customer"
            }
        }
        flow = TaskEnrichmentFlow(initial_state=initial_state)
        print("✓ Flow initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize flow: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Run the enrichment
    print("🤖 Starting AI Enrichment Process...")
    print("-" * 80)
    
    try:
        result = await flow.enrich_task(
            task_title=test_task['title'],
            task_description=test_task['description'],
            task_context=test_task['context'],
            task_priority=test_task['priority']
        )
        
        print("-" * 80)
        print("✅ Enrichment Completed Successfully!\n")
        
        # Display results
        print("📊 ENRICHMENT RESULTS:")
        print("="*80)
        
        if result.get('analysis'):
            print("\n🔍 TASK ANALYSIS:")
            print(result['analysis'])
        
        if result.get('requirements'):
            print("\n📋 REQUIREMENTS:")
            for i, req in enumerate(result['requirements'], 1):
                print(f"   {i}. {req}")
        
        if result.get('acceptance_criteria'):
            print("\n✓ ACCEPTANCE CRITERIA:")
            for i, criterion in enumerate(result['acceptance_criteria'], 1):
                print(f"   {i}. {criterion}")
        
        if result.get('estimated_effort'):
            print(f"\n⏱️  ESTIMATED EFFORT: {result['estimated_effort']}")
        
        if result.get('recommended_skills'):
            print(f"\n🎯 RECOMMENDED SKILLS: {', '.join(result['recommended_skills'])}")
        
        if result.get('risks'):
            print("\n⚠️  IDENTIFIED RISKS:")
            for i, risk in enumerate(result['risks'], 1):
                print(f"   {i}. {risk}")
        
        if result.get('dependencies'):
            print(f"\n🔗 DEPENDENCIES: {', '.join(result['dependencies'])}")
        
        print("\n" + "="*80)
        print("✅ TEST PASSED: CrewAI workflow executed successfully with OpenAI!")
        print("="*80 + "\n")
        
        return True
        
    except Exception as e:
        print("-" * 80)
        print(f"❌ Enrichment Failed: {e}")
        print(f"   Error Type: {type(e).__name__}")
        
        # Check for common issues
        if "401" in str(e) or "authentication" in str(e).lower():
            print("\n💡 SUGGESTION: Your OpenAI API key may be invalid or expired.")
        elif "quota" in str(e).lower() or "rate" in str(e).lower():
            print("\n💡 SUGGESTION: You may have exceeded your OpenAI API quota or rate limit.")
        elif "model" in str(e).lower():
            print(f"\n💡 SUGGESTION: The model '{settings.DEFAULT_LLM_MODEL}' may not be available.")
            print("   Check your OpenAI account for model access.")
        
        logger.error("CrewAI test failed", exception=e)
        return False


async def test_data_analysis():
    """Test the data analysis CrewAI flow with OpenAI."""
    
    print("\n" + "="*80)
    print("📊 Data Analysis Flow Test")
    print("="*80 + "\n")
    
    from src.crewai_flows.data_analysis_flow import DataAnalysisFlow
    
    # Test input
    test_query = "What are the key trends in our customer onboarding data over the last quarter?"
    test_data = {
        "total_signups": 1250,
        "completed_onboarding": 875,
        "avg_completion_time_days": 7.2,
        "dropoff_rate": 30,
        "primary_dropoff_step": "payment_setup",
        "customer_segments": {
            "enterprise": 120,
            "small_business": 450,
            "individual": 680
        }
    }
    
    print("📝 Test Input:")
    print(f"   Query: {test_query}")
    print(f"   Data Points: {len(test_data)} metrics")
    print()
    
    # Initialize the flow with required state
    print("🔧 Initializing DataAnalysisFlow...")
    try:
        # Create initial state
        initial_state = {
            "enriched_prompt": test_query,
            "customer_id": "test_customer",
            "user_id": "test_user"
        }
        flow = DataAnalysisFlow(initial_state=initial_state)
        print("✓ Flow initialized successfully\n")
    except Exception as e:
        print(f"❌ Failed to initialize flow: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Run the analysis
    print("🤖 Starting AI Analysis Process...")
    print("-" * 80)
    
    try:
        result = await flow.analyze_data(
            query=test_query,
            data_context=test_data,
            analysis_type="trend_analysis"
        )
        
        print("-" * 80)
        print("✅ Analysis Completed Successfully!\n")
        
        # Display results
        print("📊 ANALYSIS RESULTS:")
        print("="*80)
        
        if result.get('insights'):
            print("\n💡 KEY INSIGHTS:")
            for i, insight in enumerate(result['insights'], 1):
                print(f"   {i}. {insight}")
        
        if result.get('recommendations'):
            print("\n🎯 RECOMMENDATIONS:")
            for i, rec in enumerate(result['recommendations'], 1):
                print(f"   {i}. {rec}")
        
        if result.get('summary'):
            print(f"\n📋 SUMMARY:")
            print(result['summary'])
        
        print("\n" + "="*80)
        print("✅ DATA ANALYSIS TEST PASSED!")
        print("="*80 + "\n")
        
        return True
        
    except Exception as e:
        print("-" * 80)
        print(f"❌ Analysis Failed: {e}")
        logger.error("Data analysis test failed", exception=e)
        return False


async def main():
    """Run all tests."""
    
    print("\n" + "🎯 " * 20)
    print("Starting CrewAI + OpenAI End-to-End Test Suite")
    print("🎯 " * 20 + "\n")
    
    results = {
        "task_enrichment": False,
        "data_analysis": False
    }
    
    # Test 1: Task Enrichment
    print("\n📋 TEST 1: Task Enrichment Flow")
    results["task_enrichment"] = await test_task_enrichment()
    
    # Small delay between tests
    await asyncio.sleep(2)
    
    # Test 2: Data Analysis
    print("\n📊 TEST 2: Data Analysis Flow")
    results["data_analysis"] = await test_data_analysis()
    
    # Summary
    print("\n" + "="*80)
    print("📊 TEST SUITE SUMMARY")
    print("="*80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_status in results.items():
        status = "✅ PASSED" if passed_status else "❌ FAILED"
        print(f"{status}: {test_name.replace('_', ' ').title()}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! CrewAI is working perfectly with OpenAI!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above for details.")
    
    print("="*80 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

