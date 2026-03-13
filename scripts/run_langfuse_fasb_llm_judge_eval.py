#!/usr/bin/env python3
"""
Run FASB workspace evals as a Langfuse experiment with LLM-as-a-judge.

What this script does:
1) Loads eval questions from JSONL
2) Selects an evaluation subset (balanced-available, calibration, or quotas)
3) Creates a Langfuse dataset and dataset items
4) Runs a Langfuse experiment on those items
5) Uses an independent judge model (default: gpt-4.1) to score outputs
6) Writes a JSON summary and a human-review CSV for manual adjudication
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import dotenv_values
from langfuse import get_client
from langfuse.experiment import Evaluation
from openai import OpenAI

# Ensure repository root is importable when script is executed directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.fasb_service import get_fasb_service


def _load_env(repo_root: Path, langfuse_host: str) -> None:
    """Load environment values for local execution."""
    docker_env = repo_root / "docker/.env"
    if docker_env.exists():
        values = dotenv_values(docker_env)
        for key, value in values.items():
            if value is not None and value != "":
                os.environ.setdefault(key, value)

    # Force host-accessible Langfuse URL for local script execution.
    os.environ["LANGFUSE_HOST"] = langfuse_host
    os.environ["LANGFUSE_BASE_URL"] = langfuse_host
    os.environ.setdefault("LANGFUSE_PUBLIC_URL", langfuse_host)
    os.environ.setdefault("LANGFUSE_ENABLED", "true")

    # When running outside Docker, container hostnames are not resolvable.
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or "@postgres:" in database_url:
        os.environ["DATABASE_URL"] = "postgresql://user:password@localhost:5432/ai_enablement"


def _read_questions(path: Path) -> List[Dict[str, Any]]:
    questions: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            row = json.loads(line)
            questions.append(
                {
                    "eval_id": row.get("eval_id", f"q-{idx}"),
                    "question": row["question"],
                    "reference_answer": row["reference_answer"],
                    "difficulty": row.get("difficulty", "unknown"),
                    "gold_chunk_ids": row.get("gold_chunk_ids", []),
                }
            )
    return questions


def _select_balanced_available(questions: List[Dict[str, Any]], seed: int) -> List[Dict[str, Any]]:
    """
    Select best-available balanced set:
    - Include all medium/hard
    - Add equal number of easy items
    """
    rng = random.Random(seed)
    easy = [q for q in questions if q.get("difficulty") == "easy"]
    non_easy = [q for q in questions if q.get("difficulty") in {"medium", "hard"}]

    if not non_easy:
        return rng.sample(easy, min(10, len(easy)))

    easy_needed = min(len(easy), len(non_easy))
    easy_pick = rng.sample(easy, easy_needed)
    selected = non_easy + easy_pick
    rng.shuffle(selected)
    return selected


def _select_calibration(questions: List[Dict[str, Any]], seed: int, size: int) -> List[Dict[str, Any]]:
    """
    Build a human-calibration candidate set:
    - Always include all medium/hard
    - Fill remainder with random easy up to target size
    """
    rng = random.Random(seed)
    easy = [q for q in questions if q.get("difficulty") == "easy"]
    non_easy = [q for q in questions if q.get("difficulty") in {"medium", "hard"}]

    if size <= len(non_easy):
        return rng.sample(non_easy, size)

    remainder = size - len(non_easy)
    easy_pick = rng.sample(easy, min(remainder, len(easy)))
    selected = non_easy + easy_pick
    rng.shuffle(selected)
    return selected


def _select_quota(
    questions: List[Dict[str, Any]],
    seed: int,
    easy_count: int,
    medium_count: int,
    hard_count: int,
    allow_replacement: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Select an explicit quota by difficulty.

    If requested count exceeds available pool and allow_replacement=True,
    sample with replacement for the deficit.
    """
    rng = random.Random(seed)
    pools = {
        "easy": [q for q in questions if q.get("difficulty") == "easy"],
        "medium": [q for q in questions if q.get("difficulty") == "medium"],
        "hard": [q for q in questions if q.get("difficulty") == "hard"],
    }
    targets = {"easy": easy_count, "medium": medium_count, "hard": hard_count}

    selected: List[Dict[str, Any]] = []
    replacement_counts: Dict[str, int] = {}

    for difficulty, target in targets.items():
        if target <= 0:
            continue

        pool = pools.get(difficulty, [])
        if not pool:
            raise ValueError(
                f"No questions available for difficulty '{difficulty}', "
                f"cannot satisfy target={target}."
            )

        if target <= len(pool):
            picked = rng.sample(pool, target)
        else:
            if not allow_replacement:
                raise ValueError(
                    f"Not enough '{difficulty}' questions: requested={target}, available={len(pool)}"
                )
            replacement_counts[difficulty] = target - len(pool)
            picked = list(pool)
            picked.extend(rng.choice(pool) for _ in range(target - len(pool)))

        # Copy dicts so repeated picks do not alias the same object.
        selected.extend(dict(item) for item in picked)

    rng.shuffle(selected)
    selection_meta = {
        "targets": targets,
        "available": {k: len(v) for k, v in pools.items()},
        "allow_replacement": allow_replacement,
        "replacement_counts": replacement_counts,
    }
    return selected, selection_meta


