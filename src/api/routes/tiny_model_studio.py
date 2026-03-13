"""
Tiny Model Studio API routes.

This is intentionally isolated (in-memory run/project stores) so we can ship it as a
separate feature module, similar to SOW and Content Research.
"""

import asyncio
import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from src.api.schemas.tiny_model_studio import (
    TinyModelCandidateResult,
    TinyModelDatasetApprovalRequest,
    TinyModelDatasetGenerationRequest,
    TinyModelDatasetPreviewResponse,
    TinyModelDatasetPreviewRow,
    TinyModelErrorTolerance,
    TinyModelEvent,
    TinyModelMicroReviewRequest,
    TinyModelPredictRequest,
    TinyModelPredictResponse,
    TinyModelProjectCreateRequest,
    TinyModelProjectResponse,
    TinyModelProjectStage,
    TinyModelRunCreateRequest,
    TinyModelRunResponse,
    TinyModelRunStatus,
    TinyModelRunSubmitResponse,
    TinyModelSampleUploadResponse,
    TinyModelTaskType,
    TinyModelTrainingRequest,
    TinyModelVersionResponse,
    TinyModelWinnerSelectionRequest,
)
from src.core.logging import LogCategory, get_logger
from src.middleware.authorization import AuthorizationMiddleware
from src.services.tiny_model_studio import (
    BuildResult,
    SweepLevel,
    TaskType,
    TinyModelStudioService,
    WinnerPolicy,
)

logger = get_logger(__name__, LogCategory.API)
router = APIRouter(prefix="/v1/tiny-model-studio", tags=["Tiny Model Studio"])
auth_middleware = AuthorizationMiddleware()
access_dependency = auth_middleware.require_any_permission(
    ["ai_console:access", "assistant:access", "platform:admin"]
)
studio_service = TinyModelStudioService()

