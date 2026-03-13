"""
RAG Evaluation Celery Tasks

Async tasks for running RAG evaluations.
"""
import asyncio
from celery import Task

from src.celery_app import celery_app
from src.core.logging import get_logger
from src.models import database
from src.models.rag_eval import EvalRunStatus

logger = get_logger(__name__, component="tasks.rag_eval")


class RAGEvalTask(Task):
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


@celery_app.task(bind=True, base=RAGEvalTask, max_retries=1, soft_time_limit=3600)
def run_rag_evaluation(self, eval_run_id: int):
    """
    Run a RAG evaluation asynchronously.
    
    Args:
        eval_run_id: ID of the RAGEvalRun to execute
    """
    from src.services.rag_eval_service import RAGEvalService
    from src.models.rag_eval import RAGEvalRun
    
    logger.info(
        "rag_eval_task_started",
        eval_run_id=eval_run_id,
        task_id=self.request.id,
    )
    
    try:
        # Get the evaluation run
        eval_run = self.db.query(RAGEvalRun).filter(RAGEvalRun.id == eval_run_id).first()
        
        if not eval_run:
            logger.error(f"Evaluation run {eval_run_id} not found")
            return {"status": "error", "message": "Evaluation run not found"}
        
        if eval_run.status not in [EvalRunStatus.PENDING, EvalRunStatus.RUNNING]:
            logger.warning(
                f"Evaluation run {eval_run_id} has status {eval_run.status}, skipping"
            )
            return {"status": "skipped", "message": f"Status is {eval_run.status.value}"}
        
        # Create service and run evaluation
        service = RAGEvalService(self.db)
        
        # Run the async evaluation in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            eval_run = loop.run_until_complete(service.run_evaluation(eval_run))
        finally:
            loop.close()
        
        logger.info(
            "rag_eval_task_completed",
            eval_run_id=eval_run_id,
            run_id=eval_run.run_id,
            pass_rate=eval_run.pass_rate,
            status=eval_run.status.value,
        )
        
        return {
            "status": "completed",
            "run_id": eval_run.run_id,
            "pass_rate": eval_run.pass_rate,
            "total_questions": eval_run.total_questions,
            "pass_count": eval_run.pass_count,
            "fail_count": eval_run.fail_count,
        }
        
    except Exception as e:
        logger.error(
            "rag_eval_task_failed",
            eval_run_id=eval_run_id,
            error=str(e),
            exc_info=True,
        )
        
        # Update status in database
        try:
            eval_run = self.db.query(RAGEvalRun).filter(RAGEvalRun.id == eval_run_id).first()
            if eval_run:
                eval_run.status = EvalRunStatus.FAILED
                eval_run.error_message = str(e)
                self.db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update eval run status: {db_error}")
        
        raise


