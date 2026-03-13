#!/usr/bin/env python3
"""
Simple CrewAI test with OpenAI integration.
Tests basic Agent and Task creation with the configured LLM.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from crewai import Agent, Task, Crew, Process
from src.core.config import get_settings
from src.core.logging import get_logger, setup_logging

logger = get_logger(__name__, component="test_crewai")


def test_basic_agent():
    """Test basic CrewAI agent with OpenAI."""
    
    print("\n" + "="*80)
    print("🤖 CrewAI + OpenAI Basic Agent Test")
    print("="*80 + "\n")
    
    # Setup
    settings = get_settings()
    setup_logging(settings)
    
    # Verify OpenAI configuration
    print(f"📋 Configuration:")
    print(f"   - LLM Model: {settings.DEFAULT_LLM_MODEL}")
    print(f"   - OpenAI API Key: {'✓ Set (' + settings.OPENAI_API_KEY[:20] + '...)' if settings.OPENAI_API_KEY else '✗ Missing'}")
    print(f"   - API Base URL: {settings.OPENAI_API_BASE_URL}")
    print()
    
    if not settings.OPENAI_API_KEY:
        print("❌ ERROR: OPENAI_API_KEY is not set!")
        print("   Please set it in your .env file or environment variables.")
        return False
    
    # Configure LLM
    from crewai import LLM
    
    llm = LLM(
        model=settings.DEFAULT_LLM_MODEL,
        temperature=0.7,
        base_url=settings.OPENAI_API_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
    )
    
    print("🔧 Creating AI Agent...")
    try:
        # Create a business analyst agent
        analyst = Agent(
            role="Business Analyst",
            goal="Analyze business problems and provide actionable insights",
            backstory=(
                "You are an experienced business analyst with expertise in "
                "process improvement, data analysis, and strategic planning. "
                "You excel at breaking down complex problems into manageable steps."
            ),
            llm=llm,
            verbose=True,
        )
        print("✓ Agent created successfully\n")
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        return False
    
    # Test task
    print("📝 Test Problem:")
    problem = "Our e-commerce platform has a 30% cart abandonment rate at the payment step. How can we improve this?"
    print(f"   {problem}")
    print()
    
    # Create analysis task
    print("🔧 Creating Analysis Task...")
    try:
        analysis_task = Task(
            description=f"""
            Analyze the following business problem and provide a comprehensive solution:
            
            Problem: {problem}
            
            Please provide:
            1. Root cause analysis (3-5 potential causes)
            2. Recommended solutions (3-5 specific actions)
            3. Expected impact of each solution
            4. Implementation priority (1-5, with 1 being highest)
            5. Estimated effort (low, medium, high)
            
            Format your response as a structured analysis.
            """,
            expected_output="Structured business analysis with root causes, solutions, impact, and priorities",
            agent=analyst,
        )
        print("✓ Task created successfully\n")
    except Exception as e:
        print(f"❌ Failed to create task: {e}")
        return False
    
    # Create and run crew
    print("🚀 Starting AI Analysis...")
    print("-" * 80)
    
    try:
        crew = Crew(
            agents=[analyst],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True,
        )
        
        result = crew.kickoff()
        
        print("-" * 80)
        print("✅ Analysis Completed Successfully!\n")
        
        # Display result
        print("📊 ANALYSIS RESULT:")
        print("="*80)
        print(result)
        print("="*80 + "\n")
        
        print("✅ TEST PASSED: CrewAI is working with OpenAI!")
        print("   - Agent created and configured")
        print("   - Task executed successfully")
        print("   - LLM responded with analysis")
        print()
        
        return True
        
    except Exception as e:
        print("-" * 80)
        print(f"❌ Analysis Failed: {e}")
        print(f"   Error Type: {type(e).__name__}")
        
        # Check for common issues
        error_str = str(e)
        if "401" in error_str or "authentication" in error_str.lower():
            print("\n💡 SUGGESTION: Your OpenAI API key may be invalid or expired.")
        elif "quota" in error_str.lower() or "rate" in error_str.lower():
            print("\n💡 SUGGESTION: You may have exceeded your OpenAI API quota or rate limit.")
        elif "model" in error_str.lower() and "gpt-4o-mini" in error_str.lower():
            print(f"\n💡 SUGGESTION: The model 'gpt-4o-mini' may not be available.")
            print("   Try changing DEFAULT_LLM_MODEL to 'gpt-4' or 'gpt-3.5-turbo' in your .env file.")
        elif "model" in error_str.lower():
            print(f"\n💡 SUGGESTION: The model '{settings.DEFAULT_LLM_MODEL}' may not be available.")
            print("   Check your OpenAI account for model access.")
        
        logger.error("CrewAI test failed", exception=e)
        
        # Print full traceback for debugging
        import traceback
        print("\n🔍 Full Error Details:")
        print("-" * 80)
        traceback.print_exc()
        print("-" * 80)
        
        return False


def main():
    """Run test."""
    
    print("\n" + "🎯 " * 20)
    print("CrewAI + OpenAI Integration Test")
    print("🎯 " * 20)
    
    success = test_basic_agent()
    
    print("\n" + "="*80)
    if success:
        print("🎉 SUCCESS: CrewAI is fully operational with OpenAI!")
        print("\nNext Steps:")
        print("  - The task enrichment and data analysis flows are ready to use")
        print("  - Agents can be called via API endpoints")
        print("  - CrewAI will use your configured OpenAI model for all LLM tasks")
    else:
        print("❌ TEST FAILED: See error details above")
        print("\nTroubleshooting:")
        print("  1. Verify your OpenAI API key is correct")
        print("  2. Check if your API key has sufficient credits")
        print("  3. Ensure you have access to the specified model")
        print("  4. Try a different model (gpt-4, gpt-3.5-turbo)")
    print("="*80 + "\n")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