# In-memory feature state (MVP-style, similar to content_research/sow)
_runs: dict[str, dict[str, Any]] = {}
_projects: dict[str, dict[str, Any]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _append_event(run_data: dict[str, Any], event_type: str, message: str, payload: dict[str, Any] | None) -> None:
    event = {
        "timestamp": _utcnow(),
        "event_type": event_type,
        "message": message,
        "payload": payload or {},
    }
    run_data["events"].append(event)
    run_data["updated_at"] = _utcnow()


def _get_run_or_404(run_id: str) -> dict[str, Any]:
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


def _get_project_or_404(project_id: str) -> dict[str, Any]:
    project = _projects.get(project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _assert_owner(item: dict[str, Any], customer_id: str) -> None:
    if item["customer_id"] != customer_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _to_project_response(project: dict[str, Any]) -> TinyModelProjectResponse:
    return TinyModelProjectResponse(
        project_id=project["project_id"],
        project_name=project["project_name"],
        task_type=TinyModelTaskType(project["task_type"]),
        problem_brief=project["problem_brief"],
        stage=TinyModelProjectStage(project["stage"]),
        sample_record_count=len(project.get("sample_rows", [])),
        approved_record_count=len(project.get("approved_rows", [])),
        latest_run_id=project.get("latest_run_id"),
        created_at=project["created_at"],
        updated_at=project["updated_at"],
    )


def _to_run_response(run: dict[str, Any]) -> TinyModelRunResponse:
    return TinyModelRunResponse(
        run_id=run["run_id"],
        project_id=run.get("project_id"),
        project_name=run["project_name"],
        task_type=TinyModelTaskType(run["task_type"]),
        sweep_level=run.get("sweep_level", "standard"),
        max_sweep_candidates=run.get("max_sweep_candidates"),
        status=TinyModelRunStatus(run["status"]),
        created_at=run["created_at"],
        updated_at=run["updated_at"],
        coverage_summary=run.get("coverage_summary", {}),
        dataset_versions=run.get("dataset_versions", []),
        candidates=[
            TinyModelCandidateResult(
                name=candidate["name"],
                task_type=TinyModelTaskType(candidate["task_type"]),
                family=candidate["family"],
                is_baseline=bool(candidate.get("is_baseline", False)),
                sweep_stage=str(candidate.get("sweep_stage", "baseline")),
                hyperparameters=candidate.get("hyperparameters", {}),
                metrics_mean=candidate["metrics_mean"],
                metrics_std=candidate["metrics_std"],
                quality_score=candidate["quality_score"],
                overfit_risk=candidate["overfit_risk"],
                latency_ms=candidate["latency_ms"],
                interpretability_score=candidate["interpretability_score"],
                artifact_size_bytes=candidate["artifact_size_bytes"],
                details=candidate.get("details", {}),
            )
            for candidate in run.get("candidates", [])
        ],
        selected_candidate=run.get("selected_candidate"),
        selected_policy=run.get("selected_policy"),
        published_versions=run.get("published_versions", []),
        events=[TinyModelEvent(**event) for event in run.get("events", [])],
        error_message=run.get("error_message"),
    )


def _parse_rows_from_file(upload_file: UploadFile, content: str) -> list[dict[str, Any]]:
    suffix = Path(upload_file.filename or "").suffix.lower()
    if suffix == ".csv":
        return [dict(row) for row in csv.DictReader(io.StringIO(content))]
    if suffix == ".json":
        payload = json.loads(content)
        rows = payload.get("rows", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("JSON payload must be an array or {\"rows\": [...]}")
        return [row for row in rows if isinstance(row, dict)]

    # Default to JSONL when extension is .jsonl or unknown
    rows: list[dict[str, Any]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _new_run_data(
    *,
    run_id: str,
    customer_id: str,
    user_id: int,
    project_name: str,
    task_type: TaskType,
    sweep_level: str,
    max_sweep_candidates: int | None,
    quality_threshold: float,
    project_id: str | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "project_id": project_id,
        "customer_id": customer_id,
        "user_id": user_id,
        "project_name": project_name,
        "task_type": task_type.value,
        "status": TinyModelRunStatus.PENDING.value,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
        "quality_threshold": quality_threshold,
        "sweep_level": sweep_level,
        "max_sweep_candidates": max_sweep_candidates,
        "candidates": [],
        "candidate_models": {},
        "dataset_versions": [],
        "coverage_summary": {},
        "events": [],
        "published_versions": [],
        "selected_model": None,
        "selected_version_id": None,
        "selected_candidate": None,
        "selected_policy": None,
        "error_message": None,
    }


def _hydrate_run_from_build(run_data: dict[str, Any], build: BuildResult) -> None:
    run_data["dataset_versions"] = [
        {
            "version_id": item.version_id,
            "created_at": item.created_at,
            "record_count": item.record_count,
            "synthetic_count": item.synthetic_count,
            "llm_labeled_count": item.llm_labeled_count,
            "label_counts": item.label_counts,
            "notes": item.notes,
        }
        for item in build.dataset_versions
    ]
    run_data["coverage_summary"] = build.coverage_summary
    run_data["candidate_models"] = {
        candidate.name: candidate.model for candidate in build.candidate_results
    }
    run_data["candidate_results_internal"] = build.candidate_results
    run_data["candidates"] = [
        studio_service.serialize_candidate(candidate) for candidate in build.candidate_results
    ]


@router.post(
    "/projects",
    response_model=TinyModelProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a tiny model project from a problem brief",
)
async def create_project(
    request: TinyModelProjectCreateRequest,
    current_user=Depends(access_dependency),
):
    project_id = f"tms_proj_{uuid.uuid4().hex[:12]}"
    project_data: dict[str, Any] = {
        "project_id": project_id,
        "customer_id": current_user.customer_id,
        "user_id": current_user.user_id,
        "project_name": request.project_name,
        "task_type": request.task_type.value,
        "problem_brief": request.problem_brief,
        "error_tolerance": request.error_tolerance.value,
        "stage": TinyModelProjectStage.PROBLEM_DEFINED.value,
        "sample_rows": [],
        "micro_preview_rows": [],
        "micro_review": {},
        "preview_rows": [],
        "generated_rows": [],
        "approved_rows": [],
        "coverage_summary": {},
        "generation_config": {},
        "latest_run_id": None,
        "created_at": _utcnow(),
        "updated_at": _utcnow(),
    }
    _projects[project_id] = project_data
    return _to_project_response(project_data)


@router.get(
    "/projects",
    response_model=list[TinyModelProjectResponse],
    summary="List my tiny model projects",
)
async def list_projects(current_user=Depends(access_dependency)):
    customer_projects = [
        project
        for project in _projects.values()
        if project.get("customer_id") == current_user.customer_id
    ]
    customer_projects.sort(key=lambda item: item["created_at"], reverse=True)
    return [_to_project_response(project) for project in customer_projects]


@router.get(
    "/projects/{project_id}",
    response_model=TinyModelProjectResponse,
    summary="Get tiny model project",
)
async def get_project(
    project_id: str,
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)
    return _to_project_response(project)


@router.post(
    "/projects/{project_id}/sample-data",
    response_model=TinyModelSampleUploadResponse,
    summary="Upload sample data (.jsonl/.json/.csv)",
)
async def upload_sample_data(
    project_id: str,
    file: UploadFile = File(...),
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)

    content = (await file.read()).decode("utf-8")
    if not content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    try:
        parsed_rows = _parse_rows_from_file(file, content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse sample data: {exc}",
        ) from exc

    task_type = TaskType(project["task_type"])
    normalized_rows = studio_service.prepare_sample_rows(
        task_type=task_type,
        rows=parsed_rows,
        source="user_upload",
    )
    if len(normalized_rows) < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 5 valid sample rows are required",
        )

    project["sample_rows"] = normalized_rows
    project["preview_rows"] = []
    project["generated_rows"] = []
    project["approved_rows"] = []
    project["coverage_summary"] = {}
    project["stage"] = TinyModelProjectStage.SAMPLE_UPLOADED.value
    project["updated_at"] = _utcnow()

    return TinyModelSampleUploadResponse(
        project_id=project_id,
        stage=TinyModelProjectStage.SAMPLE_UPLOADED,
        sample_record_count=len(normalized_rows),
    )


@router.post(
    "/projects/{project_id}/seed-sample-data",
    response_model=TinyModelSampleUploadResponse,
    summary="Generate built-in sample data for testing",
)
async def seed_sample_data(
    project_id: str,
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)

    task_type = TaskType(project["task_type"])
    row_fn = {
        TaskType.CLASSIFICATION: studio_service._classification_row,
        TaskType.REGRESSION: studio_service._regression_row,
        TaskType.CLUSTERING: studio_service._clustering_row,
    }[task_type]

    rows = [row_fn(source="seed_sample") for _ in range(30)]

    project["sample_rows"] = rows
    project["preview_rows"] = []
    project["generated_rows"] = []
    project["approved_rows"] = []
    project["coverage_summary"] = {}
    project["stage"] = TinyModelProjectStage.SAMPLE_UPLOADED.value
    project["updated_at"] = _utcnow()

    return TinyModelSampleUploadResponse(
        project_id=project_id,
        stage=TinyModelProjectStage.SAMPLE_UPLOADED,
        sample_record_count=len(rows),
    )


@router.post(
    "/projects/{project_id}/generate-micro-preview",
    response_model=TinyModelDatasetPreviewResponse,
    summary="Generate small sample batch for review",
)
async def generate_micro_preview(
    project_id: str,
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)

    sample_rows = project.get("sample_rows", [])
    if not sample_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload sample data before generating micro-preview",
        )

    task_type = TaskType(project["task_type"])
    error_tolerance = project.get("error_tolerance", "balanced")
    
    micro_rows = studio_service._augment_rows(
        task_type=task_type,
        synthetic_examples=10,
        use_llm_augmentation=False,
        llm_model="",
        problem_brief=project["problem_brief"],
        base_rows=sample_rows,
        error_tolerance=error_tolerance,
    )

    project["micro_preview_rows"] = micro_rows
    project["stage"] = TinyModelProjectStage.MICRO_PREVIEW_READY.value
    project["updated_at"] = _utcnow()

    preview_rows = [
        TinyModelDatasetPreviewRow(
            text=row.get("text", ""),
            metadata=row.get("metadata", {}),
            label=row.get("label"),
            target=row.get("target"),
            source=str(row.get("provenance", {}).get("source", "micro_preview")),
        )
        for row in micro_rows
    ]

    return TinyModelDatasetPreviewResponse(
        project_id=project_id,
        stage=TinyModelProjectStage.MICRO_PREVIEW_READY,
        seed_count=len(sample_rows),
        synthetic_proposed_count=len(micro_rows),
        synthetic_approved_count=0,
        final_record_count=len(sample_rows) + len(micro_rows),
        coverage_summary={},
        preview_rows=preview_rows,
    )


@router.post(
    "/projects/{project_id}/review-micro-preview",
    response_model=TinyModelProjectResponse,
    summary="Submit micro-preview review feedback",
)
async def review_micro_preview(
    project_id: str,
    request: TinyModelMicroReviewRequest,
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)

    micro_rows = project.get("micro_preview_rows", [])
    if not micro_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate micro-preview before submitting review",
        )

    approved_rows = [micro_rows[i] for i in request.approved_indices if i < len(micro_rows)]
    rejected_rows = [micro_rows[i] for i in request.rejected_indices if i < len(micro_rows)]

    project["micro_review"] = {
        "approved_rows": approved_rows,
        "rejected_rows": rejected_rows,
        "approved_count": len(approved_rows),
        "rejected_count": len(rejected_rows),
    }
    project["stage"] = TinyModelProjectStage.SAMPLE_UPLOADED.value
    project["updated_at"] = _utcnow()

    return _to_project_response(project)


@router.post(
    "/projects/{project_id}/generate-preview",
    response_model=TinyModelDatasetPreviewResponse,
    summary="Generate augmented dataset preview",
)
async def generate_dataset_preview(
    project_id: str,
    request: TinyModelDatasetGenerationRequest,
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)

    sample_rows = project.get("sample_rows", [])
    if not sample_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload sample data before generating preview",
        )

    micro_review = project.get("micro_review", {})
    approved_micro_rows = micro_review.get("approved_rows", [])
    base_rows = sample_rows + approved_micro_rows if approved_micro_rows else sample_rows

    task_type = TaskType(project["task_type"])
    error_tolerance = project.get("error_tolerance", "balanced")
    try:
        preview = studio_service.build_dataset_preview(
            task_type=task_type,
            problem_brief=project["problem_brief"],
            sample_rows=base_rows,
            synthetic_examples=request.synthetic_examples,
            use_llm_augmentation=request.augmenter.value == "openai",
            llm_model=request.llm_model,
            approval_rate=request.approval_rate,
            max_preview_rows=request.max_preview_rows,
            error_tolerance=error_tolerance,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    project["preview_rows"] = preview["preview_rows"]
    project["generated_rows"] = preview["combined_rows"]
    project["coverage_summary"] = preview["coverage_summary"]
    project["generation_config"] = request.model_dump()
    project["stage"] = TinyModelProjectStage.PREVIEW_READY.value
    project["updated_at"] = _utcnow()

    preview_rows = [
        TinyModelDatasetPreviewRow(
            text=row.get("text", ""),
            metadata=row.get("metadata", {}),
            label=row.get("label"),
            target=row.get("target"),
            source=str(row.get("provenance", {}).get("source", "unknown")),
        )
        for row in project["preview_rows"]
    ]

    return TinyModelDatasetPreviewResponse(
        project_id=project_id,
        stage=TinyModelProjectStage.PREVIEW_READY,
        seed_count=preview["seed_count"],
        synthetic_proposed_count=preview["synthetic_proposed_count"],
        synthetic_approved_count=preview["synthetic_approved_count"],
        final_record_count=preview["final_record_count"],
        coverage_summary=preview["coverage_summary"],
        preview_rows=preview_rows,
    )


@router.post(
    "/projects/{project_id}/approve-preview",
    response_model=TinyModelProjectResponse,
    summary="Approve or reject generated preview",
)
async def approve_dataset_preview(
    project_id: str,
    request: TinyModelDatasetApprovalRequest,
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)

    generated_rows = project.get("generated_rows", [])
    if not generated_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate a dataset preview before approval",
        )

    if request.approve:
        project["approved_rows"] = generated_rows
        project["stage"] = TinyModelProjectStage.READY_TO_TRAIN.value
    else:
        project["approved_rows"] = []
        project["stage"] = TinyModelProjectStage.SAMPLE_UPLOADED.value

    project["updated_at"] = _utcnow()
    return _to_project_response(project)


