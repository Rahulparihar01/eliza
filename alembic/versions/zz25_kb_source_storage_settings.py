"""Add source/storage fields to knowledge bases.

Revision ID: zz25_kb_source_storage_settings
Revises: zz24_merge_ws_content_heads
Create Date: 2026-02-17

This migration is idempotent so environments that received manual schema
changes before this revision was restored can still upgrade cleanly.
"""

from typing import Sequence, Set, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "zz25_kb_source_storage_settings"
down_revision: Union[str, Sequence[str], None] = "zz24_merge_ws_content_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core"]


def _column_names(table_name: str) -> Set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> Set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    columns = _column_names("knowledge_bases")

    if "source_type" not in columns:
        op.add_column(
            "knowledge_bases",
            sa.Column("source_type", sa.String(length=50), nullable=True),
        )
    if "source_config" not in columns:
        op.add_column(
            "knowledge_bases",
            sa.Column("source_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        )
    if "storage_backend" not in columns:
        op.add_column(
            "knowledge_bases",
            sa.Column("storage_backend", sa.String(length=50), nullable=True),
        )
    if "storage_config" not in columns:
        op.add_column(
            "knowledge_bases",
            sa.Column("storage_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        )

    columns = _column_names("knowledge_bases")

    if "source_type" in columns:
        op.execute("UPDATE knowledge_bases SET source_type = 'elasticsearch' WHERE source_type IS NULL")
        op.alter_column("knowledge_bases", "source_type", existing_type=sa.String(length=50), nullable=False)
    if "storage_backend" in columns:
        op.execute("UPDATE knowledge_bases SET storage_backend = 'tenant_default' WHERE storage_backend IS NULL")
        op.alter_column(
            "knowledge_bases",
            "storage_backend",
            existing_type=sa.String(length=50),
            nullable=False,
        )

    indexes = _index_names("knowledge_bases")
    if "ix_knowledge_bases_source_type" not in indexes:
        op.create_index("ix_knowledge_bases_source_type", "knowledge_bases", ["source_type"])
    if "ix_knowledge_bases_storage_backend" not in indexes:
        op.create_index("ix_knowledge_bases_storage_backend", "knowledge_bases", ["storage_backend"])


def downgrade() -> None:
    indexes = _index_names("knowledge_bases")
    if "ix_knowledge_bases_storage_backend" in indexes:
        op.drop_index("ix_knowledge_bases_storage_backend", table_name="knowledge_bases")
    if "ix_knowledge_bases_source_type" in indexes:
        op.drop_index("ix_knowledge_bases_source_type", table_name="knowledge_bases")

    columns = _column_names("knowledge_bases")
    if "storage_config" in columns:
        op.drop_column("knowledge_bases", "storage_config")
    if "storage_backend" in columns:
        op.drop_column("knowledge_bases", "storage_backend")
    if "source_config" in columns:
        op.drop_column("knowledge_bases", "source_config")
    if "source_type" in columns:
        op.drop_column("knowledge_bases", "source_type")
