"""
Role Baseline Builder

Builds baseline profiles for ANY role type by analyzing current employees.
Uses Neo4j to extract career path patterns, skill distributions, and success indicators.

Role-agnostic: queries are parameterized by the target role provided at build time.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog

from src.models.talent_analysis import BaselineProfile, CareerPathPattern

logger = structlog.get_logger(__name__)


class RoleBaselineBuilder:
    """
    Builds baseline profiles for any role type.
    
    Analyzes current employees in the target role at the company to extract:
    - Common career paths
    - Skill distributions
    - Company clusters
    - Success patterns
    
    Default weights with optional adjustments from diagnostic analysis.
    """
    
    # Default attribute weights (role-agnostic)
    DEFAULT_WEIGHTS = {
        "technical_skills": 0.30,     # Core technical/domain skills for the role
        "engineering_skills": 0.20,   # General professional/engineering skills
        "experience_level": 0.15,     # Years of experience
        "career_trajectory": 0.15,    # Progression pattern
        "company_background": 0.10,   # Company cluster fit
        "achievements": 0.10          # Quantified impact
    }
    
    def __init__(self, neo4j_service=None):
        """
        Initialize baseline builder.
        
        Args:
            neo4j_service: Neo4j service for graph queries (optional, will import if needed)
        """
        self.logger = logger.bind(service="role_baseline_builder")
        self.neo4j_service = neo4j_service
    
    def _get_neo4j_service(self):
        """Lazy initialization of Neo4j service."""
        if self.neo4j_service is None:
            try:
                from src.services.graph.neo4j_service import Neo4jService
                self.neo4j_service = Neo4jService()
                self.logger.info("Neo4j service initialized for baseline builder")
            except ImportError as e:
                self.logger.error("Failed to import Neo4j service", error=str(e))
                raise ImportError("Neo4j service not available")
        
        return self.neo4j_service
    
    def build(
        self,
        customer_id: str,
        role: str = "",
        diagnostic_adjustments: Optional[Dict[str, float]] = None,
        employee_ids: Optional[List[int]] = None
    ) -> BaselineProfile:
        """
        Build baseline profile for the target role.
        
        Args:
            customer_id: Customer ID to query employees for
            role: Target role to build baseline for (e.g., 'Backend Engineer', 'Data Scientist')
            diagnostic_adjustments: Optional weight adjustments from diagnostic agent
            employee_ids: Optional specific employee IDs to use as baseline (if None, queries by role)
            
        Returns:
            BaselineProfile with role-specific patterns and weights
        """
        try:
            self.logger.info("Building role baseline", customer_id=customer_id, role=role)
            
            # Query employees in the target role from Neo4j (or from PDL persons table if employee_ids provided)
            role_employees = self._query_role_employees(customer_id, role, employee_ids)
            
            if not role_employees:
                self.logger.warning(
                    "No employees found for role",
                    customer_id=customer_id,
                    role=role
                )
                return self._create_empty_baseline(role, diagnostic_adjustments)
            
            self.logger.info(
                "Found employees for baseline",
                count=len(role_employees),
                customer_id=customer_id,
                role=role
            )
            
            # Extract patterns from career paths
            career_paths = self._analyze_career_paths(role_employees)
            
            # Analyze skill distributions
            skill_dist = self._analyze_skills(role_employees)
            
            # Find company clusters
            company_clusters = self._find_company_clusters(role_employees)
            
            # Calculate average experience
            avg_experience = self._calculate_avg_experience(role_employees)
            
            # Identify success patterns
            success_patterns = self._identify_success_patterns(role_employees)
            
            # Merge default weights with diagnostic adjustments
            final_weights = self.DEFAULT_WEIGHTS.copy()
            if diagnostic_adjustments:
                for attr, adjustment in diagnostic_adjustments.items():
                    if attr in final_weights:
                        final_weights[attr] = adjustment
                        self.logger.info(
                            "Applied diagnostic adjustment",
                            attribute=attr,
                            original=self.DEFAULT_WEIGHTS[attr],
                            adjusted=adjustment
                        )
            
            # Calculate data quality
            quality_score = self._calculate_quality_score(role_employees)
            
            baseline = BaselineProfile(
                role_type=role,
                prototype_employee_ids=[e['id'] for e in role_employees],
                attribute_weights=final_weights,
                common_career_paths=career_paths,
                skill_distributions=skill_dist,
                company_clusters=company_clusters,
                average_years_experience=avg_experience,
                success_patterns=success_patterns,
                data_quality_score=quality_score
            )
            
            self.logger.info(
                "Baseline profile built successfully",
                role=role,
                employee_count=len(role_employees),
                career_paths=len(career_paths),
                skills=len(skill_dist),
                quality_score=quality_score
            )
            
            return baseline
            
        except Exception as e:
            self.logger.error(
                "Failed to build baseline profile",
                customer_id=customer_id,
                role=role,
                error=str(e)
            )
            return self._create_empty_baseline(role, diagnostic_adjustments)
    
    def _query_role_employees(self, customer_id: str, role: str, employee_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        Query Neo4j for current employees in the target role, or fetch specific employees from PDL persons table.
        
        Args:
            customer_id: Customer ID
            role: Target role title to search for
            employee_ids: Optional list of specific employee IDs to use (queries PDL persons table)
            
        Returns:
            List of employee data dictionaries
        """
        # If specific employee_ids provided, query from PDL persons table instead of Neo4j
        if employee_ids:
            try:
                from src.models.database import SessionLocal, init_database
                from src.models.connector import PDLPerson
                
                if SessionLocal is None:
                    init_database()
                
                db = SessionLocal()
                try:
                    employees = db.query(PDLPerson).filter(
                        PDLPerson.id.in_(employee_ids)
                    ).all()
                    
                    result = []
                    for emp in employees:
                        result.append({
                            "id": emp.id,
                            "full_name": emp.full_name,
                            "current_title": emp.job_title,
                            "skills": emp.skills if isinstance(emp.skills, list) else [],
                            "years_experience": emp.inferred_years_experience or 5,
                            "current_company": emp.job_company_name,
                            "education": []
                        })
                    
                    self.logger.info(f"Fetched {len(result)} specific employees from PDL persons table")
                    return result
                finally:
                    db.close()
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch employees from PDL persons: {e}")
        
        # Default: Query Neo4j for employees matching the target role
        try:
            neo4j = self._get_neo4j_service()
            
            # Build role search terms from the provided role
            role_lower = role.lower()
            role_keywords = self._extract_role_keywords(role_lower)
            
            # Build dynamic CONTAINS clause from role keywords
            contains_clauses = " OR ".join([
                f"toLower(p.current_title) CONTAINS '{kw}'"
                for kw in role_keywords
            ])
            
            query = f"""
            MATCH (p:Person)-[r:EMPLOYED_AT]->(c:Company)
            WHERE c.customer_id = $customer_id
              AND ({contains_clauses})
              AND r.is_current = true
            
            // Get full career path
            MATCH (p)-[e:WORKED_AT]->(company:Company)
            WITH p, c, collect({{
                company: company.name,
                title: e.title,
                start_date: e.start_date,
                end_date: e.end_date,
                is_current: e.is_current
            }}) as career_history
            ORDER BY e.start_date
            
            RETURN 
                p.pdl_id as id,
                p.full_name as name,
                p.current_title as current_title,
                c.name as current_company,
                p.skills as skills,
                p.years_experience as years_experience,
                career_history
            LIMIT 50
            """
            
            result = neo4j.run_query(query, {"customer_id": customer_id})
            
            employees = []
            for record in result:
                employees.append(dict(record))
            
            return employees
            
        except Exception as e:
            self.logger.error(
                "Failed to query employees from Neo4j",
                customer_id=customer_id,
                role=role,
                error=str(e)
            )
            return []
    
    def _extract_role_keywords(self, role_lower: str) -> List[str]:
        """
        Extract search keywords from a role title for Neo4j CONTAINS queries.
        
        Generates multiple variations to maximize matches.
        E.g., 'Senior Machine Learning Engineer' -> ['machine learning', 'ml engineer', 'ml']
        """
        keywords = set()
        
        # Add the full role (without seniority prefix)
        clean_role = role_lower
        for prefix in ['senior ', 'staff ', 'principal ', 'lead ', 'junior ', 'sr ', 'jr ']:
            if clean_role.startswith(prefix):
                clean_role = clean_role[len(prefix):]
                break
        
        keywords.add(clean_role)
        
        # Add individual significant words (skip common filler words)
        skip_words = {'senior', 'junior', 'staff', 'principal', 'lead', 'sr', 'jr', 'the', 'a', 'an', 'of', 'and', 'or', 'in'}
        for word in role_lower.split():
            if word not in skip_words and len(word) > 2:
                keywords.add(word)
        
        return list(keywords)
    
    def _analyze_career_paths(self, employees: List[Dict[str, Any]]) -> List[CareerPathPattern]:
        """
        Analyze career progression patterns.
        
        Looks for common patterns like:
        - Startup IC → Scale-up Senior → Tech Lead
        - Big Tech IC → Startup Senior
        - Academic → Industry transition
        """
        patterns = []
        
        # Group by career progression type
        path_groups = {}
        
        for emp in employees:
            career_history = emp.get('career_history', [])
            
            if len(career_history) < 2:
                continue
            
            # Create a simplified path signature
            path_sig = self._create_path_signature(career_history)
            
            if path_sig not in path_groups:
                path_groups[path_sig] = []
            
            path_groups[path_sig].append(emp['id'])
        
        # Convert to CareerPathPattern objects
        for path_sig, emp_ids in path_groups.items():
            if len(emp_ids) >= 2:  # Only patterns with 2+ employees
                patterns.append(CareerPathPattern(
                    path_description=path_sig,
                    frequency=len(emp_ids),
                    example_employees=emp_ids
                ))
        
        # Sort by frequency
        patterns.sort(key=lambda x: x.frequency, reverse=True)
        
        return patterns[:10]  # Top 10 patterns
    
    def _create_path_signature(self, career_history: List[Dict[str, Any]]) -> str:
        """
        Create a simplified career path signature.
        
        Example: "Startup IC → Scale-up Senior → Tech Lead"
        """
        if not career_history:
            return "Unknown"
        
        # Simplify each role
        simplified_roles = []
        for job in career_history[-4:]:  # Last 4 roles
            title = job.get('title', '').lower()
            company = job.get('company', '').lower()
            
            # Determine seniority
            if any(x in title for x in ['lead', 'principal', 'staff', 'senior staff']):
                level = "Lead"
            elif 'senior' in title or 'sr' in title:
                level = "Senior"
            elif 'junior' in title or 'jr' in title:
                level = "Junior"
            else:
                level = "Mid"
            
            # Determine company type (simplified)
            if any(x in company for x in ['google', 'facebook', 'amazon', 'microsoft', 'apple']):
                company_type = "BigTech"
            elif len(company) > 0:
                company_type = "Company"
            else:
                company_type = "Unknown"
            
            simplified_roles.append(f"{company_type} {level}")
        
        return " → ".join(simplified_roles)
    
    def _analyze_skills(self, employees: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Analyze skill distributions among baseline employees.
        
        Returns:
            Dict mapping skill name to frequency (0.0-1.0)
        """
        skill_counts = {}
        total_employees = len(employees)
        
        for emp in employees:
            skills = emp.get('skills', [])
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(',')]
            
            for skill in skills:
                if isinstance(skill, dict):
                    skill = skill.get('name', '')
                
                skill = str(skill).strip().lower()
                if skill:
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        # Convert to frequencies
        skill_frequencies = {
            skill: count / total_employees
            for skill, count in skill_counts.items()
        }
        
        # Sort by frequency and return top 50
        sorted_skills = sorted(
            skill_frequencies.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return dict(sorted_skills[:50])
    
    def _find_company_clusters(self, employees: List[Dict[str, Any]]) -> List[str]:
        """
        Find common companies in career paths.
        
        Returns:
            List of companies that appear frequently in career histories
        """
        company_counts = {}
        
        for emp in employees:
            career_history = emp.get('career_history', [])
            companies_visited = set()
            
            for job in career_history:
                company = job.get('company', '').strip()
                if company:
                    companies_visited.add(company)
            
            for company in companies_visited:
                company_counts[company] = company_counts.get(company, 0) + 1
        
        # Sort by frequency
        sorted_companies = sorted(
            company_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Return top 20 companies
        return [company for company, count in sorted_companies[:20]]
    
    def _calculate_avg_experience(self, employees: List[Dict[str, Any]]) -> float:
        """Calculate average years of experience."""
        total_experience = 0
        count = 0
        
        for emp in employees:
            years = emp.get('years_experience')
            if years is not None:
                total_experience += float(years)
                count += 1
        
        return total_experience / count if count > 0 else 5.0  # Default 5 years
    
    def _identify_success_patterns(self, employees: List[Dict[str, Any]]) -> List[str]:
        """
        Identify patterns that correlate with success.
        
        Success indicators:
        - Rapid progression (multiple promotions)
        - Working at top companies
        - Long tenure (not job hopping)
        - Diverse experience
        """
        patterns = []
        
        # Analyze progression speed
        rapid_progressions = 0
        for emp in employees:
            career_history = emp.get('career_history', [])
            if len(career_history) >= 3:
                # Check for title progression
                titles = [job.get('title', '').lower() for job in career_history]
                has_progression = any(
                    'senior' in titles[i+1] and 'senior' not in titles[i]
                    for i in range(len(titles)-1)
                )
                if has_progression:
                    rapid_progressions += 1
        
        if rapid_progressions / len(employees) > 0.3:
            patterns.append("Fast career progression (IC to Senior in 3-4 years)")
        
        # Check for startup experience
        startup_exp_count = 0
        for emp in employees:
            career_history = emp.get('career_history', [])
            has_startup = any(
                'startup' in job.get('company', '').lower()
                for job in career_history
            )
            if has_startup:
                startup_exp_count += 1
        
        if startup_exp_count / len(employees) > 0.4:
            patterns.append("Startup experience is common")
        
        # General patterns based on data (no hardcoded role assumptions)
        if employees:
            all_skills = []
            for emp in employees:
                skills = emp.get('skills', [])
                if isinstance(skills, list):
                    all_skills.extend([str(s).lower() for s in skills])
            
            if all_skills:
                from collections import Counter
                top_skills = Counter(all_skills).most_common(3)
                skill_names = [s[0] for s in top_skills]
                patterns.append(f"Common skills: {', '.join(skill_names)}")
        
        return patterns
    
    def _calculate_quality_score(self, employees: List[Dict[str, Any]]) -> float:
        """
        Calculate quality score for baseline data.
        
        Based on:
        - Number of employees (more is better)
        - Completeness of data
        - Career history depth
        """
        if not employees:
            return 0.0
        
        score = 0.0
        
        # Sample size score (max 0.4)
        sample_size = len(employees)
        if sample_size >= 20:
            score += 0.4
        elif sample_size >= 10:
            score += 0.3
        elif sample_size >= 5:
            score += 0.2
        else:
            score += 0.1
        
        # Data completeness score (max 0.4)
        complete_profiles = 0
        for emp in employees:
            has_skills = bool(emp.get('skills'))
            has_experience = bool(emp.get('years_experience'))
            has_career = len(emp.get('career_history', [])) > 0
            
            if has_skills and has_experience and has_career:
                complete_profiles += 1
        
        completeness = complete_profiles / len(employees)
        score += 0.4 * completeness
        
        # Career depth score (max 0.2)
        avg_career_length = sum(
            len(emp.get('career_history', []))
            for emp in employees
        ) / len(employees)
        
        if avg_career_length >= 4:
            score += 0.2
        elif avg_career_length >= 2:
            score += 0.1
        
        return min(score, 1.0)
    
    def _create_empty_baseline(
        self,
        role: str = "",
        diagnostic_adjustments: Optional[Dict[str, float]] = None
    ) -> BaselineProfile:
        """
        Create empty baseline profile when no employees found.
        
        Uses default weights only. No hardcoded role-specific assumptions.
        """
        final_weights = self.DEFAULT_WEIGHTS.copy()
        if diagnostic_adjustments:
            final_weights.update(diagnostic_adjustments)
        
        return BaselineProfile(
            role_type=role,
            prototype_employee_ids=[],
            attribute_weights=final_weights,
            common_career_paths=[],
            skill_distributions={},
            company_clusters=[],
            average_years_experience=5.0,
            success_patterns=[
                f"Default expectations for {role}",
                "Skills and experience derived from job description"
            ],
            data_quality_score=0.0
        )


# Backward compatibility alias
MLEngineerBaselineBuilder = RoleBaselineBuilder
