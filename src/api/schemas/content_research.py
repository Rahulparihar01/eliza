"""
Content Research API Schemas

Pydantic models for the Content Research API - web search based content generation
with source multi-selection and strict citation requirements.

KEY FEATURES:
- Source multi-selection (like POV selection)
- Strict grounding - content uses ONLY selected sources
- No fabricated information
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


# --- Enums ---

class ResearchRunStatus(str, Enum):
    PENDING = "pending"
    RESEARCHING = "researching"  # Web search in progress
    SOURCE_SELECTION = "source_selection"  # Waiting for user to select sources
    POV_SELECTION = "pov_selection"
    HOOK_SELECTION = "hook_selection"
    GENERATING = "generating"  # Content generation in progress
    COMPLETED = "completed"
    FAILED = "failed"


# --- Web Source Models ---

class WebSourceResponse(BaseModel):
    """A source retrieved from web search."""
    id: str = Field(..., description="Unique source ID for selection")
    url: str
    title: str
    snippet: str = Field(..., description="Preview/summary of source content")
    relevance_score: Optional[float] = Field(None, description="AI-scored relevance (0-1)")
    query_origin: str = Field(..., description="Which search query found this")
    source_type: str = Field(default="web")
    retrieved_at: Optional[str] = None


class ResearchPackResponse(BaseModel):
    """Complete research package from web search."""
    run_id: str
    topic: str
    queries_executed: List[str]
    total_sources_found: int
    sources: List[WebSourceResponse]
    status: ResearchRunStatus


# --- Source Selection Models ---

class SourceSelectRequest(BaseModel):
    """Request to select sources for content generation."""
    source_ids: List[str] = Field(..., description="IDs of selected sources", min_items=1)
    usage_notes: Optional[str] = Field(None, description="Notes on how to use sources")
    
    @validator('source_ids')
    def validate_source_ids(cls, v):
        if len(v) == 0:
            raise ValueError('At least one source must be selected')
        if len(v) > 20:
            raise ValueError('Maximum 20 sources can be selected')
        return v


class SelectedSourcesResponse(BaseModel):
    """Response after selecting sources."""
    run_id: str
    selected_count: int
    sources: List[WebSourceResponse]
    status: ResearchRunStatus
    message: str


# --- Content Generation Models ---

class CitationResponse(BaseModel):
    """A citation reference in the content."""
    marker: str = Field(..., description="Citation marker in text (e.g., '[Source 1]')")
    source_id: str
    url: str
    title: str


class GeneratedContentResponse(BaseModel):
    """Content generated from selected sources."""
    run_id: str
    content: str = Field(..., description="Generated content with inline citations")
    formatted_content: str = Field(..., description="Content with full citation references")
    target_word_count: int = Field(..., description="Target word count requested")
    word_count: int
    sources_cited: List[str] = Field(..., description="IDs of sources actually cited")
    citations: List[CitationResponse]
    uncited_claims: List[str] = Field(default_factory=list, description="Claims that couldn't be sourced (should be empty)")
    generated_at: datetime


# --- Run Models ---

class ResearchRunCreateRequest(BaseModel):
    """Request to create a new content research run."""
    topic: str = Field(..., description="Topic to research and write about", max_length=500)
    target_word_count: int = Field(default=1000, ge=300, le=3000, description="Target word count for the article")
    constraints: Optional[Dict[str, Any]] = Field(None, description="Optional constraints (audience, tone, etc.)")
    num_search_queries: int = Field(default=6, ge=3, le=10, description="Number of search queries for good recall")


class ResearchRunResponse(BaseModel):
    """Full research run data."""
    id: int
    run_id: str
    customer_id: str
    user_id: int
    topic: str
    target_word_count: int
    status: ResearchRunStatus
    
    # Research phase
    queries_executed: Optional[List[str]] = None
    total_sources_found: Optional[int] = None
    sources: Optional[List[WebSourceResponse]] = None
    
    # Selection phase
    selected_source_ids: Optional[List[str]] = None
    selected_sources: Optional[List[WebSourceResponse]] = None
    
    # POV/Hook (optional)
    pov_options: Optional[List[Dict[str, Any]]] = None
    selected_pov: Optional[Dict[str, Any]] = None
    hook_options: Optional[List[Dict[str, Any]]] = None
    selected_hook: Optional[Dict[str, Any]] = None
    
    # Generated content
    content: Optional[GeneratedContentResponse] = None
    
    # Metadata
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    task_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class ResearchRunListResponse(BaseModel):
    """Paginated list of research runs."""
    items: List[ResearchRunResponse]
    total: int
    page: int
    page_size: int


class ResearchRunSubmitResponse(BaseModel):
    """Response after creating a research run."""
    run_id: str
    status: ResearchRunStatus
    message: str
    task_id: Optional[str] = None


# --- POV and Hook for Content Research ---

class POVOptionResponse(BaseModel):
    """A POV option for content."""
    index: int
    label: str
    description: str
    key_concepts: List[str]
    source_refs: Optional[List[str]] = Field(None, description="Source IDs that support this POV")


class POVSelectRequest(BaseModel):
    """Request to select POV."""
    pov_index: Optional[int] = Field(None, ge=0, le=9)
    custom_pov: Optional[str] = Field(None, max_length=1000)
    
    @validator('custom_pov', always=True)
    def validate_selection(cls, v, values):
        if values.get('pov_index') is None and not v:
            raise ValueError('Either pov_index or custom_pov must be provided')
        return v


class HookOptionResponse(BaseModel):
    """A hook option."""
    index: int
    title: Optional[str] = None
    lede: str
    line1: Optional[str] = None
    pattern: Optional[str] = None
    why_it_works: Optional[str] = None


class HookSelectRequest(BaseModel):
    """Request to select hook."""
    hook_index: int = Field(..., ge=0)


# --- Generate Content Request ---

class GenerateContentRequest(BaseModel):
    """Request to generate content from selected sources."""
    use_selected_pov: bool = Field(default=True)
    use_selected_hook: bool = Field(default=True)
    strict_grounding: bool = Field(
        default=True, 
        description="If true, ONLY use information from selected sources (recommended)"
    )


class GenerateContentResponse(BaseModel):
    """Response after content generation."""
    run_id: str
    status: ResearchRunStatus
    content: Optional[GeneratedContentResponse] = None
    message: str
    warnings: Optional[Dict[str, Any]] = None