@celery_app.task(bind=True, base=RAGEvalTask, max_retries=1, soft_time_limit=3600)
def run_rag_evaluation_v2(self, eval_run_id: int, eval_set_id: int = None):
    """
    Run a RAG evaluation asynchronously (v2 with eval set support).
    
    Args:
        eval_run_id: ID of the RAGEvalRun to execute
        eval_set_id: Optional ID of the EvalSet to use
    """
    from src.services.rag_eval_service import RAGEvalService
    from src.services.eval_set_service import EvalSetService
    from src.models.rag_eval import RAGEvalRun
    
    logger.info(
        "rag_eval_v2_task_started",
        eval_run_id=eval_run_id,
        eval_set_id=eval_set_id,
        task_id=self.request.id,
    )
    
    try:
        # Get the evaluation run
        eval_run = self.db.query(RAGEvalRun).filter(RAGEvalRun.id == eval_run_id).first()
        
        if not eval_run:
            logger.error(f"Evaluation run {eval_run_id} not found")
            return {"status": "error", "message": "Evaluation run not found"}
        
        if eval_run.status not in [EvalRunStatus.PENDING, EvalRunStatus.RUNNING]:
            logger.warning(
                f"Evaluation run {eval_run_id} has status {eval_run.status}, skipping"
            )
            return {"status": "skipped", "message": f"Status is {eval_run.status.value}"}
        
        # Get eval set if specified
        eval_set = None
        if eval_set_id:
            eval_set_service = EvalSetService(self.db)
            eval_set = eval_set_service.get_eval_set(eval_set_id)
            if not eval_set:
                logger.error(f"Eval set {eval_set_id} not found")
                eval_run.status = EvalRunStatus.FAILED
                eval_run.error_message = f"Eval set {eval_set_id} not found"
                self.db.commit()
                return {"status": "error", "message": f"Eval set {eval_set_id} not found"}
        
        # Create service and run evaluation
        service = RAGEvalService(self.db)
        
        # Run the async evaluation in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            eval_run = loop.run_until_complete(service.run_evaluation_v2(eval_run, eval_set=eval_set))
        finally:
            loop.close()
        
        logger.info(
            "rag_eval_v2_task_completed",
            eval_run_id=eval_run_id,
            run_id=eval_run.run_id,
            pass_rate=eval_run.pass_rate,
            status=eval_run.status.value,
            eval_set_id=eval_set_id,
        )
        
        return {
            "status": "completed",
            "run_id": eval_run.run_id,
            "pass_rate": eval_run.pass_rate,
            "total_questions": eval_run.total_questions,
            "pass_count": eval_run.pass_count,
            "fail_count": eval_run.fail_count,
            "eval_set_id": eval_set_id,
        }
        
    except Exception as e:
        logger.error(
            "rag_eval_v2_task_failed",
            eval_run_id=eval_run_id,
            eval_set_id=eval_set_id,
            error=str(e),
            exc_info=True,
        )
        
        # Update status in database
        try:
            eval_run = self.db.query(RAGEvalRun).filter(RAGEvalRun.id == eval_run_id).first()
            if eval_run:
                eval_run.status = EvalRunStatus.FAILED
                eval_run.error_message = str(e)
                self.db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update eval run status: {db_error}")
        
        raise


@celery_app.task(bind=True, base=RAGEvalTask)
def cleanup_old_eval_runs(self, days_old: int = 30):
    """
    Clean up old evaluation runs and their results.
    
    Args:
        days_old: Delete runs older than this many days
    """
    from datetime import datetime, timedelta
    from src.models.rag_eval import RAGEvalRun, RAGEvalResult, RAGEvalTelemetryEvent
    
    logger.info(f"Cleaning up evaluation runs older than {days_old} days")
    
    cutoff = datetime.utcnow() - timedelta(days=days_old)
    
    try:
        # Find old runs
        old_runs = self.db.query(RAGEvalRun).filter(
            RAGEvalRun.created_at < cutoff
        ).all()
        
        if not old_runs:
            logger.info("No old evaluation runs to clean up")
            return {"deleted": 0}
        
        run_ids = [r.id for r in old_runs]
        
        # Delete results
        results_deleted = self.db.query(RAGEvalResult).filter(
            RAGEvalResult.eval_run_id.in_(run_ids)
        ).delete(synchronize_session=False)
        
        # Delete telemetry events
        events_deleted = self.db.query(RAGEvalTelemetryEvent).filter(
            RAGEvalTelemetryEvent.eval_run_id.in_(run_ids)
        ).delete(synchronize_session=False)
        
        # Delete runs
        runs_deleted = self.db.query(RAGEvalRun).filter(
            RAGEvalRun.id.in_(run_ids)
        ).delete(synchronize_session=False)
        
        self.db.commit()
        
        logger.info(
            "rag_eval_cleanup_completed",
            runs_deleted=runs_deleted,
            results_deleted=results_deleted,
            events_deleted=events_deleted,
        )
        
        return {
            "runs_deleted": runs_deleted,
            "results_deleted": results_deleted,
            "events_deleted": events_deleted,
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        self.db.rollback()
        raise
