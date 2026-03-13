"""Add analysis_configs table

Revision ID: zz4_add_analysis_configs_table
Revises: hh8ii9jj0kk1
Create Date: 2026-01-08 12:00:00.000000

Creates the analysis_configs table for saving and reusing talent analysis configurations.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text


# revision identifiers
revision = 'zz4_add_analysis_configs'
down_revision = 'hh8ii9jj0kk1'
branch_labels = None
depends_on = None
tags = ["core"]


def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists."""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = :table_name AND table_schema = 'public'
        );
    """), {'table_name': table_name})
    return result.scalar()


def index_exists(conn, index_name: str) -> bool:
    """Check if an index exists."""
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM pg_indexes 
            WHERE indexname = :index_name
        );
    """), {'index_name': index_name})
    return result.scalar()


def upgrade():
    conn = op.get_bind()
    
    # Check if table already exists (idempotent)
    if table_exists(conn, 'analysis_configs'):
        print("Table analysis_configs already exists, skipping table creation")
    else:
        # Create analysis_configs table
        op.create_table(
            'analysis_configs',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('customer_id', sa.String(100), nullable=False),
            sa.Column('created_by_user_id', sa.Integer(), nullable=True),
            
            # Configuration details
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            
            # Related entities
            sa.Column('blueprint_id', sa.Integer(), nullable=True),
            sa.Column('company_dna_id', sa.Integer(), nullable=True),
            sa.Column('ats_connection_id', sa.Integer(), nullable=True),
            sa.Column('selected_job_id', sa.String(100), nullable=True),
            
            # Configuration content
            sa.Column('job_description', sa.Text(), nullable=True),
            sa.Column('ideal_candidate_details', sa.Text(), nullable=True),
            sa.Column('department_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('candidate_source_mode', sa.String(20), nullable=True, server_default='ats'),
            sa.Column('uploaded_resume_files', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('market_search_limit', sa.Integer(), nullable=True, server_default='50'),
            sa.Column('max_candidate_fetch', sa.Integer(), nullable=True, server_default='100'),
            
            # Historical candidate settings
            sa.Column('include_historical_candidates', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('historical_lookback_days', sa.Integer(), nullable=True, server_default='365'),
            
            # Run tracking
            sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_analysis_id', sa.String(100), nullable=True),
            sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
            
            # Metadata
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['blueprint_id'], ['career_blueprints.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['company_dna_id'], ['company_dna_profiles.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['ats_connection_id'], ['connector_configurations.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['last_analysis_id'], ['talent_analyses.analysis_id'], ondelete='SET NULL'),
        )
        print("Created analysis_configs table")
    
    # Create indexes (idempotent - check if each exists first)
    if not index_exists(conn, 'ix_analysis_configs_customer_id'):
        op.create_index('ix_analysis_configs_customer_id', 'analysis_configs', ['customer_id'])
        print("Created index ix_analysis_configs_customer_id")
    else:
        print("Index ix_analysis_configs_customer_id already exists, skipping")
        
    if not index_exists(conn, 'ix_analysis_configs_created_at'):
        op.create_index('ix_analysis_configs_created_at', 'analysis_configs', ['created_at'])
        print("Created index ix_analysis_configs_created_at")
    else:
        print("Index ix_analysis_configs_created_at already exists, skipping")
        
    if not index_exists(conn, 'ix_analysis_configs_created_by'):
        op.create_index('ix_analysis_configs_created_by', 'analysis_configs', ['created_by_user_id'])
        print("Created index ix_analysis_configs_created_by")
    else:
        print("Index ix_analysis_configs_created_by already exists, skipping")
    
    print("Migration zz4_add_analysis_configs complete")


def downgrade():
    op.drop_index('ix_analysis_configs_created_by', table_name='analysis_configs')
    op.drop_index('ix_analysis_configs_created_at', table_name='analysis_configs')
    op.drop_index('ix_analysis_configs_customer_id', table_name='analysis_configs')
    op.drop_table('analysis_configs')
