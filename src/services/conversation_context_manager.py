"""
Conversation Context Manager

Critical component for managing conversation context for SQL generation and LLM responses.
Manages sliding window of messages, formats data results, and builds enhanced questions.

This is a critical piece of the system performing at a high level.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.core.config import Settings
from src.core.logging import get_logger
from src.models.data_analyst import DataAnalystConversation, DataAnalystMessage

logger = get_logger(__name__, component="conversation.context.manager")


class ConversationContextManager:
    """
    Manages conversation context for SQL generation and LLM responses.
    
    Responsibilities:
    - Extract last N messages from conversation (sliding window)
    - Format data results (first 5 rows only)
    - Build context string for Vanna/LLM
    - Handle both data and conversational messages
    - Track message IDs for clear traceability
    
    This is a critical component - iterate and extend as needed.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize context manager with settings.
        
        Args:
            settings: Application settings containing context configuration
        """
        self.settings = settings
        self.context_window_size = settings.data_analyst_context_window_size  # Default: 10
        self.context_data_rows = settings.data_analyst_context_data_rows  # Default: 5
        
        logger.debug(
            "context_manager_initialized",
            context_window_size=self.context_window_size,
            context_data_rows=self.context_data_rows
        )
    
    def get_conversation_context(
        self,
        conversation: DataAnalystConversation,
        exclude_message_id: Optional[str] = None
    ) -> str:
        """
        Build conversation context string from last N messages (sliding window).
        
        Returns formatted context including:
        - Previous questions/messages (last N, excluding current)
        - Data results (first 5 rows only)
        - SQL queries (for data messages)
        - Conversational responses (for conversational messages)
        - Message IDs for traceability
        
        Args:
            conversation: The conversation to extract context from
            exclude_message_id: Message ID to exclude from context (current message being processed)
            
        Returns:
            Formatted context string for LLM/Vanna
        """
        if not conversation:
            return ""
        
        # Get context messages (last N, excluding current)
        context_messages = self.get_context_messages(conversation, exclude_message_id)
        
        if not context_messages:
            return ""
        
        context_parts = []
        context_parts.append("Previous conversation context (last {} messages):".format(
            len(context_messages)
        ))
        context_parts.append("")
        
        for msg in context_messages:
            msg_context = self._format_message_for_context(msg)
            if msg_context:
                context_parts.append(msg_context)
                context_parts.append("")
        
        return "\n".join(context_parts)
    
    def get_context_messages(
        self,
        conversation: DataAnalystConversation,
        exclude_message_id: Optional[str] = None
    ) -> List[DataAnalystMessage]:
        """
        Get last N messages for context (sliding window).
        
        Returns messages ordered by message_order DESC, limited to context_window_size.
        Excludes the message with exclude_message_id if provided.
        
        Args:
            conversation: The conversation to get messages from
            exclude_message_id: Message ID to exclude
            
        Returns:
            List of messages ordered by message_order DESC, limited to context_window_size
        """
        if not conversation or not conversation.messages:
            return []
        
        # Filter out excluded message and sort by order
        messages = [
            msg for msg in conversation.messages
            if msg.message_id != exclude_message_id and msg.message_order is not None
        ]
        
        # Sort by message_order DESC (most recent first)
        messages.sort(key=lambda m: m.message_order or 0, reverse=True)
        
        # Take last N (sliding window)
        context_messages = messages[:self.context_window_size]
        
        # Reverse to chronological order (oldest first for context)
        context_messages.reverse()
        
        logger.debug(
            "context_messages_retrieved",
            conversation_id=conversation.conversation_id,
            total_messages=len(conversation.messages),
            context_messages=len(context_messages),
            excluded_message_id=exclude_message_id
        )
        
        return context_messages
    
    def format_data_result_for_context(
        self,
        result_data: Dict[str, Any],
        message_id: str
    ) -> str:
        """
        Format data result for context (first 5 rows only).
        
        Example output:
        "Message ID: {message_id}
        Previous query returned:
        Columns: [total_premium_collected]
        Sample data (first 5 rows):
        - Row 1: -2919.75
        - Row 2: 12500.00
        ..."
        
        Args:
            result_data: The result data dict with columns, rows, row_count
            message_id: The message ID for traceability
            
        Returns:
            Formatted string representation of data result
        """
        if not result_data or not isinstance(result_data, dict):
            return ""
        
        columns = result_data.get("columns", [])
        rows = result_data.get("rows", [])
        row_count = result_data.get("row_count", 0)
        
        if not columns or not rows:
            return ""
        
        # Take only first N rows
        sample_rows = rows[:self.context_data_rows]
        
        parts = []
        parts.append(f"Message ID: {message_id}")
        parts.append(f"Previous query returned {row_count} row(s)")
        parts.append(f"Columns: {columns}")
        parts.append(f"Sample data (first {len(sample_rows)} rows):")
        
        for idx, row in enumerate(sample_rows, 1):
            # Format row as key-value pairs
            row_str = ", ".join([f"{col}={val}" for col, val in zip(columns, row)])
            parts.append(f"  - Row {idx}: {row_str}")
        
        if row_count > len(sample_rows):
            parts.append(f"  ... ({row_count - len(sample_rows)} more rows)")
        
        return "\n".join(parts)
    
    def build_enhanced_question(
        self,
        conversation: DataAnalystConversation,
        current_question: str,
        exclude_message_id: Optional[str] = None
    ) -> str:
        """
        Build enhanced question with conversation context.
        
        Format:
        "Previous conversation context:
        [Last N messages with data summaries]
        
        Current question: {current_question}"
        
        Args:
            conversation: The conversation to get context from
            current_question: The current question being asked
            exclude_message_id: Message ID to exclude from context
            
        Returns:
            Enhanced question string with context
        """
        context = self.get_conversation_context(conversation, exclude_message_id)
        
        if not context:
            return current_question
        
        enhanced = f"""{context}

Current question: {current_question}"""
        
        logger.debug(
            "enhanced_question_built",
            conversation_id=conversation.conversation_id if conversation else None,
            context_length=len(context),
            question_length=len(current_question)
        )
        
        return enhanced
    
    def _format_message_for_context(self, message: DataAnalystMessage) -> str:
        """
        Format a single message for context string.
        
        Args:
            message: The message to format
            
        Returns:
            Formatted string representation of the message
        """
        if not message:
            return ""
        
        parts = []
        parts.append(f"--- Message {message.message_order} (ID: {message.message_id}) ---")
        parts.append(f"Type: {message.message_type}")
        parts.append(f"Question: {message.original_question}")
        
        if message.message_type == "data":
            # Include SQL if available
            if message.generated_sql:
                parts.append(f"SQL: {message.generated_sql[:200]}...")  # Truncate long SQL
            
            # Include data result summary (first 5 rows)
            if message.result_data:
                data_summary = self.format_data_result_for_context(
                    message.result_data,
                    message.message_id or message.question_id
                )
                if data_summary:
                    parts.append(f"Result: {data_summary}")
        
        elif message.message_type == "conversational":
            # Include conversational response if available
            if message.conversational_response:
                parts.append(f"Response: {message.conversational_response[:200]}...")  # Truncate long responses
        
        return "\n".join(parts)

