"""
Data Connector Models

Supports multiple connector instances using the same connector type.
Each instance has a static query configured via UI.

Example:
- Instance 1: PDL connector for "FAANG Engineers" (query: {company: FAANG, role: engineer})
- Instance 2: PDL connector for "Healthcare Execs" (query: {industry: healthcare, title: exec})
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum

from src.models.database import BaseModel, Base


# Enums for connector states
class ConnectorType(str, Enum):
    """Connector types."""
    PEOPLE_DATA_LABS = "people_data_labs"
    GREENHOUSE = "greenhouse"
    HUBSPOT = "hubspot"
    FATHOM = "fathom"
    LEVER = "lever"
    WORKDAY = "workday"
    BAMBOOHR = "bamboohr"
    FILESYSTEM = "filesystem"
    # Add other connector types as needed


class SyncMode(str, Enum):
    """Sync modes."""
    FULL_REFRESH = "full_refresh"
    INCREMENTAL = "incremental"


class SyncStatus(str, Enum):
    """Sync run statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IngestionStatus(str, Enum):
    """Ingestion data statuses."""
    PENDING = "pending"
    INGESTED = "ingested"
    TRANSFORMED = "transformed"
    ENRICHED = "enriched"
    FAILED = "failed"


class ConnectorTelemetryEventType(str, Enum):
    """Telemetry event types."""
    SYNC_STARTED = "sync_started"
    SYNC_PROGRESS = "sync_progress"
    SYNC_COMPLETED = "sync_completed"
    SYNC_FAILED = "sync_failed"
    RATE_LIMIT_HIT = "rate_limit_hit"
    SCHEMA_DRIFT_DETECTED = "schema_drift_detected"
    COST_THRESHOLD_WARNING = "cost_threshold_warning"
    RECORD_INGESTED = "record_ingested"
    RECORD_TRANSFORMED = "record_transformed"
    RECORD_DEDUPLICATED = "record_deduplicated"
    RECORD_SKIPPED = "record_skipped"


class ConnectorConfiguration(BaseModel):
    """
    Connector configuration - one row per connector instance.
    
    Multiple instances can use same connector_type with different queries.
    Supports query versioning for tracking changes over time.
    """
    __tablename__ = "connector_configurations"
    
    # Identity
    connector_id = Column(String(100), unique=True, nullable=False, index=True)
    
    # Connector type (which code to use)
    connector_type = Column(String(50), nullable=False, index=True)  # "people_data_labs"
    
    # User-friendly identification
    connector_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)  # ["recruiting", "engineering"]
    
    # Multi-tenant
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    
    # Credentials
    use_shared_credentials = Column(Boolean, default=True)
    credentials_encrypted = Column(Text, nullable=True)  # Per-connector credentials if needed
    
    # Configuration (including static query)
    sync_config = Column(JSON, nullable=False, default={})
    sync_config_version = Column(Integer, default=1)
    sync_config_history = Column(JSON, nullable=True)  # Track query changes
    
    # Cost controls
    max_records_per_sync = Column(Integer, nullable=True)
    estimated_cost_per_sync = Column(Float, nullable=True)
    total_cost_to_date = Column(Float, default=0.0)
    
    # Scheduling
    sync_schedule = Column(String(100), nullable=True)  # Cron expression
    sync_mode = Column(String(20), default="incremental")  # "full" or "incremental"
    
    # Status
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_healthy = Column(Boolean, default=True, nullable=False)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    health_check_message = Column(Text, nullable=True)
    
    # Audit
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    sync_runs = relationship("ConnectorSyncRun", back_populates="connector", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_connector_customer_type', 'customer_id', 'connector_type'),
        Index('ix_connector_enabled', 'is_enabled', 'customer_id'),
        {'extend_existing': True}
    )
    
    def update_query(self, new_query: Dict[str, Any], updated_by_user_id: int):
        """
        Update search query and maintain version history.
        
        Args:
            new_query: New query configuration
            updated_by_user_id: User ID making the change
        """
        if not self.sync_config_history:
            self.sync_config_history = []
        
        self.sync_config_history.append({
            "version": self.sync_config_version,
            "query": self.sync_config.get("search_query"),
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": updated_by_user_id
        })
        
        self.sync_config["search_query"] = new_query
        self.sync_config_version += 1


