#!/usr/bin/env python3
"""
Minimal test to isolate the SQLAlchemy session binding issue
"""

import sys
import os
sys.path.append('/app')

from src.models.database import SessionLocal
from src.models.document import Document, DocumentStatus
from contextlib import contextmanager
from sqlalchemy.exc import SQLAlchemyError

@contextmanager
def get_db_session():
    """Context manager for database sessions with proper error handling"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def test_minimal_document_creation():
    """Test minimal document creation"""
    
    print("🔍 Testing minimal document creation...")
    
    try:
        with get_db_session() as db:
            print("✅ Database session created successfully")
            
            # Create minimal document
            document = Document(
                filename="test.txt",
                original_filename="test.txt",
                file_path="/app/data/test.txt",
                file_size=100,
                mime_type="text/plain",
                file_hash="test_hash",
                customer_id="local-dev",
                upload_batch_id="test_batch",
                status=DocumentStatus.UPLOADED
            )
            
            print("✅ Document object created successfully")
            
            # Add to session
            db.add(document)
            print("✅ Document added to session successfully")
            
            # Flush to get ID
            db.flush()
            print("✅ Session flushed successfully")
            
            # Get document ID
            document_id = document.id
            print(f"✅ Document ID retrieved: {document_id}")
            
            # Convert to primitive int
            document_id_int = int(document_id)
            print(f"✅ Document ID converted to int: {document_id_int}")
            
            # Transaction will be committed by context manager
            print("✅ Document creation completed successfully")
            return document_id_int
            
    except SQLAlchemyError as e:
        print(f"❌ SQLAlchemy error: {e}")
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        raise

if __name__ == "__main__":
    try:
        doc_id = test_minimal_document_creation()
        print(f"🎉 SUCCESS: Document created with ID {doc_id}")
    except Exception as e:
        print(f"💥 FAILED: {e}")
        import traceback
        traceback.print_exc()
