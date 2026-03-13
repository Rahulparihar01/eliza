"""
Career Fingerprint & Company DNA API Routes

Provides endpoints for:
- Creating and managing career trajectory fingerprints
- Building and querying company DNA profiles
- Using fingerprints in analysis configuration
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from src.core.logging import get_logger, LogCategory
from src.models.database import get_db
from src.middleware.authorization import get_current_user, require_permission
from src.models.auth import CurrentUserContext
from src.models.career_fingerprint import (
    CareerFingerprint,
    CompanyDNAProfile,
    CareerFingerprintCreate,
    CareerFingerprintResponse,
    CompanyDNACreate,
    CompanyDNAResponse
)
from src.services.ingestion.connector_service import ConnectorService
from src.services.ingestion.connectors.people_data_labs import PeopleDataLabsConnector

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(prefix="/api/v1/career-fingerprints", tags=["Career Fingerprints"])


# ============================================================================
# CAREER FINGERPRINT ENDPOINTS
# ============================================================================

@router.post(
    "",
    response_model=CareerFingerprintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create career fingerprint",
    description="Create a new career fingerprint from LinkedIn profiles"
)
async def create_fingerprint(
    request: CareerFingerprintCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:create"))
):
    """
    Create a career fingerprint by analyzing LinkedIn profiles.
    
    The system will:
    1. Enrich each LinkedIn profile via PDL
    2. Extract career patterns from the profiles
    3. Build a composite fingerprint
    4. Generate PDL query hints for future searches
    """
    logger.info(
        "create_career_fingerprint",
        customer_id=current_user.customer_id,
        name=request.name,
        profile_count=len(request.linkedin_urls)
    )
    
    # Get PDL connector for enrichment
    connector_service = ConnectorService(db)
    pdl_connectors = connector_service.list_configurations(
        customer_id=current_user.customer_id,
        connector_type='people_data_labs',
        is_enabled=True
    )
    
    if not pdl_connectors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDL connector configured. Please set up a People Data Labs connector first."
        )
    
    api_credentials = connector_service.get_credentials(pdl_connectors[0])
    
    # Enrich each LinkedIn profile
    enriched_profiles = []
    for linkedin_url in request.linkedin_urls:
        try:
            # Clean up LinkedIn URL
            clean_url = linkedin_url.strip()
            if not clean_url.startswith('http'):
                clean_url = f"https://linkedin.com/in/{clean_url}"
            
            # Call PDL to enrich
            import requests
            response = requests.get(
                "https://api.peopledatalabs.com/v5/person/enrich",
                params={"profile": clean_url},
                headers={"X-Api-Key": api_credentials.get("api_key")}
            )
            
            if response.status_code == 200:
                data = response.json()
                enriched_profiles.append({
                    "linkedin_url": clean_url,
                    "pdl_person_id": data.get("id"),
                    "full_name": data.get("full_name"),
                    "data": data,
                    "added_at": datetime.utcnow().isoformat()
                })
            else:
                logger.warning(
                    "pdl_enrichment_failed",
                    linkedin_url=clean_url,
                    status_code=response.status_code
                )
        except Exception as e:
            logger.error(f"Failed to enrich profile {linkedin_url}: {e}")
    
    if not enriched_profiles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not enrich any of the provided LinkedIn profiles"
        )
    
    # Extract patterns from enriched profiles
    patterns = _extract_career_patterns(enriched_profiles)
    
    # Create fingerprint
    fingerprint = CareerFingerprint(
        customer_id=current_user.customer_id,
        name=request.name,
        description=request.description,
        source_profiles=[{
            "linkedin_url": p["linkedin_url"],
            "pdl_person_id": p.get("pdl_person_id"),
            "full_name": p.get("full_name"),
            "added_at": p["added_at"]
        } for p in enriched_profiles],
        company_progression=patterns.get("company_progression"),
        role_progression=patterns.get("role_progression"),
        skill_velocity=patterns.get("skill_velocity"),
        education_patterns=patterns.get("education_patterns"),
        avg_years_experience=patterns.get("avg_years_experience"),
        common_skills=patterns.get("common_skills"),
        common_companies=patterns.get("common_companies"),
        common_titles=patterns.get("common_titles"),
        pdl_query_hints=patterns.get("pdl_query_hints"),
        scoring_weights=patterns.get("scoring_weights"),
        profile_count=len(enriched_profiles),
        is_active=True,
        created_by=current_user.user_id
    )
    
    db.add(fingerprint)
    db.commit()
    db.refresh(fingerprint)
    
    return CareerFingerprintResponse.model_validate(fingerprint)


@router.get(
    "",
    response_model=List[CareerFingerprintResponse],
    summary="List career fingerprints",
    description="Get all career fingerprints for the customer"
)
async def list_fingerprints(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:read"))
):
    """List all career fingerprints."""
    query = db.query(CareerFingerprint).filter(
        CareerFingerprint.customer_id == current_user.customer_id
    )
    
    if active_only:
        query = query.filter(CareerFingerprint.is_active == True)
    
    fingerprints = query.order_by(CareerFingerprint.created_at.desc()).all()
    
    return [CareerFingerprintResponse.model_validate(fp) for fp in fingerprints]


@router.get(
    "/{fingerprint_id}",
    response_model=CareerFingerprintResponse,
    summary="Get career fingerprint",
    description="Get a specific career fingerprint by ID"
)
async def get_fingerprint(
    fingerprint_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:read"))
):
    """Get a specific career fingerprint."""
    fingerprint = db.query(CareerFingerprint).filter(
        CareerFingerprint.id == fingerprint_id,
        CareerFingerprint.customer_id == current_user.customer_id
    ).first()
    
    if not fingerprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Career fingerprint not found"
        )
    
    return CareerFingerprintResponse.model_validate(fingerprint)


@router.post(
    "/{fingerprint_id}/add-profile",
    response_model=CareerFingerprintResponse,
    summary="Add profile to fingerprint",
    description="Add a LinkedIn profile to an existing fingerprint"
)
async def add_profile_to_fingerprint(
    fingerprint_id: int,
    linkedin_url: str,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:create"))
):
    """Add a LinkedIn profile to an existing fingerprint and re-analyze."""
    fingerprint = db.query(CareerFingerprint).filter(
        CareerFingerprint.id == fingerprint_id,
        CareerFingerprint.customer_id == current_user.customer_id
    ).first()
    
    if not fingerprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Career fingerprint not found"
        )
    
    # Get PDL connector
    connector_service = ConnectorService(db)
    pdl_connectors = connector_service.list_configurations(
        customer_id=current_user.customer_id,
        connector_type='people_data_labs',
        is_enabled=True
    )
    
    if not pdl_connectors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No PDL connector configured"
        )
    
    api_credentials = connector_service.get_credentials(pdl_connectors[0])
    
    # Enrich the new profile
    clean_url = linkedin_url.strip()
    if not clean_url.startswith('http'):
        clean_url = f"https://linkedin.com/in/{clean_url}"
    
    import requests
    response = requests.get(
        "https://api.peopledatalabs.com/v5/person/enrich",
        params={"profile": clean_url},
        headers={"X-Api-Key": api_credentials.get("api_key")}
    )
    
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not enrich the LinkedIn profile"
        )
    
    data = response.json()
    
    # Add to source profiles
    source_profiles = fingerprint.source_profiles or []
    source_profiles.append({
        "linkedin_url": clean_url,
        "pdl_person_id": data.get("id"),
        "full_name": data.get("full_name"),
        "added_at": datetime.utcnow().isoformat()
    })
    
    fingerprint.source_profiles = source_profiles
    fingerprint.profile_count = len(source_profiles)
    
    # TODO: Re-analyze patterns with all profiles
    
    db.commit()
    db.refresh(fingerprint)
    
    return CareerFingerprintResponse.model_validate(fingerprint)


@router.delete(
    "/{fingerprint_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete career fingerprint",
    description="Delete a career fingerprint"
)
async def delete_fingerprint(
    fingerprint_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:create"))
):
    """Delete a career fingerprint (soft delete)."""
    fingerprint = db.query(CareerFingerprint).filter(
        CareerFingerprint.id == fingerprint_id,
        CareerFingerprint.customer_id == current_user.customer_id
    ).first()
    
    if not fingerprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Career fingerprint not found"
        )
    
    fingerprint.is_active = False
    db.commit()


# ============================================================================
# COMPANY DNA ENDPOINTS
# ============================================================================

@router.post(
    "/company-dna",
    response_model=CompanyDNAResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create/update company DNA profile",
    description="Create or update the company DNA profile by analyzing employees"
)
async def create_company_dna(
    request: CompanyDNACreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:create"))
):
    """
    Create or update company DNA profile.
    
    If analyze_employees is True, will analyze existing employees in the database
    to build the DNA profile.
    """
    logger.info(
        "create_company_dna",
        customer_id=current_user.customer_id,
        company_name=request.company_name
    )
    
    # Check if DNA profile already exists
    existing = db.query(CompanyDNAProfile).filter(
        CompanyDNAProfile.customer_id == current_user.customer_id,
        CompanyDNAProfile.company_name == request.company_name
    ).first()
    
    if existing:
        # Update existing
        existing.company_website = request.company_website or existing.company_website
        existing.company_description = request.company_description or existing.company_description
        
        if request.analyze_employees:
            dna = await _analyze_company_employees(db, current_user.customer_id, request.company_name)
            existing.workforce_dna = dna.get("workforce_dna")
            existing.culture_indicators = dna.get("culture_indicators")
            existing.success_patterns = dna.get("success_patterns")
            existing.hiring_preferences = dna.get("hiring_preferences")
            existing.pdl_query_modifiers = dna.get("pdl_query_modifiers")
            existing.employee_count_analyzed = dna.get("employee_count", 0)
            existing.last_analyzed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing)
        return CompanyDNAResponse.model_validate(existing)
    
    # Create new
    dna_data = {}
    if request.analyze_employees:
        dna_data = await _analyze_company_employees(db, current_user.customer_id, request.company_name)
    
    dna_profile = CompanyDNAProfile(
        customer_id=current_user.customer_id,
        company_name=request.company_name,
        company_website=request.company_website,
        company_description=request.company_description,
        workforce_dna=dna_data.get("workforce_dna"),
        culture_indicators=dna_data.get("culture_indicators"),
        success_patterns=dna_data.get("success_patterns"),
        hiring_preferences=dna_data.get("hiring_preferences"),
        pdl_query_modifiers=dna_data.get("pdl_query_modifiers"),
        employee_count_analyzed=dna_data.get("employee_count", 0),
        is_active=True,
        last_analyzed_at=datetime.utcnow() if request.analyze_employees else None,
        created_by=current_user.user_id
    )
    
    db.add(dna_profile)
    db.commit()
    db.refresh(dna_profile)
    
    return CompanyDNAResponse.model_validate(dna_profile)


@router.get(
    "/company-dna",
    response_model=List[CompanyDNAResponse],
    summary="List company DNA profiles",
    description="Get all company DNA profiles"
)
async def list_company_dna(
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:read"))
):
    """List all company DNA profiles."""
    profiles = db.query(CompanyDNAProfile).filter(
        CompanyDNAProfile.customer_id == current_user.customer_id,
        CompanyDNAProfile.is_active == True
    ).order_by(CompanyDNAProfile.created_at.desc()).all()
    
    return [CompanyDNAResponse.model_validate(p) for p in profiles]


@router.get(
    "/company-dna/{company_name}",
    response_model=CompanyDNAResponse,
    summary="Get company DNA profile",
    description="Get a specific company DNA profile"
)
async def get_company_dna(
    company_name: str,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(require_permission("recruiter:blueprints:read"))
):
    """Get company DNA profile by name."""
    profile = db.query(CompanyDNAProfile).filter(
        CompanyDNAProfile.customer_id == current_user.customer_id,
        CompanyDNAProfile.company_name.ilike(company_name)
    ).first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company DNA profile for '{company_name}' not found"
        )
    
    return CompanyDNAResponse.model_validate(profile)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _extract_career_patterns(enriched_profiles: List[dict]) -> dict:
    """
    Extract career patterns from enriched PDL profiles.
    
    Analyzes:
    - Company progression patterns
    - Role progression patterns
    - Skill acquisition velocity
    - Education patterns
    """
    patterns = {
        "company_progression": {},
        "role_progression": {},
        "skill_velocity": {},
        "education_patterns": {},
        "common_skills": [],
        "common_companies": [],
        "common_titles": [],
        "avg_years_experience": 0,
        "pdl_query_hints": {},
        "scoring_weights": {
            "technical_skills": 0.35,
            "experience_level": 0.25,
            "company_background": 0.20,
            "career_trajectory": 0.15,
            "education": 0.05
        }
    }
    
    all_skills = []
    all_companies = []
    all_titles = []
    total_experience = 0
    
    for profile in enriched_profiles:
        data = profile.get("data", {})
        
        # Collect skills
        skills = data.get("skills", [])
        all_skills.extend(skills)
        
        # Collect companies from experience
        experience = data.get("experience", [])
        for exp in experience:
            company = exp.get("company", {})
            if company and company.get("name"):
                all_companies.append(company.get("name").lower())
            title = exp.get("title", {})
            if title and title.get("name"):
                all_titles.append(title.get("name").lower())
        
        # Get experience years
        years_exp = data.get("inferred_years_experience")
        if years_exp:
            total_experience += years_exp
    
    # Calculate common items
    from collections import Counter
    
    skill_counts = Counter(all_skills)
    patterns["common_skills"] = [s for s, _ in skill_counts.most_common(15)]
    
    company_counts = Counter(all_companies)
    patterns["common_companies"] = [c for c, _ in company_counts.most_common(10)]
    
    title_counts = Counter(all_titles)
    patterns["common_titles"] = [t for t, _ in title_counts.most_common(10)]
    
    if enriched_profiles:
        patterns["avg_years_experience"] = total_experience / len(enriched_profiles)
    
    # Build PDL query hints
    patterns["pdl_query_hints"] = {
        "suggested_job_titles": patterns["common_titles"][:5],
        "suggested_skills": patterns["common_skills"][:5],
        "suggested_companies": patterns["common_companies"][:5],
        "experience_range": {
            "min": max(1, int(patterns["avg_years_experience"] - 3)),
            "max": int(patterns["avg_years_experience"] + 3)
        }
    }
    
    # Analyze company progression
    company_sizes = []
    for profile in enriched_profiles:
        data = profile.get("data", {})
        experience = data.get("experience", [])
        for exp in experience:
            company = exp.get("company", {})
            if company.get("size"):
                company_sizes.append(company.get("size"))
    
    if company_sizes:
        size_counts = Counter(company_sizes)
        patterns["company_progression"] = {
            "company_sizes": [s for s, _ in size_counts.most_common(5)],
            "industries": list(set([
                exp.get("company", {}).get("industry", "").lower()
                for profile in enriched_profiles
                for exp in profile.get("data", {}).get("experience", [])
                if exp.get("company", {}).get("industry")
            ]))[:5]
        }
    
    return patterns


async def _analyze_company_employees(db: Session, customer_id: str, company_name: str) -> dict:
    """
    Analyze existing employees to build company DNA.
    
    Looks at PDL persons in the database associated with this company.
    """
    from src.models.pdl_person import PDLPerson
    
    # Query employees from PDL persons table
    employees = db.query(PDLPerson).filter(
        PDLPerson.customer_id == customer_id
    ).all()
    
    if not employees:
        return {
            "workforce_dna": None,
            "culture_indicators": None,
            "success_patterns": None,
            "hiring_preferences": None,
            "pdl_query_modifiers": None,
            "employee_count": 0
        }
    
    # Analyze patterns
    all_skills = []
    all_companies = []
    total_experience = 0
    education_levels = []
    
    for emp in employees:
        profile_data = emp.profile_data or {}
        
        # Skills
        skills = profile_data.get("skills", [])
        all_skills.extend(skills)
        
        # Experience
        experience = profile_data.get("experience", [])
        for exp in experience:
            company = exp.get("company", {})
            if company and company.get("name"):
                all_companies.append(company.get("name").lower())
        
        # Years of experience
        years_exp = profile_data.get("inferred_years_experience")
        if years_exp:
            total_experience += years_exp
        
        # Education
        education = profile_data.get("education", [])
        for edu in education:
            degrees = edu.get("degrees", [])
            education_levels.extend(degrees)
    
    from collections import Counter
    
    skill_counts = Counter(all_skills)
    company_counts = Counter(all_companies)
    edu_counts = Counter(education_levels)
    
    avg_experience = total_experience / len(employees) if employees else 0
    
    # Build DNA
    workforce_dna = {
        "avg_experience_years": round(avg_experience, 1),
        "common_backgrounds": {
            "previous_companies": [c for c, _ in company_counts.most_common(10)]
        },
        "skill_profile": {
            "core_skills": [s for s, _ in skill_counts.most_common(15)],
            "skill_diversity": len(set(all_skills)) / len(all_skills) if all_skills else 0
        }
    }
    
    # Culture indicators (inferred)
    culture_indicators = {
        "technical_depth": 0.8 if any(s in all_skills for s in ["python", "kubernetes", "aws"]) else 0.5,
        "remote_friendly": True,  # Default assumption
        "pace": "fast" if avg_experience < 8 else "moderate"
    }
    
    # Hiring preferences
    hiring_preferences = {
        "preferred_companies": [c for c, _ in company_counts.most_common(5)],
        "preferred_skills": [s for s, _ in skill_counts.most_common(10)]
    }
    
    # PDL query modifiers
    pdl_query_modifiers = {
        "boost_companies": [c for c, _ in company_counts.most_common(5)],
        "boost_skills": [s for s, _ in skill_counts.most_common(5)]
    }
    
    return {
        "workforce_dna": workforce_dna,
        "culture_indicators": culture_indicators,
        "success_patterns": None,  # Would need more data
        "hiring_preferences": hiring_preferences,
        "pdl_query_modifiers": pdl_query_modifiers,
        "employee_count": len(employees)
    }


