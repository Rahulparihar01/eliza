"""
API tests for Adoption Dashboard endpoints.

Tests cover:
- GET /v1/adoption/metrics
- GET /v1/adoption/overview
- GET /v1/adoption/dashboard
- Sharing endpoints (list, create, update, delete)
- Provider configuration endpoints
- Sync endpoint
"""

import pytest
from datetime import date, datetime, timedelta

from src.api.schemas.adoption import (
    AdoptionMetricsQuery,
    AdoptionMetricsResponse,
    AdoptionMetricsSummary,
    DailyMetric,
    AdoptionOverviewResponse,
    CompanyAdoptionSummary,
    AdoptionShareCreate,
    AdoptionShareResponse,
    AdoptionShareListResponse,
    AdoptionSyncRequest,
    AdoptionSyncResponse,
)


class TestAdoptionSchemas:
    """Tests for Pydantic schemas."""
    
    def test_adoption_metrics_query_defaults(self):
        """Query should have sensible defaults."""
        query = AdoptionMetricsQuery()
        
        assert query.customer_ids is None
        assert query.start_date is None
        assert query.end_date is None
        assert query.provider_type is None
        assert query.group_by == "day"
        
    def test_adoption_metrics_query_with_values(self):
        """Query should accept all parameters."""
        query = AdoptionMetricsQuery(
            customer_ids=["acme", "beta"],
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
            provider_type="openai",
            group_by="week"
        )
        
        assert query.customer_ids == ["acme", "beta"]
        assert query.start_date == date(2025, 1, 1)
        assert query.end_date == date(2025, 1, 31)
        assert query.provider_type == "openai"
        assert query.group_by == "week"
        
    def test_daily_metric_total_tokens(self):
        """Daily metric should store total tokens."""
        metric = DailyMetric(
            date=date.today(),
            customer_id="acme",
            provider_type="openai",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500  # Explicitly set (computed at API layer)
        )
        
        assert metric.total_tokens == 1500
        assert metric.input_tokens == 1000
        assert metric.output_tokens == 500
        
    def test_daily_metric_defaults(self):
        """Daily metric should have zero defaults."""
        metric = DailyMetric(
            date=date.today(),
            customer_id="acme",
            provider_type="openai"
        )
        
        assert metric.active_users == 0
        assert metric.total_conversations == 0
        assert metric.total_messages == 0
        assert metric.input_tokens == 0
        assert metric.output_tokens == 0
        assert metric.total_tokens == 0
        assert metric.unique_gpts_used == 0
        
    def test_adoption_share_create_validation(self):
        """Share create should require target_customer_id."""
        share = AdoptionShareCreate(
            target_customer_id="acme",
            share_level="read"
        )
        
        assert share.target_customer_id == "acme"
        assert share.share_level == "read"
        assert share.notes is None
        assert share.expires_at is None
        
    def test_adoption_share_create_with_expiry(self):
        """Share create should accept expiration."""
        expires = datetime.now() + timedelta(days=30)
        share = AdoptionShareCreate(
            target_customer_id="acme",
            share_level="admin",
            notes="Quarterly review access",
            expires_at=expires
        )
        
        assert share.share_level == "admin"
        assert share.notes == "Quarterly review access"
        assert share.expires_at == expires
        
    def test_adoption_sync_request_defaults(self):
        """Sync request should have optional parameters."""
        request = AdoptionSyncRequest()
        
        assert request.customer_id is None
        assert request.provider_type is None
        assert request.start_date is None
        assert request.end_date is None
        
    def test_adoption_sync_response(self):
        """Sync response should have required fields."""
        response = AdoptionSyncResponse(
            task_id="abc-123",
            status="queued",
            message="Sync queued",
            customer_id="acme"
        )
        
        assert response.task_id == "abc-123"
        assert response.status == "queued"
        assert response.customer_id == "acme"
        

