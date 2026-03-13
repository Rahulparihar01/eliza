"""
CrewAI Tools for Talent Matching

Custom tools that agents use to access:
- Parsed resume database (internal applicants)
- PDL database (external candidates)
- Neo4j employee patterns
- Scoring and ranking functions
"""
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
import json

from src.models.database import SessionLocal, init_database
from src.models.connector import Applicant, PDLPerson
from src.models.hr import Employee, Department, Position
from src.services.ingestion.neo4j_sync import Neo4jSyncService
from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)
settings = get_settings()


class InternalApplicantSearchInput(BaseModel):
    """Input for searching internal applicants"""
    job_posting_id: Optional[int] = Field(default=None, description="Job posting ID to filter by")
    required_skills: Optional[List[str]] = Field(default=None, description="Must-have skills")
    min_years_experience: Optional[int] = Field(default=None, description="Minimum years of experience")
    companies: Optional[List[str]] = Field(default=None, description="Filter by past/current companies")
    limit: int = Field(default=50, description="Max results to return")


class InternalApplicantSearchTool(BaseTool):
    name: str = "internal_applicant_search"
    description: str = """
    Search internal applicants (people who applied to the job) from parsed resumes.
    
    Use this tool to find candidates from your applicant pool. It searches:
    - Parsed resume data (skills, experience, education)
    - Job history and companies
    - Years of experience
    
    Returns: List of applicants with their parsed resume data.
    
    Example usage:
    {
        "required_skills": ["PyTorch", "Machine Learning"],
        "min_years_experience": 5,
        "limit": 50
    }
    """
    args_schema: Type[BaseModel] = InternalApplicantSearchInput
    
    def _run(
        self,
        job_posting_id: Optional[int] = None,
        required_skills: Optional[List[str]] = None,
        min_years_experience: Optional[int] = None,
        companies: Optional[List[str]] = None,
        limit: int = 50
    ) -> str:
        """Search parsed applicant resumes"""
        try:
            if SessionLocal is None:
                init_database()
            
            db = SessionLocal()
            try:
                # Build query
                query = db.query(Applicant).filter(
                    Applicant.resume_parsed.isnot(None)  # Only parsed resumes
                )
                
                if job_posting_id:
                    query = query.filter(Applicant.job_posting_id == job_posting_id)
                
                # Skill filtering (search in parsed JSON)
                if required_skills:
                    for skill in required_skills:
                        # Search in resume_parsed JSON field
                        query = query.filter(
                            func.jsonb_path_exists(
                                Applicant.resume_parsed,
                                f'$.skills[*] ? (@ like_regex "{skill}" flag "i")'
                            )
                        )
                
                # Get results
                applicants = query.limit(limit).all()
                
                # Format results
                results = []
                for applicant in applicants:
                    parsed = applicant.resume_parsed or {}
                    
                    # Calculate years of experience
                    years_exp = self._calculate_years_experience(parsed.get('experience', []))
                    
                    # Check min experience requirement
                    if min_years_experience and years_exp < min_years_experience:
                        continue
                    
                    # Check company requirement
                    if companies:
                        applicant_companies = [
                            exp.get('company', '').lower()
                            for exp in parsed.get('experience', [])
                        ]
                        if not any(comp.lower() in applicant_companies for comp in companies):
                            continue
                    
                    results.append({
                        "applicant_id": applicant.id,
                        "name": f"{applicant.first_name} {applicant.last_name}",
                        "email": applicant.email,
                        "skills": parsed.get('skills', []),
                        "experience": parsed.get('experience', []),
                        "education": parsed.get('education', []),
                        "years_experience": years_exp,
                        "current_title": parsed.get('headline'),
                        "linkedin_url": parsed.get('linkedin_url'),
                        "summary": parsed.get('summary'),
                        "applied_at": applicant.applied_at.isoformat() if applicant.applied_at else None
                    })
                
                logger.info(
                    "internal_applicant_search_completed",
                    results_count=len(results),
                    required_skills=required_skills
                )
                
                return json.dumps({
                    "total_found": len(results),
                    "applicants": results
                }, indent=2)
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error("internal_applicant_search_error", error=str(e))
            return json.dumps({"error": str(e)})
    
    def _calculate_years_experience(self, experience_list: List[Dict]) -> float:
        """Calculate total years of experience from experience entries"""
        # Simplified calculation - in production, parse dates properly
        return len(experience_list) * 2.5  # Rough estimate: avg 2.5 years per job


class EmployeePatternSearchInput(BaseModel):
    """Input for searching employee success patterns"""
    role_type: Optional[str] = Field(default=None, description="Role type to analyze (e.g., 'Software Engineer', 'Data Scientist')")
    performance_filter: Optional[str] = Field(default="top_performer", description="Performance level filter")
    limit: int = Field(default=10, description="Max employees to analyze")