def _strip_sources(answer: str) -> str:
    if not answer:
        return ""
    match = re.search(r"\n\nSources:\n[\s\S]*?$", answer)
    return answer[: match.start()] if match else answer


def _clamp_score(value: Any, default: float = 0.0) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, score))


def _difficulty_distribution(items: List[Dict[str, Any]]) -> Dict[str, int]:
    return dict(Counter(item.get("difficulty", "unknown") for item in items))


def _extract_item_input(item: Any) -> Dict[str, Any]:
    # Langfuse dataset item -> object with .input
    if hasattr(item, "input"):
        value = getattr(item, "input")
        return value if isinstance(value, dict) else {"question": str(value)}

    # Local experiment item -> dict with "input"
    if isinstance(item, dict):
        value = item.get("input", {})
        return value if isinstance(value, dict) else {"question": str(value)}

    return {"question": str(item)}


def _extract_item_metadata(item: Any) -> Dict[str, Any]:
    if hasattr(item, "metadata"):
        value = getattr(item, "metadata")
        return value if isinstance(value, dict) else {}
    if isinstance(item, dict):
        value = item.get("metadata", {})
        return value if isinstance(value, dict) else {}
    return {}


def _create_or_get_dataset(
    langfuse_client: Any,
    dataset_name: str,
    description: str,
    metadata: Dict[str, Any],
) -> Any:
    try:
        langfuse_client.create_dataset(
            name=dataset_name,
            description=description,
            metadata=metadata,
        )
    except Exception as exc:  # noqa: BLE001
        # Dataset may already exist. Safe to continue.
        if "already exists" not in str(exc).lower() and "409" not in str(exc):
            raise

    return langfuse_client.get_dataset(name=dataset_name)


def _upsert_dataset_items(
    langfuse_client: Any,
    dataset_name: str,
    items: List[Dict[str, Any]],
    source_path: str,
) -> None:
    for idx, item in enumerate(items):
        sample_id = f"{item['eval_id']}__sample_{idx + 1}"
        metadata = {
            "eval_id": item["eval_id"],
            "sample_n": idx + 1,
            "difficulty": item.get("difficulty"),
        }
        try:
            langfuse_client.create_dataset_item(
                dataset_name=dataset_name,
                input={
                    "question": item["question"],
                    "eval_id": item["eval_id"],
                    "sample_id": sample_id,
                    "difficulty": item.get("difficulty"),
                },
                expected_output=item["reference_answer"],
                metadata=metadata,
            )
        except Exception as exc:  # noqa: BLE001
            # Item may already exist (idempotent behavior for reruns)
            if "already exists" in str(exc).lower() or "409" in str(exc):
                continue
            raise