@router.post(
    "/projects/{project_id}/train",
    response_model=TinyModelRunSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Train candidates from approved dataset",
)
async def train_from_project(
    project_id: str,
    request: TinyModelTrainingRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(access_dependency),
):
    project = _get_project_or_404(project_id)
    _assert_owner(project, current_user.customer_id)

    approved_rows = project.get("approved_rows", [])
    if not approved_rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approve generated data before training",
        )

    run_id = f"tms_{uuid.uuid4().hex[:12]}"
    task_type = TaskType(project["task_type"])
    run_data = _new_run_data(
        run_id=run_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        project_name=project["project_name"],
        task_type=task_type,
        sweep_level=request.sweep_level.value,
        max_sweep_candidates=request.max_sweep_candidates,
        quality_threshold=request.quality_threshold,
        project_id=project_id,
    )
    _runs[run_id] = run_data
    _append_event(run_data, "run_created", "Build run created from approved dataset", {"project_id": project_id})

    project["latest_run_id"] = run_id
    project["stage"] = TinyModelProjectStage.TRAINING.value
    project["updated_at"] = _utcnow()

    def _emit(event_type: str, message: str, payload: dict[str, Any] | None) -> None:
        _append_event(run_data, event_type, message, payload)

    def _execute_run() -> None:
        try:
            run_data["status"] = TinyModelRunStatus.RUNNING.value
            _append_event(run_data, "run_started", "Build run started", None)

            build = studio_service.run_build_from_rows(
                task_type=task_type,
                rows=approved_rows,
                k_folds=request.k_folds,
                sweep_level=SweepLevel(request.sweep_level.value),
                max_sweep_candidates=request.max_sweep_candidates,
                event_callback=_emit,
            )

            _hydrate_run_from_build(run_data, build)
            run_data["status"] = TinyModelRunStatus.AWAITING_SELECTION.value
            _append_event(
                run_data,
                "run_ready_for_selection",
                "Build run complete. Explicit winner selection required.",
                {"candidate_count": len(build.candidate_results)},
            )

            project["stage"] = TinyModelProjectStage.TRAINED.value
            project["updated_at"] = _utcnow()
        except Exception as exc:
            logger.error(
                "tiny_model_studio_run_failed",
                run_id=run_id,
                project_id=project_id,
                error=str(exc),
                exc_info=True,
            )
            run_data["status"] = TinyModelRunStatus.FAILED.value
            run_data["error_message"] = str(exc)
            _append_event(run_data, "run_failed", "Build run failed", {"error": str(exc)})
            project["stage"] = TinyModelProjectStage.FAILED.value
            project["updated_at"] = _utcnow()

    background_tasks.add_task(_execute_run)
    return TinyModelRunSubmitResponse(
        run_id=run_id,
        status=TinyModelRunStatus.PENDING,
        message="Tiny Model Studio training accepted and queued.",
    )


