"""
Adoption Dashboard API Routes.

Endpoints for:
- GET /adoption/metrics - Query adoption metrics (union across accessible companies)
- GET /adoption/overview - Get overview of all accessible companies
- GET /adoption/dashboard - Pre-computed dashboard widget data
- GET /adoption/shares - List adoption shares
- POST /adoption/shares - Create a new share
- PATCH /adoption/shares/{id} - Update a share
- DELETE /adoption/shares/{id} - Delete a share
- GET /adoption/providers - List adoption-configured providers
- POST /adoption/providers/{id}/enable - Enable a provider for adoption
- POST /adoption/sync - Trigger manual sync (admin only)
"""

from typing import Optional, List, Dict
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.models.database import get_db
from src.middleware.authorization import (
    get_current_user,
    require_permission,
    check_adoption_access,
    AuthorizationMiddleware
)
from src.core.auth_context import CurrentUserContext
from src.core.logging import get_logger, LogCategory
from src.services.adoption_service import AdoptionService
from src.api.schemas.adoption import (
    # Metrics
    AdoptionMetricsQuery,
    AdoptionMetricsResponse,
    AdoptionMetricsSummary,
    CompanyMetricsResponse,
    DailyMetric,
    AdoptionOverviewResponse,
    CompanyAdoptionSummary,
    DashboardWidgetsResponse,
    # GPT Analytics
    TopGPTsResponse,
    GPTUsersResponse,
    GPTInfo,
    # User Analytics
    TopUsersResponse,
    TopUserInfo,
    # Sharing
    AdoptionShareCreate,
    AdoptionShareUpdate,
    AdoptionShareResponse,
    AdoptionShareListResponse,
    # Providers
    AdoptionProviderConfig,
    AdoptionProviderListResponse,
    # Sync
    AdoptionSyncRequest,
    AdoptionSyncResponse,
)

logger = get_logger(__name__, LogCategory.API)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/v1/adoption", tags=["Adoption Dashboard"])


class AdoptionIntegrityCheckResponse(BaseModel):
    """On-demand integrity diagnostics for tenant adoption sync data."""
    customer_id: str
    provider_type: Optional[str]
    is_consistent: bool
    latest_metric_date: Optional[str]
    latest_conversation_date: Optional[str]
    gap_days: int


# =============================================================================
# Dependencies
# =============================================================================

def get_adoption_service(
    db: Session = Depends(get_db),
    current_user: CurrentUserContext = Depends(get_current_user)
) -> AdoptionService:
    """Get AdoptionService instance with current user context."""
    return AdoptionService(db, current_user)


# =============================================================================
# Metrics Endpoints
# =============================================================================

