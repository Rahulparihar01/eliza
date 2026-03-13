"""
Load Caylent employees from PDL API into the database.

This script:
1. Queries PDL for all current Caylent employees
2. Transforms the data to PDLPerson records
3. Loads them into PostgreSQL
4. Optionally syncs to Elasticsearch and Neo4j
"""
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import database
from src.models.connector import ConnectorConfiguration, ConnectorType, SyncMode
from src.models.customer import Customer
from src.services.ingestion.connector_service import ConnectorService
from src.utils.encryption import encrypt_value
import json

# Configuration
PDL_API_KEY = os.getenv('PDL_API_KEY', '5bc8459782ab4964e99f96cf3638d9d9f96c9c06aac3e1fd92ddf554386cdde7')
CUSTOMER_ID = 'eliza'
CONNECTOR_ID = 'caylent_employees_loader'

def main():
    """Load Caylent employees from PDL."""
    print(f"\n{'='*70}")
    print("LOADING CAYLENT EMPLOYEES FROM PDL")
    print(f"{'='*70}\n")
    
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        # Step 1: Ensure customer exists
        print("[1/5] Checking customer...")
        customer = db.query(Customer).filter(Customer.customer_id == CUSTOMER_ID).first()
        if not customer:
            print(f"   ❌ Customer '{CUSTOMER_ID}' not found. Please create it first.")
            return
        print(f"   ✅ Customer found: {customer.name}")
        
        # Step 2: Create or get connector configuration
        print("\n[2/5] Setting up PDL connector...")
        
        # Delete existing if present
        existing = db.query(ConnectorConfiguration).filter(
            ConnectorConfiguration.connector_id == CONNECTOR_ID
        ).first()
        if existing:
            db.delete(existing)
            db.commit()
            print("   Removed existing connector")
        
        # Encrypt credentials
        credentials_dict = {"api_key": PDL_API_KEY}
        credentials_json = json.dumps(credentials_dict)
        credentials_encrypted = encrypt_value(credentials_json)
        
        # Create connector config with proper Elasticsearch query format
        config = ConnectorConfiguration(
            customer_id=CUSTOMER_ID,
            connector_id=CONNECTOR_ID,
            connector_name='Caylent Employees Loader',
            connector_type=ConnectorType.PEOPLE_DATA_LABS,
            use_shared_credentials=False,
            credentials_encrypted=credentials_encrypted,
            sync_config={
                "search_query": {
                    "job_company_name": "Caylent"
                }
            },
            sync_mode=SyncMode.FULL_REFRESH,
            is_enabled=True
        )
        db.add(config)
        db.commit()
        print(f"   ✅ Connector created: {config.connector_id}")
        
        # Step 3: Estimate cost
        print("\n[3/5] Estimating cost...")
        connector_service = ConnectorService(db)
        
        from src.services.ingestion.connectors.people_data_labs import PeopleDataLabsConnector
        pdl_connector = PeopleDataLabsConnector(
            credentials={"api_key": PDL_API_KEY},
            config={},
            customer_id=CUSTOMER_ID
        )
        
        estimated_count = pdl_connector.estimate_record_count(config.sync_config["search_query"])
        estimated_cost = estimated_count * 0.02 if estimated_count else 0
        
        print(f"   📊 Estimated records: {estimated_count}")
        print(f"   💰 Estimated cost: ${estimated_cost:.2f}")
        
        # Ask for confirmation
        if estimated_count > 100:
            response = input(f"\n   ⚠️  This will fetch {estimated_count} records (${estimated_cost:.2f}). Continue? [y/N]: ")
            if response.lower() != 'y':
                print("   ❌ Aborted by user")
                return
        
        # Step 4: Run sync
        print("\n[4/5] Running PDL sync...")
        print("   This may take a few minutes...")
        
        # Trigger sync
        sync_run = connector_service.trigger_sync(
            connector_id=config.connector_id,
            customer_id=CUSTOMER_ID,
            manual_trigger=True
        )
        
        print(f"   Sync run created: {sync_run.sync_id}")
        
        # Execute sync
        result = connector_service.execute_sync(
            connector_id=config.connector_id,
            customer_id=CUSTOMER_ID,
            sync_mode="full",
            sync_params={
                "sync_run_id": sync_run.id,
                "sync_id": sync_run.sync_id,
                "connector_type": config.connector_type,
                "sync_config": config.sync_config,
                "max_records": None  # Get all records
            },
            task_id="load_caylent_employees"
        )
        
        if result['status'] == 'completed':
            print(f"   ✅ Sync completed successfully!")
            print(f"   📦 Records extracted: {result['records_extracted']}")
            print(f"   💾 Records loaded: {result['records_loaded']}")
        else:
            print(f"   ❌ Sync failed: {result.get('error')}")
            return
        
        # Step 5: Verify data
        print("\n[5/5] Verifying loaded data...")
        
        from src.models.connector import PDLPerson
        
        # Count total Caylent employees
        total = db.query(PDLPerson).filter(
            PDLPerson.customer_id == CUSTOMER_ID,
            PDLPerson.job_company_name.ilike('%caylent%')
        ).count()
        
        print(f"   ✅ Total Caylent employees in database: {total}")
        
        # Sample some records
        samples = db.query(PDLPerson).filter(
            PDLPerson.customer_id == CUSTOMER_ID,
            PDLPerson.job_company_name.ilike('%caylent%')
        ).limit(5).all()
        
        print("\n   Sample employees:")
        for person in samples:
            print(f"   • {person.full_name or 'Unknown'} - {person.job_title or 'N/A'}")
            print(f"     Skills: {len(person.skills) if person.skills else 0} skills")
        
        # Count by role
        print("\n   Employees by role:")
        roles = db.execute("""
            SELECT job_title_role, COUNT(*) as count
            FROM pdl_persons
            WHERE customer_id = :customer_id
            AND job_company_name ILIKE '%caylent%'
            AND job_title_role IS NOT NULL
            GROUP BY job_title_role
            ORDER BY count DESC
            LIMIT 10
        """, {"customer_id": CUSTOMER_ID})
        
        for row in roles:
            print(f"   • {row.job_title_role}: {row.count}")
        
        print(f"\n{'='*70}")
        print("✅ CAYLENT EMPLOYEES LOADED SUCCESSFULLY!")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == '__main__':
    main()

