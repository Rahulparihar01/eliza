"""Merge workspace prompt config and content writer migration heads.

Revision ID: zz24_merge_ws_content_heads
Revises: zz23_workspace_prompt_cfg, zzb_add_content_writer_tables
Create Date: 2026-02-12
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "zz24_merge_ws_content_heads"
down_revision: Union[str, Sequence[str], None] = ("zz23_workspace_prompt_cfg", "zzb_add_content_writer_tables")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core", "content"]


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
