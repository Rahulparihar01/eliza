"""
AI Enablement Platform - Models Package

This module exports all database models and database utilities.
Import order is important for SQLAlchemy foreign key relationships.
"""

# Database core - import first
# Note: engine, SessionLocal, async_engine, and AsyncSessionLocal are NOT imported directly
# to avoid capturing their None values at import time. Access them via database.SessionLocal etc.
from . import database
from .database import (
    Base, 
    get_db, 
    get_async_session,
    init_database, 
    init_async_database,
    check_database_health, 
    check_database_health_sync
)

# Provide dynamic access to session factories that get set after initialization
def __getattr__(name):
    """
    Dynamically access database session factories and engines.
    This ensures we always get the current value, not a stale import-time snapshot.
    """
    if name in ('SessionLocal', 'AsyncSessionLocal', 'engine', 'async_engine'):
        return getattr(database, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Models - import in dependency order
from .customer import Customer, CustomerAIProvider
from .auth import User, UserSession, Role, Permission, UserAuditLog, PasswordHistory, TemporaryRoleAssignment
# TODO: UserAPIKey model needs to be created - temporarily commented out
# from .api_keys import UserAPIKey
from .document import Document, DocumentChunk, UploadBatch, DocumentStatus, ChunkingStrategy
from .connector import (
    ConnectorConfiguration,
    ConnectorSyncRun,
    IngestedData,
    ConnectorTelemetry,
    PDLPerson,
    TalentAnalysis,
    TalentAnalysisEvent,
    TalentAnalysisStatus,
    JobPosting,
    Applicant,
    ApplicantScore,
    BaselineEmployeeProfile,
    ConnectorType,
    SyncMode,
    SyncStatus,
    IngestionStatus,
    ConnectorTelemetryEventType
)
from .business_intelligence import (
    BIQuestion, BIEnrichedPrompt, BIAnalysisSession,
    BIAgentTelemetry, BIAnalysisResult,
    QuestionStatus, AgentStatus, TelemetryEventType,
    add_bi_relationships
)
from .email_tracking import (
    OutreachEmail,
    EmailOpen,
    EmailClick,
    EmailReply,
    EmailLink,
    EmailStatus,
    DeliveryStatus,
    SentVia
)
from .email_templates import (
    EmailTemplate,
    EmailTemplateSection,
    GeneratedEmail,
    PDLQueryCache,
    CustomerSettings,
    TemplateSectionType,
    TemplateCategory
)
from .candidate import (
    Candidate,
    CandidateAnalysisScore,
    CandidateScoreFeedback
)

# Talent Configuration models (Career Blueprints, Company DNA)
from .talent_config import (
    CareerBlueprint,
    CompanyDNAProfile
)

# Multi-Tenant Admin models
from .tenant_admin import (
    PlatformFeature,
    FeaturePermission,
    TenantFeatureAllocation,
    UserInvite,
    PlatformAdmin
)

# Reference Check Voice Agent models
from .reference_check import (
    ReferenceRequestStatus,
    ReferenceStatus,
    RelationshipType,
    QuestionType,
    QuestionPriority,
    CallStatus,
    CallType,
    ScheduledCallStatus,
    ReferenceCheckRequest,
    CandidateReference,
    ReferenceCallTemplate,
    ReferenceTemplateQuestion,
    ReferenceVoicePersona,
    ReferenceConsentTemplate,
    ReferenceScheduledCall,
    ReferenceCall,
    ReferenceCallTranscript,
    ReferenceQuestionResponse,
    ReferenceCallSummary,
    ReferenceCheckAuditLog,
    CustomerCallerId,
    CustomerCallSettings
)

# Enhanced Audit models for SOC2 compliance
from .audit import (
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

# Adoption Dashboard models
from .adoption import (
    AdoptionDataShare,
    AdoptionSyncConfig,
    AdoptionDailyMetrics,
    AdoptionSourceType,
    AdoptionShareLevel,
)

# RAG Evaluation models
from .rag_eval import (
    RAGEvalRun,
    RAGEvalResult,
    RAGEvalTelemetryEvent,
    EvalRunStatus,
    EvalVerdict,
)
from .eval_set import (
    EvalSet,
    EvalSetUsage,
    EvalSetType,
    EvalSetCategory,
)

# Agent Configuration (must be before GEPA which references it)
from .agent_configuration import AgentConfiguration

# GEPA Optimizer models
from .gepa_optimizer import (
    OptimizerJob,
    OptimizerJobStatus,
    CandidateVariant,
    VariantStatus,
    GEPAEvaluationResult,
    TraceArtifact,
    ParetoSnapshot,
    GEPATelemetryEvent,
    PromotedVariantHistory,
    MutationType,
    ComponentType,
    FeedbackType,
    FeedbackRating,
    GEPAHumanFeedback,
)

# Prompt Management models
from .prompt_template import (
    PromptTemplate,
    PromptChangeLog,
    DomainPromptConfig,
    DomainPromptFeedback,
    PromptType,
    PromptStatus,
)

# RAGFlow Domain models (RAG Chat Service)
from .ragflow_domain import (
    RAGFlowDomain,
    RAGFlowDocument,
    RAGFlowConversation,
    RAGFlowMessage,
    RAGFlowDomainStatus,
    RAGFlowDocumentStatus,
    RAGFlowParserType,
)

# Workspace models (extends RAGFlow with templates and knowledge bases)
from .workspace import (
    WorkspaceTemplate,
    KnowledgeBase,
    KnowledgeBasePermission,
    WorkspaceTemplateType,
    KnowledgeBaseStatus,
    KnowledgeBasePermissionType,
    KnowledgeBaseSourceType,
    KnowledgeBaseStorageBackend,
)

# Tenant Theme model (white-label customization)
from .tenant_theme import TenantTheme

# Tenant SSO models (legacy config + multi-provider/domain tables)
from .tenant_sso import TenantSSOConfig, TenantSSOProvider, TenantSSODomain
from .user_sso_identity import UserSSOIdentity

# Retrieval subsystem models (HubSpot search, data-source connections)
from .retrieval import UserDataSourceConnection, RetrievalRun

# Content Writer models
from .content_writer import (
    ContentWriterRun,
    ResearchPack,
    DraftArtifact,
    ContentWriterSkill,
    ContentFormat,
    SourceType,
    RunStatus as ContentWriterRunStatus,
    SkillType,
    IssueType,
    add_content_writer_relationships,
)

# Add BI relationships to existing models
add_bi_relationships()

# Add Content Writer relationships
add_content_writer_relationships()

# Export all models and utilities
__all__ = [
    # Database utilities
    "Base",
    "engine", 
    "SessionLocal",
    "async_engine",
    "AsyncSessionLocal", 
    "get_db",
    "get_async_session",
    "init_database",
    "init_async_database",
    "check_database_health",
    "check_database_health_sync",
    
    # Customer models
    "Customer",
    "CustomerAIProvider",
    
    # User models
    "User",
    "UserSession",
    "Role",
    "Permission",
    "UserAuditLog",
    "PasswordHistory",
    "TemporaryRoleAssignment",
    # "UserAPIKey",  # TODO: Uncomment when UserAPIKey model is created
    
    # Document models
    "Document",
    "DocumentChunk",
    "UploadBatch",
    "DocumentStatus",
    "ChunkingStrategy",
    
    # Connector models
    "ConnectorConfiguration",
    "ConnectorSyncRun",
    "IngestedData",
    "ConnectorTelemetry",
    "PDLPerson",
    "TalentAnalysis",
    "TalentAnalysisEvent",
    "TalentAnalysisStatus",
    "JobPosting",
    "Applicant",
    "ApplicantScore",
    "BaselineEmployeeProfile",
    "ConnectorType",
    "SyncMode",
    "SyncStatus",
    "IngestionStatus",
    "ConnectorTelemetryEventType",

    # Business Intelligence models
    "BIQuestion",
    "BIEnrichedPrompt",
    "BIAnalysisSession",
    "BIAgentTelemetry",
    "BIAnalysisResult",
    "QuestionStatus",
    "AgentStatus",
    "TelemetryEventType",
    
    # Email Tracking models
    "OutreachEmail",
    "EmailOpen",
    "EmailClick",
    "EmailReply",
    "EmailLink",
    "EmailStatus",
    "DeliveryStatus",
    "SentVia",
    
    # Email Templates models
    "EmailTemplate",
    "EmailTemplateSection",
    "GeneratedEmail",
    "PDLQueryCache",
    "CustomerSettings",
    "TemplateSectionType",
    "TemplateCategory",
    
    # Candidate models (new architecture)
    "Candidate",
    "CandidateAnalysisScore",
    
    # Talent Configuration models
    "CareerBlueprint",
    "CompanyDNAProfile",
    
    # Multi-Tenant Admin models
    "PlatformFeature",
    "FeaturePermission",
    "TenantFeatureAllocation",
    "UserInvite",
    "PlatformAdmin",
    
    # Reference Check Voice Agent models
    "ReferenceRequestStatus",
    "ReferenceStatus",
    "RelationshipType",
    "QuestionType",
    "QuestionPriority",
    "CallStatus",
    "CallType",
    "ScheduledCallStatus",
    "ReferenceCheckRequest",
    "CandidateReference",
    "ReferenceCallTemplate",
    "ReferenceTemplateQuestion",
    "ReferenceVoicePersona",
    "ReferenceConsentTemplate",
    "ReferenceScheduledCall",
    "ReferenceCall",
    "ReferenceCallTranscript",
    "ReferenceQuestionResponse",
    "ReferenceCallSummary",
    "ReferenceCheckAuditLog",
    "CustomerCallerId",
    "CustomerCallSettings",
    
    # Enhanced Audit models (SOC2 compliance)
    "DataAccessAuditLog",
    "RLSViolationLog",
    "TenantActivitySummary",
    "ComplianceReport",
    "AuditAction",
    "AuditSeverity",
    "AuditOutcome",
    "DataClassification",
    "get_data_classification",
    
    # Adoption Dashboard models
    "AdoptionDataShare",
    "AdoptionSyncConfig",
    "AdoptionDailyMetrics",
    "AdoptionSourceType",
    "AdoptionShareLevel",
    
    # RAG Evaluation models
    "RAGEvalRun",
    "RAGEvalResult",
    "RAGEvalTelemetryEvent",
    "EvalRunStatus",
    "EvalVerdict",
    "EvalSet",
    "EvalSetUsage",
    "EvalSetType",
    "EvalSetCategory",
    
    # Agent Configuration
    "AgentConfiguration",
    
    # GEPA Optimizer models
    "OptimizerJob",
    "OptimizerJobStatus",
    "CandidateVariant",
    "VariantStatus",
    "GEPAEvaluationResult",
    "TraceArtifact",
    "ParetoSnapshot",
    "GEPATelemetryEvent",
    "PromotedVariantHistory",
    "MutationType",
    "ComponentType",
    "FeedbackType",
    "FeedbackRating",
    "GEPAHumanFeedback",
    
    # Prompt Management models
    "PromptTemplate",
    "PromptChangeLog",
    "DomainPromptConfig",
    "DomainPromptFeedback",
    "PromptType",
    "PromptStatus",
    
    # RAGFlow Domain models (RAG Chat Service)
    "RAGFlowDomain",
    "RAGFlowDocument",
    "RAGFlowConversation",
    "RAGFlowMessage",
    "RAGFlowDomainStatus",
    "RAGFlowDocumentStatus",
    "RAGFlowParserType",
    
    # Workspace models (templates and knowledge bases)
    "WorkspaceTemplate",
    "KnowledgeBase",
    "KnowledgeBasePermission",
    "WorkspaceTemplateType",
    "KnowledgeBaseStatus",
    "KnowledgeBasePermissionType",
    "KnowledgeBaseSourceType",
    "KnowledgeBaseStorageBackend",
    
    # Tenant Theme model
    "TenantTheme",
    "TenantSSOConfig",
    "TenantSSOProvider",
    "TenantSSODomain",
    "UserSSOIdentity",
    
    # Retrieval models
    "UserDataSourceConnection",
    "RetrievalRun",

    # Content Writer models
    "ContentWriterRun",
    "ResearchPack",
    "DraftArtifact",
    "ContentWriterSkill",
    "ContentFormat",
    "SourceType",
    "ContentWriterRunStatus",
    "SkillType",
    "IssueType",
]
