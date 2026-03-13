"""
Content Writer API Schemas

Pydantic models for the Research-First Content Writer API endpoints.
Supports runs, research packs, drafts, skills, and section refinement.
"""
from typing import Any, Dict, List, Optional, Literal, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


# --- Enums (matching database models) ---

class ContentFormat(str, Enum):
    LINKEDIN = "linkedin"
    BLOG = "blog"
    TWITTER_ARTICLE = "twitter_article"


class SourceType(str, Enum):
    WEB = "web"
    REDDIT = "reddit"
    HACKER_NEWS = "hacker_news"
    TWITTER = "twitter"
    CURATED_BLOGS = "curated_blogs"
    PASTED_TEXT = "pasted_text"


class RunStatus(str, Enum):
    PENDING = "pending"
    RESEARCHING = "researching"
    POV_SELECTION = "pov_selection"
    HOOK_SELECTION = "hook_selection"
    OUTLINE_SELECTION = "outline_selection"
    DRAFTING = "drafting"
    COMPLETED = "completed"
    FAILED = "failed"


class SkillType(str, Enum):
    VOICE = "voice"
    PILLARS = "pillars"
    HOOKS = "hooks"
    EXAMPLES = "examples"
    PROOF_BANK = "proof_bank"


class IssueType(str, Enum):
    """Types of issues that can be identified in content for refinement."""
    TOO_VAGUE = "too_vague"
    CONTRADICTORY = "contradictory"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    OFF_BRAND = "off_brand"
    WEAK_HOOK = "weak_hook"
    POOR_FLOW = "poor_flow"
    TOO_TECHNICAL = "too_technical"
    TOO_GENERIC = "too_generic"
    WRONG_TONE = "wrong_tone"
    NEEDS_EVIDENCE = "needs_evidence"


# --- Run Request/Response Models ---

class RunCreateRequest(BaseModel):
    """Request to create a new content writer run."""
    topic: str = Field(..., description="Content topic", max_length=500)
    format: ContentFormat = Field(..., description="Output format")
    selected_sources: List[SourceType] = Field(default_factory=list, description="Research sources to use (optional)")
    pasted_text: Optional[str] = Field(None, description="User-pasted text (optional, used if pasted_text in sources)", max_length=51200)
    constraints: Optional[Dict[str, Any]] = Field(None, description="Optional constraints (audience, tone, length)")
    
    @validator('pasted_text', always=True)
    def validate_pasted_text(cls, v, values):
        if 'selected_sources' in values and SourceType.PASTED_TEXT in values['selected_sources']:
            if not v or not v.strip():
                raise ValueError('pasted_text is required when pasted_text source is selected')
        return v


class POVPointerResponse(BaseModel):
    """A POV concept/approach suggestion."""
    index: int
    label: str = Field(..., description="Short label (e.g., 'Contrarian Take', 'Operator Playbook')")
    description: str = Field(..., description="2-3 sentence description of this POV approach")
    key_concepts: List[str] = Field(..., description="3-5 key concepts/angles to emphasize")
    research_refs: Optional[List[int]] = Field(None, description="Research pack excerpt IDs to support this POV")


class HookOptionResponse(BaseModel):
    """A hook option for the content using the Alec Paul framework."""
    index: int
    title: Optional[str] = Field(None, description="Title for blog/twitter article (null for LinkedIn)")
    lede: str = Field(..., description="Full hook - Line 1 (social proof + story) + Line 2 (expectation)")
    line1: Optional[str] = Field(None, description="Just the first line that must work standalone (mobile test)")
    pattern: Optional[str] = Field(None, description="Hook pattern used (Unexpected Result, Contrarian Confession, etc.)")
    why_it_works: Optional[str] = Field(None, description="Brief explanation of why this hook is effective")
    format: ContentFormat


class OutlineSectionResponse(BaseModel):
    """A section in an outline."""
    title: str
    summary: str


class OutlineOptionResponse(BaseModel):
    """An outline option for long-form content."""
    index: int
    sections: List[OutlineSectionResponse]


