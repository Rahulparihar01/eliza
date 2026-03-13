"""
LinkedIn Profile Enrichment API

Enriches LinkedIn profile URLs using People Data Labs API.
Extracts the LinkedIn username from the URL and queries PDL for profile details.

Includes caching to reduce API costs:
- Results are cached for a configurable TTL (default 30 days)
- Profiles are stored in PDLPerson table for future reference
"""

from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import requests
import re

from src.models.database import get_db
from src.middleware.authorization import get_current_user
from src.core.auth_context import CurrentUserContext
from src.core.config import get_settings
from src.core.logging import get_logger, LogCategory
from src.models.connector import ConnectorConfiguration, PDLPerson
from src.services.email_generation_service import PDLCacheService

logger = get_logger(__name__, LogCategory.API)
router = APIRouter(prefix="/api/v1/linkedin", tags=["LinkedIn Enrichment"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class LinkedInEnrichmentRequest(BaseModel):
    """Request to enrich a LinkedIn profile URL"""
    linkedin_url: str = Field(description="LinkedIn profile URL (e.g., https://www.linkedin.com/in/username)")


class LinkedInProfileResponse(BaseModel):
    """Enriched LinkedIn profile data from PDL"""
    found: bool = Field(description="Whether the profile was found in PDL")
    linkedin_url: str = Field(description="Original LinkedIn URL")
    linkedin_username: Optional[str] = Field(None, description="Extracted LinkedIn username")
    
    # Profile data (if found)
    pdl_id: Optional[str] = Field(None, description="PDL person ID (external)")
    pdl_person_id: Optional[int] = Field(None, description="Database ID in pdl_persons table")
    full_name: Optional[str] = Field(None, description="Full name")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    
    # Job info
    job_title: Optional[str] = Field(None, description="Current job title")
    job_title_role: Optional[str] = Field(None, description="Job title role category")
    job_company_name: Optional[str] = Field(None, description="Current company")
    job_company_size: Optional[str] = Field(None, description="Company size range")
    job_company_industry: Optional[str] = Field(None, description="Company industry")
    
    # Location
    location_name: Optional[str] = Field(None, description="Location")
    location_country: Optional[str] = Field(None, description="Country")
    
    # Skills & Experience
    skills: Optional[List[str]] = Field(None, description="Skills list")
    inferred_years_experience: Optional[int] = Field(None, description="Years of experience")
    
    # Education
    education: Optional[List[dict]] = Field(None, description="Education history")
    
    # Work history
    experience: Optional[List[dict]] = Field(None, description="Work experience history")
    
    # Metadata
    likelihood: Optional[int] = Field(None, description="PDL confidence score (1-10)")
    error_message: Optional[str] = Field(None, description="Error message if lookup failed")
    cached: bool = Field(default=False, description="Whether this result came from cache")


class LinkedInBatchEnrichmentRequest(BaseModel):
    """Request to enrich multiple LinkedIn profiles"""
    linkedin_urls: List[str] = Field(description="List of LinkedIn profile URLs")


class LinkedInBatchEnrichmentResponse(BaseModel):
    """Response with multiple enriched profiles"""
    profiles: List[LinkedInProfileResponse]
    total_requested: int
    total_found: int
    total_not_found: int


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_linkedin_username(url: str) -> Optional[str]:
    """
    Extract LinkedIn username from a profile URL.
    
    Handles various URL formats:
    - https://www.linkedin.com/in/username
    - https://linkedin.com/in/username/
    - http://www.linkedin.com/in/username
    - linkedin.com/in/username
    
    Returns:
        LinkedIn username or None if extraction fails
    """
    # Normalize URL
    url = url.strip().lower()
    
    # Pattern to match LinkedIn profile URLs
    patterns = [
        r'linkedin\.com/in/([a-zA-Z0-9_-]+)/?',
        r'linkedin\.com/pub/([a-zA-Z0-9_-]+)/?',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def get_pdl_api_key(db: Session, customer_id: str) -> Optional[str]:
    """
    Get PDL API key from connector configuration.
    
    Looks for an active PDL connector configuration, first for the customer,
    then falls back to any active PDL connector (shared API key scenario).
    """
    import json
    from src.utils.encryption import decrypt_value
    
    # First try to find a customer-specific PDL connector
    config = db.query(ConnectorConfiguration).filter(
        ConnectorConfiguration.customer_id == customer_id,
        ConnectorConfiguration.connector_type == "people_data_labs",
        ConnectorConfiguration.is_enabled == True
    ).first()
    
    if config and config.credentials_encrypted:
        try:
            # Credentials are stored as encrypted JSON string
            credentials_json = decrypt_value(config.credentials_encrypted)
            credentials = json.loads(credentials_json)
            if isinstance(credentials, dict) and credentials.get("api_key"):
                logger.info(f"Using PDL API key from customer connector: {customer_id}")
                return credentials.get("api_key")
        except Exception as e:
            logger.error(f"Failed to decrypt PDL credentials for {customer_id}: {e}")
    
    # Fall back to any active PDL connector (shared API key scenario)
    config = db.query(ConnectorConfiguration).filter(
        ConnectorConfiguration.connector_type == "people_data_labs",
        ConnectorConfiguration.is_enabled == True
    ).first()
    
    if config and config.credentials_encrypted:
        try:
            # Credentials are stored as encrypted JSON string
            credentials_json = decrypt_value(config.credentials_encrypted)
            credentials = json.loads(credentials_json)
            if isinstance(credentials, dict) and credentials.get("api_key"):
                logger.info(f"Using PDL API key from shared connector: {config.customer_id}")
                return credentials.get("api_key")
        except Exception as e:
            logger.error(f"Failed to decrypt shared PDL credentials: {e}")
    
    # Fall back to settings
    settings = get_settings()
    return getattr(settings, 'pdl_api_key', None)


def enrich_linkedin_profile(linkedin_url: str, api_key: str) -> LinkedInProfileResponse:
    """
    Enrich a LinkedIn profile using PDL Person Search API.
    
    Uses the PDL Person Search API with linkedin_username filter to find
    the person's profile data.
    
    API Docs: https://docs.peopledatalabs.com/docs/person-search-api
    """
    username = extract_linkedin_username(linkedin_url)
    
    if not username:
        return LinkedInProfileResponse(
            found=False,
            linkedin_url=linkedin_url,
            error_message="Could not extract LinkedIn username from URL"
        )
    
    try:
        # Use PDL Person Search API with linkedin_username filter
        # This is more reliable than the Enrichment API for LinkedIn lookups
        response = requests.post(
            "https://api.peopledatalabs.com/v5/person/search",
            headers={
                "X-Api-Key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"linkedin_username": username.lower()}}
                        ]
                    }
                },
                "size": 1,
                "pretty": True
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            persons = data.get("data", [])
            
            if persons and len(persons) > 0:
                person = persons[0]
                
                logger.info(
                    "linkedin_enrichment_success",
                    linkedin_username=username,
                    pdl_id=person.get("id"),
                    full_name=person.get("full_name")
                )
                
                return LinkedInProfileResponse(
                    found=True,
                    linkedin_url=linkedin_url,
                    linkedin_username=username,
                    pdl_id=person.get("id"),
                    full_name=person.get("full_name"),
                    first_name=person.get("first_name"),
                    last_name=person.get("last_name"),
                    job_title=person.get("job_title"),
                    job_title_role=person.get("job_title_role"),
                    job_company_name=person.get("job_company_name"),
                    job_company_size=person.get("job_company_size"),
                    job_company_industry=person.get("job_company_industry"),
                    location_name=person.get("location_name"),
                    location_country=person.get("location_country"),
                    skills=person.get("skills", []),
                    inferred_years_experience=person.get("inferred_years_experience"),
                    education=person.get("education", []),
                    experience=person.get("experience", []),
                    likelihood=person.get("likelihood")
                )
            else:
                # No results found
                logger.info(
                    "linkedin_enrichment_not_found",
                    linkedin_username=username,
                    linkedin_url=linkedin_url
                )
                
                return LinkedInProfileResponse(
                    found=False,
                    linkedin_url=linkedin_url,
                    linkedin_username=username,
                    error_message="Profile not found in People Data Labs database"
                )
        
        elif response.status_code == 404:
            # No records found - PDL returns 404 when no matches
            logger.info(
                "linkedin_enrichment_not_found",
                linkedin_username=username,
                linkedin_url=linkedin_url
            )
            
            return LinkedInProfileResponse(
                found=False,
                linkedin_url=linkedin_url,
                linkedin_username=username,
                error_message="Profile not found in People Data Labs database"
            )
        
        elif response.status_code == 401:
            logger.error("PDL API key is invalid")
            return LinkedInProfileResponse(
                found=False,
                linkedin_url=linkedin_url,
                linkedin_username=username,
                error_message="API authentication failed"
            )
        
        elif response.status_code == 429:
            logger.warning("PDL rate limit exceeded")
            return LinkedInProfileResponse(
                found=False,
                linkedin_url=linkedin_url,
                linkedin_username=username,
                error_message="Rate limit exceeded. Please try again later."
            )
        
        else:
            logger.error(
                "linkedin_enrichment_api_error",
                status_code=response.status_code,
                response=response.text[:200]
            )
            return LinkedInProfileResponse(
                found=False,
                linkedin_url=linkedin_url,
                linkedin_username=username,
                error_message=f"API error: {response.status_code}"
            )
    
    except requests.exceptions.Timeout:
        logger.error("PDL API request timed out")
        return LinkedInProfileResponse(
            found=False,
            linkedin_url=linkedin_url,
            linkedin_username=username,
            error_message="Request timed out"
        )
    
    except Exception as e:
        logger.error(f"LinkedIn enrichment failed: {e}", exc_info=True)
        return LinkedInProfileResponse(
            found=False,
            linkedin_url=linkedin_url,
            linkedin_username=username,
            error_message=str(e)
        )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post(
    "/enrich",
    response_model=LinkedInProfileResponse,
    summary="Enrich LinkedIn Profile",
    description="Enrich a LinkedIn profile URL using People Data Labs API"
)
async def enrich_linkedin_profile_endpoint(
    request: LinkedInEnrichmentRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Enrich a LinkedIn profile URL with data from People Data Labs.
    
    Takes a LinkedIn profile URL, extracts the username, and queries PDL
    to get full profile details including:
    - Name and contact info
    - Current job title and company
    - Skills and experience
    - Education history
    - Work history
    
    This is useful for the look-alike employee selection feature where users
    can add any LinkedIn profile as a baseline for candidate matching.
    
    Results are cached for 30 days (configurable) to reduce API costs.
    """
    logger.info(
        "linkedin_enrichment_request",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        linkedin_url=request.linkedin_url
    )
    
    # Extract username for cache lookup
    username = extract_linkedin_username(request.linkedin_url)
    
    if not username:
        return LinkedInProfileResponse(
            found=False,
            linkedin_url=request.linkedin_url,
            error_message="Could not extract LinkedIn username from URL"
        )
    
    # Check cache first
    cache_service = PDLCacheService(db, current_user.customer_id)
    cache_query = {"linkedin_username": username.lower()}
    cached_pdl_ids = cache_service.get_cached_results(cache_query, "linkedin_enrichment")
    
    if cached_pdl_ids and len(cached_pdl_ids) > 0:
        # Try to get profile from database
        pdl_person = db.query(PDLPerson).filter(
            PDLPerson.pdl_id == cached_pdl_ids[0],
            PDLPerson.customer_id == current_user.customer_id
        ).first()
        
        if pdl_person:
            logger.info(
                "linkedin_enrichment_cache_hit",
                linkedin_username=username,
                pdl_id=pdl_person.pdl_id
            )
            
            return LinkedInProfileResponse(
                found=True,
                linkedin_url=request.linkedin_url,
                linkedin_username=username,
                pdl_id=pdl_person.pdl_id,
                pdl_person_id=pdl_person.id,  # Database ID for blueprint references
                full_name=pdl_person.full_name,
                first_name=pdl_person.first_name,
                last_name=pdl_person.last_name,
                job_title=pdl_person.job_title,
                job_title_role=pdl_person.job_title_role,
                job_company_name=pdl_person.job_company_name,
                job_company_size=pdl_person.job_company_size,
                job_company_industry=pdl_person.job_company_industry,
                location_name=pdl_person.location_name,
                location_country=pdl_person.location_country,
                skills=pdl_person.skills or [],
                inferred_years_experience=pdl_person.inferred_years_experience,
                education=pdl_person.education_history or [],
                experience=pdl_person.work_history or [],
                likelihood=pdl_person.pdl_likelihood,
                cached=True
            )
    
    # Get PDL API key
    api_key = get_pdl_api_key(db, current_user.customer_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDL API key not configured. Please configure a People Data Labs connector."
        )
    
    # Enrich the profile from PDL
    result = enrich_linkedin_profile(request.linkedin_url, api_key)
    
    # Store in database and cache if found
    pdl_person_id = None
    if result.found and result.pdl_id:
        # Store/update PDLPerson record
        existing_person = db.query(PDLPerson).filter(
            PDLPerson.pdl_id == result.pdl_id,
            PDLPerson.customer_id == current_user.customer_id
        ).first()
        
        if existing_person:
            # Update existing record
            existing_person.full_name = result.full_name
            existing_person.first_name = result.first_name
            existing_person.last_name = result.last_name
            existing_person.job_title = result.job_title
            existing_person.job_title_role = result.job_title_role
            existing_person.job_company_name = result.job_company_name
            existing_person.job_company_size = result.job_company_size
            existing_person.job_company_industry = result.job_company_industry
            existing_person.location_name = result.location_name
            existing_person.location_country = result.location_country
            existing_person.skills = result.skills
            existing_person.inferred_years_experience = result.inferred_years_experience
            existing_person.education_history = result.education
            existing_person.work_history = result.experience
            existing_person.pdl_likelihood = result.likelihood
            existing_person.linkedin_url = request.linkedin_url
            existing_person.linkedin_username = result.linkedin_username
            existing_person.sync_count += 1
            pdl_person_id = existing_person.id
            logger.info(
                "pdl_person_updated",
                pdl_id=result.pdl_id,
                pdl_person_id=pdl_person_id,
                full_name=result.full_name
            )
        else:
            # Create new record
            new_person = PDLPerson(
                pdl_id=result.pdl_id,
                customer_id=current_user.customer_id,
                full_name=result.full_name,
                first_name=result.first_name,
                last_name=result.last_name,
                job_title=result.job_title,
                job_title_role=result.job_title_role,
                job_company_name=result.job_company_name,
                job_company_size=result.job_company_size,
                job_company_industry=result.job_company_industry,
                location_name=result.location_name,
                location_country=result.location_country,
                skills=result.skills,
                inferred_years_experience=result.inferred_years_experience,
                education_history=result.education,
                work_history=result.experience,
                pdl_likelihood=result.likelihood,
                linkedin_url=request.linkedin_url,
                linkedin_username=result.linkedin_username,
                sync_count=1
            )
            db.add(new_person)
            db.flush()  # Get the ID before commit
            pdl_person_id = new_person.id
            logger.info(
                "pdl_person_created",
                pdl_id=result.pdl_id,
                pdl_person_id=pdl_person_id,
                full_name=result.full_name
            )
        
        db.commit()
        
        # Cache the result
        cache_service.cache_results(cache_query, "linkedin_enrichment", [result.pdl_id])
    
    # Return result with database ID included
    return LinkedInProfileResponse(
        found=result.found,
        linkedin_url=result.linkedin_url,
        linkedin_username=result.linkedin_username,
        pdl_id=result.pdl_id,
        pdl_person_id=pdl_person_id,  # Include database ID
        full_name=result.full_name,
        first_name=result.first_name,
        last_name=result.last_name,
        job_title=result.job_title,
        job_title_role=result.job_title_role,
        job_company_name=result.job_company_name,
        job_company_size=result.job_company_size,
        job_company_industry=result.job_company_industry,
        location_name=result.location_name,
        location_country=result.location_country,
        skills=result.skills,
        inferred_years_experience=result.inferred_years_experience,
        education=result.education,
        experience=result.experience,
        likelihood=result.likelihood,
        error_message=result.error_message,
        cached=False
    )


@router.post(
    "/enrich/batch",
    response_model=LinkedInBatchEnrichmentResponse,
    summary="Batch Enrich LinkedIn Profiles",
    description="Enrich multiple LinkedIn profile URLs at once"
)
async def batch_enrich_linkedin_profiles(
    request: LinkedInBatchEnrichmentRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Enrich multiple LinkedIn profiles in a single request.
    
    Limited to 10 profiles per request to manage API costs.
    """
    if len(request.linkedin_urls) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 LinkedIn URLs per batch request"
        )
    
    logger.info(
        "linkedin_batch_enrichment_request",
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        url_count=len(request.linkedin_urls)
    )
    
    # Get PDL API key
    api_key = get_pdl_api_key(db, current_user.customer_id)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PDL API key not configured. Please configure a People Data Labs connector."
        )
    
    # Enrich each profile
    profiles = []
    for url in request.linkedin_urls:
        result = enrich_linkedin_profile(url, api_key)
        profiles.append(result)
    
    found_count = sum(1 for p in profiles if p.found)
    
    return LinkedInBatchEnrichmentResponse(
        profiles=profiles,
        total_requested=len(request.linkedin_urls),
        total_found=found_count,
        total_not_found=len(request.linkedin_urls) - found_count
    )


@router.get(
    "/validate/{linkedin_url:path}",
    response_model=dict,
    summary="Validate LinkedIn URL",
    description="Validate a LinkedIn URL format and extract username"
)
async def validate_linkedin_url(
    linkedin_url: str,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """
    Validate a LinkedIn URL and extract the username.
    
    Does not make any API calls - just validates the URL format.
    """
    username = extract_linkedin_username(linkedin_url)
    
    return {
        "valid": username is not None,
        "linkedin_url": linkedin_url,
        "linkedin_username": username,
        "message": "Valid LinkedIn URL" if username else "Invalid LinkedIn URL format"
    }

