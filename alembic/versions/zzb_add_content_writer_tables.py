"""Add Content Writer tables

Revision ID: zzb_add_content_writer_tables
Revises: zz22_workspace_templates_kb
Create Date: 2026-02-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'zzb_add_content_writer_tables'
down_revision: Union[str, None] = 'zz22_workspace_templates_kb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["content"]


def upgrade() -> None:
    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE content_format AS ENUM ('linkedin', 'blog', 'twitter_article');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE source_type AS ENUM (
                'web', 'reddit', 'hacker_news', 'twitter', 'curated_blogs', 'pasted_text'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE content_writer_run_status AS ENUM (
                'pending', 'researching', 'pov_selection', 'hook_selection', 
                'outline_selection', 'drafting', 'completed', 'failed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE skill_type AS ENUM ('voice', 'pillars', 'hooks', 'examples', 'proof_bank');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE issue_type AS ENUM (
                'too_vague', 'contradictory', 'unsupported_claim', 'off_brand', 
                'weak_hook', 'poor_flow', 'too_technical', 'too_generic', 
                'wrong_tone', 'needs_evidence'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create content_writer_runs table
    op.create_table(
        'content_writer_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Input configuration
        sa.Column('topic', sa.Text(), nullable=False),
        sa.Column('format', sa.String(50), nullable=False),
        sa.Column('selected_sources', sa.JSON(), nullable=False),
        sa.Column('pasted_text', sa.Text(), nullable=True),
        sa.Column('constraints', sa.JSON(), nullable=True),
        
        # Status tracking
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # Generated POV options
        sa.Column('pov_options', sa.JSON(), nullable=True),
        sa.Column('selected_pov', sa.JSON(), nullable=True),
        
        # Generated hook options
        sa.Column('hook_options', sa.JSON(), nullable=True),
        sa.Column('selected_hook', sa.JSON(), nullable=True),
        
        # Generated outline options
        sa.Column('outline_options', sa.JSON(), nullable=True),
        sa.Column('selected_outline', sa.JSON(), nullable=True),
        
        # Skills applied
        sa.Column('applied_skill_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        
        # Celery task tracking
        sa.Column('task_id', sa.String(100), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    
    # Create indexes for content_writer_runs
    op.create_index('ix_content_writer_runs_run_id', 'content_writer_runs', ['run_id'], unique=True)
    op.create_index('ix_content_writer_runs_customer_id', 'content_writer_runs', ['customer_id'])
    op.create_index('ix_content_writer_runs_user_id', 'content_writer_runs', ['user_id'])
    op.create_index('ix_content_writer_runs_status', 'content_writer_runs', ['status'])
    op.create_index('ix_content_writer_runs_created_at', 'content_writer_runs', ['created_at'])
    op.create_index('ix_content_writer_runs_task_id', 'content_writer_runs', ['task_id'])
    
    # Create research_packs table
    op.create_table(
        'research_packs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        
        # Structured research data
        sa.Column('key_takeaways', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('excerpts', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('contested_items', sa.JSON(), nullable=True),
        sa.Column('best_counterargument', sa.Text(), nullable=True),
        
        # User interactions
        sa.Column('selected_excerpt_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['content_writer_runs.id'], ondelete='CASCADE'),
    )
    
    # Create index for research_packs
    op.create_index('ix_research_packs_run_id', 'research_packs', ['run_id'])
    
    # Create draft_artifacts table
    op.create_table(
        'draft_artifacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        
        # Draft content
        sa.Column('format', sa.String(50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        
        # Metadata
        sa.Column('word_count', sa.Integer(), nullable=True),
        sa.Column('character_count', sa.Integer(), nullable=True),
        
        # Version tracking
        sa.Column('parent_version_id', sa.Integer(), nullable=True),
        sa.Column('refinement_type', sa.String(50), nullable=True),
        sa.Column('refinement_instruction', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['content_writer_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_version_id'], ['draft_artifacts.id'], ),
    )
    
    # Create indexes for draft_artifacts
    op.create_index('ix_draft_artifacts_run_id', 'draft_artifacts', ['run_id'])
    op.create_index('idx_draft_artifacts_run_version', 'draft_artifacts', ['run_id', 'version'])
    
    # Create content_writer_skills table
    op.create_table(
        'content_writer_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Skill type and content
        sa.Column('skill_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content', sa.JSON(), nullable=False),
        
        # Usage tracking
        sa.Column('is_default', sa.Boolean(), server_default='false'),
        sa.Column('usage_count', sa.Integer(), server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    
    # Create indexes for content_writer_skills
    op.create_index('ix_content_writer_skills_skill_id', 'content_writer_skills', ['skill_id'], unique=True)
    op.create_index('ix_content_writer_skills_customer_id', 'content_writer_skills', ['customer_id'])
    op.create_index('ix_content_writer_skills_user_id', 'content_writer_skills', ['user_id'])
    op.create_index('idx_content_writer_skills_user', 'content_writer_skills', ['user_id', 'customer_id'])
    op.create_index('idx_content_writer_skills_type', 'content_writer_skills', ['skill_type'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('content_writer_skills')
    op.drop_table('draft_artifacts')
    op.drop_table('research_packs')
    op.drop_table('content_writer_runs')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS issue_type')
    op.execute('DROP TYPE IF EXISTS skill_type')
    op.execute('DROP TYPE IF EXISTS content_writer_run_status')
    op.execute('DROP TYPE IF EXISTS source_type')
    op.execute('DROP TYPE IF EXISTS content_format')
