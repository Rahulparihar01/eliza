"""
Talent Configuration API Routes

Endpoints for managing Career Blueprints and Company DNA profiles.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models import get_db
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext
from src.services.career_blueprint_service import CareerBlueprintService
from src.services.company_dna_service import CompanyDNAService

auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/talent-config", tags=["talent-config"])


# ============================================================================
# Pydantic Models - Career Blueprints
# ============================================================================

class CareerBlueprintCreate(BaseModel):
    """Request to create a new career blueprint."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    role_category: Optional[str] = None
    linkedin_urls: List[str] = Field(..., min_length=1)
    enriched_profiles: List[Dict[str, Any]] = Field(..., min_length=1)


class CareerBlueprintUpdate(BaseModel):
    """Request to update a career blueprint."""
    name: Optional[str] = None
    description: Optional[str] = None
    role_category: Optional[str] = None
    pdl_query_hints: Optional[Dict[str, Any]] = None
    scoring_weights: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class CareerBlueprintResponse(BaseModel):
    """Career blueprint response."""
    id: int
    customer_id: str
    name: str
    description: Optional[str]
    role_category: Optional[str]
    source_linkedin_urls: List[str]
    source_profile_count: int
    company_progression: Optional[Dict[str, Any]]
    role_progression: Optional[Dict[str, Any]]
    skill_profile: Optional[Dict[str, Any]]
    experience_profile: Optional[Dict[str, Any]]
    education_profile: Optional[Dict[str, Any]]
    pdl_query_hints: Optional[Dict[str, Any]]
    scoring_weights: Optional[Dict[str, Any]]
    is_active: bool
    usage_count: int
    last_used_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    
    class Config:
        from_attributes = True


class CareerBlueprintListResponse(BaseModel):
    """List of career blueprints."""
    blueprints: List[CareerBlueprintResponse]
    total: int


# ============================================================================
# Pydantic Models - Company DNA
# ============================================================================

class CompanyDNACreate(BaseModel):
    """Request to create/refresh a company DNA profile."""
    company_name: str = Field(..., min_length=1, max_length=255)
    role_category: str = Field(..., min_length=1, max_length=100)
    time_window_months: int = Field(default=24, ge=1, le=120)
    employee_fetch_limit: int = Field(default=50, ge=5, le=100, description="Max employees to fetch from PDL if not in local DB (5-100)")


class CompanyDNAUpdate(BaseModel):
    """Request to update company DNA preferences."""
    hiring_preferences: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class CompanyDNAResponse(BaseModel):
    """Company DNA profile response."""
    id: int
    customer_id: str
    company_name: str
    company_website: Optional[str]
    role_category: str
    time_window_months: int
    employee_count_analyzed: int
    workforce_dna: Optional[Dict[str, Any]]
    culture_indicators: Optional[Dict[str, Any]]
    success_patterns: Optional[Dict[str, Any]]
    hiring_preferences: Optional[Dict[str, Any]]
    pdl_query_modifiers: Optional[Dict[str, Any]]
    is_active: bool
    is_default: bool
    last_analyzed_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    
    class Config:
        from_attributes = True


class CompanyDNAListResponse(BaseModel):
    """List of company DNA profiles."""
    profiles: List[CompanyDNAResponse]
    total: int


# ============================================================================
# Career Blueprint Endpoints
# ============================================================================

