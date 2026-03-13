"""Merge current heads as flatten baseline bridge.

Revision ID: zz26_flatten_baseline_merge
Revises: zz25_kb_source_storage_settings, zzc_retrieval_conversations
Create Date: 2026-02-19
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "zz26_flatten_baseline_merge"
down_revision: Union[str, Sequence[str], None] = (
    "zz25_kb_source_storage_settings",
    "zzc_retrieval_conversations",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["retrieval"]


def upgrade() -> None:
    """Merge-only revision; no schema changes."""
    pass


def downgrade() -> None:
    """Merge-only revision; no schema changes."""
    pass
