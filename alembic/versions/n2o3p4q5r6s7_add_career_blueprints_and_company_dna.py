"""add_career_blueprints_and_company_dna

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2025-12-10 14:00:00.000000

Creates tables for advanced candidate analysis features:
- `career_blueprints` - Reusable career pattern templates from look-alike profiles
- `company_dna_profiles` - Organization hiring patterns scoped by company + role
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'n2o3p4q5r6s7'
down_revision = 'm1n2o3p4q5r6'
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade() -> None:
    # =========================================================================
    # CREATE `career_blueprints` TABLE
    # Stores reusable career pattern templates extracted from look-alike profiles
    # =========================================================================
    op.create_table(
        'career_blueprints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        
        # Blueprint identification
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('role_category', sa.String(100), nullable=True),  # e.g., "engineering", "sales"
        
        # Source profiles (LinkedIn URLs that were enriched to create this blueprint)
        sa.Column('source_linkedin_urls', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('source_profile_count', sa.Integer(), nullable=False, server_default='0'),
        
        # Extracted patterns
        sa.Column('company_progression', postgresql.JSONB(), nullable=True),
        # {
        #   "pattern": "startup → growth → enterprise",
        #   "company_sizes": ["1-50", "51-500", "500+"],
        #   "industries": ["saas", "fintech", "cloud"],
        #   "common_companies": ["stripe", "databricks"]
        # }
        
        sa.Column('role_progression', postgresql.JSONB(), nullable=True),
        # {
        #   "pattern": "IC → Senior → Staff",
        #   "avg_months_per_level": 24,
        #   "title_sequence": ["engineer", "senior engineer", "staff engineer"]
        # }
        
        sa.Column('skill_profile', postgresql.JSONB(), nullable=True),
        # {
        #   "core_skills": ["python", "aws", "kubernetes"],
        #   "skill_frequencies": {"python": 0.95, "aws": 0.80},
        #   "emerging_skills": ["langchain", "bedrock"]
        # }
        
        sa.Column('experience_profile', postgresql.JSONB(), nullable=True),
        # {
        #   "avg_years": 8.5,
        #   "min_years": 5,
        #   "max_years": 15,
        #   "avg_role_count": 4
        # }
        
        sa.Column('education_profile', postgresql.JSONB(), nullable=True),
        # {
        #   "degree_distribution": {"bachelors": 0.9, "masters": 0.4, "phd": 0.1},
        #   "common_majors": ["computer science", "mathematics"],
        #   "common_schools": []
        # }
        
        # PDL query hints derived from this blueprint
        sa.Column('pdl_query_hints', postgresql.JSONB(), nullable=True),
        # {
        #   "suggested_titles": ["senior software engineer", "staff engineer"],
        #   "suggested_skills": ["python", "aws"],
        #   "experience_range": [5, 12],
        #   "target_companies": ["stripe", "databricks"]
        # }
        
        # Scoring configuration
        sa.Column('scoring_weights', postgresql.JSONB(), nullable=True),
        # {
        #   "skill_alignment": 0.30,
        #   "experience_fit": 0.20,
        #   "trajectory_match": 0.20,
        #   "company_background": 0.15,
        #   "organizational_fit": 0.15
        # }
        
        # Status and metadata
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
    )
    
    # Indexes for career_blueprints
    op.create_index('ix_career_blueprints_customer', 'career_blueprints', ['customer_id'])
    op.create_index('ix_career_blueprints_name', 'career_blueprints', ['customer_id', 'name'])
    op.create_index('ix_career_blueprints_role', 'career_blueprints', ['customer_id', 'role_category'])
    op.create_index('ix_career_blueprints_active', 'career_blueprints', ['customer_id', 'is_active'])
    
    # =========================================================================
    # CREATE `company_dna_profiles` TABLE
    # Stores organizational hiring patterns scoped by company + role category
    # =========================================================================
    op.create_table(
        'company_dna_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        
        # Company identification
        sa.Column('company_name', sa.String(255), nullable=False),
        sa.Column('company_website', sa.String(500), nullable=True),
        sa.Column('role_category', sa.String(100), nullable=False),  # e.g., "engineering", "sales", "all"
        
        # Analysis parameters
        sa.Column('time_window_months', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('employee_count_analyzed', sa.Integer(), nullable=False, server_default='0'),
        
        # Workforce DNA - patterns from current employees
        sa.Column('workforce_dna', postgresql.JSONB(), nullable=True),
        # {
        #   "avg_experience_years": 8.2,
        #   "experience_distribution": {"0-2": 0.1, "3-5": 0.25, "6-10": 0.40, "10+": 0.25},
        #   "common_backgrounds": {
        #     "faang_alumni_rate": 0.15,
        #     "startup_experience_rate": 0.45,
        #     "consulting_background_rate": 0.30
        #   },
        #   "skill_profile": {
        #     "core_skills": ["aws", "terraform", "kubernetes", "python"],
        #     "skill_frequencies": {"aws": 0.85, "python": 0.80},
        #     "emerging_skills": ["genai", "bedrock", "langchain"]
        #   },
        #   "education_profile": {
        #     "bachelors_rate": 0.85,
        #     "masters_rate": 0.35,
        #     "phd_rate": 0.05,
        #     "cs_degree_rate": 0.60
        #   },
        #   "location_distribution": {"remote": 0.70, "us": 0.25, "international": 0.05}
        # }
        
        # Culture indicators - inferred from workforce patterns
        sa.Column('culture_indicators', postgresql.JSONB(), nullable=True),
        # {
        #   "pace": "fast",  # based on avg tenure
        #   "technical_depth": "high",
        #   "remote_friendly": true,
        #   "avg_tenure_months": 18,
        #   "growth_stage": "scale-up"
        # }
        
        # Success patterns - what backgrounds correlate with success
        sa.Column('success_patterns', postgresql.JSONB(), nullable=True),
        # {
        #   "common_previous_companies": ["aws", "google cloud", "hashicorp"],
        #   "common_previous_roles": ["cloud architect", "devops engineer"],
        #   "career_progression_patterns": ["IC → Senior in 2-3 years"],
        #   "skill_acquisition_patterns": ["cloud first, then containers"]
        # }
        
        # Hiring preferences - configurable by user
        sa.Column('hiring_preferences', postgresql.JSONB(), nullable=True),
        # {
        #   "preferred_source_companies": ["aws", "google cloud", "datadog"],
        #   "preferred_backgrounds": ["cloud consulting", "devops"],
        #   "preferred_skills": ["aws", "terraform", "eks"],
        #   "avoid_patterns": [],
        #   "must_have_criteria": []
        # }
        
        # PDL query modifiers - how to adjust searches based on DNA
        sa.Column('pdl_query_modifiers', postgresql.JSONB(), nullable=True),
        # {
        #   "boost_companies": ["aws", "hashicorp", "datadog"],
        #   "boost_skills": ["aws", "terraform", "eks"],
        #   "experience_adjustment": 0,  # +/- years from JD requirement
        #   "education_filter": null  # or ["bachelors", "masters"]
        # }
        
        # Status and metadata
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        # Unique constraint: one DNA profile per company + role combination
        sa.UniqueConstraint('customer_id', 'company_name', 'role_category', name='uq_company_dna_company_role'),
    )
    
    # Indexes for company_dna_profiles
    op.create_index('ix_company_dna_customer', 'company_dna_profiles', ['customer_id'])
    op.create_index('ix_company_dna_company', 'company_dna_profiles', ['customer_id', 'company_name'])
    op.create_index('ix_company_dna_role', 'company_dna_profiles', ['customer_id', 'role_category'])
    
    # =========================================================================
    # ADD blueprint_id to talent_analyses for tracking which blueprint was used
    # =========================================================================
    op.add_column(
        'talent_analyses',
        sa.Column('blueprint_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_talent_analyses_blueprint',
        'talent_analyses',
        'career_blueprints',
        ['blueprint_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Remove foreign key and column from talent_analyses
    op.drop_constraint('fk_talent_analyses_blueprint', 'talent_analyses', type_='foreignkey')
    op.drop_column('talent_analyses', 'blueprint_id')
    
    # Drop indexes
    op.drop_index('ix_company_dna_role', 'company_dna_profiles')
    op.drop_index('ix_company_dna_company', 'company_dna_profiles')
    op.drop_index('ix_company_dna_customer', 'company_dna_profiles')
    
    op.drop_index('ix_career_blueprints_active', 'career_blueprints')
    op.drop_index('ix_career_blueprints_role', 'career_blueprints')
    op.drop_index('ix_career_blueprints_name', 'career_blueprints')
    op.drop_index('ix_career_blueprints_customer', 'career_blueprints')
    
    # Drop tables
    op.drop_table('company_dna_profiles')
    op.drop_table('career_blueprints')

