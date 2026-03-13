"""
Enhanced PDL Query Builder

Builds detailed PDL queries using:
- Career Blueprints (skill patterns, trajectory, target companies)
- Company DNA (organizational fit, success patterns)
- Diagnostic Report (JD requirements, priorities)
- Baseline Profile (employee patterns)

Generates highly targeted queries for quality candidate matches.
"""
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
import structlog

from src.models.talent_analysis import DiagnosticReport, BaselineProfile
from src.models.talent_config import CareerBlueprint, CompanyDNAProfile
from src.services.talent.pdl_query_builder import PDLQueryParams

logger = structlog.get_logger(__name__)


class EnhancedPDLQueryBuilder:
    """
    Enhanced PDL query builder using blueprints and DNA.
    
    Generates more targeted queries by combining:
    1. Blueprint skill profiles and company patterns
    2. DNA success patterns and hiring preferences
    3. Diagnostic requirements from JD
    4. Baseline employee patterns
    """
    
    def __init__(
        self,
        blueprint: Optional[CareerBlueprint] = None,
        company_dna: Optional[CompanyDNAProfile] = None
    ):
        """
        Initialize with optional blueprint and DNA.
        
        Args:
            blueprint: Career Blueprint for skill/trajectory patterns
            company_dna: Company DNA for organizational patterns
        """
        self.blueprint = blueprint
        self.company_dna = company_dna
        self.logger = logger.bind(
            service="enhanced_pdl_query_builder",
            blueprint_id=blueprint.id if blueprint else None,
            dna_id=company_dna.id if company_dna else None
        )
    
    def build_enhanced_query(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile,
        role: str = "",
        limit: int = 50
    ) -> PDLQueryParams:
        """
        Build an enhanced PDL query using all available context.
        
        Args:
            diagnostic: Diagnostic report with JD requirements
            baseline: Baseline profile from employees
            role: Target role title
            limit: Number of results
            
        Returns:
            PDLQueryParams with detailed targeting
        """
        self.logger.info(
            "building_enhanced_query",
            role=role,
            has_blueprint=self.blueprint is not None,
            has_dna=self.company_dna is not None
        )
        
        # Extract skills from all sources
        required_skills, optional_skills = self._build_skill_requirements(
            diagnostic, baseline
        )
        
        # Extract experience range
        min_exp, max_exp = self._build_experience_range(diagnostic, baseline)
        
        # Extract company targeting
        company_types, industries, past_companies = self._build_company_targeting(
            diagnostic, baseline
        )
        
        # Extract education requirements
        degrees, majors = self._build_education_requirements(diagnostic, baseline)
        
        # Extract locations
        locations = self._build_location_targeting(diagnostic, baseline)
        
        # Determine job title role category
        job_title_role = self._determine_role_category(role)
        
        query = PDLQueryParams(
            job_title_role=job_title_role,
            job_title=role.lower(),
            required_skills=required_skills[:5],  # PDL works best with 5 or fewer
            optional_skills=optional_skills[:10],
            min_years_experience=min_exp,
            max_years_experience=max_exp,
            current_company_types=company_types,
            current_company_industries=industries,
            past_company_names=past_companies[:15],  # Top 15 target companies
            education_degrees=degrees,
            education_majors=majors,
            locations=locations,
            limit=limit,
            version=1,
            refinement_notes=self._build_refinement_notes()
        )
        
        self.logger.info(
            "enhanced_query_built",
            required_skills=len(required_skills),
            optional_skills=len(optional_skills),
            target_companies=len(past_companies),
            experience_range=f"{min_exp}-{max_exp}"
        )
        
        return query
    
    def _build_skill_requirements(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> Tuple[List[str], List[str]]:
        """Build skill requirements from all sources."""
        required_skills = set()
        optional_skills = set()
        
        # 1. From diagnostic (JD requirements)
        for skill in diagnostic.required_skills:
            required_skills.add(skill.lower())
        for skill in diagnostic.preferred_skills:
            optional_skills.add(skill.lower())
        
        # 2. From baseline (employee patterns)
        if baseline.skill_distributions:
            sorted_skills = sorted(
                baseline.skill_distributions.items(),
                key=lambda x: x[1],
                reverse=True
            )
            # Top 3 baseline skills are required
            for skill, freq in sorted_skills[:3]:
                if freq >= 0.5:  # Present in 50%+ of employees
                    required_skills.add(skill.lower())
                else:
                    optional_skills.add(skill.lower())
            # Next 7 are optional
            for skill, _ in sorted_skills[3:10]:
                optional_skills.add(skill.lower())
        
        # 3. From blueprint (look-alike patterns)
        if self.blueprint and self.blueprint.skill_profile:
            sp = self.blueprint.skill_profile
            
            # Core skills from blueprint are required
            for skill in sp.get("core_skills", [])[:5]:
                required_skills.add(skill.lower())
            
            # Common skills are optional
            for skill in sp.get("common_skills", []):
                if skill.lower() not in required_skills:
                    optional_skills.add(skill.lower())
        
        # 4. From DNA (organizational skill profile)
        if self.company_dna and self.company_dna.workforce_dna:
            dna_skills = self.company_dna.workforce_dna.get("skill_profile", {})
            
            # DNA core skills boost required
            for skill in dna_skills.get("core_skills", [])[:3]:
                required_skills.add(skill.lower())
        
        # Remove optional skills that are already required
        optional_skills = optional_skills - required_skills
        
        return list(required_skills), list(optional_skills)
    
    def _build_experience_range(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> Tuple[int, int]:
        """Build experience range from all sources."""
        min_exp = 2
        max_exp = 15
        
        # From baseline
        baseline_avg = baseline.average_years_experience
        min_exp = max(0, int(baseline_avg) - 3)
        max_exp = int(baseline_avg) + 5
        
        # From blueprint (if available)
        if self.blueprint and self.blueprint.experience_profile:
            ep = self.blueprint.experience_profile
            if ep.get("min_years"):
                min_exp = max(min_exp - 1, int(ep["min_years"]) - 1)  # Slightly broader
            if ep.get("max_years"):
                max_exp = min(max_exp + 2, int(ep["max_years"]) + 2)
        
        # From DNA (organizational average)
        if self.company_dna and self.company_dna.workforce_dna:
            dna_avg = self.company_dna.workforce_dna.get("avg_experience_years", baseline_avg)
            # Adjust toward DNA average
            target_avg = (baseline_avg + dna_avg) / 2
            min_exp = max(0, int(target_avg) - 4)
            max_exp = int(target_avg) + 6
        
        return min_exp, max_exp
    
    def _build_company_targeting(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> Tuple[List[str], List[str], List[str]]:
        """Build company targeting from all sources."""
        company_types = ["private", "public"]
        industries = ["technology", "software"]
        target_companies = set()
        
        # From baseline (company clusters - use actual data, no hardcoded lists)
        for cluster in baseline.company_clusters:
            if isinstance(cluster, dict):
                # Structured cluster with company list
                for company in cluster.get("companies", []):
                    target_companies.add(company.lower())
            elif isinstance(cluster, str):
                # Simple company name string
                target_companies.add(cluster.lower())
        
        # From blueprint (common companies from look-alikes)
        if self.blueprint and self.blueprint.company_progression:
            cp = self.blueprint.company_progression
            for company in cp.get("common_companies", []):
                target_companies.add(company.lower())
            
            # Industries from blueprint
            for industry in cp.get("industries", []):
                if industry.lower() not in industries:
                    industries.append(industry.lower())
        
        # From DNA (success patterns)
        if self.company_dna and self.company_dna.success_patterns:
            sp = self.company_dna.success_patterns
            for company in sp.get("common_previous_companies", []):
                target_companies.add(company.lower())
        
        # From DNA (boost companies)
        if self.company_dna and self.company_dna.pdl_query_modifiers:
            pm = self.company_dna.pdl_query_modifiers
            for company in pm.get("boost_companies", []):
                target_companies.add(company.lower())
        
        return company_types, industries, list(target_companies)
    
    def _build_education_requirements(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> Tuple[List[str], List[str]]:
        """Build education requirements from blueprint data (no hardcoded majors)."""
        degrees = ["bachelors", "masters"]
        majors = []
        
        # From blueprint (education profile) - derives majors from actual data
        if self.blueprint and self.blueprint.education_profile:
            ep = self.blueprint.education_profile
            
            degree_dist = ep.get("degree_distribution", {})
            if degree_dist.get("phd", 0) > 0.2:
                degrees.append("phd")
            
            for major in ep.get("common_majors", []):
                if major.lower() not in majors:
                    majors.append(major.lower())
        
        return degrees, majors
    
    def _build_location_targeting(
        self,
        diagnostic: DiagnosticReport,
        baseline: BaselineProfile
    ) -> List[str]:
        """Build location targeting."""
        locations = []
        
        # Default tech hubs
        default_locations = [
            "san francisco, california",
            "new york, new york",
            "seattle, washington",
            "austin, texas",
            "boston, massachusetts"
        ]
        
        # Check if DNA indicates remote-friendly
        if self.company_dna and self.company_dna.culture_indicators:
            ci = self.company_dna.culture_indicators
            if ci.get("remote_friendly", False):
                # Don't filter by location for remote-friendly orgs
                return []
        
        # Use default locations for non-remote orgs
        return default_locations
    
    def _determine_role_category(self, role: str) -> List[str]:
        """Determine PDL job_title_role category from role title."""
        role_lower = role.lower()
        
        if any(kw in role_lower for kw in ["engineer", "developer", "architect", "sre", "devops"]):
            return ["engineering"]
        elif any(kw in role_lower for kw in ["data scientist", "ml", "machine learning", "ai"]):
            return ["engineering", "research"]
        elif any(kw in role_lower for kw in ["product manager", "product owner"]):
            return ["product"]
        elif any(kw in role_lower for kw in ["designer", "ux", "ui"]):
            return ["design"]
        elif any(kw in role_lower for kw in ["sales", "account"]):
            return ["sales"]
        elif any(kw in role_lower for kw in ["marketing", "growth"]):
            return ["marketing"]
        else:
            return ["engineering"]  # Default
    
    def _build_refinement_notes(self) -> str:
        """Build refinement notes describing query sources."""
        sources = ["Diagnostic Report"]
        
        if self.blueprint:
            sources.append(f"Blueprint: {self.blueprint.name}")
        if self.company_dna:
            sources.append(f"DNA: {self.company_dna.company_name}/{self.company_dna.role_category}")
        
        return f"Enhanced query built from: {', '.join(sources)}"
    
    def convert_to_pdl_api_payload(self, query_params: PDLQueryParams) -> Dict[str, Any]:
        """
        Convert PDLQueryParams to PDL API payload.
        
        Uses PDL's SQL-like query syntax for precise matching.
        """
        sql_clauses = []
        
        # Job title role (standardized category)
        if query_params.job_title_role:
            role_clause = " OR ".join([f'job_title_role:"{r}"' for r in query_params.job_title_role])
            sql_clauses.append(f"({role_clause})")
        
        # Job title (specific title matching)
        if query_params.job_title:
            sql_clauses.append(f'job_title:"{query_params.job_title}"')
        
        # Required skills (AND - must have all)
        if query_params.required_skills:
            skill_clause = " AND ".join([f'skills:"{s}"' for s in query_params.required_skills])
            sql_clauses.append(f"({skill_clause})")
        
        # Experience range
        if query_params.min_years_experience is not None:
            sql_clauses.append(f"inferred_years_experience:>={query_params.min_years_experience}")
        if query_params.max_years_experience is not None:
            sql_clauses.append(f"inferred_years_experience:<={query_params.max_years_experience}")
        
        # Company industries
        if query_params.current_company_industries:
            ind_clause = " OR ".join([f'job_company_industry:"{i}"' for i in query_params.current_company_industries])
            sql_clauses.append(f"({ind_clause})")
        
        # Past companies (OR - any of these)
        if query_params.past_company_names:
            # Use experience.company.name for past companies
            company_clause = " OR ".join([f'experience.company.name:"{c}"' for c in query_params.past_company_names])
            sql_clauses.append(f"({company_clause})")
        
        # Education degrees
        if query_params.education_degrees:
            deg_clause = " OR ".join([f'education.degrees:"{d}"' for d in query_params.education_degrees])
            sql_clauses.append(f"({deg_clause})")
        
        # Education majors
        if query_params.education_majors:
            maj_clause = " OR ".join([f'education.majors:"{m}"' for m in query_params.education_majors])
            sql_clauses.append(f"({maj_clause})")
        
        # Locations
        if query_params.locations:
            loc_clause = " OR ".join([f'location_name:"{l}"' for l in query_params.locations])
            sql_clauses.append(f"({loc_clause})")
        
        # Combine with AND
        sql_query = " AND ".join(sql_clauses) if sql_clauses else ""
        
        payload = {
            "sql": f"SELECT * FROM person WHERE {sql_query}" if sql_query else "SELECT * FROM person",
            "size": query_params.limit,
            "pretty": True
        }
        
        self.logger.info(
            "pdl_payload_created",
            query_length=len(sql_query),
            clause_count=len(sql_clauses),
            limit=query_params.limit
        )
        
        return payload

