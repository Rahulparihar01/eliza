"""add hr applicant tables

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-10-11 23:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade():
    # Create job_postings table
    op.create_table(
        'job_postings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(255), nullable=False),
        sa.Column('connector_id', sa.Integer(), nullable=False),
        sa.Column('external_job_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('department', sa.String(255), nullable=True),
        sa.Column('office', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requirements', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='open'),
        sa.Column('remote_url', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_configurations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_job_postings_customer_id', 'job_postings', ['customer_id'])
    op.create_index('ix_job_postings_connector_id', 'job_postings', ['connector_id'])
    op.create_index('ix_job_postings_external_job_id', 'job_postings', ['external_job_id'])
    op.create_index('ix_job_postings_status', 'job_postings', ['status'])
    op.create_index('ix_job_postings_created_at', 'job_postings', ['created_at'])
    
    # Create applicants table
    op.create_table(
        'applicants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(255), nullable=False),
        sa.Column('job_posting_id', sa.Integer(), nullable=False),
        sa.Column('external_applicant_id', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(255), nullable=True),
        sa.Column('last_name', sa.String(255), nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('resume_filename', sa.String(500), nullable=True),
        sa.Column('resume_path', sa.String(1000), nullable=True),
        sa.Column('resume_url', sa.String(1000), nullable=True),
        sa.Column('resume_parsed', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('profile_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='new'),
        sa.Column('current_stage', sa.String(255), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_applicants_customer_id', 'applicants', ['customer_id'])
    op.create_index('ix_applicants_job_posting_id', 'applicants', ['job_posting_id'])
    op.create_index('ix_applicants_external_applicant_id', 'applicants', ['external_applicant_id'])
    op.create_index('ix_applicants_email', 'applicants', ['email'])
    op.create_index('ix_applicants_status', 'applicants', ['status'])
    op.create_index('ix_applicants_applied_at', 'applicants', ['applied_at'])
    
    # Create applicant_scores table
    op.create_table(
        'applicant_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('applicant_id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.String(255), nullable=False),
        sa.Column('overall_score', sa.Float(), nullable=False),
        sa.Column('skills_score', sa.Float(), nullable=True),
        sa.Column('experience_score', sa.Float(), nullable=True),
        sa.Column('career_trajectory_score', sa.Float(), nullable=True),
        sa.Column('company_fit_score', sa.Float(), nullable=True),
        sa.Column('education_score', sa.Float(), nullable=True),
        sa.Column('embedding_similarity', sa.Float(), nullable=True),
        sa.Column('matched_employee_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('dimension_scores', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['applicant_id'], ['applicants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analysis_id'], ['talent_analyses.analysis_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_applicant_scores_applicant_id', 'applicant_scores', ['applicant_id'])
    op.create_index('ix_applicant_scores_analysis_id', 'applicant_scores', ['analysis_id'])
    op.create_index('ix_applicant_scores_overall_score', 'applicant_scores', ['overall_score'])
    
    # Create baseline_employee_profiles table (cached employee baseline per role)
    op.create_table(
        'baseline_employee_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(255), nullable=False),
        sa.Column('role_title', sa.String(500), nullable=False),
        sa.Column('employee_count', sa.Integer(), nullable=False),
        sa.Column('employee_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('aggregated_skills', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('common_companies', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('education_patterns', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('career_paths', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('avg_years_experience', sa.Float(), nullable=True),
        sa.Column('baseline_embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
    )
    op.create_index('ix_baseline_profiles_customer_id', 'baseline_employee_profiles', ['customer_id'])
    op.create_index('ix_baseline_profiles_role_title', 'baseline_employee_profiles', ['role_title'])
    op.create_unique_constraint('uq_baseline_customer_role', 'baseline_employee_profiles', ['customer_id', 'role_title'])


def downgrade():
    op.drop_table('applicant_scores')
    op.drop_table('applicants')
    op.drop_table('baseline_employee_profiles')
    op.drop_table('job_postings')

