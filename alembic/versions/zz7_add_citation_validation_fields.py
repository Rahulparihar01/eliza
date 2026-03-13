"""Add citation validation fields to RAG eval tables

Revision ID: zz7_citation_eval
Revises: zz6_add_rag_eval_tables
Create Date: 2026-01-15 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'zz7_citation_eval'
down_revision: Union[str, None] = 'zz6_add_rag_eval_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["evals"]


def upgrade() -> None:
    op.add_column(
        'rag_eval_runs',
        sa.Column('eval_type', sa.String(length=50), nullable=False, server_default='rag_full')
    )
    op.add_column(
        'rag_eval_runs',
        sa.Column('citation_page_accuracy_mean', sa.Float(), nullable=True)
    )
    op.add_column(
        'rag_eval_results',
        sa.Column('citation_page_validations', sa.JSON(), nullable=True)
    )
    op.add_column(
        'rag_eval_results',
        sa.Column('citation_page_score', sa.Float(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('rag_eval_results', 'citation_page_score')
    op.drop_column('rag_eval_results', 'citation_page_validations')
    op.drop_column('rag_eval_runs', 'citation_page_accuracy_mean')
    op.drop_column('rag_eval_runs', 'eval_type')