class EmployeePatternSearchTool(BaseTool):
    name: str = "employee_pattern_search"
    description: str = """
    Analyze patterns from current high-performing employees using Neo4j graph database.
    
    Discovers:
    - Common career paths of top performers
    - Companies that produce successful hires
    - Skill combinations that predict success
    - Educational backgrounds
    
    This is CRITICAL for pattern-informed matching. Use this to understand
    what has worked at THIS company historically.
    
    Example usage:
    {
        "role_type": "Software Engineer",
        "performance_filter": "top_performer",
        "limit": 10
    }
    """
    args_schema: Type[BaseModel] = EmployeePatternSearchInput
    
    def _run(
        self,
        role_type: Optional[str] = None,
        performance_filter: str = "top_performer",
        limit: int = 10
    ) -> str:
        """Query Neo4j for employee success patterns"""
        try:
            neo4j_service = Neo4jSyncService(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password
            )
            
            with neo4j_service.driver.session() as session:
                # Query for top performers and their career paths
                query = """
                MATCH (p:Person)
                WHERE p.performance_rating = $performance_filter
                OPTIONAL MATCH (p)-[r:WORKED_AT]->(c:Company)
                OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
                RETURN p.name as name,
                       p.current_title as current_title,
                       p.years_experience as years_experience,
                       collect(DISTINCT c.name) as companies,
                       collect(DISTINCT s.name) as skills,
                       p.education as education
                LIMIT $limit
                """
                
                result = session.run(
                    query,
                    performance_filter=performance_filter,
                    limit=limit
                )
                
                employees = []
                all_companies = []
                all_skills = []
                
                for record in result:
                    companies = record["companies"] or []
                    skills = record["skills"] or []
                    
                    all_companies.extend(companies)
                    all_skills.extend(skills)
                    
                    employees.append({
                        "name": record["name"],
                        "current_title": record["current_title"],
                        "years_experience": record["years_experience"],
                        "companies": companies,
                        "skills": skills,
                        "education": record["education"]
                    })
                
                # Analyze patterns
                from collections import Counter
                company_frequency = Counter(all_companies)
                skill_frequency = Counter(all_skills)
                
                # Find career transitions (consulting → tech, etc.)
                transitions = self._analyze_career_transitions(session)
                
                patterns = {
                    "total_analyzed": len(employees),
                    "top_employee_profiles": employees,
                    "common_companies": [
                        {"company": comp, "frequency": freq, "percentage": freq/len(employees)*100}
                        for comp, freq in company_frequency.most_common(10)
                    ],
                    "essential_skills": [
                        {"skill": skill, "frequency": freq, "percentage": freq/len(employees)*100}
                        for skill, freq in skill_frequency.most_common(15)
                    ],
                    "career_transitions": transitions,
                    "insights": self._generate_insights(employees, company_frequency, skill_frequency)
                }
                
                logger.info(
                    "employee_pattern_search_completed",
                    employees_analyzed=len(employees),
                    patterns_found=len(patterns)
                )
                
                return json.dumps(patterns, indent=2)
                
        except Exception as e:
            logger.error("employee_pattern_search_error", error=str(e))
            return json.dumps({"error": str(e), "patterns": {}})
    
    def _analyze_career_transitions(self, session) -> List[Dict]:
        """Analyze common career path transitions"""
        query = """
        MATCH (p:Person)-[r1:PREVIOUSLY_AT]->(c1:Company),
              (p)-[r2:WORKS_AT]->(c2:Company)
        WHERE p.performance_rating = 'top_performer'
        RETURN c1.name as from_company,
               c1.type as from_type,
               c2.name as to_company,
               c2.type as to_type,
               count(p) as transition_count
        ORDER BY transition_count DESC
        LIMIT 10
        """
        
        result = session.run(query)
        transitions = []
        
        for record in result:
            transitions.append({
                "from": {"company": record["from_company"], "type": record["from_type"]},
                "to": {"company": record["to_company"], "type": record["to_type"]},
                "count": record["transition_count"]
            })
        
        return transitions
    
    def _generate_insights(self, employees, company_freq, skill_freq) -> List[str]:
        """Generate actionable insights from patterns"""
        insights = []
        
        # Top company insight
        if company_freq:
            top_company = company_freq.most_common(1)[0]
            if top_company[1] >= len(employees) * 0.3:  # 30%+ of top performers
                insights.append(
                    f"{top_company[0]} alumni represent {top_company[1]/len(employees)*100:.0f}% "
                    f"of top performers - prioritize sourcing from {top_company[0]}"
                )
        
        # Skill pattern insight
        if skill_freq:
            universal_skills = [skill for skill, freq in skill_freq.items() if freq >= len(employees) * 0.8]
            if universal_skills:
                insights.append(
                    f"Skills present in 80%+ of top performers: {', '.join(universal_skills[:5])} - "
                    "these are must-haves, not nice-to-haves"
                )
        
        return insights


