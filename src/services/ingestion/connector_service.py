"""
Connector Service - Orchestration Layer

Manages connector configurations, sync runs, and data ingestion pipeline.
Coordinates between connectors, database, and Celery tasks.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from uuid import uuid4
import json

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.core.logging import get_logger, LogCategory, bind_context
from src.core.config import get_settings
from src.models.connector import (
    ConnectorConfiguration,
    ConnectorSyncRun,
    IngestedData,
    ConnectorTelemetry,
    SyncStatus,
    SyncMode,
    IngestionStatus,
    ConnectorTelemetryEventType
)
from src.models.customer import Customer, CustomerAIProvider
from src.utils.encryption import encrypt_value, decrypt_value, EncryptionError
from .connectors import create_connector, validate_connector_config, get_connector_class

logger = get_logger(__name__, LogCategory.BUSINESS)


class ConnectorService:
    """
    Service for managing data connectors and sync operations.
    
    Responsibilities:
    - CRUD operations for ConnectorConfiguration
    - Credential encryption/decryption
    - Sync orchestration (start, monitor, cancel)
    - Telemetry tracking
    - Cost estimation and validation
    """
    
    def __init__(self, db: Session):
        """Initialize connector service."""
        self.db = db
        self.settings = get_settings()
    
    # -------------------------------------------------------------------------
    # Configuration Management
    # -------------------------------------------------------------------------
    
    def create_configuration(
        self,
        customer_id: str,
        connector_type: str,
        connector_name: str,
        credentials: Dict[str, str],
        sync_config: Dict[str, Any],
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by_user_id: Optional[int] = None,
        use_shared_credentials: bool = False,
        sync_schedule: Optional[str] = None
    ) -> ConnectorConfiguration:
        """
        Create new connector configuration.
        
        Steps:
        1. Validate connector type exists
        2. Validate sync configuration
        3. Test connection
        4. Estimate record count
        5. Encrypt credentials
        6. Save to database
        
        Args:
            customer_id: Customer identifier
            connector_type: Type identifier (e.g., "people_data_labs")
            connector_name: User-friendly name
            credentials: Unencrypted credentials dict
            sync_config: Connector-specific configuration
            description: Optional description
            tags: Optional tags for filtering
            created_by_user_id: User who created this config
            use_shared_credentials: Use customer-wide credentials
            sync_schedule: Cron expression for scheduled syncs
            
        Returns:
            Created ConnectorConfiguration
            
        Raises:
            ValueError: If validation fails
            EncryptionError: If credential encryption fails
        """
        bind_context(
            operation="create_configuration",
            customer_id=customer_id,
            connector_type=connector_type
        )
        
        # 1. Check for duplicate connector name
        # A duplicate is: same name for the same customer (among enabled connectors)
        # Different names are allowed even with identical configurations
        existing = self.db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.customer_id == customer_id,
            ConnectorConfiguration.connector_name == connector_name,
            ConnectorConfiguration.is_enabled == True  # Only check enabled connectors
        ).first()
        
        if existing:
            logger.error(
                "duplicate_connector_name",
                connector_name=connector_name,
                existing_id=existing.connector_id
            )
            raise ValueError(
                f"A connector named '{connector_name}' already exists. "
                f"Please choose a different name."
            )
        
        # 2. Validate connector type
        try:
            connector_class = get_connector_class(connector_type)
        except ValueError as e:
            logger.error("invalid_connector_type", error=str(e))
            raise
        
        # 3. Validate configuration
        is_valid, error_msg = validate_connector_config(connector_type, sync_config)
        if not is_valid:
            logger.error("invalid_sync_config", error=error_msg)
            raise ValueError(f"Invalid sync configuration: {error_msg}")
        
        # 4. Test connection
        logger.info("testing_connector_connection", connector_name=connector_name)
        connector = create_connector(
            connector_type=connector_type,
            credentials=credentials,
            config=sync_config,
            customer_id=customer_id
        )
        
        check_result = connector.check()
        if check_result["status"] != "healthy":
            error_msg = check_result.get("message", "Connection test failed")
            logger.error("connector_check_failed", error=error_msg)
            raise ValueError(f"Connector connection test failed: {error_msg}")
        
        # 5. Estimate record count (for cost validation)
        estimated_count = None
        if hasattr(connector, 'estimate_record_count'):
            # Pass sync_config as query_params for estimate
            estimated_count = connector.estimate_record_count(sync_config)
            logger.info(
                "connector_estimate",
                connector_name=connector_name,
                estimated_count=estimated_count
            )
            
            # Check if cost warning threshold exceeded
            if estimated_count and estimated_count > 0:
                estimated_cost = estimated_count * self.settings.connector_cost_per_record
                if estimated_cost > self.settings.connector_cost_warning_threshold:
                    # Require acknowledgment in config
                    if not sync_config.get("estimated_cost_acknowledged"):
                        logger.warning(
                            "cost_acknowledgment_required",
                            estimated_count=estimated_count,
                            estimated_cost=estimated_cost
                        )
                        raise ValueError(
                            f"This query will fetch approximately {estimated_count:,} records "
                            f"(estimated cost: ${estimated_cost:.2f}). "
                            f"Please acknowledge by setting 'estimated_cost_acknowledged': true in config."
                        )
        
        # 5. Encrypt credentials
        if not use_shared_credentials:
            try:
                credentials_json = json.dumps(credentials)
                credentials_encrypted = encrypt_value(credentials_json)
            except EncryptionError as e:
                logger.error("credential_encryption_failed", error=str(e))
                raise
        else:
            credentials_encrypted = None
        
        # 6. Save to database
        connector_id = f"{connector_type}_{customer_id}_{uuid4().hex[:8]}"
        
        config_record = ConnectorConfiguration(
            connector_id=connector_id,
            connector_type=connector_type,
            connector_name=connector_name,
            description=description,
            tags=tags or [],
            customer_id=customer_id,
            use_shared_credentials=use_shared_credentials,
            credentials_encrypted=credentials_encrypted,
            sync_config=sync_config,
            sync_config_version=1,
            sync_config_history=[],
            sync_schedule=sync_schedule,
            sync_mode=SyncMode.FULL_REFRESH.value,
            is_enabled=True,
            created_by_user_id=created_by_user_id
        )
        
        self.db.add(config_record)
        
        try:
            self.db.commit()
            self.db.refresh(config_record)
            
            logger.info(
                "connector_configuration_created",
                connector_id=connector_id,
                connector_name=connector_name,
                customer_id=customer_id,
                estimated_count=estimated_count
            )
            
            return config_record
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error("connector_configuration_save_failed", error=str(e))
            raise ValueError("Failed to save connector configuration")
    
    def update_configuration(
        self,
        connector_id: str,
        customer_id: str,
        updates: Dict[str, Any]
    ) -> ConnectorConfiguration:
        """
        Update connector configuration.
        
        If sync_config is updated:
        - Validate new configuration
        - Version the config (increment version, save old to history)
        - Test connection with new config
        
        Args:
            connector_id: Connector identifier
            customer_id: Customer ID (for authorization)
            updates: Fields to update
            
        Returns:
            Updated ConnectorConfiguration
        """
        bind_context(
            operation="update_configuration",
            connector_id=connector_id,
            customer_id=customer_id
        )
        
        # Fetch existing config
        config = self.get_configuration(connector_id, customer_id)
        if not config:
            raise ValueError(f"Connector {connector_id} not found")
        
        # Handle sync_config updates (versioning)
        if "sync_config" in updates:
            new_sync_config = updates["sync_config"]
            
            # Validate new config
            is_valid, error_msg = validate_connector_config(
                config.connector_type,
                new_sync_config
            )
            if not is_valid:
                raise ValueError(f"Invalid sync configuration: {error_msg}")
            
            # Version the config
            old_config_history = config.sync_config_history or []
            old_config_history.append({
                "version": config.sync_config_version,
                "config": config.sync_config,
                "updated_at": datetime.utcnow().isoformat()
            })
            
            config.sync_config = new_sync_config
            config.sync_config_version += 1
            config.sync_config_history = old_config_history
            
            logger.info(
                "sync_config_versioned",
                connector_id=connector_id,
                new_version=config.sync_config_version
            )
        
        # Update other fields
        updatable_fields = [
            "connector_name", "description", "tags", "sync_schedule",
            "is_enabled", "sync_mode"
        ]
        for field in updatable_fields:
            if field in updates:
                setattr(config, field, updates[field])
        
        # Handle credential updates
        if "credentials" in updates:
            new_credentials = updates["credentials"]
            credentials_json = json.dumps(new_credentials)
            config.credentials_encrypted = encrypt_value(credentials_json)
            
            logger.info("connector_credentials_updated", connector_id=connector_id)
        
        try:
            self.db.commit()
            self.db.refresh(config)
            
            logger.info(
                "connector_configuration_updated",
                connector_id=connector_id
            )
            
            return config
            
        except IntegrityError as e:
            self.db.rollback()
            logger.error("connector_update_failed", error=str(e))
            raise ValueError("Failed to update connector configuration")
    
    def get_configuration(
        self,
        connector_id: str,
        customer_id: str
    ) -> Optional[ConnectorConfiguration]:
        """Get connector configuration by ID."""
        return self.db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.connector_id == connector_id,
            ConnectorConfiguration.customer_id == customer_id
        ).first()
    
    def get_configuration_by_id(
        self,
        config_id: int
    ) -> Optional[ConnectorConfiguration]:
        """Get connector configuration by numeric ID."""
        return self.db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.id == config_id
        ).first()
    
    def list_configurations(
        self,
        customer_id: str,
        connector_type: Optional[str] = None,
        is_enabled: Optional[bool] = None
    ) -> List[ConnectorConfiguration]:
        """List connector configurations with optional filters."""
        query = self.db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.customer_id == customer_id
        )
        
        if connector_type:
            query = query.filter(ConnectorConfiguration.connector_type == connector_type)
        
        if is_enabled is not None:
            query = query.filter(ConnectorConfiguration.is_enabled == is_enabled)
        
        return query.order_by(ConnectorConfiguration.created_at.desc()).all()
    
    def delete_configuration(
        self,
        connector_id: str,
        customer_id: str
    ) -> bool:
        """
        Delete connector configuration.
        
        Soft delete: mark as disabled and archive.
        Related sync runs and data are preserved for audit.
        """
        config = self.get_configuration(connector_id, customer_id)
        if not config:
            return False
        
        config.is_enabled = False
        self.db.commit()
        
        logger.info(
            "connector_configuration_deleted",
            connector_id=connector_id,
            customer_id=customer_id
        )
        
        return True
    
    # -------------------------------------------------------------------------
    # Credential Management
    # -------------------------------------------------------------------------
    
    def get_credentials(
        self,
        config: ConnectorConfiguration
    ) -> Dict[str, str]:
        """
        Get decrypted credentials for a connector.
        
        If using shared credentials, fetch from CustomerAIProvider.
        Otherwise, decrypt from connector config.
        """
        if config.use_shared_credentials:
            # Fetch shared credentials (e.g., from CustomerAIProvider)
            # For now, this is a placeholder - implement based on your auth model
            logger.warning(
                "shared_credentials_not_implemented",
                connector_id=config.connector_id
            )
            raise NotImplementedError("Shared credentials not yet implemented")
        else:
            if not config.credentials_encrypted:
                raise ValueError("No credentials stored for this connector")
            
            try:
                credentials_json = decrypt_value(config.credentials_encrypted)
                return json.loads(credentials_json)
            except EncryptionError as e:
                logger.error(
                    "credential_decryption_failed",
                    connector_id=config.connector_id,
                    error=str(e)
                )
                raise
    
    # -------------------------------------------------------------------------
    # Sync Orchestration
    # -------------------------------------------------------------------------
    
    def trigger_sync(
        self,
        connector_id: str,
        customer_id: str,
        manual_trigger: bool = True
    ) -> ConnectorSyncRun:
        """
        Trigger a connector sync.
        
        Steps:
        1. Validate connector is enabled
        2. Check no active sync is running
        3. Create ConnectorSyncRun record
        4. Dispatch Celery task (run_connector_sync)
        5. Return sync run record
        
        Args:
            connector_id: Connector identifier
            customer_id: Customer ID
            manual_trigger: True if manually triggered, False if scheduled
            
        Returns:
            ConnectorSyncRun record
        """
        bind_context(
            operation="trigger_sync",
            connector_id=connector_id,
            customer_id=customer_id
        )
        
        # 1. Fetch and validate configuration
        config = self.get_configuration(connector_id, customer_id)
        if not config:
            raise ValueError(f"Connector {connector_id} not found")
        
        if not config.is_enabled:
            raise ValueError(f"Connector {connector_id} is disabled")
        
        # 2. Check for active syncs
        active_sync = self.db.query(ConnectorSyncRun).filter(
            ConnectorSyncRun.connector_id == config.id,
            ConnectorSyncRun.status.in_([SyncStatus.PENDING.value, SyncStatus.RUNNING.value])
        ).first()
        
        if active_sync:
            raise ValueError(
                f"Sync already in progress for connector {connector_id} "
                f"(sync_id: {active_sync.sync_id})"
            )
        
        # 3. Create sync run record
        sync_id = f"sync_{uuid4().hex}"
        
        sync_run = ConnectorSyncRun(
            sync_id=sync_id,
            connector_id=config.id,
            customer_id=customer_id,
            sync_mode=config.sync_mode,
            triggered_by="manual" if manual_trigger else "scheduled",
            status=SyncStatus.PENDING.value,
            records_extracted=0,
            records_loaded=0,
            records_skipped=0,
            records_failed=0
        )
        
        self.db.add(sync_run)
        self.db.commit()
        self.db.refresh(sync_run)
        
        # 4. Log telemetry
        self._log_telemetry(
            sync_id=sync_id,
            customer_id=customer_id,
            event_type=ConnectorTelemetryEventType.SYNC_STARTED,
            current_stage="triggering",
            user_message=f"Sync triggered for {config.connector_name}",
            metadata={
                "manual_trigger": manual_trigger,
                "connector_name": config.connector_name
            }
        )
        
        # 5. Dispatch Celery task (if available)
        try:
            from src.tasks.ingestion_tasks import run_connector_sync
            
            logger.info(
                "dispatching_celery_task",
                sync_id=sync_id,
                connector_id=connector_id,
                customer_id=customer_id,
                sync_mode=config.sync_mode
            )
            
            task = run_connector_sync.delay(
                connector_id=connector_id,
                customer_id=customer_id,
                sync_mode=config.sync_mode,
                sync_params={
                    "sync_run_id": sync_run.id,
                    "sync_id": sync_id,
                    "connector_type": config.connector_type,
                    "sync_config": config.sync_config
                }
            )
            
            # Update with Celery task ID
            sync_run.celery_task_id = task.id
            self.db.commit()
            
            logger.info(
                "celery_task_dispatched",
                sync_id=sync_id,
                task_id=task.id
            )
        except ImportError as e:
            # Celery not available (e.g., in tests)
            logger.warning(
                "celery_not_available",
                sync_id=sync_id,
                error=str(e),
                note="Celery not installed, sync must be executed manually"
            )
        except Exception as e:
            # Any other error
            logger.error(
                "celery_task_dispatch_failed",
                sync_id=sync_id,
                error=str(e),
                error_type=type(e).__name__
            )
            # Don't fail the whole request, just log it
            pass
        
        return sync_run
    
    def _log_telemetry(
        self,
        sync_id: str,
        customer_id: str,
        event_type: ConnectorTelemetryEventType,
        metadata: Optional[Dict[str, Any]] = None,
        records_processed: int = 0,
        api_calls_made: int = 0,
        cost_so_far: float = 0.0,
        progress_percentage: Optional[float] = None,
        current_stage: Optional[str] = None,
        user_message: Optional[str] = None
    ):
        """Log telemetry event for connector sync."""
        telemetry = ConnectorTelemetry(
            sync_id=sync_id,
            customer_id=customer_id,
            event_type=event_type.value,
            records_processed=records_processed,
            api_calls_made=api_calls_made,
            cost_so_far=cost_so_far,
            progress_percentage=progress_percentage,
            current_stage=current_stage,
            user_message=user_message,
            telemetry_metadata=metadata or {}
        )
        
        self.db.add(telemetry)
        self.db.commit()
    
    # -------------------------------------------------------------------------
    # Sync Execution (Full Pipeline)
    # -------------------------------------------------------------------------
    
    def execute_sync(
        self,
        connector_id: str,
        customer_id: str,
        sync_mode: str,
        sync_params: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """
        Execute complete connector sync pipeline.
        
        Pipeline:
        1. Load connector configuration and credentials
        2. Initialize connector
        3. Fetch sync run record
        4. Update status to RUNNING
        5. Stream records from connector
        6. Save batches to IngestedData (staging)
        7. Transform batches to domain models (PDLPerson)
        8. Log telemetry
        9. Update sync run with final status
        
        Args:
            connector_id: Connector identifier
            customer_id: Customer ID
            sync_mode: "full" or "incremental"
            sync_params: Sync parameters (includes sync_run_id)
            task_id: Celery task ID
            
        Returns:
            Sync result dictionary
        """
        start_time = datetime.utcnow()
        
        bind_context(
            operation="execute_sync",
            connector_id=connector_id,
            customer_id=customer_id,
            task_id=task_id
        )
        
        # Extract sync_run_id from params
        sync_run_id = sync_params.get("sync_run_id")
        sync_id = sync_params.get("sync_id")
        connector_type = sync_params.get("connector_type")
        config_dict = sync_params.get("sync_config", {})
        
        if not sync_run_id:
            raise ValueError("sync_run_id required in sync_params")
        
        # Fetch sync run record
        sync_run = self.db.query(ConnectorSyncRun).filter(
            ConnectorSyncRun.id == sync_run_id
        ).first()
        
        if not sync_run:
            raise ValueError(f"Sync run {sync_run_id} not found")
        
        # Fetch connector configuration
        config = self.get_configuration(connector_id, customer_id)
        if not config:
            raise ValueError(f"Connector {connector_id} not found")
        
        try:
            # Update status to RUNNING
            sync_run.status = SyncStatus.RUNNING.value
            sync_run.started_at = start_time
            self.db.commit()
            
            # Get credentials
            credentials = self.get_credentials(config)
            
            # Initialize connector
            from .connectors import create_connector
            connector = create_connector(
                connector_type=connector_type,
                credentials=credentials,
                config=config_dict,
                customer_id=customer_id
            )
            
            logger.info(
                "connector_initialized",
                connector_id=connector_id,
                connector_type=connector_type,
                sync_id=sync_id
            )
            
            # Initialize transformer (for PDL)
            transformer = None
            if connector_type == "people_data_labs":
                from .transformers import PDLTransformer
                transformer = PDLTransformer(self.db)
            
            # Stream and process records
            total_records = 0
            total_batches = 0
            records_loaded = 0
            records_skipped = 0
            records_failed = 0
            
            for batch in connector.read_stream(sync_mode=sync_mode, sync_params=config_dict):
                if not batch:
                    continue
                
                total_batches += 1
                batch_size = len(batch)
                total_records += batch_size
                
                logger.debug(
                    "processing_batch",
                    sync_id=sync_id,
                    batch_number=total_batches,
                    batch_size=batch_size,
                    total_records=total_records
                )
                
                # Stage 1: Save to IngestedData (staging)
                ingested_data_ids = self._save_to_staging(
                    raw_records=batch,
                    sync_id=sync_id,
                    connector_id=config.id,
                    customer_id=customer_id
                )
                records_loaded += len(ingested_data_ids)
                
                # Stage 2: Transform to domain model
                if transformer:
                    try:
                        transform_stats = transformer.transform_batch(
                            raw_records=batch,
                            customer_id=customer_id,
                            sync_id=sync_id,
                            ingested_data_ids=ingested_data_ids
                        )
                        
                        records_skipped += transform_stats.get("duplicates", 0)
                        records_failed += transform_stats.get("failed", 0)
                        
                        logger.info(
                            "batch_transformed",
                            sync_id=sync_id,
                            batch_number=total_batches,
                            transform_stats=transform_stats
                        )
                        
                    except Exception as e:
                        logger.error(
                            "batch_transform_failed",
                            sync_id=sync_id,
                            batch_number=total_batches,
                            error=str(e),
                            exc_info=True
                        )
                        records_failed += batch_size
                
                # Update sync run progress
                sync_run.records_extracted = total_records
                sync_run.records_loaded = records_loaded
                sync_run.records_skipped = records_skipped
                sync_run.records_failed = records_failed
                self.db.commit()
                
                # Log telemetry for progress
                self._log_telemetry(
                    sync_id=sync_id,
                    customer_id=customer_id,
                    event_type=ConnectorTelemetryEventType.SYNC_PROGRESS,
                    records_processed=batch_size,
                    current_stage="extracting",
                    user_message=f"Processing batch {total_batches}",
                    metadata={
                        "batch_number": total_batches,
                        "total_records": total_records
                    }
                )
            
            # Sync completed successfully
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            sync_run.status = SyncStatus.COMPLETED.value
            sync_run.completed_at = end_time
            sync_run.duration_seconds = int(duration)
            sync_run.records_extracted = total_records
            sync_run.records_loaded = records_loaded
            sync_run.records_skipped = records_skipped
            sync_run.records_failed = records_failed
            self.db.commit()
            
            # Log completion telemetry
            self._log_telemetry(
                sync_id=sync_id,
                customer_id=customer_id,
                event_type=ConnectorTelemetryEventType.SYNC_COMPLETED,
                records_processed=total_records,
                current_stage="completed",
                progress_percentage=100.0,
                user_message=f"Sync completed: {total_records} records processed",
                metadata={
                    "total_batches": total_batches,
                    "records_extracted": total_records,
                    "records_loaded": records_loaded,
                    "records_skipped": records_skipped,
                    "duration_seconds": duration
                }
            )
            
            # Update connector last_sync metadata
            config.last_sync_at = end_time
            config.last_sync_status = SyncStatus.COMPLETED.value
            config.last_sync_message = f"Successfully synced {total_records:,} records"
            self.db.commit()
            
            logger.info(
                "sync_completed",
                sync_id=sync_id,
                connector_id=connector_id,
                duration_seconds=duration,
                total_records=total_records,
                records_processed=records_loaded
            )
            
            return {
                "success": True,
                "sync_id": sync_id,
                "records_synced": total_records,
                "records_loaded": records_loaded,
                "records_failed": records_failed,
                "duration_seconds": duration,
                "batches_processed": total_batches
            }
            
        except Exception as e:
            # Sync failed
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            error_message = str(e)
            
            sync_run.status = SyncStatus.FAILED.value
            sync_run.completed_at = end_time
            sync_run.duration_seconds = int(duration)
            sync_run.error_message = error_message
            self.db.commit()
            
            # Log failure telemetry
            self._log_telemetry(
                sync_id=sync_id,
                customer_id=customer_id,
                event_type=ConnectorTelemetryEventType.SYNC_FAILED,
                current_stage="failed",
                user_message=f"Sync failed: {error_message}",
                metadata={
                    "records_extracted": sync_run.records_extracted,
                    "records_loaded": sync_run.records_loaded,
                    "records_skipped": sync_run.records_skipped,
                    "duration_seconds": duration,
                    "error": error_message
                }
            )
            
            # Update connector last_sync metadata
            config.last_sync_at = end_time
            config.last_sync_status = SyncStatus.FAILED.value
            config.last_sync_message = f"Sync failed: {error_message[:200]}"
            self.db.commit()
            
            logger.error(
                "sync_failed",
                sync_id=sync_id,
                connector_id=connector_id,
                error=error_message,
                duration_seconds=duration,
                exc_info=True
            )
            
            raise
    
    def _save_to_staging(
        self,
        raw_records: List[Dict[str, Any]],
        sync_id: str,
        connector_id: int,
        customer_id: str
    ) -> List[int]:
        """
        Save raw records to IngestedData staging table.
        
        Args:
            raw_records: List of raw JSON records
            sync_id: Sync ID (string UUID)
            connector_id: Connector configuration ID
            customer_id: Customer ID
            
        Returns:
            List of ingested_data.id values for the saved records
        """
        ingested_data_ids = []
        
        for record in raw_records:
            # Extract source record ID if available
            source_record_id = record.get("id") or record.get("_id") or None
            
            ingested_data = IngestedData(
                customer_id=customer_id,
                connector_id=connector_id,
                sync_id=sync_id,
                source_record_id=source_record_id,
                raw_data=record,
                status=IngestionStatus.PENDING.value
            )
            
            self.db.add(ingested_data)
            self.db.flush()  # Generate the ID
            ingested_data_ids.append(ingested_data.id)
        
        # Commit staging data
        try:
            self.db.commit()
        except IntegrityError as e:
            self.db.rollback()
            logger.error("staging_commit_failed", error=str(e))
            raise
        
        return ingested_data_ids

