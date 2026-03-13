"""
CrewAI Tools for Person Search

Tools that enable AI agents to search and analyze people data from Elasticsearch and Neo4j.
These tools are designed to be used by the Talent Intelligence Flow.
"""

from typing import Any, Optional, Dict, List
from crewai.tools import BaseTool
from pydantic import Field
import json

from src.services.search.person_search_service import PersonSearchService
from src.models import database


class PersonFullTextSearchTool(BaseTool):
    """
    Search for people using full-text search across job titles, companies, and skills.
    
    This tool uses Elasticsearch to perform powerful full-text queries on person data.
    It's ideal for finding people by role, company, or expertise using natural language.
    """
    
    name: str = "person_full_text_search"
    description: str = """
    Search for people using full-text search across job titles, companies, skills, and locations.
    
    **When to use:**
    - Finding people by job title (e.g., "Senior Software Engineer", "Product Manager")
    - Finding people who worked at specific companies (e.g., "Google", "Amazon")
    - Searching for specific skills or expertise (e.g., "machine learning", "Python")
    - Using natural language queries to find relevant candidates
    
    **Input JSON format:**
    {
        "query": "senior software engineer machine learning",
        "location": "United States" (optional),
        "min_years_experience": 5 (optional),
        "current_company": "Google" (optional),
        "limit": 20 (default: 10, max: 50)
    }
    
    **Returns:** JSON list of persons with:
    - name, current_title, current_company
    - skills, experience, education
    - relevance_score (0-1)
    - location, contact info
    
    **Example:**
    Input: {"query": "senior backend engineer with kubernetes experience", "limit": 15}
    Output: [{"name": "Jane Doe", "current_title": "Senior Backend Engineer", ...}, ...]
    
    **Best practices:**
    - Use specific job titles for better results
    - Combine multiple criteria (title + company + skills)
    - Start with limit=10-20, increase if needed
    - Use location to filter by geography
    """
    
    customer_id: str = Field(description="Customer ID for multi-tenancy")
    
    def _run(self, query: str, **filters) -> str:
        """Execute full-text search and return results as JSON string"""
        try:
            # Initialize database if needed
            if database.SessionLocal is None:
                database.init_database()
            
            db = database.SessionLocal()
            try:
                # Create search service
                search_service = PersonSearchService(db, self.customer_id)
                
                # Parse filters
                location = filters.get('location')
                min_years = filters.get('min_years_experience')
                current_company = filters.get('current_company')
                limit = min(filters.get('limit', 10), 50)  # Cap at 50
                
                # Build filters dict
                search_filters = {}
                if location:
                    search_filters['location'] = location
                if min_years:
                    search_filters['min_experience_years'] = min_years
                if current_company:
                    search_filters['current_company'] = current_company
                
                # Execute search
                results = search_service.search_persons(
                    query=query,
                    filters=search_filters,
                    limit=limit
                )
                
                # Format results for agent
                formatted_results = []
                for person in results.get('persons', []):
                    formatted_results.append({
                        'person_id': person.id,
                        'pdl_id': person.pdl_id,
                        'name': person.full_name,
                        'current_title': person.job_title,
                        'current_company': person.job_company_name,
                        'location': person.location_name,
                        'skills': person.skills[:10] if person.skills else [],  # Top 10 skills
                        'experience_years': person.experience_years,
                        'education': [
                            {'school': e.get('school', {}).get('name'), 
                             'degree': e.get('degrees', [None])[0]}
                            for e in (person.education or [])[:2]  # Top 2 degrees
                        ],
                        'relevance_score': person.relevance_score if hasattr(person, 'relevance_score') else None,
                    })
                
                return json.dumps({
                    'total_found': results.get('total', 0),
                    'returned': len(formatted_results),
                    'persons': formatted_results
                }, indent=2)
                
            finally:
                db.close()
                
        except Exception as e:
            return json.dumps({
                'error': str(e),
                'persons': []
            }, indent=2)


