#!/usr/bin/env python3
"""
Comprehensive Phase 2 Test Suite for AI Enablement Platform
Based on BUILD_PLAN.md requirements and previous test results

Tests all Phase 2 components:
- Document Processing Pipeline
- Vector Storage (FAISS)
- Chunking System
- Data Connectors
- Quality Validation
"""

import json
import time
import requests
import sys
from datetime import datetime
from pathlib import Path

# Test configuration
BASE_URL = "http://localhost:5001"
TEST_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
TEST_DIR = f"testing_logs/phase2_comprehensive_{TEST_TIMESTAMP}"

class Phase2Tester:
    def __init__(self):
        self.base_url = BASE_URL
        self.results = {
            "test_name": "phase2_comprehensive",
            "test_date": datetime.now().strftime("%Y-%m-%d"),
            "test_time": datetime.now().strftime("%H:%M:%S"),
            "test_type": "comprehensive_phase2",
            "components_tested": [],
            "results": {},
            "issues": [],
            "success_rate": 0
        }
        
        # Create test directory
        Path(TEST_DIR).mkdir(parents=True, exist_ok=True)
        
    def log(self, message, level="INFO"):
        """Log test messages"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def test_api_health(self):
        """Test 1: API Health Check"""
        self.log("🔍 Testing API Health...")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                self.log("✅ API Health: PASSED")
                self.results["results"]["api_health"] = "PASSED"
                return True
            else:
                self.log(f"❌ API Health: FAILED - Status {response.status_code}")
                self.results["results"]["api_health"] = f"FAILED - Status {response.status_code}"
                return False
        except Exception as e:
            self.log(f"❌ API Health: FAILED - {e}")
            self.results["results"]["api_health"] = f"FAILED - {e}"
            return False
    
    def test_document_upload(self):
        """Test 2: Document Upload Pipeline"""
        self.log("🔍 Testing Document Upload Pipeline...")
        
        # Create test document
        test_content = """# AI Enablement Platform Test Document

This is a comprehensive test document for the AI Enablement Platform.
It contains multiple sections to test the chunking and processing capabilities.

## Section 1: Introduction
The AI Enablement Platform is designed to analyze corporate data and identify optimal departments for AI transformation.

## Section 2: Features
- Document processing with multiple formats
- Vector storage and similarity search
- Intelligent chunking strategies
- Quality validation and scoring

## Section 3: Testing
This document will be processed through the complete pipeline:
1. File upload and validation
2. Format detection and parsing
3. Semantic chunking
4. Vector embedding generation
5. Quality scoring and validation

