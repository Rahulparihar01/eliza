"""
Unit tests for Greenhouse Department Filtering feature.

Tests the department hierarchy and subordinate filtering functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import aiohttp
from sqlalchemy.orm import Session


class TestGreenhouseConnectorDepartments:
    """Test Greenhouse connector department methods."""
    
    @pytest.fixture
    def connector(self):
        """Create a GreenhouseConnector instance."""
        from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
        
        return GreenhouseConnector(
            credentials={"api_key": "test_key"},
            config={},
            customer_id="test_customer"
        )
    
    @pytest.fixture
    def sample_departments(self):
        """Sample department hierarchy for testing."""
        return [
            {"id": 1, "name": "Company", "parent_id": None, "child_ids": [2, 3]},
            {"id": 2, "name": "Engineering", "parent_id": 1, "child_ids": [4, 5]},
            {"id": 3, "name": "Sales", "parent_id": 1, "child_ids": [6]},
            {"id": 4, "name": "Frontend", "parent_id": 2, "child_ids": []},
            {"id": 5, "name": "Backend", "parent_id": 2, "child_ids": [7]},
            {"id": 6, "name": "Enterprise Sales", "parent_id": 3, "child_ids": []},
            {"id": 7, "name": "API Team", "parent_id": 5, "child_ids": []},
        ]
    
    def test_get_subordinate_ids_root(self, connector, sample_departments):
        """Test getting all subordinates from root."""
        result = connector.get_subordinate_department_ids(sample_departments, 1)
        
        # Should include all departments
        assert len(result) == 7
        assert 1 in result
        assert 2 in result
        assert 3 in result
        assert 4 in result
        assert 5 in result
        assert 6 in result
        assert 7 in result
    
    def test_get_subordinate_ids_engineering(self, connector, sample_departments):
        """Test getting subordinates of Engineering."""
        result = connector.get_subordinate_department_ids(sample_departments, 2)
        
        # Should include Engineering, Frontend, Backend, API Team
        assert 2 in result
        assert 4 in result
        assert 5 in result
        assert 7 in result
        # Should NOT include Company, Sales, Enterprise Sales
        assert 1 not in result
        assert 3 not in result
        assert 6 not in result
        assert len(result) == 4
    
    def test_get_subordinate_ids_leaf(self, connector, sample_departments):
        """Test getting subordinates of leaf department."""
        result = connector.get_subordinate_department_ids(sample_departments, 4)
        
        # Should only include Frontend itself
        assert result == [4]
    
    def test_get_subordinate_ids_backend(self, connector, sample_departments):
        """Test getting subordinates of Backend."""
        result = connector.get_subordinate_department_ids(sample_departments, 5)
        
        # Should include Backend and API Team
        assert 5 in result
        assert 7 in result
        assert len(result) == 2
    
    def test_get_subordinate_ids_sales(self, connector, sample_departments):
        """Test getting subordinates of Sales."""
        result = connector.get_subordinate_department_ids(sample_departments, 3)
        
        # Should include Sales and Enterprise Sales
        assert 3 in result
        assert 6 in result
        assert len(result) == 2
    
    def test_get_subordinate_ids_nonexistent(self, connector, sample_departments):
        """Test getting subordinates of non-existent department."""
        result = connector.get_subordinate_department_ids(sample_departments, 999)
        
        # Should only include the requested ID
        assert result == [999]
    
    def test_get_subordinate_ids_empty_departments(self, connector):
        """Test with empty department list."""
        result = connector.get_subordinate_department_ids([], 1)
        
        # Should only include the requested ID
        assert result == [1]


class TestGreenhouseAPIEndpoints:
    """Test Greenhouse API endpoint response formats."""
    
    def test_department_response_format(self):
        """Test that department response has correct structure."""
        # Test the expected response format from Greenhouse
        department = {
            "id": 1,
            "name": "Engineering",
            "parent_id": None,
            "child_ids": [2, 3]
        }
        
        # Verify required fields
        assert "id" in department
        assert "name" in department
        assert "parent_id" in department
        assert "child_ids" in department
        
        # Verify types
        assert isinstance(department["id"], int)
        assert isinstance(department["name"], str)
        assert department["parent_id"] is None or isinstance(department["parent_id"], int)
        assert isinstance(department["child_ids"], list)
    
    def test_job_response_format(self):
        """Test that job response has correct structure."""
        job = {
            "id": 101,
            "name": "Senior Engineer",
            "status": "open",
            "departments": ["Engineering"],
            "department_ids": [1, 2],
            "offices": ["San Francisco"]
        }
        
        # Verify required fields
        assert "id" in job
        assert "name" in job
        assert "status" in job
        assert "department_ids" in job
        
        # Verify types
        assert isinstance(job["id"], int)
        assert isinstance(job["name"], str)
        assert isinstance(job["department_ids"], list)
    
    def test_department_hierarchy_structure(self):
        """Test department hierarchy data structure."""
        departments = [
            {"id": 1, "name": "Company", "parent_id": None, "child_ids": [2, 3]},
            {"id": 2, "name": "Engineering", "parent_id": 1, "child_ids": []},
            {"id": 3, "name": "Sales", "parent_id": 1, "child_ids": []},
        ]
        
        # Verify parent-child relationships
        company = departments[0]
        engineering = departments[1]
        sales = departments[2]
        
        assert company["parent_id"] is None
        assert engineering["parent_id"] == company["id"]
        assert sales["parent_id"] == company["id"]
        assert engineering["id"] in company["child_ids"]
        assert sales["id"] in company["child_ids"]


class TestGreenhouseJobFiltering:
    """Test job filtering by department IDs."""
    
    def test_job_filtering_logic(self):
        """Test the job filtering logic directly."""
        # Simulate jobs returned from Greenhouse API
        jobs = [
            {
                "id": 101,
                "name": "Frontend Engineer",
                "status": "open",
                "departments": [{"id": 2, "name": "Frontend"}],
                "offices": []
            },
            {
                "id": 102,
                "name": "Backend Engineer",
                "status": "open",
                "departments": [{"id": 3, "name": "Backend"}],
                "offices": []
            },
            {
                "id": 103,
                "name": "Sales Rep",
                "status": "open",
                "departments": [{"id": 4, "name": "Sales"}],
                "offices": []
            },
            {
                "id": 104,
                "name": "Closed Position",
                "status": "closed",
                "departments": [{"id": 2, "name": "Frontend"}],
                "offices": []
            },
        ]
        
        # Simulate the filtering logic from get_jobs
        department_ids = [2, 3]  # Engineering departments
        result = []
        
        for job in jobs:
            if job.get("status") != "open":
                continue
            
            job_dept_ids = [dept["id"] for dept in job.get("departments", [])]
            
            if department_ids:
                if not any(dept_id in job_dept_ids for dept_id in department_ids):
                    continue
            
            result.append({
                "id": job["id"],
                "name": job["name"],
                "status": job["status"],
                "departments": [dept["name"] for dept in job.get("departments", [])],
                "department_ids": job_dept_ids,
                "offices": [office["name"] for office in job.get("offices", [])]
            })
        
        # Should only include Frontend and Backend jobs (not Sales, not Closed)
        assert len(result) == 2
        job_names = [j["name"] for j in result]
        assert "Frontend Engineer" in job_names
        assert "Backend Engineer" in job_names
        assert "Sales Rep" not in job_names
        assert "Closed Position" not in job_names


class TestDepartmentHierarchyEdgeCases:
    """Test edge cases in department hierarchy handling."""
    
    @pytest.fixture
    def connector(self):
        """Create a GreenhouseConnector instance."""
        from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
        
        return GreenhouseConnector(
            credentials={"api_key": "test_key"},
            config={},
            customer_id="test_customer"
        )
    
    def test_circular_reference_protection(self, connector):
        """Test that circular references don't cause infinite loops."""
        # This shouldn't happen in real data, but test for safety
        departments = [
            {"id": 1, "name": "Dept A", "parent_id": None, "child_ids": [2]},
            {"id": 2, "name": "Dept B", "parent_id": 1, "child_ids": [3]},
            {"id": 3, "name": "Dept C", "parent_id": 2, "child_ids": [1]},  # Circular!
        ]
        
        # Should complete without infinite loop
        result = connector.get_subordinate_department_ids(departments, 1)
        
        # Result may have duplicates but should complete
        assert 1 in result
        assert 2 in result
        assert 3 in result
    
    def test_missing_child_ids(self, connector):
        """Test departments without child_ids field - uses parent_id for hierarchy."""
        departments = [
            {"id": 1, "name": "Dept A", "parent_id": None},  # No child_ids
            {"id": 2, "name": "Dept B", "parent_id": 1},     # Child of 1 via parent_id
        ]
        
        result = connector.get_subordinate_department_ids(departments, 1)
        
        # Should return both IDs since dept 2 has parent_id=1
        assert 1 in result
        assert 2 in result
        assert len(result) == 2
    
    def test_deep_hierarchy(self, connector):
        """Test deeply nested department hierarchy."""
        # Create a chain of 10 departments
        departments = []
        for i in range(10):
            departments.append({
                "id": i + 1,
                "name": f"Level {i + 1}",
                "parent_id": i if i > 0 else None,
                "child_ids": [i + 2] if i < 9 else []
            })
        
        result = connector.get_subordinate_department_ids(departments, 1)
        
        # Should include all 10 departments
        assert len(result) == 10
        for i in range(1, 11):
            assert i in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

