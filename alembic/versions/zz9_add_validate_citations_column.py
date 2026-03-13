"""Add validate_citations column to rag_eval_runs

Revision ID: zz9_validate_citations
Revises: zz7_citation_eval
Create Date: 2026-01-15 14:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'zz9_validate_citations'
down_revision: Union[str, None] = 'zz7_citation_eval'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["evals"]


def upgrade() -> None:
    # Add validate_citations column to rag_eval_runs table
    op.add_column(
        "rag_eval_runs",
        sa.Column("validate_citations", sa.Boolean(), nullable=True, server_default="false")
    )


def downgrade() -> None:
    op.drop_column("rag_eval_runs", "validate_citations")
