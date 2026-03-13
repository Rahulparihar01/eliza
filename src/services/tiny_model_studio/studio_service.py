"""
Tiny Model Studio service.

This module provides an isolated sklearn/numpy implementation for:
- sample dataset generation (classification / regression / clustering),
- optional LLM-assisted synthetic augmentation,
- coverage enforcement for required feature values,
- parallel candidate training/evaluation with k-fold CV,
- winner policy selection (best vs lightest),
- model artifact publishing and inference.
"""

import json
import pickle
import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Self

import numpy as np
from openai import OpenAI
from sklearn.base import BaseEstimator, TransformerMixin, clone
from sklearn.cluster import Birch, KMeans, MiniBatchKMeans
from sklearn.ensemble import RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    adjusted_rand_score,
    classification_report,
    confusion_matrix,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.model_selection import (
    KFold,
    ParameterSampler,
    StratifiedKFold,
    cross_val_predict,
    cross_validate,
)
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


class TaskType(str, Enum):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"


class WinnerPolicy(str, Enum):
    BEST = "best"
    LIGHTEST = "lightest"


class SweepLevel(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class SparseToDenseTransformer(BaseEstimator, TransformerMixin):
    """Convert sparse matrices from TF-IDF into dense arrays for clustering models."""

    def fit(self, _x: Any, _y: Any = None) -> Self:
        return self

    def transform(self, x: Any) -> np.ndarray:
        if hasattr(x, "toarray"):
            return x.toarray()
        return np.asarray(x)


@dataclass
class DatasetVersion:
    version_id: str
    created_at: str
    record_count: int
    synthetic_count: int
    llm_labeled_count: int
    label_counts: dict[str, int]
    notes: str


@dataclass
class CandidateEvaluation:
    name: str
    task_type: TaskType
    family: str
    is_baseline: bool
    sweep_stage: str
    hyperparameters: dict[str, Any]
    metrics_mean: dict[str, float]
    metrics_std: dict[str, float]
    quality_score: float
    overfit_risk: str
    latency_ms: float
    interpretability_score: float
    artifact_size_bytes: int
    model: Any
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildResult:
    dataset_versions: list[DatasetVersion]
    coverage_summary: dict[str, Any]
    candidate_results: list[CandidateEvaluation]


class TinyModelStudioService:
    """Service that runs Tiny Model Studio build runs in-process."""

    def __init__(self, artifact_root: str | Path = "artifacts/tiny_model_studio", random_seed: int = 42):
        self.artifact_root = Path(artifact_root)
        self.random_seed = random_seed
        self.rng = np.random.default_rng(random_seed)

        self.classification_feature_space = {
            "intent": ["bug_report", "billing_issue", "feature_request", "security_incident"],
            "channel": ["email", "chat", "phone"],
            "priority": ["low", "medium", "high"],
            "region": ["us", "eu", "apac"],
        }
        self.regression_feature_space = {
            "priority": ["low", "medium", "high"],
            "complexity": ["low", "medium", "high"],
            "dependency_risk": ["low", "medium", "high"],
            "queue_size": ["small", "medium", "large"],
        }
        self.clustering_feature_space = {
            "archetype": ["cost_sensitive", "stability_first", "speed_first"],
            "channel": ["email", "chat", "phone"],
            "region": ["us", "eu", "apac"],
        }
        self.interpretability_scores = {
            "logistic_regression": 0.95,
            "multinomial_nb": 0.90,
            "ridge": 0.92,
            "random_forest_regressor": 0.65,
            "kmeans": 0.74,
            "minibatch_kmeans": 0.72,
            "birch": 0.76,
        }

    def run_build(
        self,
        task_type: TaskType,
        seed_examples: int,
        synthetic_examples: int,
        use_llm_augmentation: bool,
        llm_model: str,
        k_folds: int,
        sweep_level: SweepLevel = SweepLevel.STANDARD,
        max_sweep_candidates: int | None = None,
        approval_rate: float = 1.0,
        problem_brief: str | None = None,
        event_callback: Callable[[str, str, dict[str, Any] | None], None] | None = None,
    ) -> BuildResult:
        """Run end-to-end dataset + training build."""
        self._emit(event_callback, "seed_dataset_start", "Generating seed dataset", None)
        seed_rows = self._generate_seed_rows(task_type, seed_examples)
        seed_rows = self._deduplicate_rows(seed_rows, [])

        v1 = self._build_dataset_version(seed_rows, notes="Seed dataset snapshot (v1)")
        self._emit(
            event_callback,
            "seed_dataset_complete",
            "Seed dataset generated",
            {"record_count": len(seed_rows), "version_id": v1.version_id},
        )

        self._emit(
            event_callback,
            "augmentation_start",
            "Generating synthetic/LLM-assisted examples",
            {"synthetic_target": synthetic_examples, "use_llm_augmentation": use_llm_augmentation},
        )
        proposed_rows = self._augment_rows(
            task_type=task_type,
            synthetic_examples=synthetic_examples,
            use_llm_augmentation=use_llm_augmentation,
            llm_model=llm_model,
            problem_brief=problem_brief,
            base_rows=seed_rows,
        )
        proposed_rows = self._deduplicate_rows(proposed_rows, seed_rows)

        approved_target = round(len(proposed_rows) * approval_rate)
        approved_rows = proposed_rows[:approved_target]

        combined_rows = seed_rows + approved_rows
        combined_rows = self._ensure_coverage(task_type, combined_rows)
        coverage_summary = self._coverage_summary(task_type, combined_rows)

        v2 = self._build_dataset_version(
            combined_rows,
            notes=(
                "Augmented dataset snapshot (v2) with approved synthetic/LLM examples "
                "and enforced feature coverage"
            ),
        )
        self._emit(
            event_callback,
            "augmentation_complete",
            "Augmentation and coverage checks completed",
            {
                "proposed_count": len(proposed_rows),
                "approved_count": len(approved_rows),
                "version_id": v2.version_id,
                "coverage_ok": coverage_summary.get("all_requirements_met", False),
            },
        )

        self._emit(event_callback, "training_start", "Starting parallel candidate evaluation", None)
        candidate_results = self._evaluate_candidates(
            task_type=task_type,
            rows=combined_rows,
            k_folds=k_folds,
            sweep_level=sweep_level,
            max_sweep_candidates=max_sweep_candidates,
            event_callback=event_callback,
        )
        self._emit(
            event_callback,
            "training_complete",
            "Candidate evaluation complete",
            {"candidate_count": len(candidate_results)},
        )

        return BuildResult(
            dataset_versions=[v1, v2],
            coverage_summary=coverage_summary,
            candidate_results=candidate_results,
        )

    def prepare_sample_rows(
        self,
        task_type: TaskType,
        rows: list[dict[str, Any]],
        source: str = "user_upload",
    ) -> list[dict[str, Any]]:
        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            normalized = self._normalize_external_row(task_type, row, source=source)
            if normalized is not None:
                normalized_rows.append(normalized)
        return self._deduplicate_rows(normalized_rows, [])

    def build_dataset_preview(
        self,
        task_type: TaskType,
        problem_brief: str,
        sample_rows: list[dict[str, Any]],
        synthetic_examples: int,
        use_llm_augmentation: bool,
        llm_model: str,
        approval_rate: float = 1.0,
        max_preview_rows: int = 60,
        error_tolerance: str = "balanced",
    ) -> dict[str, Any]:
        if not sample_rows:
            raise ValueError("At least one sample row is required")

        seed_rows = self._deduplicate_rows(sample_rows, [])
        proposed_rows = self._augment_rows(
            task_type=task_type,
            synthetic_examples=synthetic_examples,
            use_llm_augmentation=use_llm_augmentation,
            llm_model=llm_model,
            problem_brief=problem_brief,
            base_rows=seed_rows,
            error_tolerance=error_tolerance,
        )
        proposed_rows = self._deduplicate_rows(proposed_rows, seed_rows)
        approved_target = max(0, min(len(proposed_rows), round(len(proposed_rows) * approval_rate)))
        approved_rows = proposed_rows[:approved_target]

        combined_rows = seed_rows + approved_rows
        combined_rows = self._ensure_coverage(task_type, combined_rows)
        coverage_summary = self._coverage_summary(task_type, combined_rows)

        return {
            "seed_count": len(seed_rows),
            "synthetic_proposed_count": len(proposed_rows),
            "synthetic_approved_count": len(approved_rows),
            "final_record_count": len(combined_rows),
            "coverage_summary": coverage_summary,
            "preview_rows": combined_rows[:max_preview_rows],
            "combined_rows": combined_rows,
        }

    def run_build_from_rows(
        self,
        task_type: TaskType,
        rows: list[dict[str, Any]],
        k_folds: int,
        sweep_level: SweepLevel = SweepLevel.STANDARD,
        max_sweep_candidates: int | None = None,
        event_callback: Callable[[str, str, dict[str, Any] | None], None] | None = None,
    ) -> BuildResult:
        if not rows:
            raise ValueError("Training rows are required")

        deduped_rows = self._deduplicate_rows(rows, [])
        if not deduped_rows:
            raise ValueError("No valid training rows found")

        self._emit(event_callback, "training_dataset_start", "Preparing approved training dataset", None)
        deduped_rows = self._ensure_coverage(task_type, deduped_rows)
        coverage_summary = self._coverage_summary(task_type, deduped_rows)
        v1 = self._build_dataset_version(
            deduped_rows,
            notes="User-approved dataset snapshot for training",
        )
        self._emit(
            event_callback,
            "training_dataset_ready",
            "Approved dataset ready for model sweep",
            {"record_count": len(deduped_rows), "version_id": v1.version_id},
        )

        self._emit(event_callback, "training_start", "Starting parallel candidate evaluation", None)
        candidate_results = self._evaluate_candidates(
            task_type=task_type,
            rows=deduped_rows,
            k_folds=k_folds,
            sweep_level=sweep_level,
            max_sweep_candidates=max_sweep_candidates,
            event_callback=event_callback,
        )
        self._emit(
            event_callback,
            "training_complete",
            "Candidate evaluation complete",
            {"candidate_count": len(candidate_results)},
        )

        return BuildResult(
            dataset_versions=[v1],
            coverage_summary=coverage_summary,
            candidate_results=candidate_results,
        )

    def select_winner(
        self,
        task_type: TaskType,
        candidates: list[CandidateEvaluation],
        winner_policy: WinnerPolicy,
        quality_threshold: float = 0.9,
    ) -> CandidateEvaluation:
        if not candidates:
            raise ValueError("No candidate results are available")

        if winner_policy == WinnerPolicy.BEST:
            return self._select_best(task_type, candidates)

        best_candidate = self._select_best(task_type, candidates)
        quality_gate = self._build_quality_gate(task_type, best_candidate.quality_score, quality_threshold)
        filtered = [c for c in candidates if quality_gate(c.quality_score)]
        if not filtered:
            filtered = [best_candidate]

        filtered.sort(
            key=lambda item: (
                item.latency_ms,
                -item.interpretability_score,
                item.artifact_size_bytes,
            )
        )
        return filtered[0]

    def publish_model(
        self,
        run_id: str,
        task_type: TaskType,
        winner_policy: WinnerPolicy,
        winner: CandidateEvaluation,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        version_id = f"model_{uuid.uuid4().hex[:10]}"
        version_dir = self.artifact_root / run_id / version_id
        version_dir.mkdir(parents=True, exist_ok=True)

        model_path = version_dir / "model.pkl"
        model_path.write_bytes(pickle.dumps(winner.model))

        payload = {
            "version_id": version_id,
            "run_id": run_id,
            "task_type": task_type.value,
            "winner_policy": winner_policy.value,
            "candidate_name": winner.name,
            "published_at": self._utcnow_iso(),
            "artifact_path": str(model_path),
            "metrics_mean": winner.metrics_mean,
            "metrics_std": winner.metrics_std,
            "quality_score": winner.quality_score,
            "latency_ms": winner.latency_ms,
            "interpretability_score": winner.interpretability_score,
            "artifact_size_bytes": winner.artifact_size_bytes,
            "details": winner.details,
        }
        if metadata:
            payload["metadata"] = metadata

        (version_dir / "metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def predict(self, model: Any, task_type: TaskType, inputs: list[str]) -> dict[str, Any]:
        if not inputs:
            raise ValueError("At least one input is required")

        if task_type == TaskType.CLASSIFICATION:
            predictions = model.predict(inputs).tolist()
            probabilities = None
            if hasattr(model, "predict_proba"):
                probs = model.predict_proba(inputs)
                classes = model.classes_.tolist()
                probabilities = [
                    {cls: float(prob) for cls, prob in zip(classes, row, strict=False)} for row in probs
                ]
            return {"predictions": predictions, "probabilities": probabilities}

        if task_type == TaskType.REGRESSION:
            predictions = [float(value) for value in model.predict(inputs).tolist()]
            return {"predictions": predictions}

        if task_type == TaskType.CLUSTERING:
            predictions = [int(value) for value in model.predict(inputs).tolist()]
            return {"predictions": predictions}

        raise ValueError(f"Unsupported task type: {task_type}")

    def serialize_candidate(self, candidate: CandidateEvaluation) -> dict[str, Any]:
        return {
            "name": candidate.name,
            "task_type": candidate.task_type.value,
            "family": candidate.family,
            "is_baseline": candidate.is_baseline,
            "sweep_stage": candidate.sweep_stage,
            "hyperparameters": candidate.hyperparameters,
            "metrics_mean": candidate.metrics_mean,
            "metrics_std": candidate.metrics_std,
            "quality_score": candidate.quality_score,
            "overfit_risk": candidate.overfit_risk,
            "latency_ms": candidate.latency_ms,
            "interpretability_score": candidate.interpretability_score,
            "artifact_size_bytes": candidate.artifact_size_bytes,
            "details": candidate.details,
        }

    def _generate_seed_rows(self, task_type: TaskType, count: int) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if task_type == TaskType.CLASSIFICATION:
            for _ in range(count):
                rows.append(self._classification_row(source="seed"))
        elif task_type == TaskType.REGRESSION:
            for _ in range(count):
                rows.append(self._regression_row(source="seed"))
        elif task_type == TaskType.CLUSTERING:
            for _ in range(count):
                rows.append(self._clustering_row(source="seed"))
        else:
            raise ValueError(f"Unsupported task type: {task_type}")
        return rows

    def _augment_rows(
        self,
        task_type: TaskType,
        synthetic_examples: int,
        use_llm_augmentation: bool,
        llm_model: str,
        problem_brief: str | None = None,
        base_rows: list[dict[str, Any]] | None = None,
        error_tolerance: str = "balanced",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        llm_count = synthetic_examples // 2 if use_llm_augmentation else 0

        if llm_count > 0:
            llm_rows = self._llm_generate_rows(
                task_type=task_type,
                count=llm_count,
                llm_model=llm_model,
                problem_brief=problem_brief,
                base_rows=base_rows,
                error_tolerance=error_tolerance,
            )
            rows.extend(llm_rows)

        remaining = max(synthetic_examples - len(rows), 0)
        for _ in range(remaining):
            if task_type == TaskType.CLASSIFICATION:
                rows.append(self._classification_row(source="template_synthetic"))
            elif task_type == TaskType.REGRESSION:
                rows.append(self._regression_row(source="template_synthetic"))
            else:
                rows.append(self._clustering_row(source="template_synthetic"))

        return rows

    def _llm_generate_rows(
        self,
        task_type: TaskType,
        count: int,
        llm_model: str,
        problem_brief: str | None = None,
        base_rows: list[dict[str, Any]] | None = None,
        error_tolerance: str = "balanced",
    ) -> list[dict[str, Any]]:
        import os

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return []

        feature_space = self._feature_space(task_type)
        sample_rows = base_rows[:8] if base_rows else []
        sample_rows_payload = [
            {
                "text": row.get("text", ""),
                "metadata": row.get("metadata", {}),
                "label": row.get("label"),
                "target": row.get("target"),
            }
            for row in sample_rows
        ]
        error_guidance = ""
        if error_tolerance != "balanced":
            tolerance_hints = {
                "false_positive": "Generate more ambiguous examples that are harder to classify correctly.",
                "false_negative": "Generate clearer, more separable examples with distinct features.",
                "over_predict": "Generate examples where the model might predict higher than actual.",
                "under_predict": "Generate examples where the model might predict lower than actual.",
                "over_segment": "Generate examples with more variation within groups.",
                "under_segment": "Generate examples with clear cluster boundaries.",
            }
            error_guidance = f"\nError tolerance preference: {tolerance_hints.get(error_tolerance, '')}\n"
        
        prompt = (
            "Generate synthetic training rows as strict JSON.\n"
            f"Task type: {task_type.value}\n"
            f"Problem brief: {problem_brief or 'N/A'}\n"
            f"Allowed feature values: {json.dumps(feature_space)}\n"
            f"Sample rows to mimic style/distribution: {json.dumps(sample_rows_payload)}\n"
            f"{error_guidance}"
            f"Return JSON only in the format: {{\"rows\": [ ... ]}} with exactly {count} rows.\n"
            "Each row must include keys: text, metadata, label, target.\n"
            "For non-classification tasks set label to null.\n"
            "For non-regression tasks set target to null.\n"
            "No markdown, no explanations."
        )

        try:
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You generate clean JSON training data for machine learning prototypes.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            content = response.choices[0].message.content or ""
            payload = json.loads(content)
            rows = payload.get("rows", [])
        except Exception:
            return []

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            normalized = self._normalize_generated_row(task_type, row, source="llm_synthetic")
            if normalized is not None:
                normalized_rows.append(normalized)
        return normalized_rows[:count]

    def _normalize_generated_row(
        self, task_type: TaskType, row: dict[str, Any], source: str
    ) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None

        text = str(row.get("text", "")).strip()
        if not text:
            return None

        metadata_raw = row.get("metadata")
        if not isinstance(metadata_raw, dict):
            metadata_raw = {}

        feature_space = self._feature_space(task_type)
        metadata: dict[str, str] = {}
        for key, allowed_values in feature_space.items():
            value = str(metadata_raw.get(key, "")).strip()
            if value not in allowed_values:
                value = str(self.rng.choice(allowed_values))
            metadata[key] = value

        label: str | None = None
        target: float | None = None

        if task_type == TaskType.CLASSIFICATION:
            label_value = row.get("label")
            label = str(label_value).strip() if label_value is not None else metadata["intent"]
            if label not in feature_space["intent"]:
                label = metadata["intent"]
        elif task_type == TaskType.REGRESSION:
            target_value = row.get("target")
            try:
                target = float(target_value)
            except (TypeError, ValueError):
                target = float(self._compute_regression_target(metadata))

        return {
            "text": text,
            "metadata": metadata,
            "label": label,
            "target": target,
            "provenance": {"source": source, "created_at": self._utcnow_iso()},
            "approved": False,
        }

    def _normalize_external_row(
        self,
        task_type: TaskType,
        row: dict[str, Any],
        source: str,
    ) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None

        text = (
            str(row.get("text") or row.get("input") or row.get("prompt") or row.get("content") or "")
            .strip()
        )
        if not text:
            return None

        feature_space = self._feature_space(task_type)
        metadata_raw = row.get("metadata")
        if not isinstance(metadata_raw, dict):
            metadata_raw = {}

        metadata: dict[str, str] = {}
        for feature_name, allowed_values in feature_space.items():
            candidate = metadata_raw.get(feature_name, row.get(feature_name))
            value = str(candidate).strip() if candidate is not None else ""
            if value not in allowed_values:
                value = str(self.rng.choice(allowed_values))
            metadata[feature_name] = value

        label: str | None = None
        target: float | None = None
        if task_type == TaskType.CLASSIFICATION:
            label_value = row.get("label") or row.get("intent")
            if label_value is not None:
                label = str(label_value).strip()
            if label not in self.classification_feature_space["intent"]:
                label = metadata["intent"]
        elif task_type == TaskType.REGRESSION:
            raw_target = row.get("target", row.get("value", row.get("score")))
            try:
                target = float(raw_target)
            except (TypeError, ValueError):
                target = float(self._compute_regression_target(metadata))

        return {
            "text": text,
            "metadata": metadata,
            "label": label,
            "target": target,
            "provenance": {"source": source, "created_at": self._utcnow_iso()},
            "approved": True,
        }

    def _classification_row(self, source: str, forced: dict[str, str] | None = None) -> dict[str, Any]:
        forced = forced or {}
        intent = forced.get("intent") or str(self.rng.choice(self.classification_feature_space["intent"]))
        channel = forced.get("channel") or str(self.rng.choice(self.classification_feature_space["channel"]))
        priority = forced.get("priority") or str(self.rng.choice(self.classification_feature_space["priority"]))
        region = forced.get("region") or str(self.rng.choice(self.classification_feature_space["region"]))

        intent_phrases = {
            "bug_report": "reports a reproducible defect after the latest release",
            "billing_issue": "cannot reconcile invoice line items for this month",
            "feature_request": "asks for workflow automation to reduce manual work",
            "security_incident": "suspects unusual login behavior and possible exposure",
        }
        text = (
            f"{channel.title()} request from {region.upper()} with {priority} priority: "
            f"the customer {intent_phrases[intent]}."
        )

        return {
            "text": text,
            "metadata": {
                "intent": intent,
                "channel": channel,
                "priority": priority,
                "region": region,
            },
            "label": intent,
            "target": None,
            "provenance": {"source": source, "created_at": self._utcnow_iso()},
            "approved": source == "seed",
        }

    def _regression_row(self, source: str, forced: dict[str, str] | None = None) -> dict[str, Any]:
        forced = forced or {}
        priority = forced.get("priority") or str(self.rng.choice(self.regression_feature_space["priority"]))
        complexity = forced.get("complexity") or str(
            self.rng.choice(self.regression_feature_space["complexity"])
        )
        dependency_risk = forced.get("dependency_risk") or str(
            self.rng.choice(self.regression_feature_space["dependency_risk"])
        )
        queue_size = forced.get("queue_size") or str(self.rng.choice(self.regression_feature_space["queue_size"]))

        metadata = {
            "priority": priority,
            "complexity": complexity,
            "dependency_risk": dependency_risk,
            "queue_size": queue_size,
        }
        target = self._compute_regression_target(metadata)

        text = (
            "Ticket profile: "
            f"priority={priority}, complexity={complexity}, dependency_risk={dependency_risk}, "
            f"queue_size={queue_size}. Estimate resolution effort."
        )

        return {
            "text": text,
            "metadata": metadata,
            "label": None,
            "target": target,
            "provenance": {"source": source, "created_at": self._utcnow_iso()},
            "approved": source == "seed",
        }

    def _clustering_row(self, source: str, forced: dict[str, str] | None = None) -> dict[str, Any]:
        forced = forced or {}
        archetype = forced.get("archetype") or str(
            self.rng.choice(self.clustering_feature_space["archetype"])
        )
        channel = forced.get("channel") or str(self.rng.choice(self.clustering_feature_space["channel"]))
        region = forced.get("region") or str(self.rng.choice(self.clustering_feature_space["region"]))

        archetype_text = {
            "cost_sensitive": "prioritizes reduced spend, budget controls, and lower operating cost",
            "stability_first": "prioritizes reliability, fewer incidents, and predictable service levels",
            "speed_first": "prioritizes faster delivery, rapid iteration, and reduced cycle time",
        }
        text = f"{channel.title()} note from {region.upper()} team that {archetype_text[archetype]}."

        return {
            "text": text,
            "metadata": {"archetype": archetype, "channel": channel, "region": region},
            "label": None,
            "target": None,
            "provenance": {"source": source, "created_at": self._utcnow_iso()},
            "approved": source == "seed",
        }

    def _compute_regression_target(self, metadata: dict[str, str]) -> float:
        base = {"low": 10.0, "medium": 24.0, "high": 48.0}[metadata["priority"]]
        complexity_adj = {"low": 4.0, "medium": 10.0, "high": 22.0}[metadata["complexity"]]
        dependency_adj = {"low": 3.0, "medium": 9.0, "high": 17.0}[metadata["dependency_risk"]]
        queue_adj = {"small": -2.0, "medium": 4.0, "large": 11.0}[metadata["queue_size"]]
        noise = float(self.rng.normal(0, 3))
        return float(max(1.0, base + complexity_adj + dependency_adj + queue_adj + noise))

    def _ensure_coverage(self, task_type: TaskType, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        feature_space = self._feature_space(task_type)
        min_count = 3
        coverage = self._count_feature_values(rows, feature_space)

        for feature_name, values in feature_space.items():
            for value in values:
                while coverage[feature_name][value] < min_count:
                    forced = {feature_name: value}
                    if task_type == TaskType.CLASSIFICATION:
                        row = self._classification_row(source="coverage_fill", forced=forced)
                    elif task_type == TaskType.REGRESSION:
                        row = self._regression_row(source="coverage_fill", forced=forced)
                    else:
                        row = self._clustering_row(source="coverage_fill", forced=forced)
                    row["approved"] = True
                    rows.append(row)
                    coverage[feature_name][value] += 1

        if task_type == TaskType.CLASSIFICATION:
            label_counts = Counter(str(row.get("label", "")) for row in rows if row.get("label"))
            for label in self.classification_feature_space["intent"]:
                while label_counts[label] < min_count:
                    row = self._classification_row(source="coverage_fill", forced={"intent": label})
                    row["approved"] = True
                    rows.append(row)
                    label_counts[label] += 1

        return rows

    def _coverage_summary(self, task_type: TaskType, rows: list[dict[str, Any]]) -> dict[str, Any]:
        feature_space = self._feature_space(task_type)
        coverage = self._count_feature_values(rows, feature_space)
        missing: list[dict[str, Any]] = []

        for feature_name, values in feature_space.items():
            for value in values:
                count = coverage[feature_name][value]
                if count < 1:
                    missing.append({"feature": feature_name, "value": value, "count": count})

        label_counts: dict[str, int] = {}
        if task_type == TaskType.CLASSIFICATION:
            label_counts = Counter(str(row.get("label", "")) for row in rows if row.get("label"))
            for label in self.classification_feature_space["intent"]:
                if label_counts.get(label, 0) < 1:
                    missing.append({"feature": "label", "value": label, "count": label_counts.get(label, 0)})

        return {
            "all_requirements_met": len(missing) == 0,
            "feature_counts": {k: dict(v) for k, v in coverage.items()},
            "label_counts": dict(label_counts),
            "missing_requirements": missing,
            "total_records": len(rows),
        }

    def _count_feature_values(
        self, rows: list[dict[str, Any]], feature_space: dict[str, list[str]]
    ) -> dict[str, dict[str, int]]:
        counts: dict[str, dict[str, int]] = {
            feature_name: defaultdict(int) for feature_name in feature_space
        }
        for row in rows:
            metadata = row.get("metadata", {})
            for feature_name in feature_space:
                value = metadata.get(feature_name)
                if value:
                    counts[feature_name][str(value)] += 1
        return counts

    def _evaluate_candidates(
        self,
        task_type: TaskType,
        rows: list[dict[str, Any]],
        k_folds: int,
        sweep_level: SweepLevel,
        max_sweep_candidates: int | None = None,
        event_callback: Callable[[str, str, dict[str, Any] | None], None] | None = None,
    ) -> list[CandidateEvaluation]:
        family_spaces = self._family_param_spaces(task_type)
        sweep_plan = self._sweep_plan(sweep_level)
        family_count = len(family_spaces)

        baseline_specs: list[dict[str, Any]] = []
        coarse_specs: list[dict[str, Any]] = []
        signature_set: set[str] = set()

        for family_name, family_config in family_spaces.items():
            baseline_params = family_config["baseline"]
            baseline_spec = {
                "name": family_name,
                "family": family_name,
                "stage": "baseline",
                "is_baseline": True,
                "hyperparameters": baseline_params,
            }
            baseline_specs.append(baseline_spec)
            signature_set.add(self._candidate_signature(family_name, baseline_params))

            sampled = self._sample_param_dicts(
                param_grid=family_config["grid"],
                n_samples=sweep_plan["coarse_per_family"],
                existing_signatures=signature_set,
                family_name=family_name,
            )
            for index, params in enumerate(sampled, start=1):
                coarse_specs.append(
                    {
                        "name": f"{family_name}__c{index}",
                        "family": family_name,
                        "stage": "coarse",
                        "is_baseline": False,
                        "hyperparameters": params,
                    }
                )

        if max_sweep_candidates is not None:
            max_sweep_candidates = max(max_sweep_candidates, family_count)
            remaining_after_baseline = max_sweep_candidates - len(baseline_specs)
            coarse_specs = coarse_specs[: max(0, remaining_after_baseline)]

        stage1_specs = baseline_specs + coarse_specs
        stage1_results = self._evaluate_candidate_specs(
            task_type=task_type,
            rows=rows,
            k_folds=k_folds,
            candidate_specs=stage1_specs,
            event_callback=event_callback,
        )

        results_by_family: dict[str, list[CandidateEvaluation]] = defaultdict(list)
        for item in stage1_results:
            results_by_family[item.family].append(item)

        refine_specs: list[dict[str, Any]] = []
        for family_name, family_results in results_by_family.items():
            family_results.sort(key=lambda item: item.quality_score, reverse=True)
            anchors = family_results[: sweep_plan["refine_from_top_per_family"]]
            family_config = family_spaces[family_name]
            refine_index = 1
            for anchor in anchors:
                refined = self._sample_refined_param_dicts(
                    param_grid=family_config["grid"],
                    anchor_params=anchor.hyperparameters,
                    n_samples=sweep_plan["refine_per_anchor"],
                    existing_signatures=signature_set,
                    family_name=family_name,
                )
                for params in refined:
                    refine_specs.append(
                        {
                            "name": f"{family_name}__r{refine_index}",
                            "family": family_name,
                            "stage": "refine",
                            "is_baseline": False,
                            "hyperparameters": params,
                        }
                    )
                    refine_index += 1

        if max_sweep_candidates is not None:
            remaining_slots = max_sweep_candidates - len(stage1_specs)
            refine_specs = refine_specs[: max(0, remaining_slots)]

        stage2_results = self._evaluate_candidate_specs(
            task_type=task_type,
            rows=rows,
            k_folds=k_folds,
            candidate_specs=refine_specs,
            event_callback=event_callback,
        )

        all_results = stage1_results + stage2_results
        all_results.sort(key=lambda item: item.quality_score, reverse=True)
        return all_results

    def _evaluate_candidate_specs(
        self,
        task_type: TaskType,
        rows: list[dict[str, Any]],
        k_folds: int,
        candidate_specs: list[dict[str, Any]],
        event_callback: Callable[[str, str, dict[str, Any] | None], None] | None = None,
    ) -> list[CandidateEvaluation]:
        if not candidate_specs:
            return []

        results: list[CandidateEvaluation] = []
        max_workers = min(4, len(candidate_specs))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for spec in candidate_specs:
                model = self._build_model(
                    task_type=task_type,
                    family_name=spec["family"],
                    hyperparameters=spec["hyperparameters"],
                )
                future = pool.submit(
                    self._evaluate_single_candidate,
                    task_type,
                    spec["name"],
                    spec["family"],
                    spec["stage"],
                    spec["is_baseline"],
                    spec["hyperparameters"],
                    model,
                    rows,
                    k_folds,
                )
                futures[future] = spec["name"]

            for future in as_completed(futures):
                candidate_name = futures[future]
                result = future.result()
                results.append(result)
                self._emit(
                    event_callback,
                    "candidate_complete",
                    f"Candidate evaluation complete: {candidate_name}",
                    {
                        "candidate": candidate_name,
                        "quality_score": result.quality_score,
                        "family": result.family,
                        "stage": result.sweep_stage,
                        "is_baseline": result.is_baseline,
                    },
                )
        return results

    def _sweep_plan(self, sweep_level: SweepLevel) -> dict[str, int]:
        plans = {
            SweepLevel.QUICK: {"coarse_per_family": 2, "refine_from_top_per_family": 1, "refine_per_anchor": 1},
            SweepLevel.STANDARD: {"coarse_per_family": 5, "refine_from_top_per_family": 2, "refine_per_anchor": 2},
            SweepLevel.DEEP: {"coarse_per_family": 10, "refine_from_top_per_family": 2, "refine_per_anchor": 4},
        }
        return plans[sweep_level]

    def _family_param_spaces(self, task_type: TaskType) -> dict[str, dict[str, dict[str, Any]]]:
        if task_type == TaskType.CLASSIFICATION:
            return {
                "logistic_regression": {
                    "baseline": {
                        "tfidf_max_features": 3000,
                        "tfidf_ngram_range": (1, 2),
                        "c": 1.0,
                        "penalty": "l2",
                        "class_weight": None,
                    },
                    "grid": {
                        "tfidf_max_features": [1500, 2500, 3500, 5000],
                        "tfidf_ngram_range": [(1, 1), (1, 2)],
                        "c": [0.05, 0.2, 0.5, 1.0, 3.0, 8.0],
                        "penalty": ["l1", "l2"],
                        "class_weight": [None, "balanced"],
                    },
                },
                "multinomial_nb": {
                    "baseline": {
                        "tfidf_max_features": 3000,
                        "tfidf_ngram_range": (1, 2),
                        "alpha": 1.0,
                    },
                    "grid": {
                        "tfidf_max_features": [1200, 2200, 3200, 4500],
                        "tfidf_ngram_range": [(1, 1), (1, 2)],
                        "alpha": [0.05, 0.1, 0.3, 0.7, 1.0, 1.5, 2.0],
                    },
                },
            }

        if task_type == TaskType.REGRESSION:
            return {
                "ridge": {
                    "baseline": {
                        "tfidf_max_features": 3000,
                        "tfidf_ngram_range": (1, 2),
                        "alpha": 1.0,
                        "solver": "auto",
                    },
                    "grid": {
                        "tfidf_max_features": [1200, 2400, 3600, 5000],
                        "tfidf_ngram_range": [(1, 1), (1, 2)],
                        "alpha": [0.01, 0.1, 0.5, 1.0, 3.0, 8.0, 15.0],
                        "solver": ["auto", "svd", "cholesky"],
                    },
                },
                "random_forest_regressor": {
                    "baseline": {
                        "tfidf_max_features": 3000,
                        "tfidf_ngram_range": (1, 2),
                        "n_estimators": 140,
                        "max_depth": None,
                        "min_samples_split": 2,
                        "min_samples_leaf": 1,
                    },
                    "grid": {
                        "tfidf_max_features": [1500, 2500, 3500],
                        "tfidf_ngram_range": [(1, 1), (1, 2)],
                        "n_estimators": [80, 120, 180, 260],
                        "max_depth": [None, 8, 16, 32],
                        "min_samples_split": [2, 4, 8],
                        "min_samples_leaf": [1, 2, 4],
                    },
                },
            }

        return {
            "kmeans": {
                "baseline": {
                    "tfidf_max_features": 512,
                    "tfidf_ngram_range": (1, 2),
                    "n_clusters": 3,
                    "n_init": 20,
                    "max_iter": 300,
                },
                "grid": {
                    "tfidf_max_features": [256, 512, 768],
                    "tfidf_ngram_range": [(1, 1), (1, 2)],
                    "n_clusters": [2, 3, 4, 5, 6],
                    "n_init": [10, 20, 30],
                    "max_iter": [200, 300, 500],
                },
            },
            "minibatch_kmeans": {
                "baseline": {
                    "tfidf_max_features": 512,
                    "tfidf_ngram_range": (1, 2),
                    "n_clusters": 3,
                    "batch_size": 64,
                    "n_init": 20,
                    "max_iter": 300,
                },
                "grid": {
                    "tfidf_max_features": [256, 512, 768],
                    "tfidf_ngram_range": [(1, 1), (1, 2)],
                    "n_clusters": [2, 3, 4, 5, 6],
                    "batch_size": [32, 64, 128, 256],
                    "n_init": [10, 20, 30],
                    "max_iter": [200, 300, 500],
                },
            },
            "birch": {
                "baseline": {
                    "tfidf_max_features": 512,
                    "tfidf_ngram_range": (1, 2),
                    "threshold": 0.5,
                    "branching_factor": 50,
                    "n_clusters": 3,
                },
                "grid": {
                    "tfidf_max_features": [256, 512, 768],
                    "tfidf_ngram_range": [(1, 1), (1, 2)],
                    "threshold": [0.25, 0.4, 0.5, 0.7, 0.9],
                    "branching_factor": [25, 50, 100],
                    "n_clusters": [2, 3, 4, 5, 6],
                },
            },
        }

    def _build_model(
        self,
        task_type: TaskType,
        family_name: str,
        hyperparameters: dict[str, Any],
    ) -> Pipeline:
        if task_type == TaskType.CLASSIFICATION:
            if family_name == "logistic_regression":
                return Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                ngram_range=tuple(hyperparameters["tfidf_ngram_range"]),
                                max_features=int(hyperparameters["tfidf_max_features"]),
                            ),
                        ),
                        (
                            "model",
                            LogisticRegression(
                                max_iter=800,
                                solver="liblinear",
                                random_state=self.random_seed,
                                C=float(hyperparameters["c"]),
                                penalty=str(hyperparameters["penalty"]),
                                class_weight=hyperparameters["class_weight"],
                            ),
                        ),
                    ]
                )
            if family_name == "multinomial_nb":
                return Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                ngram_range=tuple(hyperparameters["tfidf_ngram_range"]),
                                max_features=int(hyperparameters["tfidf_max_features"]),
                            ),
                        ),
                        ("model", MultinomialNB(alpha=float(hyperparameters["alpha"]))),
                    ]
                )

        if task_type == TaskType.REGRESSION:
            if family_name == "ridge":
                return Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                ngram_range=tuple(hyperparameters["tfidf_ngram_range"]),
                                max_features=int(hyperparameters["tfidf_max_features"]),
                            ),
                        ),
                        (
                            "model",
                            Ridge(
                                alpha=float(hyperparameters["alpha"]),
                                solver=str(hyperparameters["solver"]),
                            ),
                        ),
                    ]
                )
            if family_name == "random_forest_regressor":
                return Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                ngram_range=tuple(hyperparameters["tfidf_ngram_range"]),
                                max_features=int(hyperparameters["tfidf_max_features"]),
                            ),
                        ),
                        (
                            "model",
                            RandomForestRegressor(
                                n_estimators=int(hyperparameters["n_estimators"]),
                                random_state=self.random_seed,
                                max_depth=hyperparameters["max_depth"],
                                min_samples_split=int(hyperparameters["min_samples_split"]),
                                min_samples_leaf=int(hyperparameters["min_samples_leaf"]),
                            ),
                        ),
                    ]
                )

        if task_type == TaskType.CLUSTERING:
            if family_name == "kmeans":
                return Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                ngram_range=tuple(hyperparameters["tfidf_ngram_range"]),
                                max_features=int(hyperparameters["tfidf_max_features"]),
                            ),
                        ),
                        ("to_dense", SparseToDenseTransformer()),
                        (
                            "model",
                            KMeans(
                                n_clusters=int(hyperparameters["n_clusters"]),
                                n_init=int(hyperparameters["n_init"]),
                                max_iter=int(hyperparameters["max_iter"]),
                                random_state=self.random_seed,
                            ),
                        ),
                    ]
                )
            if family_name == "minibatch_kmeans":
                return Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                ngram_range=tuple(hyperparameters["tfidf_ngram_range"]),
                                max_features=int(hyperparameters["tfidf_max_features"]),
                            ),
                        ),
                        ("to_dense", SparseToDenseTransformer()),
                        (
                            "model",
                            MiniBatchKMeans(
                                n_clusters=int(hyperparameters["n_clusters"]),
                                batch_size=int(hyperparameters["batch_size"]),
                                n_init=int(hyperparameters["n_init"]),
                                max_iter=int(hyperparameters["max_iter"]),
                                random_state=self.random_seed,
                            ),
                        ),
                    ]
                )
            if family_name == "birch":
                return Pipeline(
                    [
                        (
                            "tfidf",
                            TfidfVectorizer(
                                ngram_range=tuple(hyperparameters["tfidf_ngram_range"]),
                                max_features=int(hyperparameters["tfidf_max_features"]),
                            ),
                        ),
                        ("to_dense", SparseToDenseTransformer()),
                        (
                            "model",
                            Birch(
                                threshold=float(hyperparameters["threshold"]),
                                branching_factor=int(hyperparameters["branching_factor"]),
                                n_clusters=int(hyperparameters["n_clusters"]),
                            ),
                        ),
                    ]
                )

        raise ValueError(f"Unsupported model family '{family_name}' for task type '{task_type.value}'")

    def _candidate_signature(self, family_name: str, params: dict[str, Any]) -> str:
        return f"{family_name}:{json.dumps(params, sort_keys=True, default=str)}"

    def _sample_param_dicts(
        self,
        param_grid: dict[str, list[Any]],
        n_samples: int,
        existing_signatures: set[str],
        family_name: str,
    ) -> list[dict[str, Any]]:
        if n_samples <= 0:
            return []

        sampled: list[dict[str, Any]] = []
        sampler = ParameterSampler(
            param_distributions=param_grid,
            n_iter=max(n_samples * 4, n_samples),
            random_state=self.random_seed,
        )
        for params in sampler:
            normalized = dict(params)
            signature = self._candidate_signature(family_name, normalized)
            if signature in existing_signatures:
                continue
            existing_signatures.add(signature)
            sampled.append(normalized)
            if len(sampled) >= n_samples:
                break
        return sampled

    def _sample_refined_param_dicts(
        self,
        param_grid: dict[str, list[Any]],
        anchor_params: dict[str, Any],
        n_samples: int,
        existing_signatures: set[str],
        family_name: str,
    ) -> list[dict[str, Any]]:
        if n_samples <= 0:
            return []

        sampled: list[dict[str, Any]] = []
        attempts = max(20, n_samples * 12)
        keys = list(param_grid.keys())

        for _ in range(attempts):
            params: dict[str, Any] = {}
            for key in keys:
                choices = param_grid[key]
                anchor_value = anchor_params.get(key, choices[0])
                if anchor_value in choices:
                    index = choices.index(anchor_value)
                    start = max(0, index - 1)
                    end = min(len(choices), index + 2)
                    neighborhood = choices[start:end]
                    params[key] = neighborhood[self.rng.integers(0, len(neighborhood))]
                else:
                    params[key] = choices[self.rng.integers(0, len(choices))]

            signature = self._candidate_signature(family_name, params)
            if signature in existing_signatures:
                continue
            existing_signatures.add(signature)
            sampled.append(params)
            if len(sampled) >= n_samples:
                break

        return sampled

    def _new_clustering_pipeline(self, clusterer: Any) -> Pipeline:
        return Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=512)),
                ("to_dense", SparseToDenseTransformer()),
                ("model", clusterer),
            ]
        )

    def _evaluate_single_candidate(
        self,
        task_type: TaskType,
        name: str,
        family: str,
        sweep_stage: str,
        is_baseline: bool,
        hyperparameters: dict[str, Any],
        model: Pipeline,
        rows: list[dict[str, Any]],
        k_folds: int,
    ) -> CandidateEvaluation:
        inputs = [self._row_to_training_text(row) for row in rows]

        result: CandidateEvaluation
        if task_type == TaskType.CLASSIFICATION:
            labels = [str(row["label"]) for row in rows]
            result = self._evaluate_classifier(name, model, inputs, labels, k_folds)
        elif task_type == TaskType.REGRESSION:
            targets = [float(row["target"]) for row in rows]
            result = self._evaluate_regressor(name, model, inputs, targets, k_folds)
        else:
            result = self._evaluate_clusterer(name, model, inputs)

        result.family = family
        result.sweep_stage = sweep_stage
        result.is_baseline = is_baseline
        result.hyperparameters = hyperparameters
        result.interpretability_score = self.interpretability_scores.get(family, result.interpretability_score)
        result.details = {
            **result.details,
            "family": family,
            "sweep_stage": sweep_stage,
            "is_baseline": is_baseline,
            "hyperparameters": hyperparameters,
        }
        return result

    def _evaluate_classifier(
        self,
        name: str,
        model: Pipeline,
        inputs: list[str],
        labels: list[str],
        requested_k: int,
    ) -> CandidateEvaluation:
        min_class_count = min(Counter(labels).values())
        k = max(2, min(requested_k, 5, min_class_count))
        cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=self.random_seed)
        scoring = {
            "precision_macro": "precision_macro",
            "recall_macro": "recall_macro",
            "f1_macro": "f1_macro",
        }
        scores = cross_validate(model, inputs, labels, cv=cv, scoring=scoring)
        preds = cross_val_predict(clone(model), inputs, labels, cv=cv)
        report = classification_report(labels, preds, output_dict=True, zero_division=0)
        label_order = sorted(set(labels))
        cm = confusion_matrix(labels, preds, labels=label_order).tolist()

        model.fit(inputs, labels)
        latency_ms = self._latency_ms(model, inputs)
        artifact_size = len(pickle.dumps(model))
        f1_mean = float(np.mean(scores["test_f1_macro"]))
        f1_std = float(np.std(scores["test_f1_macro"]))

        return CandidateEvaluation(
            name=name,
            task_type=TaskType.CLASSIFICATION,
            family="",
            is_baseline=False,
            sweep_stage="",
            hyperparameters={},
            metrics_mean={
                "precision_macro": float(np.mean(scores["test_precision_macro"])),
                "recall_macro": float(np.mean(scores["test_recall_macro"])),
                "f1_macro": f1_mean,
            },
            metrics_std={
                "precision_macro": float(np.std(scores["test_precision_macro"])),
                "recall_macro": float(np.std(scores["test_recall_macro"])),
                "f1_macro": f1_std,
            },
            quality_score=f1_mean,
            overfit_risk=self._overfit_risk_from_std(f1_std),
            latency_ms=latency_ms,
            interpretability_score=self.interpretability_scores.get(name, 0.6),
            artifact_size_bytes=artifact_size,
            model=model,
            details={
                "k_folds": k,
                "labels": label_order,
                "confusion_matrix": cm,
                "per_class_metrics": {
                    label: {
                        "precision": float(report[label]["precision"]),
                        "recall": float(report[label]["recall"]),
                        "f1_score": float(report[label]["f1-score"]),
                        "support": int(report[label]["support"]),
                    }
                    for label in label_order
                    if label in report
                },
            },
        )

    def _evaluate_regressor(
        self,
        name: str,
        model: Pipeline,
        inputs: list[str],
        targets: list[float],
        requested_k: int,
    ) -> CandidateEvaluation:
        k = max(2, min(requested_k, 5, max(2, len(inputs) // 4)))
        cv = KFold(n_splits=k, shuffle=True, random_state=self.random_seed)
        scoring = {
            "mae": "neg_mean_absolute_error",
            "rmse": "neg_root_mean_squared_error",
            "r2": "r2",
        }
        scores = cross_validate(model, inputs, targets, cv=cv, scoring=scoring)
        preds = cross_val_predict(clone(model), inputs, targets, cv=cv)

        abs_errors = np.abs(np.array(targets) - np.array(preds))
        top_error_indices = np.argsort(abs_errors)[-3:][::-1]
        top_errors = [
            {
                "index": int(idx),
                "actual": float(targets[idx]),
                "predicted": float(preds[idx]),
                "absolute_error": float(abs_errors[idx]),
                "text": inputs[idx][:180],
            }
            for idx in top_error_indices
        ]

        model.fit(inputs, targets)
        latency_ms = self._latency_ms(model, inputs)
        artifact_size = len(pickle.dumps(model))
        rmse_values = -scores["test_rmse"]
        mae_values = -scores["test_mae"]
        rmse_mean = float(np.mean(rmse_values))
        rmse_std = float(np.std(rmse_values))

        return CandidateEvaluation(
            name=name,
            task_type=TaskType.REGRESSION,
            family="",
            is_baseline=False,
            sweep_stage="",
            hyperparameters={},
            metrics_mean={
                "mae": float(np.mean(mae_values)),
                "rmse": rmse_mean,
                "r2": float(np.mean(scores["test_r2"])),
            },
            metrics_std={
                "mae": float(np.std(mae_values)),
                "rmse": rmse_std,
                "r2": float(np.std(scores["test_r2"])),
            },
            quality_score=-rmse_mean,
            overfit_risk=self._overfit_risk_from_std(rmse_std),
            latency_ms=latency_ms,
            interpretability_score=self.interpretability_scores.get(name, 0.6),
            artifact_size_bytes=artifact_size,
            model=model,
            details={
                "k_folds": k,
                "residual_summary": {
                    "p50_abs_error": float(np.quantile(abs_errors, 0.5)),
                    "p90_abs_error": float(np.quantile(abs_errors, 0.9)),
                    "max_abs_error": float(np.max(abs_errors)),
                    "largest_errors": top_errors,
                },
            },
        )

    def _evaluate_clusterer(self, name: str, model: Pipeline, inputs: list[str]) -> CandidateEvaluation:
        tfidf = model.named_steps["tfidf"]
        to_dense = model.named_steps["to_dense"]
        clusterer = model.named_steps["model"]
        features = tfidf.fit_transform(inputs)
        dense_features = to_dense.transform(features)
        clusterer.fit(dense_features)

        labels = clusterer.predict(dense_features)
        unique_labels = set(labels.tolist())
        if len(unique_labels) < 2:
            silhouette = -1.0
            davies = float("inf")
        else:
            silhouette = float(silhouette_score(dense_features, labels))
            davies = float(davies_bouldin_score(dense_features, labels))

        ari_scores = []
        if len(unique_labels) > 1:
            for _ in range(4):
                jitter = self.rng.normal(0, 0.02, dense_features.shape)
                noisy = dense_features + jitter
                alt_clusterer = clone(clusterer)
                alt_clusterer.fit(noisy)
                alt_labels = alt_clusterer.predict(noisy)
                ari_scores.append(adjusted_rand_score(labels, alt_labels))

        stability_mean = float(np.mean(ari_scores)) if ari_scores else 0.0
        stability_std = float(np.std(ari_scores)) if ari_scores else 0.0

        model.fit(inputs)
        latency_ms = self._latency_ms(model, inputs)
        artifact_size = len(pickle.dumps(model))

        quality = silhouette + (1.0 / (1.0 + davies if np.isfinite(davies) else 1000.0))

        return CandidateEvaluation(
            name=name,
            task_type=TaskType.CLUSTERING,
            family="",
            is_baseline=False,
            sweep_stage="",
            hyperparameters={},
            metrics_mean={
                "silhouette": silhouette,
                "davies_bouldin": davies if np.isfinite(davies) else 999.0,
                "stability_proxy_ari": stability_mean,
            },
            metrics_std={
                "silhouette": 0.0,
                "davies_bouldin": 0.0,
                "stability_proxy_ari": stability_std,
            },
            quality_score=float(quality),
            overfit_risk="low" if stability_mean >= 0.65 else "medium",
            latency_ms=latency_ms,
            interpretability_score=self.interpretability_scores.get(name, 0.6),
            artifact_size_bytes=artifact_size,
            model=model,
            details={
                "cluster_count": len(unique_labels),
                "cluster_sizes": dict(Counter(int(label) for label in labels.tolist())),
            },
        )

    def _select_best(self, task_type: TaskType, candidates: list[CandidateEvaluation]) -> CandidateEvaluation:
        if task_type == TaskType.REGRESSION:
            # quality_score is negative RMSE, so max() still picks lowest RMSE candidate.
            return max(candidates, key=lambda item: item.quality_score)
        return max(candidates, key=lambda item: item.quality_score)

    def _build_quality_gate(
        self, task_type: TaskType, best_quality_score: float, quality_threshold: float
    ) -> Callable[[float], bool]:
        threshold = max(0.0, min(1.0, quality_threshold))

        if task_type in {TaskType.CLASSIFICATION, TaskType.CLUSTERING}:
            minimum = best_quality_score * threshold
            return lambda score: score >= minimum

        # Regression quality_score = -RMSE. Higher is better (less negative).
        max_delta = abs(best_quality_score) * (1.0 - threshold)
        return lambda score: score >= (best_quality_score - max_delta)

    def _latency_ms(self, model: Any, inputs: list[str]) -> float:
        sample = inputs[: min(32, len(inputs))]
        if not sample:
            return 0.0
        start = time.perf_counter()
        for _ in range(5):
            model.predict(sample)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 5
        return float(round(elapsed_ms, 4))

    def _overfit_risk_from_std(self, metric_std: float) -> str:
        if metric_std <= 0.03:
            return "low"
        if metric_std <= 0.08:
            return "medium"
        return "high"

    def _row_to_training_text(self, row: dict[str, Any]) -> str:
        metadata = row.get("metadata", {})
        metadata_str = " ".join(f"{key}:{value}" for key, value in sorted(metadata.items()))
        return f"{row.get('text', '')} {metadata_str}".strip()

    def _build_dataset_version(self, rows: list[dict[str, Any]], notes: str) -> DatasetVersion:
        label_counts: dict[str, int] = {}
        if any(row.get("label") is not None for row in rows):
            label_counts = dict(Counter(str(row["label"]) for row in rows if row.get("label")))
        synthetic_count = sum(1 for row in rows if row.get("provenance", {}).get("source") != "seed")
        llm_count = sum(
            1
            for row in rows
            if str(row.get("provenance", {}).get("source", "")).startswith("llm")
        )
        return DatasetVersion(
            version_id=f"dataset_{uuid.uuid4().hex[:10]}",
            created_at=self._utcnow_iso(),
            record_count=len(rows),
            synthetic_count=synthetic_count,
            llm_labeled_count=llm_count,
            label_counts=label_counts,
            notes=notes,
        )

    def _deduplicate_rows(
        self, candidate_rows: list[dict[str, Any]], existing_rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        seen_texts = {self._normalize_text(row.get("text", "")) for row in existing_rows}
        deduped: list[dict[str, Any]] = []
        for row in candidate_rows:
            normalized = self._normalize_text(row.get("text", ""))
            if not normalized:
                continue
            if normalized in seen_texts:
                continue
            seen_texts.add(normalized)
            deduped.append(row)
        return deduped

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.strip().lower().split())

    def _feature_space(self, task_type: TaskType) -> dict[str, list[str]]:
        if task_type == TaskType.CLASSIFICATION:
            return self.classification_feature_space
        if task_type == TaskType.REGRESSION:
            return self.regression_feature_space
        if task_type == TaskType.CLUSTERING:
            return self.clustering_feature_space
        raise ValueError(f"Unsupported task type: {task_type}")

    def _emit(
        self,
        callback: Callable[[str, str, dict[str, Any] | None], None] | None,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None,
    ) -> None:
        if callback is not None:
            callback(event_type, message, payload)

    def _utcnow_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
