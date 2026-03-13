"""add_talent_analysis_tables

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-10-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'  # Previous migration for connector tables
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade() -> None:
    # Create talent_analyses table
    op.create_table(
        'talent_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.String(length=100), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        
        # Input
        sa.Column('job_description', sa.Text(), nullable=True),
        sa.Column('ideal_candidate_description', sa.Text(), nullable=True),
        sa.Column('manual_persona', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Status
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Results
        sa.Column('ideal_persona', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('candidates', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('insights_report', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Metadata
        sa.Column('candidate_count', sa.Integer(), server_default='0'),
        sa.Column('top_candidate_fit_score', sa.Float(), nullable=True),
        sa.Column('average_fit_score', sa.Float(), nullable=True),
        
        # Timing
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Celery task ID
        sa.Column('task_id', sa.String(length=100), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.UniqueConstraint('analysis_id')
    )
    
    # Create indexes for talent_analyses
    op.create_index('ix_talent_analysis_customer_status', 'talent_analyses', ['customer_id', 'status'])
    op.create_index('ix_talent_analysis_created', 'talent_analyses', ['created_at'])
    op.create_index(op.f('ix_talent_analyses_analysis_id'), 'talent_analyses', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_talent_analyses_task_id'), 'talent_analyses', ['task_id'], unique=False)
    
    # Create talent_analysis_events table
    op.create_table(
        'talent_analysis_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.String(length=100), nullable=False),
        
        # Event details
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('progress_percentage', sa.Integer(), nullable=True),
        
        # Data payload
        sa.Column('data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Timing
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['talent_analyses.analysis_id'], ),
    )
    
    # Create indexes for talent_analysis_events
    op.create_index('ix_talent_event_analysis_timestamp', 'talent_analysis_events', ['analysis_id', 'timestamp'])
    op.create_index(op.f('ix_talent_analysis_events_analysis_id'), 'talent_analysis_events', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_talent_analysis_events_timestamp'), 'talent_analysis_events', ['timestamp'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index(op.f('ix_talent_analysis_events_timestamp'), table_name='talent_analysis_events')
    op.drop_index(op.f('ix_talent_analysis_events_analysis_id'), table_name='talent_analysis_events')
    op.drop_index('ix_talent_event_analysis_timestamp', table_name='talent_analysis_events')
    
    op.drop_index(op.f('ix_talent_analyses_task_id'), table_name='talent_analyses')
    op.drop_index(op.f('ix_talent_analyses_analysis_id'), table_name='talent_analyses')
    op.drop_index('ix_talent_analysis_created', table_name='talent_analyses')
    op.drop_index('ix_talent_analysis_customer_status', table_name='talent_analyses')
    
    # Drop tables
    op.drop_table('talent_analysis_events')
    op.drop_table('talent_analyses')

