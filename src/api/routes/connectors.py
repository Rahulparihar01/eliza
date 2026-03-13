"""
Connector API Routes

REST endpoints for managing data connectors, syncs, and telemetry.
Admin-only access for connector configuration.
"""
import json
from contextlib import nullcontext
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.database import get_db
from src.models.connector import (
    ConnectorConfiguration,
    ConnectorSyncRun,
    ConnectorTelemetry,
    PDLPerson
)
from src.api.schemas.connector_schemas import (
    ConnectorConfigCreate,
    ConnectorConfigUpdate,
    ConnectorConfigResponse,
    ConnectorConfigListResponse,
    TriggerSyncRequest,
    SyncRunResponse,
    SyncRunListResponse,
    TelemetryEventResponse,
    TelemetryListResponse,
    ConnectorTypeResponse,
    ConnectorTypeListResponse,
    ConnectorTypeInfo,
    AvailableConnectorTypesResponse,
    ValidateConfigRequest,
    ValidateConfigResponse,
    TestConnectionRequest,
    TestConnectionResponse,
    EstimateCostRequest,
    EstimateCostResponse,
    PDLPersonResponse,
    PDLPersonListResponse,
    ConnectorStatisticsResponse,
    PersonSearchRequest,
    PersonSearchResponse,
    PersonSearchResult,
    CareerTransitionRequest,
    SkillSearchRequest,
    CompanyNetworkRequest,
    AggregationsRequest,
    AggregationsResponse
)
from src.middleware.authorization import get_current_user, require_permission
from src.models.auth import User
from src.services.ingestion.connector_service import ConnectorService
from src.services.ingestion.connectors import (
    list_available_connectors,
    validate_connector_config,
    create_connector
)
from src.services.langfuse_service import get_langfuse_service
from src.utils.encryption import EncryptionError
from src.core.logging import get_logger, LogCategory, bind_context
from src.core.config import get_settings

logger = get_logger(__name__, LogCategory.API)
router = APIRouter(prefix="/api/connectors", tags=["connectors"])
settings = get_settings()


def _safe_trace_observation_update(observation: Any, **kwargs: Any) -> None:
    if observation is None:
        return
    try:
        observation.update(**kwargs)
    except Exception:
        pass


def _connector_trace_scope(
    *,
    name: str,
    input_data: Dict[str, Any],
    metadata: Dict[str, Any],
    user_id: int,
    session_id: str,
):
    langfuse_service = get_langfuse_service()
    if not langfuse_service.enabled:
        return nullcontext({"trace_id": None, "observation": None})
    if langfuse_service.current_trace_id:
        return langfuse_service.span_scope(
            name=name,
            input_data=input_data,
            metadata=metadata,
        )
    return langfuse_service.trace_scope(
        name=name,
        input_data=input_data,
        metadata=metadata,
        session_id=session_id,
        user_id=str(user_id),
    )


# -------------------------------------------------------------------------
# Connector Type Endpoints
# -------------------------------------------------------------------------

