"""add scheduled job tables

Revision ID: kk1ll2mm3nn4
Revises: jj0kk1ll2mm3
Create Date: 2026-01-05 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'kk1ll2mm3nn4'
down_revision = 'jj0kk1ll2mm3'
branch_labels = None
depends_on = None
tags = ["ops"]


def upgrade():
    # Create scheduled_job_configs table
    op.create_table(
        'scheduled_job_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_name', sa.String(255), nullable=False),
        sa.Column('schedule_type', sa.String(20), nullable=False, server_default='interval'),
        sa.Column('schedule_value', sa.String(100), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', sa.String(20), nullable=False, server_default='idle'),
        sa.Column('last_run_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_task_id', sa.String(100), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_name')
    )
    op.create_index('ix_scheduled_job_configs_job_name', 'scheduled_job_configs', ['job_name'])
    
    # Create scheduled_job_executions table
    op.create_table(
        'scheduled_job_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_name', sa.String(100), nullable=False),
        sa.Column('task_id', sa.String(100), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='running'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_traceback', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(50), nullable=False, server_default='scheduler'),
        sa.Column('triggered_by_user_id', sa.Integer(), nullable=True),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scheduled_job_executions_job_name', 'scheduled_job_executions', ['job_name'])
    op.create_index('ix_scheduled_job_executions_task_id', 'scheduled_job_executions', ['task_id'])
    
    # Insert initial job configuration for adoption sync
    op.execute("""
        INSERT INTO scheduled_job_configs (
            job_name, display_name, description, task_name,
            schedule_type, schedule_value, is_enabled, last_run_status
        ) VALUES (
            'adoption-daily-sync',
            'Adoption Daily Sync',
            'Syncs ChatGPT Enterprise adoption metrics from OpenAI Compliance API. Runs automatically every 6 hours.',
            'adoption.daily_sync',
            'interval',
            '21600',
            true,
            'idle'
        )
    """)


def downgrade():
    op.drop_index('ix_scheduled_job_executions_task_id', table_name='scheduled_job_executions')
    op.drop_index('ix_scheduled_job_executions_job_name', table_name='scheduled_job_executions')
    op.drop_table('scheduled_job_executions')
    
    op.drop_index('ix_scheduled_job_configs_job_name', table_name='scheduled_job_configs')
    op.drop_table('scheduled_job_configs')

