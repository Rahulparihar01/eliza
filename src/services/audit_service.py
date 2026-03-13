"""
AI Enablement Platform - Audit Service

Comprehensive audit logging service for security, compliance, and monitoring.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from enum import Enum

from src.models.auth import UserAuditLog, User
from src.services.base_service import BaseService

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Standard audit action types for consistency."""
    
    # Authentication actions
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    
    # Session management
    SESSION_CREATED = "session_created"
    SESSION_EXPIRED = "session_expired"
    SESSION_TERMINATED = "session_terminated"
    SESSION_REFRESHED = "session_refreshed"

    # API key management
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_USED = "api_key_used"
    API_KEY_EXPIRED = "api_key_expired"
    
    # User management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    USER_VIEWED = "user_viewed"
    USERS_LIST_ACCESSED = "users_list_accessed"
    USER_PASSWORD_RESET = "user_password_reset"
    USERS_BULK_UPDATED = "users_bulk_updated"
    USERS_EXPORTED = "users_exported"
    
    # Role and permission management
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    
    # Document management
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_VIEWED = "document_viewed"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_SHARED = "document_shared"
    DOCUMENTS_LIST_ACCESSED = "documents_list_accessed"
    DOCUMENT_METRICS_ACCESSED = "document_metrics_accessed"
    PROCESSING_QUEUE_ACCESSED = "processing_queue_accessed"
    DOCUMENT_REPROCESS_INITIATED = "document_reprocess_initiated"
    DOCUMENT_ADMIN_DELETED = "document_admin_deleted"
    DOCUMENTS_BULK_DELETED = "documents_bulk_deleted"
    
    # Search and AI operations
    SEARCH_EXECUTED = "search_executed"
    AI_QUERY_EXECUTED = "ai_query_executed"
    MODEL_CONFIGURED = "model_configured"
    AI_PROVIDERS_ACCESSED = "ai_providers_accessed"
    AI_USAGE_METRICS_ACCESSED = "ai_usage_metrics_accessed"
    AI_PROVIDER_CONFIG_UPDATED = "ai_provider_config_updated"
    AI_PROVIDER_TESTED = "ai_provider_tested"
    
    # System administration
    SYSTEM_CONFIG_CHANGED = "system_config_changed"
    SYSTEM_HEALTH_ACCESSED = "system_health_accessed"
    SYSTEM_METRICS_ACCESSED = "system_metrics_accessed"
    ADMIN_DASHBOARD_ACCESSED = "admin_dashboard_accessed"
    AUDIT_LOGS_ACCESSED = "audit_logs_accessed"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    
    # Security events
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SECURITY_VIOLATION = "security_violation"


