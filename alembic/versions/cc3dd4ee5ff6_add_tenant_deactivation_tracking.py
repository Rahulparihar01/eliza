"""Add tenant deactivation tracking fields

Revision ID: cc3dd4ee5ff6
Revises: bb2cc3dd4ee5
Create Date: 2024-12-27

Adds fields to track tenant deactivation:
- deactivated_at: When the tenant was deactivated
- deactivated_by: User ID who deactivated the tenant  
- deactivation_reason: Reason for deactivation
"""

from alembic import op
import sqlalchemy as sa


revision = 'cc3dd4ee5ff6'
down_revision = 'bb2cc3dd4ee5'
branch_labels = None
depends_on = None
tags = ["tenancy", "auth"]


def upgrade() -> None:
    # Add deactivation tracking columns to customers table
    op.add_column('customers', sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('customers', sa.Column('deactivated_by', sa.Integer(), nullable=True))
    op.add_column('customers', sa.Column('deactivation_reason', sa.Text(), nullable=True))
    
    # Add foreign key constraint for deactivated_by
    op.create_foreign_key(
        'fk_customers_deactivated_by_users',
        'customers',
        'users',
        ['deactivated_by'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # Add index for faster lookups on active status
    op.create_index('ix_customers_is_active', 'customers', ['is_active'])


def downgrade() -> None:
    # Drop the index
    op.drop_index('ix_customers_is_active', table_name='customers')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_customers_deactivated_by_users', 'customers', type_='foreignkey')
    
    # Drop the columns
    op.drop_column('customers', 'deactivation_reason')
    op.drop_column('customers', 'deactivated_by')
    op.drop_column('customers', 'deactivated_at')

