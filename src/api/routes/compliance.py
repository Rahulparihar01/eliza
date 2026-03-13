"""
Compliance and Audit API Routes

API endpoints for accessing audit logs, compliance reports, and security monitoring.
Required for SOC2 compliance dashboards and audit responses.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.middleware.authorization import (
    get_current_user,
    require_permission,
    CurrentUserContext,
)
from src.services.data_access_audit_service import DataAccessAuditService
from src.models.audit import (
    DataAccessAuditLog,
    RLSViolationLog,
    TenantActivitySummary,
    ComplianceReport,
)

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance & Audit"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class DataAccessLogResponse(BaseModel):
    """Response schema for data access log entries."""
    id: int
    timestamp: datetime
    user_id: Optional[int]
    customer_id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    api_endpoint: Optional[str]
    api_method: Optional[str]
    records_affected: Optional[int]
    data_classification: Optional[str]
    outcome: str
    denial_reason: Optional[str]
    severity: str
    duration_ms: Optional[int]
    ip_address: Optional[str]

    class Config:
        from_attributes = True


class DataAccessLogListResponse(BaseModel):
    """Paginated list of data access logs."""
    logs: List[DataAccessLogResponse]
    total: int
    page: int
    page_size: int


class RLSViolationResponse(BaseModel):
    """Response schema for RLS violation entries."""
    id: int
    timestamp: datetime
    user_id: Optional[int]
    customer_id: str
    target_customer_id: str
    table_name: str
    operation: str
    blocked_by: str
    severity: str
    investigated: bool
    investigated_by: Optional[int]
    investigated_at: Optional[datetime]
    investigation_notes: Optional[str]
    ip_address: Optional[str]
    api_endpoint: Optional[str]

    class Config:
        from_attributes = True


class RLSViolationListResponse(BaseModel):
    """Paginated list of RLS violations."""
    violations: List[RLSViolationResponse]
    total: int
    page: int
    page_size: int


class TenantActivitySummaryResponse(BaseModel):
    """Response schema for tenant activity summary."""
    id: int
    period_start: datetime
    period_end: datetime
    period_type: str
    customer_id: str
    total_requests: int
    total_reads: int
    total_writes: int
    total_deletes: int
    unique_users: int
    login_count: int
    failed_login_count: int
    permission_denied_count: int
    rls_violation_count: int
    pii_access_count: int
    sensitive_data_access_count: int

    class Config:
        from_attributes = True


class ComplianceReportResponse(BaseModel):
    """Response schema for compliance reports."""
    id: int
    report_type: str
    report_name: str
    description: Optional[str]
    customer_id: Optional[str]
    start_date: datetime
    end_date: datetime
    generated_by: int
    generated_at: datetime
    generation_duration_ms: Optional[int]
    status: str
    error_message: Optional[str]
    access_count: int

    class Config:
        from_attributes = True


class GenerateReportRequest(BaseModel):
    """Request to generate a compliance report."""
    report_type: str = Field(..., description="Type: user_access, tenant_security, data_access")
    start_date: datetime
    end_date: datetime
    user_id: Optional[int] = Field(None, description="User ID for user_access reports")


class AuditDashboardResponse(BaseModel):
    """Dashboard summary for audit/compliance overview."""
    period_start: datetime
    period_end: datetime
    total_data_access_events: int
    total_rls_violations: int
    total_denied_access: int
    high_severity_events: int
    unique_users_active: int
    top_accessed_resources: List[dict]
    recent_violations: List[RLSViolationResponse]


# =============================================================================
# Data Access Audit Endpoints
# =============================================================================

@router.get("/audit/data-access", response_model=DataAccessLogListResponse)
async def list_data_access_logs(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    action: Optional[str] = Query(None, description="Filter by action (SELECT, INSERT, UPDATE, DELETE)"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (success, denied, error)"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, critical)"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List data access audit logs for the current tenant.
    
    Requires: audit:read permission or platform:admin
    """
    # Check permission
    if not current_user.has_permission('audit:read') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:read required"
        )
    
    audit_service = DataAccessAuditService(db)
    
    # Platform admins can see all, others only their tenant
    customer_id = None if current_user.has_permission('platform:admin') else current_user.customer_id
    
    logs, total = await audit_service.get_data_access_logs(
        customer_id=customer_id,
        user_id=user_id,
        resource_type=resource_type,
        action=action,
        outcome=outcome,
        severity=severity,
        start_date=start_date,
        end_date=end_date,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    
    return DataAccessLogListResponse(
        logs=[DataAccessLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit/data-access/{log_id}", response_model=DataAccessLogResponse)
async def get_data_access_log(
    log_id: int,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a specific data access log entry."""
    if not current_user.has_permission('audit:read') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:read required"
        )
    
    log = db.query(DataAccessAuditLog).filter(DataAccessAuditLog.id == log_id).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    # Verify tenant access
    if not current_user.has_permission('platform:admin') and log.customer_id != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Audit log not found")
    
    return DataAccessLogResponse.model_validate(log)


# =============================================================================
# RLS Violation Endpoints
# =============================================================================

@router.get("/audit/rls-violations", response_model=RLSViolationListResponse)
async def list_rls_violations(
    target_customer_id: Optional[str] = Query(None, description="Filter by target tenant"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    investigated: Optional[bool] = Query(None, description="Filter by investigation status"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List RLS violation attempts.
    
    Platform admins see all violations, tenant admins see violations by their users.
    """
    if not current_user.has_permission('audit:read') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:read required"
        )
    
    audit_service = DataAccessAuditService(db)
    
    # Platform admins can see all, others only their tenant's users
    customer_id = None if current_user.has_permission('platform:admin') else current_user.customer_id
    
    violations, total = await audit_service.get_rls_violations(
        customer_id=customer_id,
        target_customer_id=target_customer_id,
        user_id=user_id,
        investigated=investigated,
        start_date=start_date,
        end_date=end_date,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    
    return RLSViolationListResponse(
        violations=[RLSViolationResponse.model_validate(v) for v in violations],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/audit/rls-violations/{violation_id}/investigate")
async def mark_violation_investigated(
    violation_id: int,
    notes: str = Query(..., description="Investigation notes"),
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark an RLS violation as investigated."""
    if not current_user.has_permission('audit:update') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:update required"
        )
    
    violation = db.query(RLSViolationLog).filter(RLSViolationLog.id == violation_id).first()
    
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    # Verify access
    if not current_user.has_permission('platform:admin') and violation.customer_id != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    violation.investigated = True
    violation.investigated_by = current_user.user_id
    violation.investigated_at = datetime.now(timezone.utc)
    violation.investigation_notes = notes
    
    db.commit()
    
    return {"message": "Violation marked as investigated", "violation_id": violation_id}


# =============================================================================
# Compliance Reports Endpoints
# =============================================================================

@router.get("/reports", response_model=List[ComplianceReportResponse])
async def list_compliance_reports(
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List compliance reports for the current tenant."""
    if not current_user.has_permission('audit:read') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:read required"
        )
    
    query = db.query(ComplianceReport)
    
    # Filter by tenant
    if not current_user.has_permission('platform:admin'):
        query = query.filter(ComplianceReport.customer_id == current_user.customer_id)
    
    if report_type:
        query = query.filter(ComplianceReport.report_type == report_type)
    if status:
        query = query.filter(ComplianceReport.status == status)
    
    reports = query.order_by(ComplianceReport.generated_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    return [ComplianceReportResponse.model_validate(r) for r in reports]


@router.post("/reports/generate", response_model=ComplianceReportResponse)
async def generate_compliance_report(
    request: GenerateReportRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Generate a new compliance report.
    
    Report types:
    - user_access: Access report for a specific user (requires user_id)
    - tenant_security: Security report for the tenant
    - data_access: Data access summary report
    """
    if not current_user.has_permission('audit:create') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:create required"
        )
    
    audit_service = DataAccessAuditService(db)
    
    if request.report_type == 'user_access':
        if not request.user_id:
            raise HTTPException(
                status_code=400,
                detail="user_id is required for user_access reports"
            )
        report = await audit_service.generate_user_access_report(
            customer_id=current_user.customer_id,
            user_id=request.user_id,
            start_date=request.start_date,
            end_date=request.end_date,
            generated_by=current_user.user_id,
        )
    elif request.report_type == 'tenant_security':
        report = await audit_service.generate_tenant_security_report(
            customer_id=current_user.customer_id,
            start_date=request.start_date,
            end_date=request.end_date,
            generated_by=current_user.user_id,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown report type: {request.report_type}"
        )
    
    return ComplianceReportResponse.model_validate(report)


@router.get("/reports/{report_id}", response_model=dict)
async def get_compliance_report(
    report_id: int,
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a compliance report with full data."""
    if not current_user.has_permission('audit:read') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:read required"
        )
    
    report = db.query(ComplianceReport).filter(ComplianceReport.id == report_id).first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Verify tenant access
    if not current_user.has_permission('platform:admin') and report.customer_id != current_user.customer_id:
        raise HTTPException(status_code=404, detail="Report not found")
    
    # Update access tracking
    report.last_accessed_at = datetime.now(timezone.utc)
    report.access_count += 1
    db.commit()
    
    return {
        "metadata": ComplianceReportResponse.model_validate(report).model_dump(),
        "data": report.report_data,
    }


# =============================================================================
# Dashboard Endpoints
# =============================================================================

@router.get("/dashboard", response_model=AuditDashboardResponse)
async def get_audit_dashboard(
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get audit dashboard summary for compliance monitoring.
    
    Provides overview of:
    - Total data access events
    - RLS violations
    - Denied access attempts
    - High severity events
    - Top accessed resources
    """
    if not current_user.has_permission('audit:read') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:read required"
        )
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    
    customer_id = None if current_user.has_permission('platform:admin') else current_user.customer_id
    
    audit_service = DataAccessAuditService(db)
    
    # Get summary statistics
    from sqlalchemy import func
    
    query_base = db.query(DataAccessAuditLog)
    if customer_id:
        query_base = query_base.filter(DataAccessAuditLog.customer_id == customer_id)
    query_base = query_base.filter(
        DataAccessAuditLog.timestamp >= start_date,
        DataAccessAuditLog.timestamp <= end_date,
    )
    
    total_events = query_base.count()
    denied_events = query_base.filter(DataAccessAuditLog.outcome == 'denied').count()
    high_severity = query_base.filter(DataAccessAuditLog.severity.in_(['high', 'critical'])).count()
    unique_users = db.query(func.count(func.distinct(DataAccessAuditLog.user_id))).filter(
        DataAccessAuditLog.customer_id == customer_id if customer_id else True,
        DataAccessAuditLog.timestamp >= start_date,
    ).scalar()
    
    # Get RLS violations
    violations, violation_count = await audit_service.get_rls_violations(
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        limit=10,
    )
    
    # Get top accessed resources
    top_resources = db.query(
        DataAccessAuditLog.resource_type,
        func.count(DataAccessAuditLog.id).label('count')
    ).filter(
        DataAccessAuditLog.customer_id == customer_id if customer_id else True,
        DataAccessAuditLog.timestamp >= start_date,
    ).group_by(DataAccessAuditLog.resource_type).order_by(
        func.count(DataAccessAuditLog.id).desc()
    ).limit(10).all()
    
    return AuditDashboardResponse(
        period_start=start_date,
        period_end=end_date,
        total_data_access_events=total_events,
        total_rls_violations=violation_count,
        total_denied_access=denied_events,
        high_severity_events=high_severity,
        unique_users_active=unique_users or 0,
        top_accessed_resources=[
            {"resource_type": r[0], "count": r[1]} for r in top_resources
        ],
        recent_violations=[RLSViolationResponse.model_validate(v) for v in violations],
    )


# =============================================================================
# Activity Summary Endpoints
# =============================================================================

@router.get("/activity/summary", response_model=List[TenantActivitySummaryResponse])
async def get_activity_summary(
    period_type: str = Query("daily", description="Period type: hourly, daily, weekly, monthly"),
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    current_user: CurrentUserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get aggregated activity summary for the tenant."""
    if not current_user.has_permission('audit:read') and not current_user.has_permission('platform:admin'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: audit:read required"
        )
    
    audit_service = DataAccessAuditService(db)
    
    summaries = await audit_service.get_tenant_activity_summary(
        customer_id=current_user.customer_id,
        period_type=period_type,
        start_date=start_date,
        end_date=end_date,
    )
    
    return [TenantActivitySummaryResponse.model_validate(s) for s in summaries]

