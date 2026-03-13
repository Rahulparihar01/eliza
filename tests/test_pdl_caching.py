"""
Unit tests for PDL Profile Caching feature.

Tests the 30-day cache TTL for PDL query results to reduce API costs.
"""

import pytest
import hashlib
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from src.models.email_templates import PDLQueryCache, CustomerSettings
from src.models.connector import PDLPerson


class TestPDLQueryCacheModel:
    """Test PDLQueryCache model."""
    
    def test_is_valid_future_expiry(self):
        """Test cache is valid when expiry is in the future."""
        cache = PDLQueryCache()
        cache.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        assert cache.is_valid() is True
    
    def test_is_valid_past_expiry(self):
        """Test cache is invalid when expiry is in the past."""
        cache = PDLQueryCache()
        cache.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        
        assert cache.is_valid() is False
    
    def test_is_valid_exact_expiry(self):
        """Test cache is invalid at exact expiry time."""
        cache = PDLQueryCache()
        cache.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        assert cache.is_valid() is False


class TestPDLCacheServiceIntegration:
    """Integration tests for PDL caching in LinkedIn enrichment."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session with proper chaining."""
        session = Mock(spec=Session)
        
        # Setup query chain for PDLQueryCache
        cache_query = Mock()
        session.query.return_value = cache_query
        cache_query.filter.return_value = cache_query
        cache_query.first.return_value = None
        
        return session
    
    @pytest.fixture
    def sample_pdl_person(self):
        """Create a sample PDLPerson for testing."""
        person = PDLPerson()
        person.pdl_id = "pdl_test_123"
        person.customer_id = "test_customer"
        person.full_name = "John Doe"
        person.first_name = "John"
        person.last_name = "Doe"
        person.job_title = "Senior Software Engineer"
        person.job_company_name = "Acme Corp"
        person.location_name = "San Francisco, CA"
        person.skills = ["Python", "JavaScript", "AWS"]
        person.inferred_years_experience = 8
        person.linkedin_url = "https://linkedin.com/in/johndoe"
        person.linkedin_username = "johndoe"
        person.sync_count = 1
        return person
    
    def test_cache_query_hash_consistency(self):
        """Test that query hashing is consistent."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = PDLCacheService(mock_db, "test_customer")
        
        # Same query should produce same hash
        query = {"linkedin_username": "johndoe"}
        hash1 = service._hash_query(query)
        hash2 = service._hash_query(query)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 produces 64 hex chars
    
    def test_cache_query_hash_order_independence(self):
        """Test that query hash is independent of key order."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = PDLCacheService(mock_db, "test_customer")
        
        query1 = {"a": 1, "b": 2, "c": 3}
        query2 = {"c": 3, "a": 1, "b": 2}
        
        assert service._hash_query(query1) == service._hash_query(query2)
    
    def test_cache_ttl_from_settings(self):
        """Test that cache TTL is read from customer settings."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_settings = Mock()
        mock_settings.pdl_cache_ttl_days = 45
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        service = PDLCacheService(mock_db, "test_customer")
        
        assert service.cache_ttl_days == 45
    
    def test_cache_ttl_default_when_no_settings(self):
        """Test that cache TTL defaults to 30 days when no settings."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = PDLCacheService(mock_db, "test_customer")
        
        assert service.cache_ttl_days == 30
    
    def test_cache_hit_increments_counter(self):
        """Test that cache hit increments the hit counter."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_cache_entry = Mock()
        mock_cache_entry.result_pdl_ids = ["pdl_123"]
        mock_cache_entry.cache_hit_count = 5
        mock_cache_entry.expires_at = datetime.now(timezone.utc) + timedelta(days=10)
        
        # Setup the query chain properly
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = mock_cache_entry
        
        service = PDLCacheService(mock_db, "test_customer")
        
        result = service.get_cached_results({"test": "query"}, "linkedin_enrichment")
        
        assert result == ["pdl_123"]
        assert mock_cache_entry.cache_hit_count == 6
        mock_db.commit.assert_called()
    
    def test_cache_miss_returns_none(self):
        """Test that cache miss returns None."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        
        service = PDLCacheService(mock_db, "test_customer")
        
        result = service.get_cached_results({"test": "query"}, "linkedin_enrichment")
        
        assert result is None
    
    def test_cache_results_sets_expiry(self):
        """Test that caching results sets proper expiry date."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value.first.return_value = None
        
        service = PDLCacheService(mock_db, "test_customer")
        service._settings = None  # Force default TTL
        
        before = datetime.now(timezone.utc)
        result = service.cache_results(
            {"linkedin_username": "test"},
            "linkedin_enrichment",
            ["pdl_456"]
        )
        after = datetime.now(timezone.utc)
        
        # Verify add was called
        mock_db.add.assert_called_once()
        
        # Get the added cache entry
        added_entry = mock_db.add.call_args[0][0]
        
        # Expiry should be approximately 30 days from now
        expected_expiry_min = before + timedelta(days=30)
        expected_expiry_max = after + timedelta(days=30)
        
        assert added_entry.expires_at >= expected_expiry_min
        assert added_entry.expires_at <= expected_expiry_max
    
    def test_invalidate_cache_by_type(self):
        """Test invalidating cache entries by query type."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5
        
        service = PDLCacheService(mock_db, "test_customer")
        
        count = service.invalidate_cache("linkedin_enrichment")
        
        assert count == 5
        mock_db.commit.assert_called()
    
    def test_cleanup_expired_entries(self):
        """Test cleaning up expired cache entries."""
        from src.services.email_generation_service import PDLCacheService
        
        mock_db = Mock(spec=Session)
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 10
        
        service = PDLCacheService(mock_db, "test_customer")
        
        count = service.cleanup_expired()
        
        assert count == 10
        mock_db.commit.assert_called()


