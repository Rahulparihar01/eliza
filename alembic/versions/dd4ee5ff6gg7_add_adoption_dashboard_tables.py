"""Add adoption dashboard tables

Revision ID: dd4ee5ff6gg7
Revises: cc3dd4ee5ff6
Create Date: 2025-12-28

This migration adds tables for the adoption dashboard feature:
- Adds is_adoption_source to customer_ai_providers
- Creates adoption_data_shares table for tenant-to-tenant sharing
- Creates adoption_daily_metrics table for aggregated metrics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


revision = 'dd4ee5ff6gg7'
down_revision = 'cc3dd4ee5ff6'
branch_labels = None
depends_on = None
tags = ["adoption"]


def upgrade() -> None:
    # =========================================================================
    # 1. Add is_adoption_source to customer_ai_providers
    # =========================================================================
    op.add_column(
        'customer_ai_providers',
        sa.Column('is_adoption_source', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Index for finding adoption sources quickly
    op.create_index(
        'ix_customer_ai_providers_adoption_source',
        'customer_ai_providers',
        ['is_adoption_source'],
        postgresql_where=sa.text('is_adoption_source = true')
    )
    
    # =========================================================================
    # 2. Create adoption_data_shares table
    # =========================================================================
    op.create_table(
        'adoption_data_shares',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        # WHO is sharing (the data owner)
        sa.Column('source_customer_id', sa.String(length=100), nullable=False),
        
        # WHO can view the data
        sa.Column('target_customer_id', sa.String(length=100), nullable=False),
        
        # Configuration
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('share_level', sa.String(length=20), nullable=False, server_default='read'),  # "read" or "admin"
        
        # Audit
        sa.Column('shared_by_user_id', sa.Integer(), nullable=True),
        sa.Column('shared_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['shared_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('source_customer_id', 'target_customer_id', name='uq_adoption_share')
    )
    
    op.create_index('ix_adoption_data_shares_source', 'adoption_data_shares', ['source_customer_id'])
    op.create_index('ix_adoption_data_shares_target', 'adoption_data_shares', ['target_customer_id'])
    op.create_index('ix_adoption_data_shares_enabled', 'adoption_data_shares', ['is_enabled'])
    
    # =========================================================================
    # 3. Create adoption_daily_metrics table
    # =========================================================================
    op.create_table(
        'adoption_daily_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        # Identifiers
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),  # openai_compliance, eliza_platform, etc.
        sa.Column('metric_date', sa.Date(), nullable=False),
        
        # Core metrics
        sa.Column('active_users', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_messages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_conversations', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_images', sa.Integer(), nullable=False, server_default='0'),
        
        # Token usage
        sa.Column('input_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.BigInteger(), nullable=False, server_default='0'),
        
        # Breakdowns (JSONB for flexibility)
        sa.Column('model_breakdown', JSON, nullable=True),   # {"gpt-4": 1000, "gpt-4o": 500}
        sa.Column('top_gpts', JSON, nullable=True),          # [{"name": "...", "uses": 100}]
        sa.Column('user_distribution', JSON, nullable=True), # {"power": 10, "regular": 50, "light": 100}
        
        # Additional metadata
        sa.Column('sync_metadata', JSON, nullable=True),     # {"last_sync_id": "...", "records_processed": 100}
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('customer_id', 'source_type', 'metric_date', name='uq_adoption_metrics')
    )
    
    op.create_index('ix_adoption_daily_metrics_customer', 'adoption_daily_metrics', ['customer_id'])
    op.create_index('ix_adoption_daily_metrics_source_type', 'adoption_daily_metrics', ['source_type'])
    op.create_index('ix_adoption_daily_metrics_date', 'adoption_daily_metrics', ['metric_date'])
    op.create_index(
        'ix_adoption_daily_metrics_customer_date',
        'adoption_daily_metrics',
        ['customer_id', 'metric_date']
    )


def downgrade() -> None:
    # Drop adoption_daily_metrics
    op.drop_index('ix_adoption_daily_metrics_customer_date', table_name='adoption_daily_metrics')
    op.drop_index('ix_adoption_daily_metrics_date', table_name='adoption_daily_metrics')
    op.drop_index('ix_adoption_daily_metrics_source_type', table_name='adoption_daily_metrics')
    op.drop_index('ix_adoption_daily_metrics_customer', table_name='adoption_daily_metrics')
    op.drop_table('adoption_daily_metrics')
    
    # Drop adoption_data_shares
    op.drop_index('ix_adoption_data_shares_enabled', table_name='adoption_data_shares')
    op.drop_index('ix_adoption_data_shares_target', table_name='adoption_data_shares')
    op.drop_index('ix_adoption_data_shares_source', table_name='adoption_data_shares')
    op.drop_table('adoption_data_shares')
    
    # Remove is_adoption_source from customer_ai_providers
    op.drop_index('ix_customer_ai_providers_adoption_source', table_name='customer_ai_providers')
    op.drop_column('customer_ai_providers', 'is_adoption_source')

