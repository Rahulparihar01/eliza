"""
GEPA Optimizer Service

Core service implementing the GEPA (Genetic Prompt Algorithm) optimization.
Handles population management, mutation/crossover, evaluation, and Pareto optimization.
"""
import asyncio
import hashlib
import json
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from difflib import SequenceMatcher, unified_diff
import numpy as np

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.core.logging import get_logger
from src.core.config import get_settings
from src.models.eval_set import EvalSet
from src.models.gepa_optimizer import (
    OptimizerJob, OptimizerJobStatus,
    CandidateVariant, VariantStatus,
    GEPAEvaluationResult, TraceArtifact,
    ParetoSnapshot, GEPATelemetryEvent, PromotedVariantHistory,
    MutationType, ComponentType,
    GEPAHumanFeedback, FeedbackType, FeedbackRating
)
from src.services.gepa_dspy_engine import GEPADSPyEngine
from src.services.langfuse_service import get_langfuse_service
from src.services.workspace_rag_backend import (
    WorkspacePromptTemplate,
    refresh_workspace_prompt_templates_for_domain,
)

logger = get_logger(__name__, component="services.gepa_optimizer")


class GEPAOptimizerService:
    """
    Service for managing GEPA optimization jobs.
    
    Implements:
    - Job lifecycle management (create, run, pause, cancel)
    - Genetic algorithm operations (selection, crossover, mutation)
    - Pareto frontier computation
    - Evaluation orchestration
    - Variant promotion
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self._llm_client = None
        self.langfuse_service = get_langfuse_service()
    
    @property
    def llm_client(self):
        """Lazy-load LLM client for mutations."""
        if self._llm_client is None:
            # Import here to avoid circular dependencies
            from litellm import acompletion
            self._llm_client = acompletion
        return self._llm_client
    
    # ==================== Job Management ====================
    
    def create_optimizer_job(
        self,
        customer_id: str,
        user_id: int,
        name: str,
        components: List[Dict[str, Any]],
        objectives: List[Dict[str, Any]],
        domain: Optional[str] = None,
        description: Optional[str] = None,
        agent_config_id: Optional[int] = None,
        eval_suite_id: Optional[int] = None,
        population_size: int = 10,
        max_iterations: int = 20,
        eval_budget: int = 500,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.5,
        elite_count: int = 2,
        optimization_strategy: str = "dspy_mipro",
    ) -> OptimizerJob:
        """Create a new optimizer job."""
        job_id = f"gepa_{uuid.uuid4().hex[:12]}"
        
        # Extract component types and initial values
        target_components = [c["component_type"] for c in components]
        baseline_components = {
            c["component_type"]: c["initial_value"] 
            for c in components
        }
        
        # Extract objectives
        objective_names = [o["name"] for o in objectives]
        objective_weights = {o["name"]: o.get("weight", 1.0) for o in objectives}
        
        job = OptimizerJob(
            job_id=job_id,
            customer_id=customer_id,
            user_id=user_id,
            name=name,
            description=description,
            domain=domain,
            agent_config_id=agent_config_id,
            eval_suite_id=eval_suite_id,
            target_components=target_components,
            baseline_components=baseline_components,
            objectives=objective_names,
            objective_weights=objective_weights,
            optimization_strategy=optimization_strategy,
            population_size=population_size,
            max_iterations=max_iterations,
            eval_budget=eval_budget,
            mutation_rate=mutation_rate,
            crossover_rate=crossover_rate,
            elite_count=elite_count,
            status=OptimizerJobStatus.PENDING,
        )
        
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        
        # Create baseline variant
        self._create_baseline_variant(job)
        
        logger.info(
            "gepa_job_created",
            job_id=job_id,
            customer_id=customer_id,
            components=target_components,
            objectives=objective_names,
            optimization_strategy=optimization_strategy,
        )
        
        return job
    
    def _create_baseline_variant(self, job: OptimizerJob) -> CandidateVariant:
        """Create the baseline variant from initial component values."""
        variant = CandidateVariant(
            job_id=job.id,
            variant_id=f"baseline_{uuid.uuid4().hex[:8]}",
            generation=0,
            component_values=job.baseline_components,
            is_baseline=True,
            status=VariantStatus.PENDING,
        )
        self.db.add(variant)
        self.db.commit()
        self.db.refresh(variant)
        return variant
    
    def get_job(self, job_id: str) -> Optional[OptimizerJob]:
        """Get an optimizer job by job_id."""
        return self.db.query(OptimizerJob).filter(
            OptimizerJob.job_id == job_id
        ).first()
    
    def get_job_by_id(self, id: int) -> Optional[OptimizerJob]:
        """Get an optimizer job by database ID."""
        return self.db.query(OptimizerJob).filter(OptimizerJob.id == id).first()
    
    def list_jobs(
        self,
        customer_id: str,
        status: Optional[OptimizerJobStatus] = None,
        domain: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[OptimizerJob], int]:
        """List optimizer jobs for a customer, optionally filtered by domain."""
        query = self.db.query(OptimizerJob).filter(
            OptimizerJob.customer_id == customer_id
        )
        
        if status:
            query = query.filter(OptimizerJob.status == status)
        
        if domain:
            query = query.filter(OptimizerJob.domain == domain)
        
        total = query.count()
        jobs = query.order_by(OptimizerJob.created_at.desc()).offset(offset).limit(limit).all()
        
        return jobs, total
    
    def pause_job(self, job_id: str, reason: Optional[str] = None) -> OptimizerJob:
        """Pause a running optimization job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job.status != OptimizerJobStatus.RUNNING:
            raise ValueError(f"Job {job_id} is not running (status: {job.status})")
        
        job.status = OptimizerJobStatus.PAUSED
        if reason:
            self._emit_telemetry(job.id, "info", message=f"Paused: {reason}")
        
        self.db.commit()
        return job
    
    def resume_job(self, job_id: str) -> OptimizerJob:
        """Resume a paused optimization job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job.status != OptimizerJobStatus.PAUSED:
            raise ValueError(f"Job {job_id} is not paused (status: {job.status})")
        
        job.status = OptimizerJobStatus.RUNNING
        self._emit_telemetry(job.id, "info", message="Resumed")
        
        self.db.commit()
        return job
    
    def cancel_job(self, job_id: str, reason: Optional[str] = None) -> OptimizerJob:
        """Cancel an optimization job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        if job.status in [OptimizerJobStatus.COMPLETED, OptimizerJobStatus.CANCELLED]:
            raise ValueError(f"Job {job_id} is already {job.status}")
        
        job.status = OptimizerJobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        job.error_message = reason
        
        self._emit_telemetry(
            job.id, "complete",
            message=f"Cancelled: {reason}" if reason else "Cancelled by user"
        )
        
        self.db.commit()
        return job
    
    # ==================== Main Optimization Loop ====================
    
    async def run_optimization(self, job: OptimizerJob) -> OptimizerJob:
        """
        Run the full GEPA optimization loop.
        
        1. Initialize population with baseline + random mutations
        2. Evaluate population
        3. Compute Pareto frontier
        4. Select parents via tournament selection
        5. Generate offspring via crossover and mutation
        6. Repeat until budget exhausted or max iterations reached
        """
        logger.info("gepa_optimization_started", job_id=job.job_id)
        
        try:
            job.status = OptimizerJobStatus.RUNNING
            job.started_at = datetime.utcnow()
            self.db.commit()
            
            self._emit_telemetry(
                job.id, "info", 
                message="Starting GEPA optimization",
                stage_name="initialization"
            )

            strategy = (job.optimization_strategy or "genetic").lower()
            if strategy in {"dspy_bootstrap", "dspy_mipro"}:
                return await self._run_dspy_optimization(job)
            
            # Initialize population
            await self._initialize_population(job)
            
            # Main optimization loop
            for iteration in range(job.max_iterations):
                if job.status == OptimizerJobStatus.PAUSED:
                    logger.info("gepa_job_paused", job_id=job.job_id, iteration=iteration)
                    return job
                
                if job.status == OptimizerJobStatus.CANCELLED:
                    logger.info("gepa_job_cancelled", job_id=job.job_id, iteration=iteration)
                    return job
                
                if job.total_evals_used >= job.eval_budget:
                    logger.info("gepa_budget_exhausted", job_id=job.job_id, iteration=iteration)
                    self._emit_telemetry(job.id, "info", message="Evaluation budget exhausted")
                    break
                
                job.current_iteration = iteration + 1
                self.db.commit()
                
                progress = (iteration / job.max_iterations) * 100
                self._emit_telemetry(
                    job.id, "progress",
                    message=f"Iteration {iteration + 1}/{job.max_iterations}",
                    stage_name=f"iteration_{iteration + 1}",
                    progress_percentage=progress,
                    data={"iteration": iteration + 1}
                )
                
                # Evaluate pending variants
                await self._evaluate_population(job)
                
                # Compute Pareto frontier
                self._compute_pareto_frontier(job, iteration + 1)
                
                # Check for early stopping
                if self._should_stop_early(job):
                    logger.info("gepa_early_stopping", job_id=job.job_id, iteration=iteration)
                    self._emit_telemetry(job.id, "info", message="Early stopping - convergence detected")
                    break
                
                # Generate next generation (unless last iteration)
                if iteration < job.max_iterations - 1:
                    await self._evolve_population(job, iteration + 1)
            
            # Final evaluation of any remaining variants
            await self._evaluate_population(job)
            
            # Final Pareto frontier
            self._compute_pareto_frontier(job, job.current_iteration)
            
            # Update best variant
            self._update_best_variant(job)
            
            job.status = OptimizerJobStatus.COMPLETED
            job.completed_at = datetime.utcnow()
            self.db.commit()
            
            self._emit_telemetry(
                job.id, "complete",
                message="Optimization completed successfully",
                progress_percentage=100,
                data={
                    "total_iterations": job.current_iteration,
                    "total_evals": job.total_evals_used,
                    "best_quality": job.best_quality_score,
                }
            )
            
            logger.info(
                "gepa_optimization_completed",
                job_id=job.job_id,
                iterations=job.current_iteration,
                evals_used=job.total_evals_used,
                best_quality=job.best_quality_score,
            )
            
            return job
            
        except Exception as e:
            logger.error("gepa_optimization_failed", job_id=job.job_id, error=str(e), exc_info=True)
            
            job.status = OptimizerJobStatus.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(e)
            self.db.commit()
            
            self._emit_telemetry(job.id, "error", message=f"Optimization failed: {str(e)}")
            
            raise

    def _load_eval_set_questions(self, job: OptimizerJob) -> List[Dict[str, Any]]:
        """Load eval examples for DSPy optimization."""
        if job.eval_suite_id:
            eval_set = self.db.query(EvalSet).filter(EvalSet.id == job.eval_suite_id).first()
            if eval_set and (eval_set.customer_id in (None, job.customer_id)):
                return eval_set.questions or []

        # Fallback to static eval jsonl file if available.
        questions: List[Dict[str, Any]] = []
        path = Path(self.settings.rag_eval_questions_path or "")
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    for i, line in enumerate(f):
                        if i >= 50:
                            break
                        row = json.loads(line)
                        questions.append(
                            {
                                "question": row.get("question", ""),
                                "reference_answer": row.get("reference_answer", ""),
                                "difficulty": row.get("difficulty"),
                                "gold_chunk_ids": row.get("gold_chunk_ids", []),
                            }
                        )
            except Exception as exc:
                logger.warning("gepa_dspy_eval_file_load_failed", error=str(exc))
        return questions

    def _build_workspace_template_from_job(self, job: OptimizerJob) -> WorkspacePromptTemplate:
        """Build WorkspacePromptTemplate from GEPA baseline components."""
        from src.models.ragflow_domain import RAGFlowDomain

        workspace = None
        if job.domain:
            workspace = self.db.query(RAGFlowDomain).filter(
                RAGFlowDomain.customer_id == job.customer_id,
                RAGFlowDomain.name == job.domain,
                RAGFlowDomain.is_active == True,
            ).first()

        baseline = job.baseline_components or {}
        system_prompt = baseline.get("system_prompt") or "You are a retrieval grounded assistant."
        query_rewrite_prompt = baseline.get("query_rewrite_prompt")
        synthesis_prompt = baseline.get("answer_synthesis_prompt")
        retrieval_prompt = baseline.get("retrieval_instructions")

        workspace_id = workspace.id if workspace else 0
        workspace_name = (
            workspace.display_name
            if workspace is not None
            else (job.domain or job.name or "workspace")
        )
        domain = workspace.name if workspace is not None else (job.domain or "knowledge_base")

        return WorkspacePromptTemplate(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            domain=domain,
            system_prompt=system_prompt,
            query_rewrite_prompt=query_rewrite_prompt,
            synthesis_prompt=synthesis_prompt,
            retrieval_prompt=retrieval_prompt,
            model=self.settings.default_llm_model or "gpt-4o-mini",
            temperature=0.1,
            max_tokens=1024,
            top_k=5,
            similarity_threshold=0.0,
            use_query_rewrite=bool(query_rewrite_prompt),
            use_hybrid_search=True,
            citation_mode=True,
            max_context_chunks=5,
            gepa_variant_id=None,
            gepa_job_id=job.id,
            prompt_version=1,
        )

    async def _run_dspy_optimization(self, job: OptimizerJob) -> OptimizerJob:
        """Run DSPy-based optimization and materialize candidates as GEPA variants."""
        strategy = (job.optimization_strategy or "dspy_mipro").lower()
        dspy_strategy = "bootstrap" if strategy == "dspy_bootstrap" else "mipro"

        template = self._build_workspace_template_from_job(job)
        eval_questions = self._load_eval_set_questions(job)
        engine = GEPADSPyEngine(
            workspace_template=template,
            eval_set_questions=eval_questions,
            customer_id=job.customer_id,
        )

        self._emit_telemetry(
            job.id,
            "info",
            message=f"Running DSPy optimization ({strategy})",
            stage_name="dspy_optimization",
            progress_percentage=10,
        )
        self.langfuse_service.trace_gepa_step(
            job_id=job.job_id,
            step_name="optimize_start",
            model=template.model,
            input_data={
                "strategy": strategy,
                "objective_count": len(job.objectives or []),
                "target_components": job.target_components,
                "eval_examples": len(eval_questions),
            },
            output_data={"status": "started"},
            strategy=strategy,
            customer_id=job.customer_id,
            domain=job.domain,
        )

        self.langfuse_service.trace_generation(
            name="gepa-dspy-job",
            model=template.model,
            input_data={
                "job_id": job.job_id,
                "strategy": strategy,
                "objectives": job.objectives,
                "target_components": job.target_components,
                "eval_examples": len(eval_questions),
            },
            output_data={"status": "started"},
            workspace_id=template.workspace_id,
            domain=template.domain,
            customer_id=job.customer_id,
            prompt_version=template.prompt_version,
            gepa_variant_id=template.gepa_variant_id,
            extra_metadata={"gepa_job_id": job.id},
        )

        optimized_template = engine.optimize(
            objectives=job.objectives or [],
            strategy=dspy_strategy,
        )
        self.langfuse_service.trace_gepa_step(
            job_id=job.job_id,
            step_name="optimize_complete",
            model=template.model,
            input_data={"strategy": strategy},
            output_data={"optimized_template": optimized_template.model_dump(mode="json")},
            strategy=strategy,
            customer_id=job.customer_id,
            domain=job.domain,
        )

        # Ensure baseline exists.
        baseline = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job.id,
                CandidateVariant.is_baseline == True,
            )
        ).first()
        if not baseline:
            baseline = self._create_baseline_variant(job)

        optimized_components = engine.template_to_components(
            optimized_template,
            job.baseline_components,
        )

        variant = CandidateVariant(
            job_id=job.id,
            variant_id=f"dspy_{uuid.uuid4().hex[:8]}",
            generation=1,
            parent_variant_ids=[baseline.variant_id],
            mutation_type=MutationType.REFLECTION_GUIDED,
            component_values=optimized_components,
            component_diffs=self._compute_diffs(job.baseline_components, optimized_components),
            status=VariantStatus.PENDING,
        )
        self.db.add(variant)
        self.db.commit()
        self.db.refresh(variant)

        job.current_iteration = 1
        self.db.commit()

        self._emit_telemetry(
            job.id,
            "evaluation",
            message="Evaluating DSPy candidate variant",
            stage_name="dspy_evaluation",
            progress_percentage=60,
            data={"variant_id": variant.variant_id},
        )

        await self._evaluate_variant(job, variant)
        self.langfuse_service.trace_gepa_step(
            job_id=job.job_id,
            step_name="variant_evaluated",
            model=template.model,
            input_data={"variant_id": variant.variant_id},
            output_data={
                "quality_score": variant.quality_score,
                "groundedness_score": variant.groundedness_score,
                "citation_accuracy": variant.citation_accuracy,
                "avg_latency_ms": variant.avg_latency_ms,
                "avg_cost": variant.avg_cost,
            },
            strategy=strategy,
            customer_id=job.customer_id,
            domain=job.domain,
            variant_id=variant.id,
        )
        self.db.commit()

        self._compute_pareto_frontier(job, 1)
        self._update_best_variant(job)

        job.total_evals_used = max(job.total_evals_used, 1)
        job.status = OptimizerJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        self.db.commit()

        self._emit_telemetry(
            job.id,
            "complete",
            message=f"DSPy optimization completed ({strategy})",
            progress_percentage=100,
            data={
                "strategy": strategy,
                "best_quality": job.best_quality_score,
                "variant_id": variant.variant_id,
            },
        )

        self.langfuse_service.trace_generation(
            name="gepa-dspy-job",
            model=template.model,
            input_data={
                "job_id": job.job_id,
                "strategy": strategy,
            },
            output_data={
                "status": "completed",
                "best_quality": job.best_quality_score,
                "variant_id": variant.variant_id,
            },
            workspace_id=template.workspace_id,
            domain=template.domain,
            customer_id=job.customer_id,
            prompt_version=optimized_template.prompt_version,
            gepa_variant_id=variant.id,
            extra_metadata={"gepa_job_id": job.id},
        )

        logger.info(
            "gepa_dspy_completed",
            job_id=job.job_id,
            strategy=strategy,
            variant_id=variant.variant_id,
            best_quality=job.best_quality_score,
        )
        return job
    
    # ==================== Population Management ====================
    
    async def _initialize_population(self, job: OptimizerJob):
        """Initialize population with baseline and random mutations."""
        self._emit_telemetry(
            job.id, "info",
            message=f"Initializing population with {job.population_size} variants",
            stage_name="initialization"
        )
        
        # Get baseline variant
        baseline = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job.id,
                CandidateVariant.is_baseline == True
            )
        ).first()
        
        # Generate additional variants through mutation
        variants_needed = job.population_size - 1  # -1 for baseline
        
        for i in range(variants_needed):
            # Apply random mutation to baseline
            selected_mutation = random.choice([
                MutationType.REPHRASE,
                MutationType.EXPAND,
                MutationType.RESTRUCTURE,
            ])
            mutated_values, _ = await self._mutate_components(
                job, baseline.component_values, 
                mutation_type=selected_mutation
            )
            
            variant = CandidateVariant(
                job_id=job.id,
                variant_id=f"init_{uuid.uuid4().hex[:8]}",
                generation=0,
                parent_variant_ids=[baseline.variant_id],
                mutation_type=selected_mutation,
                component_values=mutated_values,
                component_diffs=self._compute_diffs(job.baseline_components, mutated_values),
                status=VariantStatus.PENDING,
            )
            self.db.add(variant)
        
        self.db.commit()
        logger.info("gepa_population_initialized", job_id=job.job_id, population_size=job.population_size)
    
    async def _evolve_population(self, job: OptimizerJob, generation: int):
        """Generate next generation through selection, crossover, and mutation."""
        self._emit_telemetry(
            job.id, "mutation",
            message=f"Evolving population for generation {generation}",
            stage_name=f"evolution_{generation}"
        )
        
        # Get evaluated variants sorted by fitness
        evaluated = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job.id,
                CandidateVariant.status == VariantStatus.EVALUATED
            )
        ).all()
        
        if len(evaluated) < 2:
            logger.warning("gepa_insufficient_evaluated", job_id=job.job_id, count=len(evaluated))
            return
        
        # Elite selection - keep top performers
        elites = sorted(evaluated, key=lambda v: v.quality_score or 0, reverse=True)[:job.elite_count]
        
        # Generate offspring
        offspring_count = job.population_size - job.elite_count
        
        for i in range(offspring_count):
            if random.random() < job.crossover_rate and len(evaluated) >= 2:
                # Crossover
                parents = random.sample(evaluated, 2)
                child_values = self._crossover(
                    parents[0].component_values,
                    parents[1].component_values
                )
                parent_ids = [parents[0].variant_id, parents[1].variant_id]
                mutation_type = MutationType.CROSSOVER
            else:
                # Tournament selection + mutation
                parent = self._tournament_select(evaluated, tournament_size=3)
                child_values = parent.component_values.copy()
                parent_ids = [parent.variant_id]
                mutation_type = None
            
            # Apply mutation
            incorporated_feedback_ids = []
            if random.random() < job.mutation_rate:
                # Select mutation type based on trace analysis if available
                selected_mutation = await self._select_mutation_type(job, parent_ids[0] if parent_ids else None)
                child_values, incorporated_feedback_ids = await self._mutate_components(
                    job, child_values, mutation_type=selected_mutation
                )
                mutation_type = selected_mutation
            
            variant = CandidateVariant(
                job_id=job.id,
                variant_id=f"g{generation}_{uuid.uuid4().hex[:8]}",
                generation=generation,
                parent_variant_ids=parent_ids,
                mutation_type=mutation_type,
                component_values=child_values,
                component_diffs=self._compute_diffs(job.baseline_components, child_values),
                status=VariantStatus.PENDING,
            )
            self.db.add(variant)
            self.db.flush()  # Get the ID
            
            # Mark feedback as incorporated if any was used
            if incorporated_feedback_ids:
                self.mark_feedback_incorporated(incorporated_feedback_ids, variant.id)
        
        self.db.commit()
        logger.info("gepa_population_evolved", job_id=job.job_id, generation=generation)
    
    def _tournament_select(
        self, 
        population: List[CandidateVariant], 
        tournament_size: int = 3
    ) -> CandidateVariant:
        """Select a variant using tournament selection with human feedback bonus."""
        tournament = random.sample(population, min(tournament_size, len(population)))
        
        # Prefer variants on Pareto frontier (rank 0)
        # Then by quality score + feedback bonus
        def fitness_key(v):
            rank = v.pareto_rank if v.pareto_rank is not None else float('inf')
            quality = v.quality_score if v.quality_score is not None else 0
            # Add human feedback bonus (-0.2 to +0.2)
            feedback_bonus = self.compute_feedback_bonus(v.id)
            adjusted_quality = quality + feedback_bonus
            return (-rank, adjusted_quality)  # Lower rank is better
        
        return max(tournament, key=fitness_key)
    
    def _crossover(
        self, 
        parent1_values: Dict[str, str], 
        parent2_values: Dict[str, str]
    ) -> Dict[str, str]:
        """Perform crossover between two parent variants."""
        child_values = {}
        
        for component in parent1_values.keys():
            if random.random() < 0.5:
                child_values[component] = parent1_values[component]
            else:
                child_values[component] = parent2_values.get(component, parent1_values[component])
        
        return child_values
    
    async def _select_mutation_type(
        self, 
        job: OptimizerJob, 
        parent_variant_id: Optional[str]
    ) -> MutationType:
        """Select mutation type, preferring reflection-guided mutations if traces available."""
        if parent_variant_id:
            # Check if there are failure traces we can learn from
            parent = self.db.query(CandidateVariant).filter(
                and_(
                    CandidateVariant.job_id == job.id,
                    CandidateVariant.variant_id == parent_variant_id
                )
            ).first()
            
            if parent and parent.trace_artifacts:
                failure_traces = [t for t in parent.trace_artifacts if t.trace_type == "failure"]
                if failure_traces:
                    return MutationType.ERROR_TARGETED
        
        # Default distribution
        weights = {
            MutationType.REPHRASE: 0.3,
            MutationType.EXPAND: 0.2,
            MutationType.COMPRESS: 0.15,
            MutationType.RESTRUCTURE: 0.15,
            MutationType.ADD_CONSTRAINT: 0.1,
            MutationType.REFLECTION_GUIDED: 0.1,
        }
        
        types = list(weights.keys())
        probs = list(weights.values())
        return random.choices(types, weights=probs, k=1)[0]
    
    async def _mutate_components(
        self,
        job: OptimizerJob,
        component_values: Dict[str, str],
        mutation_type: MutationType,
        traces: Optional[List[Dict]] = None,
        feedback_context: Optional[str] = None,
    ) -> Tuple[Dict[str, str], List[int]]:
        """
        Apply mutation to component values using LLM.
        
        Returns:
            Tuple of (mutated_components, incorporated_feedback_ids)
        """
        mutated = component_values.copy()
        incorporated_feedback_ids = []
        
        # Get feedback context if not provided and we have unincorporated feedback
        if feedback_context is None:
            feedback_context = self.build_feedback_context_for_mutation(job.id)
            if feedback_context:
                # Get the feedback IDs that were used
                unincorporated = self.get_unincorporated_feedback(job.id)
                incorporated_feedback_ids = [f.id for f in unincorporated[:8]]  # Use top 8
        
        # Select which components to mutate (usually 1-2)
        components_to_mutate = random.sample(
            list(component_values.keys()),
            k=min(random.randint(1, 2), len(component_values))
        )
        
        for component in components_to_mutate:
            original = component_values[component]
            mutated[component] = await self._apply_mutation(
                original, mutation_type, component, traces, feedback_context
            )
        
        return mutated, incorporated_feedback_ids
    
    async def _apply_mutation(
        self,
        original: str,
        mutation_type: MutationType,
        component_name: str,
        traces: Optional[List[Dict]] = None,
        feedback_context: Optional[str] = None,
    ) -> str:
        """Apply a specific mutation to a text component using LLM."""
        
        # Base mutation prompts
        mutation_prompts = {
            MutationType.REPHRASE: """Rephrase the following prompt while preserving its meaning and intent. 
Make it clearer and more effective. Only output the rephrased prompt, nothing else.
{feedback_section}
Original prompt:
{original}""",
            
            MutationType.EXPAND: """Expand the following prompt by adding more detail, examples, or clarification.
Keep the core intent but make it more comprehensive. Only output the expanded prompt.
{feedback_section}
Original prompt:
{original}""",
            
            MutationType.COMPRESS: """Condense the following prompt to be more concise while preserving key instructions.
Remove redundancy but keep essential information. Only output the compressed prompt.
{feedback_section}
Original prompt:
{original}""",
            
            MutationType.RESTRUCTURE: """Restructure the following prompt to improve its organization and flow.
Use better formatting (bullets, sections) if helpful. Only output the restructured prompt.
{feedback_section}
Original prompt:
{original}""",
            
            MutationType.ADD_CONSTRAINT: """Add a specific constraint or guardrail to the following prompt.
The constraint should improve output quality, accuracy, or safety. Only output the modified prompt.
{feedback_section}
Original prompt:
{original}""",
            
            MutationType.REFLECTION_GUIDED: """Improve the following prompt based on the feedback from human reviewers and common issues in RAG systems.
Focus on improving: citation accuracy, factual grounding, and relevance.
{feedback_section}
Original prompt:
{original}

Output only the improved prompt.""",
            
            MutationType.ERROR_TARGETED: """Improve the following prompt to address these specific failures:
{error_context}
{feedback_section}
Original prompt:
{original}

Output only the improved prompt that addresses these issues.""",
        }
        
        prompt_template = mutation_prompts.get(mutation_type, mutation_prompts[MutationType.REPHRASE])
        
        # Build error context
        error_context = ""
        if mutation_type == MutationType.ERROR_TARGETED and traces:
            error_context = "\n".join([
                f"- {t.get('error_message', 'Unknown error')}" 
                for t in traces[:3]
            ])
        
        # Build feedback section
        feedback_section = ""
        if feedback_context:
            feedback_section = f"""
## Human Feedback to Consider:
{feedback_context}

Please incorporate this feedback into your mutation."""
        
        prompt = prompt_template.format(
            original=original, 
            error_context=error_context,
            feedback_section=feedback_section,
        )
        
        try:
            response = await self.llm_client(
                model=self.settings.default_llm_model or "gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
                temperature=0.7,
            )
            
            mutated = response.choices[0].message.content.strip()
            
            # Sanity check - don't accept empty or drastically different results
            if len(mutated) < 10 or len(mutated) > len(original) * 5:
                logger.warning("gepa_mutation_rejected", reason="size_check_failed")
                return original
            
            return mutated
            
        except Exception as e:
            logger.error("gepa_mutation_failed", error=str(e))
            return original
    
    # ==================== Evaluation ====================
    
    async def _evaluate_population(self, job: OptimizerJob):
        """Evaluate all pending variants in the population."""
        pending = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job.id,
                CandidateVariant.status == VariantStatus.PENDING
            )
        ).all()
        
        if not pending:
            return
        
        self._emit_telemetry(
            job.id, "evaluation",
            message=f"Evaluating {len(pending)} variants",
            stage_name="evaluation"
        )
        
        for variant in pending:
            if job.total_evals_used >= job.eval_budget:
                logger.info("gepa_budget_exhausted_during_eval", job_id=job.job_id)
                break
            
            await self._evaluate_variant(job, variant)
        
        self.db.commit()
    
    async def _evaluate_variant(self, job: OptimizerJob, variant: CandidateVariant):
        """Evaluate a single variant against the eval suite."""
        variant.status = VariantStatus.EVALUATING
        self.db.commit()
        
        try:
            # For now, use a simplified evaluation
            # In production, this would call the actual RAG eval service
            results = await self._run_eval_suite(job, variant)
            
            # Compute aggregate scores
            if results:
                variant.quality_score = np.mean([r.get("factual_correctness", 0) for r in results])
                variant.groundedness_score = np.mean([r.get("faithfulness", 0) for r in results])
                variant.citation_accuracy = np.mean([r.get("citation_compliance", 0) for r in results])
                variant.avg_latency_ms = np.mean([r.get("latency_ms", 0) for r in results])
                variant.avg_cost = np.mean([r.get("estimated_cost", 0) for r in results])
                
                # Store individual results
                for result in results:
                    eval_result = GEPAEvaluationResult(
                        variant_id=variant.id,
                        eval_case_id=result.get("eval_case_id", str(uuid.uuid4())),
                        question=result.get("question", ""),
                        expected_answer=result.get("expected_answer"),
                        model_response=result.get("model_response"),
                        factual_correctness=result.get("factual_correctness"),
                        faithfulness=result.get("faithfulness"),
                        context_precision=result.get("context_precision"),
                        context_recall=result.get("context_recall"),
                        citation_compliance=result.get("citation_compliance"),
                        verdict=result.get("verdict"),
                        verdict_reason=result.get("verdict_reason"),
                        latency_ms=result.get("latency_ms"),
                        estimated_cost=result.get("estimated_cost"),
                        tool_calls=result.get("tool_calls"),
                        retrieved_docs=result.get("retrieved_docs"),
                    )
                    self.db.add(eval_result)
                
                job.total_evals_used += len(results)
            
            variant.status = VariantStatus.EVALUATED
            
            logger.info(
                "gepa_variant_evaluated",
                job_id=job.job_id,
                variant_id=variant.variant_id,
                quality=variant.quality_score,
            )
            
        except Exception as e:
            logger.error(
                "gepa_variant_eval_failed",
                job_id=job.job_id,
                variant_id=variant.variant_id,
                error=str(e),
            )
            variant.status = VariantStatus.FAILED
            
            # Store failure trace
            trace = TraceArtifact(
                variant_id=variant.id,
                trace_id=f"fail_{uuid.uuid4().hex[:8]}",
                trace_type="failure",
                trace_data={"error": str(e)},
                error_count=1,
            )
            self.db.add(trace)
    
    async def _run_eval_suite(
        self, 
        job: OptimizerJob, 
        variant: CandidateVariant
    ) -> List[Dict[str, Any]]:
        """
        Run evaluation suite against a variant.
        
        This is a placeholder - in production, integrate with RAGEvalService.
        """
        # TODO: Integrate with actual RAG eval service
        # For now, return simulated results for development
        
        results = []
        
        # Simulate evaluation with some random variation
        base_quality = 0.7 + random.uniform(-0.1, 0.2)
        base_faithfulness = 0.6 + random.uniform(-0.1, 0.2)
        
        # Simulate 5 test cases
        for i in range(5):
            result = {
                "eval_case_id": f"eval_{i}",
                "question": f"Test question {i}",
                "expected_answer": f"Expected answer {i}",
                "model_response": f"Model response {i}",
                "factual_correctness": base_quality + random.uniform(-0.05, 0.05),
                "faithfulness": base_faithfulness + random.uniform(-0.05, 0.05),
                "context_precision": 0.7 + random.uniform(-0.1, 0.1),
                "context_recall": 0.65 + random.uniform(-0.1, 0.1),
                "citation_compliance": random.choice([0, 1]),
                "verdict": "pass" if random.random() > 0.3 else "fail",
                "latency_ms": 500 + random.uniform(0, 500),
                "estimated_cost": 0.01 + random.uniform(0, 0.02),
            }
            results.append(result)
        
        return results
    
    # ==================== Pareto Optimization ====================
    
    def _compute_pareto_frontier(self, job: OptimizerJob, iteration: int):
        """Compute Pareto frontier over evaluated variants."""
        evaluated = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job.id,
                CandidateVariant.status == VariantStatus.EVALUATED
            )
        ).all()
        
        if not evaluated:
            return
        
        # Build objective matrix
        # Objectives to maximize: quality, groundedness, citation_accuracy
        # Objectives to minimize: latency, cost
        
        objectives_config = {
            "quality": ("quality_score", True),  # (attr, maximize)
            "groundedness": ("groundedness_score", True),
            "citation_accuracy": ("citation_accuracy", True),
            "latency": ("avg_latency_ms", False),
            "cost": ("avg_cost", False),
        }
        
        # Extract scores
        scores = []
        for v in evaluated:
            score_row = []
            for obj_name in job.objectives:
                if obj_name in objectives_config:
                    attr, maximize = objectives_config[obj_name]
                    value = getattr(v, attr) or 0
                    # Negate minimization objectives so higher is always better
                    score_row.append(value if maximize else -value)
                else:
                    score_row.append(0)
            scores.append(score_row)
        
        scores = np.array(scores)
        
        # Compute Pareto ranks using non-dominated sorting
        ranks = self._non_dominated_sort(scores)
        
        # Update variant ranks and crowding distances
        frontier_ids = []
        for i, v in enumerate(evaluated):
            v.pareto_rank = ranks[i]
            if ranks[i] == 0:
                frontier_ids.append(v.variant_id)
        
        # Compute crowding distance for diversity preservation
        crowding = self._compute_crowding_distance(scores, ranks)
        for i, v in enumerate(evaluated):
            v.crowding_distance = crowding[i]
        
        # Compute frontier statistics
        frontier_variants = [v for v in evaluated if v.pareto_rank == 0]
        frontier_stats = self._compute_frontier_stats(frontier_variants, job.objectives)
        
        # Save Pareto snapshot (upsert to handle retries)
        existing_snapshot = self.db.query(ParetoSnapshot).filter(
            and_(
                ParetoSnapshot.job_id == job.id,
                ParetoSnapshot.iteration == iteration
            )
        ).first()
        
        if existing_snapshot:
            # Update existing snapshot
            existing_snapshot.frontier_variant_ids = frontier_ids
            existing_snapshot.frontier_count = len(frontier_ids)
            existing_snapshot.frontier_stats = frontier_stats
            existing_snapshot.hypervolume = self._compute_hypervolume(scores, ranks)
            diversity = np.mean(crowding) if len(crowding) > 0 else 0
            existing_snapshot.diversity_score = min(diversity, 1e9) if np.isfinite(diversity) else 0
        else:
            # Create new snapshot
            diversity = np.mean(crowding) if len(crowding) > 0 else 0
            diversity = min(diversity, 1e9) if np.isfinite(diversity) else 0
            snapshot = ParetoSnapshot(
                job_id=job.id,
                iteration=iteration,
                frontier_variant_ids=frontier_ids,
                frontier_count=len(frontier_ids),
                frontier_stats=frontier_stats,
                hypervolume=self._compute_hypervolume(scores, ranks),
                diversity_score=diversity,
            )
            self.db.add(snapshot)
        
        self.db.commit()
        
        self._emit_telemetry(
            job.id, "frontier",
            message=f"Pareto frontier updated: {len(frontier_ids)} variants",
            data={
                "iteration": iteration,
                "frontier_count": len(frontier_ids),
                "frontier_ids": frontier_ids[:5],  # Limit for SSE
            }
        )
        
        logger.info(
            "gepa_pareto_computed",
            job_id=job.job_id,
            iteration=iteration,
            frontier_size=len(frontier_ids),
        )
    
    def _non_dominated_sort(self, scores: np.ndarray) -> List[int]:
        """
        Non-dominated sorting (NSGA-II style).
        Returns rank for each individual (0 = Pareto frontier).
        """
        n = len(scores)
        if n == 0:
            return []
        
        # domination_count[i] = number of individuals that dominate i
        # dominated[i] = set of individuals that i dominates
        domination_count = [0] * n
        dominated = [[] for _ in range(n)]
        ranks = [0] * n
        
        for i in range(n):
            for j in range(i + 1, n):
                if self._dominates(scores[i], scores[j]):
                    dominated[i].append(j)
                    domination_count[j] += 1
                elif self._dominates(scores[j], scores[i]):
                    dominated[j].append(i)
                    domination_count[i] += 1
        
        # Find first front (rank 0)
        current_front = [i for i in range(n) if domination_count[i] == 0]
        rank = 0
        
        while current_front:
            for i in current_front:
                ranks[i] = rank
            
            next_front = []
            for i in current_front:
                for j in dominated[i]:
                    domination_count[j] -= 1
                    if domination_count[j] == 0:
                        next_front.append(j)
            
            current_front = next_front
            rank += 1
        
        return ranks
    
    def _dominates(self, a: np.ndarray, b: np.ndarray) -> bool:
        """Check if solution a dominates solution b (all objectives >= and at least one >)."""
        return np.all(a >= b) and np.any(a > b)
    
    def _compute_crowding_distance(self, scores: np.ndarray, ranks: List[int]) -> List[float]:
        """Compute crowding distance for diversity preservation."""
        n = len(scores)
        if n == 0:
            return []
        
        # Use large finite value instead of infinity (JSON-safe)
        INF_REPLACEMENT = 1e9
        distances = [0.0] * n
        
        for obj_idx in range(scores.shape[1]):
            # Sort by this objective
            sorted_indices = np.argsort(scores[:, obj_idx])
            
            # Boundary points get large distance (preserves them in selection)
            distances[sorted_indices[0]] = INF_REPLACEMENT
            distances[sorted_indices[-1]] = INF_REPLACEMENT
            
            # Compute distance for middle points
            obj_range = scores[sorted_indices[-1], obj_idx] - scores[sorted_indices[0], obj_idx]
            if obj_range > 0:
                for i in range(1, n - 1):
                    distances[sorted_indices[i]] += (
                        scores[sorted_indices[i + 1], obj_idx] - 
                        scores[sorted_indices[i - 1], obj_idx]
                    ) / obj_range
        
        return distances
    
    def _compute_hypervolume(self, scores: np.ndarray, ranks: List[int]) -> float:
        """Compute hypervolume indicator for frontier quality."""
        # Simplified hypervolume - sum of dominated area
        frontier_scores = scores[np.array(ranks) == 0]
        if len(frontier_scores) == 0:
            return 0.0
        
        # Use reference point as worst value in each dimension
        ref_point = np.min(scores, axis=0) - 0.1
        
        # Simple approximation: sum of products of distances to reference
        volume = 0.0
        for s in frontier_scores:
            volume += np.prod(s - ref_point)
        
        return float(volume)
    
    def _compute_frontier_stats(
        self, 
        frontier_variants: List[CandidateVariant],
        objectives: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Compute statistics for the Pareto frontier."""
        stats = {}
        
        attr_map = {
            "quality": "quality_score",
            "groundedness": "groundedness_score",
            "citation_accuracy": "citation_accuracy",
            "latency": "avg_latency_ms",
            "cost": "avg_cost",
        }
        
        for obj in objectives:
            attr = attr_map.get(obj)
            if attr:
                values = [getattr(v, attr) or 0 for v in frontier_variants]
                if values:
                    stats[obj] = {
                        "min": float(np.min(values)),
                        "max": float(np.max(values)),
                        "mean": float(np.mean(values)),
                    }
        
        return stats
    
    # ==================== Utility Methods ====================
    
    def _compute_diffs(
        self, 
        baseline: Dict[str, str], 
        variant: Dict[str, str]
    ) -> Dict[str, Any]:
        """Compute diffs between baseline and variant component values."""
        diffs = {}
        
        for component, baseline_value in baseline.items():
            variant_value = variant.get(component, "")
            
            if baseline_value != variant_value:
                # Compute unified diff
                baseline_lines = baseline_value.splitlines(keepends=True)
                variant_lines = variant_value.splitlines(keepends=True)
                
                diff = list(unified_diff(baseline_lines, variant_lines, lineterm=''))
                
                added = [line[1:] for line in diff if line.startswith('+') and not line.startswith('+++')]
                removed = [line[1:] for line in diff if line.startswith('-') and not line.startswith('---')]
                
                # Compute similarity
                similarity = SequenceMatcher(None, baseline_value, variant_value).ratio()
                
                diffs[component] = {
                    "added": added,
                    "removed": removed,
                    "similarity_score": similarity,
                }
        
        return diffs
    
    def _should_stop_early(self, job: OptimizerJob) -> bool:
        """Check if optimization should stop early due to convergence."""
        # Get last 3 Pareto snapshots
        snapshots = self.db.query(ParetoSnapshot).filter(
            ParetoSnapshot.job_id == job.id
        ).order_by(ParetoSnapshot.iteration.desc()).limit(3).all()
        
        if len(snapshots) < 3:
            return False
        
        # Check if hypervolume has converged
        volumes = [s.hypervolume or 0 for s in snapshots]
        if all(v > 0 for v in volumes):
            improvement = (volumes[0] - volumes[-1]) / max(volumes[-1], 0.001)
            if improvement < 0.01:  # Less than 1% improvement
                return True
        
        return False
    
    def _update_best_variant(self, job: OptimizerJob):
        """Update the best variant reference on the job."""
        best = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job.id,
                CandidateVariant.status == VariantStatus.EVALUATED,
                CandidateVariant.pareto_rank == 0
            )
        ).order_by(CandidateVariant.quality_score.desc()).first()
        
        if best:
            job.best_variant_id = best.id
            job.best_quality_score = best.quality_score
    
    def _emit_telemetry(
        self,
        job_id: int,
        event_type: str,
        message: Optional[str] = None,
        stage_name: Optional[str] = None,
        progress_percentage: Optional[float] = None,
        data: Optional[Dict] = None,
    ):
        """Emit a telemetry event for SSE streaming."""
        event = GEPATelemetryEvent(
            job_id=job_id,
            event_type=event_type,
            message=message,
            stage_name=stage_name,
            progress_percentage=progress_percentage,
            data=data,
        )
        self.db.add(event)
        self.db.commit()
    
    # ==================== Variant Management ====================
    
    def get_variants(
        self,
        job_id: int,
        generation: Optional[int] = None,
        pareto_rank: Optional[int] = None,
        status: Optional[VariantStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[CandidateVariant], int]:
        """Get variants for a job with optional filters."""
        query = self.db.query(CandidateVariant).filter(
            CandidateVariant.job_id == job_id
        )
        
        if generation is not None:
            query = query.filter(CandidateVariant.generation == generation)
        if pareto_rank is not None:
            query = query.filter(CandidateVariant.pareto_rank == pareto_rank)
        if status:
            query = query.filter(CandidateVariant.status == status)
        
        total = query.count()
        variants = query.order_by(
            CandidateVariant.pareto_rank.asc().nullslast(),
            CandidateVariant.quality_score.desc().nullslast()
        ).offset(offset).limit(limit).all()
        
        return variants, total
    
    def get_variant(self, job_id: int, variant_id: str) -> Optional[CandidateVariant]:
        """Get a specific variant."""
        return self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job_id,
                CandidateVariant.variant_id == variant_id
            )
        ).first()
    
    def get_variant_eval_results(
        self,
        variant_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[GEPAEvaluationResult], int]:
        """Get evaluation results for a variant."""
        query = self.db.query(GEPAEvaluationResult).filter(
            GEPAEvaluationResult.variant_id == variant_id
        )
        total = query.count()
        results = query.order_by(GEPAEvaluationResult.created_at).offset(offset).limit(limit).all()
        return results, total
    
    def get_variant_traces(
        self,
        variant_id: int,
        trace_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[TraceArtifact], int]:
        """Get trace artifacts for a variant."""
        query = self.db.query(TraceArtifact).filter(
            TraceArtifact.variant_id == variant_id
        )
        if trace_type:
            query = query.filter(TraceArtifact.trace_type == trace_type)
        
        total = query.count()
        traces = query.order_by(TraceArtifact.created_at.desc()).offset(offset).limit(limit).all()
        return traces, total
    
    # ==================== Promotion ====================
    
    def promote_variant(
        self,
        job_id: int,
        variant_id: str,
        environment: str,
        user_id: int,
        domain: Optional[str] = None,
        auto_activate: bool = False,
        notes: Optional[str] = None,
        create_backup: bool = True,
        agent_config_id: Optional[int] = None,  # Deprecated, kept for backwards compatibility
    ) -> PromotedVariantHistory:
        """
        Promote a variant to an environment via Prompt Management.
        
        This creates new prompt versions in the Prompt Management system,
        optionally auto-activating them for immediate use.
        
        Args:
            job_id: GEPA job ID
            variant_id: Variant ID to promote
            environment: Target environment (dev/staging/prod)
            user_id: User performing the promotion
            domain: Target domain for prompts (e.g., 'fasb', 'insurance')
            auto_activate: Whether to immediately activate the new prompt versions
            notes: Optional notes about the promotion
            create_backup: Whether to backup previous values
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        variant = self.get_variant(job_id, variant_id)
        if not variant:
            raise ValueError(f"Variant {variant_id} not found")
        
        if variant.status != VariantStatus.EVALUATED:
            raise ValueError(f"Variant {variant_id} has not been evaluated")
        
        # Infer domain if not provided (prefer explicit job.domain)
        if not domain:
            job_domain = getattr(job, "domain", None)
            if job_domain:
                domain = job_domain
            else:
                # Fallback: try to extract from job name (e.g., "FASB optimization" -> "fasb")
                domain = job.name.lower().split()[0] if job.name else "default"
        
        # Import PromptManagementService
        from src.services.prompt_management_service import PromptManagementService
        from src.models.prompt_template import PromptType
        
        prompt_service = PromptManagementService(self.db)
        
        # Map GEPA component types to Prompt Management types
        component_to_prompt_type = {
            "system_prompt": PromptType.SYSTEM,
            "query_rewrite_prompt": PromptType.QUERY_REWRITE,
            "answer_synthesis_prompt": PromptType.SYNTHESIS,
            "retrieval_instructions": PromptType.RETRIEVAL,
            "evaluation_criteria": PromptType.EVALUATION,
        }
        
        created_prompts = []
        previous_values = {}
        
        # Create prompt versions for each component
        for component, value in variant.component_values.items():
            prompt_type = component_to_prompt_type.get(component)
            if not prompt_type:
                # Use CUSTOM type for unknown components
                prompt_type = PromptType.CUSTOM
            
            # Get current active prompt for backup
            if create_backup:
                current = prompt_service.get_prompt(
                    customer_id=job.customer_id,
                    domain=domain,
                    prompt_type=prompt_type,
                )
                if current:
                    previous_values[component] = current.content
            
            # Create new prompt version
            quality_score = int(variant.quality_score * 100) if variant.quality_score else None
            prompt = prompt_service.promote_from_gepa(
                customer_id=job.customer_id,
                domain=domain,
                prompt_type=prompt_type,
                content=value,
                gepa_job_id=job.id,
                gepa_variant_id=variant.id,
                user_id=user_id,
                quality_score=quality_score,
                auto_activate=auto_activate,
            )
            created_prompts.append({
                "component": component,
                "prompt_id": prompt.id,
                "version": prompt.version,
                "prompt_type": prompt_type.value,
            })
        
        # Create promotion history
        promotion = PromotedVariantHistory(
            variant_id=variant.id,
            job_id=job.id,
            variant_snapshot=variant.component_values,
            environment=environment,
            promoted_by_user_id=user_id,
            agent_config_id=None,  # Using Prompt Management instead
            previous_values=previous_values if create_backup else None,
            scores_at_promotion={
                "quality": variant.quality_score,
                "groundedness": variant.groundedness_score,
                "citation_accuracy": variant.citation_accuracy,
                "latency": variant.avg_latency_ms,
                "cost": variant.avg_cost,
            },
            notes=notes,
            rollback_info={
                "domain": domain,
                "prompts_created": created_prompts,
                "auto_activated": auto_activate,
            },
        )
        self.db.add(promotion)
        
        # Update variant status
        variant.is_promoted = True
        variant.promoted_at = datetime.utcnow()
        variant.promoted_to = environment
        variant.status = VariantStatus.PROMOTED
        
        self.db.commit()
        self.db.refresh(promotion)

        # Refresh workspace prompt snapshots and invalidate cached agents.
        try:
            refresh_workspace_prompt_templates_for_domain(
                domain=domain,
                customer_id=job.customer_id,
                db=self.db,
                gepa_variant_id=variant.id,
                gepa_job_id=job.id,
            )
        except Exception as exc:
            logger.warning(
                "workspace_prompt_refresh_failed_after_promotion",
                job_id=job.job_id,
                variant_id=variant_id,
                domain=domain,
                error=str(exc),
            )
        
        logger.info(
            "gepa_variant_promoted",
            job_id=job.job_id,
            variant_id=variant_id,
            environment=environment,
            domain=domain,
            prompts_created=len(created_prompts),
            auto_activated=auto_activate,
        )
        
        return promotion
    
    # ==================== Telemetry ====================
    
    def get_telemetry_events(
        self,
        job_id: int,
        after_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[GEPATelemetryEvent]:
        """Get telemetry events for SSE streaming."""
        query = self.db.query(GEPATelemetryEvent).filter(
            GEPATelemetryEvent.job_id == job_id
        )
        
        if after_id:
            query = query.filter(GEPATelemetryEvent.id > after_id)
        
        return query.order_by(GEPATelemetryEvent.id).limit(limit).all()
    
    def get_pareto_snapshots(
        self,
        job_id: int,
        limit: int = 50,
    ) -> List[ParetoSnapshot]:
        """Get Pareto snapshots for a job."""
        return self.db.query(ParetoSnapshot).filter(
            ParetoSnapshot.job_id == job_id
        ).order_by(ParetoSnapshot.iteration).limit(limit).all()
    
    # ==================== Human Feedback ====================
    
    RATING_TO_NUMERIC = {
        FeedbackRating.STRONGLY_NEGATIVE: -2,
        FeedbackRating.NEGATIVE: -1,
        FeedbackRating.NEUTRAL: 0,
        FeedbackRating.POSITIVE: 1,
        FeedbackRating.STRONGLY_POSITIVE: 2,
    }
    
    def submit_feedback(
        self,
        job_id: int,
        variant_id: int,
        user_id: int,
        feedback_type: str,
        rating: str,
        eval_result_id: Optional[int] = None,
        query_text: Optional[str] = None,
        response_text: Optional[str] = None,
        comment: Optional[str] = None,
        tags: Optional[List[str]] = None,
        improvement_suggestions: Optional[str] = None,
        target_components: Optional[List[str]] = None,
    ) -> GEPAHumanFeedback:
        """Submit human feedback on a variant."""
        rating_enum = FeedbackRating(rating)
        rating_numeric = self.RATING_TO_NUMERIC[rating_enum]
        
        feedback = GEPAHumanFeedback(
            job_id=job_id,
            variant_id=variant_id,
            user_id=user_id,
            feedback_type=FeedbackType(feedback_type),
            rating=rating_enum,
            rating_numeric=rating_numeric,
            eval_result_id=eval_result_id,
            query_text=query_text,
            response_text=response_text,
            comment=comment,
            tags=tags,
            improvement_suggestions=improvement_suggestions,
            target_components=target_components,
            incorporated=False,
        )
        
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        
        logger.info(
            "gepa_feedback_submitted",
            job_id=job_id,
            variant_id=variant_id,
            feedback_type=feedback_type,
            rating=rating,
        )
        
        return feedback
    
    def get_variant_feedback(self, variant_id: int) -> List[GEPAHumanFeedback]:
        """Get all feedback for a variant."""
        return self.db.query(GEPAHumanFeedback).filter(
            GEPAHumanFeedback.variant_id == variant_id
        ).order_by(GEPAHumanFeedback.created_at.desc()).all()
    
    def get_job_feedback(
        self,
        job_id: int,
        incorporated: Optional[bool] = None,
    ) -> List[GEPAHumanFeedback]:
        """Get all feedback for a job, optionally filtered."""
        query = self.db.query(GEPAHumanFeedback).filter(
            GEPAHumanFeedback.job_id == job_id
        )
        
        if incorporated is not None:
            query = query.filter(GEPAHumanFeedback.incorporated == incorporated)
        
        return query.order_by(GEPAHumanFeedback.created_at.desc()).all()
    
    def get_feedback_by_id(self, feedback_id: int) -> Optional[GEPAHumanFeedback]:
        """Get a specific feedback entry."""
        return self.db.query(GEPAHumanFeedback).filter(
            GEPAHumanFeedback.id == feedback_id
        ).first()
    
    def delete_feedback(self, feedback_id: int) -> None:
        """Delete a feedback entry."""
        self.db.query(GEPAHumanFeedback).filter(
            GEPAHumanFeedback.id == feedback_id
        ).delete()
        self.db.commit()
    
    def get_feedback_stats(self, job_id: int) -> Dict[str, Any]:
        """Get aggregated feedback statistics for a job."""
        feedback_list = self.get_job_feedback(job_id)
        
        total = len(feedback_list)
        incorporated = sum(1 for f in feedback_list if f.incorporated)
        pending = total - incorporated
        
        # Rating distribution
        by_rating = {}
        by_type = {"per_query": 0, "overall": 0}
        all_tags = []
        variants_set = set()
        
        for f in feedback_list:
            # By rating
            rating_key = f.rating.value
            by_rating[rating_key] = by_rating.get(rating_key, 0) + 1
            
            # By type
            by_type[f.feedback_type.value] += 1
            
            # Tags
            if f.tags:
                all_tags.extend(f.tags)
            
            # Variants
            variants_set.add(f.variant_id)
        
        # Most common tags
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        most_tagged = sorted(tag_counts.keys(), key=lambda t: tag_counts[t], reverse=True)[:10]
        
        # Average rating
        avg_rating = None
        if total > 0:
            avg_rating = sum(f.rating_numeric for f in feedback_list) / total
        
        return {
            "total_feedback": total,
            "incorporated_count": incorporated,
            "pending_count": pending,
            "average_rating": avg_rating,
            "feedback_by_type": by_type,
            "feedback_by_rating": by_rating,
            "most_tagged": most_tagged,
            "variants_with_feedback": len(variants_set),
        }
    
    def get_unincorporated_feedback(self, job_id: int) -> List[GEPAHumanFeedback]:
        """Get all unincorporated feedback for a job (for mutation guidance)."""
        return self.db.query(GEPAHumanFeedback).filter(
            and_(
                GEPAHumanFeedback.job_id == job_id,
                GEPAHumanFeedback.incorporated == False,
            )
        ).order_by(
            GEPAHumanFeedback.rating_numeric.asc(),  # negative first (-2..)
            GEPAHumanFeedback.created_at.desc(),
        ).all()

    def seed_feedback_on_baseline(
        self,
        job_id: int,
        user_id: int,
        seed_feedback: List[Dict[str, Any]],
    ) -> int:
        """
        Attach external feedback (e.g., prod/user feedback) to the BASELINE variant of a job.
        This makes it immediately available to guide mutations during this run.
        """
        job = self.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        baseline = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job.id,
                CandidateVariant.is_baseline == True,
            )
        ).first()
        if not baseline:
            raise ValueError("Baseline variant not found")

        rating_map = {
            -2: FeedbackRating.STRONGLY_NEGATIVE,
            -1: FeedbackRating.NEGATIVE,
            0: FeedbackRating.NEUTRAL,
            1: FeedbackRating.POSITIVE,
            2: FeedbackRating.STRONGLY_POSITIVE,
        }

        created = 0
        for item in seed_feedback:
            rating_numeric = int(item.get("rating_numeric", -1))
            rating_numeric = max(-2, min(2, rating_numeric))
            rating_enum = rating_map[rating_numeric]

            fb = GEPAHumanFeedback(
                job_id=job.id,
                variant_id=baseline.id,
                user_id=user_id,
                feedback_type=FeedbackType.OVERALL,
                rating=rating_enum,
                rating_numeric=rating_numeric,
                comment=item.get("comment"),
                tags=item.get("tags"),
                improvement_suggestions=item.get("improvement_suggestions"),
                target_components=item.get("target_components"),
                incorporated=False,
            )
            self.db.add(fb)
            created += 1

        self.db.commit()
        logger.info("gepa_seed_feedback_attached", job_id=job.job_id, created=created)
        return created
    
    def mark_feedback_incorporated(
        self,
        feedback_ids: List[int],
        incorporated_in_variant_id: int,
    ) -> None:
        """Mark feedback as incorporated into a new variant."""
        now = datetime.utcnow()
        self.db.query(GEPAHumanFeedback).filter(
            GEPAHumanFeedback.id.in_(feedback_ids)
        ).update({
            "incorporated": True,
            "incorporated_at": now,
            "incorporated_in_variant_id": incorporated_in_variant_id,
        }, synchronize_session=False)
        self.db.commit()
    
    def compute_feedback_bonus(self, variant_id: int) -> float:
        """
        Compute a fitness bonus/penalty based on human feedback.
        
        Returns a value between -0.2 and +0.2 to adjust the variant's fitness.
        """
        feedback_list = self.get_variant_feedback(variant_id)
        if not feedback_list:
            return 0.0
        
        # Weight recent feedback more heavily
        total_weight = 0.0
        weighted_sum = 0.0
        
        for i, f in enumerate(feedback_list):
            # More recent feedback gets higher weight (index 0 = most recent)
            weight = 1.0 / (i + 1)
            # Normalize rating to [-1, 1]
            normalized_rating = f.rating_numeric / 2.0
            weighted_sum += normalized_rating * weight
            total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        # Average weighted rating in [-1, 1]
        avg_weighted = weighted_sum / total_weight
        # Scale to [-0.2, 0.2]
        return avg_weighted * 0.2
    
    def build_feedback_context_for_mutation(self, job_id: int) -> str:
        """
        Build a context string from human feedback for use in reflection-guided mutations.
        
        This summarizes the feedback to help the LLM understand what improvements are needed.
        """
        feedback_list = self.get_unincorporated_feedback(job_id)
        
        if not feedback_list:
            return ""
        
        # Group by type
        negative_feedback = [f for f in feedback_list if f.rating_numeric < 0]
        positive_feedback = [f for f in feedback_list if f.rating_numeric > 0]
        
        context_parts = []
        
        if negative_feedback:
            context_parts.append("### Issues identified by human reviewers:")
            for f in negative_feedback[:5]:  # Limit to top 5
                parts = []
                if f.comment:
                    parts.append(f.comment)
                if f.improvement_suggestions:
                    parts.append(f"Suggestion: {f.improvement_suggestions}")
                if f.tags:
                    parts.append(f"Tags: {', '.join(f.tags)}")
                if parts:
                    context_parts.append(f"- {' | '.join(parts)}")
        
        if positive_feedback:
            context_parts.append("\n### What reviewers liked:")
            for f in positive_feedback[:3]:  # Limit to top 3
                if f.comment:
                    context_parts.append(f"- {f.comment}")
        
        return "\n".join(context_parts)