class POVSelectRequest(BaseModel):
    """Request to select a POV from options."""
    pov_index: Optional[int] = Field(None, description="Index of selected POV (0-4)", ge=0, le=9)
    custom_pov: Optional[str] = Field(None, description="User-provided custom POV instruction")
    
    @validator('custom_pov', always=True)
    def validate_selection(cls, v, values):
        if values.get('pov_index') is None and not v:
            raise ValueError('Either pov_index or custom_pov must be provided')
        return v


class HookSelectRequest(BaseModel):
    """Request to select a hook from options."""
    hook_index: int = Field(..., description="Index of selected hook", ge=0)


class OutlineSelectRequest(BaseModel):
    """Request to select an outline from options."""
    outline_index: int = Field(..., description="Index of selected outline", ge=0)


class ResearchPackExcerptResponse(BaseModel):
    """An excerpt from the research pack."""
    id: int
    text: str
    source_url: Optional[str] = None
    source_type: SourceType
    metadata: Optional[Dict[str, Any]] = None
    selected: bool = False


class ResearchPackResponse(BaseModel):
    """Research pack data for a run."""
    run_id: str
    key_takeaways: List[Dict[str, Any]]
    excerpts: List[ResearchPackExcerptResponse]
    contested_items: Optional[List[Dict[str, Any]]] = None
    best_counterargument: Optional[str] = None
    selected_excerpt_ids: List[int] = []


class DraftArtifactResponse(BaseModel):
    """A draft artifact version."""
    id: int
    run_id: str
    version: int
    format: ContentFormat
    content: str
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    generated_at: datetime
    refinement_type: Optional[str] = None
    refinement_instruction: Optional[str] = None


