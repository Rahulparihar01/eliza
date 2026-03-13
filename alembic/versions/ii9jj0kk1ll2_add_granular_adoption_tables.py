"""Add granular adoption tables for GPTs, conversations, and user-GPT interactions

Revision ID: ii9jj0kk1ll2
Revises: hh8ii9jj0kk1
Create Date: 2026-01-04

This migration adds three new tables for richer adoption analytics:
- adoption_gpts: GPT metadata synced from ChatGPT Enterprise
- adoption_conversations: Individual conversation records (no content)
- adoption_user_gpt_interactions: User-GPT interaction summaries

These tables enable:
- Tracking which users interact with which GPTs
- User outreach for feedback collection
- Detailed per-GPT and per-user analytics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ii9jj0kk1ll2'
down_revision = 'hh8ii9jj0kk1'
branch_labels = None
depends_on = None
tags = ["adoption"]


def upgrade():
    # Create adoption_gpts table
    op.create_table(
        'adoption_gpts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Tenant ownership
        sa.Column('customer_id', sa.String(100), sa.ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False, index=True),
        
        # GPT identifiers
        sa.Column('external_gpt_id', sa.String(100), nullable=False, index=True),
        sa.Column('short_url', sa.String(255), nullable=True),
        
        # GPT metadata
        sa.Column('name', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        
        # Creator info
        sa.Column('creator_user_id', sa.String(100), nullable=True, index=True),
        sa.Column('creator_email', sa.String(255), nullable=True, index=True),
        sa.Column('creator_name', sa.String(255), nullable=True),
        
        # Visibility and status
        sa.Column('visibility', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        
        # Timestamps from OpenAI
        sa.Column('external_created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('external_updated_at', sa.DateTime(timezone=True), nullable=True),
        
        # Sync tracking
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'external_gpt_id', name='uq_adoption_gpt'),
    )
    
    # Create adoption_conversations table
    op.create_table(
        'adoption_conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Tenant ownership
        sa.Column('customer_id', sa.String(100), sa.ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Conversation identifiers
        sa.Column('external_conversation_id', sa.String(100), nullable=False, index=True),
        
        # User info
        sa.Column('user_external_id', sa.String(100), nullable=True, index=True),
        sa.Column('user_email', sa.String(255), nullable=True, index=True),
        
        # GPT used (nullable - not all conversations use a GPT)
        sa.Column('gpt_id', sa.Integer(), sa.ForeignKey('adoption_gpts.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('external_gpt_id', sa.String(100), nullable=True, index=True),
        
        # Conversation metrics (no content!)
        sa.Column('message_count', sa.Integer(), nullable=False, default=0),
        sa.Column('user_message_count', sa.Integer(), nullable=False, default=0),
        
        # Timestamps
        sa.Column('conversation_created_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('conversation_updated_at', sa.DateTime(timezone=True), nullable=True),
        
        # Sync tracking
        sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'external_conversation_id', name='uq_adoption_conversation'),
    )
    
    # Create adoption_user_gpt_interactions table
    op.create_table(
        'adoption_user_gpt_interactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        
        # Tenant ownership
        sa.Column('customer_id', sa.String(100), sa.ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False, index=True),
        
        # User info
        sa.Column('user_external_id', sa.String(100), nullable=False, index=True),
        sa.Column('user_email', sa.String(255), nullable=True, index=True),
        
        # GPT reference
        sa.Column('gpt_id', sa.Integer(), sa.ForeignKey('adoption_gpts.id', ondelete='CASCADE'), nullable=False, index=True),
        
        # Interaction metrics
        sa.Column('total_conversations', sa.Integer(), nullable=False, default=0),
        sa.Column('total_messages', sa.Integer(), nullable=False, default=0),
        
        # Timestamps
        sa.Column('first_interaction_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'user_external_id', 'gpt_id', name='uq_user_gpt_interaction'),
    )
    
    # Add indexes for common queries (if not exists - for idempotency)
    from sqlalchemy import text
    connection = op.get_bind()
    
    # Check and create indexes if they don't exist
    result = connection.execute(text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_adoption_gpts_creator_email'"))
    if not result.fetchone():
        op.create_index('ix_adoption_gpts_creator_email', 'adoption_gpts', ['creator_email'])
    
    result = connection.execute(text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_adoption_conversations_created_at'"))
    if not result.fetchone():
        op.create_index('ix_adoption_conversations_created_at', 'adoption_conversations', ['conversation_created_at'])
    
    result = connection.execute(text("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_adoption_user_gpt_last_interaction'"))
    if not result.fetchone():
        op.create_index('ix_adoption_user_gpt_last_interaction', 'adoption_user_gpt_interactions', ['last_interaction_at'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_adoption_user_gpt_last_interaction', table_name='adoption_user_gpt_interactions')
    op.drop_index('ix_adoption_conversations_created_at', table_name='adoption_conversations')
    op.drop_index('ix_adoption_gpts_creator_email', table_name='adoption_gpts')
    
    # Drop tables in reverse order (due to foreign keys)
    op.drop_table('adoption_user_gpt_interactions')
    op.drop_table('adoption_conversations')
    op.drop_table('adoption_gpts')

