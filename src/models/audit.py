"""
AI Enablement Platform - Enhanced Audit Models for SOC2 Compliance

Comprehensive audit logging for security, compliance, and monitoring.
Includes data access tracking and RLS violation logging.
"""

from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from .database import Base


class AuditAction(str, Enum):
    """Standard audit action types for consistency."""
    
    # Authentication actions
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_COMPLETED = "password_reset_completed"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_UNLOCKED = "account_unlocked"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    MFA_VERIFIED = "mfa_verified"
    MFA_FAILED = "mfa_failed"
    
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
    USER_INVITED = "user_invited"
    USERS_LIST_ACCESSED = "users_list_accessed"
    
    # Role and permission management
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    
    # Data access (for compliance tracking)
    DATA_READ = "data_read"
    DATA_CREATED = "data_created"
    DATA_UPDATED = "data_updated"
    DATA_DELETED = "data_deleted"
    DATA_EXPORTED = "data_exported"
    DATA_SEARCHED = "data_searched"
    
    # Document management
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_VIEWED = "document_viewed"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_SHARED = "document_shared"
    
    # System administration
    SYSTEM_CONFIG_CHANGED = "system_config_changed"
    TENANT_CREATED = "tenant_created"
    TENANT_UPDATED = "tenant_updated"
    FEATURE_ALLOCATED = "feature_allocated"
    FEATURE_DEALLOCATED = "feature_deallocated"
    
    # Security events
    PERMISSION_DENIED = "permission_denied"
    RLS_VIOLATION = "rls_violation"
    CROSS_TENANT_ACCESS_ATTEMPT = "cross_tenant_access_attempt"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SECURITY_VIOLATION = "security_violation"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


class AuditSeverity(str, Enum):
    """Audit event severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataClassification(str, Enum):
    """Data classification levels for compliance."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    PII = "pii"  # Personally Identifiable Information
    SENSITIVE = "sensitive"
    RESTRICTED = "restricted"


class AuditOutcome(str, Enum):
    """Outcome of an audited action."""
    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    ERROR = "error"
    PARTIAL = "partial"


class DataAccessAuditLog(Base):
    """
    Comprehensive data access audit log for SOC2 compliance.
    
    Tracks WHO accessed WHAT data, WHEN, from WHERE, and the OUTCOME.
    This is the primary audit table for proving tenant isolation and
    tracking all data access for compliance reporting.
    """

    __tablename__ = 'data_access_audit_log'
    __table_args__ = (
        # Composite indexes for common query patterns
        Index('ix_data_access_customer_timestamp', 'customer_id', 'timestamp'),
        Index('ix_data_access_user_timestamp', 'user_id', 'timestamp'),
        Index('ix_data_access_resource_type', 'resource_type', 'timestamp'),
        Index('ix_data_access_action_outcome', 'action', 'outcome'),
        Index('ix_data_access_severity', 'severity', 'timestamp'),
        {'extend_existing': True}
    )
    
    # Primary key - using BigInteger for high volume
    id = Column(BigInteger, primary_key=True, index=True)
    
    # Timestamp - immutable, set by database
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # WHO - User context
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)  # Tenant context - CRITICAL for multi-tenant
    session_id = Column(String(255), nullable=True)
    
    # Request context
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True, index=True)  # For request correlation
    
    # WHAT - Action details
    action = Column(String(50), nullable=False, index=True)  # SELECT, INSERT, UPDATE, DELETE, EXPORT
    resource_type = Column(String(100), nullable=False, index=True)  # Table/entity name
    resource_id = Column(String(255), nullable=True)  # Primary key of accessed resource
    resource_ids = Column(ARRAY(String), nullable=True)  # For bulk operations
    
    # API context
    api_endpoint = Column(String(255), nullable=True)
    api_method = Column(String(10), nullable=True)  # GET, POST, PUT, DELETE
    
    # Data details
    records_affected = Column(Integer, nullable=True)
    data_classification = Column(String(50), nullable=True)  # PII, sensitive, public
    fields_accessed = Column(ARRAY(String), nullable=True)  # Which columns were accessed
    
    # Query context (hashed for pattern analysis, not storing raw queries)
    query_hash = Column(String(64), nullable=True)  # SHA256 of query for detecting unusual patterns
    query_params_hash = Column(String(64), nullable=True)  # Hash of parameters
    
    # OUTCOME
    outcome = Column(String(20), nullable=False, default='success')  # success, denied, error
    denial_reason = Column(String(255), nullable=True)  # Why access was denied
    error_message = Column(Text, nullable=True)  # Error details if failed
    
    # Severity and classification
    severity = Column(String(20), nullable=False, default='low')
    
    # Performance tracking
    duration_ms = Column(Integer, nullable=True)  # How long the operation took
    
    # Additional context as JSON
    additional_context = Column(JSONB, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])


