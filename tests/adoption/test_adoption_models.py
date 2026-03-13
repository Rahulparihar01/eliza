"""
Unit tests for Adoption Dashboard models.

Tests cover:
- AdoptionDataShare model creation and methods
- AdoptionDailyMetrics model creation and methods
- AdoptionSourceType constants
- AdoptionShareLevel constants
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.models.adoption import (
    AdoptionDataShare,
    AdoptionDailyMetrics,
    AdoptionSourceType,
    AdoptionShareLevel,
)


class TestAdoptionSourceType:
    """Tests for AdoptionSourceType constants."""
    
    def test_all_types_returns_list(self):
        """all_types should return a list of all source types."""
        types = AdoptionSourceType.all_types()
        assert isinstance(types, list)
        assert len(types) >= 5  # At least 5 types defined
        
    def test_all_types_contains_expected_values(self):
        """all_types should contain expected source types."""
        types = AdoptionSourceType.all_types()
        assert AdoptionSourceType.OPENAI_COMPLIANCE in types
        assert AdoptionSourceType.ELIZA_PLATFORM in types
        assert AdoptionSourceType.GOOGLE_GEMINI_COMPLIANCE in types
        assert AdoptionSourceType.ANTHROPIC_COMPLIANCE in types
        assert AdoptionSourceType.MICROSOFT_COPILOT in types
        
    def test_is_valid_returns_true_for_valid_types(self):
        """is_valid should return True for valid source types."""
        assert AdoptionSourceType.is_valid("openai_compliance") is True
        assert AdoptionSourceType.is_valid("eliza_platform") is True
        
    def test_is_valid_returns_false_for_invalid_types(self):
        """is_valid should return False for invalid source types."""
        assert AdoptionSourceType.is_valid("invalid_source") is False
        assert AdoptionSourceType.is_valid("") is False
        assert AdoptionSourceType.is_valid("OPENAI_COMPLIANCE") is False  # Case sensitive


class TestAdoptionShareLevel:
    """Tests for AdoptionShareLevel constants."""
    
    def test_all_levels_returns_list(self):
        """all_levels should return a list of all share levels."""
        levels = AdoptionShareLevel.all_levels()
        assert isinstance(levels, list)
        assert len(levels) == 2  # read and admin
        
    def test_all_levels_contains_expected_values(self):
        """all_levels should contain expected share levels."""
        levels = AdoptionShareLevel.all_levels()
        assert AdoptionShareLevel.READ in levels
        assert AdoptionShareLevel.ADMIN in levels
        
    def test_is_valid_returns_true_for_valid_levels(self):
        """is_valid should return True for valid share levels."""
        assert AdoptionShareLevel.is_valid("read") is True
        assert AdoptionShareLevel.is_valid("admin") is True
        
    def test_is_valid_returns_false_for_invalid_levels(self):
        """is_valid should return False for invalid share levels."""
        assert AdoptionShareLevel.is_valid("write") is False
        assert AdoptionShareLevel.is_valid("") is False
        assert AdoptionShareLevel.is_valid("READ") is False  # Case sensitive


class TestAdoptionDataShare:
    """Tests for AdoptionDataShare model."""
    
    def test_model_creation(self):
        """AdoptionDataShare should be creatable with required fields."""
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=True,
            share_level="read"
        )
        
        assert share.source_customer_id == "acme"
        assert share.target_customer_id == "blackstone"
        assert share.is_enabled is True
        assert share.share_level == "read"
        
    def test_is_active_returns_true_when_enabled_no_expiry(self):
        """is_active should return True when enabled and no expiry."""
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=True,
            share_level="read",
            expires_at=None
        )
        
        assert share.is_active() is True
        
    def test_is_active_returns_false_when_disabled(self):
        """is_active should return False when disabled."""
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=False,
            share_level="read"
        )
        
        assert share.is_active() is False
        
    def test_is_active_returns_false_when_expired(self):
        """is_active should return False when expired."""
        past_date = datetime.now(timezone.utc) - timedelta(days=1)
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=True,
            share_level="read",
            expires_at=past_date
        )
        
        assert share.is_active() is False
        
    def test_is_active_returns_true_when_not_expired(self):
        """is_active should return True when expiry is in the future."""
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=True,
            share_level="read",
            expires_at=future_date
        )
        
        assert share.is_active() is True
        
    def test_grants_admin_returns_true_for_active_admin_share(self):
        """grants_admin should return True for active admin share."""
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=True,
            share_level="admin",
            expires_at=None
        )
        
        assert share.grants_admin() is True
        
    def test_grants_admin_returns_false_for_read_share(self):
        """grants_admin should return False for read-only share."""
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=True,
            share_level="read"
        )
        
        assert share.grants_admin() is False
        
    def test_grants_admin_returns_false_for_disabled_admin_share(self):
        """grants_admin should return False for disabled admin share."""
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=False,
            share_level="admin"
        )
        
        assert share.grants_admin() is False
        
    def test_repr_format(self):
        """__repr__ should return a readable string."""
        share = AdoptionDataShare(
            source_customer_id="acme",
            target_customer_id="blackstone",
            is_enabled=True,
            share_level="read"
        )
        
        repr_str = repr(share)
        assert "AdoptionDataShare" in repr_str
        assert "acme" in repr_str
        assert "blackstone" in repr_str
        assert "read" in repr_str


class TestAdoptionDailyMetrics:
    """Tests for AdoptionDailyMetrics model."""
    
    def test_model_creation(self):
        """AdoptionDailyMetrics should be creatable with required fields."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            active_users=100,
            total_messages=5000,
            total_conversations=1000,
            total_images=50
        )
        
        assert metrics.customer_id == "acme"
        assert metrics.source_type == "openai_compliance"
        assert metrics.metric_date == date(2025, 12, 28)
        assert metrics.active_users == 100
        assert metrics.total_messages == 5000
        assert metrics.total_conversations == 1000
        assert metrics.total_images == 50
        
    def test_total_tokens_property(self):
        """total_tokens should return sum of input and output tokens."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            input_tokens=100000,
            output_tokens=50000
        )
        
        assert metrics.total_tokens == 150000
        
    def test_total_tokens_handles_none(self):
        """total_tokens should handle None values gracefully."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            input_tokens=None,
            output_tokens=None
        )
        
        assert metrics.total_tokens == 0
        
    def test_get_model_usage_returns_count(self):
        """get_model_usage should return count for specific model."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            model_breakdown={"gpt-4": 1000, "gpt-4o": 500, "gpt-3.5-turbo": 200}
        )
        
        assert metrics.get_model_usage("gpt-4") == 1000
        assert metrics.get_model_usage("gpt-4o") == 500
        assert metrics.get_model_usage("gpt-3.5-turbo") == 200
        
    def test_get_model_usage_returns_zero_for_unknown(self):
        """get_model_usage should return 0 for unknown models."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            model_breakdown={"gpt-4": 1000}
        )
        
        assert metrics.get_model_usage("unknown-model") == 0
        
    def test_get_model_usage_handles_none_breakdown(self):
        """get_model_usage should handle None model_breakdown."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            model_breakdown=None
        )
        
        assert metrics.get_model_usage("gpt-4") == 0
        
    def test_get_top_gpt_names_returns_sorted_list(self):
        """get_top_gpt_names should return sorted list of GPT names."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            top_gpts=[
                {"name": "Code Helper", "uses": 100},
                {"name": "Writing Assistant", "uses": 500},
                {"name": "Data Analyst", "uses": 200},
            ]
        )
        
        top_names = metrics.get_top_gpt_names(limit=3)
        assert top_names == ["Writing Assistant", "Data Analyst", "Code Helper"]
        
    def test_get_top_gpt_names_respects_limit(self):
        """get_top_gpt_names should respect the limit parameter."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            top_gpts=[
                {"name": "GPT1", "uses": 500},
                {"name": "GPT2", "uses": 400},
                {"name": "GPT3", "uses": 300},
                {"name": "GPT4", "uses": 200},
                {"name": "GPT5", "uses": 100},
            ]
        )
        
        top_names = metrics.get_top_gpt_names(limit=2)
        assert len(top_names) == 2
        assert top_names == ["GPT1", "GPT2"]
        
    def test_get_top_gpt_names_handles_none(self):
        """get_top_gpt_names should handle None top_gpts."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            top_gpts=None
        )
        
        assert metrics.get_top_gpt_names() == []
        
    def test_repr_format(self):
        """__repr__ should return a readable string."""
        metrics = AdoptionDailyMetrics(
            customer_id="acme",
            source_type="openai_compliance",
            metric_date=date(2025, 12, 28),
            active_users=100,
            total_messages=5000
        )
        
        repr_str = repr(metrics)
        assert "AdoptionDailyMetrics" in repr_str
        assert "acme" in repr_str
        assert "openai_compliance" in repr_str


class TestCustomerAIProviderAdoptionField:
    """Tests for the is_adoption_source field on CustomerAIProvider."""
    
    def test_customer_ai_provider_has_adoption_field(self):
        """CustomerAIProvider should have is_adoption_source field."""
        from src.models.customer import CustomerAIProvider
        
        # Check that the column exists in the model
        assert hasattr(CustomerAIProvider, 'is_adoption_source')
        
    def test_customer_ai_provider_adoption_field_defaults_false(self):
        """is_adoption_source should default to False."""
        from src.models.customer import CustomerAIProvider
        
        provider = CustomerAIProvider(
            customer_id="acme",
            provider_name="openai_compliance"
        )
        
        # Default should be False (or the column default)
        assert provider.is_adoption_source is None or provider.is_adoption_source is False

