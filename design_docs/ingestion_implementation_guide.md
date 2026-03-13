# Data Ingestion Layer Implementation Guide
## Architecture Without CrewAI

**Last Updated:** October 8, 2025  
**Status:** Implementation Ready

---

## Executive Summary

This document outlines the implementation of a dedicated data ingestion layer using:
- **Airbyte CDK** for connector framework (600+ pre-built connectors)
- **Celery dedicated worker** on separate `ingestion` queue
- **NO CrewAI** (CrewAI reserved for AI analysis, not data extraction)
- Multi-tenant isolation following existing `customer_id` patterns

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  USER / ADMIN PORTAL                                        │
│  • Configure connectors                                      │
│  • Trigger manual syncs                                      │
│  • View sync status & telemetry                             │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP API
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  FASTAPI APP (src/api/routes/connectors.py)                │
│  • Connector CRUD                                            │
│  • Enqueue sync tasks                                        │
│  • Stream telemetry via SSE                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │ Celery Task Queue
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  CELERY INGESTION WORKER (Dedicated Container)             │
│  Queue: "ingestion"                                          │
│  Concurrency: 2 workers                                      │
│  Timeout: 2 hours per sync                                   │
│                                                              │
│  Tasks:                                                      │
│  • run_connector_sync()                                      │
│  • schedule_connector_sync()                                 │
│  • test_connector_connection()                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  CONNECTOR SERVICE (src/services/ingestion/)                │
│  • Load connector config & credentials (encrypted)           │
│  • Initialize appropriate connector instance                 │
│  • Execute sync: extract → transform → load                  │
│  • Manage state, checkpoints, pagination                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  CONNECTORS (Airbyte CDK-based)                             │
│  • PeopleDataLabsConnector                                   │
│  • SalesforceConnector (future)                              │
│  • PostgreSQLConnector (future)                              │
│  • etc.                                                      │
│                                                              │
│  Each connector implements:                                  │
│  • check()      - Test connection                           │
│  • discover()   - Get available streams/tables              │
│  • read()       - Stream records with pagination            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  EXTERNAL DATA SOURCES                                      │
│  • People Data Labs API                                      │
│  • Salesforce                                                │
│  • Customer databases                                        │
│  • Cloud storage                                             │
└─────────────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  STAGING STORAGE (PostgreSQL)                               │
│  Table: ingested_data                                        │
│  • Raw JSON records                                          │
│  • Per-customer isolation                                    │
│  • Status tracking: pending → enriched → indexed            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓ (Optional enrichment)
┌─────────────────────────────────────────────────────────────┐
│  AI ENRICHMENT LAYER (Optional, uses CrewAI if needed)      │
│  • Only for records needing AI analysis                     │
│  • Example: "Extract job seniority from title"              │
│  • Uses existing CrewAI agents                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  FINAL STORAGE                                              │
│  • Production tables (normalized data)                       │
│  • Vector indexes (FAISS - for search)                      │
│  • Graph relationships (Neo4j - for network analysis)        │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Connector Configuration

Stores per-customer connector configurations with encrypted credentials.

```python
# src/models/connector.py
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.models.database import BaseModel

class ConnectorConfiguration(BaseModel):
    """Customer-specific data connector configurations."""
    
    __tablename__ = "connector_configurations"
    
    # Identification
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)
    connector_id = Column(String(100), unique=True, nullable=False, index=True)  # "pdl_sales_prospects"
    
    # Configuration
    connector_type = Column(String(50), nullable=False)  # "people_data_labs", "salesforce", etc.
    connector_name = Column(String(255), nullable=False)  # "PDL - Sales Prospects"
    description = Column(Text, nullable=True)
    
    # Credentials (encrypted using your EncryptionService)
    credentials_encrypted = Column(Text, nullable=True)
    
    # Connector-specific configuration
    sync_config = Column(JSON, nullable=False, default={})  # API params, filters, mappings
    
    # Scheduling
    sync_schedule = Column(String(100), nullable=True)  # Cron expression: "0 2 * * *"
    sync_mode = Column(String(20), default="incremental")  # "full" or "incremental"
    
    # Status
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_healthy = Column(Boolean, default=True, nullable=False)
    last_health_check = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relationships
    customer = relationship("Customer", foreign_keys=[customer_id])
    sync_runs = relationship("ConnectorSyncRun", back_populates="connector")
    
    __table_args__ = (
        Index('ix_connector_customer_type', 'customer_id', 'connector_type'),
    )
```