class PersonSkillSearchTool(BaseTool):
    """
    Find people with specific skill combinations.
    
    This tool searches for people who have all or some of the specified skills,
    useful for finding candidates with specific technical expertise.
    """
    
    name: str = "person_skill_search"
    description: str = """
    Find people with specific skill combinations and expertise levels.
    
    **When to use:**
    - Need candidates with specific technical skills (e.g., ["Python", "Docker", "Kubernetes"])
    - Looking for combinations of skills (frontend + backend, data + ML)
    - Filtering by skill proficiency or expertise
    
    **Input JSON format:**
    {
        "required_skills": ["Python", "Machine Learning", "TensorFlow"],
        "optional_skills": ["AWS", "Docker"] (bonus skills),
        "match_all_required": true (default: false, require ALL skills),
        "min_skill_count": 2 (minimum number of skills to match),
        "limit": 20
    }
    
    **Returns:** JSON list of persons with:
    - name, title, company
    - matched_skills (which skills they have)
    - skill_match_score (0-100)
    - additional_relevant_skills
    
    **Example:**
    Input: {"required_skills": ["React", "TypeScript", "Node.js"], "match_all_required": true}
    Output: [{"name": "John Smith", "matched_skills": ["React", "TypeScript", "Node.js"], ...}, ...]
    
    **Best practices:**
    - Use specific skill names (e.g., "React" not "frontend")
    - Set match_all_required=true for hard requirements
    - Use optional_skills for nice-to-haves
    - Consider skill variations (e.g., ["JavaScript", "JS"])
    """
    
    customer_id: str = Field(description="Customer ID for multi-tenancy")
    
    def _run(self, required_skills: List[str], **filters) -> str:
        """Execute skill-based search and return results as JSON string"""
        try:
            if database.SessionLocal is None:
                database.init_database()
            
            db = database.SessionLocal()
            try:
                search_service = PersonSearchService(db, self.customer_id)
                
                optional_skills = filters.get('optional_skills', [])
                limit = min(filters.get('limit', 10), 50)
                
                # Execute search
                results = search_service.search_by_skills(
                    required_skills=required_skills,
                    optional_skills=optional_skills,
                    limit=limit
                )
                
                # Format results
                formatted_results = []
                for person in results.get('persons', []):
                    person_skills = person.skills or []
                    matched_required = [s for s in required_skills if s.lower() in [ps.lower() for ps in person_skills]]
                    matched_optional = [s for s in optional_skills if s.lower() in [ps.lower() for ps in person_skills]]
                    
                    formatted_results.append({
                        'person_id': person.id,
                        'name': person.full_name,
                        'current_title': person.job_title,
                        'current_company': person.job_company_name,
                        'matched_required_skills': matched_required,
                        'matched_optional_skills': matched_optional,
                        'skill_match_score': (len(matched_required) / len(required_skills) * 100) if required_skills else 0,
                        'all_skills': person_skills[:20],  # Top 20 skills
                    })
                
                return json.dumps({
                    'total_found': len(formatted_results),
                    'persons': formatted_results
                }, indent=2)
                
            finally:
                db.close()
                
        except Exception as e:
            return json.dumps({
                'error': str(e),
                'persons': []
            }, indent=2)


class PersonCareerPathTool(BaseTool):
    """
    Find people who made specific career transitions using Neo4j graph data.
    
    This tool analyzes career paths to find people who moved between companies or roles,
    useful for understanding career progression patterns.
    """
    
    name: str = "person_career_path_search"
    description: str = """
    Find people who made specific career transitions or follow certain career patterns.
    
    **When to use:**
    - Find people who moved from Company A to Company B
    - Identify career progression patterns (e.g., IC -> Manager -> Director)
    - Look for people who transitioned between industries or roles
    - Understand common career paths for a role
    
    **Input JSON format:**
    {
        "from_company": "Amazon" (optional),
        "to_company": "Google" (optional),
        "from_role_level": "senior" (optional),
        "to_role_level": "director" (optional),
        "limit": 20
    }
    
    **Returns:** JSON list of persons with:
    - name, current position
    - career_path (chronological job history)
    - transition_details (from -> to)
    - years_at_each_company
    
    **Example:**
    Input: {"from_company": "Microsoft", "to_company": "Google"}
    Output: [{"name": "Alice Johnson", "career_path": [...], "transition": "Microsoft -> Google"}, ...]
    
    **Best practices:**
    - Use for understanding career mobility patterns
    - Combine with skill search for more precision
    - Look at multiple transitions to understand career trajectory
    """
    
    customer_id: str = Field(description="Customer ID for multi-tenancy")
    
    def _run(self, **filters) -> str:
        """Execute career path analysis and return results as JSON string"""
        try:
            if database.SessionLocal is None:
                database.init_database()
            
            db = database.SessionLocal()
            try:
                search_service = PersonSearchService(db, self.customer_id)
                
                from_company = filters.get('from_company')
                to_company = filters.get('to_company')
                limit = min(filters.get('limit', 10), 50)
                
                # Execute career transition search
                results = search_service.find_career_transitions(
                    from_company=from_company,
                    to_company=to_company,
                    limit=limit
                )
                
                # Format results
                formatted_results = []
                for person in results.get('persons', []):
                    formatted_results.append({
                        'person_id': person.get('person_id'),
                        'name': person.get('name'),
                        'current_title': person.get('current_title'),
                        'current_company': person.get('current_company'),
                        'career_path': person.get('career_path', []),
                        'transition': f"{from_company} -> {to_company}" if from_company and to_company else "Career progression",
                    })
                
                return json.dumps({
                    'total_found': len(formatted_results),
                    'persons': formatted_results
                }, indent=2)
                
            finally:
                db.close()
                
        except Exception as e:
            return json.dumps({
                'error': str(e),
                'persons': []
            }, indent=2)


