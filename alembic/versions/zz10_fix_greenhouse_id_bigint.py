"""Fix greenhouse_id column type from INTEGER to BIGINT

Revision ID: zz10_greenhouse_bigint
Revises: zz9_validate_citations
Create Date: 2026-01-28 16:30:00.000000

Greenhouse IDs can exceed the INTEGER max value (2,147,483,647).
For example: 126889264004

This migration changes the column type to BIGINT to support these large IDs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'zz10_greenhouse_bigint'
down_revision: Union[str, None] = 'zz9_validate_citations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["connectors"]


def upgrade() -> None:
    # Change greenhouse_id from INTEGER to BIGINT
    # This is safe because BIGINT can hold all INTEGER values
    op.alter_column(
        'candidates',
        'greenhouse_id',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True
    )


def downgrade() -> None:
    # Revert to INTEGER (warning: may fail if values exceed INTEGER range)
    op.alter_column(
        'candidates',
        'greenhouse_id',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True
    )
