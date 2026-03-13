"""add_conversation_model_and_rename_questions_to_messages

Revision ID: 5fca85f13108
Revises: j0k1l2m3n4o5
Create Date: 2025-11-19 18:47:29.801436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5fca85f13108'
down_revision: Union[str, Sequence[str], None] = 'j0k1l2m3n4o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core"]


def upgrade() -> None:
    """Add conversation model and rename questions to messages."""
    
    # Create enum types if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE conversation_type AS ENUM (
                'user',
                'group'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;

        DO $$ BEGIN
            CREATE TYPE conversation_status AS ENUM (
                'active',
                'deleted'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;

        DO $$ BEGIN
            CREATE TYPE message_type AS ENUM (
                'data',
                'conversational'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create data_analyst_conversations table
    op.create_table(
        'data_analyst_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),  # Creator/owner
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('data_source_type', sa.String(length=50), nullable=False),
        
        # Conversation type and sharing
        sa.Column('conversation_type', sa.String(length=50), nullable=False, server_default='user'),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        
        # Participants (JSON array: [{user_id: int, role: str, joined_at: timestamp}])
        sa.Column('participants', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        
        # Conversation metadata
        sa.Column('title', sa.String(length=255), nullable=True),  # Auto-generated, user can rename
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        
        # Context for LLM/Vanna (stores last 10 messages summary)
        sa.Column('conversation_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_activity_at', sa.DateTime(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('conversation_id')
    )
    
    # Create indexes for conversations
    op.create_index('ix_data_analyst_conversations_conversation_id', 'data_analyst_conversations', ['conversation_id'])
    op.create_index('ix_data_analyst_conversations_user_id', 'data_analyst_conversations', ['user_id'])
    op.create_index('ix_data_analyst_conversations_customer_id', 'data_analyst_conversations', ['customer_id'])
    op.create_index('ix_data_analyst_conversations_conversation_type', 'data_analyst_conversations', ['conversation_type'])
    op.create_index('ix_data_analyst_conversations_status', 'data_analyst_conversations', ['status'])
    op.create_index('ix_data_analyst_conversations_last_activity_at', 'data_analyst_conversations', ['last_activity_at'])
    
    # Create GIN index for JSONB participants array queries
    op.execute("CREATE INDEX ix_data_analyst_conversations_participants ON data_analyst_conversations USING GIN (participants)")
    
    # Rename data_analyst_questions to data_analyst_messages
    op.rename_table('data_analyst_questions', 'data_analyst_messages')
    
    # Add conversation and message tracking columns
    op.add_column('data_analyst_messages', sa.Column('conversation_id', sa.String(length=100), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('message_id', sa.String(length=100), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('message_order', sa.Integer(), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('message_type', sa.String(length=50), nullable=False, server_default='data'))
    op.add_column('data_analyst_messages', sa.Column('parent_message_id', sa.String(length=100), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('conversational_response', sa.Text(), nullable=True))
    
    # Add intent detection and clarification columns
    op.add_column('data_analyst_messages', sa.Column('detected_intent', sa.String(length=50), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('intent_confidence', sa.String(length=50), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('clarification_prompt', sa.Text(), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('clarification_response', sa.Text(), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('clarified_question', sa.Text(), nullable=True))
    op.add_column('data_analyst_messages', sa.Column('intent_confirmed', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_message_conversation',
        'data_analyst_messages',
        'data_analyst_conversations',
        ['conversation_id'],
        ['conversation_id'],
        ondelete='CASCADE'
    )
    
    # Create indexes for messages
    op.create_index('ix_data_analyst_messages_conversation_id', 'data_analyst_messages', ['conversation_id'])
    op.create_index('ix_data_analyst_messages_message_id', 'data_analyst_messages', ['message_id'], unique=True)
    op.create_index('ix_data_analyst_messages_message_order', 'data_analyst_messages', ['conversation_id', 'message_order'])
    op.create_index('ix_data_analyst_messages_message_type', 'data_analyst_messages', ['message_type'])
    op.create_index('ix_data_analyst_messages_parent_message_id', 'data_analyst_messages', ['parent_message_id'])


def downgrade() -> None:
    """Revert conversation model and rename messages back to questions."""
    
    # Drop indexes for messages
    op.drop_index('ix_data_analyst_messages_parent_message_id', table_name='data_analyst_messages')
    op.drop_index('ix_data_analyst_messages_message_type', table_name='data_analyst_messages')
    op.drop_index('ix_data_analyst_messages_message_order', table_name='data_analyst_messages')
    op.drop_index('ix_data_analyst_messages_message_id', table_name='data_analyst_messages')
    op.drop_index('ix_data_analyst_messages_conversation_id', table_name='data_analyst_messages')
    
    # Drop foreign key
    op.drop_constraint('fk_message_conversation', 'data_analyst_messages', type_='foreignkey')
    
    # Remove conversation-related columns
    op.drop_column('data_analyst_messages', 'intent_confirmed')
    op.drop_column('data_analyst_messages', 'clarified_question')
    op.drop_column('data_analyst_messages', 'clarification_response')
    op.drop_column('data_analyst_messages', 'clarification_prompt')
    op.drop_column('data_analyst_messages', 'intent_confidence')
    op.drop_column('data_analyst_messages', 'detected_intent')
    op.drop_column('data_analyst_messages', 'conversational_response')
    op.drop_column('data_analyst_messages', 'parent_message_id')
    op.drop_column('data_analyst_messages', 'message_type')
    op.drop_column('data_analyst_messages', 'message_order')
    op.drop_column('data_analyst_messages', 'message_id')
    op.drop_column('data_analyst_messages', 'conversation_id')
    
    # Rename table back
    op.rename_table('data_analyst_messages', 'data_analyst_questions')
    
    # Drop conversation table indexes
    op.execute("DROP INDEX IF EXISTS ix_data_analyst_conversations_participants")
    op.drop_index('ix_data_analyst_conversations_last_activity_at', table_name='data_analyst_conversations')
    op.drop_index('ix_data_analyst_conversations_status', table_name='data_analyst_conversations')
    op.drop_index('ix_data_analyst_conversations_conversation_type', table_name='data_analyst_conversations')
    op.drop_index('ix_data_analyst_conversations_customer_id', table_name='data_analyst_conversations')
    op.drop_index('ix_data_analyst_conversations_user_id', table_name='data_analyst_conversations')
    op.drop_index('ix_data_analyst_conversations_conversation_id', table_name='data_analyst_conversations')
    
    # Drop conversation table
    op.drop_table('data_analyst_conversations')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS message_type")
    op.execute("DROP TYPE IF EXISTS conversation_status")
    op.execute("DROP TYPE IF EXISTS conversation_type")
