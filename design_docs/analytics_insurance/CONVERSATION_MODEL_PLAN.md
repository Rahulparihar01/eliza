# Data Analyst Conversation Model - Implementation Plan

## Problem Statement

Currently, the Data Analyst Agent treats each question as an isolated execution. However, users need to have **conversations** where they can:
- Ask follow-up questions that reference previous results
- Build on previous queries ("show me that broken down by state")
- Maintain context across multiple questions
- View conversation history
- Ask both **data questions** (SQL) AND **conversational questions** (SOPs, documentation, general questions)

## Current Architecture

```
User Question → DataAnalystQuestion → SQL Generation → Results → Display
```

**Issues:**
- No conversation context
- Each question is isolated
- No way to reference previous results
- No conversation history
- Can't handle mixed question types (data vs conversational)

## Proposed Architecture

```
User → Conversation → Multiple Messages → 
  ├─ Data Messages → SQL Generation → Results → Display
  └─ Conversational Messages → LLM Response → Display
```

## Key Requirements Summary

### Conversation Types
- **User Conversations**: User-specific, private
- **Group Conversations**: Shared within customer/org, multiple participants

### Message Types
- **DATA Messages**: Require SQL generation and data retrieval
- **CONVERSATIONAL Messages**: SOPs, documentation, general questions (no SQL)

### Context Management (CRITICAL)
- **Sliding Window**: Last 10 messages in context
- **Data Context**: Only first 5 rows of results (not full datasets)
- **Full Q&A**: Pass complete Q&A context (not summarized)
- **Message Tracking**: Each message has unique `message_id`
- **Explicit Context Manager**: Dedicated `ConversationContextManager` class for context handling

### Limits (Centralized Configuration)
- Max messages per conversation: 100
- Max active conversations per user: 100
- Context window: Last 10 messages
- Data rows in context: 5 rows
- **Storage**: Centralized in `src/core/config.py`

### UI Structure
- **Main View**: Linear chat-style conversation thread
- **Left Sidebar**: Collapsible conversation list
- **Right Pane**: Data/SQL details for data messages
- **Actions**: "New Conversation" and "New Group Conversation" buttons

## Database Schema Changes

### New Table: `data_analyst_conversations`

```sql
CREATE TABLE data_analyst_conversations (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(100) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,  -- Creator/owner
    customer_id VARCHAR(100) NOT NULL,
    data_source_type VARCHAR(50) NOT NULL,  -- 'insurance', etc.
    
    -- Conversation type and sharing
    conversation_type VARCHAR(50) NOT NULL DEFAULT 'user',  -- 'user' or 'group'
    is_shared BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Participants (JSON array for group conversations)
    participants JSONB DEFAULT '[]'::jsonb,  -- [{user_id: int, role: str, joined_at: timestamp}]
    
    -- Conversation metadata
    title VARCHAR(255),  -- Auto-generated from first question, user can rename
    description TEXT,    -- Optional user description
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'active',  -- 'active', 'deleted'
    
    -- Context (for LLM/Vanna) - stores summary of conversation
    conversation_context JSONB,  -- Last 10 messages summary, key data points
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMP,  -- Last message/question
    
    -- Indexes
    INDEX idx_conversations_user (user_id, customer_id),
    INDEX idx_conversations_type (conversation_type, is_shared),
    INDEX idx_conversations_status (status),
    INDEX idx_conversations_activity (last_activity_at DESC),
    INDEX idx_conversations_participants USING GIN (participants)  -- GIN index for JSONB array queries
);
```

### Participants Storage (JSON Array)

Participants are stored as a JSON array directly in the `data_analyst_conversations` table for simplicity and easy iteration:

```json
{
  "participants": [
    {
      "user_id": 1,
      "role": "owner",
      "joined_at": "2024-01-01T00:00:00Z"
    },
    {
      "user_id": 2,
      "role": "participant",
      "joined_at": "2024-01-02T00:00:00Z"
    }
  ]
}
```

**Benefits:**
- Simpler schema (no separate table)
- Easy to iterate/manage (simple JSON array operations)
- Flexible (can add metadata per participant easily)
- Less joins needed for queries

### Updated Table: `data_analyst_questions` → Rename to `data_analyst_messages`

**Rationale**: Questions can be both data queries AND conversational messages. Renaming to "messages" better reflects the dual nature.

