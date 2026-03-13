"""
OpenAI ChatGPT Enterprise Compliance API Client.

Client for fetching usage and adoption metrics from OpenAI's Compliance API
for ChatGPT Enterprise customers.

API Documentation: https://api.chatgpt.com/v1
OpenAPI Spec: src/services/adoption/openapi.json
"""

import logging
import httpx
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceUser:
    """User from the Compliance API."""
    id: str
    email: str
    name: Optional[str] = None
    role: Optional[str] = None  # account-owner, account-admin, standard-user
    status: Optional[str] = None  # active, inactive
    created_at: Optional[float] = None


@dataclass
class ConversationSummary:
    """Summary of a conversation from the Compliance API."""
    id: str
    user_id: str
    user_email: Optional[str] = None
    title: Optional[str] = None
    created_at: Optional[float] = None
    last_active_at: Optional[float] = None
    message_count: int = 0


@dataclass
class GPTSummary:
    """Summary of a GPT from the Compliance API."""
    id: str
    owner_id: Optional[str] = None
    owner_email: Optional[str] = None
    builder_name: Optional[str] = None
    created_at: Optional[float] = None
    visibility: Optional[str] = None
    # From latest_config
    name: Optional[str] = None  # The actual GPT name
    description: Optional[str] = None  # GPT description


@dataclass
class GPTUsageInfo:
    """GPT usage information for daily metrics."""
    id: str
    name: str
    uses: int
    creator_email: Optional[str] = None
    short_url: Optional[str] = None


@dataclass
class DailyUsageSummary:
    """Aggregated daily usage metrics derived from compliance data."""
    date: date
    active_users: int = 0
    total_conversations: int = 0
    total_messages: int = 0
    input_tokens: int = 0  # Not directly available, placeholder
    output_tokens: int = 0  # Not directly available, placeholder
    unique_models: int = 0
    unique_gpts: int = 0
    # GPT adoption metrics
    gpt_conversations: int = 0  # Conversations using custom GPTs
    base_conversations: int = 0  # Conversations using base ChatGPT
    model_breakdown: Dict[str, int] = field(default_factory=dict)
    gpt_breakdown: List[Dict[str, Any]] = field(default_factory=list)  # List of GPT info dicts
    user_breakdown: Dict[str, int] = field(default_factory=dict)


