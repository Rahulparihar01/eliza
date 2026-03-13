"""
Master Test Runner for Data Ingestion Layer

Runs all test suites in sequence:
1. Unit Tests - Individual components (rate limiter, connector, transformer)
2. Integration Tests - Full pipeline (end-to-end)
3. API Tests - REST endpoints (16 endpoints)

Run with: python3 tests/run_all_ingestion_tests.py
"""
import sys
import os
from pathlib import Path
import subprocess
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 100)
    print(f"  {title}")
    print("=" * 100 + "\n")


def print_section(title):
    """Print a formatted section."""
    print("\n" + "-" * 100)
    print(f"  {title}")
    print("-" * 100 + "\n")


def run_test_file(test_file, description):
    """Run a single test file and return success status."""
    print_section(f"Running: {description}")
    print(f"File: {test_file}\n")
    
    try:
        # Run the test file
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=False,
            text=True,
            cwd=str(project_root)
        )
        
        if result.returncode == 0:
            print(f"\n✅ {description} - PASSED")
            return True
        else:
            print(f"\n❌ {description} - FAILED (exit code: {result.returncode})")
            return False
            
    except Exception as e:
        print(f"\n❌ {description} - ERROR: {e}")
        return False


def main():
    """Run all test suites."""
    start_time = datetime.now()
    
    print_header("DATA INGESTION LAYER - COMPREHENSIVE TEST SUITE")
    
    print("⚠️  IMPORTANT NOTES:")
    print("   • These tests use REAL API calls to People Data Labs")
    print("   • All queries are limited to 1 record to minimize costs")
    print("   • API authentication may be required for some tests")
    print("   • Tests require database connection (PostgreSQL)")
    print("   • Estimated runtime: 2-5 minutes")
    print()
    
    input("Press ENTER to start tests (or Ctrl+C to cancel)...")
    
    # Define test suites
    test_suites = [
        {
            "file": "tests/test_ingestion_unit_tests.py",
            "description": "Unit Tests (Components)",
            "sections": [
                "Rate Limiter",
                "PDL Connector",
                "PDL Transformer",
                "Config Validation"
            ]
        },
        {
            "file": "tests/test_ingestion_pipeline_comprehensive.py",
            "description": "Integration Tests (Full Pipeline)",
            "sections": [
                "Connector Discovery",
                "Config Validation",
                "Connection Testing",
                "Cost Estimation",
                "Configuration CRUD",
                "Sync Execution",
                "Data Transformation",
                "Deduplication",
                "Query Versioning",
                "Statistics"
            ]
        },
        {
            "file": "tests/test_ingestion_api_endpoints.py",
            "description": "API Tests (REST Endpoints)",
            "sections": [
                "List Connector Types",
                "Validate Config",
                "Test Connection",
                "Estimate Cost",
                "Create Configuration",
                "List Configurations",
                "Get Configuration",
                "Update Configuration",
                "Trigger Sync",
                "List Sync Runs",
                "Get Sync Run",
                "Get Telemetry",
                "List PDL Persons",
                "Get Statistics",
                "Delete Configuration"
            ]
        }
    ]
    
    # Run each test suite
    results = []
    
    for suite in test_suites:
        print_section(f"Test Suite: {suite['description']}")
        print(f"Testing: {', '.join(suite['sections'][:3])}...")
        if len(suite['sections']) > 3:
            print(f"         and {len(suite['sections']) - 3} more\n")
        
        success = run_test_file(suite["file"], suite["description"])
        results.append({
            "suite": suite["description"],
            "success": success
        })
        
        if not success:
            print(f"\n⚠️  WARNING: {suite['description']} failed, but continuing with remaining tests...")
    
    # Print summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print_header("TEST SUITE SUMMARY")
    
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    
    print(f"Total Test Suites: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏱️  Duration: {duration:.1f} seconds")
    print()
    
    # Detailed results
    print("Detailed Results:")
    for i, result in enumerate(results, 1):
        status = "✅ PASS" if result["success"] else "❌ FAIL"
        print(f"  {i}. {status} - {result['suite']}")
    
    print()
    
    if failed == 0:
        print("=" * 100)
        print("🎉 ALL TEST SUITES PASSED! 🎉")
        print("=" * 100)
        print()
        print("✅ Your data ingestion layer is working correctly!")
        print("✅ All components tested: Connector, Transformer, Service, API")
        print("✅ Pipeline validated: Extract → Stage → Transform → Store")
        print()
        return 0
    else:
        print("=" * 100)
        print(f"⚠️  {failed} TEST SUITE(S) FAILED")
        print("=" * 100)
        print()
        print("Please review the errors above and:")
        print("  1. Check database connection (PostgreSQL running?)")
        print("  2. Verify API keys (PDL API key valid?)")
        print("  3. Check authentication (API tests may need auth headers)")
        print("  4. Review logs for specific error messages")
        print()
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

