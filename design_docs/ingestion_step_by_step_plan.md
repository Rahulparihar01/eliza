# Data Ingestion Layer - Step-by-Step Implementation Plan
## With Query Validation, Cost Controls, and Deduplication

**Last Updated:** October 8, 2025  
**Estimated Timeline:** 8-10 weeks  
**Team Size:** 1-2 engineers

---

## Architecture Summary

```
Base PDL Connector (Code) + Multiple Configured Instances (Static Queries)

Example Instances:
├── "FAANG Senior Engineers"     → Query: {company: FAANG, role: engineer, years: 5+}
├── "Healthcare Data Scientists" → Query: {industry: healthcare, role: data_scientist}
└── "NYC Sales Executives"       → Query: {location: NYC, role: sales, title: VP+}

Each instance:
- Uses same connector code (PeopleDataLabsConnector)
- Has unique static query configured via UI
- Independent scheduling, quotas, and cost tracking
```

---

## Phase 0: Foundation Setup (Week 1)

### Tasks

#### Task 0.1: Install Airbyte CDK Dependencies
**Files:** `requirements.txt`

**Action:**
```bash
# Already added, but verify:
pip install airbyte-cdk>=0.90.0 airbyte-protocol-models>=0.7.0
```

**Verification:**
```python
python -c "import airbyte_cdk; print(airbyte_cdk.__version__)"
```

---

#### Task 0.2: Create Directory Structure
**Action:**
```bash
mkdir -p src/services/ingestion/connectors
mkdir -p src/services/ingestion/transformers
mkdir -p src/api/schemas
touch src/services/ingestion/__init__.py
touch src/services/ingestion/connectors/__init__.py
touch src/services/ingestion/transformers/__init__.py
```

**Expected Structure:**
```
src/
├── services/
│   └── ingestion/
│       ├── __init__.py
│       ├── connector_service.py
│       ├── rate_limiter.py
│       ├── connectors/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   └── people_data_labs.py
│       └── transformers/
│           ├── __init__.py
│           ├── pdl_transformer.py
│           └── pdl_to_document.py (optional, Phase 3)
├── api/
│   └── schemas/
│       └── connectors.py
└── tasks/
    └── ingestion_tasks.py (already created)
```

---

#### Task 0.3: Update Core Config
**File:** `src/core/config.py`

**Add ingestion-specific settings:**
```python
# src/core/config.py (add to Settings class)

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Data Ingestion Configuration
    max_connector_records_default: int = Field(default=10000, alias="MAX_CONNECTOR_RECORDS_DEFAULT")
    connector_cost_per_record: float = Field(default=0.02, alias="CONNECTOR_COST_PER_RECORD")
    connector_cost_warning_threshold: float = Field(default=100.0, alias="CONNECTOR_COST_WARNING_THRESHOLD")
    connector_execution_timeout: int = Field(default=7200, alias="CONNECTOR_EXECUTION_TIMEOUT")
    pdl_default_rate_limit: int = Field(default=60, alias="PDL_DEFAULT_RATE_LIMIT")
```

**Update `.env` file:**
```bash
# Data Ingestion Settings
MAX_CONNECTOR_RECORDS_DEFAULT=10000
CONNECTOR_COST_PER_RECORD=0.02
CONNECTOR_COST_WARNING_THRESHOLD=100.0
CONNECTOR_EXECUTION_TIMEOUT=7200
PDL_DEFAULT_RATE_LIMIT=60
```

**Deliverable:** ✅ Settings available in application

---

## Phase 1: Database Models & Migration (Week 1-2)

### Task 1.1: Create Connector Models
**File:** `src/models/connector.py`

