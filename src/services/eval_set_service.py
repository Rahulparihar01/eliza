"""
Eval Set Service - CRUD and validation for evaluation sets.

Supports both built-in static sets and user-uploaded sets.
"""
import csv
import json
import uuid
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.models.eval_set import EvalSet, EvalSetType, EvalSetCategory, EvalSetUsage

logger = get_logger(__name__, component="eval_set.service")

# Max limits for validation
MAX_EVAL_SET_EXAMPLES = 1000
MAX_JSONL_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
REQUIRED_QUESTION_FIELDS = {"question", "reference_answer"}
OPTIONAL_QUESTION_FIELDS = {"eval_id", "difficulty", "gold_chunk_ids", "reference_contexts", "tags"}
ALLOWED_UPLOAD_EXTENSIONS = {".jsonl", ".csv", ".json"}


class EvalSetValidationError(Exception):
    """Raised when eval set validation fails."""
    pass


class EvalSetService:
    """Service for managing evaluation sets."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============= Validation =============
    
    def validate_jsonl_content(
        self,
        content: str,
        max_examples: int = MAX_EVAL_SET_EXAMPLES,
        max_size: int = MAX_JSONL_SIZE_BYTES,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Validate JSONL content and return parsed questions + stats.
        
        Args:
            content: Raw JSONL string
            max_examples: Maximum allowed examples
            max_size: Maximum content size in bytes
            
        Returns:
            Tuple of (questions list, difficulty distribution dict)
            
        Raises:
            EvalSetValidationError: If validation fails
        """
        # Size check
        if len(content.encode('utf-8')) > max_size:
            raise EvalSetValidationError(
                f"Content exceeds maximum size of {max_size / 1024 / 1024:.1f} MB"
            )
        
        questions: List[Dict[str, Any]] = []
        difficulty_counts: Dict[str, int] = {}
        errors: List[str] = []
        
        lines = content.strip().split('\n')
        if len(lines) > max_examples:
            raise EvalSetValidationError(
                f"Too many examples ({len(lines)}). Maximum allowed: {max_examples}"
            )
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {i}: Invalid JSON - {str(e)}")
                continue
            
            # Check required fields
            missing = REQUIRED_QUESTION_FIELDS - set(row.keys())
            if missing:
                errors.append(f"Line {i}: Missing required fields: {missing}")
                continue
            
            # Ensure eval_id exists (generate if missing)
            if "eval_id" not in row or not row["eval_id"]:
                row["eval_id"] = str(uuid.uuid4())
            
            # Track difficulty distribution
            difficulty = row.get("difficulty", "unknown")
            difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
            
            questions.append(row)
        
        if errors:
            # Report first 10 errors
            error_summary = "\n".join(errors[:10])
            if len(errors) > 10:
                error_summary += f"\n... and {len(errors) - 10} more errors"
            raise EvalSetValidationError(f"Validation failed:\n{error_summary}")
        
        if not questions:
            raise EvalSetValidationError("No valid questions found in content")
        
        logger.info(
            "eval_set_validated",
            count=len(questions),
            difficulty_distribution=difficulty_counts
        )
        
        return questions, difficulty_counts

    def validate_csv_content(
        self,
        content: str,
        max_examples: int = MAX_EVAL_SET_EXAMPLES,
        max_size: int = MAX_JSONL_SIZE_BYTES,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Validate CSV content and return parsed questions + stats."""
        if len(content.encode("utf-8")) > max_size:
            raise EvalSetValidationError(
                f"Content exceeds maximum size of {max_size / 1024 / 1024:.1f} MB"
            )

        reader = csv.DictReader(StringIO(content))
        if not reader.fieldnames:
            raise EvalSetValidationError("CSV file is missing a header row")

        questions: List[Dict[str, Any]] = []
        difficulty_counts: Dict[str, int] = {}
        errors: List[str] = []

        for i, row in enumerate(reader, 2):  # row 1 is header
            if len(questions) >= max_examples:
                raise EvalSetValidationError(
                    f"Too many examples ({len(questions)}). Maximum allowed: {max_examples}"
                )

            normalized = self._normalize_question_row(row)
            missing = REQUIRED_QUESTION_FIELDS - set(normalized.keys())
            if missing:
                errors.append(f"Line {i}: Missing required fields: {missing}")
                continue

            # Ensure required values are non-empty after normalization.
            if not str(normalized.get("question", "")).strip():
                errors.append(f"Line {i}: Missing required value for 'question'")
                continue
            if not str(normalized.get("reference_answer", "")).strip():
                errors.append(f"Line {i}: Missing required value for 'reference_answer'")
                continue

            difficulty = str(normalized.get("difficulty", "unknown"))
            difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
            questions.append(normalized)

        if errors:
            error_summary = "\n".join(errors[:10])
            if len(errors) > 10:
                error_summary += f"\n... and {len(errors) - 10} more errors"
            raise EvalSetValidationError(f"Validation failed:\n{error_summary}")

        if not questions:
            raise EvalSetValidationError("No valid questions found in content")

        logger.info(
            "eval_set_validated_csv",
            count=len(questions),
            difficulty_distribution=difficulty_counts,
        )
        return questions, difficulty_counts

    def validate_json_content(
        self,
        content: str,
        max_examples: int = MAX_EVAL_SET_EXAMPLES,
        max_size: int = MAX_JSONL_SIZE_BYTES,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Validate JSON content (array/object) and return parsed questions + stats."""
        if len(content.encode("utf-8")) > max_size:
            raise EvalSetValidationError(
                f"Content exceeds maximum size of {max_size / 1024 / 1024:.1f} MB"
            )

        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise EvalSetValidationError(f"Invalid JSON: {exc}") from exc

        if isinstance(payload, dict):
            rows = payload.get("questions")
            if not isinstance(rows, list):
                raise EvalSetValidationError(
                    "JSON object must contain a 'questions' array when top-level type is object"
                )
        elif isinstance(payload, list):
            rows = payload
        else:
            raise EvalSetValidationError("JSON content must be an array or an object with 'questions'")

        if len(rows) > max_examples:
            raise EvalSetValidationError(
                f"Too many examples ({len(rows)}). Maximum allowed: {max_examples}"
            )

        questions: List[Dict[str, Any]] = []
        difficulty_counts: Dict[str, int] = {}
        errors: List[str] = []
        for i, row in enumerate(rows, 1):
            if not isinstance(row, dict):
                errors.append(f"Item {i}: Expected object but got {type(row).__name__}")
                continue

            normalized = self._normalize_question_row(row)
            missing = REQUIRED_QUESTION_FIELDS - set(normalized.keys())
            if missing:
                errors.append(f"Item {i}: Missing required fields: {missing}")
                continue

            if not str(normalized.get("question", "")).strip():
                errors.append(f"Item {i}: Missing required value for 'question'")
                continue
            if not str(normalized.get("reference_answer", "")).strip():
                errors.append(f"Item {i}: Missing required value for 'reference_answer'")
                continue

            difficulty = str(normalized.get("difficulty", "unknown"))
            difficulty_counts[difficulty] = difficulty_counts.get(difficulty, 0) + 1
            questions.append(normalized)

        if errors:
            error_summary = "\n".join(errors[:10])
            if len(errors) > 10:
                error_summary += f"\n... and {len(errors) - 10} more errors"
            raise EvalSetValidationError(f"Validation failed:\n{error_summary}")

        if not questions:
            raise EvalSetValidationError("No valid questions found in content")

        logger.info(
            "eval_set_validated_json",
            count=len(questions),
            difficulty_distribution=difficulty_counts,
        )
        return questions, difficulty_counts

    def validate_dataset_content(
        self,
        content: str,
        filename: Optional[str] = None,
        max_examples: int = MAX_EVAL_SET_EXAMPLES,
        max_size: int = MAX_JSONL_SIZE_BYTES,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Validate uploaded eval set content across JSONL, CSV, or JSON formats.
        """
        suffix = Path(filename or "").suffix.lower()

        if suffix and suffix not in ALLOWED_UPLOAD_EXTENSIONS:
            raise EvalSetValidationError(
                f"Unsupported file format '{suffix}'. Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}"
            )

        if suffix == ".csv":
            return self.validate_csv_content(content, max_examples=max_examples, max_size=max_size)
        if suffix == ".json":
            return self.validate_json_content(content, max_examples=max_examples, max_size=max_size)

        # Default to JSONL if extension is unknown/missing.
        return self.validate_jsonl_content(content, max_examples=max_examples, max_size=max_size)

    def _normalize_question_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize parsed question payloads from JSON/CSV to a canonical dict."""
        normalized = dict(row)

        # Normalize required textual fields.
        if "question" in normalized and normalized["question"] is not None:
            normalized["question"] = str(normalized["question"]).strip()
        if "reference_answer" in normalized and normalized["reference_answer"] is not None:
            normalized["reference_answer"] = str(normalized["reference_answer"]).strip()

        # Ensure eval_id exists.
        if not normalized.get("eval_id"):
            normalized["eval_id"] = str(uuid.uuid4())

        # Default difficulty when omitted.
        difficulty = normalized.get("difficulty")
        normalized["difficulty"] = str(difficulty).strip() if difficulty else "unknown"

        # Parse array-like optional fields when coming from CSV.
        for field_name in ("gold_chunk_ids", "reference_contexts", "tags"):
            if field_name in normalized:
                normalized[field_name] = self._parse_optional_array_field(normalized[field_name])

        return normalized

    def _parse_optional_array_field(self, value: Any) -> List[Any]:
        """Parse CSV/string list-like fields into arrays."""
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

            # Try JSON list first.
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass

            delimiter = ";" if ";" in stripped else ","
            return [item.strip() for item in stripped.split(delimiter) if item.strip()]

        # Fallback for scalar values.
        return [value]
    
    # ============= CRUD Operations =============
    
    def create_eval_set(
        self,
        customer_id: Optional[str],
        name: str,
        questions: List[Dict[str, Any]],
        domain: str = "fasb",
        description: Optional[str] = None,
        set_type: EvalSetType = EvalSetType.UPLOADED,
        category: EvalSetCategory = EvalSetCategory.GENERAL,
        tags: Optional[List[str]] = None,
        is_built_in: bool = False,
        user_id: Optional[int] = None,
        difficulty_distribution: Optional[Dict[str, int]] = None,
    ) -> EvalSet:
        """Create a new eval set."""
        # Calculate difficulty distribution if not provided
        if difficulty_distribution is None:
            difficulty_distribution = {}
            for q in questions:
                diff = q.get("difficulty", "unknown")
                difficulty_distribution[diff] = difficulty_distribution.get(diff, 0) + 1
        
        eval_set = EvalSet(
            customer_id=customer_id,
            name=name,
            description=description,
            domain=domain,
            set_type=set_type,
            category=category,
            questions=questions,
            example_count=len(questions),
            difficulty_distribution=difficulty_distribution,
            tags=tags,
            is_built_in=is_built_in,
            created_by_user_id=user_id,
        )
        
        self.db.add(eval_set)
        self.db.commit()
        self.db.refresh(eval_set)
        
        logger.info(
            "eval_set_created",
            eval_set_id=eval_set.id,
            name=name,
            set_type=set_type.value,
            example_count=len(questions)
        )
        
        return eval_set
    
    def get_eval_set(self, eval_set_id: int) -> Optional[EvalSet]:
        """Get an eval set by ID."""
        return self.db.query(EvalSet).filter(EvalSet.id == eval_set_id).first()
    
    def get_eval_set_for_customer(
        self,
        eval_set_id: int,
        customer_id: str
    ) -> Optional[EvalSet]:
        """
        Get an eval set, ensuring customer has access.
        
        Customer can access:
        - Their own uploaded sets
        - All static/built-in sets (customer_id IS NULL)
        """
        return self.db.query(EvalSet).filter(
            EvalSet.id == eval_set_id,
            or_(
                EvalSet.customer_id == customer_id,
                EvalSet.customer_id.is_(None)  # Static sets
            )
        ).first()
    
    def list_eval_sets(
        self,
        customer_id: str,
        domain: Optional[str] = None,
        set_type: Optional[EvalSetType] = None,
        category: Optional[EvalSetCategory] = None,
        include_static: bool = True,
    ) -> List[EvalSet]:
        """
        List eval sets accessible to a customer.
        
        Returns both customer's uploaded sets and static sets.
        """
        conditions = []
        
        # Customer's own sets OR static sets
        if include_static:
            conditions.append(
                or_(
                    EvalSet.customer_id == customer_id,
                    EvalSet.customer_id.is_(None)
                )
            )
        else:
            conditions.append(EvalSet.customer_id == customer_id)
        
        if domain:
            conditions.append(EvalSet.domain == domain)
        
        if set_type:
            conditions.append(EvalSet.set_type == set_type)
        
        if category:
            conditions.append(EvalSet.category == category)
        
        return self.db.query(EvalSet).filter(
            and_(*conditions)
        ).order_by(
            EvalSet.is_built_in.desc(),  # Built-in first
            EvalSet.set_type,            # Then by type
            EvalSet.name                 # Then alphabetically
        ).all()
    
    def update_eval_set(
        self,
        eval_set_id: int,
        customer_id: str,
        **kwargs
    ) -> Optional[EvalSet]:
        """
        Update an eval set (only uploaded sets owned by customer).
        
        Cannot modify built-in/static sets.
        """
        eval_set = self.db.query(EvalSet).filter(
            EvalSet.id == eval_set_id,
            EvalSet.customer_id == customer_id,
            EvalSet.is_built_in == False
        ).first()
        
        if not eval_set:
            return None
        
        for key, value in kwargs.items():
            if hasattr(eval_set, key) and value is not None:
                setattr(eval_set, key, value)
        
        # Recalculate stats if questions changed
        if "questions" in kwargs:
            questions = kwargs["questions"]
            eval_set.example_count = len(questions)
            difficulty_distribution = {}
            for q in questions:
                diff = q.get("difficulty", "unknown")
                difficulty_distribution[diff] = difficulty_distribution.get(diff, 0) + 1
            eval_set.difficulty_distribution = difficulty_distribution
        
        self.db.commit()
        self.db.refresh(eval_set)
        
        return eval_set
    
    def delete_eval_set(
        self,
        eval_set_id: int,
        customer_id: str
    ) -> bool:
        """
        Delete an eval set (only uploaded sets owned by customer).
        
        Cannot delete built-in/static sets.
        """
        result = self.db.query(EvalSet).filter(
            EvalSet.id == eval_set_id,
            EvalSet.customer_id == customer_id,
            EvalSet.is_built_in == False
        ).delete()
        
        self.db.commit()
        
        if result > 0:
            logger.info("eval_set_deleted", eval_set_id=eval_set_id)
            return True
        return False
    
    def get_questions(
        self,
        eval_set_id: int,
        customer_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get questions from an eval set (with pagination)."""
        eval_set = self.get_eval_set_for_customer(eval_set_id, customer_id)
        if not eval_set:
            return []
        
        questions = eval_set.questions or []
        
        if offset:
            questions = questions[offset:]
        if limit:
            questions = questions[:limit]
        
        return questions
    
    # ============= Usage Tracking =============
    
    def record_usage(
        self,
        eval_set_id: int,
        eval_run_id: int,
        example_count: int
    ) -> EvalSetUsage:
        """Record that an eval run used this eval set."""
        usage = EvalSetUsage(
            eval_set_id=eval_set_id,
            eval_run_id=eval_run_id,
            example_count_at_run=example_count
        )
        self.db.add(usage)
        self.db.commit()
        return usage
    
    # ============= Seeding Built-in Sets =============
    
    def seed_static_sets(self, force: bool = False) -> List[EvalSet]:
        """
        Seed built-in static eval sets if they don't exist.
        
        Creates curated subsets covering common RAG failure modes.
        """
        # Check if already seeded
        existing = self.db.query(EvalSet).filter(
            EvalSet.is_built_in == True
        ).count()
        
        if existing > 0 and not force:
            logger.info("static_eval_sets_already_seeded", count=existing)
            return []
        
        created_sets = []
        
        # Define the built-in sets
        BUILT_IN_SETS = [
            {
                "name": "Retrieval Quality - Core",
                "description": "Tests retrieval accuracy with questions requiring specific document sections. Focuses on whether the RAG system retrieves the correct context.",
                "category": EvalSetCategory.RETRIEVAL,
                "tags": ["retrieval", "context-accuracy", "core"],
                "filter_fn": lambda q: q.get("difficulty") in ["medium", "hard"] and len(q.get("gold_chunk_ids", [])) > 0,
                "max_count": 30,
            },
            {
                "name": "Synthesis & Grounding",
                "description": "Tests answer synthesis quality and citation compliance. Questions where the answer must be grounded in retrieved context with proper citations.",
                "category": EvalSetCategory.GROUNDING,
                "tags": ["synthesis", "citations", "grounding"],
                "filter_fn": lambda q: q.get("difficulty") in ["medium", "hard"],
                "max_count": 25,
            },
            {
                "name": "Edge Cases & Hard Questions",
                "description": "Challenging questions that test edge cases, ambiguous scenarios, and complex multi-step reasoning.",
                "category": EvalSetCategory.EDGE_CASES,
                "tags": ["hard", "edge-cases", "complex"],
                "filter_fn": lambda q: q.get("difficulty") == "hard",
                "max_count": 20,
            },
        ]
        
        # Load questions from configured path, fallback paths, or starter defaults
        try:
            from src.core.config import get_settings
            
            settings = get_settings()
            eval_path = Path(settings.rag_eval_questions_path)
            if not eval_path.exists():
                logger.warning(
                    "static_eval_seed_file_missing",
                    path=str(eval_path),
                )
                return []
            
            all_questions = []
            with open(eval_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_questions.append(json.loads(line))
            
            logger.info("loaded_questions_for_seeding", count=len(all_questions))
            if source_path:
                logger.info("seed_questions_source", path=source_path)
            else:
                logger.warning(
                    "seed_questions_source_missing_using_starter_defaults",
                )
            
            # Create each built-in set
            for set_config in BUILT_IN_SETS:
                filter_fn = set_config.pop("filter_fn")
                max_count = set_config.pop("max_count")
                
                # Filter questions
                filtered = [q for q in all_questions if filter_fn(q)]
                
                # Take up to max_count
                if len(filtered) > max_count:
                    import random
                    random.seed(42)  # Deterministic sampling
                    filtered = random.sample(filtered, max_count)
                
                if not filtered:
                    logger.warning(
                        "no_questions_for_static_set",
                        set_name=set_config["name"]
                    )
                    continue
                
                # Calculate difficulty distribution
                diff_dist = {}
                for q in filtered:
                    d = q.get("difficulty", "unknown")
                    diff_dist[d] = diff_dist.get(d, 0) + 1
                
                eval_set = EvalSet(
                    customer_id=None,  # Static sets have no owner
                    name=set_config["name"],
                    description=set_config["description"],
                    domain="fasb",
                    set_type=EvalSetType.STATIC,
                    category=set_config["category"],
                    questions=filtered,
                    example_count=len(filtered),
                    difficulty_distribution=diff_dist,
                    tags=set_config["tags"],
                    is_built_in=True,
                    created_by_user_id=None,
                )
                
                self.db.add(eval_set)
                created_sets.append(eval_set)
                
                logger.info(
                    "static_eval_set_created",
                    name=set_config["name"],
                    count=len(filtered)
                )
            
            self.db.commit()
            
            for s in created_sets:
                self.db.refresh(s)
            
            return created_sets
            
        except Exception as e:
            logger.error(f"Failed to seed static eval sets: {e}", exc_info=True)
            self.db.rollback()
            return []

    def _load_seed_questions_with_fallback(self, preferred_path: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Load seed questions from configured path or known fallbacks.
        Returns (questions, source_path). source_path is None for generated defaults.
        """
        project_root = Path(__file__).resolve().parents[2]
        configured = Path(preferred_path)

        candidate_paths = [
            configured,
            project_root / "data" / "eval" / "eval_questions.jsonl",
            project_root / "data" / "eval" / "eval_questions.csv",
            project_root / "data" / "eval" / "eval_questions.json",
            Path("/app/eval/eval_questions.jsonl"),
            Path("/app/eval/eval_questions.csv"),
            Path("/app/eval/eval_questions.json"),
            Path("/app/data/eval/eval_questions.jsonl"),
            Path("/app/data/eval/eval_questions.csv"),
            Path("/app/data/eval/eval_questions.json"),
        ]

        deduped_paths: List[Path] = []
        seen: set[str] = set()
        for path in candidate_paths:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            deduped_paths.append(path)

        for path in deduped_paths:
            if not path.exists() or not path.is_file():
                continue
            try:
                content = path.read_text(encoding="utf-8")
                questions, _difficulty_dist = self.validate_dataset_content(content, filename=path.name)
                return questions, str(path)
            except Exception as exc:
                logger.warning(
                    "seed_questions_candidate_invalid",
                    path=str(path),
                    error=str(exc),
                )

        return self._build_default_seed_questions(), None

    def _build_default_seed_questions(self) -> List[Dict[str, Any]]:
        """Generate a minimal starter eval dataset when no seed file is present."""
        starter_rows = [
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
                "question": "When are revenue contracts typically considered complete under core transfer-of-control concepts?",
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
                "question": "Why do entities provide accounting policy notes?",
                "reference_answer": "To explain significant accounting methods, judgments, and assumptions used in preparing statements.",
                "difficulty": "easy",
                "gold_chunk_ids": ["starter-note-1"],
                "tags": ["starter", "disclosure"],
            },
            {
                "question": "What is one purpose of segment reporting disclosures?",
                "reference_answer": "To help users evaluate performance and risk across different business activities or economic environments.",
                "difficulty": "hard",
                "gold_chunk_ids": ["starter-seg-1"],
                "tags": ["starter", "segments"],
            },
            {
                "question": "How should management explain significant estimates in MD&A-style narratives?",
                "reference_answer": "Describe estimation uncertainty, assumptions, and sensitivity where changes could materially affect results.",
                "difficulty": "hard",
                "gold_chunk_ids": ["starter-est-1"],
                "tags": ["starter", "estimates"],
            },
            {
                "question": "What is the basic intent of lease accounting recognition for lessees?",
                "reference_answer": "Recognize right-of-use assets and lease liabilities for most leases on the balance sheet.",
                "difficulty": "medium",
                "gold_chunk_ids": ["starter-lease-1"],
                "tags": ["starter", "leases"],
            },
            {
                "question": "How do impairment disclosures support investors?",
                "reference_answer": "They provide context on asset write-down triggers, measurement assumptions, and financial impact.",
                "difficulty": "hard",
                "gold_chunk_ids": ["starter-imp-1"],
                "tags": ["starter", "impairment"],
            },
        ]

        normalized: List[Dict[str, Any]] = []
        for row in starter_rows:
            normalized.append(self._normalize_question_row(row))
        return normalized
    
    def ensure_static_sets_exist(self) -> int:
        """Ensure static sets are seeded. Returns count of existing/created sets."""
        existing = self.db.query(EvalSet).filter(
            EvalSet.is_built_in == True
        ).count()
        
        if existing == 0:
            created = self.seed_static_sets()
            return len(created)
        
        return existing
