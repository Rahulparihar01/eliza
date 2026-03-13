"""merge all heads

Revision ID: zz26_merge_all_heads
Revises: gg7hh8ii9jj0, kk1ll2mm3nn4, l2m3n4o5p6q7, zz10_greenhouse_bigint, zz20_add_conversation_uuid, zz23_workspace_prompt_cfg, zz26_flatten_baseline_merge, zzb_retrieval_tables
Create Date: 2026-02-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'zz26_merge_all_heads'
down_revision: Union[str, Sequence[str], None] = (
    'gg7hh8ii9jj0',
    'kk1ll2mm3nn4',
    'l2m3n4o5p6q7',
    'zz10_greenhouse_bigint',
    'zz20_add_conversation_uuid',
    'zz23_workspace_prompt_cfg',
    'zz26_flatten_baseline_merge',
    'zzb_retrieval_tables',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags = ["core"]


def upgrade() -> None:
    # This is a merge migration - no schema changes
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes
    pass