### Sync Run Tracking

Tracks each execution of a connector sync.

```python
class ConnectorSyncRun(BaseModel):
    """Tracks individual connector sync executions."""
    
    __tablename__ = "connector_sync_runs"
    
    # Identification
    sync_id = Column(String(100), unique=True, nullable=False, index=True)
    connector_id = Column(Integer, ForeignKey("connector_configurations.id"), nullable=False)
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    
    # Execution details
    celery_task_id = Column(String(100), nullable=True, index=True)
    sync_mode = Column(String(20), nullable=False)  # "full" or "incremental"
    triggered_by = Column(String(50), nullable=False)  # "scheduled", "manual", "api"
    
    # Status
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Results
    records_extracted = Column(Integer, default=0)
    records_loaded = Column(Integer, default=0)
    records_failed = Column(Integer, default=0)
    
    # State management (for incremental syncs)
    checkpoint_data = Column(JSON, nullable=True)  # Last cursor, timestamp, etc.
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Performance metrics
    duration_seconds = Column(Integer, nullable=True)
    api_calls_made = Column(Integer, default=0)
    bytes_transferred = Column(Integer, default=0)
    
    # Relationships
    connector = relationship("ConnectorConfiguration", back_populates="sync_runs")
    telemetry_events = relationship("ConnectorTelemetry", back_populates="sync_run")
    
    __table_args__ = (
        Index('ix_sync_run_customer_status', 'customer_id', 'status'),
        Index('ix_sync_run_connector_created', 'connector_id', 'created_at'),
    )
```

### Ingested Data Staging

Temporary storage for raw extracted data before enrichment/loading.

```python
class IngestedData(BaseModel):
    """Staging table for raw ingested data."""
    
    __tablename__ = "ingested_data"
    
    # Identification
    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False)
    connector_id = Column(Integer, ForeignKey("connector_configurations.id"), nullable=False)
    sync_id = Column(String(100), ForeignKey("connector_sync_runs.sync_id"), nullable=False, index=True)
    
    # Data attribution
    company_dataset = Column(String(255), nullable=True, index=True)  # Like document.company_hr_dataset
    source_record_id = Column(String(255), nullable=True)  # External ID (e.g., PDL person ID)
    
    # Raw data
    raw_data = Column(JSON, nullable=False)  # Full record from source
    
    # Processing status
    status = Column(String(50), default="pending")  # pending, enriched, indexed, failed
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Metadata
    metadata = Column(JSON, nullable=True)  # Extraction timestamp, API version, etc.
    
    __table_args__ = (
        Index('ix_ingested_customer_company', 'customer_id', 'company_dataset'),
        Index('ix_ingested_status', 'customer_id', 'status'),
        Index('ix_ingested_sync', 'sync_id', 'status'),
    )
```

### Connector Telemetry

Real-time telemetry for streaming to frontend (like your BI telemetry).

```python
class ConnectorTelemetry(BaseModel):
    """Real-time telemetry events for connector syncs."""
    
    __tablename__ = "connector_telemetry"
    
    # Identification
    sync_id = Column(String(100), ForeignKey("connector_sync_runs.sync_id"), nullable=False, index=True)
    customer_id = Column(String(100), nullable=False)
    
    # Event details
    event_type = Column(String(50), nullable=False)  # sync_started, progress, completed, error
    event_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Progress tracking
    progress_percentage = Column(Float, nullable=True)
    current_stream = Column(String(255), nullable=True)  # For multi-stream connectors
    
    # Metrics
    records_processed = Column(Integer, default=0)
    api_calls_made = Column(Integer, default=0)
    
    # User-facing message
    user_message = Column(Text, nullable=True)
    
    # Technical details
    metadata = Column(JSON, nullable=True)
    
    # Relationships
    sync_run = relationship("ConnectorSyncRun", back_populates="telemetry_events")
    
    __table_args__ = (
        Index('ix_telemetry_sync_timestamp', 'sync_id', 'event_timestamp'),
    )
```

---

## Service Layer Implementation

### Connector Service