class RLSViolationLog(Base):
    """
    Log of Row Level Security policy violations.
    
    Critical for proving tenant isolation is working and detecting
    potential security issues or bugs in the application layer.
    """

    __tablename__ = 'rls_violation_log'
    __table_args__ = (
        Index('ix_rls_violation_customer_timestamp', 'customer_id', 'timestamp'),
        Index('ix_rls_violation_target_customer', 'target_customer_id', 'timestamp'),
        {'extend_existing': True}
    )
    
    id = Column(BigInteger, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # WHO attempted the access
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    customer_id = Column(String(100), nullable=False, index=True)  # User's tenant
    
    # WHAT they tried to access
    target_customer_id = Column(String(100), nullable=False, index=True)  # Target tenant they tried to access
    table_name = Column(String(100), nullable=False)
    operation = Column(String(20), nullable=False)  # SELECT, INSERT, UPDATE, DELETE
    
    # Request context
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True)
    api_endpoint = Column(String(255), nullable=True)
    
    # Query details (sanitized)
    query_hash = Column(String(64), nullable=True)
    
    # How it was blocked
    policy_name = Column(String(100), nullable=True)  # Which RLS policy blocked it
    blocked_by = Column(String(50), nullable=False, default='rls')  # 'rls', 'application', 'middleware'
    
    # Severity - cross-tenant access attempts are HIGH by default
    severity = Column(String(20), nullable=False, default='high')
    
    # Was this investigated/resolved
    investigated = Column(Boolean, default=False)
    investigated_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    investigated_at = Column(DateTime(timezone=True), nullable=True)
    investigation_notes = Column(Text, nullable=True)
    
    # Additional context
    additional_context = Column(JSONB, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    investigator = relationship("User", foreign_keys=[investigated_by])


class TenantActivitySummary(Base):
    """
    Daily/hourly aggregated tenant activity for compliance reporting.
    
    Pre-aggregated data makes compliance reports faster to generate
    and provides quick visibility into tenant activity patterns.
    """

    __tablename__ = 'tenant_activity_summary'
    __table_args__ = (
        Index('ix_tenant_activity_customer_period', 'customer_id', 'period_start'),
        {'extend_existing': True}
    )
    
    id = Column(BigInteger, primary_key=True, index=True)
    
    # Time period
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False)
    period_type = Column(String(20), nullable=False)  # 'hourly', 'daily', 'weekly', 'monthly'
    
    # Tenant
    customer_id = Column(String(100), nullable=False, index=True)
    
    # Activity counts
    total_requests = Column(Integer, default=0)
    total_reads = Column(Integer, default=0)
    total_writes = Column(Integer, default=0)
    total_deletes = Column(Integer, default=0)
    
    # User activity
    unique_users = Column(Integer, default=0)
    login_count = Column(Integer, default=0)
    failed_login_count = Column(Integer, default=0)
    
    # Security events
    permission_denied_count = Column(Integer, default=0)
    rls_violation_count = Column(Integer, default=0)
    
    # Data access by classification
    pii_access_count = Column(Integer, default=0)
    sensitive_data_access_count = Column(Integer, default=0)
    
    # Resource access counts (JSON for flexibility)
    resource_access_counts = Column(JSONB, nullable=True)  # {"documents": 150, "users": 45, ...}
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ComplianceReport(Base):
    """
    Generated compliance reports for SOC2 audits.
    
    Stores generated reports with metadata about what data was included
    and who requested/viewed them.
    """

    __tablename__ = 'compliance_reports'
    __table_args__ = ({'extend_existing': True},)
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Report metadata
    report_type = Column(String(50), nullable=False)  # 'user_access', 'data_access', 'security_events', 'tenant_activity'
    report_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Scope
    customer_id = Column(String(100), nullable=True)  # NULL for platform-wide reports
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    
    # Report parameters and filters
    parameters = Column(JSONB, nullable=True)
    
    # Report content (or path to stored file)
    report_data = Column(JSONB, nullable=True)
    file_path = Column(String(500), nullable=True)  # If stored as file
    
    # Generation metadata
    generated_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    generation_duration_ms = Column(Integer, nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default='pending')  # pending, generating, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Access tracking
    last_accessed_at = Column(DateTime(timezone=True), nullable=True)
    access_count = Column(Integer, default=0)
    
    # Relationships
    generator = relationship("User", foreign_keys=[generated_by])


# Data classification mapping for common resource types
RESOURCE_DATA_CLASSIFICATION = {
    # PII data
    'users': DataClassification.PII,
    'candidates': DataClassification.PII,
    'user_invites': DataClassification.PII,
    'reference_check_requests': DataClassification.PII,
    'candidate_references': DataClassification.PII,
    
    # Sensitive business data
    'analysis_configs': DataClassification.CONFIDENTIAL,
    'career_blueprints': DataClassification.CONFIDENTIAL,
    'company_dna_profiles': DataClassification.CONFIDENTIAL,
    'talent_feedback': DataClassification.CONFIDENTIAL,
    
    # Internal data
    'documents': DataClassification.INTERNAL,
    'email_templates': DataClassification.INTERNAL,
    'roles': DataClassification.INTERNAL,
    'permissions': DataClassification.INTERNAL,
    
    # Restricted (admin only)
    'platform_admins': DataClassification.RESTRICTED,
    'system_settings': DataClassification.RESTRICTED,
    'platform_features': DataClassification.RESTRICTED,
}


def get_data_classification(resource_type: str) -> DataClassification:
    """Get data classification for a resource type."""
    return RESOURCE_DATA_CLASSIFICATION.get(resource_type, DataClassification.INTERNAL)

