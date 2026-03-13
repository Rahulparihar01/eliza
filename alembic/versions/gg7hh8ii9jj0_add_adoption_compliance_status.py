"""Add adoption compliance status columns to customer_ai_providers

Revision ID: gg7hh8ii9jj0
Revises: ff6gg7hh8ii9
Create Date: 2026-01-02

This migration adds columns to track the compliance API test status for
adoption-enabled providers. This allows the UI to show whether the
compliance API is accessible or needs attention.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'gg7hh8ii9jj0'
down_revision = 'ff6gg7hh8ii9'
branch_labels = None
depends_on = None
tags = ["adoption"]


def upgrade() -> None:
    """Add adoption compliance status columns."""
    # Status: 'success', 'failed', 'untested'
    op.add_column(
        'customer_ai_providers',
        sa.Column(
            'adoption_compliance_status',
            sa.String(20),
            nullable=True,
            comment='Compliance API test status: success, failed, untested'
        )
    )
    
    # Last time the compliance API was tested
    op.add_column(
        'customer_ai_providers',
        sa.Column(
            'adoption_compliance_last_checked',
            sa.DateTime(timezone=True),
            nullable=True,
            comment='When compliance API was last tested'
        )
    )
    
    # Error message if the test failed
    op.add_column(
        'customer_ai_providers',
        sa.Column(
            'adoption_compliance_error',
            sa.Text(),
            nullable=True,
            comment='Error message from last compliance API test'
        )
    )


def downgrade() -> None:
    """Remove adoption compliance status columns."""
    op.drop_column('customer_ai_providers', 'adoption_compliance_error')
    op.drop_column('customer_ai_providers', 'adoption_compliance_last_checked')
    op.drop_column('customer_ai_providers', 'adoption_compliance_status')

