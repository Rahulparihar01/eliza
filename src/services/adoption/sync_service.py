"""
Adoption Sync Service.

Orchestrates the sync of adoption metrics from external providers
(OpenAI, Anthropic, etc.) into the local database.

Stores both:
- Aggregated daily metrics (AdoptionDailyMetrics)
- Granular data (GPTs, Conversations, UserGPTInteractions)
"""

import logging
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models.adoption import (
    AdoptionSyncConfig,
    AdoptionDailyMetrics,
    AdoptionGPT,
    AdoptionConversation,
    AdoptionUserGPTInteraction
)
from src.models.customer import Customer, CustomerAIProvider
from src.utils.encryption import decrypt_value
from src.services.adoption.openai_compliance_client import (
    OpenAIComplianceClient,
    DailyUsageSummary,
    GPTSummary
)

logger = logging.getLogger(__name__)


COMPLIANCE_API_LAG_TOLERANCE_DAYS = 2


class AdoptionSyncService:
    """
    Service for syncing adoption metrics from external providers.
    
    Responsibilities:
    - Fetch provider configurations marked for adoption
    - Connect to external APIs (OpenAI Compliance, etc.)
    - Transform and store metrics in AdoptionDailyMetrics
    - Handle incremental syncs (only fetch missing days)
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_adoption_providers(
        self,
        customer_id: Optional[str] = None
    ) -> List[CustomerAIProvider]:
        """
        Get all provider configurations marked for adoption tracking.
        
        Args:
            customer_id: Optional filter by customer
            
        Returns:
            List of CustomerAIProvider with is_adoption_source=True
        """
        query = self.db.query(CustomerAIProvider).filter(
            CustomerAIProvider.is_adoption_source == True,
            CustomerAIProvider.is_enabled == True
        )
        
        if customer_id:
            query = query.filter(CustomerAIProvider.customer_id == customer_id)
        
        return query.all()
    
    def get_credentials(self, provider: CustomerAIProvider) -> Optional[Dict[str, str]]:
        """
        Decrypt and return credentials for a provider.
        
        For ChatGPT Enterprise, credentials should include:
        - api_key: The sk-proj-XXX key with compliance_export scope
        - workspace_id: The ChatGPT Enterprise workspace UUID
        
        Args:
            provider: CustomerAIProvider configuration
            
        Returns:
            Dict with credentials or None
        """
        if not provider.api_key_encrypted:
            logger.warning(f"Provider {provider.id} has no encrypted API key")
            return None
        
        try:
            credentials = json.loads(decrypt_value(provider.api_key_encrypted))
            return credentials
        except Exception as e:
            logger.error(f"Failed to decrypt credentials for provider {provider.id}: {e}")
            return None
    
    def get_api_key(self, provider: CustomerAIProvider) -> Optional[str]:
        """
        Decrypt and return the API key for a provider.
        
        Args:
            provider: CustomerAIProvider configuration
            
        Returns:
            Decrypted API key or None
        """
        credentials = self.get_credentials(provider)
        return credentials.get("api_key") if credentials else None
    
    def get_last_sync_date(
        self,
        customer_id: str,
        provider_type: str
    ) -> Optional[date]:
        """
        Get the most recent sync date for a customer/provider.
        
        Returns:
            Last synced date or None if no data exists
        """
        result = self.db.query(AdoptionDailyMetrics.metric_date).filter(
            AdoptionDailyMetrics.customer_id == customer_id,
            AdoptionDailyMetrics.source_type == provider_type
        ).order_by(AdoptionDailyMetrics.metric_date.desc()).first()
        
        return result[0] if result else None

    def get_or_create_sync_config(self, customer_id: str) -> AdoptionSyncConfig:
        """Return tenant sync config, creating a default if missing."""
        config = self.db.query(AdoptionSyncConfig).filter(
            AdoptionSyncConfig.customer_id == customer_id
        ).first()

        if config:
            return config

        config = AdoptionSyncConfig(
            customer_id=customer_id,
            initial_sync_start_date=date.today() - timedelta(days=30),
            schedule_enabled=False,
            schedule_cron=None,
        )
        self.db.add(config)
        self.db.flush()
        return config

    def check_consistency(self, customer_id: str, provider_type: str) -> Dict[str, Any]:
        """Check whether conversation and daily metric boundaries are consistent.

        A gap of up to ``COMPLIANCE_API_LAG_TOLERANCE_DAYS`` days is tolerated
        because the OpenAI Compliance API can take 1-2 days to make daily
        summary data available.
        """
        latest_metric_date = self.get_last_sync_date(customer_id, provider_type)
        latest_conversation_ts = self.db.query(
            func.max(AdoptionConversation.conversation_created_at)
        ).filter(
            AdoptionConversation.customer_id == customer_id
        ).scalar()
        latest_conversation_date = (
            latest_conversation_ts.date() if latest_conversation_ts else None
        )

        is_consistent = True
        gap_days = 0
        if latest_conversation_date and latest_metric_date:
            gap_days = (latest_conversation_date - latest_metric_date).days
            is_consistent = gap_days <= COMPLIANCE_API_LAG_TOLERANCE_DAYS

        return {
            "is_consistent": is_consistent,
            "latest_metric_date": latest_metric_date.isoformat() if latest_metric_date else None,
            "latest_conversation_date": latest_conversation_date.isoformat() if latest_conversation_date else None,
            "gap_days": gap_days,
        }

    def cleanup_partial_sync(self, customer_id: str, provider_type: str) -> Dict[str, Any]:
        """Delete conversations beyond last complete metric date."""
        last_complete_metric_date = self.get_last_sync_date(customer_id, provider_type)
        if not last_complete_metric_date:
            return {
                "cleanup_performed": False,
                "reason": "No complete metric baseline found",
                "conversations_deleted": 0,
            }

        cutoff = datetime.combine(last_complete_metric_date + timedelta(days=1), datetime.min.time())
        deleted = self.db.query(AdoptionConversation).filter(
            AdoptionConversation.customer_id == customer_id,
            AdoptionConversation.conversation_created_at >= cutoff,
        ).delete(synchronize_session=False)
        self.db.flush()

        return {
            "cleanup_performed": deleted > 0,
            "conversations_deleted": deleted,
            "cleanup_cutoff_date": last_complete_metric_date.isoformat(),
        }
    
    async def sync_provider(
        self,
        provider: CustomerAIProvider,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        force: bool = False,
        sync_run_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync adoption metrics for a single provider.
        
        Args:
            provider: Provider configuration
            start_date: Start date (defaults to last sync + 1 or 30 days ago)
            end_date: End date (defaults to yesterday)
            force: If True, re-sync existing dates
            
        Returns:
            Dict with sync results
        """
        customer_id = provider.customer_id
        provider_type = provider.provider_name
        sync_run_id = sync_run_id or str(uuid.uuid4())
        
        logger.info(
            f"Starting adoption sync: customer={customer_id}, provider={provider_type}"
        )
        
        # Get credentials
        credentials = self.get_credentials(provider)
        if not credentials:
            return {
                "success": False,
                "error": "No credentials available",
                "records_synced": 0
            }
        
        api_key = credentials.get("api_key")
        if not api_key:
            return {
                "success": False,
                "error": "No API key in credentials",
                "records_synced": 0
            }
        
        # Pre-sync integrity check and auto-recovery when we detect gap.
        integrity_result = self.check_consistency(customer_id, provider_type)
        recovery_result = None
        if not force and not integrity_result["is_consistent"]:
            logger.warning(
                f"Inconsistent adoption sync state detected for {customer_id}/{provider_type}: "
                f"gap_days={integrity_result['gap_days']}"
            )
            recovery_result = self.cleanup_partial_sync(customer_id, provider_type)
            self.db.commit()

        # Determine date range
        if end_date is None:
            end_date = date.today() - timedelta(days=1)  # Yesterday
        
        if start_date is None:
            last_sync = self.get_last_sync_date(customer_id, provider_type)
            if last_sync and not force:
                start_date = last_sync + timedelta(days=1)
            else:
                config = self.get_or_create_sync_config(customer_id)
                start_date = config.initial_sync_start_date
        
        if start_date > end_date:
            logger.info(f"No new dates to sync for {customer_id}/{provider_type}")
            return {
                "success": True,
                "message": "Already up to date",
                "records_synced": 0
            }
        
        # Create client based on provider type
        if provider_type == "openai":
            # Get workspace_id from model field or credentials fallback
            workspace_id = provider.chatgpt_workspace_id or credentials.get("workspace_id")
            if not workspace_id:
                return {
                    "success": False,
                    "error": "No chatgpt_workspace_id configured. Set it on the provider or in credentials.",
                    "records_synced": 0
                }
            
            return await self._sync_openai(
                provider=provider,
                api_key=api_key,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
                sync_run_id=sync_run_id,
                integrity_result=integrity_result,
                recovery_result=recovery_result
            )
        else:
            logger.warning(f"Unsupported provider type for adoption: {provider_type}")
            return {
                "success": False,
                "error": f"Provider type '{provider_type}' not supported for adoption sync",
                "records_synced": 0
            }
    
    async def _sync_openai(
        self,
        provider: CustomerAIProvider,
        api_key: str,
        workspace_id: str,
        start_date: date,
        end_date: date,
        sync_run_id: str,
        integrity_result: Optional[Dict[str, Any]] = None,
        recovery_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sync OpenAI/ChatGPT Enterprise usage data via Compliance API.
        
        This syncs:
        1. GPT metadata (adoption_gpts)
        2. Conversation records (adoption_conversations) - no content
        3. User-GPT interactions (adoption_user_gpt_interactions)
        4. Aggregated daily metrics (adoption_daily_metrics)
        
        Args:
            provider: Provider configuration
            api_key: Decrypted API key (sk-proj-XXX with compliance_export scope)
            workspace_id: ChatGPT Enterprise workspace UUID
            start_date: Start date
            end_date: End date
            
        Returns:
            Dict with sync results
        """
        customer_id = provider.customer_id
        client = OpenAIComplianceClient(
            api_key=api_key,
            workspace_id=workspace_id
        )
        
        records_synced = 0
        gpts_synced = 0
        conversations_synced = 0
        interactions_updated = 0
        errors = []
        
        try:
            # Test connection first
            if not await client.test_connection():
                return {
                    "success": False,
                    "error": f"Failed to connect to ChatGPT Compliance API. Check API key and workspace_id ({workspace_id})",
                    "records_synced": 0
                }
            
            # Step 1: Sync all GPTs (these are global, not per-day)
            logger.info(f"Syncing GPTs for {customer_id}...")
            try:
                gpts = await client.get_all_gpts()
                gpt_lookup: Dict[str, int] = {}  # external_id -> internal_id
                gpt_metadata_lookup: Dict[str, GPTSummary] = {gpt.id: gpt for gpt in gpts}
                
                for gpt_info in gpts:
                    gpt_record = self._upsert_gpt(customer_id, gpt_info)
                    gpt_lookup[gpt_info.id] = gpt_record.id
                    gpts_synced += 1
                
                self.db.flush()  # Ensure GPT IDs are available
                logger.info(f"Synced {gpts_synced} GPTs for {customer_id}")
            except Exception as e:
                error_msg = f"Failed to sync GPTs: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                gpt_lookup = {}
                gpt_metadata_lookup = {}
            
            # Step 2: Sync conversations with batching (memory-safe pagination)
            # Fetch ALL conversations since start_date in a single pass (more efficient)
            logger.info(f"Syncing conversations for {customer_id} ({start_date} to {end_date})...")
            try:
                conversations_synced = await self._sync_all_conversations(
                    client=client,
                    customer_id=customer_id,
                    since_date=start_date,
                    until_date=end_date,
                    gpt_lookup=gpt_lookup,
                    sync_run_id=sync_run_id,
                    batch_size=100
                )
            except Exception as e:
                error_msg = f"Failed to sync conversations: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
            
            logger.info(f"Synced {conversations_synced} total conversations for {customer_id}")
            
            # Step 3: Update user-GPT interaction summaries
            logger.info(f"Updating user-GPT interactions for {customer_id}...")
            try:
                interactions_updated = self._update_user_gpt_interactions(customer_id)
                logger.info(f"Updated {interactions_updated} user-GPT interaction records for {customer_id}")
            except Exception as e:
                error_msg = f"Failed to update user-GPT interactions: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
            
            # Step 4: Sync daily aggregated metrics (one day at a time - memory efficient)
            logger.info(f"Syncing daily metrics for {customer_id}...")
            current_date = start_date
            while current_date <= end_date:
                try:
                    summary = await client.get_daily_summary(
                        current_date,
                        gpt_metadata=gpt_metadata_lookup
                    )
                    
                    # Upsert the metrics record
                    self._upsert_daily_metrics(
                        customer_id=customer_id,
                        provider_type="openai",
                        summary=summary,
                        sync_run_id=sync_run_id
                    )
                    records_synced += 1
                    
                    logger.debug(
                        f"Synced {current_date} for {customer_id}: "
                        f"users={summary.active_users}, convos={summary.total_conversations}"
                    )
                    
                except Exception as e:
                    error_msg = f"Failed to sync {current_date}: {e}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                
                current_date += timedelta(days=1)
            
            # Commit all changes
            self.db.commit()
            
            logger.info(
                f"Adoption sync completed: customer={customer_id}, "
                f"gpts={gpts_synced}, convos={conversations_synced}, "
                f"daily_records={records_synced}, errors={len(errors)}"
            )
            
            return {
                "success": len(errors) == 0,
                "sync_run_id": sync_run_id,
                "records_synced": records_synced,
                "gpts_synced": gpts_synced,
                "conversations_synced": conversations_synced,
                "interactions_updated": interactions_updated,
                "integrity_check": integrity_result,
                "recovery": recovery_result,
                "errors": errors if errors else None,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Adoption sync failed for {customer_id}: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e),
                "sync_run_id": sync_run_id,
                "records_synced": records_synced
            }
        finally:
            await client.close()
    
    def _upsert_daily_metrics(
        self,
        customer_id: str,
        provider_type: str,
        summary: DailyUsageSummary,
        sync_run_id: Optional[str] = None
    ) -> AdoptionDailyMetrics:
        """
        Insert or update daily metrics record.
        
        Args:
            customer_id: Customer ID
            provider_type: Provider type (openai, anthropic, etc.)
            summary: Aggregated daily summary
            
        Returns:
            Created or updated AdoptionDailyMetrics
        """
        # Check for existing record
        existing = self.db.query(AdoptionDailyMetrics).filter(
            AdoptionDailyMetrics.customer_id == customer_id,
            AdoptionDailyMetrics.source_type == provider_type,
            AdoptionDailyMetrics.metric_date == summary.date
        ).first()
        
        if existing:
            # Update existing
            existing.active_users = summary.active_users
            existing.total_conversations = summary.total_conversations
            existing.total_messages = summary.total_messages
            existing.gpt_conversations = summary.gpt_conversations
            existing.base_conversations = summary.base_conversations
            existing.unique_gpts = summary.unique_gpts
            existing.input_tokens = summary.input_tokens
            existing.output_tokens = summary.output_tokens
            existing.model_breakdown = summary.model_breakdown
            existing.top_gpts = summary.gpt_breakdown
            existing.sync_metadata = {"synced_at": datetime.now(timezone.utc).isoformat()}
            existing.sync_run_id = sync_run_id
            return existing
        else:
            # Create new
            metrics = AdoptionDailyMetrics(
                customer_id=customer_id,
                source_type=provider_type,
                metric_date=summary.date,
                active_users=summary.active_users,
                total_conversations=summary.total_conversations,
                total_messages=summary.total_messages,
                gpt_conversations=summary.gpt_conversations,
                base_conversations=summary.base_conversations,
                unique_gpts=summary.unique_gpts,
                input_tokens=summary.input_tokens,
                output_tokens=summary.output_tokens,
                model_breakdown=summary.model_breakdown,
                top_gpts=summary.gpt_breakdown,
                sync_metadata={"synced_at": datetime.now(timezone.utc).isoformat()},
                sync_run_id=sync_run_id
            )
            self.db.add(metrics)
            return metrics
    
    # =========================================================================
    # Batched Conversation Sync
    # =========================================================================
    
    async def _sync_conversations_batched(
        self,
        client: OpenAIComplianceClient,
        customer_id: str,
        target_date: date,
        gpt_lookup: Dict[str, int],
        sync_run_id: Optional[str] = None,
        batch_size: int = 100
    ) -> int:
        """
        Sync conversations for a specific day with pagination.
        
        Commits after each batch to keep memory bounded. Only stores
        conversations that have activity on the target date.
        
        Args:
            client: OpenAI Compliance API client
            customer_id: Customer ID
            target_date: The specific date to sync
            gpt_lookup: Mapping of external GPT ID to internal GPT ID
            batch_size: Number of conversations per API call
            
        Returns:
            Number of conversations synced for this day
        """
        # Calculate timestamp range for the target date
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = start_of_day + timedelta(days=1)
        since_timestamp = int(start_of_day.timestamp())
        until_timestamp = int(end_of_day.timestamp())
        
        after = None
        total_synced = 0
        
        while True:
            # Fetch a page of conversations updated since start of day
            result = await client.list_conversations(
                limit=batch_size,
                after=after,
                since_timestamp=since_timestamp
            )
            
            conversations = result.get("data", [])
            batch_synced = 0
            
            for conv_data in conversations:
                # Only process if conversation has activity ON this specific day
                if self._has_activity_on_date(conv_data, since_timestamp, until_timestamp):
                    self._upsert_conversation(
                        customer_id,
                        conv_data,
                        gpt_lookup,
                        sync_run_id=sync_run_id
                    )
                    batch_synced += 1
            
            # Commit this batch to release memory
            if batch_synced > 0:
                self.db.flush()
            
            total_synced += batch_synced
            
            # Check if more pages exist
            if not result.get("has_more"):
                break
            
            after = result.get("last_id")
        
        return total_synced
    
    async def _sync_all_conversations(
        self,
        client: OpenAIComplianceClient,
        customer_id: str,
        since_date: date,
        until_date: date,
        gpt_lookup: Dict[str, int],
        sync_run_id: Optional[str] = None,
        batch_size: int = 100
    ) -> int:
        """
        Sync ALL conversations since a date in a single pass.
        
        This is more efficient than day-by-day syncing because the OpenAI API
        doesn't support an until_timestamp parameter. We fetch once and filter
        conversations by their created_at date.
        
        Args:
            client: OpenAI Compliance API client
            customer_id: Customer ID
            since_date: Start date for sync
            until_date: End date for sync (inclusive)
            gpt_lookup: Mapping of external GPT ID to internal GPT ID
            batch_size: Number of conversations per API call
            
        Returns:
            Number of conversations synced
        """
        # Calculate timestamp for the start of the since_date
        start_of_period = datetime.combine(since_date, datetime.min.time())
        since_timestamp = int(start_of_period.timestamp())
        
        # End of until_date (next day at midnight)
        end_of_period = datetime.combine(until_date + timedelta(days=1), datetime.min.time())
        until_timestamp = int(end_of_period.timestamp())
        
        after = None
        total_synced = 0
        batch_count = 0
        
        logger.info(f"Fetching all conversations since {since_date}...")
        
        while True:
            # Fetch a page of conversations
            result = await client.list_conversations(
                limit=batch_size,
                after=after,
                since_timestamp=since_timestamp
            )
            
            conversations = result.get("data", [])
            logger.info(f"Listed {len(conversations)} conversations, has_more={result.get('has_more')}")
            
            batch_synced = 0
            
            for conv_data in conversations:
                # Check if conversation is within the date range we want
                conv_created_at = conv_data.get("created_at")
                conv_updated_at = conv_data.get("updated_at")
                
                # We want conversations that were either created or have activity within our range
                # Since we're syncing ALL data, just store every conversation
                # The _upsert_conversation will handle duplicates via upsert
                self._upsert_conversation(
                    customer_id,
                    conv_data,
                    gpt_lookup,
                    sync_run_id=sync_run_id
                )
                batch_synced += 1
            
            # Commit this batch to release memory
            if batch_synced > 0:
                self.db.flush()
                self.db.commit()  # Actually commit to persist
            
            total_synced += batch_synced
            batch_count += 1
            
            # Log progress every 10 batches
            if batch_count % 10 == 0:
                logger.info(f"Progress: {total_synced} conversations synced so far...")
            
            # Check if more pages exist
            if not result.get("has_more"):
                break
            
            after = result.get("last_id")
        
        logger.info(f"Completed: {total_synced} conversations synced in {batch_count} batches")
        return total_synced
    
    def _has_activity_on_date(
        self,
        conv_data: Dict[str, Any],
        since_timestamp: int,
        until_timestamp: int
    ) -> bool:
        """
        Check if a conversation has user activity within the given time range.
        
        A conversation has activity if at least one user message was created
        within the timestamp range.
        
        Args:
            conv_data: Raw conversation data from OpenAI
            since_timestamp: Start of day (Unix timestamp)
            until_timestamp: End of day (Unix timestamp)
            
        Returns:
            True if conversation has activity on the target day
        """
        messages = conv_data.get("messages", {}).get("data", [])
        
        for msg in messages:
            msg_created_at = msg.get("created_at")
            if msg_created_at is None:
                continue
            
            # Check if message is within the target day
            if since_timestamp <= msg_created_at < until_timestamp:
                # Check if it's a user message (not assistant, system, or tool)
                author = msg.get("author", {})
                if author.get("role") == "user":
                    return True
        
        return False
    
    # =========================================================================
    # Granular Data Sync Methods
    # =========================================================================
    
    def _upsert_gpt(
        self,
        customer_id: str,
        gpt_info: GPTSummary
    ) -> AdoptionGPT:
        """
        Insert or update a GPT record.
        
        Args:
            customer_id: Customer ID
            gpt_info: GPT information from OpenAI
            
        Returns:
            Created or updated AdoptionGPT
        """
        existing = self.db.query(AdoptionGPT).filter(
            AdoptionGPT.customer_id == customer_id,
            AdoptionGPT.external_gpt_id == gpt_info.id
        ).first()
        
        # Use actual name from config, fallback to builder_name
        display_name = gpt_info.name or gpt_info.builder_name
        
        if existing:
            # Update metadata
            existing.name = display_name
            existing.description = gpt_info.description
            existing.short_url = getattr(gpt_info, 'short_url', None)
            existing.creator_user_id = gpt_info.owner_id
            existing.creator_email = gpt_info.owner_email
            existing.creator_name = gpt_info.builder_name  # Store builder_name separately
            existing.visibility = gpt_info.visibility
            existing.last_synced_at = datetime.now(timezone.utc)
            if gpt_info.created_at:
                existing.external_created_at = datetime.fromtimestamp(gpt_info.created_at, tz=timezone.utc)
            updated_at = getattr(gpt_info, 'updated_at', None)
            if updated_at:
                existing.external_updated_at = datetime.fromtimestamp(updated_at, tz=timezone.utc)
            return existing
        else:
            updated_at = getattr(gpt_info, 'updated_at', None)
            gpt = AdoptionGPT(
                customer_id=customer_id,
                external_gpt_id=gpt_info.id,
                name=display_name,
                description=gpt_info.description,
                short_url=getattr(gpt_info, 'short_url', None),
                creator_user_id=gpt_info.owner_id,
                creator_email=gpt_info.owner_email,
                creator_name=gpt_info.builder_name,
                visibility=gpt_info.visibility,
                external_created_at=datetime.fromtimestamp(gpt_info.created_at, tz=timezone.utc) if gpt_info.created_at else None,
                external_updated_at=datetime.fromtimestamp(updated_at, tz=timezone.utc) if updated_at else None,
                last_synced_at=datetime.now(timezone.utc)
            )
            self.db.add(gpt)
            self.db.flush()  # Get the ID
            return gpt
    
    def _upsert_conversation(
        self,
        customer_id: str,
        conv_data: Dict[str, Any],
        gpt_lookup: Dict[str, int],  # external_gpt_id -> AdoptionGPT.id
        sync_run_id: Optional[str] = None
    ) -> AdoptionConversation:
        """
        Insert or update a conversation record.
        
        Args:
            customer_id: Customer ID
            conv_data: Raw conversation data from OpenAI
            gpt_lookup: Mapping of external GPT ID to internal GPT ID
            
        Returns:
            Created or updated AdoptionConversation
        """
        external_conv_id = conv_data.get("id")
        
        existing = self.db.query(AdoptionConversation).filter(
            AdoptionConversation.customer_id == customer_id,
            AdoptionConversation.external_conversation_id == external_conv_id
        ).first()
        
        # Count messages
        messages = conv_data.get("messages", {}).get("data", [])
        message_count = len(messages)
        user_message_count = sum(1 for m in messages if m.get("author", {}).get("role") == "user")
        
        # Find GPT ID (from any message with gpt_id)
        external_gpt_id = None
        for msg in messages:
            if msg.get("gpt_id"):
                external_gpt_id = msg.get("gpt_id")
                break
        
        gpt_id = gpt_lookup.get(external_gpt_id) if external_gpt_id else None
        
        # Parse timestamps
        created_at = None
        updated_at = None
        if conv_data.get("created_at"):
            created_at = datetime.fromtimestamp(conv_data["created_at"], tz=timezone.utc)
        if conv_data.get("updated_at"):
            updated_at = datetime.fromtimestamp(conv_data["updated_at"], tz=timezone.utc)
        
        if existing:
            existing.user_external_id = conv_data.get("user_id")
            existing.user_email = conv_data.get("user_email")
            existing.gpt_id = gpt_id
            existing.external_gpt_id = external_gpt_id
            existing.message_count = message_count
            existing.user_message_count = user_message_count
            existing.conversation_created_at = created_at
            existing.conversation_updated_at = updated_at
            existing.last_synced_at = datetime.now(timezone.utc)
            existing.sync_run_id = sync_run_id
            return existing
        else:
            conv = AdoptionConversation(
                customer_id=customer_id,
                external_conversation_id=external_conv_id,
                user_external_id=conv_data.get("user_id"),
                user_email=conv_data.get("user_email"),
                gpt_id=gpt_id,
                external_gpt_id=external_gpt_id,
                message_count=message_count,
                user_message_count=user_message_count,
                conversation_created_at=created_at,
                conversation_updated_at=updated_at,
                last_synced_at=datetime.now(timezone.utc),
                sync_run_id=sync_run_id
            )
            self.db.add(conv)
            return conv
    
    def _update_user_gpt_interactions(self, customer_id: str) -> int:
        """
        Rebuild user-GPT interaction summaries from conversation data.
        
        This aggregates all conversation data to create user-GPT summaries.
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Number of interaction records updated
        """
        from sqlalchemy import func as sql_func
        
        # Aggregate from conversations
        interactions = self.db.query(
            AdoptionConversation.user_external_id,
            AdoptionConversation.user_email,
            AdoptionConversation.gpt_id,
            sql_func.count(AdoptionConversation.id).label('conv_count'),
            sql_func.sum(AdoptionConversation.user_message_count).label('msg_count'),
            sql_func.min(AdoptionConversation.conversation_created_at).label('first_at'),
            sql_func.max(AdoptionConversation.conversation_created_at).label('last_at')
        ).filter(
            AdoptionConversation.customer_id == customer_id,
            AdoptionConversation.gpt_id.isnot(None),
            AdoptionConversation.user_external_id.isnot(None)
        ).group_by(
            AdoptionConversation.user_external_id,
            AdoptionConversation.user_email,
            AdoptionConversation.gpt_id
        ).all()
        
        updated_count = 0
        for row in interactions:
            existing = self.db.query(AdoptionUserGPTInteraction).filter(
                AdoptionUserGPTInteraction.customer_id == customer_id,
                AdoptionUserGPTInteraction.user_external_id == row.user_external_id,
                AdoptionUserGPTInteraction.gpt_id == row.gpt_id
            ).first()
            
            if existing:
                existing.user_email = row.user_email
                existing.total_conversations = row.conv_count
                existing.total_messages = row.msg_count or 0
                existing.first_interaction_at = row.first_at
                existing.last_interaction_at = row.last_at
            else:
                interaction = AdoptionUserGPTInteraction(
                    customer_id=customer_id,
                    user_external_id=row.user_external_id,
                    user_email=row.user_email,
                    gpt_id=row.gpt_id,
                    total_conversations=row.conv_count,
                    total_messages=row.msg_count or 0,
                    first_interaction_at=row.first_at,
                    last_interaction_at=row.last_at
                )
                self.db.add(interaction)
            updated_count += 1
        
        return updated_count
    
    async def sync_all_providers(
        self,
        customer_id: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Sync all adoption-enabled providers.
        
        Args:
            customer_id: Optional filter to specific customer
            force: If True, re-sync all dates
            
        Returns:
            Dict with aggregated sync results
        """
        providers = self.get_adoption_providers(customer_id)
        
        if not providers:
            return {
                "success": True,
                "message": "No adoption providers configured",
                "providers_synced": 0,
                "total_records": 0
            }
        
        results = []
        total_records = 0
        all_success = True
        
        for provider in providers:
            try:
                result = await self.sync_provider(provider, force=force)
                results.append({
                    "provider_id": provider.id,
                    "customer_id": provider.customer_id,
                    "provider_type": provider.provider_name,
                    **result
                })
                total_records += result.get("records_synced", 0)
                if not result.get("success"):
                    all_success = False
            except Exception as e:
                logger.error(f"Failed to sync provider {provider.id}: {e}")
                results.append({
                    "provider_id": provider.id,
                    "customer_id": provider.customer_id,
                    "provider_type": provider.provider_name,
                    "success": False,
                    "error": str(e)
                })
                all_success = False
        
        return {
            "success": all_success,
            "providers_synced": len(providers),
            "total_records": total_records,
            "results": results
        }

