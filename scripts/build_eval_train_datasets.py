"""
Build train/eval dataset files (CSV + JSONL) from a source dataset.

Supported source formats:
- .jsonl (one JSON object per line)
- .csv
- .json (array or {"questions":[...]})

If no --input file is provided, starter questions are generated.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import uuid
from io import StringIO
from pathlib import Path
from typing import Any


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "eval_id",
        "question",
        "reference_answer",
        "difficulty",
        "gold_chunk_ids",
        "reference_contexts",
        "tags",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "eval_id": row.get("eval_id", ""),
                    "question": row.get("question", ""),
                    "reference_answer": row.get("reference_answer", ""),
                    "difficulty": row.get("difficulty", ""),
                    "gold_chunk_ids": json.dumps(row.get("gold_chunk_ids", []), ensure_ascii=False),
                    "reference_contexts": json.dumps(row.get("reference_contexts", []), ensure_ascii=False),
                    "tags": json.dumps(row.get("tags", []), ensure_ascii=False),
                }
            )


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    normalized["question"] = str(normalized.get("question", "")).strip()
    normalized["reference_answer"] = str(normalized.get("reference_answer", "")).strip()
    if not normalized.get("eval_id"):
        normalized["eval_id"] = str(uuid.uuid4())
    normalized["difficulty"] = str(normalized.get("difficulty", "unknown") or "unknown").strip()
    for field_name in ("gold_chunk_ids", "reference_contexts", "tags"):
        value = normalized.get(field_name, [])
        normalized[field_name] = parse_array_field(value)
    return normalized


def parse_array_field(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        delimiter = ";" if ";" in stripped else ","
        return [item.strip() for item in stripped.split(delimiter) if item.strip()]
    return [value]


def parse_input_rows(input_path: Path) -> list[dict[str, Any]]:
    content = input_path.read_text(encoding="utf-8")
    suffix = input_path.suffix.lower()

    rows: list[dict[str, Any]]
    if suffix == ".csv":
        reader = csv.DictReader(StringIO(content))
        rows = [dict(row) for row in reader]
    elif suffix == ".json":
        payload = json.loads(content)
        if isinstance(payload, dict):
            rows = payload.get("questions", [])
        elif isinstance(payload, list):
            rows = payload
        else:
            raise ValueError("Unsupported JSON payload; expected array or object with 'questions'")
    else:
        # Default to JSONL.
        rows = []
        for line in content.splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    normalized_rows = [normalize_row(row) for row in rows if isinstance(row, dict)]
    valid_rows = [
        row
        for row in normalized_rows
        if row.get("question") and row.get("reference_answer")
    ]
    if not valid_rows:
        raise ValueError("No valid rows with required fields 'question' and 'reference_answer'")
    return valid_rows


def starter_rows() -> list[dict[str, Any]]:
    base = [
        {
            "question": "What is the objective of financial reporting under FASB conceptual guidance?",
            "reference_answer": "Provide useful financial information to investors, lenders, and creditors for decision-making.",
            "difficulty": "easy",
            "gold_chunk_ids": ["starter-obj-1"],
            "tags": ["starter", "conceptual"],
        },
        {
            "question": "How should an entity classify cash flows related to operating activities?",
            "reference_answer": "Operating cash flows generally include principal revenue-producing activities and related receipts/payments.",
            "difficulty": "medium",
            "gold_chunk_ids": ["starter-cf-1"],
            "tags": ["starter", "cash-flow"],
        },
        {
            "question": "When are revenue contracts considered complete under transfer-of-control concepts?",
            "reference_answer": "When promised goods/services transfer to the customer and performance obligations are satisfied.",
            "difficulty": "medium",
            "gold_chunk_ids": ["starter-rev-1"],
            "tags": ["starter", "revenue"],
        },
        {
            "question": "What is a key disclosure objective for fair value measurements?",
            "reference_answer": "Enable users to assess valuation techniques, inputs, and the effect of fair value measurements on financial statements.",
            "difficulty": "hard",
            "gold_chunk_ids": ["starter-fv-1"],
            "tags": ["starter", "fair-value"],
        },
        {
            "question": "What does materiality generally represent in financial reporting?",
            "reference_answer": "Information is material if omitting or misstating it could influence user decisions.",
            "difficulty": "easy",
            "gold_chunk_ids": ["starter-mat-1"],
            "tags": ["starter", "materiality"],
        },
        {
            "question": "What is the basic intent of lease accounting recognition for lessees?",
            "reference_answer": "Recognize right-of-use assets and lease liabilities for most leases on the balance sheet.",
            "difficulty": "medium",
            "gold_chunk_ids": ["starter-lease-1"],
            "tags": ["starter", "leases"],
        },
    ]
    return [normalize_row(row) for row in base]


def load_rows(input_path: Path | None) -> list[dict[str, Any]]:
    if input_path is None:
        return starter_rows()
    return parse_input_rows(input_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build train/eval CSV and JSONL datasets.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Source dataset file (.jsonl, .csv, or .json). If omitted, starter questions are used.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/eval"),
        help="Output directory for generated train/eval files.",
    )
    parser.add_argument(
        "--eval-ratio",
        type=float,
        default=0.2,
        help="Fraction of rows to place in eval split (default: 0.2).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic split.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.eval_ratio <= 0 or args.eval_ratio >= 1:
        raise ValueError("--eval-ratio must be between 0 and 1")

    rows = load_rows(args.input)
    if len(rows) < 2:
        raise ValueError("Need at least 2 rows to create train/eval splits")

    rng = random.Random(args.seed)
    shuffled = rows.copy()
    rng.shuffle(shuffled)

    eval_count = max(1, round(len(shuffled) * args.eval_ratio))
    eval_rows = shuffled[:eval_count]
    train_rows = shuffled[eval_count:]
    if not train_rows:
        train_rows = eval_rows[:1]
        eval_rows = eval_rows[1:]

    output_dir: Path = args.output_dir

    # Main eval questions files are the full validated corpus used by rag-eval seeding.
    write_jsonl(output_dir / "eval_questions.jsonl", shuffled)
    write_csv(output_dir / "eval_questions.csv", shuffled)

    # Optional holdout split for dedicated offline evaluation.
    write_jsonl(output_dir / "eval_holdout_questions.jsonl", eval_rows)
    write_csv(output_dir / "eval_holdout_questions.csv", eval_rows)

    # Train split for model experimentation.
    write_jsonl(output_dir / "train_questions.jsonl", train_rows)
    write_csv(output_dir / "train_questions.csv", train_rows)

    print(f"Built datasets in {output_dir}")
    print(f"- eval_questions.jsonl ({len(shuffled)} rows)")
    print(f"- eval_questions.csv ({len(shuffled)} rows)")
    print(f"- eval_holdout_questions.jsonl ({len(eval_rows)} rows)")
    print(f"- eval_holdout_questions.csv ({len(eval_rows)} rows)")
    print(f"- train_questions.jsonl ({len(train_rows)} rows)")
    print(f"- train_questions.csv ({len(train_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
