"""merge_applet_heads

Revision ID: 07b7688bf8c2
Revises: e5b1b77ebabb, zze_flat_agent_mesh_merge
Create Date: 2026-03-02 20:10:07.108137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07b7688bf8c2'
down_revision: Union[str, Sequence[str], None] = ('e5b1b77ebabb', 'zze_flat_agent_mesh_merge')
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