Main orchestration service for connector operations.

```python
# src/services/ingestion/connector_service.py
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session

from src.core.logging import get_logger, LogCategory
from src.models.connector import (
    ConnectorConfiguration,
    ConnectorSyncRun,
    IngestedData,
    ConnectorTelemetry
)
from src.utils.encryption import EncryptionService
from .connectors import get_connector_class

logger = get_logger(__name__, LogCategory.BUSINESS)


class ConnectorService:
    """Service for managing data connector operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.encryption = EncryptionService()
    
    def execute_sync(
        self,
        connector_id: int,
        customer_id: str,
        sync_mode: str,
        sync_params: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """
        Execute a connector sync.
        
        Steps:
        1. Load connector configuration
        2. Decrypt credentials
        3. Initialize connector instance
        4. Create sync run record
        5. Execute sync (extract → load)
        6. Update sync run with results
        """
        
        # 1. Load connector configuration
        connector_config = self.db.query(ConnectorConfiguration).filter_by(
            id=connector_id,
            customer_id=customer_id
        ).first()
        
        if not connector_config:
            raise ValueError(f"Connector {connector_id} not found for customer {customer_id}")
        
        if not connector_config.is_enabled:
            raise ValueError(f"Connector {connector_id} is disabled")
        
        # 2. Decrypt credentials
        credentials = self._decrypt_credentials(connector_config.credentials_encrypted)
        
        # 3. Create sync run record
        sync_id = f"sync_{uuid.uuid4().hex[:12]}"
        sync_run = ConnectorSyncRun(
            sync_id=sync_id,
            connector_id=connector_id,
            customer_id=customer_id,
            celery_task_id=task_id,
            sync_mode=sync_mode,
            triggered_by="api",
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        self.db.add(sync_run)
        self.db.commit()
        
        # 4. Add telemetry event
        self._add_telemetry(
            sync_id=sync_id,
            customer_id=customer_id,
            event_type="sync_started",
            user_message=f"Starting {connector_config.connector_name} sync...",
            progress_percentage=0.0
        )
        
        try:
            # 5. Initialize connector
            connector_class = get_connector_class(connector_config.connector_type)
            connector = connector_class(
                credentials=credentials,
                config=connector_config.sync_config,
                customer_id=customer_id
            )
            
            # 6. Execute sync
            records_synced = 0
            
            for batch_num, record_batch in enumerate(connector.read_stream(sync_mode, sync_params)):
                # Load batch to staging
                self._load_batch_to_staging(
                    records=record_batch,
                    sync_id=sync_id,
                    customer_id=customer_id,
                    connector_id=connector_id,
                    company_dataset=sync_params.get("company_dataset")
                )
                
                records_synced += len(record_batch)
                
                # Update progress
                progress = min((batch_num + 1) * 10, 90)  # Cap at 90% until completion
                self._add_telemetry(
                    sync_id=sync_id,
                    customer_id=customer_id,
                    event_type="progress",
                    user_message=f"Synced {records_synced} records...",
                    progress_percentage=progress,
                    records_processed=records_synced
                )
            
            # 7. Mark complete
            sync_run.status = "completed"
            sync_run.completed_at = datetime.now(timezone.utc)
            sync_run.records_extracted = records_synced
            sync_run.records_loaded = records_synced
            sync_run.duration_seconds = (sync_run.completed_at - sync_run.started_at).total_seconds()
            self.db.commit()
            
            self._add_telemetry(
                sync_id=sync_id,
                customer_id=customer_id,
                event_type="sync_completed",
                user_message=f"Sync completed: {records_synced} records",
                progress_percentage=100.0,
                records_processed=records_synced
            )
            
            return {
                "success": True,
                "sync_id": sync_id,
                "records_synced": records_synced,
                "duration_seconds": sync_run.duration_seconds
            }
            
        except Exception as e:
            logger.error(f"Sync failed: {e}", exc_info=True)
            
            sync_run.status = "failed"
            sync_run.completed_at = datetime.now(timezone.utc)
            sync_run.error_message = str(e)
            self.db.commit()
            
            self._add_telemetry(
                sync_id=sync_id,
                customer_id=customer_id,
                event_type="sync_failed",
                user_message=f"Sync failed: {str(e)}",
                progress_percentage=0.0
            )
            
            return {
                "success": False,
                "sync_id": sync_id,
                "error": str(e)
            }
    
    def _decrypt_credentials(self, encrypted_creds: str) -> Dict[str, str]:
        """Decrypt connector credentials."""
        import json
        decrypted = self.encryption.decrypt(encrypted_creds)
        return json.loads(decrypted)
    
    def _load_batch_to_staging(
        self,
        records: list,
        sync_id: str,
        customer_id: str,
        connector_id: int,
        company_dataset: Optional[str]
    ):
        """Load a batch of records to staging table."""
        staging_records = []
        
        for record in records:
            staging_record = IngestedData(
                customer_id=customer_id,
                connector_id=connector_id,
                sync_id=sync_id,
                company_dataset=company_dataset,
                source_record_id=record.get("id"),
                raw_data=record,
                status="pending"
            )
            staging_records.append(staging_record)
        
        self.db.bulk_save_objects(staging_records)
        self.db.commit()
    
    def _add_telemetry(
        self,
        sync_id: str,
        customer_id: str,
        event_type: str,
        user_message: str,
        progress_percentage: float,
        records_processed: int = 0
    ):
        """Add telemetry event for sync."""
        telemetry = ConnectorTelemetry(
            sync_id=sync_id,
            customer_id=customer_id,
            event_type=event_type,
            user_message=user_message,
            progress_percentage=progress_percentage,
            records_processed=records_processed
        )
        self.db.add(telemetry)
        self.db.commit()
    
    def test_connection(self, connector_id: int, customer_id: str) -> Dict[str, Any]:
        """Test connector connection and credentials."""
        connector_config = self.db.query(ConnectorConfiguration).filter_by(
            id=connector_id,
            customer_id=customer_id
        ).first()
        
        if not connector_config:
            return {
                "success": False,
                "healthy": False,
                "message": "Connector not found"
            }
        
        try:
            credentials = self._decrypt_credentials(connector_config.credentials_encrypted)
            
            connector_class = get_connector_class(connector_config.connector_type)
            connector = connector_class(
                credentials=credentials,
                config=connector_config.sync_config,
                customer_id=customer_id
            )
            
            # Call connector's check method
            check_result = connector.check()
            
            return {
                "success": True,
                "healthy": check_result.get("status") == "healthy",
                "message": check_result.get("message", "Connection successful"),
                "metadata": check_result.get("metadata", {})
            }
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}", exc_info=True)
            return {
                "success": False,
                "healthy": False,
                "message": str(e)
            }
    
    def should_run_sync(self, connector_id: int, customer_id: str) -> Tuple[bool, str]:
        """Check if a scheduled sync should run."""
        connector_config = self.db.query(ConnectorConfiguration).filter_by(
            id=connector_id,
            customer_id=customer_id
        ).first()
        
        if not connector_config:
            return False, "Connector not found"
        
        if not connector_config.is_enabled:
            return False, "Connector disabled"
        
        # Check last sync time
        last_sync = self.db.query(ConnectorSyncRun).filter_by(
            connector_id=connector_id
        ).order_by(ConnectorSyncRun.created_at.desc()).first()
        
        if last_sync and last_sync.status == "running":
            return False, "Previous sync still running"
        
        # Check schedule (cron expression parsing)
        # TODO: Implement cron schedule checking
        
        return True, "Schedule due"
```

