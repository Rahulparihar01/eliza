"""
Conversation Service for Data Analyst Agent

Handles conversation management including:
- Creating user and group conversations
- Managing participants
- Context tracking
- Message grouping
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import uuid

from src.models.data_analyst import (
    DataAnalystConversation,
    DataAnalystMessage,
    ConversationType,
    ConversationStatus,
    ParticipantRole,
    ConversationParticipant,
    DataSourceType
)
from src.core.logging import get_logger

logger = get_logger(__name__, component="conversation.service")


class ConversationService:
    """Service for managing conversations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_conversation(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: DataSourceType,
        conversation_type: ConversationType = ConversationType.USER,
        title: Optional[str] = None,
        participant_ids: Optional[List[int]] = None
    ) -> DataAnalystConversation:
        """
        Create a new conversation.
        
        Args:
            user_id: Creator's user ID
            customer_id: Customer/organization ID
            data_source_type: Type of data source
            conversation_type: USER or GROUP
            title: Optional conversation title
            participant_ids: List of user IDs to add to group conversation
        
        Returns:
            Created conversation
        """
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        
        # Build participants list
        participants = []
        
        # Add creator as owner
        participants.append({
            "user_id": user_id,
            "role": ParticipantRole.OWNER.value,
            "joined_at": datetime.utcnow().isoformat()
        })
        
        # Add additional participants for group conversations
        if conversation_type == ConversationType.GROUP and participant_ids:
            for pid in participant_ids:
                if pid != user_id:  # Don't duplicate the owner
                    participants.append({
                        "user_id": pid,
                        "role": ParticipantRole.PARTICIPANT.value,
                        "joined_at": datetime.utcnow().isoformat()
                    })
        
        is_shared = conversation_type == ConversationType.GROUP
        
        conversation = DataAnalystConversation(
            conversation_id=conversation_id,
            user_id=user_id,
            customer_id=customer_id,
            data_source_type=data_source_type,
            conversation_type=conversation_type.value,
            is_shared=is_shared,
            participants=participants,
            title=title,
            status=ConversationStatus.ACTIVE.value,
            last_activity_at=datetime.utcnow()
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(
            "conversation_created",
            conversation_id=conversation_id,
            user_id=user_id,
            conversation_type=conversation_type.value,
            participant_count=len(participants)
        )
        
        return conversation
    
    def get_conversation(
        self,
        conversation_id: str,
        user_id: int
    ) -> Optional[DataAnalystConversation]:
        """
        Get a conversation by ID, ensuring user has access.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID requesting access
        
        Returns:
            Conversation if found and user has access, None otherwise
        """
        conversation = self.db.query(DataAnalystConversation).filter(
            DataAnalystConversation.conversation_id == conversation_id,
            DataAnalystConversation.status == ConversationStatus.ACTIVE.value
        ).first()
        
        if not conversation:
            return None
        
        # Check access: user must be owner or participant
        has_access = (
            conversation.user_id == user_id or
            any(p.get("user_id") == user_id for p in conversation.participants)
        )
        
        if not has_access:
            logger.warning(
                "conversation_access_denied",
                conversation_id=conversation_id,
                user_id=user_id
            )
            return None
        
        return conversation
    
    def list_conversations(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: Optional[DataSourceType] = None,
        conversation_type: Optional[ConversationType] = None,
        page: int = 1,
        page_size: int = 50
    ) -> tuple[List[DataAnalystConversation], int]:
        """
        List conversations accessible to a user.
        
        Args:
            user_id: User ID
            customer_id: Customer ID
            data_source_type: Optional filter by data source
            conversation_type: Optional filter by conversation type
            page: Page number (1-indexed)
            page_size: Items per page
        
        Returns:
            Tuple of (conversations list, total count)
        """
        query = self.db.query(DataAnalystConversation).filter(
            DataAnalystConversation.status == ConversationStatus.ACTIVE.value,
            DataAnalystConversation.customer_id == customer_id
        )
        
        # Filter by data source if specified
        if data_source_type:
            query = query.filter(DataAnalystConversation.data_source_type == data_source_type)
        
        # Filter by conversation type if specified
        if conversation_type:
            query = query.filter(DataAnalystConversation.conversation_type == conversation_type.value)
        
        # Filter to conversations where user is owner or participant
        # Note: This uses PostgreSQL JSONB operators
        query = query.filter(
            (DataAnalystConversation.user_id == user_id) |
            (DataAnalystConversation.participants.op('@>')(f'[{{"user_id": {user_id}}}]'))
        )
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        conversations = query.order_by(
            DataAnalystConversation.last_activity_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        
        return conversations, total
    
    def delete_conversation(
        self,
        conversation_id: str,
        user_id: int
    ) -> bool:
        """
        Delete (soft delete) a conversation.
        
        Only the owner can delete a conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID requesting deletion
        
        Returns:
            True if deleted, False otherwise
        """
        conversation = self.db.query(DataAnalystConversation).filter(
            DataAnalystConversation.conversation_id == conversation_id,
            DataAnalystConversation.user_id == user_id,  # Only owner can delete
            DataAnalystConversation.status == ConversationStatus.ACTIVE.value
        ).first()
        
        if not conversation:
            logger.warning(
                "conversation_delete_failed",
                conversation_id=conversation_id,
                user_id=user_id,
                reason="not_found_or_not_owner"
            )
            return False
        
        conversation.status = ConversationStatus.DELETED.value
        self.db.commit()
        
        logger.info(
            "conversation_deleted",
            conversation_id=conversation_id,
            user_id=user_id
        )
        
        return True
    
    def update_conversation_title(
        self,
        conversation_id: str,
        user_id: int,
        title: str
    ) -> Optional[DataAnalystConversation]:
        """
        Update conversation title.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (must be owner)
            title: New title
        
        Returns:
            Updated conversation or None if not found/unauthorized
        """
        conversation = self.get_conversation(conversation_id, user_id)
        
        if not conversation or conversation.user_id != user_id:
            return None
        
        conversation.title = title
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation
    
    def add_participant(
        self,
        conversation_id: str,
        user_id: int,
        new_participant_id: int
    ) -> Optional[DataAnalystConversation]:
        """
        Add a participant to a group conversation.
        
        Args:
            conversation_id: Conversation ID
            user_id: User ID (must be owner)
            new_participant_id: User ID to add
        
        Returns:
            Updated conversation or None if not found/unauthorized
        """
        conversation = self.get_conversation(conversation_id, user_id)
        
        if not conversation or conversation.user_id != user_id:
            return None
        
        if conversation.conversation_type != ConversationType.GROUP.value:
            logger.warning(
                "add_participant_failed",
                conversation_id=conversation_id,
                reason="not_group_conversation"
            )
            return None
        
        # Check if already a participant
        if any(p.get("user_id") == new_participant_id for p in conversation.participants):
            return conversation  # Already a participant
        
        # Add new participant
        conversation.participants.append({
            "user_id": new_participant_id,
            "role": ParticipantRole.PARTICIPANT.value,
            "joined_at": datetime.utcnow().isoformat()
        })
        
        # Mark as modified for SQLAlchemy to detect the change
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        logger.info(
            "participant_added",
            conversation_id=conversation_id,
            new_participant_id=new_participant_id
        )
        
        return conversation
    
    def get_message_count(self, conversation_id: str) -> int:
        """Get the number of messages in a conversation."""
        return self.db.query(DataAnalystMessage).filter(
            DataAnalystMessage.conversation_id == conversation_id
        ).count()
    
    def get_latest_message(
        self,
        conversation_id: str
    ) -> Optional[DataAnalystMessage]:
        """Get the most recent message in a conversation."""
        return self.db.query(DataAnalystMessage).filter(
            DataAnalystMessage.conversation_id == conversation_id
        ).order_by(DataAnalystMessage.message_order.desc()).first()
