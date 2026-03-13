"""add_candidates_and_scores_tables

Revision ID: m1n2o3p4q5r6
Revises: l2m3n4o5p6q7
Create Date: 2025-12-10 02:00:00.000000

Creates the proper normalized candidate database:
- `candidates` - Master candidate table with profile data
- `candidate_analysis_scores` - Scores per candidate per analysis

This replaces the JSON blob approach in talent_analyses.candidates
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'm1n2o3p4q5r6'
# Merge both heads: l2m3n4o5p6q7 (email templates) and k1l2m3n4o5p6 (talent feedback)
down_revision = ('l2m3n4o5p6q7', 'k1l2m3n4o5p6')
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade() -> None:
    # =========================================================================
    # CREATE `candidates` TABLE - Master candidate database
    # =========================================================================
    op.create_table(
        'candidates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        
        # Identity (for deduplication)
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('greenhouse_id', sa.Integer(), nullable=True),
        sa.Column('pdl_id', sa.String(length=100), nullable=True),
        
        # Profile Data
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('github_url', sa.String(length=500), nullable=True),
        sa.Column('location', sa.String(length=255), nullable=True),
        
        # Current Employment
        sa.Column('current_title', sa.String(length=255), nullable=True),
        sa.Column('current_company', sa.String(length=255), nullable=True),
        
        # Parsed Resume Data (flexible JSONB)
        sa.Column('skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('experience', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('education', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('certifications', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        
        # Source Tracking
        sa.Column('source', sa.String(length=50), nullable=True),  # 'greenhouse', 'pdl', 'upload', 'manual'
        sa.Column('source_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('load_date', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
    )
    
    # Indexes for candidates
    op.create_index('ix_candidates_customer_id', 'candidates', ['customer_id'])
    op.create_index('ix_candidates_email', 'candidates', ['email'])
    op.create_index('ix_candidates_greenhouse_id', 'candidates', ['greenhouse_id'])
    op.create_index('ix_candidates_pdl_id', 'candidates', ['pdl_id'])
    op.create_index('ix_candidates_full_name', 'candidates', ['full_name'])
    op.create_index('ix_candidates_customer_email', 'candidates', ['customer_id', 'email'], unique=True)
    
    # Partial unique index for greenhouse_id (only when not null)
    op.execute("""
        CREATE UNIQUE INDEX ix_candidates_customer_greenhouse 
        ON candidates (customer_id, greenhouse_id) 
        WHERE greenhouse_id IS NOT NULL
    """)
    
    # =========================================================================
    # CREATE `candidate_analysis_scores` TABLE - Scores per analysis
    # =========================================================================
    op.create_table(
        'candidate_analysis_scores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        
        # Relationships
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.String(length=100), nullable=False),
        
        # Scoring (fixed fields)
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('rank_overall', sa.Integer(), nullable=True),
        sa.Column('rank_in_source', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),  # 'applicant' or 'market'
        sa.Column('confidence', sa.Float(), nullable=True),
        
        # Scoring details (flexible JSONB)
        sa.Column('score_breakdown', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('patterns_matched', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('match_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Generated Email
        sa.Column('email_template_id', sa.Integer(), nullable=True),
        sa.Column('generated_email_subject', sa.String(length=500), nullable=True),
        sa.Column('generated_email_body', sa.Text(), nullable=True),
        sa.Column('email_generated_at', sa.DateTime(timezone=True), nullable=True),
        
        # Outreach Status
        sa.Column('outreach_status', sa.String(length=50), server_default='pending', nullable=False),
        sa.Column('outreach_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('outreach_notes', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('scored_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['candidate_id'], ['candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_id'], ['talent_analyses.analysis_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['email_template_id'], ['email_templates.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('candidate_id', 'analysis_id', name='uq_candidate_analysis'),
    )
    
    # Indexes for candidate_analysis_scores
    op.create_index('ix_cas_analysis_id', 'candidate_analysis_scores', ['analysis_id'])
    op.create_index('ix_cas_candidate_id', 'candidate_analysis_scores', ['candidate_id'])
    op.create_index('ix_cas_analysis_score', 'candidate_analysis_scores', ['analysis_id', 'overall_score'])
    op.create_index('ix_cas_analysis_rank', 'candidate_analysis_scores', ['analysis_id', 'rank_overall'])
    op.create_index('ix_cas_outreach_status', 'candidate_analysis_scores', ['outreach_status'])
    op.create_index('ix_cas_source', 'candidate_analysis_scores', ['source'])


def downgrade() -> None:
    # Drop candidate_analysis_scores
    op.drop_index('ix_cas_source', table_name='candidate_analysis_scores')
    op.drop_index('ix_cas_outreach_status', table_name='candidate_analysis_scores')
    op.drop_index('ix_cas_analysis_rank', table_name='candidate_analysis_scores')
    op.drop_index('ix_cas_analysis_score', table_name='candidate_analysis_scores')
    op.drop_index('ix_cas_candidate_id', table_name='candidate_analysis_scores')
    op.drop_index('ix_cas_analysis_id', table_name='candidate_analysis_scores')
    op.drop_table('candidate_analysis_scores')
    
    # Drop candidates
    op.execute('DROP INDEX IF EXISTS ix_candidates_customer_greenhouse')
    op.drop_index('ix_candidates_customer_email', table_name='candidates')
    op.drop_index('ix_candidates_full_name', table_name='candidates')
    op.drop_index('ix_candidates_pdl_id', table_name='candidates')
    op.drop_index('ix_candidates_greenhouse_id', table_name='candidates')
    op.drop_index('ix_candidates_email', table_name='candidates')
    op.drop_index('ix_candidates_customer_id', table_name='candidates')
    op.drop_table('candidates')