---

## Sample Connector: People Data Labs

```python
# src/services/ingestion/connectors/people_data_labs.py
from typing import Dict, Any, Iterator, List, Optional
import requests
import time
from collections import deque
from threading import Lock

from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, LogCategory.BUSINESS)


class RateLimiter:
    """Token bucket rate limiter."""
    
    def __init__(self, max_requests: int, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()
    
    def acquire(self):
        """Block until rate limit allows request."""
        with self.lock:
            now = time.time()
            
            # Remove old requests
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            # Check limit
            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0])
                if sleep_time > 0:
                    logger.info(f"Rate limit reached, sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    return self.acquire()
            
            self.requests.append(now)


class PeopleDataLabsConnector:
    """
    People Data Labs API connector.
    
    Implements Airbyte-style connector interface:
    - check(): Test connection
    - discover(): List available streams
    - read(): Stream person records
    """
    
    BASE_URL = "https://api.peopledatalabs.com/v5"
    
    def __init__(
        self,
        credentials: Dict[str, str],
        config: Dict[str, Any],
        customer_id: str
    ):
        self.api_key = credentials.get("api_key")
        self.customer_id = customer_id
        self.config = config
        
        # Rate limiting (from config or default 60 req/min)
        rate_limit = config.get("rate_limit", 60)
        self.rate_limiter = RateLimiter(max_requests=rate_limit)
        
        # Pagination settings
        self.page_size = config.get("page_size", 100)
    
    def check(self) -> Dict[str, Any]:
        """
        Test connection and credentials.
        
        Returns:
            {
                "status": "healthy" | "unhealthy",
                "message": str,
                "metadata": {
                    "rate_limit": int,
                    "plan_tier": str
                }
            }
        """
        try:
            # Make a minimal API call
            response = requests.post(
                f"{self.BASE_URL}/person/search",
                headers={"X-Api-Key": self.api_key},
                json={
                    "query": {"location": ["United States"]},
                    "size": 1
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy",
                    "message": "Connection successful",
                    "metadata": {
                        "rate_limit": 60,  # Would parse from response headers
                        "total_records": data.get("total", 0)
                    }
                }
            elif response.status_code == 401:
                return {
                    "status": "unhealthy",
                    "message": "Invalid API key"
                }
            else:
                return {
                    "status": "unhealthy",
                    "message": f"API error: {response.status_code}"
                }
                
        except Exception as e:
            logger.error(f"Connection check failed: {e}")
            return {
                "status": "unhealthy",
                "message": str(e)
            }
    
    def discover(self) -> Dict[str, Any]:
        """
        Discover available streams (data types).
        
        For PDL, we have:
        - person_search: Search for person records
        - company_search: Search for company records (future)
        """
        return {
            "streams": [
                {
                    "name": "person_search",
                    "supported_sync_modes": ["full_refresh", "incremental"],
                    "json_schema": self._get_person_schema()
                }
            ]
        }
    
    def read_stream(
        self,
        sync_mode: str,
        sync_params: Dict[str, Any]
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Stream person records with pagination.
        
        Args:
            sync_mode: "full" or "incremental"
            sync_params: {
                "search_query": dict,  # PDL search query
                "checkpoint": dict     # For incremental sync
            }
        
        Yields:
            Batches of person records (list of dicts)
        """
        search_query = sync_params.get("search_query", {})
        checkpoint = sync_params.get("checkpoint", {})
        
        from_ = checkpoint.get("offset", 0)
        
        while True:
            self.rate_limiter.acquire()
            
            response = requests.post(
                f"{self.BASE_URL}/person/search",
                headers={"X-Api-Key": self.api_key},
                json={
                    "query": search_query,
                    "size": self.page_size,
                    "from": from_
                }
            )
            
            if response.status_code != 200:
                error_msg = f"PDL API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            data = response.json()
            records = data.get("data", [])
            
            if not records:
                break
            
            # Yield batch
            yield records
            
            # Check if more pages
            total = data.get("total", 0)
            from_ += self.page_size
            
            if from_ >= total:
                break
    
    def _get_person_schema(self) -> Dict[str, Any]:
        """Return JSON schema for person records."""
        return {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "full_name": {"type": "string"},
                "first_name": {"type": "string"},
                "last_name": {"type": "string"},
                "job_title": {"type": "string"},
                "job_company_name": {"type": "string"},
                "emails": {"type": "array", "items": {"type": "string"}},
                "phone_numbers": {"type": "array", "items": {"type": "string"}},
                "linkedin_url": {"type": "string"},
                # ... more fields
            }
        }
```

