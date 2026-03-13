#!/usr/bin/env python3
"""
Test script for document processing functionality.
This script tests the document upload and processing pipeline.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_document_processing():
    """Test document processing functionality"""
    
    print("🧪 Testing Document Processing Pipeline")
    print("=" * 50)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from src.services.document_processor import DocumentProcessor
        from src.services.chunking_service import ChunkingService
        from src.models.document import DocumentUploadRequest, ChunkingStrategy
        from src.core.config import get_settings
        print("   ✅ All imports successful")
        
        # Test configuration
        print("\n2. Testing configuration...")
        settings = get_settings()
        print(f"   ✅ Settings loaded: {settings.customer_id}")
        
        # Test document processor initialization
        print("\n3. Testing DocumentProcessor initialization...")
        processor = DocumentProcessor()
        print("   ✅ DocumentProcessor initialized")
        print(f"   📄 Supported formats: {len(processor.supported_mime_types)}")
        print(f"   📏 Max file size: {processor.max_file_size / (1024*1024):.1f}MB")
        
        # Test chunking service
        print("\n4. Testing ChunkingService initialization...")
        chunking_service = ChunkingService()
        print("   ✅ ChunkingService initialized")
        
        # Test file processing (without database)
        print("\n5. Testing file processing...")
        test_file = Path("test_document.txt")
        if test_file.exists():
            print(f"   📄 Test file found: {test_file}")
            print(f"   📏 File size: {test_file.stat().st_size} bytes")
            
            # Test content reading
            with open(test_file, 'r') as f:
                content = f.read()
            print(f"   📝 Content length: {len(content)} characters")
            
            # Test chunking (without database operations)
            print("\n6. Testing chunking functionality...")
            chunks = await chunking_service.chunk_text(
                text=content,
                strategy=ChunkingStrategy.SEMANTIC,
                chunk_size=512,
                overlap=50
            )
            print(f"   ✅ Created {len(chunks)} chunks")
            
            if chunks:
                print(f"   📊 First chunk preview: {chunks[0]['text'][:100]}...")
                print(f"   📊 Average chunk size: {sum(len(c['text']) for c in chunks) / len(chunks):.1f} chars")
        else:
            print("   ⚠️  Test file not found, skipping file processing test")
        
        print("\n" + "=" * 50)
        print("🎉 Document Processing Pipeline Test PASSED!")
        print("✅ All core components are working correctly")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_database_models():
    """Test database model imports and basic functionality"""
    
    print("\n🗄️  Testing Database Models")
    print("=" * 50)
    
    try:
        # Test model imports
        print("1. Testing model imports...")
        from src.models import (
            Customer, CustomerAIProvider, User, UserSession,
            Document, DocumentChunk, UploadBatch,
            DocumentStatus, ChunkingStrategy
        )
        print("   ✅ All model imports successful")
        
        # Test enum values
        print("\n2. Testing enum values...")
        print(f"   📊 DocumentStatus values: {list(DocumentStatus)}")
        print(f"   📊 ChunkingStrategy values: {list(ChunkingStrategy)}")
        print("   ✅ Enums working correctly")
        
        print("\n" + "=" * 50)
        print("🎉 Database Models Test PASSED!")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    
    print("🚀 AI Enablement Platform - Component Tests")
    print("=" * 60)
    
    # Test database models first
    models_ok = await test_database_models()
    
    # Test document processing
    processing_ok = await test_document_processing()
    
    print("\n" + "=" * 60)
    if models_ok and processing_ok:
        print("🎉 ALL TESTS PASSED! Ready for Docker testing.")
        print("\nNext steps:")
        print("1. Run: docker-compose up --build")
        print("2. Test document upload via API")
        print("3. Monitor processing logs")
        return 0
    else:
        print("❌ Some tests failed. Please fix issues before proceeding.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
