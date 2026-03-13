"""Merge multiple heads into single head

Revision ID: zz3_merge_heads
Revises: kk1ll2mm3nn4, zz5_add_missing_tables
Create Date: 2026-01-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'zz3_merge_heads'
down_revision = ('kk1ll2mm3nn4', 'zz5_add_missing_tables')
branch_labels = None
depends_on = None
tags = ["core", "ops"]


def upgrade():
    """Merge migration - no schema changes needed."""
    pass


def downgrade():
    """Merge migration - no schema changes needed."""
    pass