```sql
-- Rename table (backward compatible)
ALTER TABLE data_analyst_questions RENAME TO data_analyst_messages;

-- Add conversation and message tracking
ALTER TABLE data_analyst_messages
ADD COLUMN conversation_id VARCHAR(100),
ADD COLUMN message_id VARCHAR(100) UNIQUE,  -- Unique message identifier
ADD COLUMN message_order INTEGER,  -- Order within conversation (1, 2, 3...)
ADD COLUMN message_type VARCHAR(50) NOT NULL DEFAULT 'data',  -- 'data' or 'conversational'
ADD COLUMN parent_message_id VARCHAR(100),  -- For follow-up questions referencing previous messages

ADD CONSTRAINT fk_message_conversation
    FOREIGN KEY (conversation_id) 
    REFERENCES data_analyst_conversations(conversation_id)
    ON DELETE CASCADE;

CREATE INDEX idx_messages_conversation ON data_analyst_messages(conversation_id);
CREATE INDEX idx_messages_message_id ON data_analyst_messages(message_id);
CREATE INDEX idx_messages_order ON data_analyst_messages(conversation_id, message_order);
CREATE INDEX idx_messages_type ON data_analyst_messages(message_type);
```

**Note**: Keep `question_id` column for backward compatibility, but `message_id` is the new primary identifier.

## Configuration: Centralized Limits

Add to `src/core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Data Analyst Conversation Limits (Centralized)
    data_analyst_max_messages_per_conversation: int = Field(
        default=100, 
        alias="DATA_ANALYST_MAX_MESSAGES_PER_CONVERSATION",
        description="Maximum number of messages allowed per conversation"
    )
    data_analyst_max_active_conversations_per_user: int = Field(
        default=100, 
        alias="DATA_ANALYST_MAX_ACTIVE_CONVERSATIONS_PER_USER",
        description="Maximum number of active conversations per user"
    )
    data_analyst_context_window_size: int = Field(
        default=10, 
        alias="DATA_ANALYST_CONTEXT_WINDOW_SIZE",
        description="Number of previous messages to include in context (sliding window)"
    )
    data_analyst_context_data_rows: int = Field(
        default=5, 
        alias="DATA_ANALYST_CONTEXT_DATA_ROWS",
        description="Number of data rows to include in conversation context (first N rows only)"
    )
```

## Data Model Changes

### New Model: `DataAnalystConversation`

```python
class ConversationType(str, Enum):
    USER = "user"
    GROUP = "group"

class ConversationStatus(str, Enum):
    ACTIVE = "active"
    DELETED = "deleted"

class DataAnalystConversation(BaseModel):
    __tablename__ = "data_analyst_conversations"
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)  # Creator/owner
    customer_id = Column(String(100), nullable=False, index=True)
    data_source_type = Column(SQLEnum(DataSourceType), nullable=False)
    
    # Conversation type and sharing
    conversation_type = Column(String(50), nullable=False, default=ConversationType.USER.value)
    is_shared = Column(Boolean, nullable=False, default=False)
    
    # Participants (JSON array: [{user_id: int, role: str, joined_at: timestamp}])
    participants = Column(JSON, nullable=False, default=[])  # Stored as JSON array
    
    # Metadata
    title = Column(String(255), nullable=True)  # Auto-generated, user can rename
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=ConversationStatus.ACTIVE.value)
    
    # Context for LLM/Vanna (stores last 10 messages summary)
    conversation_context = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_activity_at = Column(DateTime, nullable=True)
    
    # Relationships
    messages = relationship("DataAnalystMessage", back_populates="conversation", lazy="select", order_by="DataAnalystMessage.message_order")
```

### Participant Schema (Pydantic)

Participants are stored as JSON in the conversation record. Use Pydantic models for validation:

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ParticipantRole(str, Enum):
    OWNER = "owner"
    PARTICIPANT = "participant"

class ConversationParticipant(BaseModel):
    """Participant schema for JSON storage."""
    user_id: int
    role: ParticipantRole = ParticipantRole.PARTICIPANT
    joined_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

### Updated Model: `DataAnalystMessage` (renamed from `DataAnalystQuestion`)