@router.post(
    "/runs",
    response_model=TinyModelRunSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a tiny model build run",
)
async def create_run(
    request: TinyModelRunCreateRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(access_dependency),
):
    project: dict[str, Any] | None = None
    if request.project_id:
        project = _get_project_or_404(request.project_id)
        _assert_owner(project, current_user.customer_id)

    run_id = f"tms_{uuid.uuid4().hex[:12]}"
    task_type = TaskType(request.task_type.value)
    use_llm_augmentation = request.augmenter.value == "openai"

    run_data = _new_run_data(
        run_id=run_id,
        customer_id=current_user.customer_id,
        user_id=current_user.user_id,
        project_name=request.project_name,
        task_type=task_type,
        sweep_level=request.sweep_level.value,
        max_sweep_candidates=request.max_sweep_candidates,
        quality_threshold=request.quality_threshold,
        project_id=request.project_id,
    )
    _runs[run_id] = run_data
    _append_event(run_data, "run_created", "Build run created", {"task_type": task_type.value})

    logger.info(
        "tiny_model_studio_run_created",
        run_id=run_id,
        task_type=task_type.value,
        project_name=request.project_name,
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
    )

    if project:
        project["latest_run_id"] = run_id
        project["updated_at"] = _utcnow()

    def _emit(event_type: str, message: str, payload: dict[str, Any] | None) -> None:
        _append_event(run_data, event_type, message, payload)

    def _execute_run() -> None:
        try:
            run_data["status"] = TinyModelRunStatus.RUNNING.value
            _append_event(run_data, "run_started", "Build run started", None)

            build = studio_service.run_build(
                task_type=task_type,
                seed_examples=request.seed_examples,
                synthetic_examples=request.synthetic_examples,
                use_llm_augmentation=use_llm_augmentation,
                llm_model=request.llm_model,
                k_folds=request.k_folds,
                sweep_level=SweepLevel(request.sweep_level.value),
                max_sweep_candidates=request.max_sweep_candidates,
                approval_rate=request.approval_rate,
                problem_brief=project.get("problem_brief") if project else None,
                event_callback=_emit,
            )

            _hydrate_run_from_build(run_data, build)
            run_data["status"] = TinyModelRunStatus.AWAITING_SELECTION.value
            _append_event(
                run_data,
                "run_ready_for_selection",
                "Build run complete. Explicit winner selection required.",
                {"candidate_count": len(build.candidate_results)},
            )
        except Exception as exc:
            logger.error(
                "tiny_model_studio_run_failed",
                run_id=run_id,
                error=str(exc),
                exc_info=True,
            )
            run_data["status"] = TinyModelRunStatus.FAILED.value
            run_data["error_message"] = str(exc)
            _append_event(run_data, "run_failed", "Build run failed", {"error": str(exc)})

    background_tasks.add_task(_execute_run)
    return TinyModelRunSubmitResponse(
        run_id=run_id,
        status=TinyModelRunStatus.PENDING,
        message="Tiny Model Studio run accepted and queued.",
    )


