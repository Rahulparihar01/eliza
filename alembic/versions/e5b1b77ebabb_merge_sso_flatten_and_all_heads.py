"""merge_sso_flatten_and_all_heads

Revision ID: e5b1b77ebabb
Revises: zz26_merge_all_heads, zz28_merge_sso_flatten_heads
Create Date: 2026-03-02 19:59:18.494149

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b1b77ebabb'
down_revision: Union[str, Sequence[str], None] = ('zz26_merge_all_heads', 'zz28_merge_sso_flatten_heads')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# Applet migration tags (required for selective migration mode).
# Example: tags: Sequence[str] = ["core"] or ["adoption"]
tags: Sequence[str] = ["core", "auth", "tenancy", "retrieval"]


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