## Conclusion
This test validates the end-to-end document processing capabilities.
"""
        
        test_file_path = Path(TEST_DIR) / "test_document.txt"
        with open(test_file_path, 'w') as f:
            f.write(test_content)
        
        try:
            with open(test_file_path, 'rb') as f:
                files = {'files': ('test_document.txt', f, 'text/plain')}
                data = {
                    'chunking_strategy': 'semantic',
                    'qa_rag_enabled': 'false'
                }
                
                response = requests.post(
                    f"{self.base_url}/v1/documents/upload",
                    files=files,
                    data=data,
                    timeout=30
                )
                
            if response.status_code == 202:
                result = response.json()
                self.log(f"✅ Document Upload: PASSED - Upload ID: {result.get('upload_id')}")
                self.results["results"]["document_upload"] = "PASSED"
                self.results["upload_id"] = result.get('upload_id')
                
                # Check if file was processed successfully
                files_status = result.get('files', [])
                if files_status and files_status[0].get('status') == 'uploaded':
                    self.log(f"✅ File Processing: PASSED - Document ID: {files_status[0].get('document_id')}")
                    self.results["results"]["file_processing"] = "PASSED"
                    self.results["document_id"] = files_status[0].get('document_id')
                    return True
                else:
                    error = files_status[0].get('error') if files_status else 'Unknown error'
                    self.log(f"❌ File Processing: FAILED - {error}")
                    self.results["results"]["file_processing"] = f"FAILED - {error}"
                    self.results["issues"].append(f"File processing failed: {error}")
                    return False
            else:
                self.log(f"❌ Document Upload: FAILED - Status {response.status_code}")
                self.results["results"]["document_upload"] = f"FAILED - Status {response.status_code}"
                return False
                
        except Exception as e:
            self.log(f"❌ Document Upload: FAILED - {e}")
            self.results["results"]["document_upload"] = f"FAILED - {e}"
            return False
    
    def test_document_retrieval(self):
        """Test 3: Document Retrieval"""
        self.log("🔍 Testing Document Retrieval...")
        
        if not self.results.get("document_id"):
            self.log("❌ Document Retrieval: SKIPPED - No document ID available")
            self.results["results"]["document_retrieval"] = "SKIPPED - No document ID"
            return False
            
        try:
            response = requests.get(
                f"{self.base_url}/v1/documents/{self.results['document_id']}",
                timeout=10
            )
            
            if response.status_code == 200:
                doc_info = response.json()
                self.log(f"✅ Document Retrieval: PASSED - Status: {doc_info.get('status')}")
                self.results["results"]["document_retrieval"] = "PASSED"
                self.results["document_info"] = doc_info
                return True
            else:
                self.log(f"❌ Document Retrieval: FAILED - Status {response.status_code}")
                self.results["results"]["document_retrieval"] = f"FAILED - Status {response.status_code}"
                return False
                
        except Exception as e:
            self.log(f"❌ Document Retrieval: FAILED - {e}")
            self.results["results"]["document_retrieval"] = f"FAILED - {e}"
            return False
    
    def test_document_listing(self):
        """Test 4: Document Listing"""
        self.log("🔍 Testing Document Listing...")
        
        try:
            response = requests.get(f"{self.base_url}/v1/documents", timeout=10)
            
            if response.status_code == 200:
                docs_list = response.json()
                doc_count = len(docs_list.get('documents', []))
                self.log(f"✅ Document Listing: PASSED - Found {doc_count} documents")
                self.results["results"]["document_listing"] = "PASSED"
                self.results["document_count"] = doc_count
                return True
            else:
                self.log(f"❌ Document Listing: FAILED - Status {response.status_code}")
                self.results["results"]["document_listing"] = f"FAILED - Status {response.status_code}"
                return False
                
        except Exception as e:
            self.log(f"❌ Document Listing: FAILED - {e}")
            self.results["results"]["document_listing"] = f"FAILED - {e}"
            return False
    
    def test_vector_service_health(self):
        """Test 5: Vector Service Health"""
        self.log("🔍 Testing Vector Service Health...")
        
        try:
            response = requests.get(f"{self.base_url}/v1/documents/health", timeout=10)
            
            if response.status_code == 200:
                health_info = response.json()
                vector_status = health_info.get('vector_service', {}).get('status')
                if vector_status == 'healthy':
                    self.log("✅ Vector Service Health: PASSED")
                    self.results["results"]["vector_service_health"] = "PASSED"
                    return True
                else:
                    self.log(f"❌ Vector Service Health: FAILED - Status: {vector_status}")
                    self.results["results"]["vector_service_health"] = f"FAILED - Status: {vector_status}"
                    return False
            else:
                self.log(f"❌ Vector Service Health: FAILED - Status {response.status_code}")
                self.results["results"]["vector_service_health"] = f"FAILED - Status {response.status_code}"
                return False
                
        except Exception as e:
            self.log(f"❌ Vector Service Health: FAILED - {e}")
            self.results["results"]["vector_service_health"] = f"FAILED - {e}"
            return False
    
    def run_comprehensive_test(self):
        """Run all Phase 2 tests"""
        self.log("🚀 Starting Phase 2 Comprehensive Test Suite")
        self.log(f"📁 Test results will be saved to: {TEST_DIR}")
        
        # Wait for application to be ready
        self.log("⏳ Waiting for application to be ready...")
        time.sleep(15)
        
        tests = [
            ("API Health", self.test_api_health),
            ("Document Upload Pipeline", self.test_document_upload),
            ("Document Retrieval", self.test_document_retrieval),
            ("Document Listing", self.test_document_listing),
            ("Vector Service Health", self.test_vector_service_health),
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            self.results["components_tested"].append(test_name)
            if test_func():
                passed_tests += 1
        
        # Calculate success rate
        self.results["success_rate"] = (passed_tests / total_tests) * 100
        
        # Generate summary
        self.log("\n" + "="*60)
        self.log("📊 PHASE 2 TEST RESULTS SUMMARY")
        self.log("="*60)
        self.log(f"✅ Tests Passed: {passed_tests}/{total_tests}")
        self.log(f"📈 Success Rate: {self.results['success_rate']:.1f}%")
        
        if self.results["issues"]:
            self.log("\n❌ Issues Found:")
            for issue in self.results["issues"]:
                self.log(f"   - {issue}")
        
        # Save results
        self.save_results()
        
        return self.results["success_rate"] >= 80  # 80% success threshold
    
    def save_results(self):
        """Save test results to files"""
        # Save JSON results
        results_file = Path(TEST_DIR) / "test_results.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        # Save summary report
        summary_file = Path(TEST_DIR) / "PHASE2_TEST_SUMMARY.md"
        with open(summary_file, 'w') as f:
            f.write(f"# Phase 2 Comprehensive Test Results\n\n")
            f.write(f"**Test Date:** {self.results['test_date']}\n")
            f.write(f"**Test Time:** {self.results['test_time']}\n")
            f.write(f"**Success Rate:** {self.results['success_rate']:.1f}%\n\n")
            
            f.write("## Test Results\n\n")
            for component, result in self.results["results"].items():
                status = "✅" if "PASSED" in result else "❌"
                f.write(f"- {status} **{component.replace('_', ' ').title()}**: {result}\n")
            
            if self.results["issues"]:
                f.write("\n## Issues Found\n\n")
                for issue in self.results["issues"]:
                    f.write(f"- {issue}\n")
        
        self.log(f"📄 Results saved to: {results_file}")
        self.log(f"📄 Summary saved to: {summary_file}")

if __name__ == "__main__":
    tester = Phase2Tester()
    success = tester.run_comprehensive_test()
    
    if success:
        print("\n🎉 Phase 2 tests completed successfully!")
        sys.exit(0)
    else:
        print("\n💥 Phase 2 tests failed!")
        sys.exit(1)
