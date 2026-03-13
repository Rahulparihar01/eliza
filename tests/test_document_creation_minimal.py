#!/usr/bin/env python3
"""
Minimal test to isolate the Document creation issue
"""

import sys
import os
sys.path.append('/app')

from contextlib import contextmanager
from src.models.database import SessionLocal
from src.models.customer import Customer
from src.models.document import Document, DocumentStatus, ChunkingStrategy, UploadBatch

@contextmanager
def get_db_session():
    """Test context manager for database sessions"""
    print(f"🔍 SessionLocal: {SessionLocal}")
    
    if SessionLocal is None:
        print("❌ SessionLocal is None!")
        raise ValueError("SessionLocal is None - database not initialized")
    
    session = SessionLocal()
    try:
        print(f"✅ Session created: {session}")
        yield session
        session.commit()
        print("✅ Session committed successfully")
    except Exception as e:
        print(f"❌ Session error: {e}")
        session.rollback()
        raise
    finally:
        session.close()
        print("✅ Session closed")

def test_minimal_document_creation():
    """Test minimal document creation to isolate the issue"""
    print("🔍 Testing minimal document creation...")
    
    try:
        with get_db_session() as db:
            print("✅ Session created successfully")
            
            # Check if customer exists
            customer = db.query(Customer).filter(Customer.customer_id == "local-dev").first()
            if not customer:
                print("❌ Customer local-dev not found")
                return False
            print(f"✅ Customer found: {customer.customer_id}")
            
            # Create a simple document
            print("🔍 Creating Document object...")
            document = Document(
                filename="test.txt",
                original_filename="test.txt", 
                file_path="/app/data/test.txt",
                file_size=100,
                mime_type="text/plain",
                file_hash="abc123",
                customer_id="local-dev",
                upload_batch_id="test_batch",
                source_id="test",
                chunking_strategy=ChunkingStrategy.SEMANTIC,
                chunking_config={},
                qa_rag_enabled=False,
                document_metadata={},
                status=DocumentStatus.UPLOADED
            )
            print("✅ Document object created")
            
            # Add to session
            print("🔍 Adding document to session...")
            db.add(document)
            print("✅ Document added to session")
            
            # Flush to get ID
            print("🔍 Flushing session to get ID...")
            db.flush()
            print("✅ Session flushed")
            
            # Get the ID
            print("🔍 Getting document ID...")
            document_id = document.id
            print(f"✅ Document ID: {document_id}")
            
            # Try to access other attributes
            print("🔍 Accessing document attributes...")
            print(f"  - filename: {document.filename}")
            print(f"  - customer_id: {document.customer_id}")
            print(f"  - status: {document.status}")
            print("✅ All attributes accessible")
            
            print("✅ Document creation test passed!")
            return document_id
            
    except Exception as e:
        print(f"❌ Document creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 Testing minimal document creation...")
    
    result = test_minimal_document_creation()
    
    if result:
        print(f"🎉 Test passed! Document ID: {result}")
        sys.exit(0)
    else:
        print("💥 Test failed!")
        sys.exit(1)