**Content:**
```python
"""
Data Connector Models

Supports multiple connector instances using the same connector type.
Each instance has a static query configured via UI.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from typing import Dict, Any, Optional

from src.models.database import BaseModel


class ConnectorConfiguration(BaseModel):
    """
    Connector configuration - one row per connector instance.
    
    Multiple instances can use same connector_type with different queries.
    Example:
    - Instance 1: PDL connector for "FAANG Engineers"
    - Instance 2: PDL connector for "Healthcare Execs"
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
    )
    
    def update_query(self, new_query: Dict[str, Any], updated_by_user_id: int):
        """Update search query and maintain version history."""
        if not self.sync_config_history:
            self.sync_config_history = []
        
        self.sync_config_history.append({
            "version": self.sync_config_version,
            "query": self.sync_config.get("search_query"),
            "updated_at": func.now(),
            "updated_by": updated_by_user_id
        })
        
        self.sync_config["search_query"] = new_query
        self.sync_config_version += 1


class ConnectorSyncRun(BaseModel):
    """Tracks individual connector sync executions."""
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
    )


class IngestedData(BaseModel):
    """Staging table for raw ingested data before transformation."""
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
    
    # Metadata
    metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('ix_ingested_customer_company', 'customer_id', 'company_dataset'),
        Index('ix_ingested_status', 'customer_id', 'status'),
        Index('ix_ingested_sync_status', 'sync_id', 'status'),
        Index('ix_ingested_source_id', 'customer_id', 'source_record_id'),
    )


class ConnectorTelemetry(BaseModel):
    """Real-time telemetry events for connector syncs (like BI telemetry)."""
    __tablename__ = "connector_telemetry"
    
    # Identification
    sync_id = Column(String(100), ForeignKey("connector_sync_runs.sync_id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(100), nullable=False)
    
    # Event details
    event_type = Column(String(50), nullable=False)
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
    
    # Technical details
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    sync_run = relationship("ConnectorSyncRun", back_populates="telemetry_events")
    
    __table_args__ = (
        Index('ix_telemetry_sync_timestamp', 'sync_id', 'event_timestamp'),
    )


class PDLPerson(BaseModel):
    """
    Normalized person record from People Data Labs.
    
    Deduplication: UPSERT by pdl_id + customer_id.
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
    
    # Tracking
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
    )
```

**Deliverable:** ✅ Models defined

---

### Task 1.2: Create Database Migration
**File:** `alembic/versions/xxx_add_connector_tables.py`

**Action:**
```bash
cd /Users/scottgay/Documents/Eliza/eliza-platform
alembic revision -m "add_connector_ingestion_tables"
```

