#!/usr/bin/env python3
"""
Full PDL Pipeline Test

Shows the complete flow:
1. Input: Job description + ideal candidate profile
2. Diagnostic Agent: Analyzes and extracts key attributes
3. PDL Query Builder: Creates search query
4. PDL API: Returns matching candidates
"""

import asyncio
import json
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import database
from src.services.talent.pdl_query_builder import PDLQueryBuilder, PDLQueryParams
from src.services.talent.diagnostic_agent import DiagnosticAgentService, DiagnosticInput
from src.models.talent_analysis import BaselineProfile, AttributePriority, CareerPathPattern
from src.services.ingestion.connector_service import ConnectorService
from src.services.ingestion.connectors.people_data_labs import PeopleDataLabsConnector


def print_section(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def print_subsection(title: str):
    print(f"\n  --- {title} ---")


async def main():
    print("\n" + "="*70)
    print("  TALENT INTELLIGENCE PIPELINE - Full Flow Demo")
    print("="*70)
    
    # ================================================================
    # STEP 1: INPUTS
    # ================================================================
    print_section("STEP 1: INPUTS")
    
    job_description = """
Senior Machine Learning Engineer - AI Platform Team

About the Role:
We are looking for a Senior Machine Learning Engineer to join our AI Platform team. 
You will be responsible for building and deploying production ML systems that power 
our core product features.

Requirements:
- 5+ years of experience in machine learning or related field
- Strong Python programming skills
- Deep experience with TensorFlow or PyTorch
- Experience deploying ML models to production at scale
- Knowledge of MLOps practices (CI/CD for ML, model monitoring)
- Experience with cloud platforms (AWS preferred, GCP or Azure also acceptable)
- Strong understanding of distributed systems

Nice to have:
- Experience with NLP or computer vision
- Familiarity with Kubernetes and containerization
- Experience with real-time inference systems
- Published research or patents in ML
- Experience leading technical projects
"""

    ideal_candidate = """
The ideal candidate is a senior ML engineer with 5-8 years of experience who has:
- Built and deployed production ML systems at scale
- Strong software engineering fundamentals, not just research
- Experience with the full ML lifecycle from experimentation to production
- Worked at a tech company or high-growth startup
- Can mentor junior engineers and lead technical initiatives
- Comfortable with ambiguity and can drive projects independently
"""

    print("\n📋 JOB DESCRIPTION:")
    print("-" * 50)
    print(job_description)
    
    print("\n👤 IDEAL CANDIDATE PROFILE:")
    print("-" * 50)
    print(ideal_candidate)
    
    # ================================================================
    # STEP 2: DIAGNOSTIC ANALYSIS
    # ================================================================
    print_section("STEP 2: DIAGNOSTIC ANALYSIS")
    
    # Create empty baseline (no existing employees to compare against)
    baseline_profile = BaselineProfile(
        role_type="ML Engineer",
        prototype_employee_ids=[],
        attribute_weights={
            "python": 0.9,
            "machine_learning": 0.95,
            "deep_learning": 0.8,
            "production_systems": 0.85,
            "cloud": 0.7
        },
        common_career_paths=[],
        skill_distributions={
            "python": 0.95,
            "tensorflow": 0.7,
            "pytorch": 0.6,
            "aws": 0.5
        },
        company_clusters=[],
        average_years_experience=6.0,
        success_patterns=[],
        data_quality_score=0.0  # No baseline data
    )
    
    # Create diagnostic agent
    diagnostic_agent = DiagnosticAgentService(
        customer_id='eliza',
        user_id=2
    )
    
    # Create input
    diagnostic_input = DiagnosticInput(
        role="Senior Machine Learning Engineer",
        job_description=job_description,
        ideal_candidate_description=ideal_candidate,
        baseline_profile=baseline_profile
    )
    
    print("\n🔍 Running diagnostic analysis with GPT-4...")
    
    # Run diagnostic
    diagnostic_report = diagnostic_agent.analyze(diagnostic_input)
    
    print(f"\n✅ DIAGNOSTIC REPORT:")
    print(f"   Role Type: {diagnostic_report.role_type}")
    print(f"   Seniority Level: {diagnostic_report.seniority_level}")
    print(f"   Confidence: {diagnostic_report.confidence:.0%}")
    
    print_subsection("Attribute Weights (Scoring Dimensions)")
    for attr in diagnostic_report.attribute_weights:
        weight = attr.weight if hasattr(attr, 'weight') else attr.get('weight', 0)
        attribute = attr.attribute if hasattr(attr, 'attribute') else attr.get('attribute', 'N/A')
        reason = attr.reason if hasattr(attr, 'reason') else attr.get('reason', 'N/A')
        bar = "█" * int(weight * 20) + "░" * (20 - int(weight * 20))
        print(f"   {attribute:25} [{bar}] {weight:.0%}")
        print(f"      └─ {reason}")
    
    print_subsection("ML Competencies")
    ml_comp = diagnostic_report.ml_competencies
    if hasattr(ml_comp, 'research_focus'):
        print(f"   {'research_focus':25} [{'█' * int(ml_comp.research_focus * 20)}{'░' * (20 - int(ml_comp.research_focus * 20))}] {ml_comp.research_focus:.0%}")
        print(f"   {'production_focus':25} [{'█' * int(ml_comp.production_focus * 20)}{'░' * (20 - int(ml_comp.production_focus * 20))}] {ml_comp.production_focus:.0%}")
        print(f"   {'mlops_focus':25} [{'█' * int(ml_comp.mlops_focus * 20)}{'░' * (20 - int(ml_comp.mlops_focus * 20))}] {ml_comp.mlops_focus:.0%}")
        print(f"   {'leadership_potential':25} [{'█' * int(ml_comp.leadership_potential * 20)}{'░' * (20 - int(ml_comp.leadership_potential * 20))}] {ml_comp.leadership_potential:.0%}")
    else:
        for key, value in ml_comp.items():
            bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
            print(f"   {key:25} [{bar}] {value:.0%}")
    
    print_subsection("Required Skills")
    print(f"   {', '.join(diagnostic_report.required_skills)}")
    
    print_subsection("Preferred Skills")
    print(f"   {', '.join(diagnostic_report.preferred_skills)}")
    
    print_subsection("Key Hypotheses")
    for i, hypothesis in enumerate(diagnostic_report.key_hypotheses, 1):
        print(f"   {i}. {hypothesis}")
    
    print_subsection("Baseline Query Params")
    for key, value in diagnostic_report.baseline_query_params.items():
        print(f"   {key}: {value}")
    
    # ================================================================
    # STEP 3: PDL QUERY CONSTRUCTION
    # ================================================================
    print_section("STEP 3: PDL QUERY CONSTRUCTION")
    
    # Initialize query builder
    query_builder = PDLQueryBuilder()
    
    # Build query from diagnostic
    pdl_query = query_builder.build_initial_query(
        diagnostic=diagnostic_report,
        baseline=baseline_profile,
        role="Senior Machine Learning Engineer",
        limit=5
    )
    
    print("\n📋 PDL QUERY PARAMETERS:")
    print(f"   Job Title: {pdl_query.job_title}")
    print(f"   Job Title Roles: {pdl_query.job_title_role}")
    print(f"   Required Skills: {pdl_query.required_skills}")
    print(f"   Optional Skills: {pdl_query.optional_skills}")
    print(f"   Min Experience: {pdl_query.min_years_experience} years")
    print(f"   Max Experience: {pdl_query.max_years_experience} years")
    print(f"   Limit: {pdl_query.limit}")
    
    # Convert to API payload
    api_payload = query_builder.convert_to_pdl_api_payload(pdl_query)
    
    print_subsection("Elasticsearch Query (sent to PDL)")
    print(f"   {api_payload.get('query', '')}")
    
    # Build simple query for connector
    simple_query = {}
    if pdl_query.job_title:
        simple_query["job_title"] = [pdl_query.job_title.lower()]
    all_skills = (pdl_query.required_skills + pdl_query.optional_skills)[:5]
    if all_skills:
        simple_query["skills"] = [s.lower() for s in all_skills]
    simple_query["location_country"] = ["united states"]
    
    print_subsection("Simplified Query (for connector)")
    print(json.dumps(simple_query, indent=4))
    
    # ================================================================
    # STEP 4: PDL API CALL
    # ================================================================
    print_section("STEP 4: PDL API RESULTS")
    
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    try:
        connector_service = ConnectorService(db)
        
        # Find existing PDL connector
        pdl_connectors = connector_service.list_configurations(
            customer_id='eliza',
            connector_type='people_data_labs',
            is_enabled=True
        )
        
        if not pdl_connectors:
            print("❌ No enabled PDL connector found!")
            return 1
        
        # Get credentials
        api_credentials = connector_service.get_credentials(pdl_connectors[0])
        
        # Initialize PDL connector
        pdl_connector = PeopleDataLabsConnector(
            credentials=api_credentials,
            config={
                "search_query": simple_query,
                "max_records": 5,
                "page_size": 5
            },
            customer_id='eliza'
        )
        
        print("\n🔍 Calling PDL API...")
        
        # Read results
        results = []
        for batch in pdl_connector.read_stream("full", {}):
            results.extend(batch)
            if len(results) >= 5:
                results = results[:5]
                break
        
        print(f"\n✅ Found {len(results)} matching candidates!\n")
        
        for i, person in enumerate(results, 1):
            print(f"{'─'*70}")
            print(f"  CANDIDATE {i}")
            print(f"{'─'*70}")
            print(f"  👤 Name:       {person.get('full_name', 'N/A')}")
            print(f"  💼 Title:      {person.get('job_title', 'N/A')}")
            print(f"  🏢 Company:    {person.get('job_company_name', 'N/A')}")
            print(f"  📍 Location:   {person.get('location_name', 'N/A')}")
            
            # Experience
            exp = person.get('inferred_years_experience')
            if exp:
                print(f"  📅 Experience: {exp} years")
            
            # Skills
            skills = person.get('skills', [])
            if skills:
                # Show first 10 skills
                skill_str = ', '.join(skills[:10])
                if len(skills) > 10:
                    skill_str += f" (+{len(skills)-10} more)"
                print(f"  🛠️  Skills:     {skill_str}")
            
            # Education
            education = person.get('education', [])
            if education:
                for edu in education[:2]:
                    school_obj = edu.get('school')
                    school = school_obj.get('name', 'N/A') if school_obj else 'N/A'
                    degrees = edu.get('degrees', [])
                    degree = degrees[0] if degrees else ''
                    majors = edu.get('majors', [])
                    major = majors[0] if majors else ''
                    if degree or major or school != 'N/A':
                        print(f"  🎓 Education:  {degree} {major} - {school}")
            
            # Work history
            experience = person.get('experience', [])
            if experience:
                print(f"  📋 Recent Roles:")
                for job in experience[:3]:
                    title = job.get('title', {}).get('name', 'N/A')
                    company = job.get('company', {}).get('name', 'N/A')
                    print(f"      • {title} at {company}")
            
            # LinkedIn
            linkedin = person.get('linkedin_url')
            if linkedin:
                print(f"  🔗 LinkedIn:   {linkedin}")
            
            print()
        
    finally:
        db.close()
    
    # ================================================================
    # SUMMARY
    # ================================================================
    print_section("SUMMARY")
    print(f"""
  ✅ Input processed: Job description + ideal candidate profile
  ✅ Diagnostic analysis: {len(diagnostic_report.attribute_weights)} scoring dimensions identified
  ✅ PDL query built: {len(pdl_query.required_skills)} required skills, {len(pdl_query.optional_skills)} optional
  ✅ Candidates found: {len(results)} matching profiles from PDL
  
  The pipeline successfully:
  1. Analyzed the job requirements using AI (GPT-4)
  2. Extracted weighted attributes and ML competencies
  3. Built a targeted PDL search query
  4. Retrieved matching candidate profiles from People Data Labs
""")
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

