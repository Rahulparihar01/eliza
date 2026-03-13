"""Add retrieval subsystem tables (user_data_source_connections, retrieval_runs)

Revision ID: zzb_retrieval_tables
Revises: zza_tenant_themes
Create Date: 2026-02-07 10:00:00.000000

This migration adds:
- user_data_source_connections: per-user encrypted OAuth / private-app tokens
- retrieval_runs: individual search run tracking (status, results, provenance)
- Composite indexes for fast ownership lookups
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "zzb_retrieval_tables"
down_revision: Union[str, None] = "zza_tenant_themes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["retrieval"]


def upgrade() -> None:
    # -- user_data_source_connections ------------------------------------------
    op.create_table(
        "user_data_source_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("customer_id", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("auth_method", sa.String(length=30), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="connected"),
        sa.Column("connected_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index(
        "idx_user_connections_lookup",
        "user_data_source_connections",
        ["user_id", "source_type", "status"],
    )
    op.create_index(
        "idx_user_connections_customer",
        "user_data_source_connections",
        ["customer_id"],
    )

    # -- retrieval_runs --------------------------------------------------------
    op.create_table(
        "retrieval_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column("customer_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=True),
        sa.Column("sources_used", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_index(
        "idx_retrieval_runs_ownership",
        "retrieval_runs",
        ["customer_id", "user_id", "run_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_retrieval_runs_ownership", table_name="retrieval_runs")
    op.drop_table("retrieval_runs")

    op.drop_index("idx_user_connections_customer", table_name="user_data_source_connections")
    op.drop_index("idx_user_connections_lookup", table_name="user_data_source_connections")
    op.drop_table("user_data_source_connections")