**Edit generated migration file:**
```python
"""add_connector_ingestion_tables

Revision ID: xxx
Revises: yyy
Create Date: 2025-10-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'xxx'
down_revision = 'yyy'  # Update to latest revision
branch_labels = None
depends_on = None


def upgrade():
    # ConnectorConfiguration table
    op.create_table(
        'connector_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connector_id', sa.String(100), nullable=False),
        sa.Column('connector_type', sa.String(50), nullable=False),
        sa.Column('connector_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('use_shared_credentials', sa.Boolean(), default=True),
        sa.Column('credentials_encrypted', sa.Text(), nullable=True),
        sa.Column('sync_config', postgresql.JSON(astext_type=sa.Text()), nullable=False, default={}),
        sa.Column('sync_config_version', sa.Integer(), default=1),
        sa.Column('sync_config_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('max_records_per_sync', sa.Integer(), nullable=True),
        sa.Column('estimated_cost_per_sync', sa.Float(), nullable=True),
        sa.Column('total_cost_to_date', sa.Float(), default=0.0),
        sa.Column('sync_schedule', sa.String(100), nullable=True),
        sa.Column('sync_mode', sa.String(20), default='incremental'),
        sa.Column('is_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_healthy', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_check_message', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_connector_customer_type', 'connector_configurations', ['customer_id', 'connector_type'])
    op.create_index('ix_connector_enabled', 'connector_configurations', ['is_enabled', 'customer_id'])
    op.create_index(op.f('ix_connector_configurations_connector_id'), 'connector_configurations', ['connector_id'], unique=True)
    
    # ConnectorSyncRun table
    op.create_table(
        'connector_sync_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_id', sa.String(100), nullable=False),
        sa.Column('connector_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('celery_task_id', sa.String(100), nullable=True),
        sa.Column('sync_mode', sa.String(20), nullable=False),
        sa.Column('triggered_by', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('records_extracted', sa.Integer(), default=0),
        sa.Column('records_loaded', sa.Integer(), default=0),
        sa.Column('records_skipped', sa.Integer(), default=0),
        sa.Column('records_failed', sa.Integer(), default=0),
        sa.Column('checkpoint_before', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('checkpoint_after', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('api_calls_made', sa.Integer(), default=0),
        sa.Column('bytes_transferred', sa.Integer(), default=0),
        sa.Column('cost_incurred', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_configurations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index(op.f('ix_connector_sync_runs_sync_id'), 'connector_sync_runs', ['sync_id'], unique=True)
    op.create_index('ix_sync_run_customer_status', 'connector_sync_runs', ['customer_id', 'status'])
    op.create_index('ix_sync_run_connector_created', 'connector_sync_runs', ['connector_id', 'created_at'])
    
    # IngestedData table
    op.create_table(
        'ingested_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('connector_id', sa.Integer(), nullable=False),
        sa.Column('sync_id', sa.String(100), nullable=False),
        sa.Column('source_record_id', sa.String(255), nullable=True),
        sa.Column('source_record_type', sa.String(50), nullable=True),
        sa.Column('company_dataset', sa.String(255), nullable=True),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('transformed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('transformed_record_type', sa.String(50), nullable=True),
        sa.Column('transformed_record_id', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_configurations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['sync_id'], ['connector_sync_runs.sync_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_ingested_customer_company', 'ingested_data', ['customer_id', 'company_dataset'])
    op.create_index('ix_ingested_status', 'ingested_data', ['customer_id', 'status'])
    op.create_index('ix_ingested_sync_status', 'ingested_data', ['sync_id', 'status'])
    op.create_index('ix_ingested_source_id', 'ingested_data', ['customer_id', 'source_record_id'])
    
    # ConnectorTelemetry table
    op.create_table(
        'connector_telemetry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('current_stage', sa.String(100), nullable=True),
        sa.Column('records_processed', sa.Integer(), default=0),
        sa.Column('api_calls_made', sa.Integer(), default=0),
        sa.Column('cost_so_far', sa.Float(), default=0.0),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sync_id'], ['connector_sync_runs.sync_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_telemetry_sync_timestamp', 'connector_telemetry', ['sync_id', 'event_timestamp'])
    
    # PDLPerson table
    op.create_table(
        'pdl_persons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pdl_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('middle_name', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(255), nullable=True),
        sa.Column('job_title_role', sa.String(100), nullable=True),
        sa.Column('job_title_sub_role', sa.String(100), nullable=True),
        sa.Column('job_title_levels', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('job_company_name', sa.String(255), nullable=True),
        sa.Column('job_company_id', sa.String(100), nullable=True),
        sa.Column('job_company_size', sa.String(50), nullable=True),
        sa.Column('job_company_industry', sa.String(100), nullable=True),
        sa.Column('job_company_location_name', sa.String(255), nullable=True),
        sa.Column('job_start_date', sa.String(50), nullable=True),
        sa.Column('primary_email', sa.String(255), nullable=True),
        sa.Column('emails', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('primary_phone', sa.String(50), nullable=True),
        sa.Column('phone_numbers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('linkedin_username', sa.String(255), nullable=True),
        sa.Column('twitter_url', sa.String(500), nullable=True),
        sa.Column('github_url', sa.String(500), nullable=True),
        sa.Column('location_name', sa.String(255), nullable=True),
        sa.Column('location_locality', sa.String(100), nullable=True),
        sa.Column('location_metro', sa.String(100), nullable=True),
        sa.Column('location_region', sa.String(100), nullable=True),
        sa.Column('location_country', sa.String(100), nullable=True),
        sa.Column('location_continent', sa.String(50), nullable=True),
        sa.Column('skills', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('inferred_years_experience', sa.Integer(), nullable=True),
        sa.Column('education_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('work_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('pdl_likelihood', sa.Integer(), nullable=True),
        sa.Column('pdl_last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_seen_sync_id', sa.String(100), nullable=True),
        sa.Column('last_updated_sync_id', sa.String(100), nullable=True),
        sa.Column('sync_count', sa.Integer(), default=1),
        sa.Column('ingested_data_id', sa.Integer(), nullable=True),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['ingested_data_id'], ['ingested_data.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_pdl_person_unique', 'pdl_persons', ['pdl_id', 'customer_id'], unique=True)
    op.create_index('ix_pdl_person_name', 'pdl_persons', ['first_name', 'last_name'])
    op.create_index('ix_pdl_person_company_role', 'pdl_persons', ['job_company_name', 'job_title_role'])
    op.create_index('ix_pdl_person_location', 'pdl_persons', ['location_country', 'location_region'])
    op.create_index('ix_pdl_person_email', 'pdl_persons', ['primary_email'])


def downgrade():
    op.drop_table('pdl_persons')
    op.drop_table('connector_telemetry')
    op.drop_table('ingested_data')
    op.drop_table('connector_sync_runs')
    op.drop_table('connector_configurations')
```

