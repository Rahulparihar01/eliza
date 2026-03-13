"""Add data analyst telemetry table

Revision ID: 7e60333efb2e
Revises: 5fca85f13108
Create Date: 2025-11-19 22:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7e60333efb2e'
down_revision = '5fca85f13108'
branch_labels = None
depends_on = None
tags = ["bi"]


def upgrade() -> None:
    """Create data analyst telemetry table for flow event tracking."""
    
    op.create_table(
        'data_analyst_telemetry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telemetry_id', sa.String(length=100), nullable=False),
        sa.Column('message_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('agent_name', sa.String(length=255), nullable=True),
        sa.Column('tool_name', sa.String(length=255), nullable=True),
        sa.Column('stage_name', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('progress_percentage', sa.Integer(), nullable=True),
        sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telemetry_id')
    )
    
    op.create_index('ix_data_analyst_telemetry_telemetry_id', 'data_analyst_telemetry', ['telemetry_id'], unique=True)
    op.create_index('ix_data_analyst_telemetry_message_id', 'data_analyst_telemetry', ['message_id'], unique=False)
    op.create_index('ix_data_analyst_telemetry_event_type', 'data_analyst_telemetry', ['event_type'], unique=False)
    op.create_index('ix_data_analyst_telemetry_timestamp', 'data_analyst_telemetry', ['timestamp'], unique=False)
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_data_analyst_telemetry_message_id_data_analyst_messages',
        'data_analyst_telemetry',
        'data_analyst_messages',
        ['message_id'],
        ['message_id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    """Drop data analyst telemetry table."""
    op.drop_constraint('fk_data_analyst_telemetry_message_id_data_analyst_messages', 'data_analyst_telemetry', type_='foreignkey')
    op.drop_index('ix_data_analyst_telemetry_timestamp', table_name='data_analyst_telemetry')
    op.drop_index('ix_data_analyst_telemetry_event_type', table_name='data_analyst_telemetry')
    op.drop_index('ix_data_analyst_telemetry_message_id', table_name='data_analyst_telemetry')
    op.drop_index('ix_data_analyst_telemetry_telemetry_id', table_name='data_analyst_telemetry')
    op.drop_table('data_analyst_telemetry')
