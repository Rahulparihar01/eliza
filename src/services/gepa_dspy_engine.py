"""
DSPy-backed GEPA optimization engine.

This engine replaces hand-rolled mutation/crossover candidate generation
with DSPy optimizers while preserving GEPA orchestration/evaluation flows.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional

from src.core.config import get_settings
from src.core.logging import get_logger
from src.services.langfuse_service import get_langfuse_service
from src.services.workspace_rag_backend import WorkspacePromptTemplate

try:
    import dspy
except Exception:  # pragma: no cover - handled gracefully at runtime
    dspy = None

logger = get_logger(__name__, component="services.gepa_dspy_engine")


if dspy is not None:

    class WorkspaceRAGSignature(dspy.Signature):
        """RAG Q&A signature matching the workspace pipeline."""

        question: str = dspy.InputField(desc="User question")
        context: str = dspy.InputField(desc="Retrieved document context")
        answer: str = dspy.OutputField(
            desc="Answer based on context with citation references like [1], [2]"
        )


    class WorkspaceRAGModule(dspy.Module):
        """DSPy module wrapping a workspace RAG prompt behavior."""

        def __init__(self, workspace_template: WorkspacePromptTemplate):
            super().__init__()
            self.template = workspace_template
            self.rag_chain = dspy.ChainOfThought(WorkspaceRAGSignature)

        def forward(self, question: str, context: str):
            return self.rag_chain(question=question, context=context)

else:

    class WorkspaceRAGSignature:  # pragma: no cover - placeholder for type references
        pass


    class WorkspaceRAGModule:  # pragma: no cover - placeholder for type references
        def __init__(self, workspace_template: WorkspacePromptTemplate):
            self.template = workspace_template


class GEPADSPyEngine:
    """
    GEPA optimization engine powered by DSPy.

    Strategies:
    - dspy_bootstrap => BootstrapFewShot
    - dspy_mipro => MIPROv2
    """

    def __init__(
        self,
        workspace_template: WorkspacePromptTemplate,
        eval_set_questions: List[dict],
        *,
        customer_id: Optional[str] = None,
    ):
        self.template = workspace_template
        self.eval_data = eval_set_questions or []
        self.customer_id = customer_id
        self.settings = get_settings()
        self.langfuse_service = get_langfuse_service()

    def _configure_dspy_lm(self) -> None:
        if dspy is None:
            raise RuntimeError("dspy is not installed")

        lm_kwargs = {
            "temperature": self.template.temperature,
            "max_tokens": self.template.max_tokens,
        }
        if self.settings.openai_api_key:
            lm_kwargs["api_key"] = self.settings.openai_api_key
        if self.settings.openai_api_base_url:
            lm_kwargs["api_base"] = self.settings.openai_api_base_url

        raw_model = self.template.model
        candidates: List[str] = []
        if "/" in raw_model:
            candidates.append(raw_model)
        else:
            candidates.append(f"openai/{raw_model}")
            candidates.append(raw_model)

        # Keep order but deduplicate.
        model_candidates = list(dict.fromkeys(candidates))
        last_error: Optional[Exception] = None
        for candidate in model_candidates:
            try:
                dspy.configure(lm=dspy.LM(model=candidate, **lm_kwargs))
                logger.info("gepa_dspy_lm_configured", model=candidate)
                return
            except Exception as exc:
                last_error = exc

        if last_error is not None:
            raise last_error

    @staticmethod
    def _normalize_context(raw_context: Any) -> str:
        if raw_context is None:
            return ""
        if isinstance(raw_context, str):
            return raw_context
        if isinstance(raw_context, list):
            return "\n".join(str(item) for item in raw_context if item)
        if isinstance(raw_context, dict):
            return str(raw_context.get("context") or raw_context.get("text") or "")
        return str(raw_context)

    def _build_examples(self) -> List[Any]:
        if dspy is None:
            return []

        examples: List[Any] = []
        for row in self.eval_data:
            question = (row or {}).get("question")
            if not question:
                continue
            expected_answer = (
                row.get("reference_answer")
                or row.get("expected_answer")
                or row.get("answer")
                or ""
            )
            context = self._normalize_context(
                row.get("context") or row.get("contexts") or row.get("retrieved_context")
            )
            example = dspy.Example(
                question=question,
                context=context,
                answer=expected_answer,
            ).with_inputs("question", "context")
            examples.append(example)
        return examples

    @staticmethod
    def _token_overlap(reference: str, prediction: str) -> float:
        ref_tokens = {token for token in re.findall(r"\w+", (reference or "").lower()) if token}
        pred_tokens = {token for token in re.findall(r"\w+", (prediction or "").lower()) if token}
        if not ref_tokens:
            return 0.0
        return len(ref_tokens.intersection(pred_tokens)) / len(ref_tokens)

    @staticmethod
    def _citation_score(prediction: str) -> float:
        citations = re.findall(r"\[(\d+)\]", prediction or "")
        if not citations:
            return 0.0
        return 1.0

    def _build_metric(self, objectives: List[str]) -> Callable[[Any, Any, Any], float]:
        normalized_objectives = set(objectives or [])

        def metric(example, pred, trace=None) -> float:
            predicted_answer = getattr(pred, "answer", "") if pred is not None else ""
            reference_answer = getattr(example, "answer", "") if example is not None else ""
            context = getattr(example, "context", "") if example is not None else ""

            score_components: List[float] = []

            overlap = self._token_overlap(reference_answer, predicted_answer)
            citation = self._citation_score(predicted_answer)
            faithfulness = (
                self._token_overlap(context, predicted_answer) if context else overlap
            )

            if "quality" in normalized_objectives or "factual_correctness" in normalized_objectives:
                score_components.append(overlap)
            if "groundedness" in normalized_objectives or "faithfulness" in normalized_objectives:
                score_components.append(faithfulness)
            if "citation_accuracy" in normalized_objectives or "citation_compliance" in normalized_objectives:
                score_components.append(citation)

            if not score_components:
                score_components.extend([overlap, faithfulness])

            return max(0.0, min(sum(score_components) / len(score_components), 1.0))

        return metric

    def _extract_instruction(self, compiled_program: Any) -> Optional[str]:
        candidates: List[str] = []

        for attr in ("instructions", "instruction", "system_prompt", "prompt"):
            value = getattr(compiled_program, attr, None)
            if isinstance(value, str) and value.strip():
                candidates.append(value.strip())

        for attr in ("rag_chain", "predictor"):
            predictor = getattr(compiled_program, attr, None)
            if predictor is None:
                continue
            for predictor_attr in ("instructions", "instruction", "prompt"):
                value = getattr(predictor, predictor_attr, None)
                if isinstance(value, str) and value.strip():
                    candidates.append(value.strip())
            signature = getattr(predictor, "signature", None)
            signature_instructions = getattr(signature, "instructions", None)
            if isinstance(signature_instructions, str) and signature_instructions.strip():
                candidates.append(signature_instructions.strip())

        if not candidates:
            return None
        return max(candidates, key=len)

    @staticmethod
    def _apply_objective_tuning(
        template: WorkspacePromptTemplate,
        objectives: List[str],
    ) -> WorkspacePromptTemplate:
        tuned = template.model_copy(deep=True)
        objective_set = set(objectives or [])

        if "faithfulness" in objective_set or "groundedness" in objective_set:
            tuned.temperature = max(0.0, min(tuned.temperature, 0.2))
        if "context_recall" in objective_set:
            tuned.top_k = min(50, max(tuned.top_k, 8))
            tuned.max_context_chunks = min(20, max(tuned.max_context_chunks, 8))
        if "citation_accuracy" in objective_set or "citation_compliance" in objective_set:
            tuned.citation_mode = True
            tuned.synthesis_prompt = (
                (tuned.synthesis_prompt or "")
                + "\n\nAlways include grounded citations [1], [2], ... for factual claims."
            ).strip()
        return tuned

    def optimize(
        self,
        objectives: List[str],
        strategy: str = "mipro",
        seed: int = 42,
    ) -> WorkspacePromptTemplate:
        """
        Run DSPy optimization and return updated workspace template.
        """
        if dspy is None:
            raise RuntimeError("dspy dependency is required for DSPy-backed optimization")

        examples = self._build_examples()
        if not examples:
            logger.warning("gepa_dspy_no_examples_fallback")
            return self._apply_objective_tuning(self.template, objectives)

        self._configure_dspy_lm()
        metric_fn = self._build_metric(objectives)
        module = WorkspaceRAGModule(self.template)

        metadata = {
            "strategy": strategy,
            "objective_count": len(objectives or []),
            "example_count": len(examples),
            "workspace_id": self.template.workspace_id,
        }
        self.langfuse_service.trace_generation(
            name="gepa-dspy-optimize.start",
            model=self.template.model,
            input_data={
                "template": self.template.model_dump(),
                "objectives": objectives,
                "strategy": strategy,
                "seed": seed,
            },
            output_data={"status": "started"},
            workspace_id=self.template.workspace_id,
            domain=self.template.domain,
            customer_id=self.customer_id,
            prompt_version=self.template.prompt_version,
            gepa_variant_id=self.template.gepa_variant_id,
            extra_metadata=metadata,
        )

        # MIPROv2 calls input() multiple times for user confirmation which
        # crashes in Celery workers (no stdin). Patch stdin to always return "y".
        import sys as _sys, io as _io

        class _AutoConfirmStdin(_io.StringIO):
            def readline(self, *a, **kw):
                return "y\n"

        _original_stdin = _sys.stdin
        _sys.stdin = _AutoConfirmStdin()

        compiled = None

        def _run_bootstrap():
            """BootstrapFewShot — reliable fallback optimizer."""
            try:
                opt = dspy.BootstrapFewShot(
                    metric=metric_fn,
                    max_bootstrapped_demos=min(8, len(examples)),
                    max_labeled_demos=min(8, len(examples)),
                )
                return opt.compile(module, trainset=examples)
            except TypeError:
                opt = dspy.BootstrapFewShot(metric=metric_fn)
                return opt.compile(module, trainset=examples)

        try:
            if strategy == "bootstrap":
                compiled = _run_bootstrap()
            else:
                try:
                    optimizer = dspy.MIPROv2(
                        metric=metric_fn,
                        auto="light",
                        num_candidates=min(8, max(2, len(examples))),
                        seed=seed,
                    )
                    compiled = optimizer.compile(module, trainset=examples)
                except Exception as mipro_exc:
                    logger.warning(
                        "gepa_mipro_failed_falling_back_to_bootstrap",
                        error=str(mipro_exc),
                        example_count=len(examples),
                    )
                    compiled = _run_bootstrap()
        finally:
            _sys.stdin = _original_stdin

        optimized_template = self._apply_objective_tuning(self.template, objectives)
        extracted_instruction = self._extract_instruction(compiled)
        if extracted_instruction:
            optimized_template.synthesis_prompt = extracted_instruction
            if "system_prompt" in objectives or "quality" in objectives:
                optimized_template.system_prompt = extracted_instruction

        optimized_template.prompt_version = (self.template.prompt_version or 0) + 1

        self.langfuse_service.trace_generation(
            name="gepa-dspy-optimize.complete",
            model=self.template.model,
            input_data={
                "strategy": strategy,
                "objective_count": len(objectives or []),
                "example_count": len(examples),
            },
            output_data={
                "optimized_template": optimized_template.model_dump(),
                "instruction_extracted": bool(extracted_instruction),
            },
            workspace_id=self.template.workspace_id,
            domain=self.template.domain,
            customer_id=self.customer_id,
            prompt_version=optimized_template.prompt_version,
            gepa_variant_id=optimized_template.gepa_variant_id,
            extra_metadata=metadata,
        )

        return optimized_template

    @staticmethod
    def template_to_components(
        template: WorkspacePromptTemplate,
        baseline_components: Dict[str, str],
    ) -> Dict[str, str]:
        """Map optimized workspace template back to GEPA component values."""
        values = dict(baseline_components or {})
        mapping = {
            "system_prompt": template.system_prompt,
            "query_rewrite_prompt": template.query_rewrite_prompt,
            "answer_synthesis_prompt": template.synthesis_prompt,
            "retrieval_instructions": template.retrieval_prompt,
        }
        for component, value in mapping.items():
            if component in values and value is not None:
                values[component] = value
        return values
