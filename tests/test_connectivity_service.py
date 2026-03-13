"""
Test script for connectivity service.

This script demonstrates the connectivity check functionality
for the BI pipeline data sources.
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.services.connectivity_service import ConnectivityService
from src.core.logging import get_logger

logger = get_logger(__name__, component="connectivity.test")


def test_connectivity_service():
    """Test the connectivity service with a sample customer."""
    
    print("\n" + "="*80)
    print("🔍 Testing Data Source Connectivity Service")
    print("="*80 + "\n")
    
    # Initialize service
    service = ConnectivityService()
    
    # Test customer ID (use your actual customer ID)
    customer_id = "local-dev"
    
    print(f"Testing connectivity for customer: {customer_id}\n")
    
    # Test HR Database connectivity
    print("📊 Checking HR Database connectivity...")
    hr_result = service.check_hr_database_connectivity(customer_id)
    print(f"   Status: {hr_result['status']}")
    print(f"   Message: {hr_result['message']}")
    print(f"   Available: {hr_result['available']}")
    if 'has_customer_data' in hr_result:
        print(f"   Has Customer Data: {hr_result['has_customer_data']}")
    print()
    
    # Test Vector Index connectivity
    print("📚 Checking Vector Index connectivity...")
    vector_result = service.check_vector_index_connectivity(customer_id)
    print(f"   Status: {vector_result['status']}")
    print(f"   Message: {vector_result['message']}")
    print(f"   Available: {vector_result['available']}")
    if 'details' in vector_result and 'total_vectors' in vector_result['details']:
        print(f"   Total Vectors: {vector_result['details']['total_vectors']}")
    print()
    
    # Test all data sources
    print("🌐 Checking all data sources...")
    all_results = service.check_all_data_sources(customer_id)
    
    print("\n" + "-"*80)
    print("Summary:")
    print("-"*80)
    
    for source_name, result in all_results.items():
        status_icon = "✅" if result['status'] == 'healthy' else "❌"
        print(f"{status_icon} {source_name.replace('_', ' ').title()}: {result['status']}")
        print(f"   {result['message']}")
    
    print("\n" + "="*80)
    summary = service.get_connectivity_summary(all_results)
    print(f"Overall: {summary}")
    print("="*80 + "\n")
    
    # Return results for programmatic use
    return all_results


def test_connectivity_with_different_customers():
    """Test connectivity with multiple customer IDs."""
    
    print("\n" + "="*80)
    print("🔍 Testing Multiple Customer IDs")
    print("="*80 + "\n")
    
    service = ConnectivityService()
    
    # Test with different customer IDs
    test_customers = ["local-dev", "caylent", "eliza"]
    
    for customer_id in test_customers:
        print(f"\nTesting customer: {customer_id}")
        print("-" * 40)
        
        results = service.check_all_data_sources(customer_id)
        
        # Quick summary
        hr_status = results['hr_database']['status']
        vector_status = results['vector_index']['status']
        
        print(f"  HR Database: {hr_status}")
        print(f"  Vector Index: {vector_status}")
        
        if results['hr_database'].get('has_customer_data'):
            print(f"  ✓ Has HR data")
        else:
            print(f"  ⚠ No HR data found")


if __name__ == "__main__":
    print("\n🚀 Starting Connectivity Service Tests\n")
    
    try:
        # Run main test
        results = test_connectivity_service()
        
        # Optionally test multiple customers
        # test_connectivity_with_different_customers()
        
        print("\n✅ Tests completed successfully!\n")
        
        # Exit with appropriate code
        all_healthy = all(r['status'] == 'healthy' for r in results.values())
        sys.exit(0 if all_healthy else 1)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

