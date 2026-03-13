"""add_ml_matching_tables

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2025-10-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd4e5f6g7h8i9'
down_revision = 'c3d4e5f6g7h8'
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade():
    """Create ML matching tables"""
    
    # Create matching_sessions table
    op.create_table(
        'matching_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(255), nullable=False),
        sa.Column('job_description', sa.Text(), nullable=False),
        sa.Column('hiring_manager_notes', sa.Text(), nullable=True),
        sa.Column('reference_employee_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ideal_candidate_profile', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('profile_synthesis_reasoning', sa.Text(), nullable=True),
        sa.Column('success_patterns_found', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('internal_candidates_analyzed', sa.Integer(), nullable=True),
        sa.Column('external_candidates_found', sa.Integer(), nullable=True),
        sa.Column('pdl_query_generated', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('pdl_query_reasoning', sa.Text(), nullable=True),
        sa.Column('pdl_query_cost_usd', sa.Float(), nullable=True),
        sa.Column('top_internal_candidate_id', sa.Integer(), nullable=True),
        sa.Column('top_external_candidate_id', sa.Integer(), nullable=True),
        sa.Column('total_duration_seconds', sa.Float(), nullable=True),
        sa.Column('total_cost_usd', sa.Float(), nullable=True),
        sa.Column('agent_trace', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for matching_sessions
    op.create_index('idx_matching_session_customer', 'matching_sessions', ['customer_id'])
    op.create_index('idx_matching_session_created', 'matching_sessions', ['created_at'])
    op.create_index('idx_matching_sessions_session_id', 'matching_sessions', ['session_id'], unique=True)
    
    # Create candidate_analyses table
    op.create_table(
        'candidate_analyses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.String(255), nullable=False),
        sa.Column('analysis_session_id', sa.String(100), nullable=False),
        sa.Column('job_posting_id', sa.Integer(), nullable=True),
        sa.Column('applicant_id', sa.Integer(), nullable=True),
        sa.Column('pdl_person_id', sa.Integer(), nullable=True),
        sa.Column('candidate_source', sa.String(50), nullable=False),
        sa.Column('ideal_profile', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('score_skills_match', sa.Float(), nullable=True),
        sa.Column('score_experience_fit', sa.Float(), nullable=True),
        sa.Column('score_career_trajectory', sa.Float(), nullable=True),
        sa.Column('score_company_background', sa.Float(), nullable=True),
        sa.Column('score_cultural_fit', sa.Float(), nullable=True),
        sa.Column('score_production_ml', sa.Float(), nullable=True),
        sa.Column('score_independence', sa.Float(), nullable=True),
        sa.Column('pattern_matches', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('why_great_fit', sa.Text(), nullable=True),
        sa.Column('potential_concerns', sa.Text(), nullable=True),
        sa.Column('evidence', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('metadata_boosts_applied', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ranking_method', sa.String(50), nullable=True),
        sa.Column('ranking_stage', sa.String(50), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('analysis_duration_ms', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id']),
        sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id']),
        sa.ForeignKeyConstraint(['pdl_person_id'], ['pdl_persons.id'])
    )
    
    # Create indexes for candidate_analyses
    op.create_index('idx_candidate_analysis_job', 'candidate_analyses', ['job_posting_id'])
    op.create_index('idx_candidate_analysis_score', 'candidate_analyses', ['total_score'])
    op.create_index('idx_candidate_analysis_customer', 'candidate_analyses', ['customer_id'])
    op.create_index('idx_candidate_analyses_session', 'candidate_analyses', ['analysis_session_id'])
    
    # Add foreign keys for matching_sessions
    op.create_foreign_key(
        'fk_matching_sessions_top_internal',
        'matching_sessions', 'candidate_analyses',
        ['top_internal_candidate_id'], ['id']
    )
    op.create_foreign_key(
        'fk_matching_sessions_top_external',
        'matching_sessions', 'candidate_analyses',
        ['top_external_candidate_id'], ['id']
    )


def downgrade():
    """Drop ML matching tables"""
    
    # Drop foreign keys first
    op.drop_constraint('fk_matching_sessions_top_internal', 'matching_sessions', type_='foreignkey')
    op.drop_constraint('fk_matching_sessions_top_external', 'matching_sessions', type_='foreignkey')
    
    # Drop candidate_analyses table
    op.drop_index('idx_candidate_analyses_session', table_name='candidate_analyses')
    op.drop_index('idx_candidate_analysis_customer', table_name='candidate_analyses')
    op.drop_index('idx_candidate_analysis_score', table_name='candidate_analyses')
    op.drop_index('idx_candidate_analysis_job', table_name='candidate_analyses')
    op.drop_table('candidate_analyses')
    
    # Drop matching_sessions table
    op.drop_index('idx_matching_sessions_session_id', table_name='matching_sessions')
    op.drop_index('idx_matching_session_created', table_name='matching_sessions')
    op.drop_index('idx_matching_session_customer', table_name='matching_sessions')
    op.drop_table('matching_sessions')