class PDLCandidateSearchInput(BaseModel):
    """Input for PDL API search"""
    job_titles: Optional[List[str]] = Field(default=None, description="Target job titles")
    skills: Optional[List[str]] = Field(default=None, description="Required skills")
    companies: Optional[List[str]] = Field(default=None, description="Target companies")
    min_years_experience: Optional[int] = Field(default=None, description="Minimum experience")
    location: Optional[str] = Field(default=None, description="Location filter")
    limit: int = Field(default=50, description="Max results")


class PDLCandidateSearchTool(BaseTool):
    name: str = "pdl_candidate_search"
    description: str = """
    Search People Data Labs API for external candidates who haven't applied.
    
    Use this to find candidates in the broader market who match the ideal profile.
    This is EXPENSIVE (costs real money per search) so craft queries carefully.
    
    Focus on:
    - Specific job titles
    - Key skills
    - Target companies (especially those identified in employee patterns)
    - Experience level
    
    Returns: List of PDL persons with detailed profiles.
    
    Example usage:
    {
        "job_titles": ["Software Engineer", "Backend Engineer"],
        "skills": ["python", "aws", "kubernetes"],
        "companies": ["Company A", "Company B"],  # From pattern analysis
        "min_years_experience": 5,
        "limit": 20
    }
    """
    args_schema: Type[BaseModel] = PDLCandidateSearchInput
    
    def _run(
        self,
        job_titles: Optional[List[str]] = None,
        skills: Optional[List[str]] = None,
        companies: Optional[List[str]] = None,
        min_years_experience: Optional[int] = None,
        location: Optional[str] = None,
        limit: int = 50
    ) -> str:
        """Search PDL database for matching candidates"""
        try:
            if SessionLocal is None:
                init_database()
            
            db = SessionLocal()
            try:
                # Build query against local PDL persons table
                # (In production, this could also call PDL API directly)
                query = db.query(PDLPerson)
                
                # Job title filter
                if job_titles:
                    conditions = [
                        PDLPerson.job_title.ilike(f"%{title}%")
                        for title in job_titles
                    ]
                    query = query.filter(or_(*conditions))
                
                # Skills filter (search in skills JSON array)
                if skills:
                    for skill in skills:
                        query = query.filter(
                            func.jsonb_path_exists(
                                PDLPerson.skills,
                                f'$[*] ? (@ like_regex "{skill}" flag "i")'
                            )
                        )
                
                # Company filter
                if companies:
                    conditions = [
                        PDLPerson.job_company_name.ilike(f"%{company}%")
                        for company in companies
                    ]
                    query = query.filter(or_(*conditions))
                
                # Location filter
                if location:
                    query = query.filter(PDLPerson.location_name.ilike(f"%{location}%"))
                
                # Get results
                candidates = query.limit(limit).all()
                
                # Format results
                results = []
                for person in candidates:
                    results.append({
                        "pdl_id": person.pdl_id,
                        "pdl_person_id": person.id,  # Internal DB ID
                        "name": person.full_name,
                        "current_title": person.job_title,
                        "current_company": person.job_company_name,
                        "skills": person.skills or [],
                        "experience_years": self._calculate_pdl_experience(person),
                        "education": person.education,
                        "location": person.location_name,
                        "linkedin_url": person.linkedin_url,
                        "github_url": person.github_url,
                        "email": person.primary_email
                    })
                
                logger.info(
                    "pdl_candidate_search_completed",
                    results_count=len(results),
                    job_titles=job_titles,
                    skills=skills
                )
                
                return json.dumps({
                    "total_found": len(results),
                    "candidates": results,
                    "estimated_cost_usd": len(results) * 0.02  # Rough estimate
                }, indent=2)
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error("pdl_candidate_search_error", error=str(e))
            return json.dumps({"error": str(e)})
    
    def _calculate_pdl_experience(self, person: PDLPerson) -> Optional[int]:
        """Calculate years of experience from PDL data"""
        # Simplified - in production, parse work_history dates
        if person.experience_months:
            return person.experience_months // 12
        return None