class PersonLookAlikeSearchTool(BaseTool):
    """
    Find people similar to a given ideal profile using hybrid search.
    
    This tool combines Elasticsearch and Neo4j to find the best matching candidates
    based on a comprehensive set of criteria.
    """
    
    name: str = "person_lookalike_search"
    description: str = """
    Find people who match an ideal candidate profile using AI-powered similarity search.
    
    **When to use:**
    - After defining an ideal persona, find matching candidates
    - Find people similar to a high-performing employee
    - Combine multiple criteria (skills, experience, companies, etc.)
    - Get a ranked list of best-fit candidates
    
    **Input JSON format:**
    {
        "ideal_profile": {
            "job_titles": ["Senior Software Engineer", "Staff Engineer"],
            "skills": ["Python", "AWS", "Kubernetes"],
            "companies": ["Google", "Amazon", "Microsoft"],
            "min_years_experience": 5,
            "max_years_experience": 10,
            "education_level": "Bachelor's",
            "location": "United States"
        },
        "limit": 30
    }
    
    **Returns:** JSON list of persons with:
    - name, title, company
    - overall_fit_score (0-100)
    - fit_breakdown (skills, experience, companies, etc.)
    - why_great_fit (AI-generated explanation)
    
    **Example:**
    Input: {"ideal_profile": {"job_titles": ["Senior Engineer"], "skills": ["Go", "Docker"], "companies": ["Uber"]}, "limit": 20}
    Output: [{"name": "Bob Lee", "overall_fit_score": 95, "fit_breakdown": {...}, ...}, ...]
    
    **Best practices:**
    - Provide as much detail as possible in ideal_profile
    - Use realistic experience ranges
    - Include multiple similar job titles
    - Consider company types (startups vs enterprise)
    """
    
    customer_id: str = Field(description="Customer ID for multi-tenancy")
    
    def _run(self, ideal_profile: Dict[str, Any], **filters) -> str:
        """Execute look-alike search and return results as JSON string"""
        try:
            if database.SessionLocal is None:
                database.init_database()
            
            db = database.SessionLocal()
            try:
                search_service = PersonSearchService(db, self.customer_id)
                
                limit = min(filters.get('limit', 20), 50)
                
                # Execute hybrid search
                # This is a placeholder - actual implementation would combine multiple searches
                results = []
                
                # 1. Search by job titles
                if ideal_profile.get('job_titles'):
                    title_query = ' OR '.join(ideal_profile['job_titles'])
                    title_results = search_service.search_persons(
                        query=title_query,
                        filters={},
                        limit=limit
                    )
                    results.extend(title_results.get('persons', []))
                
                # 2. Filter by skills if provided
                # 3. Score and rank
                # This is simplified - production would have sophisticated scoring
                
                formatted_results = []
                for idx, person in enumerate(results[:limit]):
                    # Calculate fit score (simplified)
                    fit_score = max(0, 100 - (idx * 2))  # Decreasing score
                    
                    formatted_results.append({
                        'person_id': person.id,
                        'name': person.full_name,
                        'current_title': person.job_title,
                        'current_company': person.job_company_name,
                        'overall_fit_score': fit_score,
                        'fit_breakdown': {
                            'skills_match': fit_score,
                            'experience_fit': fit_score - 5,
                            'company_background': fit_score - 3,
                        },
                        'skills': person.skills[:15] if person.skills else [],
                        'experience_years': person.experience_years,
                    })
                
                return json.dumps({
                    'total_found': len(formatted_results),
                    'ideal_profile_summary': ideal_profile,
                    'persons': formatted_results
                }, indent=2)
                
            finally:
                db.close()
                
        except Exception as e:
            return json.dumps({
                'error': str(e),
                'persons': []
            }, indent=2)


# Tool factory function for easy instantiation
def create_person_search_tools(customer_id: str) -> List[BaseTool]:
    """
    Create all person search tools for a given customer.
    
    Args:
        customer_id: Customer ID for multi-tenancy
        
    Returns:
        List of instantiated search tools
    """
    return [
        PersonFullTextSearchTool(customer_id=customer_id),
        PersonSkillSearchTool(customer_id=customer_id),
        PersonCareerPathTool(customer_id=customer_id),
        PersonLookAlikeSearchTool(customer_id=customer_id),
    ]

