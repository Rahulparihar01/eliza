"""Add UUID to ragflow_conversations

Revision ID: zz20_add_conversation_uuid
Revises: zz19_add_custom_vlm_parser_type
Create Date: 2026-01-28

Adds UUID column to conversations for URL-friendly identification.
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = 'zz20_add_conversation_uuid'
down_revision = 'zz19_add_custom_vlm_parser_type'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    # Add uuid column (nullable first to handle existing rows)
    op.add_column('ragflow_conversations', sa.Column('uuid', sa.String(36), nullable=True))
    
    # Generate UUIDs for existing rows
    connection = op.get_bind()
    conversations = connection.execute(sa.text("SELECT id FROM ragflow_conversations WHERE uuid IS NULL"))
    for row in conversations:
        connection.execute(
            sa.text("UPDATE ragflow_conversations SET uuid = :uuid WHERE id = :id"),
            {"uuid": str(uuid.uuid4()), "id": row[0]}
        )
    
    # Make column non-nullable and add index
    op.alter_column('ragflow_conversations', 'uuid', nullable=False)
    op.create_unique_constraint('uq_ragflow_conversations_uuid', 'ragflow_conversations', ['uuid'])
    op.create_index('ix_ragflow_conversations_uuid', 'ragflow_conversations', ['uuid'])


def downgrade() -> None:
    op.drop_index('ix_ragflow_conversations_uuid', table_name='ragflow_conversations')
    op.drop_constraint('uq_ragflow_conversations_uuid', 'ragflow_conversations', type_='unique')
    op.drop_column('ragflow_conversations', 'uuid')
