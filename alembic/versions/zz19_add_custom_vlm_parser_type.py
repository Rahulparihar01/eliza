"""Add custom-vlm to ragflow_parser_type enum

Revision ID: zz19_add_custom_vlm_parser_type
Revises: zz18_ragflow_domain_spec_updates
Create Date: 2026-01-28

Adds 'custom-vlm' option for using hosted VLM models (OpenAI-compatible) for document parsing.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'zz19_add_custom_vlm_parser_type'
down_revision = 'zz18_ragflow_domain_spec_updates'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    # Add 'custom-vlm' to the ragflow_parser_type enum
    op.execute("ALTER TYPE ragflow_parser_type ADD VALUE IF NOT EXISTS 'custom-vlm'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    # Would need to recreate the type, which is complex and rarely needed
    pass