**Run migration:**
```bash
alembic upgrade head
```

**Deliverable:** ✅ Tables created in database

---

### Task 1.3: Update Model Imports
**File:** `src/models/__init__.py`

**Add:**
```python
from .connector import (
    ConnectorConfiguration,
    ConnectorSyncRun,
    IngestedData,
    ConnectorTelemetry,
    PDLPerson
)
```

**File:** `src/main.py`

**Add to imports (before routes):**
```python
from src.models.connector import (
    ConnectorConfiguration,
    ConnectorSyncRun,
    IngestedData,
    ConnectorTelemetry,
    PDLPerson
)
```

**Deliverable:** ✅ Models importable throughout app

---

## Phase 2: Core Connector Implementation (Week 2-3)

### Task 2.1: Create Base Connector Interface
**File:** `src/services/ingestion/connectors/base.py`

**Content:** (See implementation guide - BaseConnector class)

**Deliverable:** ✅ Abstract base class for all connectors

---

### Task 2.2: Implement Rate Limiter
**File:** `src/services/ingestion/rate_limiter.py`

**Content:**
```python
"""
Rate Limiter for API calls.

Token bucket algorithm with thread-safe implementation.
"""
import time
from collections import deque
from threading import Lock
from typing import Optional

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class RateLimiter:
    """
    Token bucket rate limiter for API calls.
    
    Usage:
        limiter = RateLimiter(max_requests=60, time_window=60)
        limiter.acquire()  # Blocks if rate limit exceeded
    """
    
    def __init__(self, max_requests: int, time_window: int = 60):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds (default: 60)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()
        
        logger.info(
            "rate_limiter_initialized",
            max_requests=max_requests,
            time_window=time_window
        )
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a request.
        
        Blocks until rate limit allows the request or timeout occurs.
        
        Args:
            timeout: Maximum time to wait in seconds (None = wait forever)
            
        Returns:
            True if acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                now = time.time()
                
                # Remove requests outside time window
                while self.requests and self.requests[0] < now - self.time_window:
                    self.requests.popleft()
                
                # Check if we can make request
                if len(self.requests) < self.max_requests:
                    self.requests.append(now)
                    return True
                
                # Calculate sleep time
                oldest_request = self.requests[0]
                sleep_time = self.time_window - (now - oldest_request)
                
                # Check timeout
                if timeout and (time.time() - start_time) >= timeout:
                    logger.warning("rate_limiter_timeout", timeout=timeout)
                    return False
                
                logger.debug(
                    "rate_limit_hit",
                    sleep_time=sleep_time,
                    requests_in_window=len(self.requests)
                )
            
            # Sleep outside lock
            if sleep_time > 0:
                time.sleep(min(sleep_time, 1.0))  # Sleep max 1s at a time
    
    def get_current_usage(self) -> dict:
        """Get current rate limit usage statistics."""
        with self.lock:
            now = time.time()
            
            # Remove old requests
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            return {
                "requests_in_window": len(self.requests),
                "max_requests": self.max_requests,
                "utilization_percent": (len(self.requests) / self.max_requests) * 100,
                "available_capacity": self.max_requests - len(self.requests)
            }
```

**Deliverable:** ✅ Rate limiter utility

---

### Task 2.3: Implement PDL Connector
**File:** `src/services/ingestion/connectors/people_data_labs.py`

**Content:** (Full implementation with all minor recommendations - see next comment for complete code)

**Deliverable:** ✅ PDL connector with validation, estimation, rate limiting

---

### Task 2.4: Create Connector Factory
**File:** `src/services/ingestion/connectors/__init__.py`