class RunResponse(BaseModel):
    """Full run data with all artifacts."""
    id: int
    run_id: str
    customer_id: str
    user_id: int
    topic: str
    format: ContentFormat
    status: RunStatus
    selected_sources: List[SourceType]
    pasted_text: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    pov_options: Optional[List[POVPointerResponse]] = None
    selected_pov: Optional[Dict[str, Any]] = None
    hook_options: Optional[List[HookOptionResponse]] = None
    selected_hook: Optional[Dict[str, Any]] = None
    outline_options: Optional[List[OutlineOptionResponse]] = None
    selected_outline: Optional[Dict[str, Any]] = None
    applied_skill_ids: Optional[List[int]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    task_id: Optional[str] = None
    research_pack: Optional[ResearchPackResponse] = None
    latest_draft: Optional[DraftArtifactResponse] = None
    
    class Config:
        from_attributes = True


class RunListResponse(BaseModel):
    """Paginated list of runs."""
    items: List[RunResponse]
    total: int
    page: int
    page_size: int


class RunSubmitResponse(BaseModel):
    """Response after submitting a new run."""
    run_id: str
    status: RunStatus
    message: str
    task_id: Optional[str] = None


# --- Research Pack Actions ---

class ResearchPackActionRequest(BaseModel):
    """Request to perform an action on a research pack excerpt."""
    action: Literal["use", "ignore", "find_opposing_view", "find_stronger_support"]
    excerpt_id: int = Field(..., description="ID of excerpt in Research Pack")


class ResearchPackActionResponse(BaseModel):
    """Response from research pack action."""
    success: bool
    action: str
    excerpt_id: int
    message: str
    new_excerpts: Optional[List[ResearchPackExcerptResponse]] = None


# --- Section Refinement (Two-Step POV Workflow) ---

class SectionIdentifier(BaseModel):
    """Identifies a specific section of the draft."""
    paragraph_index: Optional[int] = Field(None, description="Zero-based paragraph index")
    section_title: Optional[str] = Field(None, description="Section heading (for blog posts)")
    start_char: Optional[int] = Field(None, description="Character offset start")
    end_char: Optional[int] = Field(None, description="Character offset end")
    highlighted_text: str = Field(..., description="Actual text to rewrite")


class POVSelection(BaseModel):
    """User's selected POV approach for section rewrite."""
    selected_index: Optional[int] = Field(None, description="Index from generated POV pointers (0-4)")
    custom_pov: Optional[str] = Field(None, description="User-provided custom POV instruction")
    preserve_facts: bool = Field(True, description="Keep factual claims from research pack")
    maintain_flow: bool = Field(True, description="Preserve transitions with surrounding sections")
    
    @validator('custom_pov', always=True)
    def validate_selection(cls, v, values):
        if values.get('selected_index') is None and not v:
            raise ValueError('Either selected_index or custom_pov must be provided')
        return v


class DraftRefineRequest(BaseModel):
    """Request for section-level refinement (two-step process)."""
    refinement_type: Literal["surgical", "guided", "section_critique", "generate_pov_pointers"] = Field(
        ..., description="Refinement approach"
    )
    
    # Section identification
    section: Optional[SectionIdentifier] = Field(None, description="Section to refine")
    
    # Issue identification (structured)
    issue_types: Optional[List[IssueType]] = Field(None, description="Identified issues with this section")
    issue_explanation: Optional[str] = Field(None, description="Additional context about the issue")
    
    # Two-step POV workflow
    num_pov_pointers: int = Field(5, ge=3, le=10, description="Number of POV pointers to generate (default 5)")
    pov_selection: Optional[POVSelection] = Field(None, description="Selected POV for rewrite")
    
    # Legacy support
    instruction: Optional[str] = Field(None, description="General refinement instruction")


class POVPointersResponse(BaseModel):
    """Response when generating POV pointers (Step 1)."""
    section_text: str
    document_summary: str = Field(..., description="Brief summary of overall document context")
    issue_types: List[IssueType]
    pov_pointers: List[POVPointerResponse] = Field(..., description="POV approach suggestions")


class SectionRefineResponse(BaseModel):
    """Response for section refinement (Step 2)."""
    original_text: str
    refined_text: str
    changes_summary: str = Field(..., description="Explanation of what changed and why")
    issues_addressed: List[IssueType]
    pov_applied: str = Field(..., description="Description of POV transformation applied")
    research_pack_refs: Optional[List[int]] = Field(None, description="Research pack excerpt IDs used")
    new_version: Optional[DraftArtifactResponse] = None


# --- Generate Draft ---

class GenerateDraftRequest(BaseModel):
    """Request to generate a draft (Fast Path)."""
    use_selected_pov: bool = Field(True, description="Use the selected POV")
    use_selected_hook: bool = Field(True, description="Use the selected hook")
    use_selected_outline: bool = Field(True, description="Use the selected outline (for long-form)")
    apply_default_skills: bool = Field(True, description="Apply user's default skills")
    specific_skill_ids: Optional[List[int]] = Field(None, description="Specific skill IDs to apply")


class GenerateDraftResponse(BaseModel):
    """Response after draft generation."""
    run_id: str
    status: RunStatus
    draft: Optional[DraftArtifactResponse] = None
    message: str


# --- Skills Request/Response Models ---

class SkillCreateRequest(BaseModel):
    """Request to create a new skill."""
    skill_type: SkillType = Field(..., description="Type of skill")
    name: str = Field(..., description="Skill name", max_length=255)
    description: Optional[str] = Field(None, description="Skill description")
    content: Dict[str, Any] = Field(..., description="Skill content (structure varies by type)")
    is_default: bool = Field(False, description="Auto-apply if relevant")


class SkillUpdateRequest(BaseModel):
    """Request to update a skill."""
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class SkillResponse(BaseModel):
    """Skill data."""
    id: int
    skill_id: str
    skill_type: SkillType
    name: str
    description: Optional[str] = None
    content: Dict[str, Any]
    is_default: bool
    usage_count: int
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SkillListResponse(BaseModel):
    """List of skills."""
    items: List[SkillResponse]
    total: int


# --- Draft Version History ---

class DraftVersionListResponse(BaseModel):
    """List of draft versions for a run."""
    run_id: str
    versions: List[DraftArtifactResponse]
    total: int
