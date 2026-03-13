"""Add GPT adoption metrics columns

Revision ID: jj0kk1ll2mm3
Revises: ii9jj0kk1ll2
Create Date: 2026-01-04

Adds columns to track GPT adoption rate:
- gpt_conversations: Conversations using custom GPTs
- base_conversations: Conversations using base ChatGPT
- unique_gpts: Count of unique GPTs used
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'jj0kk1ll2mm3'
down_revision: Union[str, None] = 'ii9jj0kk1ll2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["adoption"]


def upgrade() -> None:
    # Add GPT adoption tracking columns to adoption_daily_metrics
    op.add_column('adoption_daily_metrics', sa.Column('gpt_conversations', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('adoption_daily_metrics', sa.Column('base_conversations', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('adoption_daily_metrics', sa.Column('unique_gpts', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('adoption_daily_metrics', 'unique_gpts')
    op.drop_column('adoption_daily_metrics', 'base_conversations')
    op.drop_column('adoption_daily_metrics', 'gpt_conversations')

