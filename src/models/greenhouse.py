"""
Greenhouse connector Pydantic models for API requests/responses.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class GreenhouseJobResponse(BaseModel):
    """Job information from Greenhouse for UI dropdowns."""
    id: int
    name: str
    status: str
    departments: List[str] = Field(default_factory=list)
    offices: List[str] = Field(default_factory=list)


class TestGreenhouseConnectionRequest(BaseModel):
    """Request to test Greenhouse connection."""
    api_key: str = Field(..., description="Greenhouse Harvest API key")


class TestConnectionResponse(BaseModel):
    """Response from connection test."""
    success: bool
    message: str


class GreenhouseConnectorConfigRequest(BaseModel):
    """Request to create/update Greenhouse connector configuration."""
    name: str = Field(..., description="Configuration name", min_length=1, max_length=255)
    api_key: str = Field(..., description="Greenhouse Harvest API key")
    job_ids: Optional[List[int]] = Field(None, description="Filter by specific job IDs")
    application_status: Optional[str] = Field(
        None,
        description="Filter by application status (active, rejected, hired)"
    )
    candidate_tags: Optional[List[str]] = Field(
        None,
        description="Filter by candidate tags"
    )
    created_after: Optional[datetime] = Field(
        None,
        description="Only fetch candidates created after this date"
    )
    include_prospects: bool = Field(
        False,
        description="Include prospect candidates (not yet applied)"
    )
    max_candidates: int = Field(
        100,
        ge=1,
        le=1000,
        description="Maximum number of candidates to fetch"
    )
    description: Optional[str] = Field(None, description="Configuration description")
    tags: Optional[List[str]] = Field(None, description="Configuration tags")


class GreenhouseConnectorConfigResponse(BaseModel):
    """Response with Greenhouse connector configuration."""
    id: int
    connector_id: str
    connector_name: str
    connector_type: str
    description: Optional[str]
    tags: Optional[List[str]]
    customer_id: str
    is_enabled: bool
    sync_config: dict
    created_at: datetime
    updated_at: datetime
    last_sync_at: Optional[datetime]
    last_sync_status: Optional[str]
    next_sync_at: Optional[datetime]

