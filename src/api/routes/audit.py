"""
AI Enablement Platform - Audit API Routes

FastAPI routes for audit log management and security monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from src.services.audit_service import audit_service, AuditAction, AuditSeverity
from src.services.auth_service import auth_service
from src.models.auth import User, UserAuditLog
from src.middleware.authorization import get_current_user, require_permission, ResourceScope

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic models for request/response
class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[str]
    created_at: datetime
    
    # Additional computed fields
    user_email: Optional[str] = None
    severity: Optional[str] = None

    class Config:
        from_attributes = True


class AuditTrailResponse(BaseModel):
    audit_logs: List[AuditLogResponse]
    total_count: int
    page: int
    page_size: int
    has_next: bool


class AuditSummaryResponse(BaseModel):
    period: Dict[str, str]
    total_events: int
    security_events: int
    action_breakdown: Dict[str, int]
    most_active_users: List[Dict[str, Any]]


class SecurityEventsResponse(BaseModel):
    events: List[AuditLogResponse]
    total_count: int


@router.get("/logs", response_model=AuditTrailResponse)
async def get_audit_logs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    user_id: Optional[int] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    current_user: User = Depends(require_permission("audit:read", resource_type="audit_log"))
):
    """
    Get audit logs with filtering and pagination.
    Requires 'audit:read' permission.
    """
    try:
        offset = (page - 1) * page_size
        
        # Convert action string to AuditAction enum if provided
        action_filter = None
        if action:
            try:
                action_filter = [AuditAction(action)]
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid action type: {action}"
                )
        
        if user_id:
            # Get user-specific audit trail
            audit_logs, total_count = await audit_service.get_user_audit_trail(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                actions=action_filter,
                limit=page_size,
                offset=offset
            )
        else:
            # Get all audit logs (would need to implement this method)
            # For now, return empty result
            audit_logs, total_count = [], 0
        
        # Enhance audit logs with user information
        enhanced_logs = []
        for log in audit_logs:
            log_dict = {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "session_id": log.session_id,
                "created_at": log.created_at,
                "user_email": None,
                "severity": log.new_values.get("severity") if log.new_values else None
            }
            
            # Get user email if user_id exists
            if log.user_id:
                user = await auth_service.get_user_by_id(log.user_id)
                if user:
                    log_dict["user_email"] = user.email
            
            enhanced_logs.append(AuditLogResponse(**log_dict))
        
        has_next = (offset + page_size) < total_count
        
        return AuditTrailResponse(
            audit_logs=enhanced_logs,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=has_next
        )
        
    except Exception as e:
        logger.error(f"Error retrieving audit logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit logs"
        )


@router.get("/users/{user_id}/trail", response_model=AuditTrailResponse)
async def get_user_audit_trail(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=1000),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(require_permission("audit:read", resource_type="audit_log"))
):
    """
    Get audit trail for a specific user.
    Requires 'audit:read' permission.
    """
    try:
        offset = (page - 1) * page_size
        
        audit_logs, total_count = await audit_service.get_user_audit_trail(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=page_size,
            offset=offset
        )
        
        # Get user information
        target_user = await auth_service.get_user_by_id(user_id)
        user_email = target_user.email if target_user else None
        
        # Convert to response format
        enhanced_logs = []
        for log in audit_logs:
            log_dict = {
                "id": log.id,
                "user_id": log.user_id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "old_values": log.old_values,
                "new_values": log.new_values,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "session_id": log.session_id,
                "created_at": log.created_at,
                "user_email": user_email,
                "severity": log.new_values.get("severity") if log.new_values else None
            }
            enhanced_logs.append(AuditLogResponse(**log_dict))
        
        has_next = (offset + page_size) < total_count
        
        return AuditTrailResponse(
            audit_logs=enhanced_logs,
            total_count=total_count,
            page=page,
            page_size=page_size,
            has_next=has_next
        )
        
    except Exception as e:
        logger.error(f"Error retrieving user audit trail: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user audit trail"
        )


@router.get("/security-events", response_model=SecurityEventsResponse)
async def get_security_events(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    severity: Optional[str] = Query(None, description="Filter by severity: low, medium, high, critical"),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(require_permission("audit:read", resource_type="security_event"))
):
    """
    Get security-related audit events.
    Requires 'security.monitor' permission.
    """
    try:
        # Convert severity string to enum if provided
        severity_filter = None
        if severity:
            try:
                severity_filter = AuditSeverity(severity.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid severity level: {severity}"
                )
        
        events = await audit_service.get_security_events(
            start_date=start_date,
            end_date=end_date,
            severity=severity_filter,
            limit=limit
        )
        
        # Convert to response format
        enhanced_events = []
        for event in events:
            event_dict = {
                "id": event.id,
                "user_id": event.user_id,
                "action": event.action,
                "resource_type": event.resource_type,
                "resource_id": event.resource_id,
                "old_values": event.old_values,
                "new_values": event.new_values,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "session_id": event.session_id,
                "created_at": event.created_at,
                "user_email": None,
                "severity": event.new_values.get("severity") if event.new_values else None
            }
            
            # Get user email if user_id exists
            if event.user_id:
                user = await auth_service.get_user_by_id(event.user_id)
                if user:
                    event_dict["user_email"] = user.email
            
            enhanced_events.append(AuditLogResponse(**event_dict))
        
        return SecurityEventsResponse(
            events=enhanced_events,
            total_count=len(enhanced_events)
        )
        
    except Exception as e:
        logger.error(f"Error retrieving security events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security events"
        )


@router.get("/summary", response_model=AuditSummaryResponse)
async def get_audit_summary(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(require_permission("audit:read", resource_type="audit_log"))
):
    """
    Get audit summary statistics.
    Requires 'audit:read' permission.
    """
    try:
        summary = await audit_service.get_audit_summary(
            start_date=start_date,
            end_date=end_date
        )
        
        return AuditSummaryResponse(**summary)
        
    except Exception as e:
        logger.error(f"Error retrieving audit summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit summary"
        )
