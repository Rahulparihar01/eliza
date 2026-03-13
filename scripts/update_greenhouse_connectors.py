"""
Update Greenhouse connectors with the new API key.
"""
import sys
sys.path.insert(0, '/app')

from src.models import database
from src.models.connector import ConnectorConfiguration
from src.utils.encryption import encrypt_value
from datetime import datetime, UTC
import json

# Initialize database
if database.SessionLocal is None:
    database.init_database()

db = database.SessionLocal()

try:
    # New API key
    new_api_key = "ada902b97b18f7131f1784ee99dbb4a5-4"
    board_token = "caylent"  # You'll need to provide this if different
    
    print("=" * 60)
    print("Updating Greenhouse Connectors")
    print("=" * 60)
    
    # 1. Update existing Greenhouse Production connector (Harvest API)
    harvest_connector = db.query(ConnectorConfiguration).filter(
        ConnectorConfiguration.id == 67
    ).first()
    
    if harvest_connector:
        print(f"\n✅ Found Harvest API connector: {harvest_connector.connector_name}")
        harvest_connector.credentials_encrypted = encrypt_value(json.dumps({
            "api_key": new_api_key
        }))
        harvest_connector.updated_at = datetime.now(UTC)
        print(f"   Updated with new API key: {new_api_key[:10]}...")
    else:
        print("\n⚠️  Harvest API connector not found, creating new one...")
        harvest_connector = ConnectorConfiguration(
            customer_id="eliza",
            connector_name="Greenhouse Production",
            connector_type="greenhouse",
            credentials_encrypted=encrypt_value(json.dumps({
                "api_key": new_api_key
            })),
            sync_config={
                "max_candidates": 50,
                "job_ids": ""
            },
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        db.add(harvest_connector)
        print(f"   Created Harvest API connector")
    
    # 2. Create or update Job Board API connector
    job_board_connector = db.query(ConnectorConfiguration).filter(
        ConnectorConfiguration.connector_name == "Greenhouse Job Board - Applicant Submission"
    ).first()
    
    if job_board_connector:
        print(f"\n✅ Found Job Board API connector: {job_board_connector.connector_name}")
        job_board_connector.credentials_encrypted = encrypt_value(json.dumps({
            "api_key": new_api_key,
            "board_token": board_token
        }))
        job_board_connector.sync_config = {
            "board_token": board_token
        }
        job_board_connector.updated_at = datetime.now(UTC)
        print(f"   Updated with new API key and board token: {board_token}")
    else:
        print("\n⚠️  Job Board API connector not found, creating new one...")
        job_board_connector = ConnectorConfiguration(
            connector_id="greenhouse_job_board_eliza",
            customer_id="eliza",
            connector_name="Greenhouse Job Board - Applicant Submission",
            connector_type="greenhouse",
            use_shared_credentials=False,  # We store credentials directly
            credentials_encrypted=encrypt_value(json.dumps({
                "api_key": new_api_key,
                "board_token": board_token
            })),
            sync_config={
                "board_token": board_token
            },
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC)
        )
        db.add(job_board_connector)
        print(f"   Created Job Board API connector")
    
    # Commit all changes
    db.commit()
    
    print("\n" + "=" * 60)
    print("✅ SUCCESS: Both connectors updated!")
    print("=" * 60)
    print(f"\n1. Harvest API Connector: {harvest_connector.id}")
    print(f"   - Name: {harvest_connector.connector_name}")
    print(f"   - API Key: {new_api_key[:10]}...")
    print(f"   - Purpose: Query candidates from Greenhouse (read-only)")
    
    print(f"\n2. Job Board API Connector: {job_board_connector.id}")
    print(f"   - Name: {job_board_connector.connector_name}")
    print(f"   - API Key: {new_api_key[:10]}...")
    print(f"   - Board Token: {board_token}")
    print(f"   - Purpose: Submit candidates to Greenhouse jobs")
    
    print("\n" + "=" * 60)

except Exception as e:
    db.rollback()
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    db.close()