@router.get(
    "/metrics",
    response_model=List[CompanyMetricsResponse],
    summary="Get adoption metrics",
    description="Query adoption metrics across all accessible companies (union query pattern)"
)
async def get_metrics(
    company_id: Optional[str] = Query(None, description="Filter to specific company"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=365, description="Number of days if no date range"),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """
    Get adoption metrics with union query across accessible companies.
    
    Returns per-company metrics from:
    - User's own tenant
    - Companies granted via platform admin permissions
    - Companies shared via AdoptionDataShare
    """
    from collections import defaultdict
    from datetime import timedelta
    
    # Determine date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=days)
    
    # Get filter IDs
    filter_ids = [company_id] if company_id else None
    
    metrics, _ = service.get_metrics(
        customer_ids=filter_ids,
        start_date=start_date,
        end_date=end_date
    )
    
    # Group metrics by company
    company_metrics: Dict[str, List] = defaultdict(list)
    for m in metrics:
        daily = DailyMetric(
            date=m.metric_date,
            customer_id=m.customer_id,
            provider_type=m.source_type,
            active_users=m.active_users or 0,
            total_conversations=m.total_conversations or 0,
            total_messages=m.total_messages or 0,
            gpt_conversations=getattr(m, 'gpt_conversations', 0) or 0,
            base_conversations=getattr(m, 'base_conversations', 0) or 0,
            unique_gpts=getattr(m, 'unique_gpts', 0) or 0,
            input_tokens=m.input_tokens or 0,
            output_tokens=m.output_tokens or 0,
            total_tokens=(m.input_tokens or 0) + (m.output_tokens or 0)
        )
        company_metrics[m.customer_id].append(daily)
    
    # Build per-company responses
    responses = []
    for cid, daily_list in company_metrics.items():
        # Calculate summary for this company
        total_users = sum(d.active_users for d in daily_list)
        total_convos = sum(d.total_conversations for d in daily_list)
        total_msgs = sum(d.total_messages for d in daily_list)
        total_toks = sum(d.total_tokens or 0 for d in daily_list)
        total_gpt_convos = sum(d.gpt_conversations or 0 for d in daily_list)
        total_base_convos = sum(d.base_conversations or 0 for d in daily_list)
        num_days = len(daily_list)
        
        summary = AdoptionMetricsSummary(
            total_active_users=total_users,
            total_conversations=total_convos,
            total_messages=total_msgs,
            total_tokens=total_toks,
            avg_daily_users=total_users / num_days if num_days > 0 else 0,
            avg_daily_conversations=total_convos / num_days if num_days > 0 else 0,
            gpt_conversations=total_gpt_convos,
            base_conversations=total_base_convos,
            gpt_adoption_rate=(total_gpt_convos / total_convos * 100) if total_convos > 0 else 0,
            top_models=[],
            top_gpts=[]
        )
        
        responses.append(CompanyMetricsResponse(
            company_id=cid,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            metrics=sorted(daily_list, key=lambda x: x.date),
            summary=summary
        ))
    
    return responses


@router.get(
    "/overview",
    response_model=AdoptionOverviewResponse,
    summary="Get adoption overview",
    description="Overview of all accessible companies' adoption status"
)
async def get_overview(
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """Get high-level overview of all accessible companies."""
    companies = service.get_company_overview()
    
    summaries = [CompanyAdoptionSummary(**c) for c in companies]
    
    return AdoptionOverviewResponse(
        companies=summaries,
        total_companies=len(summaries),
        companies_with_data=len([c for c in companies if c["total_days_tracked"] > 0])
    )


@router.get(
    "/dashboard",
    response_model=DashboardWidgetsResponse,
    summary="Get dashboard widget data",
    description="Pre-computed data for dashboard charts and widgets"
)
async def get_dashboard_widgets(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """Get pre-computed dashboard widget data."""
    widgets = service.get_dashboard_widgets(days=days)
    return DashboardWidgetsResponse(**widgets)


# =============================================================================
# GPT Analytics Endpoints
# =============================================================================

@router.get(
    "/gpts/top",
    response_model=TopGPTsResponse,
    summary="Get top GPTs by usage",
    description="Get ranked list of GPTs with usage metrics from granular conversation data"
)
async def get_top_gpts(
    customer_id: Optional[str] = Query(None, description="Filter to specific company"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=365, description="Number of days (if no date range)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum GPTs to return"),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """
    Get top GPTs ranked by usage (user messages).
    
    Uses granular conversation data for accurate per-GPT metrics including:
    - Total user messages
    - Unique users
    - Conversation count
    - Creator information
    - GPT description
    """
    from datetime import timedelta
    
    # Calculate date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=days)
    
    customer_ids = [customer_id] if customer_id else None
    
    gpts = service.get_top_gpts(
        customer_ids=customer_ids,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    return TopGPTsResponse(
        gpts=[GPTInfo(**g) for g in gpts],
        total_count=len(gpts),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )


@router.get(
    "/gpts/{gpt_id}/users",
    response_model=GPTUsersResponse,
    summary="Get users who interacted with a GPT",
    description="Get list of users who have used a specific GPT for feedback outreach"
)
async def get_gpt_users(
    gpt_id: str = Path(..., description="External GPT ID (g-xxx)"),
    customer_id: Optional[str] = Query(None, description="Filter to specific company"),
    limit: int = Query(100, ge=1, le=500, description="Maximum users to return"),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """
    Get users who have interacted with a specific GPT.
    
    This enables targeted outreach for feedback collection on specific GPTs.
    Returns user info with interaction metrics (no message content).
    """
    users = service.get_users_for_gpt(
        gpt_external_id=gpt_id,
        customer_id=customer_id,
        limit=limit
    )
    
    return GPTUsersResponse(
        gpt_id=gpt_id,
        gpt_name=None,  # Could fetch from AdoptionGPT if needed
        users=users,
        total_count=len(users)
    )


# =============================================================================
# User Analytics Endpoints
# =============================================================================

@router.get(
    "/users/top",
    response_model=TopUsersResponse,
    summary="Get top ChatGPT users by usage",
    description="Get ranked list of users by total messages and conversations"
)
async def get_top_users(
    customer_id: Optional[str] = Query(None, description="Filter to specific company"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    days: int = Query(30, ge=1, le=365, description="Number of days (if no date range)"),
    limit: int = Query(10, ge=1, le=100, description="Maximum users to return"),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """
    Get top ChatGPT users ranked by usage (messages sent).
    
    Uses granular conversation data for accurate per-user metrics including:
    - Total conversations
    - Total messages sent
    - Unique GPTs used
    """
    # Calculate date range
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=days)
    
    customer_ids = [customer_id] if customer_id else None
    
    users = service.get_top_users(
        customer_ids=customer_ids,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    return TopUsersResponse(
        users=[TopUserInfo(**u) for u in users],
        total_count=len(users),
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )


# =============================================================================
# Sharing Endpoints
# =============================================================================

@router.get(
    "/shares",
    response_model=AdoptionShareListResponse,
    summary="List adoption shares",
    description="List shares given and received by current tenant"
)
async def list_shares(
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service),
    db: Session = Depends(get_db)
):
    """List adoption data shares for current tenant."""
    shares_given, shares_received = service.get_shares()
    
    # Get customer names for display
    customer_ids = set()
    for s in shares_given + shares_received:
        customer_ids.add(s.source_customer_id)
        customer_ids.add(s.target_customer_id)
    
    from src.models.customer import Customer
    customers = {
        c.customer_id: c.display_name or c.name
        for c in db.query(Customer).filter(Customer.customer_id.in_(customer_ids)).all()
    }
    
    given_responses = [
        AdoptionShareResponse(
            id=s.id,
            source_customer_id=s.source_customer_id,
            source_customer_name=customers.get(s.source_customer_id),
            target_customer_id=s.target_customer_id,
            target_customer_name=customers.get(s.target_customer_id),
            share_level=s.share_level,
            is_enabled=s.is_enabled,
            notes=s.notes,
            expires_at=s.expires_at,
            created_by=s.created_by,
            created_at=s.created_at,
            updated_at=s.updated_at,
            is_active=s.is_active
        )
        for s in shares_given
    ]
    
    received_responses = [
        AdoptionShareResponse(
            id=s.id,
            source_customer_id=s.source_customer_id,
            source_customer_name=customers.get(s.source_customer_id),
            target_customer_id=s.target_customer_id,
            target_customer_name=customers.get(s.target_customer_id),
            share_level=s.share_level,
            is_enabled=s.is_enabled,
            notes=s.notes,
            expires_at=s.expires_at,
            created_by=s.created_by,
            created_at=s.created_at,
            updated_at=s.updated_at,
            is_active=s.is_active
        )
        for s in shares_received
    ]
    
    return AdoptionShareListResponse(
        shares_given=given_responses,
        shares_received=received_responses,
        total_given=len(given_responses),
        total_received=len(received_responses)
    )


@router.post(
    "/shares",
    response_model=AdoptionShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create adoption share",
    description="Share your adoption data with another company"
)
async def create_share(
    request: AdoptionShareCreate,
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:manage_sharing")
    ),
    service: AdoptionService = Depends(get_adoption_service),
    db: Session = Depends(get_db)
):
    """Create a new adoption data share."""
    try:
        share = service.create_share(
            target_customer_id=request.target_customer_id,
            share_level=request.share_level,
            notes=request.notes,
            expires_at=request.expires_at
        )
        
        # Get customer names
        from src.models.customer import Customer
        customers = {
            c.customer_id: c.display_name or c.name
            for c in db.query(Customer).filter(
                Customer.customer_id.in_([share.source_customer_id, share.target_customer_id])
            ).all()
        }
        
        return AdoptionShareResponse(
            id=share.id,
            source_customer_id=share.source_customer_id,
            source_customer_name=customers.get(share.source_customer_id),
            target_customer_id=share.target_customer_id,
            target_customer_name=customers.get(share.target_customer_id),
            share_level=share.share_level,
            is_enabled=share.is_enabled,
            notes=share.notes,
            expires_at=share.expires_at,
            created_by=share.created_by,
            created_at=share.created_at,
            updated_at=share.updated_at,
            is_active=share.is_active
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch(
    "/shares/{share_id}",
    response_model=AdoptionShareResponse,
    summary="Update adoption share",
    description="Update an existing share"
)
async def update_share(
    share_id: int,
    request: AdoptionShareUpdate,
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:manage_sharing")
    ),
    service: AdoptionService = Depends(get_adoption_service),
    db: Session = Depends(get_db)
):
    """Update an existing adoption share."""
    try:
        share = service.update_share(
            share_id=share_id,
            share_level=request.share_level,
            is_enabled=request.is_enabled,
            notes=request.notes,
            expires_at=request.expires_at
        )
        
        from src.models.customer import Customer
        customers = {
            c.customer_id: c.display_name or c.name
            for c in db.query(Customer).filter(
                Customer.customer_id.in_([share.source_customer_id, share.target_customer_id])
            ).all()
        }
        
        return AdoptionShareResponse(
            id=share.id,
            source_customer_id=share.source_customer_id,
            source_customer_name=customers.get(share.source_customer_id),
            target_customer_id=share.target_customer_id,
            target_customer_name=customers.get(share.target_customer_id),
            share_level=share.share_level,
            is_enabled=share.is_enabled,
            notes=share.notes,
            expires_at=share.expires_at,
            created_by=share.created_by,
            created_at=share.created_at,
            updated_at=share.updated_at,
            is_active=share.is_active
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete(
    "/shares/{share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete adoption share",
    description="Revoke an existing share"
)
async def delete_share(
    share_id: int,
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:manage_sharing")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """Delete (revoke) an adoption share."""
    try:
        service.delete_share(share_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# =============================================================================
# Provider Configuration Endpoints
# =============================================================================

@router.get(
    "/providers",
    response_model=AdoptionProviderListResponse,
    summary="List adoption providers",
    description="List AI providers configured for adoption tracking"
)
async def list_adoption_providers(
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """List providers configured for adoption tracking."""
    providers = service.get_adoption_providers()
    
    return AdoptionProviderListResponse(
        providers=[
            AdoptionProviderConfig(
                id=p.id,
                customer_id=p.customer_id,
                provider_name=p.provider_name,
                display_name=p.name,
                is_adoption_source=p.is_adoption_source,
                is_enabled=p.is_enabled,
                last_sync_at=p.updated_at,
                sync_status=None
            )
            for p in providers
        ],
        total=len(providers)
    )


@router.post(
    "/providers/{provider_id}/enable",
    response_model=AdoptionProviderConfig,
    summary="Enable provider for adoption",
    description="Mark a provider as an adoption data source"
)
async def enable_adoption_provider(
    provider_id: int,
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission([
            "adoption:manage_sync",
            "adoption:admin:company:*"
        ])
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """Enable a provider for adoption tracking."""
    try:
        provider = service.set_adoption_source(provider_id, is_source=True)
        
        return AdoptionProviderConfig(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_name=provider.provider_name,
            display_name=provider.name,
            is_adoption_source=provider.is_adoption_source,
            is_enabled=provider.is_enabled,
            last_sync_at=provider.updated_at,
            sync_status=None
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/providers/{provider_id}/disable",
    response_model=AdoptionProviderConfig,
    summary="Disable provider for adoption",
    description="Remove a provider as an adoption data source"
)
async def disable_adoption_provider(
    provider_id: int,
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission([
            "adoption:manage_sync",
            "adoption:admin:company:*"
        ])
    ),
    service: AdoptionService = Depends(get_adoption_service)
):
    """Disable a provider for adoption tracking."""
    try:
        provider = service.set_adoption_source(provider_id, is_source=False)
        
        return AdoptionProviderConfig(
            id=provider.id,
            customer_id=provider.customer_id,
            provider_name=provider.provider_name,
            display_name=provider.name,
            is_adoption_source=provider.is_adoption_source,
            is_enabled=provider.is_enabled,
            last_sync_at=provider.updated_at,
            sync_status=None
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# =============================================================================
# Sync Endpoints
# =============================================================================

@router.get(
    "/sync/integrity-check",
    response_model=AdoptionIntegrityCheckResponse,
    summary="Run adoption sync integrity check",
    description="Checks for table consistency gaps before sync/recovery decisions."
)
async def adoption_integrity_check(
    customer_id: Optional[str] = Query(None, description="Company to check; defaults to current tenant"),
    provider_type: Optional[str] = Query(None, description="Provider type override (defaults to configured adoption provider)"),
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:view_dashboard")
    ),
    db: Session = Depends(get_db)
):
    """Run and return adoption sync integrity diagnostics."""
    from src.models.customer import CustomerAIProvider
    from src.services.adoption.sync_service import AdoptionSyncService

    target_customer_id = customer_id or current_user.customer_id
    if not check_adoption_access(current_user, target_customer_id, action="read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No read access to company '{target_customer_id}'"
        )

    selected_provider_type = provider_type
    if not selected_provider_type:
        provider = db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == target_customer_id,
            CustomerAIProvider.is_adoption_source == True,
            CustomerAIProvider.is_enabled == True
        ).first()
        selected_provider_type = provider.provider_name if provider else "openai"

    sync_service = AdoptionSyncService(db)
    result = sync_service.check_consistency(target_customer_id, selected_provider_type)

    return AdoptionIntegrityCheckResponse(
        customer_id=target_customer_id,
        provider_type=selected_provider_type,
        is_consistent=result["is_consistent"],
        latest_metric_date=result["latest_metric_date"],
        latest_conversation_date=result["latest_conversation_date"],
        gap_days=result["gap_days"],
    )


@router.post(
    "/sync",
    response_model=AdoptionSyncResponse,
    summary="Trigger manual sync",
    description="Trigger a manual adoption data sync (admin only)"
)
async def trigger_sync(
    request: AdoptionSyncRequest,
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_permission("adoption:manage_sync")
    ),
    service: AdoptionService = Depends(get_adoption_service),
    db: Session = Depends(get_db)
):
    """
    Trigger a manual adoption data sync.
    
    Queues a Celery task to sync adoption metrics from the configured
    provider (OpenAI Compliance API, etc.).
    """
    from src.tasks.adoption_sync_tasks import sync_adoption_provider, sync_all_adoption_providers
    from src.models.customer import CustomerAIProvider
    
    customer_id = request.customer_id or current_user.customer_id
    
    # Verify user has access to this company
    if not check_adoption_access(current_user, customer_id, action="admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No admin access to company '{customer_id}'"
        )
    
    # Find the adoption provider for this customer
    query = db.query(CustomerAIProvider).filter(
        CustomerAIProvider.customer_id == customer_id,
        CustomerAIProvider.is_adoption_source == True,
        CustomerAIProvider.is_enabled == True
    )
    
    if request.provider_type:
        query = query.filter(CustomerAIProvider.provider_name == request.provider_type)
    
    provider = query.first()
    
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No adoption provider configured for company '{customer_id}'"
        )
    
    # Queue the sync task
    task = sync_adoption_provider.delay(
        provider_id=provider.id,
        customer_id=customer_id,
        start_date=request.start_date.isoformat() if request.start_date else None,
        end_date=request.end_date.isoformat() if request.end_date else None,
        force=False
    )
    
    return AdoptionSyncResponse(
        task_id=task.id,
        status="queued",
        message=f"Sync task queued for provider {provider.provider_name}",
        customer_id=customer_id,
        provider_type=provider.provider_name
    )

