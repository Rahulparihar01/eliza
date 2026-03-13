"""
Tiny Model Studio API schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TinyModelTaskType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"


class TinyModelRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_SELECTION = "awaiting_selection"
    COMPLETED = "completed"
    FAILED = "failed"


class TinyModelProjectStage(str, Enum):
    PROBLEM_DEFINED = "problem_defined"
    SAMPLE_UPLOADED = "sample_uploaded"
    MICRO_PREVIEW_READY = "micro_preview_ready"
    PREVIEW_READY = "preview_ready"
    READY_TO_TRAIN = "ready_to_train"
    TRAINING = "training"
    TRAINED = "trained"
    FAILED = "failed"


class TinyModelWinnerPolicy(str, Enum):
    BEST = "best"
    LIGHTEST = "lightest"


class TinyModelAugmenter(str, Enum):
    TEMPLATE = "template"
    OPENAI = "openai"


class TinyModelSweepLevel(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class TinyModelErrorTolerance(str, Enum):
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"
    OVER_PREDICT = "over_predict"
    UNDER_PREDICT = "under_predict"
    OVER_SEGMENT = "over_segment"
    UNDER_SEGMENT = "under_segment"
    BALANCED = "balanced"


class TinyModelRunCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=3, max_length=120)
    task_type: TinyModelTaskType
    seed_examples: int = Field(default=120, ge=30, le=2000)
    synthetic_examples: int = Field(default=80, ge=0, le=2000)
    augmenter: TinyModelAugmenter = TinyModelAugmenter.TEMPLATE
    llm_model: str = Field(default="gpt-4o-mini", max_length=100)
    k_folds: int = Field(default=5, ge=2, le=10)
    sweep_level: TinyModelSweepLevel = TinyModelSweepLevel.STANDARD
    max_sweep_candidates: int | None = Field(default=None, ge=3, le=120)
    approval_rate: float = Field(default=1.0, ge=0.1, le=1.0)
    quality_threshold: float = Field(default=0.9, ge=0.5, le=1.0)
    project_id: str | None = Field(default=None, max_length=120)


class TinyModelProjectCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=3, max_length=120)
    task_type: TinyModelTaskType
    problem_brief: str = Field(..., min_length=12, max_length=4000)
    error_tolerance: TinyModelErrorTolerance = TinyModelErrorTolerance.BALANCED


class TinyModelDatasetGenerationRequest(BaseModel):
    synthetic_examples: int = Field(default=120, ge=10, le=5000)
    augmenter: TinyModelAugmenter = TinyModelAugmenter.TEMPLATE
    llm_model: str = Field(default="gpt-4o-mini", max_length=100)
    approval_rate: float = Field(default=1.0, ge=0.1, le=1.0)
    max_preview_rows: int = Field(default=60, ge=10, le=400)
    error_tolerance: TinyModelErrorTolerance = TinyModelErrorTolerance.BALANCED


class TinyModelDatasetPreviewRow(BaseModel):
    text: str
    metadata: dict[str, str] = Field(default_factory=dict)
    label: str | None = None
    target: float | None = None
    source: str


class TinyModelDatasetPreviewResponse(BaseModel):
    project_id: str
    stage: TinyModelProjectStage
    seed_count: int
    synthetic_proposed_count: int
    synthetic_approved_count: int
    final_record_count: int
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    preview_rows: list[TinyModelDatasetPreviewRow] = Field(default_factory=list)


class TinyModelDatasetApprovalRequest(BaseModel):
    approve: bool = True


class TinyModelMicroReviewRequest(BaseModel):
    approved_indices: list[int] = Field(default_factory=list)
    rejected_indices: list[int] = Field(default_factory=list)


class TinyModelTrainingRequest(BaseModel):
    k_folds: int = Field(default=5, ge=2, le=10)
    sweep_level: TinyModelSweepLevel = TinyModelSweepLevel.STANDARD
    max_sweep_candidates: int | None = Field(default=None, ge=3, le=120)
    quality_threshold: float = Field(default=0.9, ge=0.5, le=1.0)


class TinyModelRunSubmitResponse(BaseModel):
    run_id: str
    status: TinyModelRunStatus
    message: str


class TinyModelEvent(BaseModel):
    timestamp: datetime
    event_type: str
    message: str
    payload: dict[str, Any] | None = None


class TinyModelDatasetVersion(BaseModel):
    version_id: str
    created_at: datetime
    record_count: int
    synthetic_count: int
    llm_labeled_count: int
    label_counts: dict[str, int] = Field(default_factory=dict)
    notes: str


class TinyModelCandidateResult(BaseModel):
    name: str
    task_type: TinyModelTaskType
    family: str
    is_baseline: bool
    sweep_stage: str
    hyperparameters: dict[str, Any] = Field(default_factory=dict)
    metrics_mean: dict[str, float]
    metrics_std: dict[str, float]
    quality_score: float
    overfit_risk: str
    latency_ms: float
    interpretability_score: float
    artifact_size_bytes: int
    details: dict[str, Any] = Field(default_factory=dict)


class TinyModelVersionResponse(BaseModel):
    version_id: str
    run_id: str
    task_type: TinyModelTaskType
    winner_policy: TinyModelWinnerPolicy
    candidate_name: str
    published_at: datetime
    artifact_path: str
    metrics_mean: dict[str, float]
    metrics_std: dict[str, float]
    quality_score: float
    latency_ms: float
    interpretability_score: float
    artifact_size_bytes: int
    details: dict[str, Any] = Field(default_factory=dict)


class TinyModelRunResponse(BaseModel):
    run_id: str
    project_id: str | None = None
    project_name: str
    task_type: TinyModelTaskType
    sweep_level: TinyModelSweepLevel = TinyModelSweepLevel.STANDARD
    max_sweep_candidates: int | None = None
    status: TinyModelRunStatus
    created_at: datetime
    updated_at: datetime
    coverage_summary: dict[str, Any] = Field(default_factory=dict)
    dataset_versions: list[TinyModelDatasetVersion] = Field(default_factory=list)
    candidates: list[TinyModelCandidateResult] = Field(default_factory=list)
    selected_candidate: str | None = None
    selected_policy: TinyModelWinnerPolicy | None = None
    published_versions: list[TinyModelVersionResponse] = Field(default_factory=list)
    events: list[TinyModelEvent] = Field(default_factory=list)
    error_message: str | None = None


class TinyModelProjectResponse(BaseModel):
    project_id: str
    project_name: str
    task_type: TinyModelTaskType
    problem_brief: str
    stage: TinyModelProjectStage
    sample_record_count: int
    approved_record_count: int
    latest_run_id: str | None = None
    created_at: datetime
    updated_at: datetime


class TinyModelSampleUploadResponse(BaseModel):
    project_id: str
    stage: TinyModelProjectStage
    sample_record_count: int


class TinyModelWinnerSelectionRequest(BaseModel):
    winner_policy: TinyModelWinnerPolicy
    quality_threshold: float = Field(default=0.9, ge=0.5, le=1.0)


class TinyModelPredictRequest(BaseModel):
    inputs: list[str] = Field(..., min_length=1, max_length=200)
    candidate_name: str | None = Field(default=None, description="Test a specific candidate")


class TinyModelPredictResponse(BaseModel):
    run_id: str
    version_id: str
    candidate_name: str
    predictions: list[Any]
    probabilities: list[dict[str, float]] | None = None
