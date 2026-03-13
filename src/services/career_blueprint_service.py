"""
Career Blueprint Service

Manages Career Blueprints - reusable career pattern templates extracted from
look-alike LinkedIn profiles. Used to guide PDL queries and candidate scoring.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
import structlog

from src.models.talent_config import CareerBlueprint
from src.models.connector import PDLPerson

logger = structlog.get_logger(__name__)


class CareerBlueprintService:
    """
    Service for managing Career Blueprints.
    
    Blueprints capture career patterns from exemplary candidates/employees
    and are used to:
    1. Guide PDL search queries
    2. Score candidates on trajectory match
    3. Provide context to LLM for profile synthesis
    """
    
    def __init__(self, db: Session, customer_id: str):
        self.db = db
        self.customer_id = customer_id
        self.logger = logger.bind(service="career_blueprint", customer_id=customer_id)
    
    def list_blueprints(
        self,
        role_category: Optional[str] = None,
        active_only: bool = True
    ) -> List[CareerBlueprint]:
        """List all blueprints for the customer."""
        query = self.db.query(CareerBlueprint).filter(
            CareerBlueprint.customer_id == self.customer_id
        )
        
        if active_only:
            query = query.filter(CareerBlueprint.is_active == True)
        
        if role_category:
            query = query.filter(CareerBlueprint.role_category == role_category)
        
        return query.order_by(CareerBlueprint.updated_at.desc()).all()
    
    def get_blueprint(self, blueprint_id: int) -> Optional[CareerBlueprint]:
        """Get a specific blueprint by ID."""
        return self.db.query(CareerBlueprint).filter(
            and_(
                CareerBlueprint.id == blueprint_id,
                CareerBlueprint.customer_id == self.customer_id
            )
        ).first()
    
    def get_blueprint_profiles(self, blueprint_id: int) -> List[Dict[str, Any]]:
        """
        Get the full PDL profile data for a blueprint's source profiles.
        
        This fetches the cached PDLPerson records using the stored IDs,
        providing the complete profile data for analysis without duplication.
        
        Args:
            blueprint_id: The blueprint to get profiles for
            
        Returns:
            List of full profile dictionaries from pdl_persons table
        """
        from src.models.connector import PDLPerson
        
        blueprint = self.get_blueprint(blueprint_id)
        if not blueprint or not blueprint.source_pdl_person_ids:
            return []
        
        # Fetch all PDLPerson records for the stored IDs
        profiles = self.db.query(PDLPerson).filter(
            PDLPerson.id.in_(blueprint.source_pdl_person_ids)
        ).all()
        
        # Convert to dictionaries with full profile data
        result = []
        for person in profiles:
            result.append({
                "id": person.id,
                "pdl_id": person.pdl_id,
                "linkedin_url": person.linkedin_url,
                "linkedin_username": person.linkedin_username,
                "full_name": person.full_name,
                "first_name": person.first_name,
                "last_name": person.last_name,
                "job_title": person.job_title,
                "job_title_role": person.job_title_role,
                "job_company_name": person.job_company_name,
                "job_company_size": person.job_company_size,
                "job_company_industry": person.job_company_industry,
                "location_name": person.location_name,
                "location_country": person.location_country,
                "skills": person.skills or [],
                "inferred_years_experience": person.inferred_years_experience,
                "education_history": person.education_history or [],
                "work_history": person.work_history or [],
                "primary_email": person.primary_email,
                "raw_data": person.raw_data,  # Full PDL response if needed
            })
        
        return result
    
    def create_blueprint(
        self,
        name: str,
        linkedin_urls: List[str],
        enriched_profiles: List[Dict[str, Any]],
        description: Optional[str] = None,
        role_category: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> CareerBlueprint:
        """
        Create a new Career Blueprint from enriched LinkedIn profiles.
        
        Args:
            name: Blueprint name
            linkedin_urls: Source LinkedIn URLs
            enriched_profiles: PDL-enriched profile data
            description: Optional description
            role_category: Optional role category (e.g., "engineering")
            user_id: Creating user ID
            
        Returns:
            Created CareerBlueprint
        """
        self.logger.info(
            "creating_blueprint",
            name=name,
            profile_count=len(enriched_profiles)
        )
        
        # Extract patterns from profiles
        patterns = self._extract_patterns(enriched_profiles)
        
        # Generate PDL query hints
        pdl_hints = self._generate_pdl_hints(patterns, enriched_profiles)
        
        # Generate default scoring weights
        scoring_weights = self._generate_scoring_weights(patterns)
        
        # Extract PDL person IDs from enriched profiles (references to pdl_persons table)
        pdl_person_ids = []
        for profile in enriched_profiles:
            # The enriched profile should have a pdl_person_id from the cache
            if profile.get("pdl_person_id"):
                pdl_person_ids.append(profile["pdl_person_id"])
            elif profile.get("id"):
                # Fallback if the ID is stored as 'id'
                pdl_person_ids.append(profile["id"])
        
        blueprint = CareerBlueprint(
            customer_id=self.customer_id,
            name=name,
            description=description,
            role_category=role_category,
            source_linkedin_urls=linkedin_urls,
            source_profile_count=len(enriched_profiles),
            source_pdl_person_ids=pdl_person_ids if pdl_person_ids else None,
            company_progression=patterns.get("company_progression"),
            role_progression=patterns.get("role_progression"),
            skill_profile=patterns.get("skill_profile"),
            experience_profile=patterns.get("experience_profile"),
            education_profile=patterns.get("education_profile"),
            pdl_query_hints=pdl_hints,
            scoring_weights=scoring_weights,
            created_by_user_id=user_id
        )
        
        self.db.add(blueprint)
        self.db.commit()
        self.db.refresh(blueprint)
        
        self.logger.info(
            "blueprint_created",
            blueprint_id=blueprint.id,
            name=name
        )
        
        return blueprint
    
    def update_blueprint(
        self,
        blueprint_id: int,
        updates: Dict[str, Any]
    ) -> Optional[CareerBlueprint]:
        """Update an existing blueprint."""
        blueprint = self.get_blueprint(blueprint_id)
        if not blueprint:
            return None
        
        # Update allowed fields
        allowed_fields = [
            "name", "description", "role_category",
            "pdl_query_hints", "scoring_weights",
            "hiring_preferences", "is_active"
        ]
        
        for field in allowed_fields:
            if field in updates:
                setattr(blueprint, field, updates[field])
        
        blueprint.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(blueprint)
        
        return blueprint
    
    def delete_blueprint(self, blueprint_id: int) -> bool:
        """Soft delete a blueprint (mark as inactive)."""
        blueprint = self.get_blueprint(blueprint_id)
        if not blueprint:
            return False
        
        blueprint.is_active = False
        blueprint.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        
        return True
    
    def record_usage(self, blueprint_id: int) -> None:
        """Record that a blueprint was used in an analysis."""
        blueprint = self.get_blueprint(blueprint_id)
        if blueprint:
            blueprint.usage_count += 1
            blueprint.last_used_at = datetime.now(timezone.utc)
            self.db.commit()
    
    def _extract_patterns(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract career patterns from enriched profiles.
        
        Analyzes multiple profiles to find common patterns in:
        - Company progression
        - Role progression
        - Skills
        - Experience
        - Education
        """
        if not profiles:
            return {}
        
        patterns = {}
        
        # Extract company progression
        patterns["company_progression"] = self._extract_company_progression(profiles)
        
        # Extract role progression
        patterns["role_progression"] = self._extract_role_progression(profiles)
        
        # Extract skill profile
        patterns["skill_profile"] = self._extract_skill_profile(profiles)
        
        # Extract experience profile
        patterns["experience_profile"] = self._extract_experience_profile(profiles)
        
        # Extract education profile
        patterns["education_profile"] = self._extract_education_profile(profiles)
        
        return patterns
    
    def _extract_company_progression(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract company progression patterns."""
        company_sizes = []
        industries = []
        companies = []
        
        for profile in profiles:
            # Current company
            company_name = profile.get("job_company_name")
            if isinstance(company_name, str) and company_name:
                companies.append(company_name.lower())
            
            company_size = profile.get("job_company_size")
            if company_size:
                company_sizes.append(company_size)
            
            company_industry = profile.get("job_company_industry")
            if isinstance(company_industry, str) and company_industry:
                industries.append(company_industry.lower())
            
            # Work history
            work_history = profile.get("work_history") or profile.get("experience") or []
            for job in work_history:
                if isinstance(job, dict):
                    company_info = job.get("company", {})
                    if isinstance(company_info, dict):
                        name = company_info.get("name")
                        if isinstance(name, str) and name:
                            companies.append(name.lower())
                        size = company_info.get("size")
                        if size:
                            company_sizes.append(size)
                        industry = company_info.get("industry")
                        if isinstance(industry, str) and industry:
                            industries.append(industry.lower())
        
        # Count frequencies
        company_freq = self._count_frequencies(companies)
        size_freq = self._count_frequencies(company_sizes)
        industry_freq = self._count_frequencies(industries)
        
        return {
            "common_companies": list(company_freq.keys())[:10],
            "company_sizes": list(size_freq.keys())[:5],
            "industries": list(industry_freq.keys())[:5],
            "company_frequencies": dict(list(company_freq.items())[:10])
        }
    
    def _extract_role_progression(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract role progression patterns."""
        titles = []
        title_levels = []
        
        for profile in profiles:
            job_title = profile.get("job_title")
            if isinstance(job_title, str) and job_title:
                titles.append(job_title.lower())
            
            if profile.get("job_title_levels"):
                if isinstance(profile["job_title_levels"], list):
                    title_levels.extend(profile["job_title_levels"])
                else:
                    title_levels.append(profile["job_title_levels"])
            
            # Work history
            work_history = profile.get("work_history") or profile.get("experience") or []
            for job in work_history:
                if isinstance(job, dict):
                    title = job.get("title")
                    if isinstance(title, str) and title:
                        titles.append(title.lower())
        
        title_freq = self._count_frequencies(titles)
        level_freq = self._count_frequencies(title_levels)
        
        # Detect progression pattern
        pattern = self._detect_progression_pattern(profiles)
        
        return {
            "common_titles": list(title_freq.keys())[:10],
            "title_levels": list(level_freq.keys()),
            "pattern": pattern,
            "title_frequencies": dict(list(title_freq.items())[:10])
        }
    
    def _extract_skill_profile(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract skill patterns."""
        all_skills = []
        
        for profile in profiles:
            skills = profile.get("skills") or []
            if isinstance(skills, list):
                for skill in skills:
                    if isinstance(skill, str):
                        all_skills.append(skill.lower())
                    elif isinstance(skill, dict):
                        all_skills.append(skill.get("name", "").lower())
        
        skill_freq = self._count_frequencies(all_skills)
        
        # Categorize skills
        core_skills = [s for s, f in skill_freq.items() if f >= 0.5][:15]
        common_skills = [s for s, f in skill_freq.items() if 0.25 <= f < 0.5][:10]
        
        return {
            "core_skills": core_skills,
            "common_skills": common_skills,
            "skill_frequencies": dict(list(skill_freq.items())[:30])
        }
    
    def _extract_experience_profile(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract experience patterns."""
        years_list = []
        role_counts = []
        
        for profile in profiles:
            years = profile.get("inferred_years_experience") or profile.get("years_experience")
            if years:
                years_list.append(float(years))
            
            work_history = profile.get("work_history") or profile.get("experience") or []
            if work_history:
                role_counts.append(len(work_history))
        
        if not years_list:
            return {"avg_years": 5, "min_years": 2, "max_years": 10}
        
        return {
            "avg_years": round(sum(years_list) / len(years_list), 1),
            "min_years": min(years_list),
            "max_years": max(years_list),
            "avg_role_count": round(sum(role_counts) / len(role_counts), 1) if role_counts else 3
        }
    
    def _extract_education_profile(self, profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract education patterns."""
        degrees = []
        majors = []
        schools = []
        
        for profile in profiles:
            education = profile.get("education_history") or profile.get("education") or []
            for edu in education:
                if isinstance(edu, dict):
                    degree = edu.get("degree")
                    if isinstance(degree, str) and degree:
                        degrees.append(degree.lower())
                    major = edu.get("major")
                    if isinstance(major, str) and major:
                        majors.append(major.lower())
                    school_info = edu.get("school", {})
                    if isinstance(school_info, dict):
                        school_name = school_info.get("name")
                        if isinstance(school_name, str) and school_name:
                            schools.append(school_name)
        
        degree_freq = self._count_frequencies(degrees)
        major_freq = self._count_frequencies(majors)
        
        return {
            "degree_distribution": degree_freq,
            "common_majors": list(major_freq.keys())[:5],
            "common_schools": list(set(schools))[:10]
        }
    
    def _generate_pdl_hints(
        self,
        patterns: Dict[str, Any],
        profiles: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate PDL query hints from extracted patterns."""
        hints = {}
        
        # Suggested titles from role progression
        if patterns.get("role_progression", {}).get("common_titles"):
            hints["suggested_titles"] = patterns["role_progression"]["common_titles"][:5]
        
        # Suggested skills from skill profile
        if patterns.get("skill_profile", {}).get("core_skills"):
            hints["suggested_skills"] = patterns["skill_profile"]["core_skills"][:5]
        
        # Experience range from experience profile
        exp = patterns.get("experience_profile", {})
        if exp:
            hints["experience_range"] = [
                max(0, int(exp.get("min_years", 2)) - 1),
                int(exp.get("max_years", 10)) + 2
            ]
        
        # Target companies from company progression
        if patterns.get("company_progression", {}).get("common_companies"):
            hints["target_companies"] = patterns["company_progression"]["common_companies"][:10]
        
        # Industries
        if patterns.get("company_progression", {}).get("industries"):
            hints["target_industries"] = patterns["company_progression"]["industries"][:5]
        
        return hints
    
    def _generate_scoring_weights(self, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Generate default scoring weights based on patterns."""
        # Default weights - can be adjusted by user
        return {
            "skill_alignment": 0.30,
            "experience_fit": 0.20,
            "trajectory_match": 0.20,
            "company_background": 0.15,
            "organizational_fit": 0.15
        }
    
    def _count_frequencies(self, items: List[str]) -> Dict[str, float]:
        """Count item frequencies as ratios."""
        if not items:
            return {}
        
        counts = {}
        for item in items:
            if item:
                counts[item] = counts.get(item, 0) + 1
        
        total = len(items)
        return {k: round(v / total, 3) for k, v in sorted(counts.items(), key=lambda x: -x[1])}
    
    def _detect_progression_pattern(self, profiles: List[Dict[str, Any]]) -> str:
        """Detect common career progression pattern."""
        # Simplified pattern detection
        patterns = []
        
        for profile in profiles:
            work_history = profile.get("work_history") or profile.get("experience") or []
            if len(work_history) >= 2:
                titles = []
                for job in work_history[-3:]:
                    if isinstance(job, dict):
                        title = job.get("title")
                        if isinstance(title, str):
                            titles.append(title.lower())
                        else:
                            titles.append("")
                
                has_senior = any("senior" in t for t in titles)
                has_lead = any("lead" in t or "principal" in t or "staff" in t for t in titles)
                
                if has_lead:
                    patterns.append("leadership")
                elif has_senior:
                    patterns.append("senior")
                else:
                    patterns.append("ic")
        
        if not patterns:
            return "IC → Senior"
        
        leadership_rate = patterns.count("leadership") / len(patterns)
        senior_rate = patterns.count("senior") / len(patterns)
        
        if leadership_rate > 0.3:
            return "IC → Senior → Lead/Staff"
        elif senior_rate > 0.5:
            return "IC → Senior"
        else:
            return "Individual Contributor"

