"""
Adoption Dashboard Celery Tasks.

Background tasks for syncing adoption metrics from external providers.
"""

import asyncio
from datetime import date, datetime, timezone
from typing import Dict, Any, Optional, List
from celery import Task

from src.celery_app import celery_app
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class AdoptionSyncTask(Task):
    """Base task class for adoption sync tasks with retry logic."""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 300}  # 5 minutes between retries
    retry_backoff = True
    retry_backoff_max = 3600  # Max 1 hour backoff
    retry_jitter = True
    soft_time_limit = 3600  # 1 hour max execution
    time_limit = 3660  # Hard limit 1hr + 1min


@celery_app.task(
    base=AdoptionSyncTask,
    bind=True,
    name="adoption.sync_provider"
)
def sync_adoption_provider(
    self,
    provider_id: int,
    customer_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Sync adoption metrics for a single provider.
    
    Args:
        provider_id: CustomerAIProvider ID
        customer_id: Customer ID
        start_date: Optional start date (ISO format)
        end_date: Optional end date (ISO format)
        force: If True, re-sync existing dates
        
    Returns:
        Dict with sync results
    """
    from src.models import database
    from src.models.customer import CustomerAIProvider
    from src.services.adoption.sync_service import AdoptionSyncService
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        logger.info(
            f"Starting adoption sync task: provider_id={provider_id}, "
            f"customer_id={customer_id}"
        )
        
        # Get provider configuration
        provider = db.query(CustomerAIProvider).filter(
            CustomerAIProvider.id == provider_id,
            CustomerAIProvider.customer_id == customer_id
        ).first()
        
        if not provider:
            return {
                "success": False,
                "error": f"Provider {provider_id} not found for customer {customer_id}"
            }
        
        if not provider.is_adoption_source:
            return {
                "success": False,
                "error": f"Provider {provider_id} is not configured for adoption tracking"
            }
        
        # Parse dates if provided
        parsed_start = None
        parsed_end = None
        if start_date:
            parsed_start = date.fromisoformat(start_date)
        if end_date:
            parsed_end = date.fromisoformat(end_date)
        
        # Create sync service and run sync
        sync_service = AdoptionSyncService(db)
        
        # Run async sync in event loop
        result = asyncio.run(
            sync_service.sync_provider(
                provider=provider,
                start_date=parsed_start,
                end_date=parsed_end,
                force=force
            )
        )
        
        logger.info(
            f"Adoption sync completed: provider_id={provider_id}, "
            f"records_synced={result.get('records_synced', 0)}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Adoption sync task failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    base=AdoptionSyncTask,
    bind=True,
    name="adoption.sync_all_providers"
)
def sync_all_adoption_providers(
    self,
    customer_id: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Sync all adoption-enabled providers.
    
    Args:
        customer_id: Optional filter to specific customer
        force: If True, re-sync all dates
        
    Returns:
        Dict with aggregated sync results
    """
    from src.models import database
    from src.services.adoption.sync_service import AdoptionSyncService
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        logger.info(
            f"Starting sync_all_adoption_providers: customer_id={customer_id or 'all'}"
        )
        
        sync_service = AdoptionSyncService(db)
        
        # Run async sync in event loop
        result = asyncio.run(
            sync_service.sync_all_providers(
                customer_id=customer_id,
                force=force
            )
        )
        
        logger.info(
            f"Sync all providers completed: "
            f"providers={result.get('providers_synced', 0)}, "
            f"records={result.get('total_records', 0)}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Sync all providers task failed: {e}")
        raise
    finally:
        db.close()


@celery_app.task(
    name="adoption.daily_sync",
    bind=True
)
def daily_adoption_sync(
    self,
    customer_id: Optional[str] = None,
    track_job: bool = True,
) -> Dict[str, Any]:
    """
    Daily scheduled sync for all adoption providers.
    
    Called by the dispatcher or manually for tenant-scoped execution.
    Runs tenant-scoped when customer_id is provided, otherwise runs sequentially
    across all configured providers.
    """
    from src.models import database
    from src.services.adoption.sync_service import AdoptionSyncService
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    job_name = "adoption-daily-sync"
    task_id = self.request.id
    start_time = datetime.now(timezone.utc)
    
    try:
        if track_job:
            _update_job_status(db, job_name, task_id, "running", start_time)
        
        logger.info(f"Starting daily adoption sync (customer_id={customer_id or 'all'})")
        
        sync_service = AdoptionSyncService(db)
        result = asyncio.run(
            sync_service.sync_all_providers(
                customer_id=customer_id,
                force=False
            )
        )

        status = "success" if result.get("success") else "failed"
        if track_job:
            _update_job_status(
                db,
                job_name,
                task_id,
                status,
                start_time,
                result=result,
                error=None if status == "success" else "One or more provider syncs failed",
            )

        logger.info(
            f"Daily adoption sync complete: customer_id={customer_id or 'all'}, "
            f"providers={result.get('providers_synced', 0)}, total_records={result.get('total_records', 0)}"
        )
        return result
        
    except Exception as e:
        logger.error(f"Daily adoption sync failed: {e}")
        if track_job:
            _update_job_status(db, job_name, task_id, "failed", start_time, error=str(e))
        raise
    finally:
        db.close()


@celery_app.task(
    name="adoption.sync_complete",
    bind=True
)
def adoption_sync_complete(
    self,
    results: List[Dict[str, Any]],
    job_name: str,
    task_id: str,
    start_time_iso: str,
    provider_count: int
) -> Dict[str, Any]:
    """
    Callback task that runs after all provider syncs complete.
    Aggregates results and updates job status with total duration.
    """
    from src.models import database
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    start_time = datetime.fromisoformat(start_time_iso)
    
    try:
        # Aggregate results from all provider syncs
        total_conversations = 0
        total_gpts = 0
        total_records = 0
        errors = []
        successful = 0
        
        for i, result in enumerate(results):
            if result.get("success"):
                successful += 1
                total_conversations += result.get("conversations_synced", 0)
                total_gpts += result.get("gpts_synced", 0)
                total_records += result.get("records_synced", 0)
            else:
                errors.append(result.get("error", f"Provider {i} failed"))
        
        final_result = {
            "success": len(errors) == 0,
            "providers_synced": successful,
            "providers_failed": len(errors),
            "total_conversations": total_conversations,
            "total_gpts": total_gpts,
            "total_records": total_records,
            "errors": errors if errors else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        status = "success" if len(errors) == 0 else "failed"
        error_msg = "; ".join(errors) if errors else None
        
        _update_job_status(db, job_name, task_id, status, start_time, result=final_result, error=error_msg)
        
        logger.info(f"Adoption sync complete: {successful}/{provider_count} providers synced, "
                    f"{total_conversations} conversations, {total_records} daily records")
        
        return final_result
        
    except Exception as e:
        logger.error(f"Failed to finalize adoption sync: {e}")
        _update_job_status(db, job_name, task_id, "failed", start_time, error=str(e))
        raise
    finally:
        db.close()


@celery_app.task(
    name="adoption.sync_chord_error",
    bind=True
)
def adoption_sync_chord_error(
    self,
    request,
    exc,
    traceback,
    job_name: str,
    task_id: str,
    start_time_iso: str
):
    """
    Error callback for the adoption sync chord.
    
    Called when the chord or its callback fails, ensuring the job status
    is updated to 'failed' instead of being stuck on 'running' forever.
    """
    from src.models import database
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    start_time = datetime.fromisoformat(start_time_iso)
    
    try:
        error_msg = f"Chord error: {exc}" if exc else "Unknown chord error"
        logger.error(f"Adoption sync chord failed for job={job_name}: {error_msg}")
        
        _update_job_status(
            db, job_name, task_id, "failed", start_time,
            error=error_msg
        )
    except Exception as e:
        logger.error(f"Failed to handle chord error for {job_name}: {e}", exc_info=True)
    finally:
        db.close()


def _update_job_status(
    db,
    job_name: str,
    task_id: str,
    status: str,
    start_time: datetime,
    result: Optional[Dict] = None,
    error: Optional[str] = None
):
    """Update the ScheduledJobConfig and ScheduledJobExecution with status."""
    import json
    from src.models.scheduled_job import ScheduledJobConfig, ScheduledJobExecution
    
    try:
        # Expire all to ensure fresh data from DB
        db.expire_all()
        
        # Update job config
        job = db.query(ScheduledJobConfig).filter(
            ScheduledJobConfig.job_name == job_name
        ).first()
        
        if job:
            job.last_run_status = status
            job.last_task_id = task_id
            
            if status in ("success", "failed"):
                end_time = datetime.now(timezone.utc)
                duration = int((end_time - start_time).total_seconds())
                job.last_run_duration_seconds = duration
                job.last_error = error if status == "failed" else None
            
            if status == "running":
                job.last_run_at = start_time
        
        # Update or create execution record
        execution = db.query(ScheduledJobExecution).filter(
            ScheduledJobExecution.task_id == task_id
        ).first()
        
        if not execution:
            # Create new execution record
            execution = ScheduledJobExecution(
                job_name=job_name,
                task_id=task_id,
                started_at=start_time,
                status=status,
                triggered_by="scheduler"
            )
            db.add(execution)
            logger.info(f"Created job execution record: job={job_name}, task_id={task_id}, status={status}")
        else:
            # Update existing record
            execution.status = status
            if status in ("success", "failed"):
                end_time = datetime.now(timezone.utc)
                execution.completed_at = end_time
                execution.duration_seconds = int((end_time - start_time).total_seconds())
                execution.error_message = error
                if result:
                    execution.result_summary = json.dumps(result)
            logger.info(f"Updated job execution record: job={job_name}, task_id={task_id}, status={status}")
        
        db.commit()
        logger.debug(f"Job status committed: job={job_name}, status={status}")
        
    except Exception as e:
        logger.error(f"Failed to update job status for {job_name}: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass

