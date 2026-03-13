"""
Company DNA Service

Manages Company DNA Profiles - organizational hiring patterns scoped by
company + role category. Built from analyzing current employees.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import structlog

from src.models.talent_config import CompanyDNAProfile
from src.models.connector import PDLPerson

logger = structlog.get_logger(__name__)


class CompanyDNAService:
    """
    Service for managing Company DNA Profiles.
    
    DNA profiles capture organizational hiring patterns and are used to:
    1. Understand what backgrounds succeed at a company
    2. Adjust PDL queries based on organizational preferences
    3. Score candidates on organizational fit
    """
    
    def __init__(self, db: Session, customer_id: str):
        self.db = db
        self.customer_id = customer_id
        self.logger = logger.bind(service="company_dna", customer_id=customer_id)
    
    def list_dna_profiles(
        self,
        company_name: Optional[str] = None,
        role_category: Optional[str] = None,
        active_only: bool = True
    ) -> List[CompanyDNAProfile]:
        """List DNA profiles for the customer."""
        query = self.db.query(CompanyDNAProfile).filter(
            CompanyDNAProfile.customer_id == self.customer_id
        )
        
        if active_only:
            query = query.filter(CompanyDNAProfile.is_active == True)
        
        if company_name:
            query = query.filter(CompanyDNAProfile.company_name == company_name.lower())
        
        if role_category:
            query = query.filter(CompanyDNAProfile.role_category == role_category)
        
        return query.order_by(CompanyDNAProfile.company_name, CompanyDNAProfile.role_category).all()
    
    def get_dna_profile(self, profile_id: int) -> Optional[CompanyDNAProfile]:
        """Get a specific DNA profile by ID."""
        return self.db.query(CompanyDNAProfile).filter(
            and_(
                CompanyDNAProfile.id == profile_id,
                CompanyDNAProfile.customer_id == self.customer_id
            )
        ).first()
    
    def get_dna_for_company_role(
        self,
        company_name: str,
        role_category: str
    ) -> Optional[CompanyDNAProfile]:
        """Get DNA profile for a specific company + role combination."""
        return self.db.query(CompanyDNAProfile).filter(
            and_(
                CompanyDNAProfile.customer_id == self.customer_id,
                CompanyDNAProfile.company_name == company_name.lower(),
                CompanyDNAProfile.role_category == role_category,
                CompanyDNAProfile.is_active == True
            )
        ).first()
    
    def create_or_update_dna(
        self,
        company_name: str,
        role_category: str,
        time_window_months: int = 24,
        user_id: Optional[int] = None,
        employee_fetch_limit: int = 50
    ) -> CompanyDNAProfile:
        """
        Create or update a Company DNA profile by analyzing employees.
        
        Args:
            company_name: Company to analyze (e.g., "caylent")
            role_category: Role category (e.g., "engineering", "sales", "all")
            time_window_months: Only analyze employees from this window
            user_id: User creating/updating the profile
            employee_fetch_limit: Max employees to fetch from PDL if not in local DB (default: 50)
            
        Returns:
            Created or updated CompanyDNAProfile
        """
        self.logger.info(
            "creating_dna_profile",
            company=company_name,
            role_category=role_category,
            time_window=time_window_months,
            employee_fetch_limit=employee_fetch_limit
        )
        
        # Fetch employee data from PDL persons
        employees = self._fetch_employee_data(company_name, role_category, time_window_months, employee_fetch_limit)
        
        if not employees:
            self.logger.warning("no_employees_found", company=company_name)
        
        # Analyze workforce
        workforce_dna = self._analyze_workforce(employees)
        culture_indicators = self._analyze_culture(employees)
        success_patterns = self._extract_success_patterns(employees)
        pdl_modifiers = self._generate_pdl_modifiers(workforce_dna, success_patterns)
        
        # Check if profile exists
        existing = self.get_dna_for_company_role(company_name, role_category)
        
        if existing:
            # Update existing profile
            existing.time_window_months = time_window_months
            existing.employee_count_analyzed = len(employees)
            existing.workforce_dna = workforce_dna
            existing.culture_indicators = culture_indicators
            existing.success_patterns = success_patterns
            existing.pdl_query_modifiers = pdl_modifiers
            existing.last_analyzed_at = datetime.now(timezone.utc)
            existing.updated_at = datetime.now(timezone.utc)
            
            self.db.commit()
            self.db.refresh(existing)
            
            self.logger.info(
                "dna_profile_updated",
                profile_id=existing.id,
                employee_count=len(employees)
            )
            
            return existing
        else:
            # Create new profile
            profile = CompanyDNAProfile(
                customer_id=self.customer_id,
                company_name=company_name.lower(),
                role_category=role_category,
                time_window_months=time_window_months,
                employee_count_analyzed=len(employees),
                workforce_dna=workforce_dna,
                culture_indicators=culture_indicators,
                success_patterns=success_patterns,
                pdl_query_modifiers=pdl_modifiers,
                last_analyzed_at=datetime.now(timezone.utc),
                created_by_user_id=user_id
            )
            
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
            
            self.logger.info(
                "dna_profile_created",
                profile_id=profile.id,
                employee_count=len(employees)
            )
            
            return profile
    
    def update_hiring_preferences(
        self,
        profile_id: int,
        preferences: Dict[str, Any]
    ) -> Optional[CompanyDNAProfile]:
        """Update user-configurable hiring preferences."""
        profile = self.get_dna_profile(profile_id)
        if not profile:
            return None
        
        profile.hiring_preferences = preferences
        profile.updated_at = datetime.now(timezone.utc)
        
        # Regenerate PDL modifiers with new preferences
        profile.pdl_query_modifiers = self._generate_pdl_modifiers(
            profile.workforce_dna or {},
            profile.success_patterns or {},
            preferences
        )
        
        self.db.commit()
        self.db.refresh(profile)
        
        return profile
    
    def delete_dna_profile(self, profile_id: int) -> bool:
        """Soft delete a DNA profile."""
        profile = self.get_dna_profile(profile_id)
        if not profile:
            return False
        
        profile.is_active = False
        profile.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        
        return True
    
    def _fetch_employee_data(
        self,
        company_name: str,
        role_category: str,
        time_window_months: int,
        employee_fetch_limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Fetch employee data from PDL persons table.
        
        If no employees are found locally, queries PDL API to fetch and store them.
        
        Args:
            company_name: Company name to search for
            role_category: Department or role type to filter by
            time_window_months: Time window for local employee search
            employee_fetch_limit: Max employees to fetch from PDL (default: 50)
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_window_months * 30)
        
        # First, try to find employees in our local database
        employees = self._fetch_local_employees(company_name, role_category, cutoff_date)
        
        if employees:
            self.logger.info(
                "found_local_employees",
                company=company_name,
                role_category=role_category,
                count=len(employees)
            )
            return employees
        
        # No local employees found - query PDL and store results
        self.logger.info(
            "no_local_employees_querying_pdl",
            company=company_name,
            role_category=role_category,
            fetch_limit=employee_fetch_limit
        )
        
        employees = self._fetch_and_store_pdl_employees(company_name, role_category, time_window_months, employee_fetch_limit)
        
        return employees
    
    def _fetch_local_employees(
        self,
        company_name: str,
        role_category: str,
        cutoff_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch employees from local PDL persons table."""
        # Query PDL persons who work at the company
        query = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == self.customer_id,
            PDLPerson.created_at >= cutoff_date
        )
        
        # Filter by company name in job_company_name
        query = query.filter(
            PDLPerson.job_company_name.ilike(f"%{company_name}%")
        )
        
        # Filter by role category if specified (now supports free-text)
        if role_category and role_category.lower() not in ("all", ""):
            # Check if it's a predefined category or free text
            role_filters = self._get_role_category_filters(role_category)
            if role_filters:
                query = query.filter(
                    or_(*[PDLPerson.job_title.ilike(f"%{kw}%") for kw in role_filters])
                )
            else:
                # Free text - search directly
                query = query.filter(
                    or_(
                        PDLPerson.job_title.ilike(f"%{role_category}%"),
                        PDLPerson.job_company_industry.ilike(f"%{role_category}%")
                    )
                )
        
        persons = query.all()
        
        # Convert to dictionaries
        employees = []
        for person in persons:
            emp_data = {
                "id": person.id,
                "full_name": person.full_name,
                "job_title": person.job_title,
                "job_company_name": person.job_company_name,
                "job_company_size": person.job_company_size,
                "job_company_industry": person.job_company_industry,
                "job_title_levels": person.job_title_levels,
                "inferred_years_experience": person.inferred_years_experience,
                "skills": person.skills or [],
                "education_history": person.education_history or [],
                "work_history": person.work_history or [],
                "location": person.location_name,
                "created_at": person.created_at
            }
            employees.append(emp_data)
        
        return employees
    
    def _fetch_and_store_pdl_employees(
        self,
        company_name: str,
        role_category: str,
        time_window_months: int,
        employee_fetch_limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Query PDL API for employees using the configured connector and store in database.
        
        Args:
            company_name: Company name to search for
            role_category: Department or role type to filter by
            time_window_months: Not used for PDL query, kept for consistency
            employee_fetch_limit: Max employees to fetch from PDL (default: 50)
        
        Returns the employee data in the same format as _fetch_local_employees.
        """
        try:
            import json
            from src.models.connector import ConnectorConfiguration
            from src.services.ingestion.connectors.people_data_labs import PeopleDataLabsConnector
            from src.services.ingestion.transformers.pdl_transformer import PDLTransformer
            from src.utils.encryption import decrypt_value
            
            # Find the PDL connector configuration for this customer
            pdl_config = self.db.query(ConnectorConfiguration).filter(
                ConnectorConfiguration.customer_id == self.customer_id,
                ConnectorConfiguration.connector_type == 'people_data_labs',
                ConnectorConfiguration.is_enabled == True
            ).first()
            
            if not pdl_config:
                self.logger.warning(
                    "no_pdl_connector_configured",
                    customer_id=self.customer_id,
                    message="No PDL connector found for this customer. Please configure a People Data Labs connector."
                )
                return []
            
            # Decrypt credentials from the encrypted storage
            credentials = None
            if pdl_config.credentials_encrypted:
                try:
                    credentials_json = decrypt_value(pdl_config.credentials_encrypted)
                    credentials = json.loads(credentials_json)
                except Exception as e:
                    self.logger.error(
                        "failed_to_decrypt_pdl_credentials",
                        connector_id=pdl_config.id,
                        error=str(e)
                    )
                    return []
            
            if not credentials or not credentials.get('api_key'):
                self.logger.warning(
                    "pdl_connector_missing_api_key",
                    connector_id=pdl_config.id,
                    message="PDL connector is configured but missing API key"
                )
                return []
            
            # Build the search query for company employees
            search_query = {
                "job_company_name": [company_name]
            }
            
            # Add role/department filter if specified
            # Use job_title_role for broad categories (engineering, sales, etc.)
            # Use job_title for specific titles (Software Engineer, etc.)
            if role_category and role_category.lower() not in ("all", ""):
                role_lower = role_category.lower().strip()
                
                # Check if it's a broad category (use job_title_role)
                broad_categories = [
                    "engineering", "sales", "marketing", "product", "design",
                    "operations", "finance", "hr", "human resources", "legal",
                    "support", "customer success", "data", "research", "it",
                    "administration", "executive", "management"
                ]
                
                if any(cat in role_lower for cat in broad_categories):
                    # Use job_title_role for broad category matching
                    search_query["job_title_role"] = [role_category]
                else:
                    # Use job_title for specific title matching
                    search_query["job_title"] = [role_category]
            
            self.logger.info(
                "querying_pdl_for_employees",
                company=company_name,
                role_category=role_category,
                search_query=search_query,
                fetch_limit=employee_fetch_limit
            )
            
            # Initialize the PDL connector with the decrypted credentials and config
            connector = PeopleDataLabsConnector(
                credentials=credentials,
                config={
                    "search_query": search_query,
                    "max_records": min(employee_fetch_limit, 100),  # PDL max is 100 per request
                    "page_size": min(employee_fetch_limit, 100)
                },
                customer_id=self.customer_id
            )
            
            # Use the connector to fetch records
            pdl_records = []
            try:
                for batch in connector.read_stream("full", {"max_records": employee_fetch_limit}):
                    pdl_records.extend(batch)
                    if len(pdl_records) >= employee_fetch_limit:
                        break
            except Exception as e:
                self.logger.warning(
                    "pdl_stream_error",
                    error=str(e),
                    records_fetched=len(pdl_records)
                )
            
            if not pdl_records:
                self.logger.warning(
                    "no_pdl_results",
                    company=company_name,
                    role_category=role_category
                )
                return []
            
            self.logger.info(
                "pdl_results_received",
                company=company_name,
                count=len(pdl_records)
            )
            
            # Transform and store results
            transformer = PDLTransformer(self.db, self.customer_id)
            employees = []
            
            for person_data in pdl_records:
                try:
                    # Transform the raw PDL data and store in database
                    pdl_person = transformer.transform_and_store(person_data)
                    
                    if pdl_person:
                        emp_data = {
                            "id": pdl_person.id,
                            "full_name": pdl_person.full_name,
                            "job_title": pdl_person.job_title,
                            "job_company_name": pdl_person.job_company_name,
                            "job_company_size": pdl_person.job_company_size,
                            "job_company_industry": pdl_person.job_company_industry,
                            "job_title_levels": pdl_person.job_title_levels,
                            "inferred_years_experience": pdl_person.inferred_years_experience,
                            "skills": pdl_person.skills or [],
                            "education_history": pdl_person.education_history or [],
                            "work_history": pdl_person.work_history or [],
                            "location": pdl_person.location_name,
                            "created_at": pdl_person.created_at
                        }
                        employees.append(emp_data)
                except Exception as e:
                    self.logger.warning(
                        "failed_to_transform_pdl_person",
                        error=str(e)
                    )
                    continue
            
            self.logger.info(
                "pdl_employees_stored",
                company=company_name,
                count=len(employees)
            )
            
            return employees
            
        except Exception as e:
            self.logger.error(
                "pdl_employee_fetch_failed",
                company=company_name,
                error=str(e),
                exc_info=True
            )
            return []
    
    def _get_role_category_filters(self, role_category: str) -> List[str]:
        """Get job title keywords for a role category."""
        category_keywords = {
            "engineering": [
                "engineer", "developer", "architect", "devops", "sre",
                "platform", "infrastructure", "backend", "frontend", "fullstack",
                "data", "ml", "machine learning", "ai", "cloud"
            ],
            "sales": [
                "sales", "account", "business development", "revenue",
                "customer success", "solutions", "partnership"
            ],
            "marketing": [
                "marketing", "growth", "brand", "content", "product marketing",
                "demand gen", "communications"
            ],
            "product": [
                "product manager", "product owner", "product lead",
                "program manager", "project manager"
            ],
            "design": [
                "designer", "ux", "ui", "user experience", "visual",
                "design lead", "creative"
            ],
            "operations": [
                "operations", "ops", "people", "hr", "finance",
                "legal", "admin"
            ]
        }
        
        return category_keywords.get(role_category.lower(), [])
    
    def _analyze_workforce(self, employees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze workforce patterns."""
        if not employees:
            return {}
        
        # Experience analysis
        years_list = [e.get("inferred_years_experience", 0) for e in employees if e.get("inferred_years_experience")]
        avg_years = sum(years_list) / len(years_list) if years_list else 5
        
        # Experience distribution
        exp_dist = {"0-2": 0, "3-5": 0, "6-10": 0, "10+": 0}
        for years in years_list:
            if years <= 2:
                exp_dist["0-2"] += 1
            elif years <= 5:
                exp_dist["3-5"] += 1
            elif years <= 10:
                exp_dist["6-10"] += 1
            else:
                exp_dist["10+"] += 1
        
        total = len(years_list) or 1
        exp_dist = {k: round(v / total, 2) for k, v in exp_dist.items()}
        
        # Skill analysis
        all_skills = []
        for emp in employees:
            skills = emp.get("skills") or []
            for skill in skills:
                if isinstance(skill, str):
                    all_skills.append(skill.lower())
                elif isinstance(skill, dict):
                    all_skills.append(skill.get("name", "").lower())
        
        skill_counts = {}
        for skill in all_skills:
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        skill_freq = {k: round(v / len(employees), 2) for k, v in 
                      sorted(skill_counts.items(), key=lambda x: -x[1])[:30]}
        
        core_skills = [s for s, f in skill_freq.items() if f >= 0.3][:15]
        
        # Background analysis
        previous_companies = []
        for emp in employees:
            work_history = emp.get("work_history") or []
            for job in work_history[1:]:  # Skip current job
                if isinstance(job, dict):
                    company = job.get("company")
                    if isinstance(company, dict):
                        company_name = company.get("name")
                        if isinstance(company_name, str) and company_name:
                            previous_companies.append(company_name.lower())
        
        company_counts = {}
        for company in previous_companies:
            company_counts[company] = company_counts.get(company, 0) + 1
        
        # Detect FAANG/startup/consulting backgrounds
        faang = {"google", "facebook", "meta", "amazon", "apple", "microsoft", "netflix"}
        consulting = {"mckinsey", "bain", "bcg", "deloitte", "accenture", "kpmg", "ey", "pwc"}
        
        def get_company_name_safe(job):
            """Safely extract company name from job dict."""
            if not isinstance(job, dict):
                return ""
            company = job.get("company")
            if isinstance(company, dict):
                name = company.get("name")
                if isinstance(name, str):
                    return name.lower()
            return ""
        
        faang_count = sum(1 for e in employees for j in (e.get("work_history") or []) 
                         if any(f in get_company_name_safe(j) for f in faang))
        consulting_count = sum(1 for e in employees for j in (e.get("work_history") or []) 
                               if any(c in get_company_name_safe(j) for c in consulting))
        
        # Education analysis
        degrees = {"bachelors": 0, "masters": 0, "phd": 0}
        cs_degrees = 0
        
        for emp in employees:
            education = emp.get("education_history") or []
            for edu in education:
                if isinstance(edu, dict):
                    degree = (edu.get("degree") or "").lower()
                    major = (edu.get("major") or "").lower()
                    
                    if "bachelor" in degree or "bs" in degree or "ba" in degree:
                        degrees["bachelors"] += 1
                    if "master" in degree or "ms" in degree or "mba" in degree:
                        degrees["masters"] += 1
                    if "phd" in degree or "doctorate" in degree:
                        degrees["phd"] += 1
                    
                    if any(kw in major for kw in ["computer", "software", "cs", "engineering"]):
                        cs_degrees += 1
        
        total_emp = len(employees) or 1
        
        return {
            "avg_experience_years": round(avg_years, 1),
            "experience_distribution": exp_dist,
            "common_backgrounds": {
                "faang_alumni_rate": round(faang_count / total_emp, 2),
                "consulting_background_rate": round(consulting_count / total_emp, 2),
                "common_previous_companies": list(sorted(company_counts.items(), key=lambda x: -x[1])[:10])
            },
            "skill_profile": {
                "core_skills": core_skills,
                "skill_frequencies": skill_freq
            },
            "education_profile": {
                "bachelors_rate": round(degrees["bachelors"] / total_emp, 2),
                "masters_rate": round(degrees["masters"] / total_emp, 2),
                "phd_rate": round(degrees["phd"] / total_emp, 2),
                "cs_degree_rate": round(cs_degrees / total_emp, 2)
            }
        }
    
    def _analyze_culture(self, employees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze culture indicators from workforce patterns."""
        if not employees:
            return {}
        
        # Infer pace from experience levels
        years_list = [e.get("inferred_years_experience", 0) for e in employees if e.get("inferred_years_experience")]
        avg_years = sum(years_list) / len(years_list) if years_list else 5
        
        # Infer technical depth from skill diversity
        all_skills = set()
        for emp in employees:
            skills = emp.get("skills") or []
            for skill in skills:
                if isinstance(skill, str):
                    all_skills.add(skill.lower())
        
        # Infer remote-friendliness from location diversity
        locations = [e.get("location", "") for e in employees if e.get("location")]
        unique_locations = len(set(locations))
        
        return {
            "pace": "fast" if avg_years < 6 else "moderate" if avg_years < 10 else "established",
            "technical_depth": "high" if len(all_skills) > 50 else "moderate" if len(all_skills) > 20 else "focused",
            "remote_friendly": unique_locations > len(employees) * 0.5,
            "avg_experience_years": round(avg_years, 1),
            "skill_diversity": len(all_skills),
            "location_diversity": unique_locations
        }
    
    def _extract_success_patterns(self, employees: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract patterns that indicate success at the company."""
        if not employees:
            return {}
        
        # Most common previous companies
        previous_companies = []
        previous_roles = []
        
        for emp in employees:
            work_history = emp.get("work_history") or []
            for job in work_history[1:3]:  # Last 2 jobs before current
                if isinstance(job, dict):
                    # Safely extract company name
                    company = job.get("company")
                    if isinstance(company, dict):
                        company_name = company.get("name")
                        if isinstance(company_name, str) and company_name:
                            previous_companies.append(company_name.lower())
                    # Safely extract title
                    title = job.get("title")
                    if isinstance(title, str) and title:
                        previous_roles.append(title.lower())
        
        company_counts = {}
        for company in previous_companies:
            company_counts[company] = company_counts.get(company, 0) + 1
        
        role_counts = {}
        for role in previous_roles:
            role_counts[role] = role_counts.get(role, 0) + 1
        
        return {
            "common_previous_companies": [c for c, _ in sorted(company_counts.items(), key=lambda x: -x[1])[:15]],
            "common_previous_roles": [r for r, _ in sorted(role_counts.items(), key=lambda x: -x[1])[:10]],
            "employee_count": len(employees)
        }
    
    def _generate_pdl_modifiers(
        self,
        workforce_dna: Dict[str, Any],
        success_patterns: Dict[str, Any],
        hiring_preferences: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate PDL query modifiers from DNA analysis."""
        modifiers = {}
        
        # Boost companies from success patterns
        if success_patterns.get("common_previous_companies"):
            modifiers["boost_companies"] = success_patterns["common_previous_companies"][:10]
        
        # Boost skills from workforce DNA
        if workforce_dna.get("skill_profile", {}).get("core_skills"):
            modifiers["boost_skills"] = workforce_dna["skill_profile"]["core_skills"][:10]
        
        # Experience adjustment based on workforce avg
        avg_exp = workforce_dna.get("avg_experience_years", 5)
        modifiers["target_experience"] = [max(1, int(avg_exp) - 3), int(avg_exp) + 3]
        
        # Apply user preferences if provided
        if hiring_preferences:
            if hiring_preferences.get("preferred_source_companies"):
                modifiers["boost_companies"] = hiring_preferences["preferred_source_companies"]
            if hiring_preferences.get("preferred_skills"):
                modifiers["boost_skills"] = hiring_preferences["preferred_skills"]
            if hiring_preferences.get("must_have_criteria"):
                modifiers["required_criteria"] = hiring_preferences["must_have_criteria"]
        
        return modifiers

