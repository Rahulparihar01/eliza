#!/usr/bin/env python3
"""
Quick test of Claude 3.5 Sonnet for Synthesis Agent
Tests that the LLM provider is configured correctly and can generate responses.
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from src.services.talent.synthesis_agent import SynthesisAgentService, SynthesisInput
from src.models.talent_analysis import (
    DiagnosticReport, AttributePriority, CandidateScore,
    DimensionScore
)

def test_synthesis_agent():
    """Test that Claude synthesis agent works"""
    print("Testing Claude 3.5 Sonnet for Synthesis Agent...")
    print("=" * 60)
    
    # Create minimal test data
    diagnostic = DiagnosticReport(
        attribute_priorities=[
            AttributePriority(attribute="Python", weight=0.9, rationale="Core skill"),
            AttributePriority(attribute="PyTorch", weight=0.8, rationale="Key framework"),
        ],
        required_skills=["Python", "PyTorch"],
        preferred_skills=["MLOps"],
        experience_requirements="5+ years ML experience",
        key_patterns=["Startup experience", "PhD in ML"]
    )
    
    # Create mock applicant scores
    applicant_scores = [
        CandidateScore(
            candidate_id="resume_01.pdf",
            candidate_name="John Doe",
            overall_score=8.5,
            dimension_scores=[
                DimensionScore(dimension="skills", score=9.0, weight=0.3),
                DimensionScore(dimension="experience", score=8.0, weight=0.25),
                DimensionScore(dimension="education", score=8.5, weight=0.15),
            ],
            rationale="Strong Python and PyTorch skills, startup experience"
        ),
        CandidateScore(
            candidate_id="resume_02.pdf",
            candidate_name="Jane Smith",
            overall_score=8.2,
            dimension_scores=[
                DimensionScore(dimension="skills", score=8.5, weight=0.3),
                DimensionScore(dimension="experience", score=8.5, weight=0.25),
                DimensionScore(dimension="education", score=9.0, weight=0.15),
            ],
            rationale="PhD in ML, strong fundamentals"
        )
    ]
    
    # Create mock market scores
    market_scores = [
        CandidateScore(
            candidate_id="pdl_abc123",
            candidate_name="Alice Johnson",
            overall_score=8.8,
            dimension_scores=[
                DimensionScore(dimension="skills", score=9.2, weight=0.3),
                DimensionScore(dimension="experience", score=9.0, weight=0.25),
                DimensionScore(dimension="education", score=8.0, weight=0.15),
            ],
            rationale="Exceptional PyTorch expertise, FAANG experience"
        )
    ]
    
    # Initialize synthesis agent
    print("\n1. Initializing SynthesisAgentService...")
    print("   Provider: anthropic")
    print("   Model: claude-3-5-sonnet-20241022")
    
    synthesis_agent = SynthesisAgentService(
        customer_id="test_customer",
        user_id=1,
        llm_provider="anthropic",
        llm_model="claude-3-5-sonnet-20241022"
    )
    
    print("   ✅ Agent initialized successfully")
    
    # Create synthesis input
    print("\n2. Creating synthesis input...")
    synthesis_input = SynthesisInput(
        diagnostic_report=diagnostic,
        applicant_scores=applicant_scores,
        market_scores=market_scores,
        top_overall_count=3
    )
    print("   ✅ Input created")
    
    # Run synthesis
    print("\n3. Running synthesis (calling Claude API)...")
    print("   This may take 20-30 seconds...")
    
    try:
        result = synthesis_agent.synthesize(synthesis_input)
        
        print("\n" + "=" * 60)
        print("✅ SYNTHESIS COMPLETE!")
        print("=" * 60)
        
        print(f"\n📊 Top {len(result.top_overall_candidate_ids)} Overall Candidates:")
        for i, candidate_id in enumerate(result.top_overall_candidate_ids, 1):
            print(f"   {i}. {candidate_id}")
        
        print(f"\n📝 Executive Summary (first 200 chars):")
        print(f"   {result.executive_summary[:200]}...")
        
        print(f"\n🔍 Key Patterns ({len(result.key_patterns)} found):")
        for pattern in result.key_patterns[:3]:
            print(f"   - {pattern}")
        
        print(f"\n🎯 Sourcing Recommendations ({len(result.sourcing_recommendations)} found):")
        for rec in result.sourcing_recommendations[:3]:
            print(f"   - {rec}")
        
        print("\n" + "=" * 60)
        print("✅ Claude 3.5 Sonnet is working perfectly!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ SYNTHESIS FAILED!")
        print("=" * 60)
        print(f"\nError: {str(e)}")
        print(f"\nError type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_synthesis_agent()
    sys.exit(0 if success else 1)


