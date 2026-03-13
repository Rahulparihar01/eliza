"""Add missing tables: candidate_score_feedback, career_fingerprints, user_mfa

Revision ID: zz5_add_missing_tables
Revises: zz4_add_analysis_configs
Create Date: 2026-01-08 12:30:00.000000

These tables were defined in SQLAlchemy models but had no creation migrations,
causing 500 errors when the API tried to use them.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text


# revision identifiers
revision = 'zz5_add_missing_tables'
down_revision = 'zz4_add_analysis_configs'
branch_labels = None
depends_on = None
tags = ["core"]


def table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the database."""
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
    
    # =========================================================================
    # 1. candidate_score_feedback
    # =========================================================================
    if not table_exists(conn, 'candidate_score_feedback'):
        print("Creating table: candidate_score_feedback")
        op.create_table(
            'candidate_score_feedback',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            
            # Relationships
            sa.Column('candidate_analysis_score_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('customer_id', sa.String(100), nullable=False),
            
            # User's assessment
            sa.Column('user_rating', sa.Integer(), nullable=False),  # 1-5 stars
            sa.Column('would_interview', sa.String(20), nullable=True),
            
            # Dimension-specific feedback
            sa.Column('dimension_feedback', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            
            # Free-form feedback
            sa.Column('feedback_notes', sa.Text(), nullable=True),
            
            # Action taken
            sa.Column('action_taken', sa.String(50), nullable=True),
            
            # Timestamps
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['candidate_analysis_score_id'], ['candidate_analysis_scores.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
            sa.UniqueConstraint('candidate_analysis_score_id', 'user_id', name='uq_feedback_score_user'),
        )
    else:
        print("Table candidate_score_feedback already exists, skipping")
    
    # Create indexes for candidate_score_feedback (idempotent)
    if table_exists(conn, 'candidate_score_feedback'):
        if not index_exists(conn, 'ix_csf_score_id'):
            op.create_index('ix_csf_score_id', 'candidate_score_feedback', ['candidate_analysis_score_id'])
            print("Created index ix_csf_score_id")
        if not index_exists(conn, 'ix_csf_customer_id'):
            op.create_index('ix_csf_customer_id', 'candidate_score_feedback', ['customer_id'])
            print("Created index ix_csf_customer_id")
    
    # =========================================================================
    # 2. career_fingerprints
    # =========================================================================
    if not table_exists(conn, 'career_fingerprints'):
        print("Creating table: career_fingerprints")
        op.create_table(
            'career_fingerprints',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('customer_id', sa.String(255), nullable=False),
            
            # Fingerprint metadata
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            
            # Source profiles
            sa.Column('source_profiles', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
            
            # Extracted patterns
            sa.Column('company_progression', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('role_progression', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('skill_velocity', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('industry_transitions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('education_patterns', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            
            # Aggregate stats
            sa.Column('avg_years_experience', sa.Float(), nullable=True),
            sa.Column('common_skills', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('common_companies', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('profile_count', sa.Integer(), nullable=False, server_default='0'),
            
            # For PDL matching
            sa.Column('pdl_query_hints', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('scoring_weights', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            
            # Status
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_processing', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('last_enriched_at', sa.DateTime(timezone=True), nullable=True),
            
            # BaseModel fields
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            
            sa.PrimaryKeyConstraint('id'),
        )
    else:
        print("Table career_fingerprints already exists, skipping")
    
    # Create indexes for career_fingerprints (idempotent)
    if table_exists(conn, 'career_fingerprints'):
        if not index_exists(conn, 'idx_career_fingerprint_customer'):
            op.create_index('idx_career_fingerprint_customer', 'career_fingerprints', ['customer_id'])
            print("Created index idx_career_fingerprint_customer")
        if not index_exists(conn, 'idx_career_fingerprint_active'):
            op.create_index('idx_career_fingerprint_active', 'career_fingerprints', ['is_active'])
            print("Created index idx_career_fingerprint_active")
    
    # =========================================================================
    # 3. user_mfa
    # =========================================================================
    if not table_exists(conn, 'user_mfa'):
        print("Creating table: user_mfa")
        op.create_table(
            'user_mfa',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('mfa_type', sa.String(50), nullable=False),  # 'totp', 'email'
            sa.Column('secret_key', sa.String(255), nullable=True),  # For TOTP
            sa.Column('is_enabled', sa.Boolean(), server_default='false', nullable=False),
            sa.Column('backup_codes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            
            sa.PrimaryKeyConstraint('id'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        )
    else:
        print("Table user_mfa already exists, skipping")
    
    # Create indexes for user_mfa (idempotent)
    if table_exists(conn, 'user_mfa'):
        if not index_exists(conn, 'ix_user_mfa_user_id'):
            op.create_index('ix_user_mfa_user_id', 'user_mfa', ['user_id'])
            print("Created index ix_user_mfa_user_id")
    
    print("Missing tables migration complete")


def downgrade():
    op.drop_index('ix_user_mfa_user_id', table_name='user_mfa')
    op.drop_table('user_mfa')
    
    op.drop_index('idx_career_fingerprint_active', table_name='career_fingerprints')
    op.drop_index('idx_career_fingerprint_customer', table_name='career_fingerprints')
    op.drop_table('career_fingerprints')
    
    op.drop_index('ix_csf_customer_id', table_name='candidate_score_feedback')
    op.drop_index('ix_csf_score_id', table_name='candidate_score_feedback')
    op.drop_table('candidate_score_feedback')
