"""
Comprehensive Integration Test for Data Ingestion Pipeline

Tests the complete ingestion pipeline from configuration to transformed data:
1. Configuration creation with validation
2. Connection testing
3. Cost estimation
4. Sync execution
5. Data transformation
6. Deduplication
7. Telemetry tracking
8. Statistics

Prerequisites:
- Database migrations run (alembic upgrade head)
- ENCRYPTION_KEY set

Note: Uses mocked PDL API responses to avoid rate limits and ensure deterministic testing.
"""
import time
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import responses
from sqlalchemy.orm import Session

from src.models import database
from src.models.connector import (
    ConnectorConfiguration,
    ConnectorSyncRun,
    IngestedData,
    ConnectorTelemetry,
    PDLPerson,
    SyncStatus,
    IngestionStatus,
    ConnectorTelemetryEventType
)
from src.models.customer import Customer
from src.services.ingestion.connector_service import ConnectorService
from src.services.ingestion.connectors import (
    create_connector,
    validate_connector_config,
    list_available_connectors
)
from src.services.ingestion.transformers import PDLTransformer
from src.core.logging import get_logger, LogCategory
from tests.fixtures.pdl_mock_responses import (
    SEARCH_SINGLE_RESULT_RESPONSE,
    SEARCH_NO_RESULTS_RESPONSE
)

logger = get_logger(__name__, LogCategory.BUSINESS)

# Test configuration
PDL_API_KEY = "5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7"
TEST_CUSTOMER_ID = "test_customer_ingestion"
TEST_USER_ID = 1


def setup_database():
    """Initialize database connection."""
    if database.SessionLocal is None:
        logger.info("Initializing database...")
        database.init_database()
    
    if database.SessionLocal is None:
        raise RuntimeError("Failed to initialize database")
    
    return database.SessionLocal()


def create_test_customer(db: Session):
    """Create test customer if it doesn't exist."""
    logger.info("Creating test customer...")
    
    # Check if customer already exists
    customer = db.query(Customer).filter(Customer.customer_id == TEST_CUSTOMER_ID).first()
    
    if not customer:
        customer = Customer(
            customer_id=TEST_CUSTOMER_ID,
            name="Test Customer for Ingestion",
            display_name="Test Ingestion Customer",
            is_active=True,
            subscription_tier="enterprise"
        )
        db.add(customer)
        db.commit()
        logger.info(f"✅ Created test customer: {TEST_CUSTOMER_ID}")
    else:
        logger.info(f"✅ Test customer already exists: {TEST_CUSTOMER_ID}")


def cleanup_test_data(db: Session):
    """Clean up test data from previous runs."""
    logger.info("Cleaning up test data...")
    
    # Delete in correct order (foreign keys)
    db.query(ConnectorTelemetry).filter(
        ConnectorTelemetry.customer_id == TEST_CUSTOMER_ID
    ).delete()
    
    db.query(IngestedData).filter(
        IngestedData.customer_id == TEST_CUSTOMER_ID
    ).delete()
    
    db.query(PDLPerson).filter(
        PDLPerson.customer_id == TEST_CUSTOMER_ID
    ).delete()
    
    db.query(ConnectorSyncRun).filter(
        ConnectorSyncRun.customer_id == TEST_CUSTOMER_ID
    ).delete()
    
    db.query(ConnectorConfiguration).filter(
        ConnectorConfiguration.customer_id == TEST_CUSTOMER_ID
    ).delete()
    
    db.commit()
    logger.info("Test data cleaned up")


