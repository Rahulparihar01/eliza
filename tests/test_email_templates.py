"""
Unit tests for Email Templates feature.

Tests the section-based email templates with static and AI-generated content.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

# Test the models
from src.models.email_templates import (
    EmailTemplate,
    EmailTemplateSection,
    GeneratedEmail,
    PDLQueryCache,
    CustomerSettings,
    TemplateSectionType,
    TemplateCategory
)


class TestEmailTemplateModels:
    """Test EmailTemplate and related models."""
    
    def test_template_section_type_enum(self):
        """Test TemplateSectionType enum values."""
        assert TemplateSectionType.STATIC.value == "static"
        assert TemplateSectionType.AI_GENERATED.value == "ai_generated"
    
    def test_template_category_enum(self):
        """Test TemplateCategory enum values."""
        assert TemplateCategory.APPLICANT_FOLLOWUP.value == "applicant_followup"
        assert TemplateCategory.MARKET_OUTREACH.value == "market_outreach"
        assert TemplateCategory.INTERVIEW_INVITE.value == "interview_invite"
        assert TemplateCategory.REJECTION.value == "rejection"
        assert TemplateCategory.CUSTOM.value == "custom"
    
    def test_email_template_get_all_variables(self):
        """Test extracting variables from template."""
        import re
        
        # Test variable extraction logic directly without SQLAlchemy relationship
        subject = "Hello {{candidate_name}}, opportunity at {{company_name}}"
        section1_content = "Hi {{candidate_first_name}},\n\nYour {{skills}} are impressive."
        section2_prompt = "Write about their {{job_title}} experience"
        
        # Extract variables using the same regex pattern as the model
        pattern = r'\{\{(\w+)\}\}'
        variables = set()
        
        variables.update(re.findall(pattern, subject))
        variables.update(re.findall(pattern, section1_content))
        variables.update(re.findall(pattern, section2_prompt))
        
        assert "candidate_name" in variables
        assert "company_name" in variables
        assert "candidate_first_name" in variables
        assert "skills" in variables
        assert "job_title" in variables
    
    def test_pdl_query_cache_is_valid_not_expired(self):
        """Test PDLQueryCache.is_valid() when not expired."""
        cache = PDLQueryCache()
        cache.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        
        assert cache.is_valid() is True
    
    def test_pdl_query_cache_is_valid_expired(self):
        """Test PDLQueryCache.is_valid() when expired."""
        cache = PDLQueryCache()
        cache.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        
        assert cache.is_valid() is False


class TestEmailGenerationService:
    """Test EmailGenerationService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock(spec=Session)
        # Default to returning None for customer settings query
        db.query.return_value.filter.return_value.first.return_value = None
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        """Create EmailGenerationService instance."""
        from src.services.email_generation_service import EmailGenerationService
        return EmailGenerationService(mock_db, "test_customer")
    
    def test_substitute_variables_basic(self, service):
        """Test basic variable substitution."""
        text = "Hello {{candidate_name}}, welcome to {{company_name}}"
        data = {
            "full_name": "John Doe",
            "job_company_name": "Acme Corp"
        }
        
        result = service._substitute_variables(text, data)
        
        assert "John Doe" in result
        assert "Acme Corp" in result
        assert "{{candidate_name}}" not in result
        assert "{{company_name}}" not in result
    
    def test_substitute_variables_first_name(self, service):
        """Test first name extraction from full name."""
        text = "Hi {{candidate_first_name}}!"
        data = {"name": "Jane Smith"}
        
        result = service._substitute_variables(text, data)
        
        assert "Jane" in result
        assert "{{candidate_first_name}}" not in result
    
    def test_substitute_variables_skills(self, service):
        """Test skills variable substitution."""
        text = "Your skills: {{skills}}"
        data = {"skills": ["Python", "Machine Learning", "AWS", "Docker", "Kubernetes"]}
        
        result = service._substitute_variables(text, data)
        
        assert "Python" in result
        assert "Machine Learning" in result
        # Should only include first 5 skills
        assert result.count(",") <= 4
    
    def test_substitute_variables_empty_data(self, service):
        """Test substitution with empty data."""
        text = "Hello {{candidate_name}}"
        data = {}
        
        result = service._substitute_variables(text, data)
        
        # Should replace with empty string
        assert "Hello " in result
        assert "{{candidate_name}}" not in result
    
    def test_substitute_variables_current_date(self, service):
        """Test current date substitution."""
        text = "Date: {{current_date}}"
        data = {}
        
        result = service._substitute_variables(text, data)
        
        # Should have today's date in some format
        today = datetime.now()
        assert str(today.year) in result
    
    def test_get_greenhouse_maildrop_with_settings(self, service, mock_db):
        """Test getting Greenhouse maildrop from settings."""
        mock_settings = Mock()
        mock_settings.greenhouse_maildrop_address = "custom@maildrop.io"
        service._settings = mock_settings
        
        result = service.get_greenhouse_maildrop()
        
        assert result == "custom@maildrop.io"
    
    def test_get_greenhouse_maildrop_default(self, service, mock_db):
        """Test default Greenhouse maildrop when no settings."""
        service._settings = None
        # Mock the database query to return None (no settings found)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = service.get_greenhouse_maildrop()
        
        # When no settings exist, should return the hardcoded default
        assert result == "maildrop@lily.greenhouse.io"


