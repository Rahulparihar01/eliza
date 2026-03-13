"""Add data analyst tables

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2025-11-19 02:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'j0k1l2m3n4o5'
down_revision = 'i9j0k1l2m3n4'
branch_labels = None
depends_on = None
tags = ["bi"]


def upgrade() -> None:
    """Create data analyst tables for question tracking and results."""
    
    # Create enum types if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE data_source_type AS ENUM (
                'insurance'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;

        DO $$ BEGIN
            CREATE TYPE data_analyst_question_status AS ENUM (
                'pending',
                'processing',
                'completed',
                'failed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create data_analyst_questions table
    # Note: Using String instead of Enum to avoid SQLAlchemy trying to create the enum type
    # The enum types are already created above
    op.create_table(
        'data_analyst_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('data_source_type', sa.String(length=50), nullable=False),
        sa.Column('original_question', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('generated_sql', sa.Text(), nullable=True),
        sa.Column('sql_error', sa.Text(), nullable=True),
        sa.Column('result_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('result_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id')
    )
    
    # Create indexes
    op.create_index('ix_data_analyst_questions_question_id', 'data_analyst_questions', ['question_id'])
    op.create_index('ix_data_analyst_questions_user_id', 'data_analyst_questions', ['user_id'])
    op.create_index('ix_data_analyst_questions_customer_id', 'data_analyst_questions', ['customer_id'])
    op.create_index('ix_data_analyst_questions_status', 'data_analyst_questions', ['status'])
    op.create_index('ix_data_analyst_questions_created_at', 'data_analyst_questions', ['created_at'])


def downgrade() -> None:
    """Drop data analyst tables."""
    op.drop_index('ix_data_analyst_questions_created_at', table_name='data_analyst_questions')
    op.drop_index('ix_data_analyst_questions_status', table_name='data_analyst_questions')
    op.drop_index('ix_data_analyst_questions_customer_id', table_name='data_analyst_questions')
    op.drop_index('ix_data_analyst_questions_user_id', table_name='data_analyst_questions')
    op.drop_index('ix_data_analyst_questions_question_id', table_name='data_analyst_questions')
    op.drop_table('data_analyst_questions')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS data_analyst_question_status")
    op.execute("DROP TYPE IF EXISTS data_source_type")

