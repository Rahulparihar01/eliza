"""
Vector Index Configuration Test

Verifies that all components are using the correct FAISS index location
from centralized configuration.
"""
import json
import asyncio
from pathlib import Path

from src.core.config import get_settings
from src.services.vector_service import VectorService
from src.crewai_custom_tools import DocumentSearchTool


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"📋 {title}")
    print("=" * 80 + "\n")


def test_configuration():
    """Test that all components reference the same vector index configuration"""
    
    print_section("CENTRALIZED CONFIGURATION")
    
    settings = get_settings()
    
    print("Vector Index Configuration from settings:")
    print(f"  • vector_index_directory: {settings.vector_index_directory}")
    print(f"  • embedding_model: {settings.embedding_model}")
    print(f"  • embedding_dimension: {settings.embedding_dimension}")
    print(f"  • faiss_index_type: {settings.faiss_index_type}")
    print(f"  • data_directory: {settings.data_directory}")
    
    # Environment variables
    import os
    print("\nEnvironment Variables (if set):")
    print(f"  • VECTOR_INDEX_DIRECTORY: {os.getenv('VECTOR_INDEX_DIRECTORY', 'Not set (using default)')}")
    print(f"  • EMBEDDING_MODEL: {os.getenv('EMBEDDING_MODEL', 'Not set (using default)')}")
    
    print_section("VECTOR SERVICE CONFIGURATION")
    
    vector_service = VectorService()
    
    print("VectorService paths:")
    print(f"  • vector_dir: {vector_service.vector_dir}")
    print(f"  • index_file: {vector_service.index_file}")
    print(f"  • mapping_file: {vector_service.mapping_file}")
    print(f"  • embedding_model_name: {vector_service.embedding_model_name}")
    print(f"  • embedding_dimension: {vector_service.embedding_dimension}")
    
    print("\nFile System Check:")
    print(f"  • vector_dir exists: {vector_service.vector_dir.exists()}")
    print(f"  • index_file exists: {vector_service.index_file.exists()}")
    print(f"  • mapping_file exists: {vector_service.mapping_file.exists()}")
    
    if vector_service.index_file.exists():
        size_mb = vector_service.index_file.stat().st_size / (1024 * 1024)
        print(f"  • index_file size: {size_mb:.2f} MB")
    
    if vector_service.mapping_file.exists():
        with open(vector_service.mapping_file, 'r') as f:
            mapping = json.load(f)
            print(f"  • mapping entries: {len(mapping)}")
    
    print_section("DOCUMENT SEARCH TOOL CONFIGURATION")
    
    # Create DocumentSearchTool instance
    doc_search_tool = DocumentSearchTool(
        customer_id='eliza',
        limit=10,
        similarity_threshold=0.7
    )
    
    print("DocumentSearchTool configuration:")
    print(f"  • customer_id: {doc_search_tool.customer_id}")
    print(f"  • limit: {doc_search_tool.limit}")
    print(f"  • similarity_threshold: {doc_search_tool.similarity_threshold}")
    print(f"  • _vector_service type: {type(doc_search_tool._vector_service).__name__}")
    
    print("\nDocumentSearchTool → VectorService paths:")
    print(f"  • vector_dir: {doc_search_tool._vector_service.vector_dir}")
    print(f"  • index_file: {doc_search_tool._vector_service.index_file}")
    
    print_section("INDEX STATISTICS")
    
    async def get_stats():
        return await vector_service.get_index_stats()
    
    stats = asyncio.run(get_stats())
    
    print("FAISS Index Stats:")
    print(f"  • total_vectors: {stats['total_vectors']}")
    print(f"  • embedding_dimension: {stats['embedding_dimension']}")
    print(f"  • embedding_model: {stats['embedding_model']}")
    print(f"  • index_type: {stats['index_type']}")
    print(f"  • index_file_exists: {stats['index_file_exists']}")
    print(f"  • mapping_file_exists: {stats['mapping_file_exists']}")
    
    print_section("CONFIGURATION VERIFICATION")
    
    # Verify all components use the same paths
    checks = []
    
    # Check 1: Settings matches VectorService
    check1 = Path(settings.vector_index_directory) == vector_service.vector_dir
    checks.append(("Settings → VectorService paths match", check1))
    
    # Check 2: VectorService matches DocumentSearchTool
    check2 = vector_service.vector_dir == doc_search_tool._vector_service.vector_dir
    checks.append(("VectorService → DocumentSearchTool paths match", check2))
    
    # Check 3: Embedding models match
    check3 = (settings.embedding_model == vector_service.embedding_model_name == 
              doc_search_tool._vector_service.embedding_model_name)
    checks.append(("Embedding models match across all components", check3))
    
    # Check 4: Embedding dimensions match
    check4 = (settings.embedding_dimension == vector_service.embedding_dimension == 
              doc_search_tool._vector_service.embedding_dimension)
    checks.append(("Embedding dimensions match across all components", check4))
    
    # Check 5: Index files are consistent
    check5 = (vector_service.index_file == doc_search_tool._vector_service.index_file)
    checks.append(("Index file paths are consistent", check5))
    
    print("Configuration Checks:")
    all_passed = True
    for check_name, result in checks:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False
    
    print_section("TEST SUMMARY")
    
    if all_passed:
        print("🎉 SUCCESS! All components correctly reference the centralized configuration.")
        print()
        print("Configuration chain:")
        print("  config.py (vector_index_directory)")
        print("       ↓")
        print("  VectorService (self.settings.vector_index_directory)")
        print("       ↓")
        print("  DocumentSearchTool (_vector_service.vector_dir)")
        print("       ↓")
        print(f"  {vector_service.index_file}")
        print()
        print("All components are properly configured! ✨")
        return True
    else:
        print("⚠️  CONFIGURATION MISMATCH DETECTED!")
        print()
        print("Some components are not using the centralized configuration.")
        print("Please review the failed checks above.")
        return False


if __name__ == "__main__":
    success = test_configuration()
    exit(0 if success else 1)