class OpenAIComplianceClient:
    """
    Client for OpenAI ChatGPT Enterprise Compliance API.
    
    The Compliance API provides data export capabilities for ChatGPT Enterprise:
    - List workspace users
    - List conversations with messages
    - List GPTs and their configurations
    - List memories
    - Access compliance logs (audit, auth, etc.)
    
    Base URL: https://api.chatgpt.com/v1
    Auth: Bearer token (sk-proj-XXX)
    
    Note: This API does NOT provide direct usage/token metrics.
    We derive adoption metrics by counting users, conversations, and GPTs.
    """
    
    # ChatGPT Enterprise Compliance API base URL (NOT api.openai.com!)
    BASE_URL = "https://api.chatgpt.com/v1"
    
    def __init__(
        self, 
        api_key: str, 
        workspace_id: str,
        organization_id: Optional[str] = None
    ):
        """
        Initialize the Compliance API client.
        
        Args:
            api_key: OpenAI API key with compliance_export scope (sk-proj-XXX)
            workspace_id: ChatGPT Enterprise workspace UUID
            organization_id: Optional organization ID
        """
        self.api_key = api_key
        self.workspace_id = workspace_id
        self.organization_id = organization_id
        self._client = None
        self._gpt_cache: Optional[List[GPTSummary]] = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialize HTTP client."""
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            if self.organization_id:
                headers["OpenAI-Organization"] = self.organization_id
            
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=headers,
                timeout=60.0  # Compliance API can be slow for large workspaces
            )
        return self._client
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # =========================================================================
    # Users Endpoint
    # =========================================================================
    
    async def list_users(
        self,
        limit: int = 200,
        after: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List workspace users.
        
        GET /compliance/workspaces/{workspace_id}/users
        
        Args:
            limit: Maximum users to return (default 200)
            after: Pagination cursor (user_id to start after)
            
        Returns:
            Dict with 'data' (list of users), 'has_more', 'last_id'
        """
        params = {"limit": limit}
        if after:
            params["after"] = after
        
        try:
            response = await self.client.get(
                f"/compliance/workspaces/{self.workspace_id}/users",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Listed {len(data.get('data', []))} users, has_more={data.get('has_more')}"
                )
                return data
            else:
                logger.error(f"List users failed: {response.status_code} - {response.text}")
                response.raise_for_status()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error listing users: {e}")
            raise
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            raise
    
    async def get_all_users(self) -> List[WorkspaceUser]:
        """
        Get all workspace users (handles pagination).
        
        Returns:
            List of WorkspaceUser objects
        """
        all_users = []
        after = None
        
        while True:
            result = await self.list_users(after=after)
            
            for user_data in result.get("data", []):
                all_users.append(WorkspaceUser(
                    id=user_data.get("id"),
                    email=user_data.get("email", ""),
                    name=user_data.get("name"),
                    role=user_data.get("role"),
                    status=user_data.get("status"),
                    created_at=user_data.get("created_at")
                ))
            
            if not result.get("has_more"):
                break
            after = result.get("last_id")
        
        return all_users
    
    # =========================================================================
    # Conversations Endpoint
    # =========================================================================
    
    async def list_conversations(
        self,
        limit: int = 100,
        after: Optional[str] = None,
        since_timestamp: Optional[int] = None,
        users: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        List conversations from the workspace.
        
        GET /compliance/workspaces/{workspace_id}/conversations
        
        Args:
            limit: Maximum conversations to return (max 500)
            after: Pagination cursor (conversation_id to start after)
            since_timestamp: Only return conversations updated after this Unix timestamp
            users: Filter to specific user IDs (max 100)
            
        Returns:
            Dict with 'data' (list of conversations), 'has_more', 'last_id'
        """
        params = {"limit": min(limit, 500)}
        
        # Cannot use both after and since_timestamp
        if after:
            params["after"] = after
        elif since_timestamp:
            params["since_timestamp"] = since_timestamp
        
        if users:
            # API accepts multiple users params
            for user_id in users[:100]:
                params.setdefault("users", []).append(user_id)
        
        try:
            response = await self.client.get(
                f"/compliance/workspaces/{self.workspace_id}/conversations",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Listed {len(data.get('data', []))} conversations, has_more={data.get('has_more')}"
                )
                return data
            elif response.status_code == 429:
                logger.warning("Rate limited on conversations endpoint")
                raise httpx.HTTPStatusError(
                    "Rate limited", request=response.request, response=response
                )
            else:
                logger.error(f"List conversations failed: {response.status_code} - {response.text}")
                response.raise_for_status()
                
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            raise
    
    async def count_conversations_for_day(
        self,
        target_date: date,
        sample_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Count conversations and unique users for a SPECIFIC day.
        
        This fetches conversations updated since the start of the target day,
        then filters to only include those where created_at falls within that day.
        
        Args:
            target_date: The specific date to count metrics for
            sample_size: Max conversations to fetch
            
        Returns:
            Dict with counts, user breakdown, and GPT usage for that specific day
        """
        # Calculate timestamp range for the target date
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = start_of_day + timedelta(days=1)
        
        since_timestamp = int(start_of_day.timestamp())
        until_timestamp = int(end_of_day.timestamp())
        
        # Fetch conversations updated since start of day
        result = await self.list_conversations(
            limit=sample_size,
            since_timestamp=since_timestamp
        )
        
        conversations = result.get("data", [])
        user_counts: Dict[str, int] = {}  # Users who sent messages ON this day
        user_message_count = 0  # Messages created ON this day
        conversations_active_today = set()  # Conversations with activity ON this day
        conversations_created_today = 0  # Conversations CREATED on this day
        gpt_conversations = 0  # Conversations using a GPT today
        base_conversations = 0  # Conversations using base ChatGPT today
        gpt_usage: Dict[str, int] = {}  # Track GPT usage by gpt_id
        
        for conv in conversations:
            conv_id = conv.get("id")
            user_id = conv.get("user_id", "unknown")
            
            # Track if this conversation was CREATED on the target day
            conv_created_at = conv.get("created_at")
            if conv_created_at and since_timestamp <= conv_created_at < until_timestamp:
                conversations_created_today += 1
            
            # Count messages that were CREATED on the target day (not all messages in conversation)
            messages = conv.get("messages", {}).get("data", [])
            conv_has_gpt_today = False
            conv_had_user_message_today = False
            
            for msg in messages:
                # Check if this message was created on the target day
                msg_created_at = msg.get("created_at")
                if msg_created_at is None:
                    continue
                    
                # Only count messages CREATED on the target day
                if not (since_timestamp <= msg_created_at < until_timestamp):
                    continue
                
                # This message was created on the target day
                author = msg.get("author", {})
                if author.get("role") == "user":
                    user_message_count += 1
                    user_counts[user_id] = user_counts.get(user_id, 0) + 1
                    conv_had_user_message_today = True
                
                # Track GPT usage from messages created today
                gpt_id = msg.get("gpt_id")
                if gpt_id:
                    gpt_usage[gpt_id] = gpt_usage.get(gpt_id, 0) + 1
                    conv_has_gpt_today = True
            
            # Track conversations that had activity today
            if conv_had_user_message_today:
                conversations_active_today.add(conv_id)
                if conv_has_gpt_today:
                    gpt_conversations += 1
                else:
                    base_conversations += 1
        
        return {
            "conversation_count": len(conversations_active_today),  # Conversations with activity today
            "conversations_created": conversations_created_today,  # Conversations started today
            "has_more": result.get("has_more", False),
            "unique_users": len(user_counts),  # Users who sent messages today
            "message_count": user_message_count,  # Messages sent today
            "user_breakdown": user_counts,
            "gpt_usage": gpt_usage,  # {gpt_id: message_count on this day}
            "gpt_conversations": gpt_conversations,
            "base_conversations": base_conversations,
        }
    
    async def count_conversations_since(
        self,
        since_timestamp: int,
        sample_size: int = 500
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Use count_conversations_for_day() instead.
        
        Count conversations and unique users since a timestamp.
        This returns cumulative counts from the timestamp to now,
        which is NOT what we want for daily metrics.
        
        Args:
            since_timestamp: Unix timestamp to count from
            sample_size: Max conversations to fetch for counting
            
        Returns:
            Dict with counts and user breakdown
        """
        result = await self.list_conversations(
            limit=sample_size,
            since_timestamp=since_timestamp
        )
        
        conversations = result.get("data", [])
        user_counts: Dict[str, int] = {}
        user_message_count = 0
        
        for conv in conversations:
            user_id = conv.get("user_id", "unknown")
            user_counts[user_id] = user_counts.get(user_id, 0) + 1
            
            # Count only USER messages (not assistant, system, or tool)
            messages = conv.get("messages", {}).get("data", [])
            for msg in messages:
                author = msg.get("author", {})
                if author.get("role") == "user":
                    user_message_count += 1
        
        return {
            "conversation_count": len(conversations),
            "has_more": result.get("has_more", False),
            "unique_users": len(user_counts),
            "message_count": user_message_count,
            "user_breakdown": user_counts
        }
    
    # =========================================================================
    # GPTs Endpoint
    # =========================================================================
    
    async def list_gpts(
        self,
        limit: int = 20,
        after: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List GPTs in the workspace.
        
        GET /compliance/workspaces/{workspace_id}/gpts
        
        Args:
            limit: Maximum GPTs to return (default 20)
            after: Pagination cursor (gpt_id to start after)
            
        Returns:
            Dict with 'data' (list of GPTs), 'has_more', 'last_id'
        """
        params = {"limit": limit}
        if after:
            params["after"] = after
        
        try:
            response = await self.client.get(
                f"/compliance/workspaces/{self.workspace_id}/gpts",
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Listed {len(data.get('data', []))} GPTs, has_more={data.get('has_more')}"
                )
                return data
            else:
                logger.error(f"List GPTs failed: {response.status_code} - {response.text}")
                response.raise_for_status()
                
        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error(f"Error listing GPTs: {e}")
            raise
    
    async def get_all_gpts(self, force_refresh: bool = False) -> List[GPTSummary]:
        """
        Get all GPTs in workspace (handles pagination).
        
        Extracts name and description from latest_config if available.
        
        Returns:
            List of GPTSummary objects
        """
        if self._gpt_cache is not None and not force_refresh:
            return self._gpt_cache

        all_gpts = []
        after = None
        
        while True:
            result = await self.list_gpts(after=after)
            
            for gpt_data in result.get("data", []):
                sharing = gpt_data.get("sharing", {})
                
                # Extract name and description from latest_config
                name = None
                description = None
                latest_config = gpt_data.get("latest_config", {})
                config_data = latest_config.get("data", [])
                if config_data and len(config_data) > 0:
                    latest = config_data[0]  # Most recent config
                    name = latest.get("name")
                    description = latest.get("description")
                
                all_gpts.append(GPTSummary(
                    id=gpt_data.get("id"),
                    owner_id=gpt_data.get("owner_id"),
                    owner_email=gpt_data.get("owner_email"),
                    builder_name=gpt_data.get("builder_name"),
                    created_at=gpt_data.get("created_at"),
                    visibility=sharing.get("visibility"),
                    name=name,
                    description=description
                ))
            
            if not result.get("has_more"):
                break
            after = result.get("last_id")
        
        self._gpt_cache = all_gpts
        return all_gpts
    
    # =========================================================================
    # Daily Summary (Derived from API data)
    # =========================================================================
    
    async def get_daily_summary(
        self,
        target_date: date,
        gpt_metadata: Optional[Dict[str, GPTSummary]] = None
    ) -> DailyUsageSummary:
        """
        Get aggregated daily usage summary.
        
        Since the Compliance API doesn't provide direct usage metrics,
        we derive them by counting:
        - Active users (users with conversations created on that day)
        - Conversations created on that day
        - User messages only (not assistant/system/tool)
        - GPTs in use
        
        Args:
            target_date: Date to get summary for
            
        Returns:
            DailyUsageSummary with derived metrics
        """
        # Get conversations for the specific day (filtered by created_at)
        conv_stats = await self.count_conversations_for_day(
            target_date=target_date,
            sample_size=1000
        )
        
        # Get GPTs metadata and combine with actual usage from conversations.
        # Reuses the sync-scoped cache to avoid N x repeated API fetches.
        gpt_usage = conv_stats.get("gpt_usage", {})  # {gpt_id: usage_count}

        if gpt_metadata is None:
            try:
                gpts = await self.get_all_gpts()
                gpt_metadata = {gpt.id: gpt for gpt in gpts}
            except Exception as e:
                logger.warning(f"Failed to fetch GPTs: {e}")
                gpt_metadata = {}
        
        # Build list of GPTs with actual usage data
        gpt_list = []
        for gpt_id, uses in gpt_usage.items():
            gpt_meta = gpt_metadata.get(gpt_id)
            gpt_list.append({
                "id": gpt_id,
                "name": gpt_meta.builder_name if gpt_meta else gpt_id,
                "uses": uses,
                "creator_email": gpt_meta.owner_email if gpt_meta else None,
                "short_url": None,
            })
        
        # Sort by usage descending
        gpt_list.sort(key=lambda x: x["uses"], reverse=True)
        
        summary = DailyUsageSummary(
            date=target_date,
            active_users=conv_stats.get("unique_users", 0),
            total_conversations=conv_stats.get("conversation_count", 0),
            total_messages=conv_stats.get("message_count", 0),
            unique_gpts=len(gpt_usage),  # Count of unique GPTs actually used
            gpt_conversations=conv_stats.get("gpt_conversations", 0),
            base_conversations=conv_stats.get("base_conversations", 0),
            gpt_breakdown=gpt_list,
            user_breakdown=conv_stats.get("user_breakdown", {})
        )
        
        return summary
    
    # =========================================================================
    # Connection Test
    # =========================================================================
    
    async def test_connection(self) -> bool:
        """
        Test if the API key has access to the workspace.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to list users with limit=1 as a simple auth check
            response = await self.client.get(
                f"/compliance/workspaces/{self.workspace_id}/users",
                params={"limit": 1}
            )
            
            if response.status_code == 200:
                logger.info("Compliance API connection test successful")
                return True
            elif response.status_code == 404:
                logger.warning(f"Workspace {self.workspace_id} not found")
                return False
            else:
                logger.warning(f"Compliance API connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Compliance API connection test error: {e}")
            return False
