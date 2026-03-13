"""Merge flatten baseline and Agent Mesh retrieval heads.

Revision ID: zze_flat_agent_mesh_merge
Revises: zz26_flatten_baseline_merge, zzd_agent_mesh_retrieval
Create Date: 2026-02-26
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "zze_flat_agent_mesh_merge"
down_revision: Union[str, Sequence[str], None] = (
    "zz26_flatten_baseline_merge",
    "zzd_agent_mesh_retrieval",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core", "retrieval"]


def upgrade() -> None:
    """Merge-only revision; no schema changes."""
    pass


def downgrade() -> None:
    """Merge-only revision; no schema changes."""
    pass
