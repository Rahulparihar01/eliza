"""
Test ML Talent Intelligence pipeline with a single resume.

This test traces one resume through the entire flow:
1. Parse resume with Docling VLM
2. Build baseline profile
3. Run diagnostic agent
4. Score the candidate
5. Verify the complete flow

Purpose: Debug why 50 resumes parse successfully but result in 0 candidates.
"""
import asyncio
import os
from pathlib import Path
import structlog

from src.services.talent.orchestrator import TalentIntelligenceOrchestrator, TalentAnalysisRequest
from src.services.talent.docling_vlm_parser import DoclingVLMParser
from src.services.talent.diagnostic_agent import DiagnosticAgentService
from src.services.talent.scoring_engine import MultiDimensionalScoringEngine
from src.models.talent_analysis import CandidateSource

logger = structlog.get_logger(__name__)


async def test_single_resume_full_pipeline():
    """Test complete pipeline with one real resume."""
    
    print("\n" + "="*80)
    print("🧪 TESTING ML TALENT PIPELINE WITH SINGLE RESUME")
    print("="*80)
    
    # ================================================================
    # Step 1: Load a real ML engineer resume
    # ================================================================
    print("\n📄 STEP 1: Loading real ML engineer resume...")
    
    # Use a real resume from tests/resumes
    resume_path = Path("tests/resumes/resume_ml_01.pdf")
    if not resume_path.exists():
        # Try alternate path (from container perspective)
        resume_path = Path("/app/tests/resumes/resume_ml_01.pdf")
    
    if not resume_path.exists():
        print(f"❌ Resume not found: {resume_path}")
        return
    
    print(f"✅ Found resume: {resume_path.name}")
    print(f"   File size: {resume_path.stat().st_size:,} bytes")
    
    with open(resume_path, 'rb') as f:
        resume_bytes = f.read()
    
    print(f"✅ Loaded {len(resume_bytes):,} bytes")
    
    # ================================================================
    # Step 2: Initialize the VLM parser
    # ================================================================
    print("\n🔧 STEP 2: Initializing Docling VLM parser...")
    
    try:
        vlm_parser = DoclingVLMParser()
        print("✅ Parser initialized")
    except Exception as e:
        print(f"❌ Failed to initialize parser: {e}")
        return
    
    # ================================================================
    # Step 3: Parse the resume
    # ================================================================
    print("\n🔍 STEP 3: Parsing resume with Docling VLM...")
    print(f"   Filename: {resume_path.name}")
    print(f"   This may take 5-10 seconds for PDF processing...")
    
    import time
    parse_start = time.time()
    
    try:
        parsed_resume = await vlm_parser.parse_resume(
            file_bytes=resume_bytes,
            filename=resume_path.name
        )
        parse_duration = time.time() - parse_start
        
        print(f"✅ Resume parsed successfully in {parse_duration:.1f} seconds")
        print(f"\n📋 PARSED RESUME DETAILS:")
        print(f"   Full Name: {parsed_resume.full_name}")
        print(f"   Email: {parsed_resume.email}")
        print(f"   Phone: {parsed_resume.phone}")
        print(f"   Skills ({len(parsed_resume.skills)}): {', '.join(parsed_resume.skills[:10])}")
        if len(parsed_resume.skills) > 10:
            print(f"      ... and {len(parsed_resume.skills) - 10} more")
        print(f"   Work Experience ({len(parsed_resume.experience)} positions):")
        for i, exp in enumerate(parsed_resume.experience[:3]):
            title = exp.title or "Unknown Title"
            company = exp.company or "Unknown Company"
            duration = f"{exp.start_date or '?'} - {exp.end_date or '?'}"
            print(f"      {i+1}. {title} at {company} ({duration})")
        if len(parsed_resume.experience) > 3:
            print(f"      ... and {len(parsed_resume.experience) - 3} more")
        print(f"   Education ({len(parsed_resume.education)} entries):")
        for edu in parsed_resume.education:
            degree = edu.degree or "Unknown Degree"
            school = edu.school or "Unknown School"
            print(f"      - {degree} from {school}")
        
    except Exception as e:
        print(f"❌ PARSING FAILED: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ================================================================
    # Step 4: Load job description
    # ================================================================
    print("\n📝 STEP 4: Loading job description...")
    
    jd_path = Path("tests/Caylent_ML_Engineer_Architect_Track_JD.pdf")
    if not jd_path.exists():
        print(f"❌ Job description not found: {jd_path}")
        return
    
    with open(jd_path, 'rb') as f:
        jd_bytes = f.read()
    
    print(f"✅ Loaded job description: {len(jd_bytes):,} bytes")
    
    # ================================================================
    # Step 5: Parse job description
    # ================================================================
    print("\n🔍 STEP 5: Parsing job description...")
    
    try:
        jd_parsed = await vlm_parser.parse_resume(
            file_bytes=jd_bytes,
            filename=jd_path.name
        )
        print(f"✅ Job description parsed")
        print(f"   Role mentions: {len(jd_parsed.skills)} key requirements")
    except Exception as e:
        print(f"❌ JD parsing failed: {e}")
        # Use a simple string as fallback
        jd_text = "Machine Learning Engineer with Python, TensorFlow, AWS experience"
        print(f"   Using fallback JD text: {jd_text}")
    
    # ================================================================
    # Step 6: Initialize orchestrator components
    # ================================================================
    print("\n🔧 STEP 6: Initializing orchestrator components...")
    
    try:
        # Note: We can't easily test the full orchestrator without a database session
        # So we'll test individual components
        
        print("   Initializing diagnostic agent...")
        diagnostic_agent = DiagnosticAgentService(
            customer_id="eliza",
            user_id=2
        )
        print("   ✅ Diagnostic agent ready")
        
        print("   Initializing scoring engine...")
        scoring_engine = MultiDimensionalScoringEngine(
            customer_id="eliza"
        )
        print("   ✅ Scoring engine ready")
        
    except Exception as e:
        print(f"❌ Component initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ================================================================
    # Step 7: Run diagnostic analysis
    # ================================================================
    print("\n🤖 STEP 7: Running diagnostic agent on job description...")
    
    try:
        from src.services.talent.diagnostic_agent import DiagnosticInput
        from src.models.talent_analysis import BaselineProfile
        
        # Create a minimal baseline for testing
        baseline = BaselineProfile(
            role="Machine Learning Engineer",
            employee_count=1,
            avg_tenure_months=24,
            common_skills=["python", "tensorflow", "aws", "machine learning"],
            common_backgrounds=["Computer Science"],
            career_paths=[],
            quality_score=0.5
        )
        
        diagnostic_input = DiagnosticInput(
            job_description=f"Machine Learning Engineer role",
            ideal_candidate_profile="Experienced ML engineer with production deployment experience",
            baseline_profile=baseline,
            customer_id="eliza",
            user_id=2
        )
        
        diagnostic_start = time.time()
        diagnostic_report = await asyncio.to_thread(
            diagnostic_agent.analyze,
            diagnostic_input
        )
        diagnostic_duration = time.time() - diagnostic_start
        
        print(f"✅ Diagnostic analysis complete in {diagnostic_duration:.1f} seconds")
        print(f"\n📊 DIAGNOSTIC REPORT:")
        print(f"   Confidence: {diagnostic_report.confidence}")
        print(f"   Key Attributes ({len(diagnostic_report.attribute_weights)}):")
        for attr in diagnostic_report.attribute_weights[:5]:
            print(f"      - {attr.attribute}: priority={attr.priority}, weight={attr.weight}")
        print(f"   Hypotheses ({len(diagnostic_report.success_hypotheses)}):")
        for i, hyp in enumerate(diagnostic_report.success_hypotheses):
            print(f"      {i+1}. {hyp.hypothesis}")
        
    except Exception as e:
        print(f"❌ DIAGNOSTIC ANALYSIS FAILED: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ================================================================
    # Step 8: Score the parsed resume
    # ================================================================
    print("\n🎯 STEP 8: Scoring the candidate...")
    
    try:
        score_start = time.time()
        
        # The scoring engine expects a ParsedResume, diagnostic, and baseline
        candidate_score = await asyncio.to_thread(
            scoring_engine.score,
            resume=parsed_resume,
            diagnostic=diagnostic_report,
            baseline=baseline,
            source=CandidateSource.APPLICANT
        )
        
        score_duration = time.time() - score_start
        
        print(f"✅ Candidate scored in {score_duration:.1f} seconds")
        print(f"\n🏆 CANDIDATE SCORE:")
        print(f"   Candidate: {candidate_score.full_name}")
        print(f"   Overall Score: {candidate_score.overall_score:.2f}")
        print(f"   Source: {candidate_score.source}")
        print(f"\n   Dimension Scores:")
        for dim in candidate_score.dimensions:
            print(f"      - {dim.name}: {dim.score:.2f}")
            print(f"        Rationale: {dim.rationale[:100]}...")
        
    except Exception as e:
        print(f"❌ SCORING FAILED: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ================================================================
    # Summary
    # ================================================================
    print("\n" + "="*80)
    print("✅ PIPELINE TEST COMPLETE - ALL STAGES PASSED")
    print("="*80)
    print(f"\nTiming Summary:")
    print(f"  Resume Parsing: {parse_duration:.1f}s")
    print(f"  Diagnostic Analysis: {diagnostic_duration:.1f}s")
    print(f"  Candidate Scoring: {score_duration:.1f}s")
    print(f"  Total: {parse_duration + diagnostic_duration + score_duration:.1f}s")
    print(f"\nResults:")
    print(f"  Candidate: {candidate_score.full_name}")
    print(f"  Score: {candidate_score.overall_score:.2f}")
    print(f"  Skills: {len(parsed_resume.skills)}")
    print(f"  Experience: {len(parsed_resume.work_experience)} positions")
    print("\n🎉 The parsing and scoring pipeline is working correctly!")
    print("   The issue with 0 candidates must be in how resumes are passed")
    print("   from the API to the orchestrator.")


async def test_orchestrator_parse_method_directly():
    """Test the orchestrator's _parse_resumes method directly."""
    
    print("\n" + "="*80)
    print("🧪 TESTING ORCHESTRATOR _parse_resumes METHOD DIRECTLY")
    print("="*80)
    
    # Load real ML resume
    resume_path = Path("/app/tests/resumes/resume_ml_01.pdf")
    if not resume_path.exists():
        resume_path = Path("tests/resumes/resume_ml_01.pdf")
    
    if not resume_path.exists():
        print(f"❌ Resume not found")
        return
    
    with open(resume_path, 'rb') as f:
        resume_bytes = f.read()
    
    print(f"\n📄 Testing with: {resume_path.name} ({len(resume_bytes):,} bytes)")
    
    # Create orchestrator
    try:
        orchestrator = TalentIntelligenceOrchestrator(
            customer_id="eliza",
            user_id=2,
            neo4j_enabled=False
        )
        print("✅ Orchestrator initialized")
    except Exception as e:
        print(f"❌ Failed to create orchestrator: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test the _parse_resumes method
    print("\n🔍 Calling orchestrator._parse_resumes()...")
    print(f"   Input: List with 1 resume file")
    
    import time
    start = time.time()
    
    try:
        parsed_resumes = await orchestrator._parse_resumes(
            [(resume_bytes, resume_path.name)]
        )
        duration = time.time() - start
        
        print(f"✅ _parse_resumes returned in {duration:.1f}s")
        print(f"\n📊 RESULTS:")
        print(f"   Input count: 1")
        print(f"   Output count: {len(parsed_resumes)}")
        
        if len(parsed_resumes) == 0:
            print("\n❌ PROBLEM FOUND: _parse_resumes returned empty list!")
            print("   Even though we passed 1 resume file.")
            print("   This explains why 50 resumes result in 0 candidates.")
        else:
            print(f"\n✅ Resume parsed successfully:")
            resume = parsed_resumes[0]
            print(f"   Full Name: {resume.full_name}")
            print(f"   Email: {resume.email}")
            print(f"   Skills: {len(resume.skills)}")
            print(f"   Experience: {len(resume.experience)} positions")
            
    except Exception as e:
        print(f"❌ _parse_resumes FAILED: {e}")
        import traceback
        traceback.print_exc()


async def test_multiple_resumes():
    """Test with multiple resumes to simulate the actual flow."""
    
    print("\n" + "="*80)
    print("🧪 TESTING WITH MULTIPLE RESUMES (simulating actual flow)")
    print("="*80)
    
    # Load first 5 real ML resumes
    resume_dir = Path("/app/tests/resumes")
    if not resume_dir.exists():
        resume_dir = Path("tests/resumes")
    
    if not resume_dir.exists():
        print(f"❌ Resume directory not found")
        return
    
    resume_files = sorted(resume_dir.glob("resume_ml_*.pdf"))[:5]
    if not resume_files:
        print(f"❌ No resumes found in {resume_dir}")
        return
    
    resume_data = []
    for resume_file in resume_files:
        with open(resume_file, 'rb') as f:
            resume_data.append((f.read(), resume_file.name))
    
    print(f"\n📄 Loaded {len(resume_data)} real ML resumes...")
    for i, (content, name) in enumerate(resume_data):
        print(f"   {i+1}. {name} ({len(content):,} bytes)")
    
    # Create orchestrator
    try:
        orchestrator = TalentIntelligenceOrchestrator(
            customer_id="eliza",
            user_id=2,
            neo4j_enabled=False
        )
        print("\n✅ Orchestrator initialized")
    except Exception as e:
        print(f"❌ Failed to create orchestrator: {e}")
        return
    
    # Parse all resumes
    print(f"\n🔍 Parsing {len(resume_data)} resumes...")
    print("   (This should take 30-60+ seconds if actually processing)")
    
    import time
    start = time.time()
    
    try:
        parsed_resumes = await orchestrator._parse_resumes(resume_data)
        duration = time.time() - start
        
        print(f"\n⏱️  Duration: {duration:.1f}s")
        print(f"📊 Results:")
        print(f"   Input: {len(resume_data)} resumes")
        print(f"   Output: {len(parsed_resumes)} parsed")
        print(f"   Success rate: {len(parsed_resumes)}/{len(resume_data)} ({100*len(parsed_resumes)/len(resume_data):.0f}%)")
        
        if duration < 5:
            print(f"\n⚠️  WARNING: Parsing was suspiciously fast!")
            print(f"   Expected: 30-60+ seconds for {len(resume_data)} PDFs")
            print(f"   Actual: {duration:.1f}s")
            print(f"   This suggests parsing is not actually happening")
        
        if len(parsed_resumes) == 0:
            print("\n❌ CRITICAL: All resumes failed to parse!")
        else:
            print(f"\n✅ Sample of parsed resumes:")
            for i, resume in enumerate(parsed_resumes[:3]):
                print(f"\n   Resume {i+1}: {resume.full_name}")
                print(f"      Email: {resume.email}")
                print(f"      Skills: {len(resume.skills)}")
                print(f"      Experience: {len(resume.experience)}")
                
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🚀 ML TALENT PIPELINE DEBUGGING TEST SUITE")
    print("="*80)
    print("\nThis test will:")
    print("  1. Test complete pipeline with one resume")
    print("  2. Test orchestrator._parse_resumes() directly")
    print("  3. Test with multiple resumes to measure timing")
    print("\nStarting tests...\n")
    
    # Run all tests
    asyncio.run(test_single_resume_full_pipeline())
    asyncio.run(test_orchestrator_parse_method_directly())
    asyncio.run(test_multiple_resumes())
    
    print("\n" + "="*80)
    print("✅ TEST SUITE COMPLETE")
    print("="*80)