@router.get("/blueprints", response_model=CareerBlueprintListResponse)
async def list_blueprints(
    role_category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List all career blueprints for the customer."""
    service = CareerBlueprintService(db, current_user.customer_id)
    blueprints = service.list_blueprints(
        role_category=role_category,
        active_only=active_only
    )
    
    return CareerBlueprintListResponse(
        blueprints=[CareerBlueprintResponse(**b.to_dict()) for b in blueprints],
        total=len(blueprints)
    )


@router.get("/blueprints/{blueprint_id}", response_model=CareerBlueprintResponse)
async def get_blueprint(
    blueprint_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get a specific career blueprint."""
    service = CareerBlueprintService(db, current_user.customer_id)
    blueprint = service.get_blueprint(blueprint_id)
    
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    
    return CareerBlueprintResponse(**blueprint.to_dict())


@router.post("/blueprints", response_model=CareerBlueprintResponse)
async def create_blueprint(
    request: CareerBlueprintCreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Create a new career blueprint from enriched LinkedIn profiles."""
    service = CareerBlueprintService(db, current_user.customer_id)
    
    blueprint = service.create_blueprint(
        name=request.name,
        linkedin_urls=request.linkedin_urls,
        enriched_profiles=request.enriched_profiles,
        description=request.description,
        role_category=request.role_category,
        user_id=current_user.user_id
    )
    
    return CareerBlueprintResponse(**blueprint.to_dict())


@router.patch("/blueprints/{blueprint_id}", response_model=CareerBlueprintResponse)
async def update_blueprint(
    blueprint_id: int,
    request: CareerBlueprintUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Update a career blueprint."""
    service = CareerBlueprintService(db, current_user.customer_id)
    
    updates = request.model_dump(exclude_unset=True)
    blueprint = service.update_blueprint(blueprint_id, updates)
    
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    
    return CareerBlueprintResponse(**blueprint.to_dict())


@router.delete("/blueprints/{blueprint_id}")
async def delete_blueprint(
    blueprint_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Delete (deactivate) a career blueprint."""
    service = CareerBlueprintService(db, current_user.customer_id)
    
    success = service.delete_blueprint(blueprint_id)
    if not success:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    
    return {"status": "deleted", "blueprint_id": blueprint_id}


# ============================================================================
# Company DNA Endpoints
# ============================================================================

@router.get("/company-dna", response_model=CompanyDNAListResponse)
async def list_company_dna(
    company_name: Optional[str] = Query(None),
    role_category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """List all company DNA profiles for the customer."""
    service = CompanyDNAService(db, current_user.customer_id)
    profiles = service.list_dna_profiles(
        company_name=company_name,
        role_category=role_category,
        active_only=active_only
    )
    
    return CompanyDNAListResponse(
        profiles=[CompanyDNAResponse(**p.to_dict()) for p in profiles],
        total=len(profiles)
    )


@router.get("/company-dna/{profile_id}", response_model=CompanyDNAResponse)
async def get_company_dna(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Get a specific company DNA profile."""
    service = CompanyDNAService(db, current_user.customer_id)
    profile = service.get_dna_profile(profile_id)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Company DNA profile not found")
    
    return CompanyDNAResponse(**profile.to_dict())


@router.post("/company-dna", response_model=CompanyDNAResponse)
async def create_or_refresh_company_dna(
    request: CompanyDNACreate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """
    Create or refresh a company DNA profile.
    
    This analyzes employees from the specified company within the time window
    and extracts workforce patterns, culture indicators, and success patterns.
    
    If employees are not found in the local database, it will query PDL to fetch
    up to `employee_fetch_limit` employees and store them for future use.
    """
    service = CompanyDNAService(db, current_user.customer_id)
    
    profile = service.create_or_update_dna(
        company_name=request.company_name,
        role_category=request.role_category,
        time_window_months=request.time_window_months,
        user_id=current_user.user_id,
        employee_fetch_limit=request.employee_fetch_limit
    )
    
    return CompanyDNAResponse(**profile.to_dict())


@router.patch("/company-dna/{profile_id}", response_model=CompanyDNAResponse)
async def update_company_dna(
    profile_id: int,
    request: CompanyDNAUpdate,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Update company DNA preferences."""
    service = CompanyDNAService(db, current_user.customer_id)
    
    if request.hiring_preferences is not None:
        profile = service.update_hiring_preferences(profile_id, request.hiring_preferences)
    else:
        profile = service.get_dna_profile(profile_id)
        if profile and request.is_active is not None:
            profile.is_active = request.is_active
            db.commit()
            db.refresh(profile)
        if profile and request.is_default is not None:
            profile.is_default = request.is_default
            db.commit()
            db.refresh(profile)
    
    if not profile:
        raise HTTPException(status_code=404, detail="Company DNA profile not found")
    
    return CompanyDNAResponse(**profile.to_dict())


@router.delete("/company-dna/{profile_id}")
async def delete_company_dna(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(auth_middleware.get_current_user)
):
    """Delete (deactivate) a company DNA profile."""
    service = CompanyDNAService(db, current_user.customer_id)
    
    success = service.delete_dna_profile(profile_id)
    if not success:
        raise HTTPException(status_code=404, detail="Company DNA profile not found")
    
    return {"status": "deleted", "profile_id": profile_id}


# ============================================================================
# Role Categories Reference
# ============================================================================

@router.get("/role-categories")
async def get_role_categories():
    """Get available role categories for DNA and blueprints."""
    return {
        "categories": [
            {"id": "engineering", "name": "Engineering", "description": "Software engineers, architects, DevOps, SRE"},
            {"id": "sales", "name": "Sales", "description": "Sales, account management, business development"},
            {"id": "marketing", "name": "Marketing", "description": "Marketing, growth, content, brand"},
            {"id": "product", "name": "Product", "description": "Product managers, program managers"},
            {"id": "design", "name": "Design", "description": "UX/UI designers, creative"},
            {"id": "operations", "name": "Operations", "description": "Operations, HR, finance, legal"},
            {"id": "all", "name": "All Roles", "description": "All roles across the organization"}
        ]
    }