@router.get(
    "/runs/{run_id}",
    response_model=TinyModelRunResponse,
    summary="Get run details",
)
async def get_run(
    run_id: str,
    current_user=Depends(access_dependency),
):
    run = _get_run_or_404(run_id)
    _assert_owner(run, current_user.customer_id)
    return _to_run_response(run)


@router.get(
    "/runs",
    response_model=list[TinyModelRunResponse],
    summary="List my tiny model runs",
)
async def list_runs(
    current_user=Depends(access_dependency),
):
    customer_runs = [
        run
        for run in _runs.values()
        if run.get("customer_id") == current_user.customer_id
    ]
    customer_runs.sort(key=lambda item: item["created_at"], reverse=True)
    return [_to_run_response(run) for run in customer_runs]


@router.post(
    "/runs/{run_id}/select-winner",
    response_model=TinyModelVersionResponse,
    summary="Select and publish winner model version",
)
async def select_winner(
    run_id: str,
    request: TinyModelWinnerSelectionRequest,
    current_user=Depends(access_dependency),
):
    run = _get_run_or_404(run_id)
    _assert_owner(run, current_user.customer_id)

    if run["status"] not in {
        TinyModelRunStatus.AWAITING_SELECTION.value,
        TinyModelRunStatus.COMPLETED.value,
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run is not ready for winner selection",
        )

    candidate_results = run.get("candidate_results_internal", [])
    if not candidate_results:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No candidates available")

    task_type = TaskType(run["task_type"])
    winner = studio_service.select_winner(
        task_type=task_type,
        candidates=candidate_results,
        winner_policy=WinnerPolicy(request.winner_policy.value),
        quality_threshold=request.quality_threshold,
    )

    version = studio_service.publish_model(
        run_id=run_id,
        task_type=task_type,
        winner_policy=WinnerPolicy(request.winner_policy.value),
        winner=winner,
        metadata={
            "project_name": run["project_name"],
            "customer_id": run["customer_id"],
            "selected_by_user_id": current_user.user_id,
            "project_id": run.get("project_id"),
        },
    )

    run["selected_model"] = winner.model
    run["selected_candidate"] = winner.name
    run["selected_policy"] = request.winner_policy
    run["selected_version_id"] = version["version_id"]
    run["published_versions"].append(version)
    run["status"] = TinyModelRunStatus.COMPLETED.value
    run["updated_at"] = _utcnow()
    _append_event(
        run,
        "winner_selected",
        "Winner selected and model version published",
        {
            "candidate_name": winner.name,
            "winner_policy": request.winner_policy.value,
            "version_id": version["version_id"],
        },
    )

    if run.get("project_id"):
        project = _projects.get(str(run["project_id"]))
        if project:
            project["stage"] = TinyModelProjectStage.TRAINED.value
            project["updated_at"] = _utcnow()

    logger.info(
        "tiny_model_studio_winner_selected",
        run_id=run_id,
        candidate_name=winner.name,
        winner_policy=request.winner_policy.value,
        version_id=version["version_id"],
        user_id=current_user.user_id,
    )

    return TinyModelVersionResponse(**version)