class AuditSeverity(Enum):
    """Audit event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditService(BaseService):
    """Centralized audit logging service."""
    
    def __init__(self):
        self.retention_days = 2555  # 7 years for compliance
        self.high_risk_actions = {
            AuditAction.USER_DELETED,
            AuditAction.PERMISSION_GRANTED,
            AuditAction.PERMISSION_REVOKED,
            AuditAction.SYSTEM_CONFIG_CHANGED,
            AuditAction.BACKUP_RESTORED,
            AuditAction.SECURITY_VIOLATION
        }
    
    async def log_event(
        self,
        action: AuditAction,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> UserAuditLog:
        """
        Log an audit event with comprehensive context.
        
        Args:
            action: The action being audited
            user_id: ID of the user performing the action
            resource_type: Type of resource being acted upon
            resource_id: ID of the specific resource
            old_values: Previous values (for updates)
            new_values: New values (for updates/creates)
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session token
            severity: Event severity level
            additional_context: Any additional context data
        
        Returns:
            The created audit log entry
        """
        with self.get_db_session() as db:
            # Determine severity if not provided
            if severity is None:
                severity = self._determine_severity(action)
            
            # Enhance new_values with additional context
            enhanced_new_values = new_values or {}
            if additional_context:
                enhanced_new_values.update(additional_context)
            if severity:
                enhanced_new_values["severity"] = severity.value
            
            audit_log = UserAuditLog(
                user_id=user_id,
                action=action.value,
                resource_type=resource_type,
                resource_id=resource_id,
                old_values=old_values,
                new_values=enhanced_new_values,
                ip_address=ip_address,
                user_agent=user_agent,
                session_id=session_id
            )
            
            db.add(audit_log)
            db.commit()
            db.refresh(audit_log)
            
            # Log high-severity events to application logger
            if severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]:
                logger.warning(
                    f"High-severity audit event: {action.value} by user {user_id} "
                    f"on {resource_type}:{resource_id} from {ip_address}"
                )
            
            return audit_log
    
    def _determine_severity(self, action: AuditAction) -> AuditSeverity:
        """Determine the severity level for an audit action."""
        if action in self.high_risk_actions:
            return AuditSeverity.HIGH
        elif action in [AuditAction.LOGIN_FAILED, AuditAction.PERMISSION_DENIED]:
            return AuditSeverity.MEDIUM
        else:
            return AuditSeverity.LOW
    
    async def get_user_audit_trail(
        self,
        user_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        actions: Optional[List[AuditAction]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[UserAuditLog], int]:
        """
        Get audit trail for a specific user.
        
        Returns:
            Tuple of (audit_logs, total_count)
        """
        with self.get_db_session() as db:
            query = db.query(UserAuditLog).filter(UserAuditLog.user_id == user_id)
            
            if start_date:
                query = query.filter(UserAuditLog.created_at >= start_date)
            if end_date:
                query = query.filter(UserAuditLog.created_at <= end_date)
            if actions:
                action_values = [action.value for action in actions]
                query = query.filter(UserAuditLog.action.in_(action_values))
            
            total_count = query.count()
            audit_logs = query.order_by(desc(UserAuditLog.created_at)).offset(offset).limit(limit).all()
            
            return audit_logs, total_count
    
    async def get_security_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        limit: int = 100
    ) -> List[UserAuditLog]:
        """Get security-related audit events."""
        security_actions = [
            AuditAction.LOGIN_FAILED.value,
            AuditAction.ACCOUNT_LOCKED.value,
            AuditAction.PERMISSION_DENIED.value,
            AuditAction.SUSPICIOUS_ACTIVITY.value,
            AuditAction.SECURITY_VIOLATION.value
        ]
        
        with self.get_db_session() as db:
            query = db.query(UserAuditLog).filter(
                UserAuditLog.action.in_(security_actions)
            )
            
            if start_date:
                query = query.filter(UserAuditLog.created_at >= start_date)
            if end_date:
                query = query.filter(UserAuditLog.created_at <= end_date)
            if severity:
                # Filter by severity in new_values JSON
                query = query.filter(
                    UserAuditLog.new_values.op('->>')('severity') == severity.value
                )
            
            return query.order_by(desc(UserAuditLog.created_at)).limit(limit).all()
    
    async def get_audit_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get audit summary statistics."""
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=30)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        
        with self.get_db_session() as db:
            base_query = db.query(UserAuditLog).filter(
                and_(
                    UserAuditLog.created_at >= start_date,
                    UserAuditLog.created_at <= end_date
                )
            )
            
            total_events = base_query.count()
            
            # Count by action type
            action_counts = db.query(
                UserAuditLog.action,
                func.count(UserAuditLog.id).label('count')
            ).filter(
                and_(
                    UserAuditLog.created_at >= start_date,
                    UserAuditLog.created_at <= end_date
                )
            ).group_by(UserAuditLog.action).all()
            
            # Count security events
            security_events = base_query.filter(
                UserAuditLog.action.in_([
                    AuditAction.LOGIN_FAILED.value,
                    AuditAction.PERMISSION_DENIED.value,
                    AuditAction.SECURITY_VIOLATION.value
                ])
            ).count()
            
            # Most active users
            active_users = db.query(
                UserAuditLog.user_id,
                func.count(UserAuditLog.id).label('activity_count')
            ).filter(
                and_(
                    UserAuditLog.created_at >= start_date,
                    UserAuditLog.created_at <= end_date,
                    UserAuditLog.user_id.isnot(None)
                )
            ).group_by(UserAuditLog.user_id).order_by(
                desc('activity_count')
            ).limit(10).all()
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                },
                "total_events": total_events,
                "security_events": security_events,
                "action_breakdown": {action: count for action, count in action_counts},
                "most_active_users": [
                    {"user_id": user_id, "activity_count": count}
                    for user_id, count in active_users
                ]
            }


# Global audit service instance
audit_service = AuditService()
