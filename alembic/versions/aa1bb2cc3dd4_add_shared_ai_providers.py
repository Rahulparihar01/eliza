"""Add shared AI providers support

Revision ID: aa1bb2cc3dd4
Revises: z4a5b6c7d8e9, d7e8f9g0h1i2
Create Date: 2024-12-26

This migration adds support for platform-level AI provider sharing:
1. Adds is_global_shared column to customer_ai_providers
2. Creates shared_ai_providers junction table for selective sharing

Note: This is a merge migration that depends on both:
- z4a5b6c7d8e9 (implement_comprehensive_permissions)
- d7e8f9g0h1i2 (add_section_library_permissions)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'aa1bb2cc3dd4'
down_revision = ('z4a5b6c7d8e9', 'd7e8f9g0h1i2')
branch_labels = None
depends_on = None
tags = ["core", "tenancy"]


def upgrade() -> None:
    # Add is_global_shared column to customer_ai_providers
    # When True, this provider is automatically available to all tenants
    op.add_column(
        'customer_ai_providers',
        sa.Column('is_global_shared', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Create shared_ai_providers table for selective sharing
    op.create_table(
        'shared_ai_providers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('source_provider_id', sa.Integer(), sa.ForeignKey('customer_ai_providers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_customer_id', sa.String(100), sa.ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False),
        sa.Column('shared_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('shared_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint('source_provider_id', 'target_customer_id', name='uq_shared_provider_target')
    )
    
    # Create indexes for efficient queries
    op.create_index('ix_shared_providers_target', 'shared_ai_providers', ['target_customer_id'])
    op.create_index('ix_shared_providers_source', 'shared_ai_providers', ['source_provider_id'])
    op.create_index('ix_shared_providers_enabled', 'shared_ai_providers', ['target_customer_id', 'is_enabled'])
    
    # Create index on is_global_shared for efficient filtering
    op.create_index('ix_customer_ai_providers_global', 'customer_ai_providers', ['is_global_shared'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_customer_ai_providers_global', table_name='customer_ai_providers')
    op.drop_index('ix_shared_providers_enabled', table_name='shared_ai_providers')
    op.drop_index('ix_shared_providers_source', table_name='shared_ai_providers')
    op.drop_index('ix_shared_providers_target', table_name='shared_ai_providers')
    
    # Drop shared_ai_providers table
    op.drop_table('shared_ai_providers')
    
    # Remove is_global_shared column
    op.drop_column('customer_ai_providers', 'is_global_shared')