**Content:**
```python
"""
Connector registry and factory.

Supports multiple connector types with unified interface.
"""
from typing import Dict, Any
from .base import BaseConnector
from .people_data_labs import PeopleDataLabsConnector

CONNECTOR_REGISTRY = {
    "people_data_labs": PeopleDataLabsConnector,
    # Future connectors:
    # "salesforce": SalesforceConnector,
    # "postgresql": PostgreSQLConnector,
}


def get_connector_class(connector_type: str) -> type:
    """
    Get connector class by type.
    
    Args:
        connector_type: Type identifier (e.g., "people_data_labs")
        
    Returns:
        Connector class
        
    Raises:
        ValueError: If connector type not found
    """
    if connector_type not in CONNECTOR_REGISTRY:
        available = ", ".join(CONNECTOR_REGISTRY.keys())
        raise ValueError(
            f"Unknown connector type: {connector_type}. "
            f"Available: {available}"
        )
    
    return CONNECTOR_REGISTRY[connector_type]


def create_connector(
    connector_type: str,
    credentials: Dict[str, str],
    config: Dict[str, Any],
    customer_id: str
) -> BaseConnector:
    """
    Factory method to instantiate connector.
    
    Args:
        connector_type: Type identifier
        credentials: Connector credentials (decrypted)
        config: Connector configuration (including query)
        customer_id: Customer ID
        
    Returns:
        Initialized connector instance
    """
    connector_class = get_connector_class(connector_type)
    
    return connector_class(
        credentials=credentials,
        config=config,
        customer_id=customer_id
    )


def list_available_connectors() -> list:
    """List all available connector types."""
    return list(CONNECTOR_REGISTRY.keys())
```

**Deliverable:** ✅ Connector registry

---

## Phase 3: Connector Service & Transform (Week 3-4)

### Task 3.1: Implement Connector Service
**File:** `src/services/ingestion/connector_service.py`

**(Implementation with all minor recommendations - this is a long file, will provide in separate response)**

**Deliverable:** ✅ Service layer orchestrating connector operations

---

### Task 3.2: Implement PDL Transformer
**File:** `src/services/ingestion/transformers/pdl_transformer.py`

**(Handles deduplication via upsert - will provide in separate response)**

**Deliverable:** ✅ Transform raw PDL JSON to structured tables with deduplication

---

### Task 3.3: Update Celery Tasks
**File:** `src/tasks/ingestion_tasks.py`

**Add transform task:**
```python
@celery_app.task(
    base=IngestionTask,
    bind=True,
    name="transform_pdl_records",
    queue="ingestion"
)
def transform_pdl_records(
    self,
    sync_id: str,
    customer_id: str
) -> Dict[str, Any]:
    """Transform raw staging records to structured tables."""
    # Implementation...
```

**Deliverable:** ✅ Transform task added

---

## Phase 4: API Endpoints (Week 4-5)

### Task 4.1: Create Request/Response Schemas
**File:** `src/api/schemas/connectors.py`

**(Pydantic models for API - will provide complete code)**

**Deliverable:** ✅ API schemas with validation

---

### Task 4.2: Implement API Routes
**File:** `src/api/routes/connectors.py`

**Endpoints:**
- `POST /v1/connectors/estimate` - Estimate query results
- `POST /v1/connectors/configure` - Configure new connector
- `GET /v1/connectors` - List connectors
- `GET /v1/connectors/{id}` - Get connector details
- `PUT /v1/connectors/{id}` - Update connector
- `DELETE /v1/connectors/{id}` - Delete connector
- `POST /v1/connectors/{id}/test` - Test connection
- `POST /v1/connectors/{id}/sync` - Trigger sync
- `GET /v1/connectors/{id}/syncs` - List sync history
- `GET /v1/connectors/syncs/{sync_id}/telemetry` - Stream telemetry (SSE)

**Deliverable:** ✅ Complete REST API

---

## Phase 5: Frontend Admin UI (Week 5-6)

### Task 5.1: Create Connector Management Page
**Files:**
- `frontend/src/pages/admin/ConnectorsPage.tsx`
- `frontend/src/components/connectors/ConnectorsList.tsx`
- `frontend/src/components/connectors/ConnectorCard.tsx`

**Deliverable:** ✅ List and manage connectors

---

### Task 5.2: Create Connector Configuration Modal
**File:** `frontend/src/components/connectors/ConfigureConnectorModal.tsx`

**Features:**
- Connector type selection
- Credentials input
- Query builder (next task)
- Estimation preview
- Cost acknowledgment

**Deliverable:** ✅ Configuration UI

---

### Task 5.3: Create PDL Query Builder
**File:** `frontend/src/components/connectors/PDLQueryBuilder.tsx`

**Features:**
- Multi-select for job roles
- Tag input for companies
- Location selector
- Skills input
- Experience range
- Real-time estimation

**Deliverable:** ✅ Query builder UI

---

### Task 5.4: Create Sync History & Telemetry View
**Files:**
- `frontend/src/components/connectors/SyncHistoryTable.tsx`
- `frontend/src/components/connectors/SyncTelemetryStream.tsx`

