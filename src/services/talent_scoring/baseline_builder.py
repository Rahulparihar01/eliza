"""
Baseline Profile Builder

Creates cached baseline employee profiles by aggregating data from current employees.

Builds profiles for specific roles by:
- Finding all employees with matching titles/roles
- Aggregating skills, companies, education, career paths
- Computing average metrics (years of experience, etc.)
- Generating baseline embedding (average of employee embeddings)

Profiles are cached and rebuilt when:
- New employees are added
- Employee data changes
- Monthly refresh cycle
"""
from typing import Dict, Any, List, Optional
from collections import Counter
from datetime import datetime
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import func

import structlog

from src.models.connector import PDLPerson, BaselineEmployeeProfile

logger = structlog.get_logger(__name__)


class BaselineProfileBuilder:
    """
    Builds and maintains baseline employee profiles for roles.
    
    Aggregates data from current employees to create
    "look-alike" profiles for candidate matching.
    """
    
    def __init__(self, db: Session, customer_id: str):
        """
        Initialize baseline builder.
        
        Args:
            db: Database session
            customer_id: Customer ID for multi-tenancy
        """
        self.logger = logger.bind(service="baseline_builder", customer_id=customer_id)
        self.db = db
        self.customer_id = customer_id
    
    def build_baseline_for_role(
        self,
        role_title: str,
        company_name: Optional[str] = None,
        min_employees: int = 5
    ) -> Optional[BaselineEmployeeProfile]:
        """
        Build or update baseline profile for a specific role.
        
        Args:
            role_title: Target role (e.g., "Senior Backend Engineer")
            company_name: Filter by company (e.g., "Caylent") - uses exact match from PDL data
            min_employees: Minimum employees needed for baseline (default: 5)
            
        Returns:
            BaselineEmployeeProfile or None if insufficient data
        """
        try:
            self.logger.info(
                "Building baseline profile",
                role_title=role_title,
                company_name=company_name
            )
            
            # Find matching employees
            employees = self._find_matching_employees(role_title, company_name)
            
            if len(employees) < min_employees:
                self.logger.warning(
                    "Insufficient employees for baseline",
                    role_title=role_title,
                    found=len(employees),
                    required=min_employees
                )
                return None
            
            # Aggregate data
            aggregated_data = self._aggregate_employee_data(employees)
            
            # Check if baseline already exists
            existing_baseline = self.db.query(BaselineEmployeeProfile).filter(
                BaselineEmployeeProfile.customer_id == self.customer_id,
                BaselineEmployeeProfile.role_title == role_title
            ).first()
            
            if existing_baseline:
                # Update existing
                self._update_baseline(existing_baseline, employees, aggregated_data)
                baseline = existing_baseline
            else:
                # Create new
                baseline = self._create_baseline(role_title, employees, aggregated_data)
            
            self.logger.info(
                "Baseline profile built",
                role_title=role_title,
                employee_count=len(employees),
                baseline_id=baseline.id
            )
            
            return baseline
            
        except Exception as e:
            self.logger.error(
                "Failed to build baseline",
                role_title=role_title,
                error=str(e)
            )
            raise
    
    def _find_matching_employees(
        self,
        role_title: str,
        company_name: Optional[str] = None
    ) -> List[PDLPerson]:
        """
        Find employees matching the role title.
        
        Uses fuzzy matching on job titles in current/recent experience.
        
        Args:
            role_title: Target role
            company_name: Company to filter by (exact match on company_name field)
            
        Returns:
            List of matching PDLPerson records
        """
        query = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == self.customer_id
        )
        
        # Filter by company if specified
        if company_name:
            query = query.filter(
                PDLPerson.company_name == company_name
            )
        
        all_employees = query.all()
        
        # Filter by role (check current title or recent experience)
        matching_employees = []
        role_keywords = set(role_title.lower().split())
        
        for employee in all_employees:
            # Check current title
            if employee.title:
                title_keywords = set(employee.title.lower().split())
                if len(role_keywords & title_keywords) >= 2:  # At least 2 keywords match
                    matching_employees.append(employee)
                    continue
            
            # Check recent experience
            if employee.experience:
                for exp in employee.experience[:3]:  # Check top 3 recent roles
                    if exp.get("title", {}).get("name"):
                        exp_title = exp["title"]["name"].lower()
                        exp_keywords = set(exp_title.split())
                        if len(role_keywords & exp_keywords) >= 2:
                            matching_employees.append(employee)
                            break
        
        return matching_employees
    
    def _aggregate_employee_data(
        self,
        employees: List[PDLPerson]
    ) -> Dict[str, Any]:
        """
        Aggregate data across all employees.
        
        Computes:
        - Skills frequency map
        - Common companies
        - Education patterns (degrees, schools)
        - Career paths (common progressions)
        - Average years of experience
        - Baseline embedding (average)
        
        Args:
            employees: List of employees
            
        Returns:
            Aggregated data dictionary
        """
        aggregated = {}
        
        # Skills aggregation
        skills_counter = Counter()
        for emp in employees:
            if emp.skills:
                for skill in emp.skills:
                    skills_counter[skill.lower()] += 1
        
        aggregated["aggregated_skills"] = dict(skills_counter)
        
        # Companies aggregation
        companies_counter = Counter()
        for emp in employees:
            # Current company
            if emp.company_name:
                companies_counter[emp.company_name.lower()] += 1
            
            # Past companies
            if emp.experience:
                for exp in emp.experience:
                    company = exp.get("company", {})
                    if isinstance(company, dict):
                        company_name = company.get("name", "")
                    else:
                        company_name = str(company)
                    
                    if company_name:
                        companies_counter[company_name.lower()] += 1
        
        aggregated["common_companies"] = dict(companies_counter.most_common(20))
        
        # Education patterns
        degrees_counter = Counter()
        schools_counter = Counter()
        
        for emp in employees:
            if emp.education:
                for edu in emp.education:
                    # Degrees
                    degrees = edu.get("degrees", [])
                    if isinstance(degrees, list):
                        for degree in degrees:
                            degrees_counter[degree.lower()] += 1
                    
                    # Schools
                    school = edu.get("school", {})
                    if isinstance(school, dict):
                        school_name = school.get("name", "")
                    else:
                        school_name = str(school)
                    
                    if school_name:
                        schools_counter[school_name.lower()] += 1
        
        aggregated["education_patterns"] = {
            "common_degrees": [degree for degree, _ in degrees_counter.most_common(10)],
            "common_schools": [school for school, _ in schools_counter.most_common(15)]
        }
        
        # Career paths (common role progressions)
        career_paths = []
        for emp in employees:
            if emp.experience:
                # Extract progression (most recent to oldest)
                progression = []
                for exp in emp.experience[:5]:  # Up to 5 most recent roles
                    title = exp.get("title", {})
                    if isinstance(title, dict):
                        title_name = title.get("name", "")
                    else:
                        title_name = str(title)
                    
                    if title_name:
                        progression.append(title_name)
                
                if len(progression) >= 2:
                    career_paths.append(progression)
        
        # Find common patterns (simplified)
        aggregated["career_paths"] = career_paths[:10]  # Store top 10 examples
        
        # Average years of experience
        years_list = []
        for emp in employees:
            years = self._calculate_years_of_experience(emp)
            if years > 0:
                years_list.append(years)
        
        aggregated["avg_years_experience"] = (
            sum(years_list) / len(years_list) if years_list else 0
        )
        
        # Baseline embedding (average of all employee embeddings)
        embeddings = []
        for emp in employees:
            # TODO: Get employee embeddings from database or generate
            # For now, skip
            pass
        
        if embeddings:
            baseline_embedding = np.mean(embeddings, axis=0).tolist()
            aggregated["baseline_embedding"] = baseline_embedding
        else:
            aggregated["baseline_embedding"] = None
        
        return aggregated
    
    def _calculate_years_of_experience(self, employee: PDLPerson) -> float:
        """Calculate total years of experience for an employee."""
        if not employee.experience:
            return 0
        
        total_years = 0
        
        for exp in employee.experience:
            start_date = exp.get("start_date")
            end_date = exp.get("end_date")
            is_current = exp.get("is_current", False)
            
            if start_date:
                try:
                    if isinstance(start_date, dict):
                        start_year = start_date.get("year", 0)
                    else:
                        start_year = int(str(start_date)[:4])
                    
                    if is_current or not end_date:
                        end_year = 2025
                    else:
                        if isinstance(end_date, dict):
                            end_year = end_date.get("year", 2025)
                        else:
                            end_year = int(str(end_date)[:4])
                    
                    years = max(end_year - start_year, 0)
                    total_years += years
                except:
                    pass
        
        return total_years
    
    def _create_baseline(
        self,
        role_title: str,
        employees: List[PDLPerson],
        aggregated_data: Dict[str, Any]
    ) -> BaselineEmployeeProfile:
        """Create new baseline profile."""
        baseline = BaselineEmployeeProfile(
            customer_id=self.customer_id,
            role_title=role_title,
            employee_count=len(employees),
            employee_ids=[emp.id for emp in employees],
            aggregated_skills=aggregated_data.get("aggregated_skills"),
            common_companies=aggregated_data.get("common_companies"),
            education_patterns=aggregated_data.get("education_patterns"),
            career_paths=aggregated_data.get("career_paths"),
            avg_years_experience=aggregated_data.get("avg_years_experience"),
            baseline_embedding=aggregated_data.get("baseline_embedding"),
        )
        
        self.db.add(baseline)
        self.db.commit()
        self.db.refresh(baseline)
        
        return baseline
    
    def _update_baseline(
        self,
        baseline: BaselineEmployeeProfile,
        employees: List[PDLPerson],
        aggregated_data: Dict[str, Any]
    ):
        """Update existing baseline profile."""
        baseline.employee_count = len(employees)
        baseline.employee_ids = [emp.id for emp in employees]
        baseline.aggregated_skills = aggregated_data.get("aggregated_skills")
        baseline.common_companies = aggregated_data.get("common_companies")
        baseline.education_patterns = aggregated_data.get("education_patterns")
        baseline.career_paths = aggregated_data.get("career_paths")
        baseline.avg_years_experience = aggregated_data.get("avg_years_experience")
        baseline.baseline_embedding = aggregated_data.get("baseline_embedding")
        baseline.updated_at = datetime.now()
        
        self.db.commit()
        self.db.refresh(baseline)
    
    def refresh_all_baselines(self) -> Dict[str, int]:
        """
        Refresh all existing baselines for this customer.
        
        Useful for scheduled maintenance (monthly refresh).
        
        Returns:
            Summary of refreshed baselines
        """
        try:
            baselines = self.db.query(BaselineEmployeeProfile).filter(
                BaselineEmployeeProfile.customer_id == self.customer_id
            ).all()
            
            stats = {
                "total_baselines": len(baselines),
                "refreshed": 0,
                "failed": 0
            }
            
            for baseline in baselines:
                try:
                    self.build_baseline_for_role(baseline.role_title)
                    stats["refreshed"] += 1
                except Exception as e:
                    self.logger.error(
                        "Failed to refresh baseline",
                        role_title=baseline.role_title,
                        error=str(e)
                    )
                    stats["failed"] += 1
            
            self.logger.info("Baseline refresh complete", stats=stats)
            
            return stats
            
        except Exception as e:
            self.logger.error("Baseline refresh failed", error=str(e))
            raise