```python
class MessageType(str, Enum):
    DATA = "data"  # Requires SQL generation
    CONVERSATIONAL = "conversational"  # General question, no SQL

class DataAnalystMessage(BaseModel):  # Renamed from DataAnalystQuestion
    __tablename__ = "data_analyst_messages"  # Table renamed
    
    # Keep existing fields for backward compatibility
    id = Column(Integer, primary_key=True)
    question_id = Column(String(100), unique=True, nullable=False, index=True)  # Keep for backward compat
    user_id = Column(Integer, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    
    # Question details
    data_source_type = Column(SQLEnum(DataSourceType), nullable=False)
    original_question = Column(Text, nullable=False)  # The user's question/message
    
    # NEW: Message tracking
    message_id = Column(String(100), unique=True, nullable=True, index=True)  # New primary identifier
    conversation_id = Column(String(100), ForeignKey("data_analyst_conversations.conversation_id"), nullable=True, index=True)
    message_order = Column(Integer, nullable=True)  # Order within conversation
    message_type = Column(String(50), nullable=False, default=MessageType.DATA.value)
    parent_message_id = Column(String(100), nullable=True)  # Reference to previous message
    
    # Processing (for DATA messages only)
    status = Column(String(50), nullable=False, default=DataAnalystQuestionStatus.PENDING.value)
    generated_sql = Column(Text, nullable=True)  # Only for DATA messages
    sql_error = Column(Text, nullable=True)
    
    # Results (for DATA messages only)
    result_data = Column(JSON, nullable=True)
    result_metadata = Column(JSON, nullable=True)
    
    # Conversational response (for CONVERSATIONAL messages)
    conversational_response = Column(Text, nullable=True)  # LLM response for non-data questions
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    conversation = relationship("DataAnalystConversation", back_populates="messages", lazy="select")
    parent_message = relationship("DataAnalystMessage", remote_side=[message_id], lazy="select")
```

## Context Management System (CRITICAL)

### New Service: `ConversationContextManager`

**Critical Component**: Manages conversation context for LLM/Vanna SQL generation.

**Location**: `src/services/conversation_context_manager.py`

```python
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
        self.settings = settings
        self.context_window_size = settings.data_analyst_context_window_size  # 10
        self.context_data_rows = settings.data_analyst_context_data_rows  # 5
    
    def get_conversation_context(
        self,
        conversation: DataAnalystConversation,
        exclude_message_id: Optional[str] = None  # Exclude current message being processed
    ) -> str:
        """
        Build conversation context string from last N messages (sliding window).
        
        Returns formatted context including:
        - Previous questions/messages (last 10)
        - Data results (first 5 rows only)
        - SQL queries (for data messages)
        - Conversational responses (for conversational messages)
        - Message IDs for traceability
        """
        
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
        """
        
    def build_enhanced_question(
        self,
        conversation: DataAnalystConversation,
        current_question: str,
        exclude_message_id: Optional[str] = None
    ) -> str:
        """
        Build enhanced question with conversation context.
        
        Format:
        "Previous conversation context (last 10 messages):
        [Message 1 ID: ...]
        Question: ...
        Result: [first 5 rows] / Response: ...
        
        [Message 2 ID: ...]
        ...
        
        Current question: {current_question}"
        """
        
    def get_context_messages(
        self,
        conversation: DataAnalystConversation,
        exclude_message_id: Optional[str] = None
    ) -> List[DataAnalystMessage]:
        """
        Get last N messages for context (sliding window).
        Returns messages ordered by message_order DESC, limited to context_window_size.
        """
```

## Service Layer Changes

### New Service: `ConversationService`