---

## API Endpoints

```python
# src/api/routes/connectors.py
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from src.models.database import get_db
from src.core.auth import get_current_user
from src.models.auth import User
from src.services.ingestion.connector_service import ConnectorService
from src.api.schemas.connectors import (
    ConnectorConfigRequest,
    ConnectorConfigResponse,
    ConnectorSyncRequest,
    ConnectorSyncResponse,
    ConnectorStatusResponse
)

router = APIRouter(prefix="/v1/connectors", tags=["Data Connectors"])


@router.post("/configure", response_model=ConnectorConfigResponse)
async def configure_connector(
    request: ConnectorConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Configure a new data connector.
    
    Endpoint for admins to set up data connectors like People Data Labs,
    Salesforce, etc.
    """
    service = ConnectorService(db)
    
    connector_id = service.create_connector(
        customer_id=current_user.customer_id,
        connector_type=request.connector_type,
        connector_name=request.name,
        credentials=request.credentials,
        config=request.config,
        created_by_user_id=current_user.id
    )
    
    return ConnectorConfigResponse(
        connector_id=connector_id,
        message="Connector configured successfully"
    )


@router.post("/{connector_id}/sync", response_model=ConnectorSyncResponse)
async def trigger_sync(
    connector_id: int,
    request: ConnectorSyncRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trigger a manual connector sync.
    
    Queues a Celery task on the ingestion queue.
    """
    from src.tasks.ingestion_tasks import run_connector_sync
    
    # Queue task
    task = run_connector_sync.delay(
        connector_id=connector_id,
        customer_id=current_user.customer_id,
        sync_mode=request.sync_mode,
        sync_params=request.sync_params
    )
    
    return ConnectorSyncResponse(
        sync_id=task.id,
        status="queued",
        message="Sync started in background"
    )


@router.get("/{connector_id}/status", response_model=ConnectorStatusResponse)
async def get_connector_status(
    connector_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get connector status and recent sync history."""
    service = ConnectorService(db)
    
    status = service.get_connector_status(
        connector_id=connector_id,
        customer_id=current_user.customer_id
    )
    
    return ConnectorStatusResponse(**status)


@router.post("/{connector_id}/test")
async def test_connection(
    connector_id: int,
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Test connector connection (async)."""
    from src.tasks.ingestion_tasks import test_connector_connection
    
    task = test_connector_connection.delay(
        connector_id=connector_id,
        customer_id=current_user.customer_id
    )
    
    return {
        "test_id": task.id,
        "status": "testing",
        "message": "Connection test started"
    }
```

