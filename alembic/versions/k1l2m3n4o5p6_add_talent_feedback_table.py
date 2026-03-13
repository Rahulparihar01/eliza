"""add talent feedback table

Revision ID: add_talent_feedback
Revises: 
Create Date: 2025-11-24 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'k1l2m3n4o5p6'
down_revision = 'j0k1l2m3n4o5'
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade() -> None:
    # Create talent_feedback table
    op.create_table(
        'talent_feedback',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('customer_id', sa.String(100), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('feedback_type', sa.String(50), nullable=False),  # feature_request, bug_report, general_feedback, model_improvement
        sa.Column('category', sa.String(100), nullable=True),  # resume_parsing, scoring, search, ui_ux, performance
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('analysis_id', sa.String(100), nullable=True),  # Link to specific analysis if applicable
        sa.Column('rating', sa.Integer(), nullable=True),  # 1-5 rating for satisfaction
        sa.Column('priority', sa.String(20), default='medium'),  # low, medium, high, critical
        sa.Column('status', sa.String(20), default='submitted'),  # submitted, reviewed, in_progress, completed, declined
        sa.Column('admin_notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),  # Additional context
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    )
    
    # Create indexes for common queries
    op.create_index('idx_talent_feedback_customer_id', 'talent_feedback', ['customer_id'])
    op.create_index('idx_talent_feedback_user_id', 'talent_feedback', ['user_id'])
    op.create_index('idx_talent_feedback_type', 'talent_feedback', ['feedback_type'])
    op.create_index('idx_talent_feedback_status', 'talent_feedback', ['status'])
    op.create_index('idx_talent_feedback_created_at', 'talent_feedback', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_talent_feedback_created_at', table_name='talent_feedback')
    op.drop_index('idx_talent_feedback_status', table_name='talent_feedback')
    op.drop_index('idx_talent_feedback_type', table_name='talent_feedback')
    op.drop_index('idx_talent_feedback_user_id', table_name='talent_feedback')
    op.drop_index('idx_talent_feedback_customer_id', table_name='talent_feedback')
    
    # Drop table
    op.drop_table('talent_feedback')