```python
class ConversationService:
    def create_conversation(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: DataSourceType,
        conversation_type: ConversationType = ConversationType.USER,
        title: Optional[str] = None
    ) -> DataAnalystConversation:
        """Create a new conversation (user or group)."""
        
    def create_group_conversation(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: DataSourceType,
        participant_user_ids: List[int],  # Users to add
        title: Optional[str] = None
    ) -> DataAnalystConversation:
        """Create a group conversation with participants."""
        
    def get_conversation(
        self,
        conversation_id: str,
        user_id: int  # For permission check
    ) -> DataAnalystConversation:
        """Get conversation with all messages (check permissions)."""
        
    def list_conversations(
        self,
        user_id: int,
        customer_id: str,
        conversation_type: Optional[ConversationType] = None,
        status: Optional[str] = None,
        limit: int = 100  # From settings
    ) -> List[DataAnalystConversation]:
        """List user's conversations (user + group conversations they're in)."""
        
    def update_conversation(
        self,
        conversation_id: str,
        user_id: int,
        title: Optional[str] = None,
        status: Optional[str] = None
    ) -> DataAnalystConversation:
        """Update conversation metadata (check permissions)."""
        
    def delete_conversation(
        self,
        conversation_id: str,
        user_id: int
    ) -> None:
        """Delete conversation (soft delete, check permissions)."""
        
    def add_participant(
        self,
        conversation_id: str,
        user_id: int,  # User adding
        new_participant_user_id: int,
        role: ParticipantRole = ParticipantRole.PARTICIPANT
    ) -> List[Dict[str, Any]]:
        """
        Add participant to group conversation.
        
        Returns updated participants list.
        Uses simple JSON array operations:
        - Load current participants
        - Append new participant if not exists
        - Save back to database
        """
        
    def remove_participant(
        self,
        conversation_id: str,
        user_id: int,  # User removing
        participant_user_id: int
    ) -> List[Dict[str, Any]]:
        """
        Remove participant from group conversation.
        
        Returns updated participants list.
        Uses simple JSON array operations:
        - Load current participants
        - Filter out participant
        - Save back to database
        """
        
    def get_participants(
        self,
        conversation_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get participants list from conversation.
        
        Returns list of participant dicts.
        """
        
    def is_participant(
        self,
        conversation_id: str,
        user_id: int
    ) -> bool:
        """
        Check if user is a participant in the conversation.
        
        Uses JSON array query: WHERE participants @> '[{"user_id": X}]'
        """
```

### Updated Service: `DataAnalystService`

```python
class DataAnalystService:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.context_manager = ConversationContextManager(self.settings)  # NEW
        # ... existing initialization ...
    
    def create_message(
        self,
        user_id: int,
        customer_id: str,
        data_source_type: DataSourceType,
        question: str,
        conversation_id: Optional[str] = None,  # If None, auto-create conversation
        message_type: Optional[MessageType] = None  # Auto-detect if None
    ) -> DataAnalystMessage:
        """
        Create message, optionally in a conversation.
        
        If conversation_id is None:
        - Auto-create new conversation
        - Auto-generate title from first question
        
        If message_type is None:
        - Auto-detect using _determine_message_type()
        """
        
    def process_message(
        self,
        message_id: str,
        use_conversation_context: bool = True
    ) -> Dict[str, Any]:
        """
        Process message (data or conversational).
        
        For DATA messages:
        - Use conversation context if available (last 10 messages)
        - Generate SQL with Vanna (enhanced question with context)
        - Execute and return results
        
        For CONVERSATIONAL messages:
        - Use conversation context
        - Generate LLM response (no SQL)
        - Return conversational response
        """
        
    def _determine_message_type(self, question: str) -> MessageType:
        """
        Determine if question is DATA or CONVERSATIONAL.
        
        Heuristics:
        - Contains data-related keywords (premium, claim, loss ratio, etc.) → DATA
        - Asks about processes, SOPs, documentation → CONVERSATIONAL
        - Can be enhanced with LLM classification later
        """
```

## API Changes

### New Endpoints

1. **Create Conversation**
   ```
   POST /api/v1/data-analyst/conversations
   Body: {
     "data_source_type": "insurance",
     "conversation_type": "user",  // or "group"
     "title": "Premium Analysis Q4 2024"  // Optional, auto-generated if not provided
   }
   Response: {
     "conversation_id": "uuid",
     "title": "...",
     "conversation_type": "user",
     "created_at": "..."
   }
   ```

2. **Create Group Conversation**
   ```
   POST /api/v1/data-analyst/conversations/group
   Body: {
     "data_source_type": "insurance",
     "participant_user_ids": [1, 2, 3],
     "title": "Team Analysis Q4"  // Optional
   }
   Response: {
     "conversation_id": "uuid",
     "title": "...",
     "conversation_type": "group",
     "participants": [...]
   }
   ```

3. **List Conversations**
   ```
   GET /api/v1/data-analyst/conversations?type=user&status=active&limit=100
   Response: {
     "conversations": [
       {
         "conversation_id": "uuid",
         "title": "...",
         "conversation_type": "user",
         "message_count": 5,
         "last_activity_at": "...",
         "status": "active"
       }
     ]
   }
   ```

