"""
RAG Evaluation Service

Full RAG evaluation with Langfuse tracing and RAGAS metrics.
Integrates with the existing FASB service for RAG operations.
"""
import asyncio
import json
import math
import random
import re
import statistics
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI
import sqlalchemy as sa
from sqlalchemy.orm import Session

from src.core.config import get_settings
from src.core.logging import get_logger
from src.models.ragflow_domain import RAGFlowDomain
from src.models.rag_eval import (
    RAGEvalRun,
    RAGEvalResult,
    RAGEvalTelemetryEvent,
    EvalRunStatus,
    EvalVerdict,
    EvalSource,
)
from src.services.fasb_service import get_fasb_service, FASBContext
from src.services.citation_validation_service import CitationValidationService
from src.services.langfuse_service import get_langfuse_service
from src.services.workspace_rag_backend import get_workspace_prompt_template

logger = get_logger(__name__, component="rag_eval.service")


class RAGEvalService:
    """
    Service for running RAG evaluations with Langfuse tracing.
    
    Features:
    - Stratified or random sampling of evaluation questions
    - RAGAS metrics (factual correctness, faithfulness, context precision/recall)
    - Citation compliance checking
    - LLM-as-judge evaluation
    - Langfuse observability
    - SSE telemetry events
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.langfuse_service = get_langfuse_service()
        
        # Initialize OpenAI client for async judging
        self._async_client: Optional[AsyncOpenAI] = None
        
        # Citation validation (text-first, VLM fallback only when text missing)
        self._citation_validator = CitationValidationService()
    
    @property
    def async_client(self) -> AsyncOpenAI:
        """Lazy initialization of async OpenAI client."""
        if self._async_client is None:
            self._async_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._async_client
    
    # ============= Question Loading =============
    
    def load_eval_questions(
        self,
        path: Optional[Path] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Load evaluation questions from JSONL file.
        
        Args:
            path: Path to JSONL file (defaults to settings)
            limit: Maximum questions to load
            
        Returns:
            List of question dictionaries
        """
        if path is None:
            path = Path(self.settings.rag_eval_questions_path)
        
        questions = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if limit and i >= limit:
                        break
                    row = json.loads(line)
                    questions.append({
                        "eval_id": row.get("eval_id", str(i)),
                        "question": row["question"],
                        "expected_answer": row["reference_answer"],
                        "difficulty": row.get("difficulty", "unknown"),
                        "gold_chunk_ids": row.get("gold_chunk_ids", []),
                    })
            
            logger.info(
                "eval_questions_loaded",
                path=str(path),
                count=len(questions)
            )
            return questions
            
        except Exception as e:
            logger.error(f"Failed to load eval questions: {e}", exc_info=True)
            raise ValueError(f"Failed to load eval questions: {str(e)}")
    
    def select_questions(
        self,
        questions: List[Dict],
        sample_size: Optional[int] = None,
        difficulty_counts: Optional[Dict[str, int]] = None,
        seed: int = 42,
    ) -> List[Dict]:
        """
        Select questions either by stratified difficulty or random sample.
        
        Args:
            questions: All available questions
            sample_size: Random sample size (ignored if difficulty_counts provided)
            difficulty_counts: {"easy": N, "medium": M, "hard": K}
            seed: Random seed for reproducibility
            
        Returns:
            Selected questions
        """
        rng = random.Random(seed)
        
        # Stratified sampling by difficulty
        if difficulty_counts:
            by_diff: Dict[str, List[Dict]] = {}
            for q in questions:
                by_diff.setdefault(q["difficulty"], []).append(q)
            
            selected: List[Dict] = []
            for diff, count in difficulty_counts.items():
                pool = by_diff.get(diff, [])
                if not pool:
                    logger.warning(f"No questions found for difficulty='{diff}'")
                    continue
                if len(pool) < count:
                    logger.warning(
                        f"Requested {count} '{diff}' samples but only {len(pool)} available"
                    )
                selected.extend(rng.sample(pool, min(count, len(pool))))
            
            rng.shuffle(selected)
            return selected
        
        # Random sampling
        if sample_size is None or sample_size <= 0:
            return questions
        
        if sample_size >= len(questions):
            return questions
        
        return rng.sample(questions, sample_size)
    
    def get_questions_preview(
        self,
        sample_count: int = 5
    ) -> Dict[str, Any]:
        """Get a preview of available questions."""
        questions = self.load_eval_questions()
        
        by_diff: Dict[str, int] = {}
        for q in questions:
            diff = q.get("difficulty", "unknown")
            by_diff[diff] = by_diff.get(diff, 0) + 1
        
        # Sample a few for preview
        sample = random.sample(questions, min(sample_count, len(questions)))
        
        return {
            "total_available": len(questions),
            "by_difficulty": by_diff,
            "sample_questions": sample
        }
    
    # ============= Evaluation Core =============
    
    def _citation_compliance(self, response: str, num_contexts: int) -> int:
        """Check citation compliance in response."""
        text = (response or "").strip().lower()
        if text in {"i don't know.", "i don't know"}:
            return 1  # IDK is compliant
        
        citations = [int(c) for c in re.findall(r"\[(\d+)\]", response or "")]
        if not citations:
            return 0
        
        return int(all(1 <= c <= num_contexts for c in citations))
    
    async def _judge_response(
        self,
        question: str,
        expected_answer: str,
        model_response: str
    ) -> Dict[str, str]:
        """Use LLM to judge if model response is correct."""
        prompt = f"""Compare the model response to the expected answer and determine if it's correct.

Consider the response correct if it:
1. Contains the key information from the expected answer
2. Is factually accurate
3. Adequately addresses the question asked

Question: {question}

Expected Answer: {expected_answer}

Model Response: {model_response}

Respond with JSON only: {{"verdict": "pass" or "fail", "reason": "brief explanation"}}"""
        
        try:
            resp = await self.async_client.chat.completions.create(
                model=self.settings.rag_eval_judge_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(resp.choices[0].message.content)
            return {
                "verdict": result.get("verdict", "fail"),
                "reason": result.get("reason", "")
            }
        except Exception as e:
            logger.warning(f"Judge response failed: {e}")
            return {"verdict": "error", "reason": f"Judge error: {str(e)}"}
    
    async def _score_metrics(
        self,
        question: str,
        reference: str,
        response: str,
        contexts: List[str],
    ) -> Dict[str, float]:
        """
        Score response using RAGAS-style metrics.
        
        Simplified scoring using LLM-as-judge for each metric.
        """
        scores: Dict[str, float] = {}
        
        # Factual Correctness - how factually accurate is the response?
        try:
            fc_prompt = f"""Rate the factual correctness of the response compared to the reference on a scale of 0-1.

Reference: {reference}
Response: {response}

Output JSON: {{"score": 0.0-1.0, "reason": "brief"}}"""
            
            fc_resp = await self.async_client.chat.completions.create(
                model=self.settings.rag_eval_judge_model,
                messages=[{"role": "user", "content": fc_prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            fc_data = json.loads(fc_resp.choices[0].message.content)
            scores["factual_correctness"] = float(fc_data.get("score", 0))
        except Exception as e:
            logger.warning(f"Factual correctness scoring failed: {e}")
            scores["factual_correctness"] = float("nan")
        
        # Faithfulness - is response faithful to retrieved contexts?
        try:
            context_text = "\n".join(contexts[:5])  # Limit context length
            faith_prompt = f"""Rate how faithful the response is to the provided contexts on a scale of 0-1.
The response should only contain information that can be derived from the contexts.

Contexts:
{context_text}

Response: {response}

Output JSON: {{"score": 0.0-1.0, "reason": "brief"}}"""
            
            faith_resp = await self.async_client.chat.completions.create(
                model=self.settings.rag_eval_judge_model,
                messages=[{"role": "user", "content": faith_prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            faith_data = json.loads(faith_resp.choices[0].message.content)
            scores["faithfulness"] = float(faith_data.get("score", 0))
        except Exception as e:
            logger.warning(f"Faithfulness scoring failed: {e}")
            scores["faithfulness"] = float("nan")
        
        # Context Precision - are retrieved contexts relevant?
        try:
            cp_prompt = f"""Rate how relevant the retrieved contexts are to answering the question on a scale of 0-1.

Question: {question}
Contexts: {context_text}

Output JSON: {{"score": 0.0-1.0, "reason": "brief"}}"""
            
            cp_resp = await self.async_client.chat.completions.create(
                model=self.settings.rag_eval_judge_model,
                messages=[{"role": "user", "content": cp_prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            cp_data = json.loads(cp_resp.choices[0].message.content)
            scores["context_precision"] = float(cp_data.get("score", 0))
        except Exception as e:
            logger.warning(f"Context precision scoring failed: {e}")
            scores["context_precision"] = float("nan")
        
        # Context Recall - do contexts contain the expected answer?
        try:
            cr_prompt = f"""Rate how well the retrieved contexts cover the information needed for the reference answer on a scale of 0-1.

Reference Answer: {reference}
Contexts: {context_text}

Output JSON: {{"score": 0.0-1.0, "reason": "brief"}}"""
            
            cr_resp = await self.async_client.chat.completions.create(
                model=self.settings.rag_eval_judge_model,
                messages=[{"role": "user", "content": cr_prompt}],
                temperature=0,
                response_format={"type": "json_object"}
            )
            cr_data = json.loads(cr_resp.choices[0].message.content)
            scores["context_recall"] = float(cr_data.get("score", 0))
        except Exception as e:
            logger.warning(f"Context recall scoring failed: {e}")
            scores["context_recall"] = float("nan")
        
        return scores
    
    def _query_fasb_rag(self, question: str) -> Dict[str, Any]:
        """
        Query FASB RAG.
        
        Returns:
            Dict with answer, contexts, and citations
        """
        fasb_service = get_fasb_service()
        
        # Run the RAG pipeline
        contexts = fasb_service.retrieve(question)
        reranked_contexts = fasb_service.rerank(question, contexts)
        result = fasb_service.answer(question)
        
        return {
            "answer": result.get("answer", ""),
            "contexts": reranked_contexts,
            "citations": [c.citation for c in reranked_contexts],
        }
    
    def _get_fasb_system_prompt(self) -> str:
        """Return the FASB RAG system prompt for logging."""
        return """You are an assistant that answers questions about FASB Accounting Standards Codification (ASC).
Use ONLY the provided context. If the answer isn't in the context, say "I don't know."
When you state facts, cite sources like [1], [2] referring to the numbered context items.

FORMATTING RULES:
- Use **bold** for key terms and requirements (e.g., **no preference**, **consistently**)
- Use bullet points (- ) when listing multiple requirements or items
- Keep answers clear, structured, and authoritative
- Cite sources inline where relevant [1], [2], etc."""
    
    
    def _create_results_markdown(self, results: List["RAGEvalResult"]) -> str:
        """Create a markdown summary of evaluation results."""
        lines = ["# RAG Evaluation Results\n"]
        
        pass_count = sum(1 for r in results if r.verdict and r.verdict.value == "pass")
        fail_count = sum(1 for r in results if r.verdict and r.verdict.value == "fail")
        total = len(results)
        
        lines.append(f"**Total Questions:** {total}")
        lines.append(f"**Pass:** {pass_count} | **Fail:** {fail_count}")
        lines.append(f"**Pass Rate:** {(pass_count/total*100) if total else 0:.1f}%\n")
        lines.append("---\n")
        
        for i, r in enumerate(results, 1):
            verdict_emoji = "✅" if r.verdict and r.verdict.value == "pass" else "❌"
            lines.append(f"## Question {i} {verdict_emoji}\n")
            lines.append(f"**Difficulty:** {r.difficulty or 'N/A'}\n")
            lines.append(f"### Question")
            lines.append(f"```\n{r.question}\n```\n")
            lines.append(f"### Expected Answer")
            lines.append(f"```\n{r.expected_answer}\n```\n")
            lines.append(f"### Model Response")
            lines.append(f"```\n{r.model_response}\n```\n")
            lines.append(f"### Verdict: **{r.verdict.value.upper() if r.verdict else 'N/A'}**")
            if r.verdict_reason:
                lines.append(f"**Reason:** {r.verdict_reason}\n")
            lines.append(f"### Metrics")
            lines.append(f"| Metric | Score |")
            lines.append(f"|--------|-------|")
            lines.append(f"| Factual Correctness | {r.factual_correctness:.2f if r.factual_correctness else 'N/A'} |")
            lines.append(f"| Faithfulness | {r.faithfulness:.2f if r.faithfulness else 'N/A'} |")
            lines.append(f"| Context Precision | {r.context_precision:.2f if r.context_precision else 'N/A'} |")
            lines.append(f"| Context Recall | {r.context_recall:.2f if r.context_recall else 'N/A'} |")
            lines.append(f"| Citation Compliance | {r.citation_compliance} |")
            lines.append(f"| Contexts Retrieved | {r.contexts_count} |")
            lines.append(f"| Processing Time | {r.processing_time_ms}ms |")
            lines.append(f"\n**Citations Used:** {', '.join(r.citations) if r.citations else 'None'}\n")
            lines.append("---\n")
        
        return "\n".join(lines)
    
    async def _evaluate_single(
        self,
        item: Dict,
        idx: int,
        total: int,
        eval_run_id: int,
        validate_citations: bool = False,
        run_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> RAGEvalResult:
        """
        Evaluate a single question.
        
        Args:
            item: Question dictionary
            idx: Question index
            total: Total questions
            eval_run_id: Primary key of the parent evaluation run
            validate_citations: Whether to run citation page validation
            
        Returns:
            RAGEvalResult model instance
        """
        question = item["question"]
        start_time = time.time()
        
        # Query RAG
        loop = asyncio.get_event_loop()
        try:
            rag_result = await loop.run_in_executor(
                None,
                self._query_fasb_rag,
                question
            )
        except Exception as exc:
            logger.error(f"[{idx+1}/{total}] RAG error: {exc}")
            result = RAGEvalResult(
                eval_run_id=eval_run_id,
                eval_id=item["eval_id"],
                question_index=idx,
                question=question,
                expected_answer=item["expected_answer"],
                difficulty=item.get("difficulty"),
                model_response="",
                verdict=EvalVerdict.ERROR,
                verdict_reason=f"RAG error: {exc}",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )
            return result
        
        # Judge the response
        judgment = await self._judge_response(
            question,
            item["expected_answer"],
            rag_result["answer"]
        )
        
        # Score metrics
        context_texts = [c.text if isinstance(c, FASBContext) else c for c in rag_result["contexts"]]
        metric_scores = await self._score_metrics(
            question=question,
            reference=item["expected_answer"],
            response=rag_result["answer"],
            contexts=context_texts,
        )
        
        # Citation compliance
        citation_ok = self._citation_compliance(
            response=rag_result["answer"],
            num_contexts=len(rag_result["contexts"]),
        )
        
        # Citation page validation (text-first, VLM fallback only when text missing)
        # Only run if validate_citations is enabled (can be slow, requires PDF files)
        citation_validations = []
        citation_page_score = None
        if validate_citations:
            citation_validations = await self._citation_validator.validate_contexts(
                contexts=rag_result["contexts"],
                question=question,
                answer=rag_result["answer"],
            )
            citation_page_score = self._citation_validator.aggregate_score(citation_validations)
        
        processing_time = int((time.time() - start_time) * 1000)
        
        logger.info(
            f"[{idx+1}/{total}] {judgment['verdict'].upper()}: {question[:50]}..."
        )
        
        # Map verdict string to enum
        verdict_map = {
            "pass": EvalVerdict.PASS,
            "fail": EvalVerdict.FAIL,
            "error": EvalVerdict.ERROR,
        }
        
        result = RAGEvalResult(
            eval_run_id=eval_run_id,
            eval_id=item["eval_id"],
            question_index=idx,
            question=question,
            expected_answer=item["expected_answer"],
            difficulty=item.get("difficulty"),
            model_response=rag_result["answer"],
            verdict=verdict_map.get(judgment["verdict"], EvalVerdict.FAIL),
            verdict_reason=judgment.get("reason", ""),
            citations=rag_result.get("citations", []),
            citation_compliance=citation_ok,
            citation_page_validations=citation_validations,
            citation_page_score=citation_page_score,
            contexts_count=len(rag_result["contexts"]),
            factual_correctness=metric_scores.get("factual_correctness"),
            faithfulness=metric_scores.get("faithfulness"),
            context_precision=metric_scores.get("context_precision"),
            context_recall=metric_scores.get("context_recall"),
            processing_time_ms=processing_time,
        )

        self.langfuse_service.trace_eval_question(
            run_id=run_id or str(eval_run_id),
            question_id=item["eval_id"],
            question=question,
            expected_answer=item["expected_answer"],
            model_response=rag_result["answer"],
            metrics={
                "factual_correctness": metric_scores.get("factual_correctness"),
                "faithfulness": metric_scores.get("faithfulness"),
                "context_precision": metric_scores.get("context_precision"),
                "context_recall": metric_scores.get("context_recall"),
                "citation_compliance": citation_ok,
                "citation_page_accuracy": citation_page_score,
            },
            verdict=judgment.get("verdict"),
            customer_id=customer_id,
            domain=domain,
        )
        
        return result
    
    def _emit_telemetry(
        self,
        eval_run_id: int,
        event_type: str,
        stage_name: str = None,
        message: str = None,
        progress: float = None,
        data: Dict = None,
    ):
        """Emit telemetry event for SSE streaming.
        
        Accepts the run's primary key (int) instead of the ORM object
        to avoid ObjectDeletedError after session commits.
        """
        event = RAGEvalTelemetryEvent(
            eval_run_id=eval_run_id,
            event_type=event_type,
            stage_name=stage_name,
            message=message,
            progress_percentage=progress,
            data=data,
        )
        # Telemetry is best-effort: never let it break the main eval transaction.
        try:
            self.db.add(event)
            self.db.commit()
        except Exception:
            self.db.rollback()
    
    @staticmethod
    def _safe_mean(values: List[float]) -> float:
        """Calculate mean, ignoring NaN values."""
        cleaned = [v for v in values if isinstance(v, (int, float)) and not math.isnan(v)]
        if not cleaned:
            return float("nan")
        return statistics.fmean(cleaned)
    
    @staticmethod
    def _sanitize_for_json(obj):
        """Convert NaN values to None for JSON serialization (PostgreSQL JSON doesn't accept NaN)."""
        if isinstance(obj, dict):
            return {k: RAGEvalService._sanitize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [RAGEvalService._sanitize_for_json(v) for v in obj]
        elif isinstance(obj, float) and math.isnan(obj):
            return None
        return obj

    def _build_prompt_template_snapshot(
        self,
        customer_id: str,
        domain: str,
    ) -> Optional[Dict[str, Any]]:
        """Capture the effective workspace prompt template used for this eval run."""
        try:
            workspace = self.db.query(RAGFlowDomain).filter(
                RAGFlowDomain.customer_id == customer_id,
                RAGFlowDomain.name == domain,
                RAGFlowDomain.is_active == True,
            ).first()
            if workspace:
                template = get_workspace_prompt_template(
                    workspace_id=workspace.id,
                    customer_id=customer_id,
                    db=self.db,
                )
                return template.model_dump(mode="json")
        except Exception as exc:
            logger.warning("eval_prompt_snapshot_workspace_lookup_failed", error=str(exc))

        # Fallback snapshot for legacy FASB flow.
        try:
            fasb_service = get_fasb_service()
            return {
                "workspace_id": None,
                "workspace_name": domain,
                "domain": domain,
                "system_prompt": self._get_fasb_system_prompt(),
                "model": fasb_service.chat_model,
                "temperature": 0.0,
                "max_tokens": 1024,
                "top_k": fasb_service.rerank_keep,
                "similarity_threshold": 0.0,
                "use_query_rewrite": True,
                "use_hybrid_search": True,
                "citation_mode": True,
                "max_context_chunks": fasb_service.rerank_keep,
                "prompt_version": 1,
            }
        except Exception:
            return None
    
    # ============= Run Management =============
    
    def create_eval_run(
        self,
        customer_id: str,
        user_id: int,
        domain: str = "fasb",
        sample_size: Optional[int] = None,
        difficulty_counts: Optional[Dict[str, int]] = None,
        seed: int = 42,
        concurrency: int = 3,
        validate_citations: bool = False,
    ) -> RAGEvalRun:
        """
        Create a new evaluation run record.
        
        Args:
            customer_id: Customer identifier
            user_id: User ID who started the run
            domain: Domain to evaluate
            sample_size: Random sample size
            difficulty_counts: Stratified sampling
            seed: Random seed
            concurrency: Parallel workers
            validate_citations: Enable citation page validation
            
        Returns:
            RAGEvalRun instance
        """
        run_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Get FASB service config for snapshot
        fasb_service = get_fasb_service()
        
        eval_run = RAGEvalRun(
            run_id=run_id,
            customer_id=customer_id,
            user_id=user_id,
            domain=domain,
            eval_type="rag_full",
            sample_size=sample_size or sum(difficulty_counts.values()) if difficulty_counts else 0,
            difficulty_counts=difficulty_counts,
            seed=seed,
            concurrency=concurrency,
            validate_citations=validate_citations,
            status=EvalRunStatus.PENDING,
            chat_model=fasb_service.chat_model,
            embed_model=fasb_service.embed_model,
            judge_model=self.settings.rag_eval_judge_model,
            knn_k=fasb_service.knn_k,
            retrieve_size=fasb_service.retrieve_size,
            rerank_keep=fasb_service.rerank_keep,
            prompt_template_snapshot=self._build_prompt_template_snapshot(customer_id, domain),
        )
        
        self.db.add(eval_run)
        self.db.commit()
        self.db.refresh(eval_run)
        
        logger.info(
            "eval_run_created",
            run_id=run_id,
            domain=domain,
            sample_size=eval_run.sample_size,
        )
        
        return eval_run
    
    def create_eval_run_v2(
        self,
        customer_id: str,
        user_id: int,
        domain: str = "fasb",
        sample_size: Optional[int] = None,
        difficulty_counts: Optional[Dict[str, int]] = None,
        seed: int = 42,
        concurrency: int = 3,
        validate_citations: bool = False,
        eval_source: EvalSource = EvalSource.RANDOM_SAMPLING,
        eval_set_id: Optional[int] = None,
        eval_set_name: Optional[str] = None,
    ) -> RAGEvalRun:
        """
        Create a new evaluation run record (v2 with eval source support).
        
        Args:
            customer_id: Customer identifier
            user_id: User ID who started the run
            domain: Domain to evaluate
            sample_size: Number of questions (auto-set from eval_set if provided)
            difficulty_counts: Stratified sampling (for random_sampling source)
            seed: Random seed
            concurrency: Parallel workers
            validate_citations: Enable citation page validation
            eval_source: Source of questions (eval_set or random_sampling)
            eval_set_id: ID of eval set (if eval_source=eval_set)
            eval_set_name: Name of eval set (snapshot for reproducibility)
            
        Returns:
            RAGEvalRun instance
        """
        run_id = f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        # Get FASB service config for snapshot
        fasb_service = get_fasb_service()
        
        eval_run = RAGEvalRun(
            run_id=run_id,
            customer_id=customer_id,
            user_id=user_id,
            domain=domain,
            eval_type="rag_full",
            sample_size=sample_size or (sum(difficulty_counts.values()) if difficulty_counts else 0),
            difficulty_counts=difficulty_counts,
            seed=seed,
            concurrency=concurrency,
            validate_citations=validate_citations,
            status=EvalRunStatus.PENDING,
            eval_source=eval_source,
            eval_set_id=eval_set_id,
            eval_set_name=eval_set_name,
            chat_model=fasb_service.chat_model,
            embed_model=fasb_service.embed_model,
            judge_model=self.settings.rag_eval_judge_model,
            knn_k=fasb_service.knn_k,
            retrieve_size=fasb_service.retrieve_size,
            rerank_keep=fasb_service.rerank_keep,
            prompt_template_snapshot=self._build_prompt_template_snapshot(customer_id, domain),
        )
        
        self.db.add(eval_run)
        self.db.commit()
        self.db.refresh(eval_run)
        
        logger.info(
            "eval_run_v2_created",
            run_id=run_id,
            domain=domain,
            sample_size=eval_run.sample_size,
            eval_source=eval_source.value,
            eval_set_id=eval_set_id,
        )
        
        return eval_run
    
    def _load_questions_from_eval_set(self, eval_set) -> List[Dict[str, Any]]:
        """
        Load questions from an eval set.
        
        Args:
            eval_set: EvalSet model instance
            
        Returns:
            List of question dictionaries formatted for evaluation
        """
        questions = []
        for q in eval_set.questions or []:
            questions.append({
                "eval_id": q.get("eval_id", str(uuid.uuid4())),
                "question": q["question"],
                "expected_answer": q.get("reference_answer", q.get("expected_answer", "")),
                "difficulty": q.get("difficulty", "unknown"),
                "gold_chunk_ids": q.get("gold_chunk_ids", []),
            })
        
        logger.info(
            "eval_questions_loaded_from_set",
            eval_set_id=eval_set.id,
            eval_set_name=eval_set.name,
            count=len(questions)
        )
        
        return questions
    
    async def run_evaluation_v2(
        self,
        eval_run: RAGEvalRun,
        eval_set=None,
    ) -> RAGEvalRun:
        """
        Execute the full evaluation run (v2 with eval set support).
        
        Args:
            eval_run: The evaluation run to execute
            eval_set: Optional EvalSet instance (required if eval_source=eval_set)
            
        Returns:
            Updated RAGEvalRun with results
        """
        # Snapshot scalar fields BEFORE any commit so we never lazy-load from
        # an expired/deleted ORM object during the long-running evaluation.
        run_pk = eval_run.id
        run_id = eval_run.run_id
        run_customer_id = eval_run.customer_id
        run_domain = eval_run.domain
        run_concurrency = eval_run.concurrency
        run_validate_citations = eval_run.validate_citations
        run_eval_source = eval_run.eval_source
        run_eval_set_id = eval_run.eval_set_id
        run_eval_set_name = eval_run.eval_set_name
        run_chat_model = eval_run.chat_model
        run_embed_model = eval_run.embed_model
        run_judge_model = eval_run.judge_model
        run_knn_k = eval_run.knn_k
        run_retrieve_size = eval_run.retrieve_size
        run_rerank_keep = eval_run.rerank_keep
        run_seed = eval_run.seed
        run_sample_size = eval_run.sample_size
        run_difficulty_counts = eval_run.difficulty_counts
        try:
            # Update status
            eval_run.status = EvalRunStatus.RUNNING
            eval_run.started_at = datetime.utcnow()
            self.db.commit()
            
            self._emit_telemetry(
                run_pk,
                "info",
                "Initialization",
                "Starting evaluation run...",
                0,
            )

            self.langfuse_service.trace_generation(
                name="rag-eval-run",
                model=eval_run.chat_model or self.settings.default_llm_model,
                input_data={
                    "run_id": eval_run.run_id,
                    "domain": eval_run.domain,
                    "eval_source": eval_run.eval_source.value if eval_run.eval_source else None,
                    "sample_size": eval_run.sample_size,
                    "prompt_template_snapshot": eval_run.prompt_template_snapshot,
                },
                output_data={"status": "running"},
                customer_id=eval_run.customer_id,
                domain=eval_run.domain,
                extra_metadata={"eval_run_id": eval_run.run_id},
            )
            
            # Load questions based on eval source
            if run_eval_source == EvalSource.EVAL_SET:
                if not eval_set:
                    raise ValueError("eval_set is required when eval_source=eval_set")
                
                questions = self._load_questions_from_eval_set(eval_set)
                
                self._emit_telemetry(
                    run_pk,
                    "info",
                    "Question Loading",
                    f"Loaded {len(questions)} questions from eval set '{eval_set.name}'",
                    5,
                )
                
                # Record usage
                from src.models.eval_set import EvalSetUsage
                usage = EvalSetUsage(
                    eval_set_id=eval_set.id,
                    eval_run_id=run_pk,
                    example_count_at_run=len(questions)
                )
                self.db.add(usage)
                self.db.commit()
            else:
                # Traditional random/stratified sampling
                questions = self.load_eval_questions()
                questions = self.select_questions(
                    questions=questions,
                    sample_size=run_sample_size if not run_difficulty_counts else None,
                    difficulty_counts=run_difficulty_counts,
                    seed=run_seed,
                )
                
                self._emit_telemetry(
                    run_pk,
                    "info",
                    "Question Selection",
                    f"Selected {len(questions)} questions via random sampling",
                    5,
                )
            
            eval_run.total_questions = len(questions)
            self.db.commit()
            
            # Run evaluations with semaphore for concurrency control
            semaphore = asyncio.Semaphore(run_concurrency)
            
            async def bounded_eval(item, idx):
                async with semaphore:
                    result = await self._evaluate_single(
                        item,
                        idx,
                        len(questions),
                        run_pk,
                        run_validate_citations,
                        run_id=run_id,
                        customer_id=run_customer_id,
                        domain=run_domain,
                    )
                    # Emit progress
                    progress = ((idx + 1) / len(questions)) * 90 + 5  # 5-95%
                    self._emit_telemetry(
                        run_pk,
                        "progress",
                        "Evaluation",
                        f"Evaluated {idx+1}/{len(questions)}: {result.verdict.value}",
                        progress,
                        {"eval_id": item["eval_id"], "verdict": result.verdict.value}
                    )
                    return result
            
            tasks = [bounded_eval(q, i) for i, q in enumerate(questions)]
            results = await asyncio.gather(*tasks)
            
            # Save results to database
            for result in results:
                self.db.add(result)
            self.db.commit()
            
            # Calculate aggregate metrics
            pass_count = sum(1 for r in results if r.verdict == EvalVerdict.PASS)
            fail_count = sum(1 for r in results if r.verdict == EvalVerdict.FAIL)
            error_count = sum(1 for r in results if r.verdict == EvalVerdict.ERROR)
            total = len(results)
            pass_rate = (pass_count / total) * 100 if total > 0 else 0
            
            # Aggregate RAGAS metrics
            fc_values = [r.factual_correctness for r in results]
            faith_values = [r.faithfulness for r in results]
            cp_values = [r.context_precision for r in results]
            cr_values = [r.context_recall for r in results]
            cc_values = [r.citation_compliance for r in results]
            cpv_values = [r.citation_page_score for r in results if r.citation_page_score is not None]
            
            eval_run.pass_count = pass_count
            eval_run.fail_count = fail_count
            eval_run.error_count = error_count
            eval_run.pass_rate = pass_rate
            eval_run.factual_correctness_mean = self._safe_mean(fc_values)
            eval_run.faithfulness_mean = self._safe_mean(faith_values)
            eval_run.context_precision_mean = self._safe_mean(cp_values)
            eval_run.context_recall_mean = self._safe_mean(cr_values)
            eval_run.citation_compliance_mean = self._safe_mean(cc_values)
            eval_run.citation_page_accuracy_mean = self._safe_mean(cpv_values)
            
            # Metrics by difficulty
            metrics_by_diff = {}
            for diff in set(r.difficulty for r in results if r.difficulty):
                diff_results = [r for r in results if r.difficulty == diff]
                metrics_by_diff[diff] = {
                    "pass_rate": (sum(1 for r in diff_results if r.verdict == EvalVerdict.PASS) / len(diff_results)) * 100,
                    "factual_correctness_mean": self._safe_mean([r.factual_correctness for r in diff_results]),
                    "faithfulness_mean": self._safe_mean([r.faithfulness for r in diff_results]),
                    "context_precision_mean": self._safe_mean([r.context_precision for r in diff_results]),
                    "context_recall_mean": self._safe_mean([r.context_recall for r in diff_results]),
                    "citation_compliance_mean": self._safe_mean([r.citation_compliance for r in diff_results]),
                    "citation_page_accuracy_mean": self._safe_mean(
                        [r.citation_page_score for r in diff_results if r.citation_page_score is not None]
                    ),
                }
            eval_run.metrics_by_difficulty = self._sanitize_for_json(metrics_by_diff)
            
            # Update status
            eval_run.status = EvalRunStatus.COMPLETED
            eval_run.completed_at = datetime.utcnow()
            self.db.commit()
            
            self._emit_telemetry(
                run_pk,
                "complete",
                "Complete",
                f"Evaluation complete: {pass_count}/{total} passed ({pass_rate:.1f}%)",
                100,
                {
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "pass_rate": pass_rate,
                }
            )
            
            logger.info(
                "eval_run_v2_completed",
                run_id=run_id,
                pass_rate=pass_rate,
                total=total,
                eval_source=run_eval_source.value if run_eval_source else None,
            )

            self.langfuse_service.trace_generation(
                name="rag-eval-run",
                model=eval_run.chat_model or self.settings.default_llm_model,
                input_data={"run_id": eval_run.run_id, "domain": eval_run.domain},
                output_data={
                    "status": "completed",
                    "pass_rate": pass_rate,
                    "total_questions": total,
                },
                customer_id=eval_run.customer_id,
                domain=eval_run.domain,
                extra_metadata={"eval_run_id": eval_run.run_id},
            )
            
            return eval_run
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            # Re-fetch the run fresh — it may have been deleted or the session
            # may be in a bad state after the error.
            try:
                self.db.rollback()
                fresh_run = self.db.query(RAGEvalRun).filter(RAGEvalRun.id == run_pk).first()
                if fresh_run:
                    fresh_run.status = EvalRunStatus.FAILED
                    fresh_run.error_message = str(e)[:2000]
                    fresh_run.completed_at = datetime.utcnow()
                    self.db.commit()
                else:
                    logger.warning(f"Eval run {run_pk} was deleted during execution, cannot update status")
            except Exception as db_err:
                logger.error(f"Failed to update run status after error: {db_err}")
                try:
                    self.db.rollback()
                except Exception:
                    pass
            
            # Telemetry is best-effort
            try:
                self._emit_telemetry(
                    run_pk,
                    "error",
                    "Error",
                    f"Evaluation failed: {str(e)[:500]}",
                    -1,
                )
            except Exception:
                pass

            self.langfuse_service.trace_generation(
                name="rag-eval-run",
                model=run_chat_model or self.settings.default_llm_model,
                input_data={"run_id": run_id, "domain": run_domain},
                output_data={"status": "failed", "error": str(e)},
                customer_id=run_customer_id,
                domain=run_domain,
                extra_metadata={"eval_run_id": run_id},
            )
            
            raise
    
    async def run_evaluation(
        self,
        eval_run: RAGEvalRun,
    ) -> RAGEvalRun:
        """
        Execute the full evaluation run.
        
        Args:
            eval_run: The evaluation run to execute
            
        Returns:
            Updated RAGEvalRun with results
        """
        try:
            # Update status
            eval_run.status = EvalRunStatus.RUNNING
            eval_run.started_at = datetime.utcnow()
            self.db.commit()
            
            self._emit_telemetry(
                eval_run.id,
                "info",
                "Initialization",
                "Starting evaluation run...",
                0,
            )

            self.langfuse_service.trace_generation(
                name="rag-eval-run",
                model=eval_run.chat_model or self.settings.default_llm_model,
                input_data={
                    "run_id": eval_run.run_id,
                    "domain": eval_run.domain,
                    "sample_size": eval_run.sample_size,
                    "prompt_template_snapshot": eval_run.prompt_template_snapshot,
                },
                output_data={"status": "running"},
                customer_id=eval_run.customer_id,
                domain=eval_run.domain,
                extra_metadata={"eval_run_id": eval_run.run_id},
            )
            
            # Load and select questions
            questions = self.load_eval_questions()
            questions = self.select_questions(
                questions=questions,
                sample_size=eval_run.sample_size if not eval_run.difficulty_counts else None,
                difficulty_counts=eval_run.difficulty_counts,
                seed=eval_run.seed,
            )
            
            eval_run.total_questions = len(questions)
            self.db.commit()
            
            self._emit_telemetry(
                eval_run.id,
                "info",
                "Question Selection",
                f"Selected {len(questions)} questions for evaluation",
                5,
            )
            
            # Run evaluations with semaphore for concurrency control
            semaphore = asyncio.Semaphore(eval_run.concurrency)
            v1_run_pk = eval_run.id
            v1_validate_citations = eval_run.validate_citations if hasattr(eval_run, 'validate_citations') else False
            v1_run_id = eval_run.run_id
            v1_customer_id = eval_run.customer_id
            v1_domain = eval_run.domain
            async def bounded_eval(item, idx):
                async with semaphore:
                    result = await self._evaluate_single(
                        item,
                        idx,
                        len(questions),
                        v1_run_pk,
                        v1_validate_citations,
                        run_id=v1_run_id,
                        customer_id=v1_customer_id,
                        domain=v1_domain,
                    )
                    # Emit progress
                    progress = ((idx + 1) / len(questions)) * 90 + 5  # 5-95%
                    self._emit_telemetry(
                        v1_run_pk,
                        "progress",
                        "Evaluation",
                        f"Evaluated {idx+1}/{len(questions)}: {result.verdict.value}",
                        progress,
                        {"eval_id": item["eval_id"], "verdict": result.verdict.value}
                    )
                    return result
            
            tasks = [bounded_eval(q, i) for i, q in enumerate(questions)]
            results = await asyncio.gather(*tasks)
            
            # Save results to database
            for result in results:
                self.db.add(result)
            self.db.commit()
            
            # Calculate aggregate metrics
            pass_count = sum(1 for r in results if r.verdict == EvalVerdict.PASS)
            fail_count = sum(1 for r in results if r.verdict == EvalVerdict.FAIL)
            error_count = sum(1 for r in results if r.verdict == EvalVerdict.ERROR)
            total = len(results)
            pass_rate = (pass_count / total) * 100 if total > 0 else 0
            
            # Aggregate RAGAS metrics
            fc_values = [r.factual_correctness for r in results]
            faith_values = [r.faithfulness for r in results]
            cp_values = [r.context_precision for r in results]
            cr_values = [r.context_recall for r in results]
            cc_values = [r.citation_compliance for r in results]
            cpv_values = [r.citation_page_score for r in results if r.citation_page_score is not None]
            
            eval_run.pass_count = pass_count
            eval_run.fail_count = fail_count
            eval_run.error_count = error_count
            eval_run.pass_rate = pass_rate
            eval_run.factual_correctness_mean = self._safe_mean(fc_values)
            eval_run.faithfulness_mean = self._safe_mean(faith_values)
            eval_run.context_precision_mean = self._safe_mean(cp_values)
            eval_run.context_recall_mean = self._safe_mean(cr_values)
            eval_run.citation_compliance_mean = self._safe_mean(cc_values)
            eval_run.citation_page_accuracy_mean = self._safe_mean(cpv_values)
            
            # Snapshot means before commit (avoid lazy-load after commit)
            v1_fc_mean = eval_run.factual_correctness_mean
            v1_faith_mean = eval_run.faithfulness_mean
            v1_cp_mean = eval_run.context_precision_mean
            v1_cr_mean = eval_run.context_recall_mean
            v1_cc_mean = eval_run.citation_compliance_mean
            v1_cpa_mean = eval_run.citation_page_accuracy_mean
            
            # Metrics by difficulty
            metrics_by_diff = {}
            for diff in set(r.difficulty for r in results if r.difficulty):
                diff_results = [r for r in results if r.difficulty == diff]
                metrics_by_diff[diff] = {
                    "pass_rate": (sum(1 for r in diff_results if r.verdict == EvalVerdict.PASS) / len(diff_results)) * 100,
                    "factual_correctness_mean": self._safe_mean([r.factual_correctness for r in diff_results]),
                    "faithfulness_mean": self._safe_mean([r.faithfulness for r in diff_results]),
                    "context_precision_mean": self._safe_mean([r.context_precision for r in diff_results]),
                    "context_recall_mean": self._safe_mean([r.context_recall for r in diff_results]),
                    "citation_compliance_mean": self._safe_mean([r.citation_compliance for r in diff_results]),
                    "citation_page_accuracy_mean": self._safe_mean(
                        [r.citation_page_score for r in diff_results if r.citation_page_score is not None]
                    ),
                }
            # Sanitize NaN values to None for JSON storage (PostgreSQL JSON doesn't accept NaN)
            eval_run.metrics_by_difficulty = self._sanitize_for_json(metrics_by_diff)
            
            # Update status
            eval_run.status = EvalRunStatus.COMPLETED
            eval_run.completed_at = datetime.utcnow()
            self.db.commit()
            
            self._emit_telemetry(
                v1_run_pk,
                "complete",
                "Complete",
                f"Evaluation complete: {pass_count}/{total} passed ({pass_rate:.1f}%)",
                100,
                {
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "pass_rate": pass_rate,
                }
            )
            
            logger.info(
                "eval_run_completed",
                run_id=eval_run.run_id,
                pass_rate=pass_rate,
                total=total,
            )

            self.langfuse_service.trace_generation(
                name="rag-eval-run",
                model=eval_run.chat_model or self.settings.default_llm_model,
                input_data={"run_id": eval_run.run_id, "domain": eval_run.domain},
                output_data={
                    "status": "completed",
                    "pass_rate": pass_rate,
                    "total_questions": total,
                },
                customer_id=eval_run.customer_id,
                domain=eval_run.domain,
                extra_metadata={"eval_run_id": eval_run.run_id},
            )
            
            return eval_run
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}", exc_info=True)
            # Re-fetch the run fresh in case session state is bad
            try:
                self.db.rollback()
                fresh_run = self.db.query(RAGEvalRun).filter(RAGEvalRun.id == v1_run_pk).first()
                if fresh_run:
                    fresh_run.status = EvalRunStatus.FAILED
                    fresh_run.error_message = str(e)[:2000]
                    fresh_run.completed_at = datetime.utcnow()
                    self.db.commit()
                else:
                    logger.warning(f"Eval run {v1_run_pk} was deleted during execution, cannot update status")
            except Exception as db_err:
                logger.error(f"Failed to update run status after error: {db_err}")
                try:
                    self.db.rollback()
                except Exception:
                    pass
            
            # Telemetry is best-effort
            try:
                self._emit_telemetry(
                    v1_run_pk,
                    "error",
                    "Error",
                    f"Evaluation failed: {str(e)[:500]}",
                    -1,
                )
            except Exception:
                pass

            self.langfuse_service.trace_generation(
                name="rag-eval-run",
                model=eval_run.chat_model or self.settings.default_llm_model,
                input_data={"run_id": eval_run.run_id, "domain": eval_run.domain},
                output_data={"status": "failed", "error": str(e)},
                customer_id=eval_run.customer_id,
                domain=eval_run.domain,
                extra_metadata={"eval_run_id": eval_run.run_id},
            )
            
            raise
    
    # ============= Query Methods =============
    
    def get_eval_run(self, run_id: str) -> Optional[RAGEvalRun]:
        """Get evaluation run by run_id."""
        return self.db.query(RAGEvalRun).filter(
            RAGEvalRun.run_id == run_id
        ).first()
    
    def get_eval_run_by_id(self, id: int) -> Optional[RAGEvalRun]:
        """Get evaluation run by database ID."""
        return self.db.query(RAGEvalRun).filter(RAGEvalRun.id == id).first()
    
    def list_eval_runs(
        self,
        customer_id: str,
        domain: Optional[str] = None,
        status: Optional[EvalRunStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RAGEvalRun], int]:
        """
        List evaluation runs with filtering.
        
        Returns:
            Tuple of (runs, total_count)
        """
        # Backward-compat: some previous containers wrote enum *names* (e.g. "PENDING"/"PASS")
        # into string/enum columns. Newer code expects lowercase values ("pending"/"pass").
        # Normalize legacy uppercase values in-place so listing doesn't crash and history works.
        try:
            self.db.execute(
                sa.text(
                    """
                    UPDATE rag_eval_runs
                    SET status = lower(status::text)
                    WHERE status IS NOT NULL AND status::text ~ '[A-Z]'
                    """
                )
            )
            self.db.execute(
                sa.text(
                    """
                    UPDATE rag_eval_results
                    SET verdict = lower(verdict::text)
                    WHERE verdict IS NOT NULL AND verdict::text ~ '[A-Z]'
                    """
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

        query = self.db.query(RAGEvalRun).filter(
            RAGEvalRun.customer_id == customer_id
        )
        
        if domain:
            query = query.filter(RAGEvalRun.domain == domain)
        if status:
            query = query.filter(RAGEvalRun.status == status)
        
        total = query.count()
        runs = query.order_by(RAGEvalRun.created_at.desc()).offset(offset).limit(limit).all()
        
        return runs, total
    
    def get_eval_results(
        self,
        eval_run_id: int,
        verdict: Optional[EvalVerdict] = None,
        difficulty: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RAGEvalResult], int]:
        """
        Get evaluation results with filtering.
        
        Returns:
            Tuple of (results, total_count)
        """
        query = self.db.query(RAGEvalResult).filter(
            RAGEvalResult.eval_run_id == eval_run_id
        )
        
        if verdict:
            query = query.filter(RAGEvalResult.verdict == verdict)
        if difficulty:
            query = query.filter(RAGEvalResult.difficulty == difficulty)
        
        total = query.count()
        results = query.order_by(RAGEvalResult.question_index).offset(offset).limit(limit).all()
        
        return results, total
    
    def get_telemetry_events(
        self,
        eval_run_id: int,
        after_id: Optional[int] = None,
    ) -> List[RAGEvalTelemetryEvent]:
        """Get telemetry events for SSE streaming."""
        query = self.db.query(RAGEvalTelemetryEvent).filter(
            RAGEvalTelemetryEvent.eval_run_id == eval_run_id
        )
        
        if after_id:
            query = query.filter(RAGEvalTelemetryEvent.id > after_id)
        
        return query.order_by(RAGEvalTelemetryEvent.id).all()
    
    def cancel_eval_run(self, run_id: str, reason: str = None) -> Optional[RAGEvalRun]:
        """Cancel a running evaluation."""
        eval_run = self.get_eval_run(run_id)
        if not eval_run:
            return None
        
        if eval_run.status not in [EvalRunStatus.PENDING, EvalRunStatus.RUNNING]:
            return eval_run
        
        eval_run.status = EvalRunStatus.CANCELLED
        eval_run.error_message = reason or "Cancelled by user"
        eval_run.completed_at = datetime.utcnow()
        self.db.commit()
        
        self._emit_telemetry(
            eval_run.id,
            "cancelled",
            "Cancelled",
            f"Evaluation cancelled: {reason or 'User request'}",
            -1,
        )
        
        return eval_run
