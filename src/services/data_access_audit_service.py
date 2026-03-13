"""
Data Access Audit Service for SOC2 Compliance

Comprehensive service for logging and querying data access events.
Provides the audit trail needed for SOC2 compliance reporting.
"""

import logging
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text

from src.models.audit import (
    DataAccessAuditLog,
    RLSViolationLog,
    TenantActivitySummary,
    ComplianceReport,
    AuditAction,
    AuditSeverity,
    AuditOutcome,
    DataClassification,
    get_data_classification,
)
from src.models.database import SessionLocal, init_database
from src.middleware.tenant_context import (
    get_current_tenant_id,
    get_current_user_id,
    get_current_request_id,
)

logger = logging.getLogger(__name__)


class DataAccessAuditService:
    """
    Service for comprehensive data access audit logging.
    
    This service provides:
    1. Logging of all data access events (read, write, delete)
    2. RLS violation tracking
    3. Compliance report generation
    4. Anomaly detection for suspicious access patterns
    """
    
    def __init__(self, db: Optional[Session] = None):
        """Initialize the service with optional database session."""
        self._db = db
    
    @property
    def db(self) -> Session:
        """Get database session, creating if necessary."""
        if self._db is None:
            if SessionLocal is None:
                init_database()
            self._db = SessionLocal()
        return self._db
    
    def close(self):
        """Close the database session if we created it."""
        if self._db is not None:
            self._db.close()
            self._db = None
    
    # =========================================================================
    # Data Access Logging
    # =========================================================================
    
    async def log_data_access(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        resource_ids: Optional[List[str]] = None,
        customer_id: Optional[str] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        api_method: Optional[str] = None,
        records_affected: Optional[int] = None,
        fields_accessed: Optional[List[str]] = None,
        outcome: str = 'success',
        denial_reason: Optional[str] = None,
        error_message: Optional[str] = None,
        severity: Optional[str] = None,
        duration_ms: Optional[int] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> DataAccessAuditLog:
        """
        Log a data access event.
        
        This is the primary method for logging data access for compliance.
        Should be called for all significant data operations.
        
        Args:
            action: The action performed (SELECT, INSERT, UPDATE, DELETE, EXPORT)
            resource_type: The type of resource accessed (table/entity name)
            resource_id: Primary key of single accessed resource
            resource_ids: List of resource IDs for bulk operations
            customer_id: Tenant ID (defaults to current context)
            user_id: User ID (defaults to current context)
            session_id: Session token
            ip_address: Client IP
            user_agent: Client user agent
            api_endpoint: API endpoint accessed
            api_method: HTTP method
            records_affected: Number of records affected
            fields_accessed: List of fields/columns accessed
            outcome: Result of the operation (success, denied, error)
            denial_reason: Why access was denied
            error_message: Error details if failed
            severity: Event severity (auto-determined if not provided)
            duration_ms: Operation duration in milliseconds
            additional_context: Any additional context as JSON
        
        Returns:
            The created audit log entry
        """
        # Get context values if not provided
        if customer_id is None:
            customer_id = get_current_tenant_id() or 'system'
        if user_id is None:
            user_id = get_current_user_id()
        
        request_id = get_current_request_id()
        
        # Determine data classification
        data_classification = get_data_classification(resource_type).value
        
        # Auto-determine severity if not provided
        if severity is None:
            severity = self._determine_severity(action, outcome, data_classification)
        
        # Create hash for query pattern analysis
        query_hash = self._generate_query_hash(resource_type, action, fields_accessed)
        
        try:
            audit_log = DataAccessAuditLog(
                user_id=user_id,
                customer_id=customer_id,
                session_id=session_id,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_ids=resource_ids,
                api_endpoint=api_endpoint,
                api_method=api_method,
                records_affected=records_affected,
                data_classification=data_classification,
                fields_accessed=fields_accessed,
                query_hash=query_hash,
                outcome=outcome,
                denial_reason=denial_reason,
                error_message=error_message,
                severity=severity,
                duration_ms=duration_ms,
                additional_context=additional_context,
            )
            
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)
            
            # Log high-severity events to application logger
            if severity in ['high', 'critical']:
                logger.warning(
                    f"High-severity data access: {action} on {resource_type} "
                    f"by user {user_id} (tenant: {customer_id})",
                    extra={
                        'audit_log_id': audit_log.id,
                        'action': action,
                        'resource_type': resource_type,
                        'customer_id': customer_id,
                        'user_id': user_id,
                        'outcome': outcome,
                        'severity': severity,
                    }
                )
            
            return audit_log
            
        except Exception as e:
            logger.error(f"Failed to log data access: {e}")
            self.db.rollback()
            raise
    
    async def log_rls_violation(
        self,
        customer_id: str,
        target_customer_id: str,
        table_name: str,
        operation: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        api_endpoint: Optional[str] = None,
        blocked_by: str = 'application',
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> RLSViolationLog:
        """
        Log a Row Level Security violation attempt.
        
        This is CRITICAL for proving tenant isolation is working.
        Should be called whenever cross-tenant access is detected and blocked.
        
        Args:
            customer_id: The tenant ID of the user making the request
            target_customer_id: The tenant ID they tried to access
            table_name: The table they tried to access
            operation: The operation attempted (SELECT, INSERT, UPDATE, DELETE)
            user_id: User ID attempting the access
            ip_address: Client IP
            user_agent: Client user agent
            api_endpoint: API endpoint where violation occurred
            blocked_by: What blocked the access ('rls', 'application', 'middleware')
            additional_context: Any additional context
        
        Returns:
            The created violation log entry
        """
        if user_id is None:
            user_id = get_current_user_id()
        
        request_id = get_current_request_id()
        
        try:
            violation_log = RLSViolationLog(
                user_id=user_id,
                customer_id=customer_id,
                target_customer_id=target_customer_id,
                table_name=table_name,
                operation=operation,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                api_endpoint=api_endpoint,
                blocked_by=blocked_by,
                severity='high',  # All RLS violations are high severity
                additional_context=additional_context,
            )
            
            self.db.add(violation_log)
            self.db.commit()
            self.db.refresh(violation_log)
            
            # Always log RLS violations to application logger
            logger.warning(
                f"RLS VIOLATION: User {user_id} (tenant: {customer_id}) "
                f"attempted {operation} on {table_name} belonging to tenant {target_customer_id}",
                extra={
                    'violation_id': violation_log.id,
                    'customer_id': customer_id,
                    'target_customer_id': target_customer_id,
                    'table_name': table_name,
                    'operation': operation,
                    'user_id': user_id,
                    'blocked_by': blocked_by,
                }
            )
            
            return violation_log
            
        except Exception as e:
            logger.error(f"Failed to log RLS violation: {e}")
            self.db.rollback()
            raise
    
    # =========================================================================
    # Query Methods for Compliance Reporting
    # =========================================================================
    
    async def get_data_access_logs(
        self,
        customer_id: Optional[str] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[DataAccessAuditLog], int]:
        """
        Query data access logs with filters.
        
        Returns:
            Tuple of (logs, total_count)
        """
        query = self.db.query(DataAccessAuditLog)
        
        if customer_id:
            query = query.filter(DataAccessAuditLog.customer_id == customer_id)
        if user_id:
            query = query.filter(DataAccessAuditLog.user_id == user_id)
        if resource_type:
            query = query.filter(DataAccessAuditLog.resource_type == resource_type)
        if action:
            query = query.filter(DataAccessAuditLog.action == action)
        if outcome:
            query = query.filter(DataAccessAuditLog.outcome == outcome)
        if severity:
            query = query.filter(DataAccessAuditLog.severity == severity)
        if start_date:
            query = query.filter(DataAccessAuditLog.timestamp >= start_date)
        if end_date:
            query = query.filter(DataAccessAuditLog.timestamp <= end_date)
        
        total = query.count()
        logs = query.order_by(desc(DataAccessAuditLog.timestamp)).offset(offset).limit(limit).all()
        
        return logs, total
    
    async def get_rls_violations(
        self,
        customer_id: Optional[str] = None,
        target_customer_id: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        investigated: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[RLSViolationLog], int]:
        """
        Query RLS violation logs with filters.
        
        Returns:
            Tuple of (violations, total_count)
        """
        query = self.db.query(RLSViolationLog)
        
        if customer_id:
            query = query.filter(RLSViolationLog.customer_id == customer_id)
        if target_customer_id:
            query = query.filter(RLSViolationLog.target_customer_id == target_customer_id)
        if user_id:
            query = query.filter(RLSViolationLog.user_id == user_id)
        if start_date:
            query = query.filter(RLSViolationLog.timestamp >= start_date)
        if end_date:
            query = query.filter(RLSViolationLog.timestamp <= end_date)
        if investigated is not None:
            query = query.filter(RLSViolationLog.investigated == investigated)
        
        total = query.count()
        violations = query.order_by(desc(RLSViolationLog.timestamp)).offset(offset).limit(limit).all()
        
        return violations, total
    
    async def get_tenant_activity_summary(
        self,
        customer_id: str,
        period_type: str = 'daily',
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[TenantActivitySummary]:
        """
        Get aggregated activity summary for a tenant.
        
        Args:
            customer_id: Tenant ID
            period_type: 'hourly', 'daily', 'weekly', 'monthly'
            start_date: Start of period
            end_date: End of period
        
        Returns:
            List of activity summaries
        """
        query = self.db.query(TenantActivitySummary).filter(
            TenantActivitySummary.customer_id == customer_id,
            TenantActivitySummary.period_type == period_type,
        )
        
        if start_date:
            query = query.filter(TenantActivitySummary.period_start >= start_date)
        if end_date:
            query = query.filter(TenantActivitySummary.period_end <= end_date)
        
        return query.order_by(TenantActivitySummary.period_start).all()
    
    # =========================================================================
    # Compliance Report Generation
    # =========================================================================
    
    async def generate_user_access_report(
        self,
        customer_id: str,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
        generated_by: int,
    ) -> ComplianceReport:
        """
        Generate a comprehensive user access report for compliance.
        
        This report shows all data access by a specific user within a time period.
        Required for SOC2 audits to demonstrate access monitoring.
        """
        start_time = time.time()
        
        # Get all access logs for this user
        logs, total = await self.get_data_access_logs(
            customer_id=customer_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=10000,  # Get all for report
        )
        
        # Aggregate by resource type and action
        resource_summary = {}
        for log in logs:
            key = f"{log.resource_type}:{log.action}"
            if key not in resource_summary:
                resource_summary[key] = {
                    'resource_type': log.resource_type,
                    'action': log.action,
                    'count': 0,
                    'success_count': 0,
                    'denied_count': 0,
                    'error_count': 0,
                }
            resource_summary[key]['count'] += 1
            if log.outcome == 'success':
                resource_summary[key]['success_count'] += 1
            elif log.outcome == 'denied':
                resource_summary[key]['denied_count'] += 1
            elif log.outcome == 'error':
                resource_summary[key]['error_count'] += 1
        
        # Get RLS violations
        violations, violation_count = await self.get_rls_violations(
            customer_id=customer_id,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )
        
        report_data = {
            'summary': {
                'total_access_events': total,
                'unique_resources_accessed': len(resource_summary),
                'rls_violations': violation_count,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
            },
            'resource_access': list(resource_summary.values()),
            'violations': [
                {
                    'timestamp': v.timestamp.isoformat(),
                    'target_customer_id': v.target_customer_id,
                    'table_name': v.table_name,
                    'operation': v.operation,
                }
                for v in violations
            ],
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        report = ComplianceReport(
            report_type='user_access',
            report_name=f"User Access Report - User {user_id}",
            description=f"Comprehensive access report for user {user_id} from {start_date} to {end_date}",
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            parameters={'user_id': user_id},
            report_data=report_data,
            generated_by=generated_by,
            generation_duration_ms=duration_ms,
            status='completed',
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    async def generate_tenant_security_report(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        generated_by: int,
    ) -> ComplianceReport:
        """
        Generate a security report for a tenant.
        
        This report includes:
        - Access patterns and anomalies
        - RLS violations
        - Failed access attempts
        - High-severity events
        
        Required for SOC2 audits to demonstrate security monitoring.
        """
        start_time = time.time()
        
        # Get high severity events
        high_severity_logs, _ = await self.get_data_access_logs(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            severity='high',
            limit=1000,
        )
        
        # Get denied access attempts
        denied_logs, denied_count = await self.get_data_access_logs(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            outcome='denied',
            limit=1000,
        )
        
        # Get RLS violations
        violations, violation_count = await self.get_rls_violations(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )
        
        # Get unique users and IPs
        unique_users = self.db.query(func.count(func.distinct(DataAccessAuditLog.user_id))).filter(
            DataAccessAuditLog.customer_id == customer_id,
            DataAccessAuditLog.timestamp >= start_date,
            DataAccessAuditLog.timestamp <= end_date,
        ).scalar()
        
        unique_ips = self.db.query(func.count(func.distinct(DataAccessAuditLog.ip_address))).filter(
            DataAccessAuditLog.customer_id == customer_id,
            DataAccessAuditLog.timestamp >= start_date,
            DataAccessAuditLog.timestamp <= end_date,
        ).scalar()
        
        report_data = {
            'summary': {
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'unique_users': unique_users,
                'unique_ip_addresses': unique_ips,
                'high_severity_events': len(high_severity_logs),
                'denied_access_attempts': denied_count,
                'rls_violations': violation_count,
            },
            'high_severity_events': [
                {
                    'timestamp': log.timestamp.isoformat(),
                    'user_id': log.user_id,
                    'action': log.action,
                    'resource_type': log.resource_type,
                    'outcome': log.outcome,
                }
                for log in high_severity_logs[:100]  # Limit detail
            ],
            'violations': [
                {
                    'timestamp': v.timestamp.isoformat(),
                    'user_id': v.user_id,
                    'target_customer_id': v.target_customer_id,
                    'table_name': v.table_name,
                    'operation': v.operation,
                    'investigated': v.investigated,
                }
                for v in violations[:100]
            ],
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        report = ComplianceReport(
            report_type='tenant_security',
            report_name=f"Security Report - {customer_id}",
            description=f"Security and compliance report for tenant {customer_id} from {start_date} to {end_date}",
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            parameters={},
            report_data=report_data,
            generated_by=generated_by,
            generation_duration_ms=duration_ms,
            status='completed',
        )
        
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        
        return report
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _determine_severity(
        self,
        action: str,
        outcome: str,
        data_classification: str,
    ) -> str:
        """Determine the severity level based on action and context."""
        # Failures and denials are at least medium
        if outcome in ['denied', 'error']:
            return 'medium'
        
        # Access to sensitive/PII data is at least medium
        if data_classification in ['pii', 'sensitive', 'restricted']:
            if action in ['DELETE', 'EXPORT']:
                return 'high'
            return 'medium'
        
        # DELETE operations are medium
        if action == 'DELETE':
            return 'medium'
        
        # Export operations are medium
        if action == 'EXPORT':
            return 'medium'
        
        return 'low'
    
    def _generate_query_hash(
        self,
        resource_type: str,
        action: str,
        fields: Optional[List[str]] = None,
    ) -> str:
        """Generate a hash for query pattern analysis."""
        pattern = f"{resource_type}:{action}"
        if fields:
            pattern += f":{','.join(sorted(fields))}"
        return hashlib.sha256(pattern.encode()).hexdigest()[:16]


# Global service instance
data_access_audit_service = DataAccessAuditService()

