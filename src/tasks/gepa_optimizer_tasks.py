"""
GEPA Optimizer Celery Tasks

Async tasks for running GEPA optimization jobs in the background.
"""
import asyncio
from celery import Task

from src.celery_app import celery_app
from src.core.logging import get_logger
from src.models import database
from src.models.gepa_optimizer import OptimizerJobStatus

logger = get_logger(__name__, component="tasks.gepa_optimizer")


class GEPAOptimizerTask(Task):
    """Custom task class with database session handling."""
    
    _db = None
    
    @property
    def db(self):
        if self._db is None:
            if database.SessionLocal is None:
                database.init_database()
            self._db = database.SessionLocal()
        return self._db
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """Clean up database session after task completes."""
        if self._db:
            self._db.close()
            self._db = None


@celery_app.task(bind=True, base=GEPAOptimizerTask, max_retries=1, soft_time_limit=7200)  # 2 hour timeout
def run_gepa_optimization(self, job_id: int):
    """
    Run a GEPA optimization job asynchronously.
    
    Args:
        job_id: Database ID of the OptimizerJob to execute
    """
    from src.services.gepa_optimizer_service import GEPAOptimizerService
    from src.models.gepa_optimizer import OptimizerJob
    
    logger.info(
        "gepa_task_started",
        job_id=job_id,
        task_id=self.request.id,
    )
    
    try:
        # Get the optimizer job
        job = self.db.query(OptimizerJob).filter(OptimizerJob.id == job_id).first()
        
        if not job:
            logger.error(f"Optimizer job {job_id} not found")
            return {"status": "error", "message": "Optimizer job not found"}
        
        if job.status not in [OptimizerJobStatus.PENDING, OptimizerJobStatus.RUNNING, OptimizerJobStatus.PAUSED]:
            logger.warning(
                f"Optimizer job {job_id} has status {job.status}, skipping"
            )
            return {"status": "skipped", "message": f"Status is {job.status.value}"}
        
        # Update Celery task ID on job
        job.celery_task_id = self.request.id
        self.db.commit()
        
        # Create service and run optimization
        service = GEPAOptimizerService(self.db)
        
        # Run the async optimization in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            job = loop.run_until_complete(service.run_optimization(job))
        finally:
            loop.close()
        
        logger.info(
            "gepa_task_completed",
            job_id=job_id,
            job_job_id=job.job_id,
            status=job.status.value,
            iterations=job.current_iteration,
            evals_used=job.total_evals_used,
            best_quality=job.best_quality_score,
        )
        
        return {
            "status": "completed",
            "job_id": job.job_id,
            "iterations": job.current_iteration,
            "total_evals_used": job.total_evals_used,
            "best_quality_score": job.best_quality_score,
        }
        
    except Exception as e:
        logger.error(
            "gepa_task_failed",
            job_id=job_id,
            error=str(e),
            exc_info=True,
        )
        
        # Update status in database
        try:
            job = self.db.query(OptimizerJob).filter(OptimizerJob.id == job_id).first()
            if job and job.status not in [OptimizerJobStatus.CANCELLED]:
                job.status = OptimizerJobStatus.FAILED
                job.error_message = str(e)
                self.db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update optimizer job status: {db_error}")
        
        raise


@celery_app.task(bind=True, base=GEPAOptimizerTask)
def resume_gepa_optimization(self, job_id: int):
    """
    Resume a paused GEPA optimization job.
    
    Args:
        job_id: Database ID of the OptimizerJob to resume
    """
    from src.services.gepa_optimizer_service import GEPAOptimizerService
    from src.models.gepa_optimizer import OptimizerJob
    
    logger.info(
        "gepa_resume_task_started",
        job_id=job_id,
        task_id=self.request.id,
    )
    
    try:
        job = self.db.query(OptimizerJob).filter(OptimizerJob.id == job_id).first()
        
        if not job:
            return {"status": "error", "message": "Job not found"}
        
        if job.status != OptimizerJobStatus.PAUSED:
            return {"status": "error", "message": f"Job is not paused (status: {job.status.value})"}
        
        # Resume the job
        service = GEPAOptimizerService(self.db)
        service.resume_job(job.job_id)
        
        # Continue optimization
        job.celery_task_id = self.request.id
        self.db.commit()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            job = loop.run_until_complete(service.run_optimization(job))
        finally:
            loop.close()
        
        return {
            "status": "completed",
            "job_id": job.job_id,
            "iterations": job.current_iteration,
        }
        
    except Exception as e:
        logger.error("gepa_resume_failed", job_id=job_id, error=str(e), exc_info=True)
        raise


