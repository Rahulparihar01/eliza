"""
Pydantic schemas for Adoption Dashboard API.

Defines request/response models for:
- Adoption metrics queries and responses
- Data sharing management
- Sync operations
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field


# =============================================================================
# Metrics Schemas
# =============================================================================

class AdoptionMetricsQuery(BaseModel):
    """Query parameters for adoption metrics."""
    customer_ids: Optional[List[str]] = Field(
        None, 
        description="Filter to specific companies (uses accessible companies if not provided)"
    )
    start_date: Optional[date] = Field(None, description="Start date for metrics")
    end_date: Optional[date] = Field(None, description="End date for metrics")
    provider_type: Optional[str] = Field(None, description="Filter by provider (openai, anthropic, etc)")
    group_by: Optional[str] = Field(
        "day", 
        description="Aggregation period: day, week, month"
    )


class DailyMetric(BaseModel):
    """Single day's adoption metrics."""
    date: date
    customer_id: str
    customer_name: Optional[str] = None
    provider_type: Optional[str] = None
    active_users: int = 0
    total_conversations: int = 0
    total_messages: int = 0
    # GPT adoption metrics
    gpt_conversations: int = 0  # Conversations using custom GPTs
    base_conversations: int = 0  # Conversations using base ChatGPT
    unique_gpts: int = 0  # Count of unique GPTs used
    # Token fields (not available from Compliance API, kept for future use)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model_usage_breakdown: Optional[Dict[str, int]] = None
    
    class Config:
        from_attributes = True


class AdoptionMetricsSummary(BaseModel):
    """Summary statistics for adoption metrics."""
    total_active_users: int = 0  # Sum of daily active users (may overcount)
    total_conversations: int = 0
    total_messages: int = 0
    total_tokens: int = 0  # Not available from Compliance API
    avg_daily_users: float = 0.0  # Average daily active users (more accurate)
    avg_daily_conversations: float = 0.0
    avg_conversations_per_user: Optional[float] = None
    # GPT adoption metrics
    gpt_conversations: int = 0  # Conversations using custom GPTs
    base_conversations: int = 0  # Conversations using base ChatGPT
    gpt_adoption_rate: float = 0.0  # Percentage: gpt_conversations / total_conversations * 100
    top_models: List[Dict[str, Any]] = Field(default_factory=list)
    top_gpts: List[Dict[str, Any]] = Field(default_factory=list)


class GPTInfo(BaseModel):
    """GPT information with usage metrics."""
    id: str = Field(..., description="External GPT ID (g-xxx)")
    name: str = Field(..., description="GPT name/title")
    description: Optional[str] = Field(None, description="GPT description")
    uses: int = Field(0, description="Total user messages sent to this GPT")
    users: int = Field(0, description="Unique users who interacted")
    conversations: int = Field(0, description="Total conversations with this GPT")
    creator_email: Optional[str] = Field(None, description="Email of GPT creator")
    creator_name: Optional[str] = Field(None, description="Builder/creator display name")
    short_url: Optional[str] = Field(None, description="Short URL (chatgpt.com/g/xxx)")
    company_id: Optional[str] = Field(None, description="Tenant ID (for multi-company view)")
    company_name: Optional[str] = Field(None, description="Tenant name (for multi-company view)")


class TopUserInfo(BaseModel):
    """User information with usage metrics."""
    user_email: str = Field(..., description="User email address")
    user_external_id: Optional[str] = Field(None, description="External user ID (OpenAI user ID)")
    total_conversations: int = Field(0, description="Total conversations by this user")
    total_messages: int = Field(0, description="Total messages sent by this user")
    gpts_used: int = Field(0, description="Number of unique GPTs used")
    company_id: Optional[str] = Field(None, description="Tenant ID")
    company_name: Optional[str] = Field(None, description="Tenant name")


class TopUsersResponse(BaseModel):
    """Response containing top users by usage."""
    users: List[TopUserInfo]
    total_count: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class TopGPTsResponse(BaseModel):
    """Response containing top GPTs with usage metrics."""
    gpts: List[GPTInfo]
    total_count: int
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class GPTUsersResponse(BaseModel):
    """Response containing users who interacted with a GPT."""
    gpt_id: str
    gpt_name: Optional[str] = None
    users: List[Dict[str, Any]]
    total_count: int


class AdoptionMetricsResponse(BaseModel):
    """Response containing adoption metrics (legacy single response)."""
    query: AdoptionMetricsQuery
    summary: AdoptionMetricsSummary
    metrics: List[DailyMetric]
    companies_included: List[str]
    date_range: Dict[str, Optional[str]]


class CompanyMetricsResponse(BaseModel):
    """Per-company metrics response (used by frontend)."""
    company_id: str
    start_date: str
    end_date: str
    metrics: List[DailyMetric]
    summary: AdoptionMetricsSummary


