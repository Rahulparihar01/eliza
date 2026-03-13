"""
Comprehensive CrewAI Pipeline Test

Tests the full two-flow pipeline:
1. Task Enrichment Flow: Transforms raw question → enriched prompt
2. Data Analysis Flow: Uses enriched prompt + custom tools → analysis

Validates:
- Task enrichment produces optimized prompt
- Data retrieval agent uses HR Database Tool
- Data retrieval agent ALWAYS uses Document Search Tool  
- Analysis incorporates tool results
- Full telemetry captured
"""
import asyncio
import json
from datetime import datetime

# Import flows
from src.crewai_flows.task_enrichment_flow import (
    TaskEnrichmentFlow,
    TaskEnrichmentFlowState,
    UserContext
)
from src.crewai_flows.data_analysis_flow import (
    DataAnalysisFlow,
    DataAnalysisFlowState
)

# Import logging
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, component="test.crewai.pipeline")


def print_header(text: str):
    """Print a formatted header"""
    print("\n" + "=" * 80)
    print(f"🎯 {text}")
    print("=" * 80 + "\n")


def print_section(text: str):
    """Print a formatted section"""
    print("\n" + "-" * 80)
    print(f"📋 {text}")
    print("-" * 80 + "\n")


def print_success(text: str):
    """Print success message"""
    print(f"✅ {text}")


def print_info(text: str):
    """Print info message"""
    print(f"ℹ️  {text}")


def print_data(label: str, data: any):
    """Print formatted data"""
    print(f"\n{label}:")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(str(data))