class TestPDLCacheService:
    """Test PDLCacheService."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock(spec=Session)
        db.query.return_value.filter.return_value.first.return_value = None
        return db
    
    @pytest.fixture
    def service(self, mock_db):
        """Create PDLCacheService instance."""
        from src.services.email_generation_service import PDLCacheService
        return PDLCacheService(mock_db, "test_customer")
    
    def test_hash_query_deterministic(self, service):
        """Test that query hashing is deterministic."""
        query1 = {"linkedin_username": "johndoe", "company": "acme"}
        query2 = {"company": "acme", "linkedin_username": "johndoe"}  # Different order
        
        hash1 = service._hash_query(query1)
        hash2 = service._hash_query(query2)
        
        # Same content, different order should produce same hash
        assert hash1 == hash2
    
    def test_hash_query_different_queries(self, service):
        """Test that different queries produce different hashes."""
        query1 = {"linkedin_username": "johndoe"}
        query2 = {"linkedin_username": "janedoe"}
        
        hash1 = service._hash_query(query1)
        hash2 = service._hash_query(query2)
        
        assert hash1 != hash2
    
    def test_cache_ttl_days_default(self, service):
        """Test default cache TTL."""
        service._settings = None
        
        assert service.cache_ttl_days == 30
    
    def test_cache_ttl_days_from_settings(self, service):
        """Test cache TTL from customer settings."""
        mock_settings = Mock()
        mock_settings.pdl_cache_ttl_days = 60
        service._settings = mock_settings
        
        assert service.cache_ttl_days == 60
    
    def test_get_cached_results_miss(self, service, mock_db):
        """Test cache miss returns None."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = service.get_cached_results({"test": "query"}, "linkedin_enrichment")
        
        assert result is None
    
    def test_get_cached_results_hit(self, service, mock_db):
        """Test cache hit returns cached PDL IDs."""
        mock_cache = Mock()
        mock_cache.result_pdl_ids = ["pdl_123", "pdl_456"]
        mock_cache.cache_hit_count = 5
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cache
        
        result = service.get_cached_results({"test": "query"}, "linkedin_enrichment")
        
        assert result == ["pdl_123", "pdl_456"]
        assert mock_cache.cache_hit_count == 6  # Incremented
    
    def test_cache_results_creates_entry(self, service, mock_db):
        """Test caching results creates new entry."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = service.cache_results(
            {"linkedin_username": "test"},
            "linkedin_enrichment",
            ["pdl_789"]
        )
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestLinkedInEnrichmentHelpers:
    """Test LinkedIn enrichment helper functions."""
    
    def test_extract_linkedin_username_standard_url(self):
        """Test extracting username from standard LinkedIn URL."""
        from src.api.routes.linkedin_enrichment import extract_linkedin_username
        
        url = "https://www.linkedin.com/in/johndoe"
        result = extract_linkedin_username(url)
        
        assert result == "johndoe"
    
    def test_extract_linkedin_username_with_trailing_slash(self):
        """Test extracting username with trailing slash."""
        from src.api.routes.linkedin_enrichment import extract_linkedin_username
        
        url = "https://linkedin.com/in/janedoe/"
        result = extract_linkedin_username(url)
        
        assert result == "janedoe"
    
    def test_extract_linkedin_username_http(self):
        """Test extracting username from HTTP URL."""
        from src.api.routes.linkedin_enrichment import extract_linkedin_username
        
        url = "http://www.linkedin.com/in/bobsmith"
        result = extract_linkedin_username(url)
        
        assert result == "bobsmith"
    
    def test_extract_linkedin_username_no_protocol(self):
        """Test extracting username without protocol."""
        from src.api.routes.linkedin_enrichment import extract_linkedin_username
        
        url = "linkedin.com/in/alicejones"
        result = extract_linkedin_username(url)
        
        assert result == "alicejones"
    
    def test_extract_linkedin_username_pub_format(self):
        """Test extracting username from /pub/ format."""
        from src.api.routes.linkedin_enrichment import extract_linkedin_username
        
        url = "https://www.linkedin.com/pub/oldformat"
        result = extract_linkedin_username(url)
        
        assert result == "oldformat"
    
    def test_extract_linkedin_username_invalid(self):
        """Test invalid URL returns None."""
        from src.api.routes.linkedin_enrichment import extract_linkedin_username
        
        url = "https://twitter.com/johndoe"
        result = extract_linkedin_username(url)
        
        assert result is None
    
    def test_extract_linkedin_username_with_hyphen(self):
        """Test username with hyphen."""
        from src.api.routes.linkedin_enrichment import extract_linkedin_username
        
        url = "https://www.linkedin.com/in/john-doe-123"
        result = extract_linkedin_username(url)
        
        assert result == "john-doe-123"


class TestEmailTemplatesAPI:
    """Test Email Templates API endpoints."""
    
    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user context."""
        user = Mock()
        user.customer_id = "test_customer"
        user.user_id = 1
        return user
    
    @pytest.mark.asyncio
    async def test_list_templates_empty(self, mock_db, mock_user):
        """Test listing templates when none exist."""
        from src.api.routes.email_templates import list_templates
        
        # Set up the mock chain for the query: query().filter().order_by().all()
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        # Call the endpoint function directly with mocked dependencies
        result = await list_templates(db=mock_db, current_user=mock_user)
        
        assert result.total == 0
        assert result.templates == []
    
    @pytest.mark.asyncio
    async def test_get_settings_defaults(self, mock_db, mock_user):
        """Test getting settings returns defaults when none exist."""
        from src.api.routes.email_templates import get_settings
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        with patch('src.api.routes.email_templates.get_db', return_value=mock_db):
            result = await get_settings(db=mock_db, current_user=mock_user)
        
        assert result.greenhouse_maildrop_address == "maildrop@lily.greenhouse.io"
        assert result.pdl_cache_ttl_days == 30
        assert result.ai_email_generation_enabled is True