class CompanyAdoptionSummary(BaseModel):
    """Adoption summary for a single company."""
    # Frontend-expected fields (company_id/company_name)
    company_id: str
    company_name: Optional[str] = None
    is_own_tenant: bool = False
    has_adoption_enabled: bool = False
    last_sync_at: Optional[datetime] = None
    metrics_summary: Optional[AdoptionMetricsSummary] = None
    # Additional tracking fields
    provider_type: Optional[str] = None
    total_days_tracked: int = 0
    total_active_users: int = 0
    total_conversations: int = 0
    total_tokens: int = 0
    is_syncing: bool = False
    sync_error: Optional[str] = None


class AdoptionOverviewResponse(BaseModel):
    """Overview of all accessible companies' adoption."""
    companies: List[CompanyAdoptionSummary]
    total_companies: int
    companies_with_data: int


# =============================================================================
# Sharing Schemas
# =============================================================================

class AdoptionShareCreate(BaseModel):
    """Request to share adoption data with another company."""
    target_customer_id: str = Field(..., description="Company to share data with")
    share_level: str = Field(
        default="read", 
        description="Share level: 'read' or 'admin'"
    )
    notes: Optional[str] = Field(None, description="Optional notes about the share")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class AdoptionShareUpdate(BaseModel):
    """Request to update a share."""
    share_level: Optional[str] = Field(None, description="New share level")
    is_enabled: Optional[bool] = Field(None, description="Enable/disable share")
    notes: Optional[str] = Field(None, description="Update notes")
    expires_at: Optional[datetime] = Field(None, description="Update expiration")


class AdoptionShareResponse(BaseModel):
    """Response for an adoption share."""
    id: int
    source_customer_id: str
    source_customer_name: Optional[str] = None
    target_customer_id: str
    target_customer_name: Optional[str] = None
    share_level: str
    is_enabled: bool
    notes: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    is_active: bool = True
    
    class Config:
        from_attributes = True


class AdoptionShareListResponse(BaseModel):
    """List of adoption shares."""
    shares_given: List[AdoptionShareResponse] = Field(
        default_factory=list, 
        description="Shares where current tenant is the source"
    )
    shares_received: List[AdoptionShareResponse] = Field(
        default_factory=list, 
        description="Shares where current tenant is the target"
    )
    total_given: int = 0
    total_received: int = 0


# =============================================================================
# Sync Schemas
# =============================================================================

class AdoptionSyncRequest(BaseModel):
    """Request to trigger a manual sync."""
    customer_id: Optional[str] = Field(
        None, 
        description="Specific company to sync (defaults to current tenant)"
    )
    provider_type: Optional[str] = Field(
        None, 
        description="Specific provider to sync (defaults to all configured)"
    )
    start_date: Optional[date] = Field(None, description="Start date for sync")
    end_date: Optional[date] = Field(None, description="End date for sync")


class AdoptionSyncResponse(BaseModel):
    """Response for sync operation."""
    task_id: str
    status: str = "queued"
    message: str
    customer_id: str
    provider_type: Optional[str] = None


class AdoptionSyncStatus(BaseModel):
    """Status of a sync operation."""
    task_id: str
    status: str  # queued, running, completed, failed
    customer_id: str
    provider_type: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    records_synced: int = 0
    error_message: Optional[str] = None


# =============================================================================
# Provider Config Schemas (for adoption sources)
# =============================================================================

class AdoptionProviderConfig(BaseModel):
    """Configuration for an adoption data source."""
    id: int
    customer_id: str
    provider_name: str
    display_name: Optional[str] = None
    is_adoption_source: bool = True
    is_enabled: bool = True
    last_sync_at: Optional[datetime] = None
    sync_status: Optional[str] = None
    
    class Config:
        from_attributes = True


class AdoptionProviderListResponse(BaseModel):
    """List of adoption provider configurations."""
    providers: List[AdoptionProviderConfig]
    total: int


# =============================================================================
# Dashboard Widget Schemas
# =============================================================================

class UsageTrendData(BaseModel):
    """Data point for usage trend chart."""
    date: str
    active_users: int = 0
    conversations: int = 0
    tokens: int = 0


class ModelUsageData(BaseModel):
    """Data for model usage breakdown."""
    model: str
    count: int
    percentage: float = 0.0


class CompanyComparisonData(BaseModel):
    """Data for company comparison chart."""
    customer_id: str
    customer_name: str
    active_users: int = 0
    conversations: int = 0
    tokens: int = 0


class DashboardWidgetsResponse(BaseModel):
    """Pre-computed dashboard widget data."""
    usage_trend: List[UsageTrendData] = Field(default_factory=list)
    model_breakdown: List[ModelUsageData] = Field(default_factory=list)
    company_comparison: List[CompanyComparisonData] = Field(default_factory=list)
    period: str = "30d"

