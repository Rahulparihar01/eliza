"""
Adoption Dashboard Service.

Business logic for:
- Querying adoption metrics across companies
- Managing data sharing between tenants
- Triggering sync operations
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from src.models.adoption import (
    AdoptionDailyMetrics,
    AdoptionDataShare,
    AdoptionShareLevel,
    AdoptionGPT,
    AdoptionConversation,
    AdoptionUserGPTInteraction
)
from src.models.customer import Customer, CustomerAIProvider
from src.core.auth_context import CurrentUserContext
from src.middleware.authorization import get_accessible_adoption_companies

logger = logging.getLogger(__name__)


class AdoptionService:
    """Service for adoption dashboard operations."""
    
    def __init__(self, db: Session, current_user: CurrentUserContext):
        self.db = db
        self.current_user = current_user
    
    # =========================================================================
    # Metrics Operations
    # =========================================================================
    
    def get_accessible_companies(self) -> List[str]:
        """Get list of company IDs the current user can access."""
        return get_accessible_adoption_companies(self.current_user, action="read", db=self.db)
    
    def get_metrics(
        self,
        customer_ids: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        provider_type: Optional[str] = None,
        group_by: str = "day"
    ) -> Tuple[List[AdoptionDailyMetrics], Dict[str, Any]]:
        """
        Get adoption metrics for accessible companies.
        
        Args:
            customer_ids: Filter to specific companies (None = all accessible)
            start_date: Start date filter
            end_date: End date filter
            provider_type: Filter by provider (openai, anthropic, etc)
            group_by: Aggregation period (day, week, month)
            
        Returns:
            Tuple of (metrics list, summary dict)
        """
        # Determine which companies to query
        accessible = self.get_accessible_companies()
        
        if customer_ids:
            # Filter to only accessible companies
            query_companies = [c for c in customer_ids if c in accessible]
            if not query_companies:
                return [], self._empty_summary()
        else:
            query_companies = accessible
        
        # Build query
        query = self.db.query(AdoptionDailyMetrics).filter(
            AdoptionDailyMetrics.customer_id.in_(query_companies)
        )
        
        # Apply date filters
        if start_date:
            query = query.filter(AdoptionDailyMetrics.metric_date >= start_date)
        if end_date:
            query = query.filter(AdoptionDailyMetrics.metric_date <= end_date)
        
        # Apply provider filter
        if provider_type:
            query = query.filter(AdoptionDailyMetrics.source_type == provider_type)
        
        # Order by date
        query = query.order_by(AdoptionDailyMetrics.metric_date.desc())
        
        metrics = query.all()
        
        # Calculate summary
        summary = self._calculate_summary(metrics)
        
        return metrics, summary
    
    def get_company_overview(self) -> List[Dict[str, Any]]:
        """Get overview of all accessible companies' adoption status."""
        accessible = self.get_accessible_companies()
        
        results = []
        for customer_id in accessible:
            # Get customer info
            customer = self.db.query(Customer).filter(
                Customer.customer_id == customer_id
            ).first()
            
            # Get latest metrics
            latest = self.db.query(AdoptionDailyMetrics).filter(
                AdoptionDailyMetrics.customer_id == customer_id
            ).order_by(AdoptionDailyMetrics.metric_date.desc()).first()
            
            # Get provider config
            provider = self.db.query(CustomerAIProvider).filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.is_adoption_source == True
            ).first()
            
            # Aggregate totals
            totals = self.db.query(
                func.count(AdoptionDailyMetrics.id).label("days"),
                func.sum(AdoptionDailyMetrics.active_users).label("users"),
                func.sum(AdoptionDailyMetrics.total_conversations).label("conversations"),
                func.sum(AdoptionDailyMetrics.input_tokens + AdoptionDailyMetrics.output_tokens).label("tokens")
            ).filter(
                AdoptionDailyMetrics.customer_id == customer_id
            ).first()
            
            # Determine if this is the user's own tenant
            is_own = customer_id == self.current_user.customer_id
            
            # Determine if adoption is enabled (has a provider configured)
            has_adoption = provider is not None and provider.is_adoption_source
            
            # Build metrics summary with top_gpts
            metrics_summary = None
            if totals.days and totals.days > 0:
                # Aggregate top_gpts from recent metrics
                recent_metrics = self.db.query(AdoptionDailyMetrics).filter(
                    AdoptionDailyMetrics.customer_id == customer_id
                ).order_by(AdoptionDailyMetrics.metric_date.desc()).limit(30).all()
                
                # Aggregate GPT usage across days
                gpt_data: Dict[str, Dict] = {}
                for m in recent_metrics:
                    if m.top_gpts:
                        for gpt in m.top_gpts:
                            if isinstance(gpt, dict):
                                gpt_id = gpt.get("id", gpt.get("name", "unknown"))
                                if gpt_id not in gpt_data:
                                    gpt_data[gpt_id] = {
                                        "id": gpt.get("id", ""),
                                        "name": gpt.get("name", "Unknown"),
                                        "uses": 0,
                                        "users": gpt.get("users", 0),
                                        "conversations": gpt.get("conversations", 0),
                                        "creator_email": gpt.get("creator_email", "")
                                    }
                                gpt_data[gpt_id]["uses"] += gpt.get("uses", 0)
                
                # Sort by uses and take top 10
                top_gpts = sorted(
                    list(gpt_data.values()),
                    key=lambda x: x["uses"],
                    reverse=True
                )[:10]
                
                metrics_summary = {
                    "total_active_users": totals.users or 0,
                    "total_conversations": totals.conversations or 0,
                    "total_messages": 0,  # Would need to aggregate
                    "total_tokens": totals.tokens or 0,
                    "avg_daily_users": (totals.users or 0) / max(totals.days, 1),
                    "avg_conversations_per_user": (totals.conversations or 0) / max(totals.users or 1, 1),
                    "top_gpts": top_gpts
                }
            
            results.append({
                # Frontend-expected fields
                "company_id": customer_id,
                "company_name": customer.display_name if customer else customer_id,
                "is_own_tenant": is_own,
                "has_adoption_enabled": has_adoption,
                "last_sync_at": provider.updated_at if provider else None,
                "metrics_summary": metrics_summary,
                # Additional tracking fields
                "provider_type": latest.source_type if latest else None,
                "total_days_tracked": totals.days or 0,
                "total_active_users": totals.users or 0,
                "total_conversations": totals.conversations or 0,
                "total_tokens": totals.tokens or 0,
                "is_syncing": False,  # Would check celery task status
                "sync_error": None
            })
        
        return results
    
    def _calculate_summary(self, metrics: List[AdoptionDailyMetrics]) -> Dict[str, Any]:
        """Calculate summary statistics from metrics."""
        if not metrics:
            return self._empty_summary()
        
        total_users = sum(m.active_users or 0 for m in metrics)
        total_conversations = sum(m.total_conversations or 0 for m in metrics)
        total_messages = sum(m.total_messages or 0 for m in metrics)
        total_tokens = sum((m.input_tokens or 0) + (m.output_tokens or 0) for m in metrics)
        # GPT adoption metrics
        total_gpt_conversations = sum(getattr(m, 'gpt_conversations', 0) or 0 for m in metrics)
        total_base_conversations = sum(getattr(m, 'base_conversations', 0) or 0 for m in metrics)
        
        unique_dates = len(set(m.metric_date for m in metrics))
        
        # Aggregate model usage
        model_counts: Dict[str, int] = {}
        gpt_counts: Dict[str, int] = {}
        
        for m in metrics:
            if m.model_breakdown:
                for model, count in m.model_breakdown.items():
                    model_counts[model] = model_counts.get(model, 0) + count
            if m.top_gpts:
                # top_gpts is a list of dicts: [{"name": "...", "uses": 100}]
                for gpt_entry in m.top_gpts:
                    if isinstance(gpt_entry, dict):
                        name = gpt_entry.get("name", "Unknown")
                        uses = gpt_entry.get("uses", 0)
                        gpt_counts[name] = gpt_counts.get(name, 0) + uses
        
        top_models = sorted(
            [{"model": k, "count": v} for k, v in model_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]
        
        top_gpts = sorted(
            [{"name": k, "count": v} for k, v in gpt_counts.items()],
            key=lambda x: x["count"],
            reverse=True
        )[:10]
        
        return {
            "total_active_users": total_users,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "avg_daily_users": total_users / unique_dates if unique_dates > 0 else 0,
            "avg_daily_conversations": total_conversations / unique_dates if unique_dates > 0 else 0,
            "gpt_conversations": total_gpt_conversations,
            "base_conversations": total_base_conversations,
            "gpt_adoption_rate": (total_gpt_conversations / total_conversations * 100) if total_conversations > 0 else 0,
            "top_models": top_models,
            "top_gpts": top_gpts
        }
    
    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "total_active_users": 0,
            "total_conversations": 0,
            "total_messages": 0,
            "total_tokens": 0,
            "avg_daily_users": 0.0,
            "avg_daily_conversations": 0.0,
            "gpt_conversations": 0,
            "base_conversations": 0,
            "gpt_adoption_rate": 0.0,
            "top_models": [],
            "top_gpts": []
        }
    
    # =========================================================================
    # Granular GPT Analytics
    # =========================================================================
    
    def get_top_gpts(
        self,
        customer_ids: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get top GPTs by usage from granular conversation data.
        
        This queries the adoption_gpts and adoption_conversations tables
        for accurate per-GPT metrics.
        
        Args:
            customer_ids: Filter to specific companies (None = all accessible)
            start_date: Filter conversations from this date
            end_date: Filter conversations until this date
            limit: Max GPTs to return
            
        Returns:
            List of GPT info dicts with usage metrics
        """
        # Determine which companies to query
        accessible = self.get_accessible_companies()
        
        if customer_ids:
            query_companies = [c for c in customer_ids if c in accessible]
            if not query_companies:
                return []
        else:
            query_companies = accessible
        
        # Build join conditions including date filters
        # Date filters must be in the JOIN to properly count only matching conversations
        join_conditions = [
            AdoptionConversation.gpt_id == AdoptionGPT.id,
            AdoptionConversation.customer_id.in_(query_companies)
        ]
        
        if start_date:
            join_conditions.append(AdoptionConversation.conversation_created_at >= start_date)
        if end_date:
            join_conditions.append(AdoptionConversation.conversation_created_at <= end_date)
        
        # Build query: aggregate conversations per GPT
        query = self.db.query(
            AdoptionGPT.id,
            AdoptionGPT.customer_id,
            AdoptionGPT.external_gpt_id,
            AdoptionGPT.name,
            AdoptionGPT.description,
            AdoptionGPT.short_url,
            AdoptionGPT.creator_email,
            AdoptionGPT.creator_name,
            AdoptionGPT.visibility,
            func.count(AdoptionConversation.id).label('conversation_count'),
            func.coalesce(func.sum(AdoptionConversation.user_message_count), 0).label('message_count'),
            func.count(func.distinct(AdoptionConversation.user_external_id)).label('unique_users')
        ).outerjoin(
            AdoptionConversation,
            and_(*join_conditions)
        ).filter(
            AdoptionGPT.customer_id.in_(query_companies),
            AdoptionGPT.is_active == True
        )
        
        # Group and order
        results = query.group_by(
            AdoptionGPT.id,
            AdoptionGPT.customer_id,
            AdoptionGPT.external_gpt_id,
            AdoptionGPT.name,
            AdoptionGPT.description,
            AdoptionGPT.short_url,
            AdoptionGPT.creator_email,
            AdoptionGPT.creator_name,
            AdoptionGPT.visibility
        ).order_by(
            func.count(AdoptionConversation.id).desc()
        ).limit(limit).all()
        
        # Get customer names for display
        customer_names = {}
        if len(query_companies) > 1:
            customers = self.db.query(Customer).filter(
                Customer.customer_id.in_(query_companies)
            ).all()
            customer_names = {c.customer_id: c.display_name or c.customer_id for c in customers}
        
        # Format results - include all GPTs, even those with 0 usage
        gpts = []
        for row in results:
            gpts.append({
                "id": row.external_gpt_id,
                "name": row.name or row.external_gpt_id,
                "description": row.description,
                "uses": row.message_count or 0,
                "users": row.unique_users or 0,
                "conversations": row.conversation_count or 0,
                "creator_email": row.creator_email,
                "creator_name": row.creator_name,
                "short_url": row.short_url,
                "company_id": row.customer_id,
                "company_name": customer_names.get(row.customer_id, row.customer_id) if len(query_companies) > 1 else None
            })
        
        return gpts
    
    def get_users_for_gpt(
        self,
        gpt_external_id: str,
        customer_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get users who have interacted with a specific GPT.
        
        This enables user outreach for feedback collection.
        
        Args:
            gpt_external_id: External GPT ID (g-xxx)
            customer_id: Optional filter to specific company
            limit: Max users to return
            
        Returns:
            List of user info with interaction metrics
        """
        # Find the GPT
        gpt_query = self.db.query(AdoptionGPT).filter(
            AdoptionGPT.external_gpt_id == gpt_external_id
        )
        
        if customer_id:
            gpt_query = gpt_query.filter(AdoptionGPT.customer_id == customer_id)
        
        gpt = gpt_query.first()
        if not gpt:
            return []
        
        # Check access
        accessible = self.get_accessible_companies()
        if gpt.customer_id not in accessible:
            return []
        
        # Get user interactions for this GPT
        interactions = self.db.query(AdoptionUserGPTInteraction).filter(
            AdoptionUserGPTInteraction.gpt_id == gpt.id
        ).order_by(
            AdoptionUserGPTInteraction.total_messages.desc()
        ).limit(limit).all()
        
        return [
            {
                "user_id": i.user_external_id,
                "user_email": i.user_email,
                "total_conversations": i.total_conversations,
                "total_messages": i.total_messages,
                "first_interaction_at": i.first_interaction_at.isoformat() if i.first_interaction_at else None,
                "last_interaction_at": i.last_interaction_at.isoformat() if i.last_interaction_at else None
            }
            for i in interactions
        ]
    
    def get_top_users(
        self,
        customer_ids: Optional[List[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get top users by ChatGPT usage from conversation data.
        
        Args:
            customer_ids: Filter to specific companies (None = all accessible)
            start_date: Filter conversations from this date
            end_date: Filter conversations until this date
            limit: Max users to return
            
        Returns:
            List of user info dicts with usage metrics
        """
        # Determine which companies to query
        accessible = self.get_accessible_companies()
        
        if customer_ids:
            query_companies = [c for c in customer_ids if c in accessible]
            if not query_companies:
                return []
        else:
            query_companies = accessible
        
        # Build query: aggregate conversations per user
        query = self.db.query(
            AdoptionConversation.customer_id,
            AdoptionConversation.user_external_id,
            AdoptionConversation.user_email,
            func.count(AdoptionConversation.id).label('conversation_count'),
            func.sum(AdoptionConversation.user_message_count).label('message_count'),
            func.count(func.distinct(AdoptionConversation.gpt_id)).label('gpts_used')
        ).filter(
            AdoptionConversation.customer_id.in_(query_companies)
        )
        
        # Apply date filters
        if start_date:
            query = query.filter(AdoptionConversation.conversation_created_at >= start_date)
        if end_date:
            query = query.filter(AdoptionConversation.conversation_created_at <= end_date)
        
        # Group by user
        results = query.group_by(
            AdoptionConversation.customer_id,
            AdoptionConversation.user_external_id,
            AdoptionConversation.user_email
        ).order_by(
            func.sum(AdoptionConversation.user_message_count).desc()
        ).limit(limit).all()
        
        # Get customer names for display
        customer_names = {}
        if len(query_companies) > 1:
            customers = self.db.query(Customer).filter(
                Customer.customer_id.in_(query_companies)
            ).all()
            customer_names = {c.customer_id: c.display_name or c.customer_id for c in customers}
        
        # Format results
        users = []
        for row in results:
            users.append({
                "user_email": row.user_email or "Unknown",
                "user_external_id": row.user_external_id,
                "total_conversations": row.conversation_count or 0,
                "total_messages": row.message_count or 0,
                "gpts_used": row.gpts_used or 0,
                "company_id": row.customer_id,
                "company_name": customer_names.get(row.customer_id, row.customer_id) if len(query_companies) > 1 else None
            })
        
        return users
    
    # =========================================================================
    # Sharing Operations
    # =========================================================================
    
    def get_shares(self) -> Tuple[List[AdoptionDataShare], List[AdoptionDataShare]]:
        """
        Get shares for current tenant.
        
        Returns:
            Tuple of (shares_given, shares_received)
        """
        customer_id = self.current_user.customer_id
        
        # Shares where current tenant is source (giving access)
        shares_given = self.db.query(AdoptionDataShare).filter(
            AdoptionDataShare.source_customer_id == customer_id
        ).order_by(AdoptionDataShare.created_at.desc()).all()
        
        # Shares where current tenant is target (receiving access)
        shares_received = self.db.query(AdoptionDataShare).filter(
            AdoptionDataShare.target_customer_id == customer_id
        ).order_by(AdoptionDataShare.created_at.desc()).all()
        
        return shares_given, shares_received
    
    def create_share(
        self,
        target_customer_id: str,
        share_level: str = "read",
        notes: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> AdoptionDataShare:
        """
        Create a new adoption data share.
        
        Args:
            target_customer_id: Company to share with
            share_level: 'read' or 'admin'
            notes: Optional notes
            expires_at: Optional expiration
            
        Returns:
            Created share
        """
        source_customer_id = self.current_user.customer_id
        
        # Validate target exists
        target = self.db.query(Customer).filter(
            Customer.customer_id == target_customer_id,
            Customer.is_active == True
        ).first()
        
        if not target:
            raise ValueError(f"Target company '{target_customer_id}' not found or inactive")
        
        # Check for existing share
        existing = self.db.query(AdoptionDataShare).filter(
            AdoptionDataShare.source_customer_id == source_customer_id,
            AdoptionDataShare.target_customer_id == target_customer_id
        ).first()
        
        if existing:
            raise ValueError(f"Share already exists for '{target_customer_id}'")
        
        # Validate share level
        if not AdoptionShareLevel.is_valid(share_level):
            raise ValueError(f"Invalid share level: {share_level}")
        
        # Create share
        share = AdoptionDataShare(
            source_customer_id=source_customer_id,
            target_customer_id=target_customer_id,
            share_level=share_level,
            notes=notes,
            expires_at=expires_at,
            created_by=self.current_user.user_id,
            is_enabled=True
        )
        
        self.db.add(share)
        self.db.commit()
        self.db.refresh(share)
        
        logger.info(
            f"Created adoption share: {source_customer_id} -> {target_customer_id} "
            f"(level={share_level}, user={self.current_user.user_id})"
        )
        
        return share
    
    def update_share(
        self,
        share_id: int,
        share_level: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        notes: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> AdoptionDataShare:
        """Update an existing share."""
        share = self.db.query(AdoptionDataShare).filter(
            AdoptionDataShare.id == share_id,
            AdoptionDataShare.source_customer_id == self.current_user.customer_id
        ).first()
        
        if not share:
            raise ValueError(f"Share {share_id} not found or not owned by current tenant")
        
        if share_level is not None:
            if not AdoptionShareLevel.is_valid(share_level):
                raise ValueError(f"Invalid share level: {share_level}")
            share.share_level = share_level
        
        if is_enabled is not None:
            share.is_enabled = is_enabled
        
        if notes is not None:
            share.notes = notes
        
        if expires_at is not None:
            share.expires_at = expires_at
        
        self.db.commit()
        self.db.refresh(share)
        
        logger.info(f"Updated adoption share {share_id} (user={self.current_user.user_id})")
        
        return share
    
    def delete_share(self, share_id: int) -> bool:
        """Delete (revoke) a share."""
        share = self.db.query(AdoptionDataShare).filter(
            AdoptionDataShare.id == share_id,
            AdoptionDataShare.source_customer_id == self.current_user.customer_id
        ).first()
        
        if not share:
            raise ValueError(f"Share {share_id} not found or not owned by current tenant")
        
        target = share.target_customer_id
        self.db.delete(share)
        self.db.commit()
        
        logger.info(
            f"Deleted adoption share {share_id}: {self.current_user.customer_id} -> {target} "
            f"(user={self.current_user.user_id})"
        )
        
        return True
    
    # =========================================================================
    # Provider Configuration
    # =========================================================================
    
    def get_adoption_providers(self) -> List[CustomerAIProvider]:
        """Get AI providers configured for adoption tracking."""
        customer_id = self.current_user.customer_id
        
        return self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.customer_id == customer_id,
            CustomerAIProvider.is_adoption_source == True
        ).all()
    
    def set_adoption_source(self, provider_id: int, is_source: bool = True) -> CustomerAIProvider:
        """Mark a provider configuration as an adoption source."""
        provider = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.id == provider_id,
            CustomerAIProvider.customer_id == self.current_user.customer_id
        ).first()
        
        if not provider:
            raise ValueError(f"Provider {provider_id} not found or not owned by current tenant")
        
        provider.is_adoption_source = is_source
        self.db.commit()
        self.db.refresh(provider)
        
        logger.info(
            f"Set adoption source for provider {provider_id}: {is_source} "
            f"(user={self.current_user.user_id})"
        )
        
        return provider
    
    # =========================================================================
    # Dashboard Helpers
    # =========================================================================
    
    def get_dashboard_widgets(self, days: int = 30) -> Dict[str, Any]:
        """Get pre-computed dashboard widget data."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        metrics, summary = self.get_metrics(
            start_date=start_date,
            end_date=end_date
        )
        
        # Usage trend by date
        trend_by_date: Dict[str, Dict[str, int]] = {}
        for m in metrics:
            date_str = m.metric_date.isoformat()
            if date_str not in trend_by_date:
                trend_by_date[date_str] = {
                    "active_users": 0,
                    "conversations": 0,
                    "tokens": 0
                }
            trend_by_date[date_str]["active_users"] += m.active_users or 0
            trend_by_date[date_str]["conversations"] += m.total_conversations or 0
            trend_by_date[date_str]["tokens"] += (m.input_tokens or 0) + (m.output_tokens or 0)
        
        usage_trend = [
            {"date": d, **v} for d, v in sorted(trend_by_date.items())
        ]
        
        # Model breakdown
        total_model_count = sum(m.get("count", 0) for m in summary["top_models"])
        model_breakdown = [
            {
                "model": m["model"],
                "count": m["count"],
                "percentage": (m["count"] / total_model_count * 100) if total_model_count > 0 else 0
            }
            for m in summary["top_models"]
        ]
        
        # Company comparison
        company_metrics: Dict[str, Dict[str, Any]] = {}
        for m in metrics:
            if m.customer_id not in company_metrics:
                company_metrics[m.customer_id] = {
                    "customer_id": m.customer_id,
                    "customer_name": m.customer_id,  # Would need join for name
                    "active_users": 0,
                    "conversations": 0,
                    "tokens": 0
                }
            company_metrics[m.customer_id]["active_users"] += m.active_users or 0
            company_metrics[m.customer_id]["conversations"] += m.total_conversations or 0
            company_metrics[m.customer_id]["tokens"] += (m.input_tokens or 0) + (m.output_tokens or 0)
        
        company_comparison = sorted(
            company_metrics.values(),
            key=lambda x: x["tokens"],
            reverse=True
        )
        
        return {
            "usage_trend": usage_trend,
            "model_breakdown": model_breakdown,
            "company_comparison": company_comparison,
            "period": f"{days}d"
        }