4. **Get Conversation**
   ```
   GET /api/v1/data-analyst/conversations/{conversation_id}
   Response: {
     "conversation_id": "uuid",
     "title": "...",
     "conversation_type": "group",
     "participants": [...],
     "messages": [
       {
         "message_id": "uuid",
         "message_order": 1,
         "message_type": "data",
         "original_question": "...",
         "status": "completed",
         "result_data": {...},
         "result_metadata": {...},
         "created_at": "..."
       }
     ],
     "conversation_context": {...}
   }
   ```

5. **Update Conversation**
   ```
   PATCH /api/v1/data-analyst/conversations/{conversation_id}
   Body: {
     "title": "New Title",
     "status": "deleted"
   }
   ```

6. **Delete Conversation**
   ```
   DELETE /api/v1/data-analyst/conversations/{conversation_id}
   ```

7. **Submit Message (In Conversation)**
   ```
   POST /api/v1/data-analyst/conversations/{conversation_id}/messages
   Body: {
     "question": "What is the total premium collected in the last quarter?",
     "message_type": "data"  // Optional, auto-detected if not provided
   }
   Response: {
     "message_id": "uuid",
     "conversation_id": "uuid",
     "message_type": "data",
     "status": "pending"
   }
   ```

8. **Submit Message (Auto-create conversation)**
   ```
   POST /api/v1/data-analyst/messages
   Body: {
     "data_source_type": "insurance",
     "question": "What is the total premium collected?",
     "message_type": "data"  // Optional
   }
   Response: {
     "message_id": "uuid",
     "conversation_id": "uuid",  // Auto-created
     "status": "pending"
   }
   ```

### Updated Endpoints

- **Submit Question** (existing): Keep for backward compatibility, but internally use new message endpoints

## Frontend Changes

### New Components

1. **ConversationList** - Left sidebar (collapsible)
   - List of conversations (user + group)
   - "New Conversation" button
   - "New Group Conversation" button
   - Filter by type, status

2. **ConversationView** - Main chat interface
   - Linear chat-style message display
   - Each message shows question + results/response
   - Message input at bottom

3. **MessageBubble** - Individual message display
   - Shows question
   - For DATA messages: Shows results preview + "View Details" button
   - For CONVERSATIONAL messages: Shows LLM response

4. **DataDetailsPane** - Right side pane
   - Shows full data table, charts, SQL, insights
   - Only visible when DATA message is selected
   - Collapsible/expandable

5. **ConversationHeader** - Top bar
   - Conversation title (editable)
   - Participants (for group conversations)
   - Actions (rename, delete, share)

### UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│  Data Analyst Agent                    [Conversation Title] │
├──────────┬──────────────────────────────┬────────────────────┤
│          │                              │                    │
│          │  ┌────────────────────────┐  │  Data Details      │
│          │  │ Q1: Total premium?     │  │  ┌──────────────┐ │
│          │  │ [Results preview]      │  │  │ SQL Query     │ │
│          │  │ [View Details →]       │  │  │ [Full SQL]    │ │
│          │  └────────────────────────┘  │  └──────────────┘ │
│          │                              │  ┌──────────────┐ │
│          │  ┌────────────────────────┐  │  │ Data Table   │ │
│          │  │ Q2: By state?         │  │  │ [Full table] │ │
│          │  │ [Results preview]    │  │  └──────────────┘ │
│          │  │ [View Details →]     │  │  ┌──────────────┐ │
│          │  └────────────────────────┘  │  │ Charts       │ │
│          │                              │  │ [Charts]     │ │
│          │  ┌────────────────────────┐  │  └──────────────┘ │
│          │  │ [Message Input]        │  │                    │
│          │  └────────────────────────┘  │                    │
│          └──────────────────────────────┴────────────────────┤
│  Conversations (Collapsible)                                 │
│  ▼ Conversations                                             │
│    • Premium Q4 (user)                                       │
│    • Team Analysis (group)                                   │
│    [+ New Conversation]                                     │
│    [+ New Group Conversation]                                │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Database & Models (Critical)
- [ ] Add conversation limits to `src/core/config.py`
- [ ] Create `data_analyst_conversations` table migration (with `participants` JSONB column)
- [ ] Add `conversation_id`, `message_id`, `message_order`, `message_type` to `data_analyst_messages` table
- [ ] Rename `data_analyst_questions` → `data_analyst_messages` (backward compatible)
- [ ] Create `DataAnalystConversation` model (with `participants` JSON field)
- [ ] Update `DataAnalystMessage` model (rename from Question)
- [x] Fix Decimal JSON serialization issue ✅

