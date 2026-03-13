"""Add retrieval conversation persistence tables

Revision ID: zzc_retrieval_conversations
Revises: zzb_retrieval_tables
Create Date: 2026-02-08 12:00:00.000000

Adds:
- retrieval_conversations: persistent chat sessions
- retrieval_messages: messages within conversations
- conversation_id FK on retrieval_runs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "zzc_retrieval_conversations"
down_revision: tuple = ("zzb_retrieval_tables", "zz22_workspace_templates_kb")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["retrieval"]


def upgrade() -> None:
    # -- retrieval_conversations -----------------------------------------------
    op.create_table(
        "retrieval_conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("customer_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_retrieval_conv_user",
        "retrieval_conversations",
        ["customer_id", "user_id"],
    )

    # -- retrieval_messages ----------------------------------------------------
    op.create_table(
        "retrieval_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(length=36),
                  sa.ForeignKey("retrieval_conversations.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("follow_ups", sa.JSON(), nullable=True),
        sa.Column("run_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_retrieval_msg_conv",
        "retrieval_messages",
        ["conversation_id"],
    )

    # -- add conversation_id to retrieval_runs ---------------------------------
    op.add_column(
        "retrieval_runs",
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("retrieval_runs", "conversation_id")
    op.drop_index("idx_retrieval_msg_conv", table_name="retrieval_messages")
    op.drop_table("retrieval_messages")
    op.drop_index("idx_retrieval_conv_user", table_name="retrieval_conversations")
    op.drop_table("retrieval_conversations")
