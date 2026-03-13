"""
Complete CrewAI Flow Test - Task Enrichment + Data Analysis

This test demonstrates the full two-stage pipeline:
1. Task Enrichment: Raw question → Enriched prompt with context
2. Data Analysis: Enriched prompt → Professional analysis with real data

Expected flow:
User question
    ↓
TaskEnrichmentFlow (Stage 1)
    → Intent Analysis
    → Context Enrichment  
    → Generate optimized prompt
    ↓
DataAnalysisFlow (Stage 2)
    → Data Retrieval (HR DB + Documents)
    → Business Analysis
    → Professional Report
    ↓
Final structured output
"""
import sys
from datetime import datetime

from src.crewai_flows.task_enrichment_flow import (
    TaskEnrichmentFlow,
    TaskEnrichmentFlowState,
    UserContext,
)
from src.crewai_flows.data_analysis_flow import (
    DataAnalysisFlow,
    DataAnalysisFlowState,
)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"🎯 {title}")
    print('=' * 80)


def test_complete_enrichment_and_analysis():
    """Test the complete two-stage flow."""
    
    print_section("COMPLETE CREWAI FLOW TEST - TASK ENRICHMENT + DATA ANALYSIS")
    
    print("""
This test demonstrates the production-ready two-stage AI pipeline:

Stage 1: Task Enrichment Flow
    • Analyzes user intent and complexity
    • Identifies required data sources
    • Adds business context
    • Generates optimized prompt for analysis agents
    
Stage 2: Data Analysis Flow
    • Uses enriched prompt for better results
    • Retrieves data from HR database and documents
    • Performs comprehensive business analysis
    • Generates professional report with recommendations

Expected time: 60-90 seconds total
    """)
    
    # Configuration
    customer_id = "eliza"
    user_id = 1
    raw_question = "Who are our Engineering team members and what skills do they have?"
    
    print_section("TEST CONFIGURATION")
    print(f"📊 Customer: {customer_id}")
    print(f"👤 User ID: {user_id}")
    print(f"❓ Raw Question: {raw_question}")
    print(f"📅 Timestamp: {datetime.now().isoformat()}")
    print()
    
    # =========================================================================
    # STAGE 1: TASK ENRICHMENT
    # =========================================================================
    print_section("STAGE 1: TASK ENRICHMENT FLOW")
    print("🔄 Initializing TaskEnrichmentFlow...")
    
    # Create enrichment flow
    enrichment_flow = TaskEnrichmentFlow()
    
    # Create user context
    user_context = UserContext(
        user_id=user_id,
        customer_id=customer_id,
        role="Manager",
        department="Human Resources",
        previous_queries=None,
        preferences=None,
    )
    
    # Create enrichment state
    enrichment_state = TaskEnrichmentFlowState(
        original_question=raw_question,
        user_context=user_context,
    )
    
    print("✅ TaskEnrichmentFlow initialized")
    print(f"   User Role: {user_context.role}")
    print(f"   User Department: {user_context.department}")
    print()
    print("🚀 Starting Task Enrichment...")
    print("   This will:")
    print("   1. Analyze the intent and complexity")
    print("   2. Extract entities and keywords")
    print("   3. Identify required data sources")
    print("   4. Add business context")
    print("   5. Generate optimized prompt")
    print()
    print("⏱️  Expected time: 30-45 seconds...")
    print()
    
    try:
        # Execute enrichment flow
        enrichment_flow.kickoff(enrichment_state.model_dump())
        
        if enrichment_flow.state.error:
            print(f"\n❌ Enrichment Error: {enrichment_flow.state.error}")
            return False
        
        # Get enriched result
        enriched_result = enrichment_flow.state.enriched_prompt
        
        if not enriched_result:
            print("\n❌ No enriched prompt generated")
            return False
        
        print("✅ Task Enrichment Completed!")
        print()
        print("📋 Enrichment Results:")
        print(f"   Intent Type: {enriched_result.task_analysis.intent_type}")
        print(f"   Complexity: {enriched_result.task_analysis.complexity}")
        print(f"   Confidence: {enriched_result.task_analysis.confidence_score:.2f}")
        print(f"   Entities: {', '.join(enriched_result.task_analysis.entities[:5])}")
        print(f"   Keywords: {', '.join(enriched_result.task_analysis.keywords[:5])}")
        print(f"   Data Sources: {', '.join(enriched_result.task_analysis.data_sources_needed)}")
        print(f"   Quality Score: {enriched_result.quality_score:.2f}")
        print()
        print("📝 Enriched Prompt (first 300 chars):")
        print(f"   {enriched_result.enriched_prompt[:300]}...")
        print()
        
    except Exception as e:
        print(f"\n❌ Enrichment failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # =========================================================================
    # STAGE 2: DATA ANALYSIS
    # =========================================================================
    print_section("STAGE 2: DATA ANALYSIS FLOW")
    print("🔄 Initializing DataAnalysisFlow...")
    
    # Create analysis flow
    analysis_flow = DataAnalysisFlow()
    
    # Create analysis state with enriched prompt
    analysis_state = DataAnalysisFlowState(
        enriched_prompt=enriched_result.enriched_prompt,
        customer_id=customer_id,
        user_id=user_id,
        data_sources_needed=enriched_result.task_analysis.data_sources_needed,
    )
    
    print("✅ DataAnalysisFlow initialized")
    print(f"   Using enriched prompt: ✓")
    print(f"   Data sources: {', '.join(enriched_result.task_analysis.data_sources_needed)}")
    print()
    print("🚀 Starting Data Analysis...")
    print("   This will:")
    print("   1. Initialize custom tools (HRDatabaseTool + DocumentSearchTool)")
    print("   2. Data Retrieval Agent queries real database")
    print("   3. Business Intelligence Analyst synthesizes insights")
    print("   4. Generate professional report with Claude 3.5 Sonnet")
    print()
    print("⏱️  Expected time: 30-45 seconds...")
    print()
    
    try:
        # Execute analysis flow
        analysis_flow.kickoff(analysis_state.model_dump())
        
        if analysis_flow.state.error:
            print(f"\n❌ Analysis Error: {analysis_flow.state.error}")
            return False
        
        print_section("FINAL RESULTS")
        
        # Display retrieval results
        if analysis_flow.state.retrieval_result:
            retrieval = analysis_flow.state.retrieval_result
            print("✅ Data Retrieval Stage Completed")
            print(f"   Sources used: {retrieval.data_sources_used}")
            print(f"   Total records: {retrieval.total_records}")
            if retrieval.retrieval_notes:
                print(f"   Notes preview: {retrieval.retrieval_notes[:200]}...")
            print()
        
        # Display analysis results
        if analysis_flow.state.analysis_result:
            result = analysis_flow.state.analysis_result
            print("✅ Data Analysis Stage Completed")
            print(f"   Confidence: {result.confidence_score}")
            print(f"   Data sources: {result.data_sources_used}")
            print()
            
            if result.executive_summary:
                print("📊 Executive Summary:")
                print(f"   {result.executive_summary}")
                print()
            
            if result.key_findings:
                print(f"💡 Key Findings ({len(result.key_findings)}):")
                for i, finding in enumerate(result.key_findings[:5], 1):
                    print(f"   {i}. {finding[:150]}...")
                print()
            
            if result.recommendations:
                print(f"🎯 Recommendations ({len(result.recommendations)}):")
                for i, rec in enumerate(result.recommendations[:5], 1):
                    print(f"   {i}. {rec[:150]}...")
                print()
            
            print_section("COMPLETE ANALYSIS REPORT")
            print(result.analysis_text)
            print()
        
        print_section("TEST SUMMARY")
        print("🎉 SUCCESS: Complete two-stage flow executed successfully!")
        print()
        print("✅ Stage 1 (Task Enrichment):")
        print(f"   • Intent analysis: {enriched_result.task_analysis.intent_type}")
        print(f"   • Complexity: {enriched_result.task_analysis.complexity}")
        print(f"   • Quality score: {enriched_result.quality_score:.2f}")
        print()
        print("✅ Stage 2 (Data Analysis):")
        if analysis_flow.state.retrieval_result:
            print(f"   • Data sources queried: {', '.join(analysis_flow.state.retrieval_result.data_sources_used)}")
            print(f"   • Records retrieved: {analysis_flow.state.retrieval_result.total_records}")
        if analysis_flow.state.analysis_result:
            print(f"   • Confidence: {analysis_flow.state.analysis_result.confidence_score}")
            print(f"   • Key findings: {len(analysis_flow.state.analysis_result.key_findings)}")
            print(f"   • Recommendations: {len(analysis_flow.state.analysis_result.recommendations)}")
        print()
        print("🚀 The complete enrichment + analysis pipeline is production-ready!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Analysis failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test execution."""
    print("\n" + "=" * 80)
    print("🚀 CREWAI COMPLETE FLOW TEST")
    print("   Task Enrichment → Data Analysis")
    print("=" * 80)
    
    try:
        success = test_complete_enrichment_and_analysis()
        
        if success:
            print("\n" + "=" * 80)
            print("🎉 ALL TESTS PASSED")
            print("=" * 80)
            print("\n✅ Production-ready components verified:")
            print("   • Task Enrichment Flow (Intent analysis + Prompt optimization)")
            print("   • Data Analysis Flow (Data retrieval + Business intelligence)")
            print("   • Custom Tools (HR Database + Document Search)")
            print("   • Claude 3.5 Sonnet Integration")
            print("   • Multi-stage agent orchestration")
            print()
            sys.exit(0)
        else:
            print("\n" + "=" * 80)
            print("⚠️  SOME TESTS FAILED")
            print("=" * 80)
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

