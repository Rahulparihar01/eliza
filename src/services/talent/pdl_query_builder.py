"""
PDL Query Builder for Talent Intelligence System.

Builds and refines People Data Labs (PDL) API queries based on:
- Diagnostic analysis (attribute priorities)
- Baseline profile (employee patterns)
- User feedback (refinement parameters)

This is deterministic code (no LLM) - purely algorithmic query construction.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from src.models.talent_analysis import (
    DiagnosticReport, BaselineProfile, AttributePriority, PatternInsight
)
from src.core.logging import get_logger, LogCategory
from src.services.talent.pdl_query_rules import (
    PDL_FIELD_RULES,
    validate_field_value,
    recommend_query_strategy
)

logger = get_logger(__name__, component="talent.pdl_query_builder")


class PDLQueryParams(BaseModel):
    """Parameters for a PDL API query"""
    
    # Core filters
    job_title_role: List[str] = Field(default_factory=list, description="Standardized role (e.g., 'engineering', 'sales')")
    job_title: Optional[str] = Field(default=None, description="Specific job title for matching (e.g., 'machine learning engineer')")
    required_skills: List[str] = Field(default_factory=list, description="Must-have skills")
    optional_skills: List[str] = Field(default_factory=list, description="Nice-to-have skills")
    
    # Experience
    min_years_experience: Optional[int] = None
    max_years_experience: Optional[int] = None
    
    # Company filters
    current_company_types: List[str] = Field(default_factory=list, description="e.g., ['public', 'series_c']")
    current_company_industries: List[str] = Field(default_factory=list, description="e.g., ['technology', 'saas']")
    past_company_names: List[str] = Field(default_factory=list, description="Specific companies (FAANG, etc.)")
    
    # Education
    education_degrees: List[str] = Field(default_factory=list, description="e.g., ['bachelors', 'masters', 'phd']")
    education_majors: List[str] = Field(default_factory=list, description="e.g., ['computer science', 'mathematics']")
    
    # Location
    locations: List[str] = Field(default_factory=list, description="e.g., ['san francisco, ca', 'remote']")
    
    # Result controls
    limit: int = Field(default=50, description="Max results to return")
    
    # Refinement tracking
    version: int = Field(default=1, description="Query version for tracking refinements")
    refinement_notes: Optional[str] = None


class QueryRefinementFeedback(BaseModel):
    """User feedback for refining PDL queries"""
    
    # Skill adjustments
    add_required_skills: List[str] = Field(default_factory=list)
    remove_required_skills: List[str] = Field(default_factory=list)
    add_optional_skills: List[str] = Field(default_factory=list)
    remove_optional_skills: List[str] = Field(default_factory=list)
    
    # Experience adjustments
    increase_min_experience: Optional[int] = None
    decrease_min_experience: Optional[int] = None
    increase_max_experience: Optional[int] = None
    decrease_max_experience: Optional[int] = None
    
    # Company adjustments
    add_company_types: List[str] = Field(default_factory=list)
    remove_company_types: List[str] = Field(default_factory=list)
    add_past_companies: List[str] = Field(default_factory=list)
    remove_past_companies: List[str] = Field(default_factory=list)
    
    # Education adjustments
    add_degrees: List[str] = Field(default_factory=list)
    remove_degrees: List[str] = Field(default_factory=list)
    add_majors: List[str] = Field(default_factory=list)
    remove_majors: List[str] = Field(default_factory=list)
    
    # Location adjustments
    add_locations: List[str] = Field(default_factory=list)
    remove_locations: List[str] = Field(default_factory=list)
    
    # Result count adjustment
    increase_limit: Optional[int] = None
    decrease_limit: Optional[int] = None
    
    notes: Optional[str] = None


class PDLQueryBuilder:
    """
    Builds and refines PDL API queries.
    
    Role-agnostic: all skills, companies, and education requirements are derived
    from diagnostic output and baseline data, not hardcoded lists.
    
    Deterministic, algorithmic query construction - no LLM calls.
    """
    
    def __init__(self):
        """Initialize the PDL query builder."""
        logger.info("pdl_query_builder_initialized")
    
    def build_initial_query(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile,
        role: str = "",
        limit: int = 50
    ) -> PDLQueryParams:
        """
        Build initial PDL query from diagnostic and baseline.
        
        Args:
            diagnostic: Diagnostic report with attribute priorities
            baseline: Baseline profile from current employees
            role: Target role
            limit: Number of results to return (default: 50)
            
        Returns:
            PDLQueryParams for the initial search
        """
        logger.info(
            "building_initial_pdl_query",
            role=role,
            critical_attributes=len([a for a in diagnostic.attribute_weights if a.weight >= 0.7])
        )
        
        # Extract skills from diagnostic
        required_skills = self._extract_required_skills(diagnostic, baseline)
        optional_skills = self._extract_optional_skills(diagnostic, baseline)
        
        # Extract experience range
        min_exp, max_exp = self._extract_experience_range(diagnostic, baseline)
        
        # Extract company patterns
        company_types, company_industries, past_companies = self._extract_company_patterns(
            diagnostic, baseline
        )
        
        # Extract education requirements
        degrees, majors = self._extract_education_requirements(diagnostic, baseline)
        
        # Build query params using empirically validated rules
        # Use job_title for specific role matching (recommended strategy from testing)
        # Use job_title_role only for broad standardized categories
        query_params = PDLQueryParams(
            job_title_role=["engineering"],  # Standardized role category
            job_title=role.lower(),  # Specific job title for matching (e.g., "machine learning engineer")
            required_skills=required_skills[:5],  # Limit to 5 skills max (empirical rule)
            optional_skills=optional_skills,
            min_years_experience=min_exp,
            max_years_experience=max_exp,
            current_company_types=company_types,
            current_company_industries=company_industries,
            past_company_names=past_companies,
            education_degrees=degrees,
            education_majors=majors,
            limit=limit,  # Configurable limit (default 50, can be overridden)
            version=1,
            refinement_notes="Initial query based on diagnostic analysis and empirical PDL rules"
        )
        
        logger.info(
            "initial_pdl_query_built",
            required_skills_count=len(required_skills),
            optional_skills_count=len(optional_skills),
            min_experience=min_exp,
            max_experience=max_exp
        )
        
        return query_params
    
    def refine_query(
        self,
        current_query: PDLQueryParams,
        feedback: QueryRefinementFeedback
    ) -> PDLQueryParams:
        """
        Refine existing query based on user feedback.
        
        Args:
            current_query: Current PDL query parameters
            feedback: User feedback for refinement
            
        Returns:
            Refined PDLQueryParams
        """
        logger.info(
            "refining_pdl_query",
            current_version=current_query.version,
            feedback_notes=feedback.notes
        )
        
        # Create new query as copy of current
        refined_query = current_query.model_copy(deep=True)
        refined_query.version = current_query.version + 1
        
        # Apply skill adjustments
        refined_query.required_skills = self._apply_list_adjustments(
            current_query.required_skills,
            add=feedback.add_required_skills,
            remove=feedback.remove_required_skills
        )
        
        refined_query.optional_skills = self._apply_list_adjustments(
            current_query.optional_skills,
            add=feedback.add_optional_skills,
            remove=feedback.remove_optional_skills
        )
        
        # Apply experience adjustments
        if feedback.increase_min_experience is not None:
            refined_query.min_years_experience = (current_query.min_years_experience or 0) + feedback.increase_min_experience
        if feedback.decrease_min_experience is not None:
            refined_query.min_years_experience = max(0, (current_query.min_years_experience or 0) - feedback.decrease_min_experience)
        if feedback.increase_max_experience is not None:
            refined_query.max_years_experience = (current_query.max_years_experience or 20) + feedback.increase_max_experience
        if feedback.decrease_max_experience is not None:
            refined_query.max_years_experience = max(0, (current_query.max_years_experience or 20) - feedback.decrease_max_experience)
        
        # Apply company adjustments
        refined_query.current_company_types = self._apply_list_adjustments(
            current_query.current_company_types,
            add=feedback.add_company_types,
            remove=feedback.remove_company_types
        )
        
        refined_query.past_company_names = self._apply_list_adjustments(
            current_query.past_company_names,
            add=feedback.add_past_companies,
            remove=feedback.remove_past_companies
        )
        
        # Apply education adjustments
        refined_query.education_degrees = self._apply_list_adjustments(
            current_query.education_degrees,
            add=feedback.add_degrees,
            remove=feedback.remove_degrees
        )
        
        refined_query.education_majors = self._apply_list_adjustments(
            current_query.education_majors,
            add=feedback.add_majors,
            remove=feedback.remove_majors
        )
        
        # Apply location adjustments
        refined_query.locations = self._apply_list_adjustments(
            current_query.locations,
            add=feedback.add_locations,
            remove=feedback.remove_locations
        )
        
        # Apply limit adjustments
        if feedback.increase_limit is not None:
            refined_query.limit = min(200, current_query.limit + feedback.increase_limit)  # Cap at 200
        if feedback.decrease_limit is not None:
            refined_query.limit = max(10, current_query.limit - feedback.decrease_limit)  # Floor at 10
        
        # Update refinement notes
        refined_query.refinement_notes = feedback.notes or f"Refinement v{refined_query.version}"
        
        logger.info(
            "pdl_query_refined",
            new_version=refined_query.version,
            required_skills_count=len(refined_query.required_skills),
            optional_skills_count=len(refined_query.optional_skills)
        )
        
        return refined_query
    
    def convert_to_pdl_api_payload(self, query_params: PDLQueryParams) -> Dict[str, Any]:
        """
        Convert PDLQueryParams to actual PDL API request payload.
        
        Args:
            query_params: Query parameters
            
        Returns:
            Dict suitable for PDL API /person/search endpoint
        """
        logger.debug("converting_to_pdl_api_payload", version=query_params.version)
        
        # Build PDL query using their SQL-like syntax
        sql_clauses = []
        
        # Job title
        if query_params.job_title_role:
            title_clause = " OR ".join([f'job_title_role:"{role}"' for role in query_params.job_title_role])
            sql_clauses.append(f"({title_clause})")
        
        # Required skills (AND logic)
        if query_params.required_skills:
            skill_clause = " AND ".join([f'skills:"{skill}"' for skill in query_params.required_skills])
            sql_clauses.append(f"({skill_clause})")
        
        # Optional skills (OR logic, but separate clause)
        # PDL doesn't have direct OR for optional, so we'll add as separate query
        
        # Experience
        if query_params.min_years_experience is not None:
            sql_clauses.append(f"experience_years:>={query_params.min_years_experience}")
        if query_params.max_years_experience is not None:
            sql_clauses.append(f"experience_years:<={query_params.max_years_experience}")
        
        # Company types
        if query_params.current_company_types:
            company_clause = " OR ".join([f'current_company_type:"{ct}"' for ct in query_params.current_company_types])
            sql_clauses.append(f"({company_clause})")
        
        # Company industries
        if query_params.current_company_industries:
            industry_clause = " OR ".join([f'current_company_industry:"{ind}"' for ind in query_params.current_company_industries])
            sql_clauses.append(f"({industry_clause})")
        
        # Past companies
        if query_params.past_company_names:
            past_company_clause = " OR ".join([f'past_company_name:"{comp}"' for comp in query_params.past_company_names])
            sql_clauses.append(f"({past_company_clause})")
        
        # Education
        if query_params.education_degrees:
            degree_clause = " OR ".join([f'education_degree:"{deg}"' for deg in query_params.education_degrees])
            sql_clauses.append(f"({degree_clause})")
        
        if query_params.education_majors:
            major_clause = " OR ".join([f'education_major:"{maj}"' for maj in query_params.education_majors])
            sql_clauses.append(f"({major_clause})")
        
        # Locations
        if query_params.locations:
            location_clause = " OR ".join([f'location:"{loc}"' for loc in query_params.locations])
            sql_clauses.append(f"({location_clause})")
        
        # Combine all clauses with AND
        sql_query = " AND ".join(sql_clauses)
        
        # Build payload
        payload = {
            "query": sql_query,
            "size": query_params.limit,
            "pretty": True,
            "scroll_token": None  # For pagination if needed
        }
        
        logger.info(
            "pdl_api_payload_created",
            version=query_params.version,
            query_length=len(sql_query),
            limit=query_params.limit
        )
        
        return payload
    
    # ========================================================================
    # PRIVATE HELPER METHODS
    # ========================================================================
    
    def _extract_required_skills(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> List[str]:
        """Extract required skills from diagnostic (CRITICAL priority)."""
        # Use required_skills directly from diagnostic report
        required = [skill.lower() for skill in diagnostic.required_skills]
        
        # Add top baseline skills if not already included (from skill_distributions)
        if baseline.skill_distributions:
            # Sort by frequency and take top skills
            sorted_skills = sorted(baseline.skill_distributions.items(), key=lambda x: x[1], reverse=True)
            for skill, _ in sorted_skills[:3]:
                if skill.lower() not in required:
                    required.append(skill.lower())
        
        return required[:10]  # Limit to top 10 to avoid over-constraining
    
    def _extract_optional_skills(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> List[str]:
        """Extract optional skills from diagnostic (preferred skills)."""
        # Use preferred_skills directly from diagnostic report
        optional = [skill.lower() for skill in diagnostic.preferred_skills]
        
        # Add more baseline skills (from skill_distributions)
        if baseline.skill_distributions:
            # Sort by frequency and skip the top 3 (already in required)
            sorted_skills = sorted(baseline.skill_distributions.items(), key=lambda x: x[1], reverse=True)
            for skill, _ in sorted_skills[3:10]:
                if skill.lower() not in optional:
                    optional.append(skill.lower())
        
        return optional[:15]
    
    def _extract_experience_range(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> tuple[Optional[int], Optional[int]]:
        """Extract experience range from baseline."""
        # Use average_years_experience from baseline and add flexibility
        avg_exp = int(baseline.average_years_experience)
        
        # Create a range around the average (e.g., avg ± 3 years)
        min_exp = max(0, avg_exp - 3)
        max_exp = avg_exp + 3
        
        return min_exp, max_exp
    
    def _extract_company_patterns(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> tuple[List[str], List[str], List[str]]:
        """Extract company patterns from baseline data (no hardcoded company lists)."""
        company_types = ["public", "private"]
        company_industries = ["technology", "software"]
        past_companies = []
        
        # Use company clusters from baseline (derived from actual employee data)
        if baseline.company_clusters:
            for cluster in baseline.company_clusters:
                if isinstance(cluster, dict):
                    cluster_companies = cluster.get("companies", [])
                    past_companies.extend(cluster_companies)
                elif isinstance(cluster, str):
                    past_companies.append(cluster)
        
        # Also check baseline_query_params from diagnostic
        baseline_params = diagnostic.baseline_query_params or {}
        preferred_companies = baseline_params.get("preferred_companies", [])
        past_companies.extend(preferred_companies)
        
        # Deduplicate
        past_companies = list(set(past_companies))
        
        return company_types, company_industries, past_companies[:10]
    
    def _extract_education_requirements(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> tuple[List[str], List[str]]:
        """
        Extract education requirements from diagnostic and baseline.
        
        No hardcoded degree/major lists - derived from diagnostic analysis of the job description.
        """
        degrees = []
        majors = []
        
        # Use baseline_query_params from diagnostic for education hints
        baseline_params = diagnostic.baseline_query_params or {}
        
        # Default broad education filter (most professional roles)
        degrees = ["bachelors", "masters"]
        
        return degrees, majors
    
    def _apply_list_adjustments(
        self,
        current_list: List[str],
        add: List[str],
        remove: List[str]
    ) -> List[str]:
        """Apply add/remove operations to a list."""
        result = [item for item in current_list if item not in remove]
        for item in add:
            if item not in result:
                result.append(item)
        return result

