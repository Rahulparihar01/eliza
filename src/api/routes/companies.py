"""
Companies API Routes

API endpoints for listing available companies for HR data access.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import distinct
from pydantic import BaseModel

from src.models import get_db
from src.models.hr import Employee
from src.middleware.authorization import auth_middleware
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.API)

router = APIRouter(prefix="/v1/companies", tags=["Companies"])


# Schemas
class CompanyResponse(BaseModel):
    company_id: str
    employee_count: int
    can_access: bool


class CompaniesListResponse(BaseModel):
    companies: List[CompanyResponse]
    total: int


# Endpoints

@router.get(
    "",
    response_model=CompaniesListResponse,
    summary="List available companies",
    description="List all companies with HR data in the system, indicating which ones the user has access to."
)
async def list_companies(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    List all companies with HR data.
    
    Returns a list of companies with:
    - company_id: The company identifier
    - employee_count: Number of employees in the system
    - can_access: Whether the current user has permission to access this company's data
    """
    logger.info(
        "companies_list_requested",
        user_id=current_user.user_id
    )
    
    # Get all distinct company_ids from HR data
    company_ids = db.query(distinct(Employee.customer_id)).all()
    company_ids = [cid[0] for cid in company_ids if cid[0]]  # Filter out None values
    
    companies = []
    for company_id in sorted(company_ids):
        # Count employees for this company
        employee_count = db.query(Employee).filter(
            Employee.customer_id == company_id
        ).count()
        
        # Check if user has access to this company
        can_access = auth_middleware.check_company_access(current_user, company_id)
        
        companies.append(CompanyResponse(
            company_id=company_id,
            employee_count=employee_count,
            can_access=can_access
        ))
    
    logger.info(
        "companies_list_returned",
        user_id=current_user.user_id,
        total_companies=len(companies),
        accessible_companies=sum(1 for c in companies if c.can_access)
    )
    
    return CompaniesListResponse(
        companies=companies,
        total=len(companies)
    )


@router.get(
    "/accessible",
    response_model=CompaniesListResponse,
    summary="List accessible companies",
    description="List only companies that the current user has permission to access."
)
async def list_accessible_companies(
    db: Session = Depends(get_db),
    current_user = Depends(auth_middleware.get_current_user)
):
    """
    List only companies the user can access.
    
    This is a convenience endpoint that filters to only companies
    the user has permission to query.
    """
    logger.info(
        "accessible_companies_list_requested",
        user_id=current_user.user_id
    )
    
    # Get all distinct company_ids from HR data
    company_ids = db.query(distinct(Employee.customer_id)).all()
    company_ids = [cid[0] for cid in company_ids if cid[0]]
    
    accessible_companies = []
    for company_id in sorted(company_ids):
        # Check if user has access
        if auth_middleware.check_company_access(current_user, company_id):
            # Count employees for this company
            employee_count = db.query(Employee).filter(
                Employee.customer_id == company_id
            ).count()
            
            accessible_companies.append(CompanyResponse(
                company_id=company_id,
                employee_count=employee_count,
                can_access=True
            ))
    
    logger.info(
        "accessible_companies_list_returned",
        user_id=current_user.user_id,
        accessible_companies=len(accessible_companies)
    )
    
    return CompaniesListResponse(
        companies=accessible_companies,
        total=len(accessible_companies)
    )

