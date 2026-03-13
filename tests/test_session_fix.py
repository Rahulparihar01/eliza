#!/usr/bin/env python3
"""
Test script to verify SessionLocal is working after lazy initialization fix
"""

import sys
import os
sys.path.append('/app')

from contextlib import contextmanager
from src.models.database import SessionLocal
from src.models.customer import Customer
from src.models.document import Document, DocumentStatus
from src.services.document_processor import DocumentProcessor

@contextmanager
def get_db_session():
    """Test context manager for database sessions"""
    print(f"🔍 SessionLocal type: {type(SessionLocal)}")
    print(f"🔍 SessionLocal value: {SessionLocal}")
    
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

def test_session_creation():
    """Test basic session creation"""
    print("🔍 Testing session creation...")
    
    try:
        with get_db_session() as db:
            # Test a simple query
            customer_count = db.query(Customer).count()
            print(f"✅ Customer count: {customer_count}")
            
        print("✅ Session test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Session test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_document_processor_initialization():
    """Test DocumentProcessor initialization"""
    print("🔍 Testing DocumentProcessor initialization...")
    
    try:
        processor = DocumentProcessor()
        print("✅ DocumentProcessor created successfully")
        
        # Test the context manager
        with processor.get_db_session() as db:
            customer_count = db.query(Customer).count()
            print(f"✅ DocumentProcessor session works, customer count: {customer_count}")
            
        print("✅ DocumentProcessor test passed!")
        return True
        
    except Exception as e:
        print(f"❌ DocumentProcessor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Testing session fix...")
    
    # Test 1: Basic session creation
    session_ok = test_session_creation()
    
    # Test 2: DocumentProcessor initialization
    processor_ok = test_document_processor_initialization()
    
    if session_ok and processor_ok:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("💥 Some tests failed!")
        sys.exit(1)