@router.get("/types", response_model=AvailableConnectorTypesResponse)
async def get_available_connector_types(
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Get all available connector types with their metadata.
    
    Returns complete enum values and connector information.
    Requires connections:read permission.
    """
    from src.api.schemas.connector_schemas import ConnectorTypeInfo, AvailableConnectorTypesResponse
    from src.models.connector import ConnectorType, SyncMode
    
    connector_types_info = [
        ConnectorTypeInfo(
            type=ConnectorType.PEOPLE_DATA_LABS,
            name="People Data Labs",
            description="Ingest person and company data directly from PDL API.",
            category="people_data",
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=True
        ),
        ConnectorTypeInfo(
            type=ConnectorType.FILESYSTEM,
            name="Local Filesystem",
            description="Read files from a local directory for testing and development.",
            category="hr_data",
            requires_credentials=False,
            supported_sync_modes=[SyncMode.FULL_REFRESH],
            available=True
        ),
        ConnectorTypeInfo(
            type=ConnectorType.GREENHOUSE,
            name="Greenhouse ATS",
            description="Sync job postings and applicant data from Greenhouse.",
            category="hr_data",
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=True  # ✅ Implemented
        ),
        ConnectorTypeInfo(
            type=ConnectorType.HUBSPOT,
            name="HubSpot CRM",
            description="Access HubSpot contacts, companies, and deals.",
            category="crm",
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=True
        ),
        ConnectorTypeInfo(
            type=ConnectorType.FATHOM,
            name="Fathom",
            description="Access meeting metadata, transcripts, and summaries from Fathom.",
            category="meeting_intelligence",
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=True
        ),
        ConnectorTypeInfo(
            type=ConnectorType.LEVER,
            name="Lever ATS",
            description="Sync job postings and applicant data from Lever.",
            category="hr_data",
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=False  # Coming soon
        ),
        ConnectorTypeInfo(
            type=ConnectorType.WORKDAY,
            name="Workday",
            description="Sync employee and organizational data from Workday.",
            category="hr_data",
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=False  # Coming soon
        ),
        ConnectorTypeInfo(
            type=ConnectorType.BAMBOOHR,
            name="BambooHR",
            description="Sync employee data from BambooHR.",
            category="hr_data",
            requires_credentials=True,
            supported_sync_modes=[SyncMode.FULL_REFRESH, SyncMode.INCREMENTAL],
            available=False  # Coming soon
        ),
    ]
    
    return AvailableConnectorTypesResponse(connector_types=connector_types_info)


# -------------------------------------------------------------------------
# Connector Configuration Endpoints
# -------------------------------------------------------------------------

@router.post("/configurations", response_model=ConnectorConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_connector_configuration(
    config_data: ConnectorConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:create"))
):
    """
    Create new connector configuration.
    
    Admin-only endpoint.
    
    Steps:
    1. Validate connector type and configuration
    2. Test connection with provided credentials
    3. Estimate record count and check cost threshold
    4. Encrypt credentials
    5. Save to database
    
    Returns:
        Created connector configuration
    """
    bind_context(
        operation="create_connector_config",
        user_id=current_user.user_id,
        connector_type=config_data.connector_type
    )

    trace_metadata = {
        "component": "connectors_api",
        "flow": "connector_lifecycle",
        "stage": "create_configuration",
        "customer_id": current_user.customer_id,
        "user_id": current_user.user_id,
        "connector_type": config_data.connector_type,
    }
    trace_input = {
        "connector_type": config_data.connector_type,
        "connector_name": config_data.connector_name,
        "use_shared_credentials": bool(config_data.use_shared_credentials),
        "has_credentials": bool(config_data.credentials),
        "sync_config_keys": sorted((config_data.sync_config or {}).keys())[:30],
    }

    with _connector_trace_scope(
        name="connectors.create_configuration",
        input_data=trace_input,
        metadata=trace_metadata,
        user_id=current_user.user_id,
        session_id=f"connectors:{current_user.customer_id}",
    ) as trace_info:
        observation = trace_info.get("observation")
        service = ConnectorService(db)

        try:
            config = service.create_configuration(
                customer_id=current_user.customer_id,
                connector_type=config_data.connector_type,
                connector_name=config_data.connector_name,
                credentials=config_data.credentials,
                sync_config=config_data.sync_config,
                description=config_data.description,
                tags=config_data.tags,
                created_by_user_id=current_user.user_id,
                use_shared_credentials=config_data.use_shared_credentials,
                sync_schedule=config_data.sync_schedule
            )

            logger.info(
                "connector_configuration_created",
                connector_id=config.connector_id,
                user_id=current_user.user_id
            )
            _safe_trace_observation_update(
                observation,
                output={
                    "status": "created",
                    "connector_id": config.connector_id,
                    "connector_type": config.connector_type,
                    "is_enabled": config.is_enabled,
                },
            )
            return config

        except ValueError as e:
            logger.warning(f"Invalid connector configuration: {e}")
            _safe_trace_observation_update(
                observation,
                output={"status": "validation_failed", "error": str(e)},
                level="ERROR",
                status_message="Connector configuration validation failed",
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        except EncryptionError as e:
            logger.error(f"Connector credential encryption misconfigured: {e}", exc_info=True)
            _safe_trace_observation_update(
                observation,
                output={"status": "encryption_failed", "error": str(e)},
                level="ERROR",
                status_message="Connector credential encryption is misconfigured",
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server encryption is not configured. Set ENCRYPTION_KEY and restart the API."
            )
        except Exception as e:
            logger.error(f"Failed to create connector configuration: {e}", exc_info=True)
            _safe_trace_observation_update(
                observation,
                output={"status": "failed", "error": str(e), "error_type": type(e).__name__},
                level="ERROR",
                status_message="Failed to create connector configuration",
            )
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create connector")


@router.get("/configurations", response_model=ConnectorConfigListResponse)
async def list_connector_configurations(
    connector_type: Optional[str] = Query(None, description="Filter by connector type"),
    is_enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    List all connector configurations for the customer.
    
    Admin-only endpoint.
    """
    service = ConnectorService(db)
    
    configs = service.list_configurations(
        customer_id=current_user.customer_id,
        connector_type=connector_type,
        is_enabled=is_enabled
    )
    
    return ConnectorConfigListResponse(
        total=len(configs),
        connectors=configs
    )


@router.get("/configurations/{connector_id}", response_model=ConnectorConfigResponse)
async def get_connector_configuration(
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Get single connector configuration by ID.
    
    Admin-only endpoint.
    """
    service = ConnectorService(db)
    
    config = service.get_configuration(connector_id, current_user.customer_id)
    
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    
    return config


@router.get("/configurations/{connector_id}/preview")
async def get_connector_preview(
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Get preview data for a connector.
    
    For filesystem connectors: Returns list of files in the directory
    For PDL/API connectors: Returns sample data from the query
    
    Admin-only endpoint.
    """
    service = ConnectorService(db)
    
    config = service.get_configuration(connector_id, current_user.customer_id)
    
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    
    try:
        # Decrypt credentials
        from src.utils.encryption import decrypt_value
        credentials = {}
        if config.credentials_encrypted:
            try:
                credentials = json.loads(decrypt_value(config.credentials_encrypted))
            except Exception as e:
                logger.warning(f"Failed to decrypt credentials: {e}")
        
        # Create connector instance
        from src.services.ingestion.connectors import create_connector
        connector = create_connector(
            connector_type=config.connector_type,
            credentials=credentials,
            config=config.sync_config,
            customer_id=current_user.customer_id
        )
        
        # Get preview based on connector type
        preview_data = {}
        
        if config.connector_type == "filesystem":
            # For filesystem: List files in directory
            from pathlib import Path
            directory_path = config.sync_config.get("directory_path")
            if directory_path:
                path = Path(directory_path)
                if path.exists() and path.is_dir():
                    file_extensions = config.sync_config.get("file_extensions", [".pdf", ".docx", ".txt"])
                    files = []
                    for ext in file_extensions:
                        files.extend(path.glob(f"*{ext}"))
                    
                    preview_data = {
                        "type": "filesystem",
                        "directory": str(directory_path),
                        "total_files": len(files),
                        "files": [
                            {
                                "name": f.name,
                                "size": f.stat().st_size,
                                "modified": f.stat().st_mtime
                            }
                            for f in sorted(files)[:50]  # Limit to 50 files
                        ]
                    }
        
        elif config.connector_type == "people_data_labs":
            # For PDL: Get sample data from the query
            # Run a limited query to get sample results
            try:
                sample_records = []
                for batch in connector.read_stream("full", {"max_records": 5}):
                    sample_records.extend(batch[:5])
                    if len(sample_records) >= 5:
                        break
                
                preview_data = {
                    "type": "people_data_labs",
                    "query": config.sync_config.get("search_query", {}),
                    "sample_count": len(sample_records),
                    "sample_data": sample_records[:5]
                }
            except Exception as e:
                logger.warning(f"Failed to fetch PDL sample data: {e}")
                preview_data = {
                    "type": "people_data_labs",
                    "query": config.sync_config.get("search_query", {}),
                    "error": f"Unable to fetch sample data: {str(e)}"
                }
        
        else:
            # Generic preview for other connector types
            preview_data = {
                "type": config.connector_type,
                "config": config.sync_config
            }
        
        return preview_data
        
    except Exception as e:
        logger.error(f"Failed to get connector preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connector preview: {str(e)}"
        )


@router.put("/configurations/{connector_id}", response_model=ConnectorConfigResponse)
async def update_connector_configuration(
    connector_id: str,
    updates: ConnectorConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:update"))
):
    """
    Update connector configuration.
    
    Admin-only endpoint.
    
    If sync_config is updated:
    - Configuration is versioned
    - Old config saved to history
    - Connection tested with new config
    """
    service = ConnectorService(db)
    
    try:
        config = service.update_configuration(
            connector_id=connector_id,
            customer_id=current_user.customer_id,
            updates=updates.model_dump(exclude_unset=True)
        )
        
        logger.info(
            "connector_configuration_updated",
            connector_id=connector_id,
            user_id=current_user.user_id
        )
        
        return config
        
    except ValueError as e:
        logger.warning(f"Invalid update: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except EncryptionError as e:
        logger.error(f"Connector credential encryption misconfigured during update: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server encryption is not configured. Set ENCRYPTION_KEY and restart the API."
        )
    except Exception as e:
        logger.error(f"Failed to update connector: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update connector")


@router.delete("/configurations/{connector_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connector_configuration(
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:delete"))
):
    """
    Delete (disable) connector configuration.
    
    Admin-only endpoint.
    
    Soft delete: marks as disabled, preserves sync history.
    """
    service = ConnectorService(db)
    
    success = service.delete_configuration(connector_id, current_user.customer_id)
    
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    
    logger.info(
        "connector_configuration_deleted",
        connector_id=connector_id,
        user_id=current_user.user_id
    )


# -------------------------------------------------------------------------
# Sync Management Endpoints
# -------------------------------------------------------------------------

@router.post("/configurations/{connector_id}/trigger-sync", response_model=SyncRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_connector_sync(
    connector_id: str,
    request: TriggerSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:sync"))
):
    """
    Trigger a manual connector sync.
    
    Admin-only endpoint.
    
    Returns immediately with sync run record.
    Sync executes asynchronously via Celery task.
    
    Check sync status via GET /sync-runs/{sync_id}
    """
    bind_context(
        operation="trigger_sync",
        connector_id=connector_id,
        user_id=current_user.user_id
    )
    
    service = ConnectorService(db)
    
    try:
        sync_run = service.trigger_sync(
            connector_id=connector_id,
            customer_id=current_user.customer_id,
            manual_trigger=request.manual_trigger
        )
        
        logger.info(
            "sync_triggered",
            connector_id=connector_id,
            sync_id=sync_run.sync_id,
            user_id=current_user.user_id
        )
        
        return sync_run
        
    except ValueError as e:
        logger.warning(f"Cannot trigger sync: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to trigger sync: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to trigger sync")


@router.get("/sync-runs", response_model=SyncRunListResponse)
async def list_sync_runs(
    connector_id: Optional[str] = Query(None, description="Filter by connector ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    List sync runs for the customer.
    
    Admin-only endpoint.
    
    Supports filtering and pagination.
    """
    query = db.query(ConnectorSyncRun).filter(
        ConnectorSyncRun.customer_id == current_user.customer_id
    )
    
    if connector_id:
        # Join with ConnectorConfiguration to filter by connector_id
        query = query.join(ConnectorConfiguration).filter(
            ConnectorConfiguration.connector_id == connector_id
        )
    
    if status:
        query = query.filter(ConnectorSyncRun.status == status)
    
    total = query.count()
    sync_runs = query.order_by(ConnectorSyncRun.started_at.desc()).offset(offset).limit(limit).all()
    
    return SyncRunListResponse(
        total=total,
        sync_runs=sync_runs
    )


@router.get("/sync-runs/{sync_id}", response_model=SyncRunResponse)
async def get_sync_run(
    sync_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Get sync run details by ID.
    
    Admin-only endpoint.
    """
    sync_run = db.query(ConnectorSyncRun).filter(
        ConnectorSyncRun.sync_id == sync_id,
        ConnectorSyncRun.customer_id == current_user.customer_id
    ).first()
    
    if not sync_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found")
    
    return sync_run


# -------------------------------------------------------------------------
# Telemetry Endpoints
# -------------------------------------------------------------------------

@router.get("/sync-runs/{sync_id}/telemetry", response_model=TelemetryListResponse)
async def get_sync_telemetry(
    sync_id: str,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Get telemetry events for a sync run.
    
    Admin-only endpoint.
    
    Used for real-time progress monitoring.
    """
    # Fetch sync run to verify access
    sync_run = db.query(ConnectorSyncRun).filter(
        ConnectorSyncRun.sync_id == sync_id,
        ConnectorSyncRun.customer_id == current_user.customer_id
    ).first()
    
    if not sync_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found")
    
    query = db.query(ConnectorTelemetry).filter(
        ConnectorTelemetry.sync_run_id == sync_run.id
    )
    
    if event_type:
        query = query.filter(ConnectorTelemetry.event_type == event_type)
    
    total = query.count()
    events = query.order_by(ConnectorTelemetry.event_timestamp.asc()).limit(limit).all()
    
    return TelemetryListResponse(
        total=total,
        events=events
    )


# -------------------------------------------------------------------------
# Validation & Testing Endpoints
# -------------------------------------------------------------------------

@router.post("/validate-config", response_model=ValidateConfigResponse)
async def validate_configuration(
    request: ValidateConfigRequest,
    current_user: User = Depends(require_permission("connections:test"))
):
    """
    Validate connector configuration without saving.
    
    Admin-only endpoint.
    
    Used by frontend to validate before submission.
    """
    is_valid, error_message = validate_connector_config(
        connector_type=request.connector_type,
        config=request.sync_config
    )
    
    return ValidateConfigResponse(
        is_valid=is_valid,
        error_message=error_message if not is_valid else None
    )


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    request: TestConnectionRequest,
    current_user: User = Depends(require_permission("connections:test"))
):
    """
    Test connector connection with provided credentials.
    
    Admin-only endpoint.
    
    Does NOT save configuration - only tests connectivity.
    """
    trace_metadata = {
        "component": "connectors_api",
        "flow": "connector_lifecycle",
        "stage": "test_connection",
        "customer_id": current_user.customer_id,
        "user_id": current_user.user_id,
        "connector_type": request.connector_type,
    }
    trace_input = {
        "connector_type": request.connector_type,
        "has_credentials": bool(request.credentials),
        "sync_config_keys": sorted((request.sync_config or {}).keys())[:30],
    }

    with _connector_trace_scope(
        name="connectors.test_connection",
        input_data=trace_input,
        metadata=trace_metadata,
        user_id=current_user.user_id,
        session_id=f"connectors:{current_user.customer_id}",
    ) as trace_info:
        observation = trace_info.get("observation")
        try:
            connector = create_connector(
                connector_type=request.connector_type,
                credentials=request.credentials,
                config=request.sync_config,
                customer_id=current_user.customer_id
            )

            result = connector.check()
            success = result["status"] == "healthy"
            update_payload = {
                "output": {
                    "success": success,
                    "status": result.get("status"),
                    "message": result.get("message"),
                },
            }
            if not success:
                update_payload["level"] = "ERROR"
                update_payload["status_message"] = "Connection test returned unhealthy status"
            _safe_trace_observation_update(observation, **update_payload)

            return TestConnectionResponse(
                success=success,
                status=result["status"],
                message=result["message"],
                metadata=result.get("metadata")
            )

        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            _safe_trace_observation_update(
                observation,
                output={"success": False, "error": str(e), "error_type": type(e).__name__},
                level="ERROR",
                status_message="Connection test raised an exception",
            )
            return TestConnectionResponse(
                success=False,
                status="unhealthy",
                message=f"Connection test failed: {str(e)}"
            )


@router.post("/estimate-cost", response_model=EstimateCostResponse)
async def estimate_sync_cost(
    request: EstimateCostRequest,
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Estimate cost for a connector sync.
    
    Admin-only endpoint.
    
    Returns:
    - Estimated record count (via connector's estimate method)
    - Estimated cost based on settings.connector_cost_per_record
    - Whether cost acknowledgment is required
    """
    try:
        connector = create_connector(
            connector_type=request.connector_type,
            credentials=request.credentials,
            config=request.sync_config,
            customer_id=current_user.customer_id
        )
        
        # Check if connector supports estimation
        if not hasattr(connector, 'estimate_record_count'):
            return EstimateCostResponse(
                estimated_record_count=None,
                estimated_cost=None,
                cost_per_record=settings.connector_cost_per_record,
                requires_acknowledgment=False,
                warning_message="This connector does not support cost estimation"
            )
        
        estimated_count = connector.estimate_record_count()
        
        if estimated_count is None:
            return EstimateCostResponse(
                estimated_record_count=None,
                estimated_cost=None,
                cost_per_record=settings.connector_cost_per_record,
                requires_acknowledgment=False,
                warning_message="Unable to estimate record count for this query"
            )
        
        estimated_cost = estimated_count * settings.connector_cost_per_record
        requires_acknowledgment = estimated_cost > settings.connector_cost_warning_threshold
        
        warning_message = None
        if requires_acknowledgment:
            warning_message = (
                f"This sync will fetch approximately {estimated_count:,} records "
                f"(estimated cost: ${estimated_cost:.2f}). "
                f"Please acknowledge by setting 'estimated_cost_acknowledged': true in config."
            )
        
        return EstimateCostResponse(
            estimated_record_count=estimated_count,
            estimated_cost=estimated_cost,
            cost_per_record=settings.connector_cost_per_record,
            requires_acknowledgment=requires_acknowledgment,
            warning_message=warning_message
        )
        
    except Exception as e:
        logger.error(f"Cost estimation failed: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Cost estimation failed: {str(e)}")


# -------------------------------------------------------------------------
# Data Access Endpoints (PDL Persons)
# -------------------------------------------------------------------------

@router.get("/pdl-persons", response_model=PDLPersonListResponse)
async def list_pdl_persons(
    search: Optional[str] = Query(None, description="Search by name, email, company"),
    job_title_role: Optional[str] = Query(None, description="Filter by job title role"),
    job_company_name: Optional[str] = Query(None, description="Filter by company name"),
    location_country: Optional[str] = Query(None, description="Filter by country"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Results per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    List PDL person records for the customer.
    
    Accessible to users with connections:read permission.
    
    Supports search and filtering.
    """
    query = db.query(PDLPerson).filter(
        PDLPerson.customer_id == current_user.customer_id
    )
    
    # Search
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (PDLPerson.full_name.ilike(search_filter)) |
            (PDLPerson.primary_email.ilike(search_filter)) |
            (PDLPerson.job_company_name.ilike(search_filter))
        )
    
    # Filters
    if job_title_role:
        query = query.filter(PDLPerson.job_title_role == job_title_role)
    
    if job_company_name:
        query = query.filter(PDLPerson.job_company_name == job_company_name)
    
    if location_country:
        query = query.filter(PDLPerson.location_country == location_country)
    
    total = query.count()
    offset = (page - 1) * page_size
    persons = query.order_by(PDLPerson.created_at.desc()).offset(offset).limit(page_size).all()
    
    return PDLPersonListResponse(
        total=total,
        persons=persons,
        page=page,
        page_size=page_size
    )


@router.get("/pdl-persons/{person_id}", response_model=PDLPersonResponse)
async def get_pdl_person(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Get single PDL person record by ID.
    
    Admin-only endpoint.
    """
    person = db.query(PDLPerson).filter(
        PDLPerson.id == person_id,
        PDLPerson.customer_id == current_user.customer_id
    ).first()
    
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    
    return person


# -------------------------------------------------------------------------
# Statistics Endpoints
# -------------------------------------------------------------------------

@router.get("/configurations/{connector_id}/statistics", response_model=ConnectorStatisticsResponse)
async def get_connector_statistics(
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("connections:read"))
):
    """
    Get statistics for a connector.
    
    Admin-only endpoint.
    
    Returns aggregate metrics across all syncs.
    """
    service = ConnectorService(db)
    
    config = service.get_configuration(connector_id, current_user.customer_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found")
    
    # Aggregate statistics
    sync_stats = db.query(
        func.count(ConnectorSyncRun.id).label("total_syncs"),
        func.count(func.nullif(ConnectorSyncRun.status == "completed", False)).label("successful_syncs"),
        func.count(func.nullif(ConnectorSyncRun.status == "failed", False)).label("failed_syncs"),
        func.sum(ConnectorSyncRun.records_extracted).label("total_records"),
        func.sum(ConnectorSyncRun.records_loaded).label("total_transformed"),
        func.sum(ConnectorSyncRun.records_failed).label("total_failed"),
        func.avg(
            func.extract('epoch', ConnectorSyncRun.completed_at - ConnectorSyncRun.started_at)
        ).label("avg_duration")
    ).filter(
        ConnectorSyncRun.connector_id == config.id
    ).first()
    
    return ConnectorStatisticsResponse(
        connector_id=config.connector_id,
        connector_name=config.connector_name,
        connector_type=config.connector_type,
        total_syncs=sync_stats.total_syncs or 0,
        successful_syncs=sync_stats.successful_syncs or 0,
        failed_syncs=sync_stats.failed_syncs or 0,
        total_records_synced=sync_stats.total_records or 0,
        total_records_transformed=sync_stats.total_transformed or 0,
        total_records_failed=sync_stats.total_failed or 0,
        last_sync_at=config.last_sync_at,
        last_sync_status=config.last_sync_status,
        average_sync_duration_seconds=sync_stats.avg_duration,
        average_records_per_sync=(sync_stats.total_records / sync_stats.total_syncs) if sync_stats.total_syncs > 0 else None
    )


# ============================================================================
# Person Search Endpoints
# ============================================================================

@router.post(
    "/persons/search",
    response_model=PersonSearchResponse,
    summary="Search for persons",
    description="Search persons with text query and filters. Uses Elasticsearch if available, falls back to PostgreSQL."
)
async def search_persons(
    request: PersonSearchRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search for persons across all data stores.
    
    - Full-text search with Elasticsearch
    - Faceted filtering (company, location, skills)
    - Pagination support
    - Falls back to PostgreSQL if ES unavailable
    """
    from src.services.ingestion.person_search_service import PersonSearchService
    
    # Create search service
    search_service = PersonSearchService(db)
    
    try:
        # Execute search
        results = search_service.search_persons(
            customer_id=current_user.customer_id,
            query=request.query,
            filters=request.filters,
            page=request.page,
            page_size=request.page_size,
            use_elasticsearch=request.use_elasticsearch
        )
        
        # Convert results to response schema
        return PersonSearchResponse(**results)
        
    finally:
        search_service.close()


@router.get(
    "/persons/{pdl_id}",
    response_model=PersonSearchResult,
    summary="Get person by ID",
    description="Retrieve a single person by their PDL ID."
)
async def get_person_by_id(
    pdl_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a single person by PDL ID.
    
    Direct lookup from PostgreSQL.
    """
    from src.services.ingestion.person_search_service import PersonSearchService
    
    search_service = PersonSearchService(db)
    
    try:
        person = search_service.get_person_by_id(
            pdl_id=pdl_id,
            customer_id=current_user.customer_id
        )
        
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Person with PDL ID {pdl_id} not found"
            )
        
        return PersonSearchResult(**person)
        
    finally:
        search_service.close()


@router.post(
    "/persons/career-transitions",
    response_model=List[PersonSearchResult],
    summary="Find career transitions",
    description="Find people who moved from one company to another. Uses Neo4j for relationship queries."
)
async def find_career_transitions(
    request: CareerTransitionRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Find people who transitioned from one company to another.
    
    Uses Neo4j graph traversal for relationship analysis.
    Returns empty list if Neo4j is not available.
    """
    from src.services.ingestion.person_search_service import PersonSearchService
    
    search_service = PersonSearchService(db)
    
    try:
        results = search_service.find_career_transitions(
            customer_id=current_user.customer_id,
            from_company=request.from_company,
            to_company=request.to_company,
            limit=request.limit
        )
        
        return [PersonSearchResult(**r) for r in results]
        
    finally:
        search_service.close()


@router.post(
    "/persons/by-skills",
    response_model=List[PersonSearchResult],
    summary="Search by skills",
    description="Find people with specific skill combinations. Uses Neo4j for skill relationship queries."
)
async def search_by_skills(
    request: SkillSearchRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Find people with specific skill combinations.
    
    Uses Neo4j for skill relationship queries.
    Falls back to Elasticsearch if Neo4j unavailable.
    """
    from src.services.ingestion.person_search_service import PersonSearchService
    
    search_service = PersonSearchService(db)
    
    try:
        results = search_service.find_people_with_skills(
            customer_id=current_user.customer_id,
            skills=request.skills,
            require_all=request.require_all,
            limit=request.limit
        )
        
        return [PersonSearchResult(**r) for r in results]
        
    finally:
        search_service.close()


@router.post(
    "/persons/company-network",
    response_model=Dict,
    summary="Get company network",
    description="Get network of companies connected through people. Uses Neo4j for graph analysis."
)
async def get_company_network(
    request: CompanyNetworkRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get network of companies connected through people.
    
    Uses Neo4j graph traversal to find company-to-company relationships.
    Returns empty network if Neo4j is not available.
    """
    from src.services.ingestion.person_search_service import PersonSearchService
    
    search_service = PersonSearchService(db)
    
    try:
        network = search_service.get_company_network(
            customer_id=current_user.customer_id,
            company_name=request.company_name,
            depth=request.depth
        )
        
        return network
        
    finally:
        search_service.close()


@router.post(
    "/persons/aggregations",
    response_model=AggregationsResponse,
    summary="Get analytics aggregations",
    description="Get aggregations for analytics dashboards. Uses Elasticsearch for fast aggregations."
)
async def get_aggregations(
    request: AggregationsRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregations for analytics.
    
    Uses Elasticsearch for fast aggregations on large datasets.
    Returns empty aggregations if Elasticsearch is not available.
    """
    from src.services.ingestion.person_search_service import PersonSearchService
    
    search_service = PersonSearchService(db)
    
    try:
        aggregations = search_service.get_aggregations(
            customer_id=current_user.customer_id,
            agg_fields=request.agg_fields
        )
        
        return AggregationsResponse(aggregations=aggregations)
        
    finally:
        search_service.close()


# ============================================================================
# Greenhouse-specific endpoints
# ============================================================================

@router.get(
    "/greenhouse/jobs",
    response_model=List[Dict],
    dependencies=[Depends(require_permission("connections:read"))]
)
async def list_greenhouse_jobs(
    connector_id: str = Query(..., description="Greenhouse connector ID"),
    department_id: Optional[int] = Query(None, description="Filter by department ID (includes subordinates)"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List available jobs from Greenhouse.
    
    Used by UI to populate job selection dropdown when configuring connector.
    Fetches API key from stored connector configuration.
    
    Args:
        connector_id: The Greenhouse connector ID
        department_id: Optional department ID to filter jobs by (includes subordinate departments)
    """
    from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
    from src.services.ingestion.connector_service import ConnectorService
    
    try:
        # Get connector configuration from database
        connector_service = ConnectorService(db)
        config = connector_service.get_configuration(connector_id, current_user.customer_id)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found"
            )
        
        if config.connector_type != "greenhouse":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only works with Greenhouse connectors"
            )
        
        # Get decrypted credentials
        credentials = connector_service.get_credentials(config)
        
        # Create connector instance
        connector = GreenhouseConnector(
            credentials=credentials,
            config={},
            customer_id=current_user.customer_id
        )
        
        # If department_id provided, get all subordinate departments
        department_ids = None
        if department_id:
            departments = await connector.get_departments()
            department_ids = connector.get_subordinate_department_ids(departments, department_id)
        
        jobs = await connector.get_jobs(department_ids=department_ids)
        
        return jobs
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch Greenhouse jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Greenhouse jobs: {str(e)}"
        )


@router.get(
    "/greenhouse/departments",
    response_model=List[Dict],
    dependencies=[Depends(require_permission("connections:read"))]
)
async def list_greenhouse_departments(
    connector_id: str = Query(..., description="Greenhouse connector ID"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List departments from Greenhouse with hierarchy information.
    
    Returns departments with parent_id and child_ids for building a hierarchy tree.
    Used by UI to populate department selection dropdown when configuring connector.
    """
    from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
    from src.services.ingestion.connector_service import ConnectorService
    
    try:
        # Get connector configuration from database
        connector_service = ConnectorService(db)
        config = connector_service.get_configuration(connector_id, current_user.customer_id)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found"
            )
        
        if config.connector_type != "greenhouse":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only works with Greenhouse connectors"
            )
        
        # Get decrypted credentials
        credentials = connector_service.get_credentials(config)
        
        # Create connector instance
        connector = GreenhouseConnector(
            credentials=credentials,
            config={},
            customer_id=current_user.customer_id
        )
        
        departments = await connector.get_departments()
        
        return departments
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch Greenhouse departments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Greenhouse departments: {str(e)}"
        )


@router.get(
    "/greenhouse/departments-with-counts",
    response_model=List[Dict],
    dependencies=[Depends(require_permission("connections:read"))]
)
async def list_greenhouse_departments_with_candidate_counts(
    connector_id: str = Query(..., description="Greenhouse connector ID"),
    closed_job_lookback_days: int = Query(
        365,
        ge=30,
        le=1825,
        description="Max age in days for closed jobs to include. Open jobs are always included. Default: 365 (1 year)"
    ),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List departments from Greenhouse with candidate counts.
    
    Returns departments with the number of candidates who have applied to jobs
    in each department. Includes:
    - All candidates from currently OPEN jobs
    - Candidates from CLOSED jobs that were closed within the lookback period
    
    This helps users select departments with relevant, recent applicants while
    excluding very old historical candidates (e.g., from jobs closed 3+ years ago).
    """
    from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
    from src.services.ingestion.connector_service import ConnectorService
    from collections import defaultdict
    from datetime import datetime, timezone, timedelta
    
    try:
        # Get connector configuration from database
        connector_service = ConnectorService(db)
        config = connector_service.get_configuration(connector_id, current_user.customer_id)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found"
            )
        
        if config.connector_type != "greenhouse":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only works with Greenhouse connectors"
            )
        
        # Get decrypted credentials
        credentials = connector_service.get_credentials(config)
        
        # Create connector instance
        connector = GreenhouseConnector(
            credentials=credentials,
            config={},
            customer_id=current_user.customer_id
        )
        
        # Fetch departments
        departments = await connector.get_departments()
        
        # Calculate cutoff date for closed jobs
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=closed_job_lookback_days)
        
        # Fetch OPEN jobs (always included - these are active positions)
        open_jobs = await connector.get_jobs(status_filter="open")
        
        # Fetch CLOSED jobs that were closed after the cutoff date
        # This uses the existing get_historical_jobs method which filters by closed_at
        closed_jobs = await connector.get_historical_jobs(closed_after=cutoff_date)
        
        # Combine open + recent closed jobs
        all_relevant_jobs = open_jobs + closed_jobs
        
        logger.info(
            f"Department count: Found {len(open_jobs)} open jobs, "
            f"{len(closed_jobs)} closed jobs (within {closed_job_lookback_days} days), "
            f"total {len(all_relevant_jobs)} jobs to count candidates from"
        )
        
        # Build job_id -> department_ids mapping
        job_to_depts: Dict[int, List[int]] = {}
        for job in all_relevant_jobs:
            job_id = job.get("id")
            dept_ids = job.get("department_ids", [])
            if job_id:
                job_to_depts[job_id] = dept_ids
        
        # Count candidates per department by fetching candidates
        dept_candidate_count: Dict[int, int] = defaultdict(int)
        candidate_ids_seen: Dict[int, set] = defaultdict(set)  # Avoid double-counting
        
        # Fetch candidates (paginated)
        # Using higher page limit to capture more candidates for accurate counts
        page = 1
        max_pages = 50  # Up to 5000 candidates (50 pages * 100 per page)
        
        while page <= max_pages:
            response = await connector.fetch_candidates(page=page, per_page=100)
            candidates = response.get("candidates", [])
            
            if not candidates:
                break
            
            for candidate in candidates:
                candidate_id = candidate.get("id")
                applications = candidate.get("applications", [])
                
                for app in applications:
                    # Skip prospects (not actual applicants)
                    if app.get("prospect", False):
                        continue
                    
                    job_id = None
                    # Get job_id from the application's jobs array
                    app_jobs = app.get("jobs", [])
                    if app_jobs:
                        job_id = app_jobs[0].get("id")
                    
                    # Only count if job is in our relevant jobs list (open or recent closed)
                    if job_id and job_id in job_to_depts:
                        for dept_id in job_to_depts[job_id]:
                            # Only count each candidate once per department
                            if candidate_id not in candidate_ids_seen[dept_id]:
                                candidate_ids_seen[dept_id].add(candidate_id)
                                dept_candidate_count[dept_id] += 1
            
            if not response.get("has_next"):
                break
            page += 1
        
        # Add candidate counts to departments
        for dept in departments:
            dept["candidate_count"] = dept_candidate_count.get(dept["id"], 0)
        
        # Sort by candidate count (descending), then by name
        departments.sort(key=lambda d: (-d.get("candidate_count", 0), d.get("name", "")))
        
        return departments
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch Greenhouse departments with counts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Greenhouse departments with counts: {str(e)}"
        )


@router.post(
    "/greenhouse/test-connection",
    response_model=TestConnectionResponse,
    dependencies=[Depends(require_permission("connections:test"))]
)
async def test_greenhouse_connection(
    request: TestConnectionRequest,
    current_user = Depends(get_current_user)
):
    """
    Test Greenhouse API connection before saving configuration.
    
    Validates the API key by making a test API call.
    Expects:
    {
        "connector_type": "greenhouse",
        "credentials": {"api_key": "your_gh_api_key"},
        "sync_config": {}
    }
    """
    from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
    
    try:
        # Create connector with proper parameters
        connector = GreenhouseConnector(
            credentials=request.credentials,
            config=request.sync_config or {},
            customer_id=current_user.customer_id
        )
        
        # Use async check for async endpoint
        check_result = await connector.check_async()
        is_healthy = check_result.get("status") == "healthy"
        
        return TestConnectionResponse(
            success=is_healthy,
            status="connected" if is_healthy else "failed",
            message=check_result.get("message", "Connection test completed")
        )
        
    except Exception as e:
        logger.error(f"Greenhouse connection test failed: {e}", exc_info=True)
        return TestConnectionResponse(
            success=False,
            status="error",
            message=f"Connection test failed: {str(e)}"
        )


@router.post(
    "/greenhouse/test-query",
    response_model=Dict,
    dependencies=[Depends(require_permission("connections:read"))]
)
async def test_greenhouse_query(
    request: Dict,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test a Greenhouse query configuration to see how many candidates match.
    
    This allows users to preview their query results before running a full analysis.
    
    Request body:
    {
        "connector_id": "greenhouse_eliza_abc123",
        "query_params": {
            "job_ids": "123,456",  # Optional
            "application_status": "active",  # Optional: active, rejected, hired
            "created_after": "2024-01-01",  # Optional: ISO date
            "max_candidates": 50  # Optional: 1-1000
        }
    }
    
    Response:
    {
        "success": true,
        "job_count": 5,
        "candidate_count": 127,
        "message": "Found 127 candidates across 5 jobs"
    }
    """
    from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
    from src.services.ingestion.connector_service import ConnectorService
    
    try:
        connector_id = request.get("connector_id")
        query_params = request.get("query_params", {})
        
        if not connector_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="connector_id is required"
            )
        
        # Get connector configuration from database
        connector_service = ConnectorService(db)
        config = connector_service.get_configuration(connector_id, current_user.customer_id)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found"
            )
        
        if config.connector_type != "greenhouse":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This endpoint only works with Greenhouse connectors"
            )
        
        # Get decrypted credentials
        credentials = connector_service.get_credentials(config)
        
        # Create connector instance with query params
        connector = GreenhouseConnector(
            credentials=credentials,
            config=query_params,  # Use query params as config
            customer_id=current_user.customer_id
        )
        
        # Test the query by actually fetching candidates
        try:
            # Fetch actual candidate count using the connector's fetch_candidates method
            # This gives us the REAL count based on the filters
            max_candidates = query_params.get("max_candidates", 50)
            
            # Fetch first page to get actual count
            response = await connector.fetch_candidates(page=1, per_page=min(100, max_candidates))
            candidates = response.get("candidates", [])
            
            # Count candidates that pass filters
            candidate_count = 0
            for candidate in candidates:
                if connector._should_include_candidate(candidate):
                    candidate_count += 1
                    if candidate_count >= max_candidates:
                        break
            
            # Get job info for display
            try:
                jobs = await connector.get_jobs()
                job_count = len(jobs)
                
                # If job_ids filter is specified, only count those jobs
                if query_params.get("job_ids"):
                    requested_job_ids = [int(id.strip()) for id in query_params["job_ids"].split(",") if id.strip()]
                    filtered_jobs = [j for j in jobs if j.get("id") in requested_job_ids]
                    job_count = len(filtered_jobs)
            except:
                job_count = 0  # Job fetching is optional, candidate count is what matters
            
            return {
                "success": True,
                "job_count": job_count,
                "candidate_count": candidate_count,
                "message": f"Found {candidate_count} candidates matching your criteria" + (f" across {job_count} jobs" if job_count > 0 else "")
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for authentication errors
            if "401" in error_msg or "Unauthorized" in error_msg or "Invalid Basic Auth" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid Greenhouse API key. Please verify your API key in Configure → Dev Center → API Credential Management"
                )
            
            # Check for other common errors
            if "403" in error_msg or "Forbidden" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Greenhouse API key does not have required permissions. Please ensure it has read access to Jobs and Candidates."
                )
            
            if "404" in error_msg or "Not Found" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Greenhouse API endpoint not found. Please check your Greenhouse configuration."
                )
            
            # Generic error
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to Greenhouse API: {error_msg}"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test Greenhouse query: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error testing query: {str(e)}"
        )


# -------------------------------------------------------------------------
# Greenhouse Job Board API Endpoints (Applicant Submission)
# -------------------------------------------------------------------------

@router.post(
    "/greenhouse/submit-candidate",
    response_model=Dict,
    dependencies=[Depends(require_permission("connections:sync"))]
)
async def submit_candidate_to_greenhouse(
    request: Dict,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a market candidate to a Greenhouse job posting.
    
    This uses the Job Board API (not Harvest API) to submit external candidates
    as applicants to specific job postings.
    
    Request body:
    {
        "connector_id": "greenhouse_job_board_abc123",
        "job_id": 123456,
        "candidate": {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "+1-555-0100",
            "location": "San Francisco, CA",
            "linkedin_url": "https://linkedin.com/in/johndoe",
            "resume_url": "https://...",  # Optional: URL to fetch resume
            "resume_bytes": "base64...",   # Optional: Base64 encoded resume
            "resume_filename": "john_doe_resume.pdf",
            "cover_letter": "I am excited to apply..."
        }
    }
    
    Response:
    {
        "success": true,
        "application_id": "app_abc123",
        "message": "Candidate submitted successfully",
        "job_title": "Senior Software Engineer"
    }
    """
    from src.services.ingestion.connectors.greenhouse_job_board import GreenhouseJobBoardConnector
    from src.services.ingestion.connector_service import ConnectorService
    import base64
    
    try:
        connector_id = request.get("connector_id")
        job_id = request.get("job_id")
        candidate_data = request.get("candidate", {})
        
        if not connector_id or not job_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="connector_id and job_id are required"
            )
        
        if not candidate_data.get("first_name") or not candidate_data.get("last_name") or not candidate_data.get("email"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="first_name, last_name, and email are required"
            )
        
        # Get connector configuration from database
        connector_service = ConnectorService(db)
        config = connector_service.get_configuration(connector_id, current_user.customer_id)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found"
            )
        
        # Get decrypted credentials
        credentials = connector_service.get_credentials(config)
        api_key = credentials.get("api_key")
        board_token = credentials.get("board_token") or config.sync_config.get("board_token")
        
        if not api_key or not board_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector missing API key or board token"
            )
        
        # Create Job Board connector
        job_board = GreenhouseJobBoardConnector(
            api_key=api_key,
            board_token=board_token,
            customer_id=current_user.customer_id
        )
        
        # Process resume if provided
        resume_content = None
        resume_filename = candidate_data.get("resume_filename", "resume.pdf")
        
        if candidate_data.get("resume_bytes"):
            # Decode base64 resume
            try:
                resume_content = base64.b64decode(candidate_data["resume_bytes"])
            except Exception as e:
                logger.warning(f"Failed to decode resume: {e}")
        
        # Submit candidate
        result = await job_board.submit_candidate(
            job_id=job_id,
            first_name=candidate_data["first_name"],
            last_name=candidate_data["last_name"],
            email=candidate_data["email"],
            resume_content=resume_content,
            resume_filename=resume_filename,
            phone=candidate_data.get("phone"),
            location=candidate_data.get("location"),
            linkedin_url=candidate_data.get("linkedin_url"),
            website=candidate_data.get("website"),
            cover_letter=candidate_data.get("cover_letter")
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to submit candidate")
            )
        
        return {
            "success": True,
            "application_id": result.get("application_id"),
            "message": f"Successfully submitted {candidate_data['first_name']} {candidate_data['last_name']} to job {job_id}",
            "greenhouse_response": result.get("greenhouse_response")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit candidate to Greenhouse: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get(
    "/greenhouse/job-board/jobs",
    response_model=List[Dict],
    dependencies=[Depends(require_permission("connections:read"))]
)
async def list_greenhouse_job_board_jobs(
    connector_id: str = Query(..., description="Job Board connector ID"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all active job postings from Greenhouse Job Board.
    
    This endpoint is used to populate the job dropdown when submitting candidates.
    Returns jobs with searchable titles and IDs.
    """
    from src.services.ingestion.connectors.greenhouse_job_board import GreenhouseJobBoardConnector
    from src.services.ingestion.connector_service import ConnectorService
    
    try:
        # Get connector configuration
        connector_service = ConnectorService(db)
        config = connector_service.get_configuration(connector_id, current_user.customer_id)
        
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connector {connector_id} not found"
            )
        
        # Get credentials
        credentials = connector_service.get_credentials(config)
        api_key = credentials.get("api_key")
        board_token = credentials.get("board_token") or config.sync_config.get("board_token")
        
        if not board_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Connector missing board token"
            )
        
        # Create connector and list jobs
        job_board = GreenhouseJobBoardConnector(
            api_key=api_key,
            board_token=board_token,
            customer_id=current_user.customer_id
        )
        
        jobs = await job_board.list_jobs()
        
        # Format for frontend dropdown
        formatted_jobs = [
            {
                "id": job.get("id"),
                "title": job.get("title"),
                "location": job.get("location", {}).get("name"),
                "departments": [dept.get("name") for dept in job.get("departments", [])],
                "absolute_url": job.get("absolute_url")
            }
            for job in jobs
        ]
        
        return formatted_jobs
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list Job Board jobs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )
