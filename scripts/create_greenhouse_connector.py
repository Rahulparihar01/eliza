"""
Create Greenhouse connector configuration for Eliza customer
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.models import database
from src.models.connector import ConnectorConfiguration
from src.utils.encryption import encrypt_value
import json
import uuid
from datetime import datetime, UTC

def create_greenhouse_connector():
    """Create Greenhouse connector with API key"""
    
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        # Your Greenhouse API key
        api_key = "JiCr2mh3hp3CG4aB6a8E"
        
        # Encrypt credentials
        credentials_json = json.dumps({"api_key": api_key})
        credentials_encrypted = encrypt_value(credentials_json)
        
        # Create connector configuration directly
        config = ConnectorConfiguration(
            connector_id=f"greenhouse_eliza_{uuid.uuid4().hex[:8]}",
            customer_id="eliza",
            connector_type="greenhouse",
            connector_name="Greenhouse Production",
            use_shared_credentials=False,
            credentials_encrypted=credentials_encrypted,
            sync_config={
                "max_candidates": 50,
                "job_ids": "",  # Empty = fetch all jobs
            },
            description="Primary Greenhouse ATS connector for candidate data",
            is_enabled=True,
            created_by_user_id=2,  # scott@eliza.com
            created_at=datetime.now(UTC)
        )
        
        db.add(config)
        db.commit()
        db.refresh(config)
        
        print(f"✅ Created Greenhouse connector:")
        print(f"   ID: {config.id}")
        print(f"   Connector ID: {config.connector_id}")
        print(f"   Name: {config.connector_name}")
        print(f"   Type: {config.connector_type}")
        print(f"   Customer: {config.customer_id}")
        print(f"   Enabled: {config.is_enabled}")
        print(f"   Created: {config.created_at}")
        
        return config
        
    except Exception as e:
        print(f"❌ Error creating connector: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_greenhouse_connector()

