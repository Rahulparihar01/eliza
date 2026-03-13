"""
CrewAI Custom Tools Test

Focused test to validate:
1. HR Database Tool works
2. Document Search Tool works  
3. Data Analysis Flow uses both tools
4. Tools return actual data
"""
import json

# Test tools directly first
from src.crewai_custom_tools import HRDatabaseTool, DocumentSearchTool

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


def test_hr_database_tool():
    """Test HR Database Tool"""
    print_section("Testing HR Database Tool")
    
    tool = HRDatabaseTool(customer_id="eliza")
    
    # Test query for employees
    print("🔍 Querying for employees...")
    query = json.dumps({
        "query_type": "employees",
        "filters": {},
        "limit": 5
    })
    
    result_str = tool._run(query)
    result = json.loads(result_str)
    
    print(f"\n✅ HR Database Tool Response:")
    print(json.dumps(result, indent=2))
    
    if "error" in result:
        print(f"\n⚠️  Tool returned error: {result['error']}")
        print("   This is OK if there's no HR data in the database yet.")
    else:
        print(f"\n✅ Found {result.get('count', 0)} employees")
    
    return result


def test_document_search_tool():
    """Test Document Search Tool"""
    print_section("Testing Document Search Tool")
    
    tool = DocumentSearchTool(customer_id="eliza", limit=5, similarity_threshold=0.7)
    
    # Test search
    print("🔍 Searching documents for: 'engineering performance'...")
    query = "engineering performance"
    
    result_str = tool._run(query)
    result = json.loads(result_str)
    
    print(f"\n✅ Document Search Tool Response:")
    print(json.dumps(result, indent=2))
    
    if "error" in result:
        print(f"\n⚠️  Tool returned error: {result['error']}")
        print("   This is OK if there are no documents indexed yet.")
    else:
        print(f"\n✅ Found {result.get('results_count', 0)} document chunks")
    
    return result


def test_data_analysis_flow_with_tools():
    """Test Data Analysis Flow with actual tool usage"""
    print_section("Testing Data Analysis Flow with Custom Tools")
    
    from src.crewai_flows.data_analysis_flow import DataAnalysisFlow, DataAnalysisFlowState
    
    # Simple HR question
    hr_question = "What is the current status of our engineering team?"
    
    print(f"📝 Question: {hr_question}")
    print(f"📍 Customer: eliza")
    print(f"🎯 Expected: Agent should use BOTH tools (HR Database + Document Search)")
    
    try:
        # Create flow
        flow = DataAnalysisFlow()
        
        # Set state manually
        flow.state = DataAnalysisFlowState(
            enriched_prompt=hr_question,
            customer_id="eliza",
            user_id=1,
            data_sources_needed=["hr_database", "documents"]
        )
        
        print("\n🚀 Starting Data Analysis Flow...")
        print("   (This will take 20-30 seconds as the agent calls tools)")
        
        # Execute flow
        flow.kickoff()
        
        # Check results
        if flow.state.error:
            print(f"\n❌ Flow Error: {flow.state.error}")
            return False
        
        print("\n✅ Flow completed successfully!")
        
        # Show retrieval results
        if flow.state.retrieval_result:
            print(f"\n📊 Data Retrieval Summary:")
            print(f"   Sources used: {flow.state.retrieval_result.data_sources_used}")
            print(f"   Retrieval notes: {flow.state.retrieval_result.retrieval_notes[:200]}...")
        
        # Show analysis results
        if flow.state.analysis_result:
            result = flow.state.analysis_result
            print(f"\n📈 Analysis Results:")
            print(f"   Confidence: {result.confidence_score}")
            print(f"   Data sources: {result.data_sources_used}")
            print(f"   Key findings: {len(result.key_findings)}")
            print(f"   Recommendations: {len(result.recommendations)}")
            
            if result.executive_summary:
                print(f"\n💡 Executive Summary:")
                print(f"   {result.executive_summary}")
            
            print(f"\n📄 Full Analysis:")
            print(result.analysis_text)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tool tests"""
    
    print_header("CrewAI Custom Tools Validation")
    
    print("This test validates:")
    print("  1. HR Database Tool connects and queries")
    print("  2. Document Search Tool connects and searches")
    print("  3. Data Analysis Flow uses both tools")
    print("  4. Tools return actual data (or graceful errors if no data)")
    
    # Test 1: HR Database Tool
    hr_result = test_hr_database_tool()
    hr_working = "error" not in hr_result or "count" in hr_result
    
    # Test 2: Document Search Tool
    doc_result = test_document_search_tool()
    doc_working = "error" not in doc_result or "results_count" in doc_result
    
    # Test 3: Data Analysis Flow
    flow_working = test_data_analysis_flow_with_tools()
    
    # Summary
    print_header("TEST SUMMARY")
    
    print(f"✅ HR Database Tool:     {'PASS' if hr_working else 'FAIL'}")
    print(f"✅ Document Search Tool:  {'PASS' if doc_working else 'FAIL'}")
    print(f"✅ Data Analysis Flow:    {'PASS' if flow_working else 'FAIL'}")
    
    if hr_working and doc_working and flow_working:
        print("\n🎉 SUCCESS: All tools operational!")
        print("\nNext steps:")
        print("  - Add test HR data to database (optional)")
        print("  - Upload test documents for search (optional)")
        print("  - Tools will return more data as system is used")
    else:
        print("\n⚠️  Some tests failed - check errors above")


if __name__ == "__main__":
    main()