@router.post(
    "/runs/{run_id}/predict",
    response_model=TinyModelPredictResponse,
    summary="Run inference with the selected model version",
)
async def predict(
    run_id: str,
    request: TinyModelPredictRequest,
    current_user=Depends(access_dependency),
):
    run = _get_run_or_404(run_id)
    _assert_owner(run, current_user.customer_id)

    if request.candidate_name:
        candidate_models = run.get("candidate_models", {})
        model = candidate_models.get(request.candidate_name)
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Candidate '{request.candidate_name}' not found",
            )
        candidate_name = request.candidate_name
        version_id = "test"
    else:
        model = run.get("selected_model")
        version_id = run.get("selected_version_id")
        candidate_name = run.get("selected_candidate")
        if model is None or version_id is None or candidate_name is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No selected model. Select a winner first or specify candidate_name.",
            )

    task_type = TaskType(run["task_type"])
    result = studio_service.predict(model=model, task_type=task_type, inputs=request.inputs)
    return TinyModelPredictResponse(
        run_id=run_id,
        version_id=version_id,
        candidate_name=candidate_name,
        predictions=result["predictions"],
        probabilities=result.get("probabilities"),
    )


@router.get(
    "/runs/{run_id}/stream",
    summary="Stream run events over SSE",
)
async def stream_run_events(
    run_id: str,
    current_user=Depends(access_dependency),
):
    run = _get_run_or_404(run_id)
    _assert_owner(run, current_user.customer_id)

    async def _event_generator():
        index = 0
        while True:
            current = _runs.get(run_id)
            if current is None:
                break

            events = current.get("events", [])
            while index < len(events):
                payload = events[index]
                yield f"data: {json.dumps(payload, default=str)}\\n\\n"
                index += 1

            if current.get("status") in {
                TinyModelRunStatus.COMPLETED.value,
                TinyModelRunStatus.FAILED.value,
            }:
                break

            await asyncio.sleep(1)

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
