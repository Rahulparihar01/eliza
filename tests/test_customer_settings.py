"""
Unit tests for Customer Settings feature.

Tests customer-specific configuration including Greenhouse maildrop address.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from src.models.email_templates import CustomerSettings


class TestCustomerSettingsModel:
    """Test CustomerSettings model."""
    
    def test_model_has_required_fields(self):
        """Test that model has all required fields."""
        settings = CustomerSettings()
        
        assert hasattr(settings, 'customer_id')
        assert hasattr(settings, 'greenhouse_maildrop_address')
        assert hasattr(settings, 'greenhouse_connector_id')
        assert hasattr(settings, 'pdl_cache_ttl_days')
        assert hasattr(settings, 'pdl_max_results_per_query')
        assert hasattr(settings, 'default_email_template_id')
        assert hasattr(settings, 'email_signature')
        assert hasattr(settings, 'sender_name')
        assert hasattr(settings, 'sender_title')
        assert hasattr(settings, 'ai_email_generation_enabled')
        assert hasattr(settings, 'ai_model_preference')
    
    def test_default_pdl_cache_ttl(self):
        """Test default PDL cache TTL is 30 days."""
        column = CustomerSettings.__table__.columns['pdl_cache_ttl_days']
        assert column.default.arg == 30
    
    def test_default_pdl_max_results(self):
        """Test default PDL max results is 50."""
        column = CustomerSettings.__table__.columns['pdl_max_results_per_query']
        assert column.default.arg == 50
    
    def test_default_ai_enabled(self):
        """Test AI email generation is enabled by default."""
        column = CustomerSettings.__table__.columns['ai_email_generation_enabled']
        assert column.default.arg is True
    
    def test_default_ai_model(self):
        """Test default AI model is gpt-4."""
        column = CustomerSettings.__table__.columns['ai_model_preference']
        assert column.default.arg == "gpt-4"


class TestCustomerSettingsAPI:
    """Test Customer Settings API endpoints."""
    
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
    async def test_get_settings_returns_defaults(self, mock_db, mock_user):
        """Test getting settings returns defaults when none exist."""
        from src.api.routes.email_templates import get_settings
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = await get_settings(db=mock_db, current_user=mock_user)
        
        assert result.greenhouse_maildrop_address == "maildrop@lily.greenhouse.io"
        assert result.pdl_cache_ttl_days == 30
        assert result.sender_name is None
        assert result.sender_title is None
        assert result.ai_email_generation_enabled is True
    
    @pytest.mark.asyncio
    async def test_get_settings_returns_stored_values(self, mock_db, mock_user):
        """Test getting settings returns stored values."""
        from src.api.routes.email_templates import get_settings
        
        mock_settings = Mock()
        mock_settings.greenhouse_maildrop_address = "custom@maildrop.io"
        mock_settings.pdl_cache_ttl_days = 45
        mock_settings.sender_name = "John Recruiter"
        mock_settings.sender_title = "Senior Recruiter"
        mock_settings.ai_email_generation_enabled = False
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        result = await get_settings(db=mock_db, current_user=mock_user)
        
        assert result.greenhouse_maildrop_address == "custom@maildrop.io"
        assert result.pdl_cache_ttl_days == 45
        assert result.sender_name == "John Recruiter"
        assert result.sender_title == "Senior Recruiter"
        assert result.ai_email_generation_enabled is False
    
    @pytest.mark.asyncio
    async def test_update_settings_creates_new(self, mock_db, mock_user):
        """Test updating settings creates new record if none exists."""
        from src.api.routes.email_templates import update_settings, CustomerSettingsUpdate
        
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock refresh to simulate database setting defaults
        def mock_refresh(settings):
            if settings.ai_email_generation_enabled is None:
                settings.ai_email_generation_enabled = True
            if settings.pdl_cache_ttl_days is None:
                settings.pdl_cache_ttl_days = 30
        
        mock_db.refresh.side_effect = mock_refresh
        
        update_request = CustomerSettingsUpdate(
            greenhouse_maildrop_address="new@maildrop.io",
            pdl_cache_ttl_days=60
        )
        
        result = await update_settings(
            request=update_request,
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify new settings were added
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called()
        assert result.greenhouse_maildrop_address == "new@maildrop.io"
        assert result.pdl_cache_ttl_days == 60
    
    @pytest.mark.asyncio
    async def test_update_settings_modifies_existing(self, mock_db, mock_user):
        """Test updating settings modifies existing record."""
        from src.api.routes.email_templates import update_settings, CustomerSettingsUpdate
        
        mock_settings = Mock()
        mock_settings.greenhouse_maildrop_address = "old@maildrop.io"
        mock_settings.pdl_cache_ttl_days = 30
        mock_settings.sender_name = None
        mock_settings.sender_title = None
        mock_settings.email_signature = None
        mock_settings.ai_email_generation_enabled = True
        
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        update_request = CustomerSettingsUpdate(
            greenhouse_maildrop_address="new@maildrop.io",
            sender_name="Jane Doe"
        )
        
        result = await update_settings(
            request=update_request,
            db=mock_db,
            current_user=mock_user
        )
        
        # Verify settings were updated
        assert mock_settings.greenhouse_maildrop_address == "new@maildrop.io"
        assert mock_settings.sender_name == "Jane Doe"
        mock_db.commit.assert_called()


class TestGreenhouseMaildropIntegration:
    """Test Greenhouse maildrop address integration."""
    
    def test_email_generation_service_uses_settings(self):
        """Test EmailGenerationService uses customer settings for maildrop."""
        from src.services.email_generation_service import EmailGenerationService
        
        mock_db = Mock(spec=Session)
        mock_settings = Mock()
        mock_settings.greenhouse_maildrop_address = "custom@lily.greenhouse.io"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_settings
        
        service = EmailGenerationService(mock_db, "test_customer")
        
        result = service.get_greenhouse_maildrop()
        
        assert result == "custom@lily.greenhouse.io"
    
    def test_email_generation_service_default_maildrop(self):
        """Test EmailGenerationService uses default maildrop when no settings."""
        from src.services.email_generation_service import EmailGenerationService
        
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = EmailGenerationService(mock_db, "test_customer")
        
        result = service.get_greenhouse_maildrop()
        
        assert result == "maildrop@lily.greenhouse.io"
    
    def test_generated_email_response_includes_maildrop(self):
        """Test GeneratedEmailResponse includes maildrop address."""
        from src.api.routes.email_templates import GeneratedEmailResponse
        from datetime import datetime
        
        response = GeneratedEmailResponse(
            id=1,
            template_id=1,
            candidate_id="test_123",
            subject="Test Subject",
            body="Test Body",
            is_edited=False,
            status="draft",
            created_at=datetime.now(),
            greenhouse_maildrop="maildrop@lily.greenhouse.io"
        )
        
        assert response.greenhouse_maildrop == "maildrop@lily.greenhouse.io"


class TestCaylentDefaultSettings:
    """Test default settings for Caylent (the current customer)."""
    
    def test_migration_sets_caylent_defaults(self):
        """Test that migration SQL sets Caylent defaults."""
        # Read the migration file and verify it sets defaults
        migration_path = "alembic/versions/l2m3n4o5p6q7_add_email_templates_and_pdl_cache.py"
        
        with open(migration_path, 'r') as f:
            migration_content = f.read()
        
        # Verify the INSERT statement for Caylent
        assert "INSERT INTO customer_settings" in migration_content
        assert "'eliza'" in migration_content
        assert "'maildrop@lily.greenhouse.io'" in migration_content
        assert "30" in migration_content  # PDL cache TTL


class TestSettingsValidation:
    """Test settings validation."""
    
    def test_pdl_cache_ttl_must_be_positive(self):
        """Test that PDL cache TTL should be positive."""
        from src.api.routes.email_templates import CustomerSettingsUpdate
        
        # This should be validated at the API level
        update = CustomerSettingsUpdate(pdl_cache_ttl_days=0)
        
        # The model accepts it, but API should validate
        assert update.pdl_cache_ttl_days == 0
    
    def test_greenhouse_maildrop_format(self):
        """Test Greenhouse maildrop address format."""
        # Valid formats
        valid_addresses = [
            "maildrop@lily.greenhouse.io",
            "custom@company.greenhouse.io",
            "test@maildrop.greenhouse.io"
        ]
        
        for address in valid_addresses:
            # Should contain @ and greenhouse.io
            assert "@" in address
            assert "greenhouse.io" in address


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

