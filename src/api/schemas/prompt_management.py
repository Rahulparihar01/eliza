"""
Prompt Management API Schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PromptType(str, Enum):
    SYSTEM = "system"
    QUERY_REWRITE = "query_rewrite"
    RETRIEVAL = "retrieval"
    SYNTHESIS = "synthesis"
    EVALUATION = "evaluation"
    CUSTOM = "custom"


class PromptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    TESTING = "testing"


# ==================== Request Schemas ====================

class CreatePromptRequest(BaseModel):
    domain: str = Field(..., description="Domain identifier (e.g., 'fasb', 'insurance')")
    prompt_type: PromptType = Field(..., description="Type of prompt")
    name: str = Field(..., description="Human-readable name")
    content: str = Field(..., description="The prompt content")
    description: Optional[str] = Field(None, description="Optional description")
    variables: Optional[List[str]] = Field(None, description="List of template variables")
    is_active: bool = Field(False, description="Whether to immediately activate")


class UpdatePromptRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[List[str]] = None
    status: Optional[PromptStatus] = None


class CreateDomainRequest(BaseModel):
    domain: str = Field(..., description="Domain identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: Optional[str] = None
    use_query_rewrite: bool = True
    use_custom_system_prompt: bool = True
    default_model: Optional[str] = None
    temperature: Optional[int] = Field(None, ge=0, le=100)
    max_tokens: Optional[int] = None
    retrieval_top_k: Optional[int] = 10
    similarity_threshold: Optional[int] = Field(70, ge=0, le=100)


class UpdateDomainRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    use_query_rewrite: Optional[bool] = None
    use_custom_system_prompt: Optional[bool] = None
    default_model: Optional[str] = None
    temperature: Optional[int] = Field(None, ge=0, le=100)
    max_tokens: Optional[int] = None
    retrieval_top_k: Optional[int] = None
    similarity_threshold: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class PromoteFromGEPARequest(BaseModel):
    domain: str = Field(..., description="Target domain")
    prompt_type: PromptType = Field(..., description="Type of prompt")
    content: str = Field(..., description="Optimized prompt content")
    gepa_job_id: int = Field(..., description="GEPA job ID")
    gepa_variant_id: int = Field(..., description="GEPA variant ID")
    quality_score: Optional[int] = Field(None, ge=0, le=100)
    auto_activate: bool = Field(False, description="Auto-activate the new version")


# ==================== Response Schemas ====================

class PromptSummary(BaseModel):
    id: int
    domain: str
    prompt_type: PromptType
    name: str
    version: int
    is_active: bool
    status: PromptStatus
    usage_count: int
    avg_quality_score: Optional[int]
    gepa_job_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptDetail(PromptSummary):
    description: Optional[str]
    content: str
    variables: Optional[List[str]]
    created_by_user_id: Optional[int]
    last_modified_by_user_id: Optional[int]
    gepa_variant_id: Optional[int]

    class Config:
        from_attributes = True


class PromptVersionList(BaseModel):
    domain: str
    prompt_type: PromptType
    versions: List[PromptSummary]
    active_version: Optional[int]


class DomainConfigResponse(BaseModel):
    id: int
    domain: str
    display_name: str
    description: Optional[str]
    use_query_rewrite: bool
    use_custom_system_prompt: bool
    default_model: Optional[str]
    temperature: Optional[int]
    max_tokens: Optional[int]
    retrieval_top_k: Optional[int]
    similarity_threshold: Optional[int]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DomainWithPromptsResponse(DomainConfigResponse):
    prompts: Dict[str, PromptSummary]  # keyed by prompt_type
    stats: Dict[str, Any]


class ChangeLogEntry(BaseModel):
    id: int
    action: str
    change_summary: Optional[str]
    source: str
    source_reference: Optional[str]
    user_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class PromptChangeLogResponse(BaseModel):
    prompt_id: int
    logs: List[ChangeLogEntry]


class DomainListResponse(BaseModel):
    domains: List[DomainConfigResponse]
    total: int


class PromptListResponse(BaseModel):
    prompts: List[PromptSummary]
    total: int


class RAGPromptsResponse(BaseModel):
    """Response for active RAG prompts ready for use."""
    domain: str
    prompts: Dict[str, str]  # prompt_type -> content


class DomainStatsResponse(BaseModel):
    domain: str
    total_versions: int
    active_count: int
    draft_count: int
    archived_count: int
    gepa_optimized_count: int
    total_usage: int
    prompt_types: List[str]


# ==================== Domain Feedback (prod → GEPA) ====================

class CreateDomainFeedbackRequest(BaseModel):
    environment: str = Field("prod", pattern="^(prod|staging|dev)$")
    rating_numeric: int = Field(-1, ge=-2, le=2)
    comment: str = Field(..., min_length=1, max_length=5000)
    tags: Optional[List[str]] = Field(None, max_length=20)
    improvement_suggestions: Optional[str] = Field(None, max_length=2000)
    target_components: Optional[List[str]] = Field(
        None,
        description="GEPA component names (e.g., 'answer_synthesis_prompt')",
    )


class DomainFeedbackItem(BaseModel):
    id: int
    domain: str
    environment: str
    rating_numeric: int
    comment: str
    tags: Optional[List[str]]
    improvement_suggestions: Optional[str]
    target_components: Optional[List[str]]
    prompt_snapshot: Dict[str, Any]
    created_by_user_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class DomainFeedbackListResponse(BaseModel):
    items: List[DomainFeedbackItem]
    total: int
    page: int
    page_size: int


class GepaSeedFeedbackResponse(BaseModel):
    domain: str
    environment: str
    seed_feedback: List[Dict[str, Any]]