@celery_app.task(bind=True, base=GEPAOptimizerTask)
def cleanup_old_gepa_jobs(self, days_old: int = 30):
    """
    Clean up old GEPA optimization jobs and their data.
    
    Args:
        days_old: Delete jobs older than this many days
    """
    from datetime import datetime, timedelta
    from src.models.gepa_optimizer import (
        OptimizerJob, CandidateVariant, GEPAEvaluationResult,
        TraceArtifact, ParetoSnapshot, GEPATelemetryEvent
    )
    
    logger.info(f"Cleaning up GEPA jobs older than {days_old} days")
    
    cutoff = datetime.utcnow() - timedelta(days=days_old)
    
    try:
        # Find old completed/failed/cancelled jobs
        old_jobs = self.db.query(OptimizerJob).filter(
            OptimizerJob.created_at < cutoff,
            OptimizerJob.status.in_([
                OptimizerJobStatus.COMPLETED,
                OptimizerJobStatus.FAILED,
                OptimizerJobStatus.CANCELLED,
            ])
        ).all()
        
        if not old_jobs:
            logger.info("No old GEPA jobs to clean up")
            return {"deleted": 0}
        
        job_ids = [j.id for j in old_jobs]
        
        # Get variant IDs for cascade delete
        variant_ids = [
            v.id for v in self.db.query(CandidateVariant).filter(
                CandidateVariant.job_id.in_(job_ids)
            ).all()
        ]
        
        # Delete in order (respecting foreign keys)
        if variant_ids:
            # Delete evaluation results
            self.db.query(GEPAEvaluationResult).filter(
                GEPAEvaluationResult.variant_id.in_(variant_ids)
            ).delete(synchronize_session=False)
            
            # Delete trace artifacts
            self.db.query(TraceArtifact).filter(
                TraceArtifact.variant_id.in_(variant_ids)
            ).delete(synchronize_session=False)
        
        # Delete Pareto snapshots
        self.db.query(ParetoSnapshot).filter(
            ParetoSnapshot.job_id.in_(job_ids)
        ).delete(synchronize_session=False)
        
        # Delete telemetry events
        self.db.query(GEPATelemetryEvent).filter(
            GEPATelemetryEvent.job_id.in_(job_ids)
        ).delete(synchronize_session=False)
        
        # Delete variants
        self.db.query(CandidateVariant).filter(
            CandidateVariant.job_id.in_(job_ids)
        ).delete(synchronize_session=False)
        
        # Delete jobs
        jobs_deleted = self.db.query(OptimizerJob).filter(
            OptimizerJob.id.in_(job_ids)
        ).delete(synchronize_session=False)
        
        self.db.commit()
        
        logger.info(
            "gepa_cleanup_completed",
            jobs_deleted=jobs_deleted,
        )
        
        return {"jobs_deleted": jobs_deleted}
        
    except Exception as e:
        logger.error(f"GEPA cleanup failed: {e}", exc_info=True)
        self.db.rollback()
        raise


@celery_app.task(bind=True, base=GEPAOptimizerTask)
def evaluate_single_variant(self, job_id: int, variant_id: str):
    """
    Evaluate a single variant (useful for on-demand testing).
    
    Args:
        job_id: Database ID of the OptimizerJob
        variant_id: String variant_id to evaluate
    """
    from src.services.gepa_optimizer_service import GEPAOptimizerService
    from src.models.gepa_optimizer import OptimizerJob, CandidateVariant
    from sqlalchemy import and_
    
    logger.info(
        "gepa_single_eval_started",
        job_id=job_id,
        variant_id=variant_id,
    )
    
    try:
        job = self.db.query(OptimizerJob).filter(OptimizerJob.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Job not found"}
        
        variant = self.db.query(CandidateVariant).filter(
            and_(
                CandidateVariant.job_id == job_id,
                CandidateVariant.variant_id == variant_id
            )
        ).first()
        
        if not variant:
            return {"status": "error", "message": "Variant not found"}
        
        service = GEPAOptimizerService(self.db)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service._evaluate_variant(job, variant))
        finally:
            loop.close()
        
        self.db.commit()
        
        return {
            "status": "completed",
            "variant_id": variant_id,
            "quality_score": variant.quality_score,
            "groundedness_score": variant.groundedness_score,
        }
        
    except Exception as e:
        logger.error("gepa_single_eval_failed", error=str(e), exc_info=True)
        raise