**Features:**
- Table of past syncs
- Status indicators
- Real-time progress (SSE)
- Error details

**Deliverable:** ✅ Monitoring UI

---

## Phase 6: Testing & Hardening (Week 6-7)

### Task 6.1: Unit Tests
**Files to create:**
- `tests/services/ingestion/test_rate_limiter.py`
- `tests/services/ingestion/test_pdl_connector.py`
- `tests/services/ingestion/test_connector_service.py`
- `tests/services/ingestion/test_pdl_transformer.py`

**Deliverable:** ✅ 80%+ code coverage

---

### Task 6.2: Integration Tests
**File:** `tests/integration/test_connector_end_to_end.py`

**Test scenarios:**
- Configure connector
- Estimate query
- Run sync
- Verify data in staging
- Verify data transformed
- Verify deduplication

**Deliverable:** ✅ End-to-end tests passing

---

### Task 6.3: Load Testing
**File:** `tests/load/test_connector_concurrency.py`

**Scenarios:**
- Multiple connectors syncing simultaneously
- Large result sets (100k+ records)
- Rate limit behavior under load

**Deliverable:** ✅ Performance benchmarks

---

## Phase 7: Documentation & Deployment (Week 7-8)

### Task 7.1: API Documentation
**Update:** `docs/api/connectors.md`

**Deliverable:** ✅ Complete API docs

---

### Task 7.2: User Guide
**Create:** `UserDocumentation/DataConnectors.md`

**Sections:**
- Configuring connectors
- Understanding query syntax
- Cost management
- Troubleshooting

**Deliverable:** ✅ User documentation

---

### Task 7.3: Deploy to Staging
**Commands:**
```bash
docker-compose build app celery-worker celery-ingestion-worker
docker-compose up -d
docker-compose logs -f celery-ingestion-worker
```

**Verification:**
- Health checks passing
- Flower shows ingestion queue
- Test connector creation via API

**Deliverable:** ✅ Deployed to staging

---

### Task 7.4: Production Deployment Checklist
**File:** `docs/deployment/connector_deployment_checklist.md`

**Items:**
- [ ] Database migration applied
- [ ] Environment variables set
- [ ] Encryption key configured
- [ ] PDL API key added
- [ ] celery-ingestion-worker running
- [ ] Flower monitoring configured
- [ ] Kibana dashboards created
- [ ] Alert rules configured
- [ ] Cost tracking enabled

**Deliverable:** ✅ Production-ready

---

## Phase 8: Optional Enhancements (Week 8+)

### Task 8.1: Document Store Integration
Transform PDL persons to searchable documents (see Phase 3 in implementation guide)

**Deliverable:** Semantic search over person profiles

---

### Task 8.2: Neo4j Graph Relationships
Model person-company-skill relationships

**Deliverable:** Network analysis capabilities

---

### Task 8.3: Additional Connectors
Implement Salesforce, PostgreSQL, etc. using same base pattern

**Deliverable:** Multi-source ingestion

---

## Risk Mitigation Summary

| Risk | Mitigation | Status |
|------|-----------|--------|
| Invalid queries | Pre-save validation | ✅ Built-in |
| Cost explosion | Estimation + limits | ✅ Built-in |
| Duplicate records | Upsert by PDL ID | ✅ Built-in |
| Rate limit violations | Token bucket limiter | ✅ Built-in |
| Query evolution | Version history | ✅ Built-in |
| Long-running tasks | Dedicated queue + timeout | ✅ Built-in |
| Schema drift | Pydantic validation | ✅ Built-in |

---

## Success Criteria

By end of Phase 7, you should be able to:

1. ✅ Configure a PDL connector via admin UI
2. ✅ Define a search query with validation
3. ✅ See estimated record count and cost
4. ✅ Trigger a sync manually or on schedule
5. ✅ Monitor sync progress in real-time
6. ✅ View ingested records in `pdl_persons` table
7. ✅ Handle duplicate records correctly
8. ✅ Stay within rate limits and cost budgets
9. ✅ Track query changes over time
10. ✅ Debug failures via telemetry

---

## Next Steps

**Immediate action items:**
1. Review and approve this plan
2. Confirm any adjustments needed
3. Start with Phase 1: Database models & migration
4. I'll provide complete code for each task as we go

**Ready to start Phase 1, Task 1.1?**

