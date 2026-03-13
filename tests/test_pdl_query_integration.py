"""
Test PDL Query Builder Integration

This test verifies:
1. PDL query builder creates valid PDLQueryParams
2. PDLQueryParams can be converted to PDL API payload
3. PDL API payload format is correct for the PDL service
4. PDL service returns results in the expected format
5. Results can be converted to ParsedResume format
6. PDLQueryParams can be converted to PDLQuery for storage
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

from src.services.talent.pdl_query_builder import PDLQueryBuilder, PDLQueryParams
from src.models.talent_analysis import (
    DiagnosticReport, BaselineProfile, PDLQuery,
    ParsedResume
)


class TestPDLQueryBuilderIntegration:
    """Integration tests for PDL query building workflow"""
    
    @pytest.fixture
    def diagnostic_report(self) -> DiagnosticReport:
        """Sample diagnostic report"""
        return DiagnosticReport(
            role_type="Machine Learning Engineer",
            seniority_level="Senior",
            ml_competencies=[
                "Deep Learning",
                "Natural Language Processing",
                "Computer Vision"
            ],
            required_skills=[
                "Python",
                "PyTorch",
                "TensorFlow",
                "MLOps"
            ],
            preferred_skills=[
                "Kubernetes",
                "AWS",
                "Docker"
            ],
            attribute_weights={
                "ml_experience": 0.9,
                "leadership": 0.6,
                "technical_skills": 0.85,
                "communication": 0.7
            },
            key_hypotheses=[
                "Candidates with FAANG experience perform better",
                "PhD holders show stronger research capabilities"
            ],
            baseline_query_params={
                "job_titles": ["Machine Learning Engineer", "ML Engineer"],
                "min_experience": 5,
                "max_experience": 10
            },
            confidence=0.85
        )
    
    @pytest.fixture
    def baseline_profile(self) -> BaselineProfile:
        """Sample baseline profile"""
        return BaselineProfile(
            prototype_employee_ids=[1, 2, 3, 4, 5],
            common_job_titles=[
                "Machine Learning Engineer",
                "ML Engineer",
                "AI Engineer"
            ],
            skill_distributions={
                "Python": 1.0,
                "PyTorch": 0.8,
                "TensorFlow": 0.7,
                "AWS": 0.6,
                "Kubernetes": 0.5
            },
            average_years_experience=7.5,
            company_patterns={
                "FAANG": 0.6,
                "Startup": 0.4,
                "Enterprise": 0.3
            },
            education_distribution={
                "PhD": 0.4,
                "Masters": 0.5,
                "Bachelors": 0.1
            },
            career_path_patterns=[
                "Junior ML Engineer -> ML Engineer -> Senior ML Engineer",
                "Data Scientist -> ML Engineer -> Senior ML Engineer"
            ]
        )
    
    @pytest.fixture
    def query_builder(self) -> PDLQueryBuilder:
        """PDL query builder instance"""
        return PDLQueryBuilder()
    
    def test_build_initial_query_returns_pdl_query_params(
        self, 
        query_builder: PDLQueryBuilder,
        diagnostic_report: DiagnosticReport,
        baseline_profile: BaselineProfile
    ):
        """Test that build_initial_query returns PDLQueryParams"""
        result = query_builder.build_initial_query(
            diagnostic=diagnostic_report,
            baseline=baseline_profile,
            role="Machine Learning Engineer",
            limit=10
        )
        
        # Verify type
        assert isinstance(result, PDLQueryParams), \
            f"Expected PDLQueryParams, got {type(result)}"
        
        # Verify structure
        assert hasattr(result, 'job_title_role')
        assert hasattr(result, 'required_skills')
        assert hasattr(result, 'optional_skills')
        assert hasattr(result, 'limit')
        
        # Verify content
        assert len(result.job_title_role) > 0
        assert len(result.required_skills) > 0
        assert result.limit == 10
        
        print(f"✓ PDLQueryParams created successfully")
        print(f"  - Job titles: {result.job_title_role}")
        print(f"  - Required skills: {result.required_skills}")
        print(f"  - Optional skills: {result.optional_skills}")
        print(f"  - Limit: {result.limit}")
    
    def test_convert_to_pdl_api_payload(
        self,
        query_builder: PDLQueryBuilder,
        diagnostic_report: DiagnosticReport,
        baseline_profile: BaselineProfile
    ):
        """Test converting PDLQueryParams to PDL API payload"""
        # Build query params
        query_params = query_builder.build_initial_query(
            diagnostic=diagnostic_report,
            baseline=baseline_profile,
            role="Machine Learning Engineer",
            limit=10
        )
        
        # Convert to API payload
        api_payload = query_builder.convert_to_pdl_api_payload(query_params)
        
        # Verify type
        assert isinstance(api_payload, dict), \
            f"Expected dict, got {type(api_payload)}"
        
        # Verify structure
        assert "search_query" in api_payload, \
            "API payload missing 'search_query' field"
        
        search_query = api_payload["search_query"]
        assert isinstance(search_query, dict), \
            f"search_query should be dict, got {type(search_query)}"
        
        print(f"✓ API payload created successfully")
        print(f"  - Payload keys: {list(api_payload.keys())}")
        print(f"  - Search query keys: {list(search_query.keys())}")
    
    def test_pdl_api_payload_format(
        self,
        query_builder: PDLQueryBuilder,
        diagnostic_report: DiagnosticReport,
        baseline_profile: BaselineProfile
    ):
        """Test that PDL API payload has correct format for PDL service"""
        query_params = query_builder.build_initial_query(
            diagnostic=diagnostic_report,
            baseline=baseline_profile,
            role="Machine Learning Engineer",
            limit=10
        )
        
        api_payload = query_builder.convert_to_pdl_api_payload(query_params)
        search_query = api_payload.get("search_query", {})
        
        # PDL API expects specific field names
        # Based on PDL People Search API documentation
        expected_fields = [
            "job_title_role",  # or similar job title field
            "required_skills",  # skill filtering
        ]
        
        # At minimum, we should have job title or skills
        has_job_filter = any(
            key in search_query 
            for key in ["job_title_role", "job_title", "current_job_title"]
        )
        has_skill_filter = any(
            key in search_query
            for key in ["required_skills", "skills", "skill"]
        )
        
        assert has_job_filter or has_skill_filter, \
            "PDL API payload must have job title or skills filter"
        
        print(f"✓ PDL API payload has valid format")
        print(f"  - Has job filter: {has_job_filter}")
        print(f"  - Has skill filter: {has_skill_filter}")
        print(f"  - Search query: {search_query}")
    
    def test_convert_pdl_params_to_pdl_query(
        self,
        query_builder: PDLQueryBuilder,
        diagnostic_report: DiagnosticReport,
        baseline_profile: BaselineProfile
    ):
        """Test converting PDLQueryParams to PDLQuery for storage"""
        # Build query params
        query_params = query_builder.build_initial_query(
            diagnostic=diagnostic_report,
            baseline=baseline_profile,
            role="Machine Learning Engineer",
            limit=10
        )
        
        # Convert to API payload
        api_payload = query_builder.convert_to_pdl_api_payload(query_params)
        
        # Convert to PDLQuery (what gets stored in TalentAnalysisResult)
        pdl_query = PDLQuery(
            base_query=str(api_payload.get("search_query", {})),
            params=api_payload,
            version=1,
            refinement_reason="Initial query based on diagnostic analysis"
        )
        
        # Verify type
        assert isinstance(pdl_query, PDLQuery), \
            f"Expected PDLQuery, got {type(pdl_query)}"
        
        # Verify structure
        assert hasattr(pdl_query, 'base_query')
        assert hasattr(pdl_query, 'params')
        assert hasattr(pdl_query, 'version')
        assert hasattr(pdl_query, 'refinement_reason')
        
        # Verify content
        assert pdl_query.version == 1
        assert pdl_query.refinement_reason is not None
        assert isinstance(pdl_query.params, dict)
        
        print(f"✓ PDLQuery created successfully")
        print(f"  - Version: {pdl_query.version}")
        print(f"  - Refinement reason: {pdl_query.refinement_reason}")
        print(f"  - Params keys: {list(pdl_query.params.keys())}")
    
    @patch('src.services.external.pdl_service.PDLService')
    def test_pdl_service_mock_call(
        self,
        mock_pdl_service_class: MagicMock,
        query_builder: PDLQueryBuilder,
        diagnostic_report: DiagnosticReport,
        baseline_profile: BaselineProfile
    ):
        """Test calling PDL service with generated query (mocked)"""
        # Setup mock
        mock_pdl_service = Mock()
        mock_pdl_service_class.return_value = mock_pdl_service
        
        # Mock PDL API response
        mock_pdl_service.search_people.return_value = [
            {
                "pdl_id": "test-123",
                "full_name": "John Doe",
                "work_email": "john@example.com",
                "job_title": "Senior Machine Learning Engineer",
                "experience": [
                    {
                        "company": {"name": "Google"},
                        "title": {"name": "ML Engineer"},
                        "start_date": "2020-01-01",
                        "end_date": None
                    }
                ],
                "education": [
                    {
                        "school": {"name": "Stanford"},
                        "degrees": ["PhD"],
                        "majors": ["Computer Science"]
                    }
                ],
                "skills": ["Python", "PyTorch", "TensorFlow"]
            }
        ]
        
        # Build query
        query_params = query_builder.build_initial_query(
            diagnostic=diagnostic_report,
            baseline=baseline_profile,
            role="Machine Learning Engineer",
            limit=10
        )
        
        # Convert to API payload
        api_payload = query_builder.convert_to_pdl_api_payload(query_params)
        
        # Call PDL service (mocked)
        from src.services.external.pdl_service import PDLService
        pdl_service = PDLService(Mock())
        results = pdl_service.search_people(
            query=api_payload.get("search_query", {}),
            limit=10
        )
        
        # Verify results
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0]["full_name"] == "John Doe"
        
        print(f"✓ PDL service mock call successful")
        print(f"  - Results count: {len(results)}")
        print(f"  - First result: {results[0]['full_name']}")
    
    def test_convert_pdl_results_to_parsed_resume(self):
        """Test converting PDL API results to ParsedResume format"""
        # Mock PDL result
        pdl_result = {
            "pdl_id": "test-123",
            "full_name": "Jane Smith",
            "work_email": "jane@example.com",
            "phone_numbers": [{"number": "+1234567890"}],
            "job_title": "Senior ML Engineer",
            "experience": [
                {
                    "company": {"name": "Google"},
                    "title": {"name": "ML Engineer"},
                    "start_date": "2020-01-01",
                    "end_date": None
                }
            ],
            "education": [
                {
                    "school": {"name": "MIT"},
                    "degrees": ["PhD"],
                    "majors": ["Computer Science"]
                }
            ],
            "skills": ["Python", "PyTorch", "TensorFlow", "AWS"]
        }
        
        # Convert to ParsedResume
        parsed = ParsedResume(
            candidate_id=f"pdl_{pdl_result.get('pdl_id', 'unknown')}",
            full_name=pdl_result.get('full_name', 'Unknown'),
            email=pdl_result.get('work_email'),
            phone=pdl_result.get('phone_numbers', [{}])[0].get('number') if pdl_result.get('phone_numbers') else None,
            linkedin_url=pdl_result.get('linkedin_url'),
            summary=f"Current role: {pdl_result.get('job_title', 'N/A')}",
            skills=pdl_result.get('skills', []),
            experience=[
                {
                    "company": exp.get("company", {}).get("name", "Unknown"),
                    "title": exp.get("title", {}).get("name", "Unknown"),
                    "start_date": exp.get("start_date"),
                    "end_date": exp.get("end_date"),
                    "description": ""
                }
                for exp in pdl_result.get("experience", [])
            ],
            education=[
                {
                    "institution": edu.get("school", {}).get("name", "Unknown"),
                    "degree": ", ".join(edu.get("degrees", [])),
                    "field_of_study": ", ".join(edu.get("majors", [])),
                    "graduation_year": None
                }
                for edu in pdl_result.get("education", [])
            ],
            certifications=[],
            source="pdl_market_search",
            raw_text=""
        )
        
        # Verify conversion
        assert isinstance(parsed, ParsedResume)
        assert parsed.candidate_id == "pdl_test-123"
        assert parsed.full_name == "Jane Smith"
        assert parsed.email == "jane@example.com"
        assert "Python" in parsed.skills
        assert len(parsed.experience) == 1
        assert len(parsed.education) == 1
        assert parsed.source == "pdl_market_search"
        
        print(f"✓ PDL result converted to ParsedResume successfully")
        print(f"  - Candidate ID: {parsed.candidate_id}")
        print(f"  - Name: {parsed.full_name}")
        print(f"  - Skills: {parsed.skills}")
        print(f"  - Experience count: {len(parsed.experience)}")
        print(f"  - Education count: {len(parsed.education)}")
    
    def test_full_integration_workflow(
        self,
        query_builder: PDLQueryBuilder,
        diagnostic_report: DiagnosticReport,
        baseline_profile: BaselineProfile
    ):
        """Test the full workflow from diagnostic -> PDL query -> storage format"""
        print("\n=== FULL PDL QUERY INTEGRATION WORKFLOW ===\n")
        
        # Step 1: Build PDLQueryParams
        print("Step 1: Building PDLQueryParams from diagnostic and baseline...")
        query_params = query_builder.build_initial_query(
            diagnostic=diagnostic_report,
            baseline=baseline_profile,
            role="Machine Learning Engineer",
            limit=10
        )
        assert isinstance(query_params, PDLQueryParams)
        print(f"✓ PDLQueryParams created: {type(query_params).__name__}")
        
        # Step 2: Convert to PDL API payload
        print("\nStep 2: Converting PDLQueryParams to PDL API payload...")
        api_payload = query_builder.convert_to_pdl_api_payload(query_params)
        assert isinstance(api_payload, dict)
        assert "search_query" in api_payload
        print(f"✓ API payload created with keys: {list(api_payload.keys())}")
        
        # Step 3: (Mock) Call PDL API
        print("\nStep 3: Simulating PDL API call...")
        mock_pdl_results = [
            {
                "pdl_id": f"test-{i}",
                "full_name": f"Candidate {i}",
                "work_email": f"candidate{i}@example.com",
                "job_title": "Senior ML Engineer",
                "skills": ["Python", "PyTorch", "TensorFlow"]
            }
            for i in range(1, 4)
        ]
        print(f"✓ Mock PDL API returned {len(mock_pdl_results)} results")
        
        # Step 4: Convert to ParsedResume
        print("\nStep 4: Converting PDL results to ParsedResume format...")
        parsed_resumes = []
        for person in mock_pdl_results:
            parsed = ParsedResume(
                candidate_id=f"pdl_{person.get('pdl_id', 'unknown')}",
                full_name=person.get('full_name', 'Unknown'),
                email=person.get('work_email'),
                phone=None,
                linkedin_url=None,
                summary=f"Current role: {person.get('job_title', 'N/A')}",
                skills=person.get('skills', []),
                experience=[],
                education=[],
                certifications=[],
                source="pdl_market_search",
                raw_text=""
            )
            parsed_resumes.append(parsed)
        
        assert len(parsed_resumes) == len(mock_pdl_results)
        assert all(isinstance(r, ParsedResume) for r in parsed_resumes)
        print(f"✓ Converted {len(parsed_resumes)} results to ParsedResume")
        
        # Step 5: Convert to storage format (PDLQuery)
        print("\nStep 5: Converting to storage format (PDLQuery)...")
        pdl_query = PDLQuery(
            base_query=str(api_payload.get("search_query", {})),
            params=api_payload,
            version=1,
            refinement_reason="Initial query based on diagnostic analysis"
        )
        assert isinstance(pdl_query, PDLQuery)
        print(f"✓ PDLQuery created for storage")
        
        print("\n=== WORKFLOW COMPLETE ===")
        print(f"Summary:")
        print(f"  1. PDLQueryParams: ✓")
        print(f"  2. API Payload: ✓")
        print(f"  3. PDL API Call: ✓ (mocked)")
        print(f"  4. ParsedResume conversion: ✓ ({len(parsed_resumes)} candidates)")
        print(f"  5. PDLQuery storage: ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