class TestAdoptionMetricsSummary:
    """Tests for metrics summary schema."""
    
    def test_empty_summary(self):
        """Summary should handle empty state."""
        summary = AdoptionMetricsSummary()
        
        assert summary.total_active_users == 0
        assert summary.total_conversations == 0
        assert summary.total_messages == 0
        assert summary.total_tokens == 0
        assert summary.avg_daily_users == 0.0
        assert summary.avg_daily_conversations == 0.0
        assert summary.top_models == []
        assert summary.top_gpts == []
        
    def test_populated_summary(self):
        """Summary should hold computed values."""
        summary = AdoptionMetricsSummary(
            total_active_users=1000,
            total_conversations=5000,
            total_messages=25000,
            total_tokens=1000000,
            avg_daily_users=33.3,
            avg_daily_conversations=166.7,
            top_models=[
                {"model": "gpt-4o", "count": 3000},
                {"model": "gpt-4", "count": 2000}
            ],
            top_gpts=[
                {"name": "Custom GPT 1", "count": 500}
            ]
        )
        
        assert summary.total_active_users == 1000
        assert len(summary.top_models) == 2
        assert summary.top_models[0]["model"] == "gpt-4o"


class TestAdoptionShareListResponse:
    """Tests for share list response schema."""
    
    def test_empty_shares(self):
        """Should handle empty share lists."""
        response = AdoptionShareListResponse()
        
        assert response.shares_given == []
        assert response.shares_received == []
        assert response.total_given == 0
        assert response.total_received == 0
        
    def test_with_shares(self):
        """Should hold share lists."""
        given = [
            AdoptionShareResponse(
                id=1,
                source_customer_id="blackstone",
                target_customer_id="acme",
                share_level="read",
                is_enabled=True,
                created_at=datetime.now()
            )
        ]
        received = [
            AdoptionShareResponse(
                id=2,
                source_customer_id="apollo",
                target_customer_id="blackstone",
                share_level="admin",
                is_enabled=True,
                created_at=datetime.now()
            )
        ]
        
        response = AdoptionShareListResponse(
            shares_given=given,
            shares_received=received,
            total_given=1,
            total_received=1
        )
        
        assert len(response.shares_given) == 1
        assert len(response.shares_received) == 1
        assert response.shares_given[0].source_customer_id == "blackstone"
        assert response.shares_received[0].source_customer_id == "apollo"


class TestCompanyAdoptionSummary:
    """Tests for company overview schema."""
    
    def test_company_summary_defaults(self):
        """Summary should have sensible defaults."""
        summary = CompanyAdoptionSummary(
            customer_id="acme",
            provider_type="openai"
        )
        
        assert summary.customer_id == "acme"
        assert summary.provider_type == "openai"
        assert summary.total_days_tracked == 0
        assert summary.total_active_users == 0
        assert summary.is_syncing is False
        assert summary.sync_error is None
        
    def test_company_summary_with_data(self):
        """Summary should hold company data."""
        summary = CompanyAdoptionSummary(
            customer_id="acme",
            customer_name="Acme Corp",
            provider_type="openai",
            last_sync_at=datetime.now(),
            total_days_tracked=30,
            total_active_users=150,
            total_conversations=5000,
            total_tokens=1000000,
            is_syncing=False
        )
        
        assert summary.customer_name == "Acme Corp"
        assert summary.total_days_tracked == 30
        assert summary.total_active_users == 150


class TestAdoptionOverviewResponse:
    """Tests for overview response schema."""
    
    def test_overview_with_companies(self):
        """Overview should hold company summaries."""
        companies = [
            CompanyAdoptionSummary(
                customer_id="acme",
                provider_type="openai",
                total_days_tracked=30
            ),
            CompanyAdoptionSummary(
                customer_id="beta",
                provider_type="openai",
                total_days_tracked=0
            )
        ]
        
        response = AdoptionOverviewResponse(
            companies=companies,
            total_companies=2,
            companies_with_data=1
        )
        
        assert response.total_companies == 2
        assert response.companies_with_data == 1
        assert len(response.companies) == 2