class ConnectorSyncRun(BaseModel):
    """
    Tracks individual connector sync executions.
    
    Each sync creates one row. Includes telemetry and performance metrics.
    """
    __tablename__ = "connector_sync_runs"
    
    # Identity
    sync_id = Column(String(100), unique=True, nullable=False, index=True)
    connector_id = Column(Integer, ForeignKey("connector_configurations.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    
    # Execution details
    celery_task_id = Column(String(100), nullable=True, index=True)
    sync_mode = Column(String(20), nullable=False)  # "full" or "incremental"
    triggered_by = Column(String(50), nullable=False)  # "scheduled", "manual", "api"
    
    # Status
    status = Column(String(50), default="pending", index=True)  # pending, running, completed, failed, cancelled
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Results
    records_extracted = Column(Integer, default=0)
    records_loaded = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)  # Duplicates
    records_failed = Column(Integer, default=0)
    
    # State management (for incremental syncs)
    checkpoint_before = Column(JSON, nullable=True)  # State before sync
    checkpoint_after = Column(JSON, nullable=True)   # State after sync
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Performance metrics
    duration_seconds = Column(Integer, nullable=True)
    api_calls_made = Column(Integer, default=0)
    bytes_transferred = Column(Integer, default=0)
    
    # Cost tracking
    cost_incurred = Column(Float, default=0.0)
    
    # Relationships
    connector = relationship("ConnectorConfiguration", back_populates="sync_runs")
    telemetry_events = relationship("ConnectorTelemetry", back_populates="sync_run", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('ix_sync_run_customer_status', 'customer_id', 'status'),
        Index('ix_sync_run_connector_created', 'connector_id', 'created_at'),
        Index('ix_sync_run_dates', 'started_at', 'completed_at'),
        {'extend_existing': True}
    )


class IngestedData(BaseModel):
    """
    Staging table for raw ingested data before transformation.
    
    All data lands here first as JSON, then gets transformed to typed tables.
    """
    __tablename__ = "ingested_data"
    
    # Identification
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    connector_id = Column(Integer, ForeignKey("connector_configurations.id", ondelete="CASCADE"), nullable=False)
    sync_id = Column(String(100), ForeignKey("connector_sync_runs.sync_id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Source identification
    source_record_id = Column(String(255), nullable=True, index=True)  # External ID (e.g., PDL person ID)
    source_record_type = Column(String(50), nullable=True)  # "person", "company", etc.
    
    # Data attribution
    company_dataset = Column(String(255), nullable=True, index=True)
    
    # Raw data
    raw_data = Column(JSON, nullable=False)
    
    # Processing status
    status = Column(String(50), default="pending", index=True)  # pending, transformed, failed
    transformed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Reference to transformed record
    transformed_record_type = Column(String(50), nullable=True)  # "pdl_person"
    transformed_record_id = Column(Integer, nullable=True)
    
    # Metadata (renamed to avoid SQLAlchemy reserved word)
    ingestion_metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('ix_ingested_customer_company', 'customer_id', 'company_dataset'),
        Index('ix_ingested_status', 'customer_id', 'status'),
        Index('ix_ingested_sync_status', 'sync_id', 'status'),
        Index('ix_ingested_source_id', 'customer_id', 'source_record_id'),
        {'extend_existing': True}
    )


class ConnectorTelemetry(BaseModel):
    """
    Real-time telemetry events for connector syncs.
    
    Similar to BI telemetry - used for streaming progress to frontend.
    
    Note: This is an append-only event log. Events are never updated,
    so we exclude the updated_at column that BaseModel adds.
    """
    __tablename__ = "connector_telemetry"
    
    # Exclude updated_at since telemetry events are immutable
    __mapper_args__ = {
        'exclude_properties': ['updated_at']
    }
    
    # Identification
    sync_id = Column(String(100), ForeignKey("connector_sync_runs.sync_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(100), nullable=False)
    
    # Event details
    event_type = Column(String(50), nullable=False)  # sync_started, progress, completed, failed
    event_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Progress tracking
    progress_percentage = Column(Float, nullable=True)
    current_stage = Column(String(100), nullable=True)  # "extracting", "transforming", "loading"
    
    # Metrics
    records_processed = Column(Integer, default=0)
    api_calls_made = Column(Integer, default=0)
    cost_so_far = Column(Float, default=0.0)
    
    # User-facing message
    user_message = Column(Text, nullable=True)
    
    # Technical details (renamed to avoid SQLAlchemy reserved word)
    telemetry_metadata = Column(JSON, nullable=True)
    
    # Relationships
    sync_run = relationship("ConnectorSyncRun", back_populates="telemetry_events")
    
    __table_args__ = (
        Index('ix_telemetry_sync_timestamp', 'sync_id', 'event_timestamp'),
        {'extend_existing': True}
    )


class PDLPerson(BaseModel):
    """
    Normalized person record from People Data Labs.
    
    Deduplication: UPSERT by pdl_id + customer_id (unique index).
    Tracks how many times we've seen each person for debugging.
    """
    __tablename__ = "pdl_persons"
    
    # Identity
    pdl_id = Column(String(100), nullable=False, index=True)  # PDL's person ID
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    
    # Basic info
    full_name = Column(String(255), nullable=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    middle_name = Column(String(100), nullable=True)
    
    # Current employment
    job_title = Column(String(255), nullable=True, index=True)
    job_title_role = Column(String(100), nullable=True, index=True)
    job_title_sub_role = Column(String(100), nullable=True)
    job_title_levels = Column(JSON, nullable=True)  # ["senior", "manager"]
    
    job_company_name = Column(String(255), nullable=True, index=True)
    job_company_id = Column(String(100), nullable=True)
    job_company_size = Column(String(50), nullable=True)
    job_company_industry = Column(String(100), nullable=True)
    job_company_location_name = Column(String(255), nullable=True)
    job_start_date = Column(String(50), nullable=True)  # YYYY-MM format
    
    # Contact info
    primary_email = Column(String(255), nullable=True, index=True)
    emails = Column(JSON, nullable=True)  # All emails
    primary_phone = Column(String(50), nullable=True)
    phone_numbers = Column(JSON, nullable=True)  # All phones
    
    # Social profiles
    linkedin_url = Column(String(500), nullable=True, index=True)
    linkedin_username = Column(String(255), nullable=True)
    twitter_url = Column(String(500), nullable=True)
    github_url = Column(String(500), nullable=True)
    
    # Location
    location_name = Column(String(255), nullable=True)
    location_locality = Column(String(100), nullable=True)
    location_metro = Column(String(100), nullable=True)
    location_region = Column(String(100), nullable=True)
    location_country = Column(String(100), nullable=True, index=True)
    location_continent = Column(String(50), nullable=True)
    
    # Skills & Experience
    skills = Column(JSON, nullable=True)  # Array of skill names
    inferred_years_experience = Column(Integer, nullable=True)
    
    # Education
    education_history = Column(JSON, nullable=True)
    
    # Work history
    work_history = Column(JSON, nullable=True)  # Array of previous jobs
    
    # PDL metadata
    pdl_likelihood = Column(Integer, nullable=True)  # 1-10 confidence score
    pdl_last_updated = Column(DateTime(timezone=True), nullable=True)
    
    # Tracking (for deduplication debugging)
    first_seen_sync_id = Column(String(100), nullable=True)
    last_updated_sync_id = Column(String(100), nullable=True)
    sync_count = Column(Integer, default=1)  # How many times we've seen this person
    
    # Source references
    ingested_data_id = Column(Integer, ForeignKey("ingested_data.id"), nullable=True)
    
    # Full record (for reference)
    raw_data = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('ix_pdl_person_unique', 'pdl_id', 'customer_id', unique=True),
        Index('ix_pdl_person_name', 'first_name', 'last_name'),
        Index('ix_pdl_person_company_role', 'job_company_name', 'job_title_role'),
        Index('ix_pdl_person_location', 'location_country', 'location_region'),
        Index('ix_pdl_person_email', 'primary_email'),
        {'extend_existing': True}
    )


class TalentAnalysisStatus(str, Enum):
    """Talent analysis statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TalentAnalysis(BaseModel):
    """
    Stores AI-powered talent analysis results.
    
    Captures the full workflow:
    1. Job description + ideal candidate description input
    2. AI-generated ideal persona
    3. Ranked candidate matches
    4. Market insights and recommendations
    """
    __tablename__ = "talent_analyses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(100), unique=True, nullable=False, index=True)  # UUID
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Who requested the analysis
    
    # Input
    job_description = Column(Text, nullable=True)  # Raw job description text
    ideal_candidate_description = Column(Text, nullable=True)  # Natural language ideal candidate description
    manual_persona = Column(JSON, nullable=True)  # Manually defined persona (alternative to JD)
    
    # Status
    status = Column(String(50), nullable=False, default=TalentAnalysisStatus.PENDING.value)
    error_message = Column(Text, nullable=True)
    
    # Results (from CrewAI agents)
    ideal_persona = Column(JSON, nullable=True)  # Agent 1 output: Refined persona
    candidates = Column(JSON, nullable=True)  # Agent 2 output: Ranked candidates with fit scores
    insights_report = Column(JSON, nullable=True)  # Agent 3 output: Market analysis, recommendations
    
    # Metadata
    candidate_count = Column(Integer, default=0)
    top_candidate_fit_score = Column(Float, nullable=True)
    average_fit_score = Column(Float, nullable=True)
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Note: updated_at inherited from BaseModel but doesn't exist in DB - explicitly exclude it
    updated_at = None  # Override BaseModel's updated_at
    
    # Celery task ID
    task_id = Column(String(100), nullable=True, index=True)
    
    __table_args__ = (
        Index('ix_talent_analysis_customer_status', 'customer_id', 'status'),
        Index('ix_talent_analysis_created', 'created_at'),
        {'extend_existing': True}
    )


class TalentAnalysisEvent(Base):
    """
    Stores real-time events from talent analysis for SSE streaming.
    
    Tracks progress through the 3-agent workflow:
    - Agent 1: Job Analyst
    - Agent 2: Talent Scout
    - Agent 3: Insights Synthesizer
    """
    __tablename__ = "talent_analysis_events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(100), ForeignKey("talent_analyses.analysis_id"), nullable=False, index=True)
    
    # Event details
    event_type = Column(String(50), nullable=False)  # analysis_started, agent_1_started, agent_2_progress, etc.
    agent_name = Column(String(100), nullable=True)  # Job Analyst, Talent Scout, Insights Synthesizer
    message = Column(Text, nullable=True)  # Human-readable progress message
    progress_percentage = Column(Integer, nullable=True)  # 0-100
    
    # Data payload (optional)
    data = Column(JSON, nullable=True)  # Event-specific data
    
    # Timing
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    __table_args__ = (
        Index('ix_talent_event_analysis_timestamp', 'analysis_id', 'timestamp'),
        {'extend_existing': True}
    )


class JobPosting(BaseModel):
    """
    Job postings from HR/ATS platforms (Greenhouse, Lever, Workday, BambooHR).
    
    Stores job information synced from external HR platforms.
    """
    __tablename__ = "job_postings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(255), ForeignKey("customers.customer_id"), nullable=False, index=True)
    connector_id = Column(Integer, ForeignKey("connector_configurations.id"), nullable=False, index=True)
    
    # External system identification
    external_job_id = Column(String(255), nullable=False, index=True)  # Job ID in HR platform
    
    # Job details
    title = Column(String(500), nullable=False)
    department = Column(String(255), nullable=True)
    office = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    requirements = Column(JSON, nullable=True)  # Structured requirements
    
    # Status
    status = Column(String(50), nullable=False, default='open')  # open, closed, draft
    
    # External link
    remote_url = Column(String(1000), nullable=True)  # Link to job in HR platform
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)
    
    __table_args__ = (
        Index('ix_job_postings_customer_connector', 'customer_id', 'connector_id'),
        Index('ix_job_postings_status', 'status'),
        {'extend_existing': True}
    )


class Applicant(BaseModel):
    """
    Applicants from HR/ATS platforms.
    
    Stores applicant information and their parsed resumes.
    Links to JobPosting and can be scored against employee baseline.
    """
    __tablename__ = "applicants"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(255), ForeignKey("customers.customer_id"), nullable=False, index=True)
    job_posting_id = Column(Integer, ForeignKey("job_postings.id"), nullable=False, index=True)
    
    # External system identification
    external_applicant_id = Column(String(255), nullable=False, index=True)  # Applicant ID in HR platform
    
    # Personal information
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    
    # Resume/CV
    resume_filename = Column(String(500), nullable=True)
    resume_path = Column(String(1000), nullable=True)  # Local or S3 path
    resume_url = Column(String(1000), nullable=True)  # External URL if available
    resume_parsed = Column(JSON, nullable=True)  # Docling parsed resume (structured data)
    
    # Profile data from HR platform
    profile_data = Column(JSON, nullable=True)  # Additional data from HR system
    
    # Status
    status = Column(String(50), nullable=False, default='new')  # new, screening, interview, offer, rejected, hired
    current_stage = Column(String(255), nullable=True)  # Stage name in HR platform
    
    # Timing
    applied_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    parsed_at = Column(DateTime(timezone=True), nullable=True)  # When resume was parsed
    
    __table_args__ = (
        Index('ix_applicants_customer_job', 'customer_id', 'job_posting_id'),
        Index('ix_applicants_status', 'status'),
        Index('ix_applicants_applied_at', 'applied_at'),
        {'extend_existing': True}
    )


class ApplicantScore(BaseModel):
    """
    Scoring results for applicants compared against employee baseline.
    
    Multi-dimensional scoring:
    - Skills overlap
    - Experience pattern
    - Career trajectory
    - Company fit
    - Education alignment
    - Semantic similarity (embeddings)
    """
    __tablename__ = "applicant_scores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    applicant_id = Column(Integer, ForeignKey("applicants.id"), nullable=False, index=True)
    analysis_id = Column(String(255), ForeignKey("talent_analyses.analysis_id"), nullable=False, index=True)
    
    # Overall score (0-100)
    overall_score = Column(Float, nullable=False, index=True)
    
    # Dimension scores (0-100 each)
    skills_score = Column(Float, nullable=True)
    experience_score = Column(Float, nullable=True)
    career_trajectory_score = Column(Float, nullable=True)
    company_fit_score = Column(Float, nullable=True)
    education_score = Column(Float, nullable=True)
    embedding_similarity = Column(Float, nullable=True)  # Cosine similarity (0-1)
    
    # Supporting data
    matched_employee_ids = Column(JSON, nullable=True)  # Top 5 most similar employees
    dimension_scores = Column(JSON, nullable=True)  # Full breakdown of all scores
    reasoning = Column(Text, nullable=True)  # AI-generated explanation
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    __table_args__ = (
        Index('ix_applicant_scores_score', 'overall_score'),
        Index('ix_applicant_scores_analysis', 'analysis_id'),
        {'extend_existing': True}
    )


class BaselineEmployeeProfile(BaseModel):
    """
    Cached employee baseline profiles per role.
    
    Aggregates data from current employees in a specific role
    to create a "look-alike" profile for candidate comparison.
    
    Rebuilt when:
    - Employee data changes
    - New role is analyzed
    - Periodic refresh (monthly)
    """
    __tablename__ = "baseline_employee_profiles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(255), ForeignKey("customers.customer_id"), nullable=False, index=True)
    
    # Role identification
    role_title = Column(String(500), nullable=False, index=True)  # e.g., "Senior Backend Engineer"
    
    # Employee data
    employee_count = Column(Integer, nullable=False)
    employee_ids = Column(JSON, nullable=False)  # List of PDLPerson IDs
    
    # Aggregated patterns
    aggregated_skills = Column(JSON, nullable=True)  # Skills frequency map
    common_companies = Column(JSON, nullable=True)  # Company patterns
    education_patterns = Column(JSON, nullable=True)  # Degree/school patterns
    career_paths = Column(JSON, nullable=True)  # Common career progressions
    avg_years_experience = Column(Float, nullable=True)
    
    # Baseline embedding (average of employee embeddings)
    baseline_embedding = Column(JSON, nullable=True)  # Vector for similarity comparison
    
    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        UniqueConstraint('customer_id', 'role_title', name='uq_baseline_customer_role'),
        {'extend_existing': True}
    )