@pytest.mark.usefixtures("mock_pdl_api")
class TestIngestionPipeline:
    """Comprehensive integration tests for data ingestion pipeline."""
    
    @classmethod
    def setup_class(cls):
        """Set up test database."""
        cls.db = setup_database()
        cleanup_test_data(cls.db)
        create_test_customer(cls.db)
    
    @classmethod
    def teardown_class(cls):
        """Clean up after tests."""
        cleanup_test_data(cls.db)
        cls.db.close()
    
    @pytest.fixture(autouse=True)
    def setup_method(self, mock_pdl_api):
        """Set up mock API responses for each test."""
        # The mock_pdl_api fixture from conftest.py is automatically applied
        # This ensures all HTTP requests to PDL API are mocked
        pass
    
    # -------------------------------------------------------------------------
    # Test 1: Connector Types Discovery
    # -------------------------------------------------------------------------
    
    def test_01_list_connector_types(self):
        """Test listing available connector types."""
        logger.info("=" * 80)
        logger.info("TEST 1: List Connector Types")
        logger.info("=" * 80)
        
        connector_types = list_available_connectors()
        
        assert len(connector_types) > 0, "Should have at least one connector type"
        
        # Check for PDL connector
        pdl_connector = next((c for c in connector_types if c["type"] == "people_data_labs"), None)
        assert pdl_connector is not None, "Should have people_data_labs connector"
        
        logger.info(f"✅ Found {len(connector_types)} connector types")
        logger.info(f"✅ PDL Connector: {pdl_connector['name']} - {pdl_connector['description']}")
    
    # -------------------------------------------------------------------------
    # Test 2: Configuration Validation
    # -------------------------------------------------------------------------
    
    def test_02_validate_configuration(self):
        """Test configuration validation before creation."""
        logger.info("=" * 80)
        logger.info("TEST 2: Configuration Validation")
        logger.info("=" * 80)
        
        # Test valid configuration
        valid_config = {
            "search_query": {
                "job_title_role": ["software engineer"],
                "job_company_name": ["Google", "Amazon"],
                "location_country": ["United States"]
            },
            "max_records": 1,  # Only 1 row for testing (minimize API costs)
            "page_size": 1
        }
        
        is_valid, error = validate_connector_config("people_data_labs", valid_config)
        assert is_valid, f"Valid config should pass: {error}"
        logger.info("✅ Valid configuration passed validation")
        
        # Test invalid configuration (missing search_query)
        invalid_config = {
            "max_records": 1
        }
        
        is_valid, error = validate_connector_config("people_data_labs", invalid_config)
        assert not is_valid, "Invalid config should fail"
        logger.info(f"✅ Invalid configuration rejected: {error}")
        
        # Test invalid field
        invalid_field_config = {
            "search_query": {
                "invalid_field": ["value"]  # Not a valid PDL field
            }
        }
        
        is_valid, error = validate_connector_config("people_data_labs", invalid_field_config)
        assert not is_valid, "Config with invalid field should fail"
        logger.info(f"✅ Invalid field rejected: {error}")
    
    # -------------------------------------------------------------------------
    # Test 3: Connection Testing
    # -------------------------------------------------------------------------
    
    def test_03_test_connection(self):
        """Test connector connection with credentials."""
        logger.info("=" * 80)
        logger.info("TEST 3: Connection Testing")
        logger.info("=" * 80)
        
        credentials = {"api_key": PDL_API_KEY}
        config = {
            "search_query": {
                "location_country": ["United States"]
            },
            "max_records": 1,
            "page_size": 1
        }
        
        connector = create_connector(
            connector_type="people_data_labs",
            credentials=credentials,
            config=config,
            customer_id=TEST_CUSTOMER_ID
        )
        
        result = connector.check()
        
        assert result["status"] in ["healthy", "degraded"], f"Connection should succeed: {result}"
        logger.info(f"✅ Connection test passed: {result['status']}")
        logger.info(f"   Message: {result['message']}")
        if result.get("metadata"):
            logger.info(f"   Metadata: {result['metadata']}")
    
    # -------------------------------------------------------------------------
    # Test 4: Cost Estimation
    # -------------------------------------------------------------------------
    
    def test_04_cost_estimation(self):
        """Test cost estimation for a query."""
        logger.info("=" * 80)
        logger.info("TEST 4: Cost Estimation")
        logger.info("=" * 80)
        
        credentials = {"api_key": PDL_API_KEY}
        config = {
            "search_query": {
                "job_title_role": ["software engineer"],
                "job_company_name": ["Google"],
                "location_country": ["United States"]
            }
        }
        
        connector = create_connector(
            connector_type="people_data_labs",
            credentials=credentials,
            config=config,
            customer_id=TEST_CUSTOMER_ID
        )
        
        estimated_count = connector.estimate_record_count()
        
        assert estimated_count is not None, "Should return estimated count"
        assert estimated_count >= 0, "Estimated count should be non-negative"
        
        logger.info(f"✅ Estimated record count: {estimated_count:,}")
        logger.info(f"   Estimated cost: ${estimated_count * 0.02:.2f}")
    
    # -------------------------------------------------------------------------
    # Test 5: Configuration Creation
    # -------------------------------------------------------------------------
    
    def test_05_create_configuration(self):
        """Test creating a connector configuration."""
        logger.info("=" * 80)
        logger.info("TEST 5: Configuration Creation")
        logger.info("=" * 80)
        
        service = ConnectorService(self.db)
        
        config = service.create_configuration(
            customer_id=TEST_CUSTOMER_ID,
            connector_type="people_data_labs",
            connector_name="Test PDL Connector - AI Engineers",
            credentials={"api_key": PDL_API_KEY},
            sync_config={
                "search_query": {
                    "job_title_role": ["software engineer", "data scientist"],
                    "job_company_name": ["Google", "Amazon", "Microsoft"],
                    "location_country": ["United States"],
                    "skills": ["python", "machine learning"]
                },
                "max_records": 1,  # Only 1 row for testing (minimize API costs)
                "page_size": 1,
                "rate_limit": 60,
                "estimated_cost_acknowledged": True
            },
            description="Test connector for AI/ML engineers at top tech companies",
            tags=["test", "ai", "engineering"],
            created_by_user_id=TEST_USER_ID,
            use_shared_credentials=False,
            sync_schedule=None  # Manual trigger only for testing
        )
        
        assert config.id is not None, "Configuration should be saved with ID"
        assert config.connector_id is not None, "Should have connector_id"
        assert config.credentials_encrypted is not None, "Credentials should be encrypted"
        assert config.is_enabled is True, "Should be enabled by default"
        
        logger.info(f"✅ Configuration created: {config.connector_id}")
        logger.info(f"   Name: {config.connector_name}")
        logger.info(f"   Type: {config.connector_type}")
        logger.info(f"   Version: {config.sync_config_version}")
        
        # Store for later tests
        self.__class__.connector_id = config.connector_id
        self.__class__.connector_config_id = config.id
    
    # -------------------------------------------------------------------------
    # Test 6: List Configurations
    # -------------------------------------------------------------------------
    
    def test_06_list_configurations(self):
        """Test listing connector configurations."""
        logger.info("=" * 80)
        logger.info("TEST 6: List Configurations")
        logger.info("=" * 80)
        
        service = ConnectorService(self.db)
        
        configs = service.list_configurations(customer_id=TEST_CUSTOMER_ID)
        
        assert len(configs) > 0, "Should have at least one configuration"
        assert any(c.connector_id == self.__class__.connector_id for c in configs), "Should find our test connector"
        
        logger.info(f"✅ Found {len(configs)} configurations")
        for config in configs:
            logger.info(f"   - {config.connector_name} ({config.connector_type})")
    
    # -------------------------------------------------------------------------
    # Test 7: Trigger Manual Sync
    # -------------------------------------------------------------------------
    
    def test_07_trigger_sync(self):
        """Test triggering a manual sync."""
        logger.info("=" * 80)
        logger.info("TEST 7: Trigger Manual Sync")
        logger.info("=" * 80)
        
        service = ConnectorService(self.db)
        
        sync_run = service.trigger_sync(
            connector_id=self.__class__.connector_id,
            customer_id=TEST_CUSTOMER_ID,
            manual_trigger=True
        )
        
        assert sync_run.id is not None, "Sync run should be created"
        assert sync_run.sync_id is not None, "Should have sync_id"
        assert sync_run.status == SyncStatus.PENDING.value, "Should start in PENDING status"
        
        logger.info(f"✅ Sync triggered: {sync_run.sync_id}")
        logger.info(f"   Status: {sync_run.status}")
        logger.info(f"   Started: {sync_run.started_at}")
        
        # Store for later tests
        self.__class__.sync_run_id = sync_run.id
        self.__class__.sync_id = sync_run.sync_id
        
        # Wait a moment for Celery to pick up the task
        logger.info("   Waiting 5 seconds for Celery to start task...")
        time.sleep(5)
    
    # -------------------------------------------------------------------------
    # Test 8: Execute Sync Directly (Simulated)
    # -------------------------------------------------------------------------
    
    def test_08_execute_sync_directly(self):
        """
        Execute sync directly (simulating what Celery does).
        
        In real deployment, Celery worker would execute this.
        For testing, we run it directly.
        """
        logger.info("=" * 80)
        logger.info("TEST 8: Execute Sync Directly")
        logger.info("=" * 80)
        
        service = ConnectorService(self.db)
        
        # Fetch the connector config
        config = service.get_configuration(self.__class__.connector_id, TEST_CUSTOMER_ID)
        assert config is not None, "Configuration should exist"
        
        logger.info(f"Executing sync for: {config.connector_name}")
        logger.info(f"Query: {config.sync_config.get('search_query')}")
        
        # Execute sync
        result = service.execute_sync(
            connector_id=self.__class__.connector_id,
            customer_id=TEST_CUSTOMER_ID,
            sync_mode="full",
            sync_params={
                "sync_run_id": self.__class__.sync_run_id,
                "sync_id": self.__class__.sync_id,
                "connector_type": config.connector_type,
                "sync_config": config.sync_config
            },
            task_id="test_task_id"
        )
        
        assert result["success"] is True, f"Sync should succeed: {result}"
        assert result["records_synced"] > 0, "Should have synced some records"
        
        logger.info(f"✅ Sync completed successfully")
        logger.info(f"   Records synced: {result['records_synced']}")
        logger.info(f"   Records loaded: {result['records_loaded']}")
        logger.info(f"   Records failed: {result['records_failed']}")
        logger.info(f"   Duration: {result['duration_seconds']:.2f}s")
        logger.info(f"   Batches: {result['batches_processed']}")
    
    # -------------------------------------------------------------------------
    # Test 9: Verify Sync Run Status
    # -------------------------------------------------------------------------
    
    def test_09_verify_sync_run_status(self):
        """Verify sync run was updated with correct status."""
        logger.info("=" * 80)
        logger.info("TEST 9: Verify Sync Run Status")
        logger.info("=" * 80)
        
        sync_run = self.db.query(ConnectorSyncRun).filter(
            ConnectorSyncRun.id == self.__class__.sync_run_id
        ).first()
        
        assert sync_run is not None, "Sync run should exist"
        assert sync_run.status == SyncStatus.COMPLETED.value, f"Should be completed, got: {sync_run.status}"
        assert sync_run.completed_at is not None, "Should have end time"
        assert sync_run.records_extracted > 0, "Should have read records"
        assert sync_run.records_loaded > 0, "Should have ingested records"
        # Note: records_transformed is not a direct model field
        
        logger.info(f"✅ Sync run status verified")
        logger.info(f"   Status: {sync_run.status}")
        logger.info(f"   Records extracted: {sync_run.records_extracted}")
        logger.info(f"   Records loaded: {sync_run.records_loaded}")
        logger.info(f"   Records skipped: {sync_run.records_skipped}")
        logger.info(f"   Records failed: {sync_run.records_failed}")
    
    # -------------------------------------------------------------------------
    # Test 10: Verify Ingested Data (Staging)
    # -------------------------------------------------------------------------
    
    def test_10_verify_ingested_data(self):
        """Verify raw data was saved to staging table."""
        logger.info("=" * 80)
        logger.info("TEST 10: Verify Ingested Data (Staging)")
        logger.info("=" * 80)
        
        ingested_count = self.db.query(IngestedData).filter(
            IngestedData.sync_id == self.__class__.sync_id
        ).count()
        
        assert ingested_count > 0, "Should have ingested data records"
        
        # Check status distribution
        pending = self.db.query(IngestedData).filter(
            IngestedData.sync_id == self.__class__.sync_id,
            IngestedData.status == IngestionStatus.PENDING.value
        ).count()
        
        transformed = self.db.query(IngestedData).filter(
            IngestedData.sync_id == self.__class__.sync_id,
            IngestedData.status == IngestionStatus.TRANSFORMED.value
        ).count()
        
        failed = self.db.query(IngestedData).filter(
            IngestedData.sync_id == self.__class__.sync_id,
            IngestedData.status == IngestionStatus.FAILED.value
        ).count()
        
        logger.info(f"✅ Ingested data verified")
        logger.info(f"   Total records: {ingested_count}")
        logger.info(f"   Pending: {pending}")
        logger.info(f"   Transformed: {transformed}")
        logger.info(f"   Failed: {failed}")
        
        # Sample one record
        sample = self.db.query(IngestedData).filter(
            IngestedData.sync_id == self.__class__.sync_id
        ).first()
        
        if sample:
            logger.info(f"   Sample record ID: {sample.source_record_id}")
            logger.info(f"   Sample data keys: {list(sample.raw_data.keys())}")
    
    # -------------------------------------------------------------------------
    # Test 11: Verify Transformed Data (PDLPerson)
    # -------------------------------------------------------------------------
    
    def test_11_verify_transformed_data(self):
        """Verify data was transformed to PDLPerson records."""
        logger.info("=" * 80)
        logger.info("TEST 11: Verify Transformed Data (PDLPerson)")
        logger.info("=" * 80)
        
        persons_count = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == TEST_CUSTOMER_ID
        ).count()
        
        assert persons_count > 0, "Should have transformed PDLPerson records"
        
        logger.info(f"✅ Transformed data verified")
        logger.info(f"   Total persons: {persons_count}")
        
        # Sample records
        sample_persons = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == TEST_CUSTOMER_ID
        ).limit(5).all()
        
        logger.info(f"\n   Sample persons:")
        for person in sample_persons:
            logger.info(f"   - {person.full_name or '(no name)'}")
            logger.info(f"     Title: {person.job_title or 'N/A'}")
            logger.info(f"     Company: {person.job_company_name or 'N/A'}")
            logger.info(f"     Location: {person.location_country or 'N/A'}")
            logger.info(f"     Sync count: {person.sync_count}")
    
    # -------------------------------------------------------------------------
    # Test 12: Verify Telemetry Events
    # -------------------------------------------------------------------------
    
    def test_12_verify_telemetry(self):
        """Verify telemetry events were logged."""
        logger.info("=" * 80)
        logger.info("TEST 12: Verify Telemetry Events")
        logger.info("=" * 80)
        
        telemetry_count = self.db.query(ConnectorTelemetry).filter(
            ConnectorTelemetry.sync_id == self.__class__.sync_id
        ).count()
        
        assert telemetry_count > 0, "Should have telemetry events"
        
        # Count by event type
        event_types = self.db.query(
            ConnectorTelemetry.event_type,
            database.func.count(ConnectorTelemetry.id)
        ).filter(
            ConnectorTelemetry.sync_id == self.__class__.sync_id
        ).group_by(ConnectorTelemetry.event_type).all()
        
        logger.info(f"✅ Telemetry verified")
        logger.info(f"   Total events: {telemetry_count}")
        logger.info(f"\n   Event types:")
        for event_type, count in event_types:
            logger.info(f"   - {event_type}: {count}")
    
    # -------------------------------------------------------------------------
    # Test 13: Test Deduplication (Run Sync Again)
    # -------------------------------------------------------------------------
    
    def test_13_test_deduplication(self):
        """Test deduplication by running sync again."""
        logger.info("=" * 80)
        logger.info("TEST 13: Test Deduplication (Second Sync)")
        logger.info("=" * 80)
        
        # Get initial count
        initial_count = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == TEST_CUSTOMER_ID
        ).count()
        
        logger.info(f"Initial person count: {initial_count}")
        
        # Trigger second sync
        service = ConnectorService(self.db)
        sync_run2 = service.trigger_sync(
            connector_id=self.__class__.connector_id,
            customer_id=TEST_CUSTOMER_ID,
            manual_trigger=True
        )
        
        logger.info(f"Second sync triggered: {sync_run2.sync_id}")
        
        # Execute second sync
        config = service.get_configuration(self.__class__.connector_id, TEST_CUSTOMER_ID)
        result2 = service.execute_sync(
            connector_id=self.__class__.connector_id,
            customer_id=TEST_CUSTOMER_ID,
            sync_mode="full",
            sync_params={
                "sync_run_id": sync_run2.id,
                "sync_id": sync_run2.sync_id,
                "connector_type": config.connector_type,
                "sync_config": config.sync_config
            },
            task_id="test_task_id_2"
        )
        
        logger.info(f"Second sync completed")
        logger.info(f"   Records synced: {result2['records_synced']}")
        logger.info(f"   Records loaded: {result2['records_loaded']}")
        
        # Get final count
        final_count = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == TEST_CUSTOMER_ID
        ).count()
        
        logger.info(f"Final person count: {final_count}")
        
        # Count should be same or slightly higher (due to potential new records)
        # But should not double
        assert final_count <= initial_count * 1.2, "Deduplication should prevent doubling"
        
        # Check sync_count was incremented
        persons_with_multiple_syncs = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == TEST_CUSTOMER_ID,
            PDLPerson.sync_count > 1
        ).count()
        
        assert persons_with_multiple_syncs > 0, "Some persons should have sync_count > 1"
        
        logger.info(f"✅ Deduplication verified")
        logger.info(f"   Persons seen multiple times: {persons_with_multiple_syncs}")
        logger.info(f"   Total count change: {final_count - initial_count} ({(final_count / initial_count - 1) * 100:+.1f}%)")
    
    # -------------------------------------------------------------------------
    # Test 14: Configuration Update with Versioning
    # -------------------------------------------------------------------------
    
    def test_14_configuration_update(self):
        """Test updating configuration with versioning."""
        logger.info("=" * 80)
        logger.info("TEST 14: Configuration Update with Versioning")
        logger.info("=" * 80)
        
        service = ConnectorService(self.db)
        
        # Get initial version
        config = service.get_configuration(self.__class__.connector_id, TEST_CUSTOMER_ID)
        initial_version = config.sync_config_version
        
        logger.info(f"Initial version: {initial_version}")
        
        # Update sync_config
        updated_config = service.update_configuration(
            connector_id=self.__class__.connector_id,
            customer_id=TEST_CUSTOMER_ID,
            updates={
                "sync_config": {
                    "search_query": {
                        "job_title_role": ["data scientist"],  # Changed query
                        "job_company_name": ["Google", "Amazon"],
                        "location_country": ["United States"]
                    },
                    "max_records": 1,  # Only 1 row (minimize API costs)
                    "page_size": 1
                },
                "description": "Updated test connector"
            }
        )
        
        assert updated_config.sync_config_version == initial_version + 1, "Version should increment"
        assert updated_config.sync_config_history is not None, "Should have history"
        assert len(updated_config.sync_config_history) > 0, "History should contain old config"
        
        logger.info(f"✅ Configuration updated")
        logger.info(f"   New version: {updated_config.sync_config_version}")
        logger.info(f"   History entries: {len(updated_config.sync_config_history)}")
        logger.info(f"   Updated description: {updated_config.description}")
    
    # -------------------------------------------------------------------------
    # Test 15: Connector Statistics
    # -------------------------------------------------------------------------
    
    def test_15_connector_statistics(self):
        """Test aggregate statistics for connector."""
        logger.info("=" * 80)
        logger.info("TEST 15: Connector Statistics")
        logger.info("=" * 80)
        
        # Aggregate sync runs
        sync_runs = self.db.query(ConnectorSyncRun).join(
            ConnectorConfiguration
        ).filter(
            ConnectorConfiguration.connector_id == self.__class__.connector_id
        ).all()
        
        total_syncs = len(sync_runs)
        successful_syncs = sum(1 for s in sync_runs if s.status == SyncStatus.COMPLETED.value)
        total_records = sum(s.records_extracted for s in sync_runs)
        total_transformed = sum(s.records_loaded for s in sync_runs)
        
        logger.info(f"✅ Statistics computed")
        logger.info(f"   Total syncs: {total_syncs}")
        logger.info(f"   Successful syncs: {successful_syncs}")
        logger.info(f"   Success rate: {successful_syncs / total_syncs * 100:.1f}%")
        logger.info(f"   Total records synced: {total_records}")
        logger.info(f"   Total records transformed: {total_transformed}")
        logger.info(f"   Average records per sync: {total_records / total_syncs:.1f}")
    
    # -------------------------------------------------------------------------
    # Test 16: Final Data Integrity Check
    # -------------------------------------------------------------------------
    
    def test_16_data_integrity(self):
        """Final data integrity checks."""
        logger.info("=" * 80)
        logger.info("TEST 16: Data Integrity Check")
        logger.info("=" * 80)
        
        # Check foreign key integrity
        orphaned_sync_runs = self.db.query(ConnectorSyncRun).filter(
            ConnectorSyncRun.connector_id == self.__class__.connector_config_id,
            ~ConnectorSyncRun.connector_id.in_(
                self.db.query(ConnectorConfiguration.id)
            )
        ).count()
        
        assert orphaned_sync_runs == 0, "Should have no orphaned sync runs"
        
        # Check PDLPerson records have required fields
        persons_missing_pdl_id = self.db.query(PDLPerson).filter(
            PDLPerson.customer_id == TEST_CUSTOMER_ID,
            PDLPerson.pdl_id.is_(None)
        ).count()
        
        assert persons_missing_pdl_id == 0, "All persons should have pdl_id"
        
        # Check IngestedData records link to valid sync_run
        orphaned_ingested_data = self.db.query(IngestedData).filter(
            IngestedData.customer_id == TEST_CUSTOMER_ID,
            ~IngestedData.sync_id.in_(
                self.db.query(ConnectorSyncRun.sync_id)
            )
        ).count()
        
        assert orphaned_ingested_data == 0, "Should have no orphaned ingested data"
        
        logger.info(f"✅ Data integrity verified")
        logger.info(f"   No orphaned sync runs")
        logger.info(f"   All persons have pdl_id")
        logger.info(f"   No orphaned ingested data")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE INTEGRATION TEST - DATA INGESTION PIPELINE")
    print("=" * 80 + "\n")
    
    # Create test instance
    test_suite = TestIngestionPipeline()
    
    try:
        # Setup
        TestIngestionPipeline.setup_class()
        
        # Run tests in order
        test_suite.test_01_list_connector_types()
        test_suite.test_02_validate_configuration()
        test_suite.test_03_test_connection()
        test_suite.test_04_cost_estimation()
        test_suite.test_05_create_configuration()
        test_suite.test_06_list_configurations()
        test_suite.test_07_trigger_sync()
        test_suite.test_08_execute_sync_directly()
        test_suite.test_09_verify_sync_run_status()
        test_suite.test_10_verify_ingested_data()
        test_suite.test_11_verify_transformed_data()
        test_suite.test_12_verify_telemetry()
        test_suite.test_13_test_deduplication()
        test_suite.test_14_configuration_update()
        test_suite.test_15_connector_statistics()
        test_suite.test_16_data_integrity()
        
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80 + "\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # Cleanup
        TestIngestionPipeline.teardown_class()


if __name__ == "__main__":
    main()

