"""Add MCP Phase 1 schema: conversation source tag + MCP server configs.

Revision ID: zz30_mcp_phase1_schema
Revises: zz29_adoption_manage_jobs
Create Date: 2026-03-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "zz30_mcp_phase1_schema"
down_revision: Union[str, Sequence[str], None] = "zz29_adoption_manage_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core"]


def upgrade() -> None:
    # -- 1. Add `source` column to ragflow_conversations --
    op.add_column(
        "ragflow_conversations",
        sa.Column("source", sa.String(50), nullable=True, server_default=None),
    )
    op.create_index(
        "ix_ragflow_conversations_source",
        "ragflow_conversations",
        ["source"],
        unique=False,
    )

    # -- 2. MCP server configuration table --
    op.create_table(
        "mcp_server_configs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("customer_id", sa.String(100), sa.ForeignKey("customers.customer_id"), nullable=False, index=True),
        sa.Column("server_type", sa.String(20), nullable=False, server_default="chat"),
        sa.Column("server_name", sa.String(100), nullable=False, server_default="eliza-chat"),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon_url", sa.String(500), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allowed_workspace_ids", JSONB(), nullable=True),
        sa.Column("allowed_tool_names", JSONB(), nullable=True),
        sa.Column("enabled_widgets", JSONB(), nullable=True),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("rate_limit_rph", sa.Integer(), nullable=False, server_default=sa.text("500")),
        sa.Column("max_concurrent_sessions", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("max_async_operations", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("oauth_client_id", sa.String(255), nullable=True),
        sa.Column("oauth_redirect_uris", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("mcp_server_configs")
    op.drop_index("ix_ragflow_conversations_source", table_name="ragflow_conversations")
    op.drop_column("ragflow_conversations", "source")