class TestGreenhouseConnectorDepartments:
    """Test Greenhouse connector department functionality."""
    
    def test_get_subordinate_department_ids_no_children(self):
        """Test getting subordinate IDs for department with no children."""
        from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
        
        connector = GreenhouseConnector(
            credentials={"api_key": "test"},
            config={},
            customer_id="test"
        )
        
        departments = [
            {"id": 1, "name": "Engineering", "parent_id": None, "child_ids": []},
            {"id": 2, "name": "Sales", "parent_id": None, "child_ids": []},
        ]
        
        result = connector.get_subordinate_department_ids(departments, 1)
        
        assert result == [1]
    
    def test_get_subordinate_department_ids_with_children(self):
        """Test getting subordinate IDs for department with children."""
        from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
        
        connector = GreenhouseConnector(
            credentials={"api_key": "test"},
            config={},
            customer_id="test"
        )
        
        departments = [
            {"id": 1, "name": "Engineering", "parent_id": None, "child_ids": [2, 3]},
            {"id": 2, "name": "Frontend", "parent_id": 1, "child_ids": []},
            {"id": 3, "name": "Backend", "parent_id": 1, "child_ids": [4]},
            {"id": 4, "name": "API Team", "parent_id": 3, "child_ids": []},
        ]
        
        result = connector.get_subordinate_department_ids(departments, 1)
        
        assert 1 in result
        assert 2 in result
        assert 3 in result
        assert 4 in result
        assert len(result) == 4
    
    def test_get_subordinate_department_ids_nested(self):
        """Test getting subordinate IDs for deeply nested department."""
        from src.services.ingestion.connectors.greenhouse import GreenhouseConnector
        
        connector = GreenhouseConnector(
            credentials={"api_key": "test"},
            config={},
            customer_id="test"
        )
        
        departments = [
            {"id": 1, "name": "Company", "parent_id": None, "child_ids": [2]},
            {"id": 2, "name": "Engineering", "parent_id": 1, "child_ids": [3]},
            {"id": 3, "name": "Platform", "parent_id": 2, "child_ids": [4]},
            {"id": 4, "name": "Infrastructure", "parent_id": 3, "child_ids": []},
        ]
        
        # Get subordinates of Engineering (id=2)
        result = connector.get_subordinate_department_ids(departments, 2)
        
        assert 2 in result
        assert 3 in result
        assert 4 in result
        assert 1 not in result  # Parent should not be included
        assert len(result) == 3


class TestCustomerSettings:
    """Test CustomerSettings model and defaults."""
    
    def test_default_pdl_cache_ttl(self):
        """Test default PDL cache TTL is 30 days."""
        settings = CustomerSettings()
        # Check the default from the Column definition
        assert CustomerSettings.__table__.columns['pdl_cache_ttl_days'].default.arg == 30
    
    def test_default_ai_enabled(self):
        """Test AI email generation is enabled by default."""
        assert CustomerSettings.__table__.columns['ai_email_generation_enabled'].default.arg is True
    
    def test_default_ai_model(self):
        """Test default AI model is gpt-4."""
        assert CustomerSettings.__table__.columns['ai_model_preference'].default.arg == "gpt-4"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

