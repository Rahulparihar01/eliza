"""Merge SSO and flatten baseline migration heads.

Revision ID: zz28_merge_sso_flatten_heads
Revises: zz26_flatten_baseline_merge, zz27_multi_provider_sso
Create Date: 2026-02-26
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "zz28_merge_sso_flatten_heads"
down_revision: Union[str, Sequence[str], None] = (
    "zz26_flatten_baseline_merge",
    "zz27_multi_provider_sso",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core", "auth", "tenancy", "retrieval"]


def upgrade() -> None:
    """Merge-only revision; no schema changes."""
    pass


def downgrade() -> None:
    """Merge-only revision; no schema changes."""
    pass
