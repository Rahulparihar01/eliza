"""
Connector API Schemas

Pydantic models for connector configuration, sync runs, and telemetry.
Request/response schemas for all connector-related endpoints.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator

from src.models.connector import ConnectorType, SyncMode


# -------------------------------------------------------------------------
# Connector Configuration Schemas
# -------------------------------------------------------------------------

class PDLSearchQuery(BaseModel):
    """
    Schema for People Data Labs search query parameters.
    
    Supports all major PDL query fields for person search.
    """
    # Job fields
    job_title: Optional[List[str]] = None
    job_title_role: Optional[List[str]] = None
    job_title_sub_role: Optional[List[str]] = None
    job_title_levels: Optional[List[str]] = None
    job_company_name: Optional[List[str]] = None
    job_company_website: Optional[List[str]] = None
    job_company_size: Optional[List[str]] = None
    job_company_industry: Optional[List[str]] = None
    
    # Location fields
    location_name: Optional[List[str]] = None
    location_locality: Optional[List[str]] = None
    location_region: Optional[List[str]] = None
    location_country: Optional[List[str]] = None
    location_continent: Optional[List[str]] = None
    
    # Education fields
    education_school_name: Optional[List[str]] = None
    education_school_type: Optional[List[str]] = None
    education_degree_name: Optional[List[str]] = None
    education_major: Optional[List[str]] = None
    
    # Skills & Experience
    skills: Optional[List[str]] = None
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    
    # Personal
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_title_role": ["software engineer", "data scientist"],
                "job_company_name": ["Google", "Amazon"],
                "location_country": ["United States"],
                "skills": ["python", "machine learning"],
                "experience_years_min": 5
            }
        }


class ConnectorConfigCreate(BaseModel):
    """Request schema for creating connector configuration."""
    
    connector_type: str = Field(..., description="Type of connector (e.g., 'people_data_labs')")
    connector_name: str = Field(..., min_length=1, max_length=255, description="User-friendly name")
    description: Optional[str] = Field(None, description="Optional description")
    tags: Optional[List[str]] = Field(default=[], description="Tags for filtering")
    
    # Credentials (will be encrypted)
    credentials: Dict[str, str] = Field(..., description="Connector credentials (e.g., {'api_key': 'xxx'})")
    
    # Sync configuration
    sync_config: Dict[str, Any] = Field(..., description="Connector-specific configuration")
    sync_schedule: Optional[str] = Field(None, description="Cron expression for scheduled syncs")
    sync_mode: str = Field(default="full_refresh", description="full_refresh or incremental")
    
    use_shared_credentials: bool = Field(default=False, description="Use customer-wide credentials")
    
    class Config:
        json_schema_extra = {
            "example": {
                "connector_type": "people_data_labs",
                "connector_name": "FAANG Senior Engineers",
                "description": "Senior engineers from top tech companies",
                "tags": ["recruiting", "engineering"],
                "credentials": {
                    "api_key": "pdl_xxxxxx"
                },
                "sync_config": {
                    "search_query": {
                        "job_title_role": ["software engineer", "engineering manager"],
                        "job_company_name": ["Amazon", "Google", "Facebook", "Apple", "Microsoft"],
                        "experience_years_min": 5
                    },
                    "max_records": 10000,
                    "page_size": 100,
                    "rate_limit": 60,
                    "estimated_cost_acknowledged": True
                },
                "sync_schedule": "0 2 * * *",  # 2am daily
                "sync_mode": "full_refresh"
            }
        }


class ConnectorConfigUpdate(BaseModel):
    """Request schema for updating connector configuration."""
    
    connector_name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    
    credentials: Optional[Dict[str, str]] = None
    sync_config: Optional[Dict[str, Any]] = None
    sync_schedule: Optional[str] = None
    sync_mode: Optional[str] = None
    is_enabled: Optional[bool] = None


class ConnectorConfigResponse(BaseModel):
    """Response schema for connector configuration."""
    
    id: int
    connector_id: str
    connector_type: ConnectorType  # Use enum from models
    connector_name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    
    customer_id: str
    use_shared_credentials: Optional[bool] = False  # Made optional with default
    
    sync_config: Dict[str, Any]
    sync_config_version: Optional[int] = 1  # Made optional with default
    sync_schedule: Optional[str] = None
    sync_mode: Optional[SyncMode] = None  # Made optional - may be None in DB
    
    is_enabled: bool
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_message: Optional[str] = None
    
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    @validator('tags', pre=True, always=True)
    def ensure_tags_list(cls, v):
        """Convert None to empty list for tags."""
        return v if v is not None else []

    @validator('updated_at', pre=True, always=True)
    def ensure_updated_at(cls, v, values):
        """
        Backfill updated_at for legacy rows that were written without it.
        Prevents clients from rendering Unix epoch fallback timestamps.
        """
        return v if v is not None else values.get('created_at')
    
    class Config:
        from_attributes = True


class ConnectorConfigListResponse(BaseModel):
    """Response schema for listing connector configurations."""
    
    total: int
    connectors: List[ConnectorConfigResponse]


# -------------------------------------------------------------------------
# Sync Run Schemas
# -------------------------------------------------------------------------

class TriggerSyncRequest(BaseModel):
    """Request schema for triggering a manual sync."""
    
    manual_trigger: bool = Field(default=True, description="Whether this is a manual trigger")


class SyncRunResponse(BaseModel):
    """Response schema for sync run details."""
    
    id: int
    sync_id: str
    connector_id: int
    customer_id: str
    
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str
    error_message: Optional[str] = None
    
    records_extracted: int = 0
    records_loaded: int = 0
    records_skipped: int = 0
    records_failed: int = 0
    
    celery_task_id: Optional[str] = None
    sync_mode: str = "full"
    triggered_by: str = "manual"
    
    class Config:
        from_attributes = True


class SyncRunListResponse(BaseModel):
    """Response schema for listing sync runs."""
    
    total: int
    sync_runs: List[SyncRunResponse]


# -------------------------------------------------------------------------
# Telemetry Schemas
# -------------------------------------------------------------------------

class TelemetryEventResponse(BaseModel):
    """Response schema for telemetry events."""
    
    id: int
    sync_run_id: int
    connector_config_id: int
    customer_id: str
    
    event_type: str
    event_timestamp: datetime
    
    records_processed: int = 0
    api_calls_made: int = 0
    bytes_transferred: int = 0
    duration_seconds: Optional[float] = None
    
    error_message: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class TelemetryListResponse(BaseModel):
    """Response schema for listing telemetry events."""
    
    total: int
    events: List[TelemetryEventResponse]


# -------------------------------------------------------------------------
# Connector Type Schemas
# -------------------------------------------------------------------------

class ConnectorTypeInfo(BaseModel):
    """Information about a connector type."""
    
    type: ConnectorType
    name: str
    description: str
    category: str
    requires_credentials: bool
    supported_sync_modes: List[SyncMode]
    available: bool = True


class ConnectorTypeResponse(BaseModel):
    """Response schema for available connector types."""
    
    type: str
    name: str
    description: str
    category: str
    requires_credentials: bool
    supported_sync_modes: List[str]


class ConnectorTypeListResponse(BaseModel):
    """Response schema for listing available connector types."""
    
    total: int
    connector_types: List[ConnectorTypeResponse]


class AvailableConnectorTypesResponse(BaseModel):
    """Response with all available connector types including enum values."""
    
    connector_types: List[ConnectorTypeInfo]


# -------------------------------------------------------------------------
# Validation & Testing Schemas
# -------------------------------------------------------------------------

class ValidateConfigRequest(BaseModel):
    """Request schema for validating connector configuration."""
    
    connector_type: str
    sync_config: Dict[str, Any]


class ValidateConfigResponse(BaseModel):
    """Response schema for configuration validation."""
    
    is_valid: bool
    error_message: Optional[str] = None


class TestConnectionRequest(BaseModel):
    """Request schema for testing connector connection."""
    
    connector_type: str
    credentials: Dict[str, str]
    sync_config: Optional[Dict[str, Any]] = {}


class TestConnectionResponse(BaseModel):
    """Response schema for connection test."""
    
    success: bool
    status: str
    message: str
    metadata: Optional[Dict[str, Any]] = None


# -------------------------------------------------------------------------
# Cost Estimation Schemas
# -------------------------------------------------------------------------

class EstimateCostRequest(BaseModel):
    """Request schema for estimating sync cost."""
    
    connector_type: str
    credentials: Dict[str, str]
    sync_config: Dict[str, Any]


class EstimateCostResponse(BaseModel):
    """Response schema for cost estimation."""
    
    estimated_record_count: Optional[int] = None
    estimated_cost: Optional[float] = None
    cost_per_record: float
    requires_acknowledgment: bool
    warning_message: Optional[str] = None


# -------------------------------------------------------------------------
# PDL Person Schemas
# -------------------------------------------------------------------------

class PDLPersonResponse(BaseModel):
    """Response schema for PDL person records."""
    
    id: int
    pdl_id: str
    customer_id: str
    
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    
    job_title: Optional[str] = None
    job_title_role: Optional[str] = None
    job_company_name: Optional[str] = None
    job_company_size: Optional[str] = None
    job_company_industry: Optional[str] = None
    
    primary_email: Optional[str] = None
    emails: Optional[List[Any]] = None  # JSON array (can be strings or dicts)
    phone_numbers: Optional[List[Any]] = None  # JSON array (can be strings or dicts)
    linkedin_url: Optional[str] = None
    
    location_name: Optional[str] = None
    location_locality: Optional[str] = None
    location_region: Optional[str] = None
    location_country: Optional[str] = None
    
    skills: Optional[List[str]] = None
    education_history: Optional[List[Dict[str, Any]]] = None
    inferred_years_experience: Optional[int] = None
    
    pdl_likelihood: Optional[int] = None
    pdl_last_updated: Optional[datetime] = None
    
    first_seen_sync_id: Optional[str] = None
    last_updated_sync_id: Optional[str] = None
    sync_count: int = 1
    
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class PDLPersonListResponse(BaseModel):
    """Response schema for listing PDL persons."""
    
    total: int
    persons: List[PDLPersonResponse]
    page: int = 1
    page_size: int = 50


# -------------------------------------------------------------------------
# Statistics Schemas
# -------------------------------------------------------------------------

class ConnectorStatisticsResponse(BaseModel):
    """Response schema for connector statistics."""
    
    connector_id: str
    connector_name: str
    connector_type: str
    
    total_syncs: int
    successful_syncs: int
    failed_syncs: int
    
    total_records_synced: int
    total_records_transformed: int
    total_records_failed: int
    
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    
    average_sync_duration_seconds: Optional[float] = None
    average_records_per_sync: Optional[float] = None


# -------------------------------------------------------------------------
# Person Search Schemas
# -------------------------------------------------------------------------

class PersonSearchRequest(BaseModel):
    """Request schema for person search."""
    
    query: Optional[str] = Field(None, description="Free-text search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filters for search (company, location, etc.)")
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Results per page")
    use_elasticsearch: bool = Field(default=True, description="Use Elasticsearch if available")


class PersonSearchResult(BaseModel):
    """Single person search result."""
    
    pdl_id: str
    customer_id: str
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None
    job_title_role: Optional[str] = None
    job_company_name: Optional[str] = None
    job_company_size: Optional[str] = None
    job_company_industry: Optional[str] = None
    primary_email: Optional[str] = None
    linkedin_url: Optional[str] = None
    location_name: Optional[str] = None
    location_locality: Optional[str] = None
    location_region: Optional[str] = None
    location_country: Optional[str] = None
    skills: Optional[List[Any]] = None
    pdl_likelihood: Optional[int] = None
    sync_count: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PersonSearchResponse(BaseModel):
    """Response schema for person search."""
    
    total: int = Field(description="Total number of results")
    results: List[PersonSearchResult] = Field(description="Search results")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Results per page")
    total_pages: int = Field(description="Total number of pages")
    source: str = Field(description="Data source used (elasticsearch, postgresql)")


class CareerTransitionRequest(BaseModel):
    """Request schema for career transition analysis."""
    
    from_company: str = Field(description="Source company name")
    to_company: str = Field(description="Destination company name")
    limit: int = Field(default=50, ge=1, le=200, description="Max results")


class SkillSearchRequest(BaseModel):
    """Request schema for skill-based search."""
    
    skills: List[str] = Field(description="List of skill names")
    require_all: bool = Field(default=True, description="If true, must have ALL skills")
    limit: int = Field(default=50, ge=1, le=200, description="Max results")


class CompanyNetworkRequest(BaseModel):
    """Request schema for company network analysis."""
    
    company_name: str = Field(description="Center company name")
    depth: int = Field(default=2, ge=1, le=3, description="Traversal depth")


class AggregationsRequest(BaseModel):
    """Request schema for analytics aggregations."""
    
    agg_fields: List[str] = Field(
        description="Fields to aggregate (e.g., job_company_name, location_country, skills)"
    )
    
    @validator("agg_fields")
    def validate_agg_fields(cls, v):
        """Validate aggregation fields."""
        valid_fields = [
            "job_company_name",
            "job_title_role",
            "location_country",
            "location_region",
            "skills",
            "job_company_industry"
        ]
        for field in v:
            if field not in valid_fields:
                raise ValueError(f"Invalid aggregation field: {field}. Must be one of: {valid_fields}")
        return v


class AggregationsResponse(BaseModel):
    """Response schema for analytics aggregations."""
    
    aggregations: Dict[str, List[Dict[str, Any]]] = Field(
        description="Aggregation results by field"
    )
