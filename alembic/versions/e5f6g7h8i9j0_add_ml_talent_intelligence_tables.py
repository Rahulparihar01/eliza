"""add_ml_talent_intelligence_tables

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2025-10-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e5f6g7h8i9j0'
down_revision = 'd4e5f6g7h8i9'
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade() -> None:
    # Extend talent_analyses table with new fields for ML-specific analysis
    op.add_column('talent_analyses', sa.Column('diagnostic_report', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('talent_analyses', sa.Column('baseline_profile', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('talent_analyses', sa.Column('synthesis_report', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('talent_analyses', sa.Column('overall_confidence', sa.Float(), nullable=True))
    op.add_column('talent_analyses', sa.Column('version', sa.String(length=50), server_default='v2', nullable=False))
    
    # Create talent_analysis_candidates table
    op.create_table(
        'talent_analysis_candidates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.String(length=100), nullable=False),
        
        # Source
        sa.Column('source', sa.String(length=50), nullable=False),  # 'applicant' or 'market'
        sa.Column('source_id', sa.String(length=255), nullable=True),  # resume_id or pdl_id
        
        # Candidate data
        sa.Column('candidate_name', sa.String(length=255), nullable=True),
        sa.Column('current_title', sa.String(length=255), nullable=True),
        sa.Column('current_company', sa.String(length=255), nullable=True),
        sa.Column('parsed_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Ranking
        sa.Column('rank_overall', sa.Integer(), nullable=True),
        sa.Column('rank_in_source', sa.Integer(), nullable=False),
        
        # Scoring
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('score_breakdown', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        
        # Insights
        sa.Column('patterns_matched', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('provenance_chain', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('fit_explanation', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['talent_analyses.analysis_id'], ),
    )
    
    # Create indexes for talent_analysis_candidates
    op.create_index('ix_candidate_analysis_rank', 'talent_analysis_candidates', ['analysis_id', 'rank_overall'])
    op.create_index('ix_candidate_source', 'talent_analysis_candidates', ['source'])
    op.create_index(op.f('ix_talent_analysis_candidates_analysis_id'), 'talent_analysis_candidates', ['analysis_id'], unique=False)
    
    # Create talent_analysis_patterns table
    op.create_table(
        'talent_analysis_patterns',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.String(length=100), nullable=False),
        
        # Pattern details
        sa.Column('pattern_type', sa.String(length=100), nullable=False),  # 'career_path', 'skill_combo', 'company_cluster'
        sa.Column('pattern_description', sa.Text(), nullable=False),
        sa.Column('frequency', sa.Integer(), nullable=False),  # How many candidates have this
        sa.Column('baseline_comparison', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['talent_analyses.analysis_id'], ),
    )
    
    # Create indexes for talent_analysis_patterns
    op.create_index(op.f('ix_talent_analysis_patterns_analysis_id'), 'talent_analysis_patterns', ['analysis_id'], unique=False)
    
    # Create talent_analysis_feedback table
    op.create_table(
        'talent_analysis_feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.String(length=100), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=True),  # NULL means overall analysis feedback
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Feedback types
        sa.Column('feedback_type', sa.String(length=100), nullable=False),  # 'candidate_rating', 'attribute_weight', 'pattern_validation'
        sa.Column('feedback_value', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('feedback_text', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['talent_analyses.analysis_id'], ),
        sa.ForeignKeyConstraint(['candidate_id'], ['talent_analysis_candidates.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    
    # Create indexes for talent_analysis_feedback
    op.create_index('ix_feedback_analysis_type', 'talent_analysis_feedback', ['analysis_id', 'feedback_type'])
    op.create_index(op.f('ix_talent_analysis_feedback_analysis_id'), 'talent_analysis_feedback', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_talent_analysis_feedback_created_at'), 'talent_analysis_feedback', ['created_at'], unique=False)
    
    # Create pdl_query_history table (for refinement tracking)
    op.create_table(
        'pdl_query_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('analysis_id', sa.String(length=100), nullable=False),
        
        # Query details
        sa.Column('query_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('query_params', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('results_count', sa.Integer(), nullable=True),
        sa.Column('refinement_reason', sa.Text(), nullable=True),
        
        # Parent query (for refinement chain)
        sa.Column('parent_query_id', sa.Integer(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_id'], ['talent_analyses.analysis_id'], ),
        sa.ForeignKeyConstraint(['parent_query_id'], ['pdl_query_history.id'], ),
    )
    
    # Create indexes for pdl_query_history
    op.create_index('ix_pdl_query_analysis_version', 'pdl_query_history', ['analysis_id', 'query_version'])
    op.create_index(op.f('ix_pdl_query_history_analysis_id'), 'pdl_query_history', ['analysis_id'], unique=False)
    
    # Create hiring_manager_preferences table (for future learning)
    op.create_table(
        'hiring_manager_preferences',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_type', sa.String(length=100), nullable=False),  # 'ML Engineer', etc.
        
        # Learned weights and patterns
        sa.Column('learned_weights', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('successful_patterns', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('rejected_patterns', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Confidence and metadata
        sa.Column('confidence', sa.Float(), nullable=True),  # How much data we have
        sa.Column('sample_count', sa.Integer(), server_default='0'),  # Number of analyses
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.UniqueConstraint('user_id', 'role_type', name='uq_user_role_preference')
    )
    
    # Create indexes for hiring_manager_preferences
    op.create_index(op.f('ix_hiring_manager_preferences_user_id'), 'hiring_manager_preferences', ['user_id'], unique=False)
    op.create_index(op.f('ix_hiring_manager_preferences_role_type'), 'hiring_manager_preferences', ['role_type'], unique=False)


def downgrade() -> None:
    # Drop indexes and tables in reverse order
    op.drop_index(op.f('ix_hiring_manager_preferences_role_type'), table_name='hiring_manager_preferences')
    op.drop_index(op.f('ix_hiring_manager_preferences_user_id'), table_name='hiring_manager_preferences')
    op.drop_table('hiring_manager_preferences')
    
    op.drop_index(op.f('ix_pdl_query_history_analysis_id'), table_name='pdl_query_history')
    op.drop_index('ix_pdl_query_analysis_version', table_name='pdl_query_history')
    op.drop_table('pdl_query_history')
    
    op.drop_index(op.f('ix_talent_analysis_feedback_created_at'), table_name='talent_analysis_feedback')
    op.drop_index(op.f('ix_talent_analysis_feedback_analysis_id'), table_name='talent_analysis_feedback')
    op.drop_index('ix_feedback_analysis_type', table_name='talent_analysis_feedback')
    op.drop_table('talent_analysis_feedback')
    
    op.drop_index(op.f('ix_talent_analysis_patterns_analysis_id'), table_name='talent_analysis_patterns')
    op.drop_table('talent_analysis_patterns')
    
    op.drop_index(op.f('ix_talent_analysis_candidates_analysis_id'), table_name='talent_analysis_candidates')
    op.drop_index('ix_candidate_source', table_name='talent_analysis_candidates')
    op.drop_index('ix_candidate_analysis_rank', table_name='talent_analysis_candidates')
    op.drop_table('talent_analysis_candidates')
    
    # Remove added columns from talent_analyses
    op.drop_column('talent_analyses', 'version')
    op.drop_column('talent_analyses', 'overall_confidence')
    op.drop_column('talent_analyses', 'synthesis_report')
    op.drop_column('talent_analyses', 'baseline_profile')
    op.drop_column('talent_analyses', 'diagnostic_report')