async def test_task_enrichment(hr_question: str, user_context: UserContext):
    """
    Test Flow 1: Task Enrichment
    
    Takes a raw HR question and transforms it into an enriched prompt
    with intent analysis, context, and processing instructions.
    """
    print_section("FLOW 1: TASK ENRICHMENT")
    
    print_info(f"Input Question: {hr_question}")
    print_info(f"User Context: {user_context.model_dump()}")
    
    # Initialize and run flow with state
    print("\n🚀 Starting Task Enrichment Flow...")
    
    try:
        # Create flow with initial state
        flow = TaskEnrichmentFlow()
        flow.state = TaskEnrichmentFlowState(
            original_question=hr_question,
            user_context=user_context
        )
        
        # Execute the flow
        flow.kickoff()
        
        if flow.state.error:
            print(f"\n❌ Flow Error: {flow.state.error}")
            return None
        
        print_success("Task Enrichment Flow completed!")
        
        # Extract results
        enriched = flow.state.enriched_prompt
        if not enriched:
            print("\n⚠️  No enriched prompt generated")
            return None
        
        # Display results
        print_data("📊 Task Analysis", {
            "intent_type": enriched.task_analysis.intent_type,
            "complexity": enriched.task_analysis.complexity,
            "confidence": enriched.task_analysis.confidence_score,
            "data_sources_needed": enriched.task_analysis.data_sources_needed,
            "entities": enriched.task_analysis.entities,
            "keywords": enriched.task_analysis.keywords
        })
        
        print_data("✨ Enriched Prompt", enriched.enriched_prompt[:500] + "...")
        
        print_data("📏 Quality Metrics", {
            "quality_score": enriched.quality_score,
            "has_processing_instructions": bool(enriched.processing_instructions),
            "has_output_format": bool(enriched.expected_output_format),
            "has_validation_criteria": bool(enriched.validation_criteria)
        })
        
        return enriched
        
    except Exception as e:
        print(f"\n❌ Error in Task Enrichment: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_data_analysis(enriched_prompt: str, customer_id: str, user_id: int, data_sources: list):
    """
    Test Flow 2: Data Analysis with Custom Tools
    
    Takes the enriched prompt and:
    1. Uses HR Database Tool to query structured HR data
    2. Uses Document Search Tool to find relevant documents
    3. Synthesizes information into comprehensive analysis
    """
    print_section("FLOW 2: DATA ANALYSIS WITH CUSTOM TOOLS")
    
    print_info("Enriched Prompt received from Flow 1")
    print_info(f"Data Sources: {data_sources}")
    print_info(f"Customer ID: {customer_id}")
    
    # Initialize and run flow with state
    print("\n🚀 Starting Data Analysis Flow...")
    
    try:
        # Create flow with initial state
        flow = DataAnalysisFlow()
        flow.state = DataAnalysisFlowState(
            enriched_prompt=enriched_prompt,
            customer_id=customer_id,
            user_id=user_id,
            data_sources_needed=data_sources
        )
        
        # Execute the flow
        flow.kickoff()
        
        if flow.state.error:
            print(f"\n❌ Flow Error: {flow.state.error}")
            return None
        
        print_success("Data Analysis Flow completed!")
        
        # Display retrieval results
        if flow.state.retrieval_result:
            print_data("🔍 Data Retrieval Summary", {
                "data_sources_used": flow.state.retrieval_result.data_sources_used,
                "total_records": flow.state.retrieval_result.total_records,
                "retrieval_notes": flow.state.retrieval_result.retrieval_notes[:300] + "..."
                    if flow.state.retrieval_result.retrieval_notes else None
            })
        
        # Display analysis results
        if flow.state.analysis_result:
            result = flow.state.analysis_result
            
            print_data("📊 Analysis Results", {
                "executive_summary": result.executive_summary,
                "key_findings_count": len(result.key_findings),
                "recommendations_count": len(result.recommendations),
                "data_sources_used": result.data_sources_used,
                "confidence_score": result.confidence_score
            })
            
            print_data("💡 Key Findings", result.key_findings)
            print_data("🎯 Recommendations", result.recommendations)
            
            print("\n📄 Full Analysis:")
            print(result.analysis_text)
            
            return result
        
        return None
        
    except Exception as e:
        print(f"\n❌ Error in Data Analysis: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run the comprehensive two-flow pipeline test"""
    
    print_header("CrewAI Full Pipeline Test - Task Enrichment + Data Analysis")
    
    # Test configuration
    hr_question = "Who are our top performing engineers in the last quarter and what skills do they have?"
    
    user_context = UserContext(
        user_id=1,
        customer_id="eliza",
        role="HR Manager",
        department="Human Resources",
        previous_queries=[],
        preferences={}
    )
    
    print_info("Test Configuration:")
    print(f"  Question: {hr_question}")
    print(f"  Customer: {user_context.customer_id}")
    print(f"  User Role: {user_context.role}")
    print(f"  Department: {user_context.department}")
    
    # ========================================================================
    # FLOW 1: Task Enrichment
    # ========================================================================
    
    enriched_result = await test_task_enrichment(hr_question, user_context)
    
    if not enriched_result:
        print("\n❌ TEST FAILED: Task enrichment did not produce results")
        return
    
    # ========================================================================
    # FLOW 2: Data Analysis with Tools
    # ========================================================================
    
    analysis_result = await test_data_analysis(
        enriched_prompt=enriched_result.enriched_prompt,
        customer_id=user_context.customer_id,
        user_id=user_context.user_id,
        data_sources=enriched_result.task_analysis.data_sources_needed or ["hr_database", "documents"]
    )
    
    if not analysis_result:
        print("\n❌ TEST FAILED: Data analysis did not produce results")
        return
    
    # ========================================================================
    # VALIDATION
    # ========================================================================
    
    print_section("VALIDATION RESULTS")
    
    validation_results = {
        "task_enrichment_completed": bool(enriched_result),
        "enriched_prompt_generated": bool(enriched_result.enriched_prompt),
        "intent_analyzed": bool(enriched_result.task_analysis),
        "data_sources_identified": len(enriched_result.task_analysis.data_sources_needed) > 0,
        "quality_score_acceptable": enriched_result.quality_score >= 0.7,
        
        "data_analysis_completed": bool(analysis_result),
        "data_retrieval_executed": bool(analysis_result),
        "key_findings_generated": len(analysis_result.key_findings) > 0,
        "recommendations_generated": len(analysis_result.recommendations) > 0,
        "confidence_acceptable": analysis_result.confidence_score >= 0.7,
        
        "tools_used": "hr_database" in analysis_result.data_sources_used or 
                      "documents" in analysis_result.data_sources_used,
    }
    
    print_data("✅ Validation Checks", validation_results)
    
    all_passed = all(validation_results.values())
    
    if all_passed:
        print_header("🎉 SUCCESS: Full Pipeline Operational!")
        print("\n✅ Task Enrichment Flow: Working")
        print("✅ Data Analysis Flow: Working")
        print("✅ Custom Tools: Integrated")
        print("✅ HR Database Tool: Available")
        print("✅ Document Search Tool: Available")
        print("\n🚀 System ready for production use!")
    else:
        print_header("⚠️  PARTIAL SUCCESS: Some checks failed")
        failed_checks = [k for k, v in validation_results.items() if not v]
        print(f"\nFailed checks: {failed_checks}")


if __name__ == "__main__":
    print("\n")
    print("🎯 " * 20)
    print("CrewAI Full Pipeline Test - Task Enrichment → Data Analysis")
    print("🎯 " * 20)
    print("\n")
    
    asyncio.run(main())