### Phase 2: Context Management (Critical)
- [ ] Create `ConversationContextManager` class (`src/services/conversation_context_manager.py`)
- [ ] Implement `get_conversation_context()` method (sliding window, last 10)
- [ ] Implement `format_data_result_for_context()` method (first 5 rows only)
- [ ] Implement `build_enhanced_question()` method
- [ ] Implement `get_context_messages()` method
- [ ] Test context extraction and formatting

### Phase 3: Backend Services (Critical)
- [ ] Create `ConversationService`
- [ ] Update `DataAnalystService` to support conversations
- [ ] Add message type detection (DATA vs CONVERSATIONAL)
- [ ] Add conversation context to Vanna SQL generation
- [ ] Implement conversational message handling (LLM responses)
- [ ] Update API routes

### Phase 4: API Endpoints (High Priority)
- [ ] Create conversation CRUD endpoints
- [ ] Create group conversation endpoints
- [ ] Update message submission to support conversations
- [ ] Add conversation context to message responses
- [ ] Maintain backward compatibility with existing question endpoints

### Phase 5: Frontend (High Priority)
- [ ] Conversation list sidebar (collapsible)
- [ ] Conversation view with linear chat
- [ ] Message bubbles (data vs conversational)
- [ ] Data details right pane
- [ ] "New Conversation" and "New Group Conversation" buttons
- [ ] Conversation management (rename, delete, share)

### Phase 6: Training Integration (Medium Priority)
- [ ] Store all messages with conversation_id for training
- [ ] Export conversation Q&A pairs for Vanna training
- [ ] Periodic training job that includes conversation data

## Requirements Clarified ✅

1. **Conversation Lifecycle**: No auto-archive yet; users can delete; auto-create + button
2. **Context**: Last 10 messages, first 5 rows of data, full Q&A, explicit context manager class
3. **Naming**: Auto-generate from first question, allow rename, no preview snippet
4. **Sharing**: User conversations + group conversations with participants
5. **Limits**: 100 messages/conversation, 100 active conversations/user, centralized config
6. **UI**: Linear chat, conversation thread main object, right pane for data details
7. **Context Window**: Sliding last 10, messageID tracking, older questions for training

## Additional Considerations

### Message Type Detection

Need to determine if a question is DATA or CONVERSATIONAL:

**DATA Questions** (require SQL):
- "What is the total premium collected?"
- "Show me loss ratio by state"
- "How many claims do we have?"

**CONVERSATIONAL Questions** (no SQL):
- "What is our SOP for handling claims?"
- "Explain how loss ratio is calculated"
- "What does this data mean?"

**Implementation Strategy**:
- Start with keyword-based detection
- Can be enhanced with LLM classification later
- Allow explicit `message_type` parameter to override

### Training Data Collection

All messages (DATA and CONVERSATIONAL) should be stored for training:
- Store with `conversation_id` for context
- Store successful SQL queries for Vanna training
- Store Q&A pairs for LLM fine-tuning
- Periodic export job for training pipeline

## Questions Answered ✅

1. ✅ Conversation Lifecycle: No auto-archive; users can delete; auto-create + button
2. ✅ Context: Last 10 messages, first 5 rows, full Q&A, explicit context manager
3. ✅ Naming: Auto-generate from first question, allow rename, no preview
4. ✅ Sharing: User + group conversations with participants
5. ✅ Limits: 100 messages/conversation, 100 active conversations/user, centralized
6. ✅ UI: Linear chat, conversation main object, right pane for data
7. ✅ Context Window: Sliding last 10, messageID tracking, older for training

## Next Steps

1. ✅ **Immediate**: Fix Decimal JSON serialization bug (DONE)
2. **Phase 1**: Database & Models
3. **Phase 2**: Context Management System
4. **Phase 3**: Backend Services
5. **Phase 4**: API Endpoints
6. **Phase 5**: Frontend
7. **Phase 6**: Training Integration
