"""Add user tenant memberships for multi-tenant support

Revision ID: bb2cc3dd4ee5
Revises: aa1bb2cc3dd4
Create Date: 2024-12-27

This migration adds support for users belonging to multiple tenants:
1. Creates user_tenant_memberships table to track tenant memberships
2. Adds tracking for default tenant and first-login popup state
3. Migrates existing users to have a membership in their current tenant
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bb2cc3dd4ee5'
down_revision = 'aa1bb2cc3dd4'
branch_labels = None
depends_on = None
tags = ["tenancy", "auth"]


def upgrade() -> None:
    # Create user_tenant_memberships table
    op.create_table(
        'user_tenant_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('first_login_completed', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'customer_id', name='uq_user_tenant_membership')
    )
    
    # Create indexes for efficient lookups
    op.create_index('ix_user_tenant_memberships_user_id', 'user_tenant_memberships', ['user_id'])
    op.create_index('ix_user_tenant_memberships_customer_id', 'user_tenant_memberships', ['customer_id'])
    
    # Migrate existing users to have a membership in their current tenant
    # This ensures backward compatibility - existing users get a membership record
    op.execute("""
        INSERT INTO user_tenant_memberships (user_id, customer_id, is_default, first_login_completed, created_at)
        SELECT 
            u.id,
            u.customer_id,
            true,  -- Current tenant becomes their default
            true,  -- They've already logged in, skip the popup
            COALESCE(u.created_at, NOW())
        FROM users u
        WHERE u.customer_id IS NOT NULL
        ON CONFLICT (user_id, customer_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index('ix_user_tenant_memberships_customer_id', table_name='user_tenant_memberships')
    op.drop_index('ix_user_tenant_memberships_user_id', table_name='user_tenant_memberships')
    op.drop_table('user_tenant_memberships')

