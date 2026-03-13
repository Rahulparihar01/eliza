#!/usr/bin/env python3
"""
Quick setup script for FileSystem connector.

Usage:
    python tests/setup_filesystem_connector.py

This script:
1. Creates a filesystem connector pointing to tests/resumes/
2. Tests the connection
3. Lists available resume files
4. Ready for talent analysis testing
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import database
from src.models.customer import Customer
from src.models.connector import ConnectorType
from src.services.ingestion.connector_service import ConnectorService
from src.services.ingestion.connectors.filesystem_connector import FileSystemConnector


def main():
    """Set up filesystem connector for testing."""
    print("\n" + "="*60)
    print("FILESYSTEM CONNECTOR SETUP")
    print("="*60)
    
    # Initialize database
    if database.SessionLocal is None:
        database.init_database()
    
    db = database.SessionLocal()
    
    try:
        # Constants
        customer_id = "test_talent_fs"
        resumes_dir = Path(__file__).parent / "resumes"
        
        print(f"\nResumes Directory: {resumes_dir}")
        
        # Check if directory exists
        if not resumes_dir.exists():
            print(f"\n❌ ERROR: Resumes directory not found: {resumes_dir}")
            print("Please create the directory and add resume files.")
            return
        
        # Count resume files
        resume_files = list(resumes_dir.glob("*.pdf"))
        print(f"Found {len(resume_files)} PDF files")
        
        if len(resume_files) == 0:
            print("\n❌ ERROR: No resume files found")
            return
        
        # Create customer if needed
        customer = db.query(Customer).filter_by(id=customer_id).first()
        if not customer:
            print(f"\nCreating test customer: {customer_id}")
            customer = Customer(
                id=customer_id,
                name="Test Talent Customer",
                contact_email="talent@test.com",
                is_active=True
            )
            db.add(customer)
            db.commit()
        
        # Check if connector already exists
        connector_service = ConnectorService(db)
        existing_connectors = db.query(
            database.BaseModel.metadata.tables['connector_configurations']
        ).filter_by(
            customer_id=customer_id,
            connector_type=ConnectorType.FILESYSTEM
        ).all()
        
        if existing_connectors:
            print(f"\n✓ FileSystem connector already exists (ID: {existing_connectors[0].id})")
            connector_id = existing_connectors[0].id
        else:
            # Create connector configuration
            print("\nCreating filesystem connector...")
            config = connector_service.create_configuration(
                customer_id=customer_id,
                connector_type=ConnectorType.FILESYSTEM,
                connector_name="Test Resume Directory",
                credentials={},  # No credentials for filesystem
                sync_config={
                    "directory_path": str(resumes_dir.resolve()),
                    "file_extensions": [".pdf", ".docx", ".txt"],
                    "recursive": False
                },
                description="Filesystem connector for testing with local resumes",
                created_by_user_id=1
            )
            
            connector_id = config.id
            print(f"✓ Created connector (ID: {connector_id})")
        
        # Test connection
        print("\nTesting connection...")
        from src.models.connector import ConnectorConfiguration
        
        config = db.query(ConnectorConfiguration).filter_by(id=connector_id).first()
        
        connector = FileSystemConnector(
            credentials={},
            config=config.sync_config,
            customer_id=customer_id
        )
        
        result = connector.check_connection()
        
        if result["status"] == "success":
            print(f"✓ Connection test passed")
            print(f"  Message: {result['message']}")
            print(f"  File count: {result['details']['file_count']}")
            print(f"  Sample files:")
            for filename in result['details']['sample_files'][:5]:
                print(f"    - {filename}")
        else:
            print(f"❌ Connection test failed: {result['message']}")
            return
        
        # Display next steps
        print("\n" + "="*60)
        print("SETUP COMPLETE")
        print("="*60)
        print(f"\nConnector ID: {connector_id}")
        print(f"Customer ID: {customer_id}")
        print(f"Resume Files: {len(resume_files)}")
        print("\nNext Steps:")
        print("1. Run end-to-end test:")
        print("   pytest tests/test_talent_intelligence_end_to_end.py -v -s")
        print("\n2. Or run sync manually:")
        print(f"   POST /api/connectors/{connector_id}/sync")
        print("\n3. Or use in Talent Intelligence flow:")
        print(f"   job_posting_id = <job_id_from_sync>")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db.close()


if __name__ == "__main__":
    main()

