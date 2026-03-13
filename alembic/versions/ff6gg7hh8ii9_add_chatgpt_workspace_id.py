"""Add chatgpt_workspace_id column to customer_ai_providers

Revision ID: ff6gg7hh8ii9
Revises: ee5ff6gg7hh8
Create Date: 2024-12-29

This migration adds a chatgpt_workspace_id column to the customer_ai_providers
table to store the ChatGPT Enterprise workspace UUID required for the
Compliance API.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ff6gg7hh8ii9'
down_revision = 'ee5ff6gg7hh8'  # The adoption feature migration
branch_labels = None
depends_on = None
tags = ["adoption"]


def upgrade() -> None:
    """Add chatgpt_workspace_id column to customer_ai_providers."""
    op.add_column(
        'customer_ai_providers',
        sa.Column(
            'chatgpt_workspace_id',
            sa.String(100),
            nullable=True,
            comment='ChatGPT Enterprise workspace UUID for Compliance API'
        )
    )


def downgrade() -> None:
    """Remove chatgpt_workspace_id column."""
    op.drop_column('customer_ai_providers', 'chatgpt_workspace_id')