def _write_human_review_csv(path: Path, item_results: List[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "eval_id",
                "sample_id",
                "difficulty",
                "question",
                "expected_answer",
                "model_answer",
                "judge_overall",
                "judge_verdict",
                "judge_pass",
                "judge_reason",
                "human_pass",
                "human_score",
                "human_reason",
            ],
        )
        writer.writeheader()

        for item_result in item_results:
            item = item_result.item
            output = item_result.output or {}
            evaluations = item_result.evaluations or []

            input_data = _extract_item_input(item)
            metadata = _extract_item_metadata(item)
            expected_output = (
                item.get("expected_output")
                if isinstance(item, dict)
                else getattr(item, "expected_output", None)
            )

            eval_map = {ev.name: ev for ev in evaluations if hasattr(ev, "name")}
            judge_overall = getattr(eval_map.get("judge_overall"), "value", None)
            judge_verdict = getattr(eval_map.get("judge_verdict"), "value", None)
            judge_pass = getattr(eval_map.get("judge_pass"), "value", None)
            judge_reason = getattr(eval_map.get("judge_overall"), "comment", None)

            answer = output.get("answer", "") if isinstance(output, dict) else str(output)

            writer.writerow(
                {
                    "eval_id": metadata.get("eval_id") or input_data.get("eval_id"),
                    "sample_id": metadata.get("sample_id") or input_data.get("sample_id"),
                    "difficulty": metadata.get("difficulty") or input_data.get("difficulty"),
                    "question": input_data.get("question", ""),
                    "expected_answer": expected_output or "",
                    "model_answer": answer,
                    "judge_overall": judge_overall,
                    "judge_verdict": judge_verdict,
                    "judge_pass": judge_pass,
                    "judge_reason": judge_reason or "",
                    "human_pass": "",
                    "human_score": "",
                    "human_reason": "",
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FASB Langfuse LLM-as-judge eval.")
    parser.add_argument(
        "--questions-path",
        type=Path,
        default=Path("data/eval/eval_questions.jsonl"),
        help="Path to eval questions JSONL file",
    )
    parser.add_argument(
        "--mode",
        choices=["balanced_available", "calibration", "quota"],
        default="balanced_available",
        help="Subset selection strategy",
    )
    parser.add_argument(
        "--calibration-size",
        type=int,
        default=40,
        help="Target size when mode=calibration",
    )
    parser.add_argument("--easy-count", type=int, default=20, help="Easy quota when mode=quota")
    parser.add_argument("--medium-count", type=int, default=20, help="Medium quota when mode=quota")
    parser.add_argument("--hard-count", type=int, default=20, help="Hard quota when mode=quota")
    parser.add_argument(
        "--allow-replacement",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow sampling with replacement when quota exceeds available items",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--langfuse-host",
        type=str,
        default="http://localhost:3060",
        help="Langfuse host URL",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default="gpt-4.1",
        help="OpenAI model for LLM-as-judge",
    )
    parser.add_argument(
        "--judge-temperature",
        type=float,
        default=0.0,
        help="Judge model temperature",
    )
    parser.add_argument(
        "--judge-pass-threshold",
        type=float,
        default=0.75,
        help="Threshold on judge_overall for judge_pass=1",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=3,
        help="Experiment max concurrency",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default=None,
        help="Optional dataset name override",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path("data/eval/langfuse_reports"),
        help="Directory for JSON/CSV outputs",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _load_env(repo_root, args.langfuse_host)

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
        raise RuntimeError("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are required")

    questions_path = args.questions_path
    if not questions_path.is_absolute():
        questions_path = repo_root / questions_path
    if not questions_path.exists():
        raise FileNotFoundError(f"Questions file not found: {questions_path}")

    all_questions = _read_questions(questions_path)
    selection_meta: Dict[str, Any] = {}
    if args.mode == "balanced_available":
        selected = _select_balanced_available(all_questions, seed=args.seed)
    elif args.mode == "calibration":
        selected = _select_calibration(all_questions, seed=args.seed, size=args.calibration_size)
    else:
        selected, selection_meta = _select_quota(
            all_questions,
            seed=args.seed,
            easy_count=args.easy_count,
            medium_count=args.medium_count,
            hard_count=args.hard_count,
            allow_replacement=args.allow_replacement,
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dataset_name = args.dataset_name or f"fasb_{args.mode}_{timestamp}"
    run_name = f"fasb_llm_judge_{args.mode}_{timestamp}"
    experiment_name = "fasb-workspace-llm-as-judge"

    print(f"dataset_name={dataset_name}")
    print(f"run_name={run_name}")
    print(f"questions_selected={len(selected)}")
    print(f"difficulty_distribution={_difficulty_distribution(selected)}")
    print(f"judge_model={args.judge_model}")
    if selection_meta:
        print(f"selection_meta={selection_meta}")

    langfuse_client = get_client()
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    fasb_service = get_fasb_service()

    dataset = _create_or_get_dataset(
        langfuse_client=langfuse_client,
        dataset_name=dataset_name,
        description=(
            "FASB workspace evaluation dataset for Langfuse experiment runner "
            f"({args.mode}, seed={args.seed})."
        ),
        metadata={
            "source": str(questions_path),
            "mode": args.mode,
            "seed": args.seed,
            "selection_distribution": _difficulty_distribution(selected),
            "selection_meta": selection_meta or None,
        },
    )
    _upsert_dataset_items(
        langfuse_client=langfuse_client,
        dataset_name=dataset_name,
        items=selected,
        source_path=str(questions_path),
    )
    # Refresh so dataset.items includes newly created items.
    dataset = langfuse_client.get_dataset(name=dataset_name)
    print(f"dataset_items_loaded={len(dataset.items)}")

    def task(item: Any) -> Dict[str, Any]:
        item_input = _extract_item_input(item)
        question = item_input.get("question", "").strip()
        if not question:
            raise ValueError("Missing question in experiment item input")

        rag = fasb_service.answer(question)
        full_answer = rag.get("answer", "")
        answer_text = _strip_sources(full_answer)

        return {
            "answer": full_answer,
            "answer_text": answer_text,
            "sources": rag.get("sources", []),
            "contexts_used": rag.get("contexts_used"),
            "model": rag.get("model"),
        }

    def llm_judge_evaluator(
        *,
        input: Any,
        output: Any,
        expected_output: Any,
        metadata: Optional[Dict[str, Any]],
        **_: Dict[str, Any],
    ) -> List[Evaluation]:
        item_input = input if isinstance(input, dict) else {"question": str(input)}
        question = item_input.get("question", "")
        expected = expected_output or ""
        answer = ""
        if isinstance(output, dict):
            answer = output.get("answer_text") or output.get("answer") or ""
        else:
            answer = str(output)

        prompt = (
            "You are an expert evaluator for FASB RAG answers.\n"
            "Evaluate the assistant answer against the expected answer.\n"
            "Return JSON with these fields exactly:\n"
            "{\n"
            '  "correctness": 0.0-1.0,\n'
            '  "completeness": 0.0-1.0,\n'
            '  "grounding": 0.0-1.0,\n'
            '  "overall": 0.0-1.0,\n'
            '  "verdict": "pass" | "partial" | "fail",\n'
            '  "reason": "one short paragraph"\n'
            "}\n\n"
            f"Question:\n{question}\n\n"
            f"Expected answer:\n{expected}\n\n"
            f"Assistant answer:\n{answer}\n"
        )

        resp = openai_client.chat.completions.create(
            model=args.judge_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=args.judge_temperature,
            response_format={"type": "json_object"},
        )
        payload = json.loads(resp.choices[0].message.content or "{}")

        correctness = _clamp_score(payload.get("correctness"), default=0.0)
        completeness = _clamp_score(payload.get("completeness"), default=0.0)
        grounding = _clamp_score(payload.get("grounding"), default=0.0)
        overall = _clamp_score(payload.get("overall"), default=0.0)
        verdict = str(payload.get("verdict", "fail")).strip().lower()
        reason = str(payload.get("reason", "")).strip()

        if verdict not in {"pass", "partial", "fail"}:
            verdict = "pass" if overall >= args.judge_pass_threshold else "fail"

        judge_pass = 1.0 if overall >= args.judge_pass_threshold and verdict != "fail" else 0.0

        return [
            Evaluation(
                name="judge_overall",
                value=overall,
                comment=reason,
                data_type="NUMERIC",
                metadata={"difficulty": (metadata or {}).get("difficulty")},
            ),
            Evaluation(name="judge_correctness", value=correctness, data_type="NUMERIC"),
            Evaluation(name="judge_completeness", value=completeness, data_type="NUMERIC"),
            Evaluation(name="judge_grounding", value=grounding, data_type="NUMERIC"),
            Evaluation(name="judge_verdict", value=verdict, data_type="CATEGORICAL"),
            Evaluation(name="judge_pass", value=judge_pass, data_type="BOOLEAN"),
        ]

    def citation_format_evaluator(
        *,
        output: Any,
        **_: Dict[str, Any],
    ) -> Evaluation:
        answer = ""
        if isinstance(output, dict):
            answer = output.get("answer", "")
        else:
            answer = str(output)
        has_citation = 1.0 if re.search(r"\[\d+\]", answer or "") else 0.0
        return Evaluation(
            name="citation_format",
            value=has_citation,
            data_type="BOOLEAN",
            comment="Checks whether answer includes citation markers like [1].",
        )

    def run_aggregate_evaluator(*, item_results: List[Any], **_: Dict[str, Any]) -> List[Evaluation]:
        overall_scores: List[float] = []
        pass_flags: List[float] = []
        for item_result in item_results:
            for ev in item_result.evaluations or []:
                if ev.name == "judge_overall":
                    overall_scores.append(float(ev.value))
                elif ev.name == "judge_pass":
                    pass_flags.append(float(ev.value))

        if not overall_scores:
            return []

        mean_overall = sum(overall_scores) / len(overall_scores)
        pass_rate = (sum(pass_flags) / len(pass_flags)) if pass_flags else 0.0

        return [
            Evaluation(
                name="run_judge_overall_mean",
                value=mean_overall,
                data_type="NUMERIC",
                comment=f"Average judge_overall across {len(overall_scores)} items.",
            ),
            Evaluation(
                name="run_judge_pass_rate",
                value=pass_rate,
                data_type="NUMERIC",
                comment=f"Pass ratio across {len(pass_flags)} items.",
            ),
        ]

    experiment_result = dataset.run_experiment(
        name=experiment_name,
        run_name=run_name,
        description=(
            f"FASB workspace run using {args.mode} selection "
            f"and {args.judge_model} as LLM judge."
        ),
        task=task,
        evaluators=[llm_judge_evaluator, citation_format_evaluator],
        run_evaluators=[run_aggregate_evaluator],
        max_concurrency=args.max_concurrency,
        metadata={
            "judge_model": args.judge_model,
            "judge_pass_threshold": args.judge_pass_threshold,
            "mode": args.mode,
            "seed": args.seed,
            "dataset_name": dataset_name,
        },
    )
    langfuse_client.flush()

    # Build summary report
    item_results = experiment_result.item_results or []
    run_evals = experiment_result.run_evaluations or []

    judge_pass_values: List[float] = []
    judge_overall_values: List[float] = []
    verdicts: Counter = Counter()
    by_difficulty_pass: Dict[str, List[float]] = {}

    for item_result in item_results:
        metadata = _extract_item_metadata(item_result.item)
        diff = str(metadata.get("difficulty", "unknown"))
        evals = {ev.name: ev for ev in (item_result.evaluations or [])}
        pass_val = float(getattr(evals.get("judge_pass"), "value", 0.0))
        overall_val = float(getattr(evals.get("judge_overall"), "value", 0.0))
        verdict = str(getattr(evals.get("judge_verdict"), "value", "unknown"))

        judge_pass_values.append(pass_val)
        judge_overall_values.append(overall_val)
        verdicts[verdict] += 1
        by_difficulty_pass.setdefault(diff, []).append(pass_val)

    report = {
        "experiment_name": experiment_name,
        "run_name": run_name,
        "dataset_name": dataset_name,
        "dataset_run_id": experiment_result.dataset_run_id,
        "dataset_run_url": experiment_result.dataset_run_url,
        "judge_model": args.judge_model,
        "selection_mode": args.mode,
        "selection_meta": selection_meta,
        "questions_selected": len(selected),
        "selected_distribution": _difficulty_distribution(selected),
        "items_executed": len(item_results),
        "judge_pass_rate": (sum(judge_pass_values) / len(judge_pass_values)) if judge_pass_values else 0.0,
        "judge_overall_mean": (sum(judge_overall_values) / len(judge_overall_values)) if judge_overall_values else 0.0,
        "judge_verdict_counts": dict(verdicts),
        "difficulty_pass_rate": {
            diff: (sum(vals) / len(vals) if vals else 0.0) for diff, vals in by_difficulty_pass.items()
        },
        "run_level_evaluations": [
            {
                "name": ev.name,
                "value": ev.value,
                "comment": ev.comment,
            }
            for ev in run_evals
        ],
    }

    args.report_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = args.report_dir / f"{run_name}.json"
    review_csv_path = args.report_dir / f"{run_name}_human_review.csv"

    report_json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_human_review_csv(review_csv_path, item_results)

    print(f"dataset_run_id={experiment_result.dataset_run_id}")
    print(f"dataset_run_url={experiment_result.dataset_run_url}")
    print(f"judge_pass_rate={report['judge_pass_rate']:.4f}")
    print(f"judge_overall_mean={report['judge_overall_mean']:.4f}")
    print(f"judge_verdict_counts={report['judge_verdict_counts']}")
    print(f"report_json={report_json_path}")
    print(f"human_review_csv={review_csv_path}")


if __name__ == "__main__":
    main()

