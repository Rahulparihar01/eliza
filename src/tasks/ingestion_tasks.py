"""
Data Ingestion Celery Tasks

Async tasks for running data connector syncs (Airbyte CDK-based).
NO CrewAI - this is pure data extraction and loading.
"""
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from src.celery_app import celery_app
from src.core.logging import get_logger, LogCategory, bind_context

logger = get_logger(__name__, LogCategory.BUSINESS)


class IngestionTask(Task):
    """Base task class for ingestion tasks with retry logic."""
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3, 'countdown': 300}  # 5 minutes between retries
    retry_backoff = True
    retry_backoff_max = 3600  # Max 1 hour backoff
    retry_jitter = True
    soft_time_limit = 7200  # 2 hours max execution
    time_limit = 7260  # Hard limit 2hr + 1min


@celery_app.task(
    base=IngestionTask,
    bind=True,
    name="run_connector_sync",
    queue="ingestion"
)
def run_connector_sync(
    self,
    connector_id: int,
    customer_id: str,
    sync_mode: str = "full",
    sync_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute a connector sync programmatically.
    
    This task:
    1. Loads connector configuration (including encrypted credentials)
    2. Initializes the appropriate connector (e.g., PeopleDataLabs)
    3. Runs the sync (extract + load to staging)
    4. Updates sync status and telemetry
    
    Args:
        connector_id: Database ID of the connector configuration
        customer_id: Customer ID (for multi-tenant isolation)
        sync_mode: "full" or "incremental"
        sync_params: Optional override parameters for this sync
        
    Returns:
        Dict with sync results:
        {
            "success": bool,
            "sync_id": str,
            "records_synced": int,
            "duration_seconds": float,
            "error": Optional[str]
        }
    """
    bind_context(
        task="run_connector_sync",
        connector_id=connector_id,
        customer_id=customer_id,
        sync_mode=sync_mode
    )
    
    logger.info(
        "connector_sync_start",
        connector_id=connector_id,
        customer_id=customer_id,
        task_id=self.request.id,
        sync_mode=sync_mode
    )
    
    # Import database modules following your pattern (Rule 4b)
    from src.models import database
    
    # Ensure database is initialized (Rule 2)
    if database.SessionLocal is None:
        logger.info("SessionLocal not initialized, calling init_database()")
        database.init_database()
        
        if database.SessionLocal is None:
            raise RuntimeError("SessionLocal is still None after init_database()")
    
    db = database.SessionLocal()
    
    try:
        # Import service here to avoid circular dependencies
        from src.services.ingestion.connector_service import ConnectorService
        
        connector_service = ConnectorService(db)
        
        # Execute the sync
        sync_result = connector_service.execute_sync(
            connector_id=connector_id,
            customer_id=customer_id,
            sync_mode=sync_mode,
            sync_params=sync_params or {},
            task_id=self.request.id
        )
        
        logger.info(
            "connector_sync_complete",
            connector_id=connector_id,
            sync_id=sync_result.get("sync_id"),
            records_synced=sync_result.get("records_synced", 0),
            duration=sync_result.get("duration_seconds")
        )
        
        return sync_result
        
    except SoftTimeLimitExceeded:
        logger.error(
            "connector_sync_timeout",
            connector_id=connector_id,
            customer_id=customer_id,
            task_id=self.request.id
        )
        return {
            "success": False,
            "error": "Sync exceeded 2 hour time limit",
            "connector_id": connector_id
        }
        
    except Exception as e:
        logger.error(
            "connector_sync_exception",
            connector_id=connector_id,
            customer_id=customer_id,
            error=str(e),
            exc_info=True
        )
        return {
            "success": False,
            "error": str(e),
            "connector_id": connector_id
        }
        
    finally:
        db.close()


@celery_app.task(
    base=IngestionTask,
    bind=True,
    name="schedule_connector_sync",
    queue="ingestion"
)
def schedule_connector_sync(self, connector_id: int, customer_id: str) -> Dict[str, Any]:
    """
    Check if a connector should run and schedule it.
    Called by celery-beat for scheduled syncs.
    
    Args:
        connector_id: Connector configuration ID
        customer_id: Customer ID
        
    Returns:
        Dict with scheduling result
    """
    from src.models import database
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.services.ingestion.connector_service import ConnectorService
        
        connector_service = ConnectorService(db)
        
        # Check if sync should run (schedule, last run, etc.)
        should_run, reason = connector_service.should_run_sync(
            connector_id=connector_id,
            customer_id=customer_id
        )
        
        if should_run:
            # Queue the actual sync task
            task = run_connector_sync.delay(
                connector_id=connector_id,
                customer_id=customer_id,
                sync_mode="incremental"
            )
            
            logger.info(
                "connector_sync_scheduled",
                connector_id=connector_id,
                customer_id=customer_id,
                task_id=task.id
            )
            
            return {
                "scheduled": True,
                "task_id": task.id,
                "reason": reason
            }
        else:
            logger.info(
                "connector_sync_skipped",
                connector_id=connector_id,
                customer_id=customer_id,
                reason=reason
            )
            
            return {
                "scheduled": False,
                "reason": reason
            }
            
    finally:
        db.close()


@celery_app.task(
    base=IngestionTask,
    bind=True,
    name="test_connector_connection",
    queue="ingestion"
)
def test_connector_connection(
    self,
    connector_id: int,
    customer_id: str
) -> Dict[str, Any]:
    """
    Test a connector's connection and authentication.
    Used during connector setup to verify credentials.
    
    Args:
        connector_id: Connector configuration ID
        customer_id: Customer ID
        
    Returns:
        Dict with test results:
        {
            "success": bool,
            "healthy": bool,
            "message": str,
            "metadata": dict  # API limits, version, etc.
        }
    """
    from src.models import database
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        from src.services.ingestion.connector_service import ConnectorService
        
        connector_service = ConnectorService(db)
        
        test_result = connector_service.test_connection(
            connector_id=connector_id,
            customer_id=customer_id
        )
        
        logger.info(
            "connector_test_complete",
            connector_id=connector_id,
            customer_id=customer_id,
            healthy=test_result.get("healthy", False)
        )
        
        return test_result
        
    except Exception as e:
        logger.error(
            "connector_test_exception",
            connector_id=connector_id,
            customer_id=customer_id,
            error=str(e),
            exc_info=True
        )
        
        return {
            "success": False,
            "healthy": False,
            "message": f"Connection test failed: {str(e)}"
        }
        
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="sync_person_to_search_stores",
    queue="ingestion",
    max_retries=3,
    default_retry_delay=60
)
def sync_person_to_search_stores(
    self,
    person_id: int,
    customer_id: str,
    sync_elasticsearch: bool = True,
    sync_neo4j: bool = True
) -> Dict[str, Any]:
    """
    Async task to sync a PDL person to Elasticsearch and/or Neo4j.
    
    Called after a person is saved to PostgreSQL.
    Implements eventual consistency - failures don't block the main pipeline.
    
    Args:
        person_id: PDLPerson.id (database primary key)
        customer_id: Customer ID
        sync_elasticsearch: Whether to sync to ES
        sync_neo4j: Whether to sync to Neo4j
        
    Returns:
        Dict with sync results:
        {
            "success": bool,
            "elasticsearch": {"success": bool, "error": str},
            "neo4j": {"success": bool, "error": str}
        }
    """
    bind_context(
        task="sync_person_to_search_stores",
        person_id=person_id,
        customer_id=customer_id
    )
    
    logger.info(
        "person_sync_started",
        person_id=person_id,
        customer_id=customer_id,
        elasticsearch=sync_elasticsearch,
        neo4j=sync_neo4j
    )
    
    # Initialize database
    from src.models import database
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    results = {
        "success": False,
        "elasticsearch": {"success": False, "error": None},
        "neo4j": {"success": False, "error": None}
    }
    
    try:
        # Load person from database
        from src.models.connector import PDLPerson
        
        person = db.query(PDLPerson).filter(
            PDLPerson.id == person_id,
            PDLPerson.customer_id == customer_id
        ).first()
        
        if not person:
            error_msg = f"Person {person_id} not found"
            logger.error("person_sync_not_found", person_id=person_id)
            results["elasticsearch"]["error"] = error_msg
            results["neo4j"]["error"] = error_msg
            return results
        
        # Sync to Elasticsearch
        if sync_elasticsearch:
            try:
                from src.services.ingestion.elasticsearch_sync import ElasticsearchSyncService
                
                es_service = ElasticsearchSyncService()
                es_success = es_service.index_person(person)
                
                results["elasticsearch"]["success"] = es_success
                
                if es_success:
                    logger.info(
                        "person_indexed_elasticsearch",
                        person_id=person_id,
                        pdl_id=person.pdl_id
                    )
                else:
                    results["elasticsearch"]["error"] = "Index operation returned False"
                    
            except Exception as e:
                error_msg = str(e)
                results["elasticsearch"]["error"] = error_msg
                logger.error(
                    "elasticsearch_sync_failed",
                    person_id=person_id,
                    error=error_msg,
                    exc_info=True
                )
        
        # Sync to Neo4j
        if sync_neo4j:
            try:
                from src.services.ingestion.neo4j_sync import Neo4jSyncService
                
                neo4j_service = Neo4jSyncService()
                neo4j_success = neo4j_service.sync_person(person)
                
                results["neo4j"]["success"] = neo4j_success
                
                if neo4j_success:
                    logger.info(
                        "person_synced_neo4j",
                        person_id=person_id,
                        pdl_id=person.pdl_id
                    )
                else:
                    results["neo4j"]["error"] = "Sync operation returned False"
                    
                # Close Neo4j driver
                neo4j_service.close()
                    
            except Exception as e:
                error_msg = str(e)
                results["neo4j"]["error"] = error_msg
                logger.error(
                    "neo4j_sync_failed",
                    person_id=person_id,
                    error=error_msg,
                    exc_info=True
                )
        
        # Overall success if at least one succeeded
        results["success"] = (
            results["elasticsearch"]["success"] or 
            results["neo4j"]["success"]
        )
        
        logger.info(
            "person_sync_complete",
            person_id=person_id,
            elasticsearch_success=results["elasticsearch"]["success"],
            neo4j_success=results["neo4j"]["success"]
        )
        
        return results
        
    except Exception as e:
        logger.error(
            "person_sync_exception",
            person_id=person_id,
            error=str(e),
            exc_info=True
        )
        
        results["elasticsearch"]["error"] = str(e)
        results["neo4j"]["error"] = str(e)
        
        # Retry on unexpected errors
        raise self.retry(exc=e)
        
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="bulk_sync_persons_to_search_stores",
    queue="ingestion",
    max_retries=2
)
def bulk_sync_persons_to_search_stores(
    self,
    person_ids: List[int],
    customer_id: str
) -> Dict[str, Any]:
    """
    Bulk sync multiple persons to search stores.
    
    More efficient than individual syncs for large batches.
    
    Args:
        person_ids: List of PDLPerson.id values
        customer_id: Customer ID
        
    Returns:
        Dict with bulk sync results
    """
    bind_context(
        task="bulk_sync_persons",
        count=len(person_ids),
        customer_id=customer_id
    )
    
    logger.info(
        "bulk_sync_started",
        person_count=len(person_ids),
        customer_id=customer_id
    )
    
    # Initialize database
    from src.models import database
    
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        # Load persons
        from src.models.connector import PDLPerson
        
        persons = db.query(PDLPerson).filter(
            PDLPerson.id.in_(person_ids),
            PDLPerson.customer_id == customer_id
        ).all()
        
        if not persons:
            logger.warning("bulk_sync_no_persons_found", person_ids=person_ids)
            return {
                "success": False,
                "error": "No persons found",
                "elasticsearch": {"success": 0, "errors": 0},
                "neo4j": {"success": 0, "errors": 0}
            }
        
        results = {
            "success": True,
            "elasticsearch": {"success": 0, "errors": 0},
            "neo4j": {"success": 0, "errors": 0}
        }
        
        # Bulk sync to Elasticsearch
        try:
            from src.services.ingestion.elasticsearch_sync import ElasticsearchSyncService
            
            es_service = ElasticsearchSyncService()
            es_results = es_service.bulk_index_persons(persons)
            
            results["elasticsearch"] = es_results
            
            logger.info(
                "bulk_elasticsearch_complete",
                success=es_results["success"],
                errors=es_results["errors"]
            )
            
        except Exception as e:
            logger.error("bulk_elasticsearch_failed", error=str(e), exc_info=True)
            results["elasticsearch"]["errors"] = len(persons)
        
        # Sync to Neo4j (individual - no bulk method yet)
        try:
            from src.services.ingestion.neo4j_sync import Neo4jSyncService
            
            neo4j_service = Neo4jSyncService()
            
            for person in persons:
                try:
                    if neo4j_service.sync_person(person):
                        results["neo4j"]["success"] += 1
                    else:
                        results["neo4j"]["errors"] += 1
                except Exception as e:
                    logger.error(
                        "neo4j_person_sync_failed",
                        person_id=person.id,
                        error=str(e)
                    )
                    results["neo4j"]["errors"] += 1
            
            neo4j_service.close()
            
            logger.info(
                "bulk_neo4j_complete",
                success=results["neo4j"]["success"],
                errors=results["neo4j"]["errors"]
            )
            
        except Exception as e:
            logger.error("bulk_neo4j_failed", error=str(e), exc_info=True)
            results["neo4j"]["errors"] = len(persons)
        
        return results
        
    finally:
        db.close()