class TestLinkedInEnrichmentWithCache:
    """Test LinkedIn enrichment endpoint with caching."""
    
    @pytest.fixture
    def mock_user(self):
        """Create a mock user context."""
        user = Mock()
        user.customer_id = "test_customer"
        user.user_id = 1
        return user
    
    @pytest.mark.asyncio
    async def test_enrichment_returns_cached_result(self, mock_user):
        """Test that enrichment returns cached result when available."""
        from src.api.routes.linkedin_enrichment import (
            enrich_linkedin_profile_endpoint,
            LinkedInEnrichmentRequest
        )
        
        mock_db = Mock(spec=Session)
        
        # Setup cache hit
        mock_cache_entry = Mock()
        mock_cache_entry.result_pdl_ids = ["pdl_cached_123"]
        mock_cache_entry.cache_hit_count = 0
        mock_cache_entry.expires_at = datetime.now(timezone.utc) + timedelta(days=10)
        
        # Setup PDLPerson lookup
        mock_person = Mock()
        mock_person.pdl_id = "pdl_cached_123"
        mock_person.full_name = "Cached User"
        mock_person.first_name = "Cached"
        mock_person.last_name = "User"
        mock_person.job_title = "Engineer"
        mock_person.job_title_role = "Engineering"
        mock_person.job_company_name = "Cache Corp"
        mock_person.job_company_size = "51-200"
        mock_person.job_company_industry = "Technology"
        mock_person.location_name = "New York"
        mock_person.location_country = "US"
        mock_person.skills = ["Caching", "Performance"]
        mock_person.inferred_years_experience = 5
        mock_person.education_history = []
        mock_person.work_history = []
        mock_person.pdl_likelihood = 9
        
        # Setup query chains
        def query_side_effect(model):
            mock_query = Mock()
            if model == PDLQueryCache:
                mock_query.filter.return_value.first.return_value = mock_cache_entry
            else:  # PDLPerson
                mock_query.filter.return_value.first.return_value = mock_person
            return mock_query
        
        mock_db.query.side_effect = query_side_effect
        
        request = LinkedInEnrichmentRequest(linkedin_url="https://linkedin.com/in/cacheduser")
        
        with patch('src.api.routes.linkedin_enrichment.PDLCacheService') as MockCacheService:
            mock_service = Mock()
            mock_service.get_cached_results.return_value = ["pdl_cached_123"]
            MockCacheService.return_value = mock_service
            
            result = await enrich_linkedin_profile_endpoint(
                request=request,
                db=mock_db,
                current_user=mock_user
            )
        
        assert result.found is True
        assert result.cached is True
        assert result.full_name == "Cached User"
        assert result.pdl_id == "pdl_cached_123"


class TestPDLPersonStorage:
    """Test storing PDL profiles in database."""
    
    def test_pdl_person_fields(self):
        """Test PDLPerson model has all required fields."""
        person = PDLPerson()
        
        # Check all expected fields exist
        assert hasattr(person, 'pdl_id')
        assert hasattr(person, 'customer_id')
        assert hasattr(person, 'full_name')
        assert hasattr(person, 'first_name')
        assert hasattr(person, 'last_name')
        assert hasattr(person, 'job_title')
        assert hasattr(person, 'job_company_name')
        assert hasattr(person, 'skills')
        assert hasattr(person, 'linkedin_url')
        assert hasattr(person, 'linkedin_username')
        assert hasattr(person, 'sync_count')
    
    def test_pdl_person_sync_count_default(self):
        """Test that sync_count defaults to 1."""
        # Check the column default
        assert PDLPerson.__table__.columns['sync_count'].default.arg == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