---

## Key Differences from Your BI Pipeline

| Aspect | BI Pipeline (Current) | Ingestion Pipeline (New) |
|--------|----------------------|--------------------------|
| **Purpose** | Answer user questions with AI | Extract bulk data from APIs/DBs |
| **Uses CrewAI?** | ✅ YES (Task Enrichment + Analysis) | ❌ NO (Pure data extraction) |
| **Queue** | `celery` (default) | `ingestion` (dedicated) |
| **Timeout** | Shorter (minutes) | Longer (2 hours) |
| **Concurrency** | 4 workers | 2 workers |
| **Triggers** | User asks question | Scheduled or manual |
| **Output** | Analyzed insights | Raw records in staging |
| **State** | Question → Enrichment → Analysis | Connector → Sync → Staging |

---

## Next Steps

1. **Create Database Migration**
   ```bash
   alembic revision -m "add_connector_tables"
   # Edit migration file with models above
   alembic upgrade head
   ```

2. **Implement Connector Service**
   - Create `src/services/ingestion/` directory
   - Implement `ConnectorService` class
   - Implement `PeopleDataLabsConnector`

3. **Add API Routes**
   - Create `src/api/routes/connectors.py`
   - Create Pydantic schemas for requests/responses

4. **Build & Deploy**
   ```bash
   docker-compose build app celery-worker celery-ingestion-worker
   docker-compose up -d
   ```

5. **Test PDL Connector**
   - Configure via API
   - Trigger test sync
   - Monitor in Flower: http://localhost:5555

6. **Add Frontend UI**
   - Connector configuration page
   - Sync history & telemetry (like your BI telemetry)
   - Real-time progress via SSE

---

## Questions to Answer Before Starting

1. **Do you have a People Data Labs API key?**
   - What's your rate limit tier?
   - What's your monthly record quota?

2. **Who can configure connectors?**
   - Admin-only?
   - Or customer-facing?

3. **Data enrichment strategy?**
   - Should ingested records go through AI enrichment?
   - Or load raw to staging and enrich on-demand?

4. **Storage retention?**
   - How long to keep raw staging data?
   - When to purge old syncs?

5. **Cost limits?**
   - Per-customer spending caps?
   - Alert thresholds?

---

**Status:** Ready for implementation. All components align with existing architecture.