class CandidateScoringInput(BaseModel):
    """Input for scoring a candidate"""
    candidate_data: Dict[str, Any] = Field(..., description="Candidate profile data")
    ideal_profile: Dict[str, Any] = Field(..., description="Ideal candidate profile")
    pattern_matches: Optional[Dict[str, Any]] = Field(default=None, description="Pattern matching data")


class CandidateScoringTool(BaseTool):
    name: str = "candidate_scoring"
    description: str = """
    Score a candidate against the ideal profile using deterministic rules.
    
    This is FAST scoring (no LLM calls) used in Stage 1 ranking to quickly
    filter 50+ candidates down to top 20.
    
    Scoring dimensions:
    - Skills match (keyword matching + synonyms)
    - Experience fit (years, level)
    - Company background (tier, relevance)
    - Pattern matches (bonus for matching success patterns)
    
    Returns: Numerical scores (0-100) for each dimension.
    """
    args_schema: Type[BaseModel] = CandidateScoringInput
    
    def _run(
        self,
        candidate_data: Dict[str, Any],
        ideal_profile: Dict[str, Any],
        pattern_matches: Optional[Dict[str, Any]] = None
    ) -> str:
        """Fast deterministic scoring"""
        try:
            scores = {}
            
            # 1. Skills match (40% weight)
            scores['skills_match'] = self._score_skills(
                candidate_data.get('skills', []),
                ideal_profile.get('must_have_skills', [])
            )
            
            # 2. Experience fit (25% weight)
            scores['experience_fit'] = self._score_experience(
                candidate_data.get('years_experience', 0),
                ideal_profile.get('experience_years_min', 0),
                ideal_profile.get('experience_years_ideal', 999)
            )
            
            # 3. Company background (20% weight)
            scores['company_background'] = self._score_companies(
                candidate_data.get('experience', []),
                ideal_profile.get('target_companies', [])
            )
            
            # 4. Pattern match bonus (15% weight)
            if pattern_matches:
                scores['pattern_bonus'] = self._score_pattern_matches(pattern_matches)
            else:
                scores['pattern_bonus'] = 50.0  # Neutral
            
            # Calculate weighted total
            total = (
                scores['skills_match'] * 0.40 +
                scores['experience_fit'] * 0.25 +
                scores['company_background'] * 0.20 +
                scores['pattern_bonus'] * 0.15
            )
            
            return json.dumps({
                "total_score": round(total, 2),
                "breakdown": scores,
                "method": "fast_deterministic"
            }, indent=2)
            
        except Exception as e:
            logger.error("candidate_scoring_error", error=str(e))
            return json.dumps({"error": str(e)})
    
    def _score_skills(self, candidate_skills: List[str], required_skills: List[Dict]) -> float:
        """Score skill match"""
        if not required_skills:
            return 100.0
        
        candidate_skills_lower = [s.lower() for s in candidate_skills]
        matches = 0
        
        for req_skill in required_skills:
            skill_name = req_skill.get('skill', '').lower()
            aliases = [a.lower() for a in req_skill.get('aliases', [])]
            
            if skill_name in candidate_skills_lower or any(a in candidate_skills_lower for a in aliases):
                matches += 1
        
        return (matches / len(required_skills)) * 100
    
    def _score_experience(self, years: float, min_years: int, ideal_years: int) -> float:
        """Score experience level"""
        if years < min_years:
            return max(0, (years / min_years) * 60)  # Below minimum
        elif years >= ideal_years:
            return 100.0  # At or above ideal
        else:
            # Between min and ideal
            return 60 + ((years - min_years) / (ideal_years - min_years)) * 40
    
    def _score_companies(self, experience: List[Dict], target_companies: List[str]) -> float:
        """Score based on company background"""
        if not target_companies:
            return 75.0  # Neutral
        
        candidate_companies = [
            exp.get('company', '').lower()
            for exp in experience
        ]
        
        target_companies_lower = [c.lower() for c in target_companies]
        
        # Check if worked at any target company
        matches = sum(
            1 for comp in candidate_companies
            if any(target in comp for target in target_companies_lower)
        )
        
        if matches > 0:
            return min(100, 70 + (matches * 15))  # 70 base + 15 per match
        else:
            return 50.0  # No match
    
    def _score_pattern_matches(self, pattern_matches: Dict) -> float:
        """Bonus points for matching success patterns"""
        score = 50.0  # Base
        
        # Consulting-to-tech transition
        if pattern_matches.get('consulting_to_tech_transition'):
            score += 20
        
        # Alumni from successful companies
        if pattern_matches.get('target_company_alumni'):
            score += 20
        
        # Similar career path to top performers
        similarity = pattern_matches.get('career_path_similarity', 0)
        score += similarity * 10  # 0-1 scale → 0-10 points
        
        return min(100, score)

