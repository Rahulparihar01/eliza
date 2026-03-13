"""Add GEPA human feedback table

Revision ID: zz11_gepa_human_feedback
Revises: zz10_add_gepa_optimizer_tables
Create Date: 2026-01-16

Adds human-in-the-loop feedback support for GEPA optimization.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'zz11_gepa_human_feedback'
down_revision = 'zz10_gepa_optimizer'
branch_labels = None
depends_on = None
tags = ["ai_console", "evals"]


def upgrade() -> None:
    # Create enums and table using raw SQL to avoid SQLAlchemy's enum creation behavior
    op.execute("""
        -- Create feedback_type enum
        DO $$ BEGIN
            CREATE TYPE feedback_type AS ENUM ('per_query', 'overall');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        
        -- Create feedback_rating enum
        DO $$ BEGIN
            CREATE TYPE feedback_rating AS ENUM ('strongly_negative', 'negative', 'neutral', 'positive', 'strongly_positive');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        
        -- Create gepa_human_feedback table
        CREATE TABLE IF NOT EXISTS gepa_human_feedback (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now(),
            
            -- Links
            job_id INTEGER NOT NULL REFERENCES gepa_optimizer_jobs(id) ON DELETE CASCADE,
            variant_id INTEGER NOT NULL REFERENCES gepa_candidate_variants(id) ON DELETE CASCADE,
            
            -- Feedback type and rating
            feedback_type feedback_type NOT NULL,
            rating feedback_rating NOT NULL,
            rating_numeric INTEGER NOT NULL,
            
            -- Optional link to evaluation result
            eval_result_id INTEGER REFERENCES gepa_evaluation_results(id) ON DELETE SET NULL,
            
            -- Query context
            query_text TEXT,
            response_text TEXT,
            
            -- Feedback content
            comment TEXT,
            tags JSONB,
            improvement_suggestions TEXT,
            target_components JSONB,
            
            -- Who
            user_id INTEGER NOT NULL REFERENCES users(id),
            
            -- Incorporation tracking
            incorporated BOOLEAN NOT NULL DEFAULT FALSE,
            incorporated_at TIMESTAMP,
            incorporated_in_variant_id INTEGER REFERENCES gepa_candidate_variants(id) ON DELETE SET NULL
        );
        
        -- Create indexes
        CREATE INDEX IF NOT EXISTS ix_gepa_human_feedback_job_id ON gepa_human_feedback(job_id);
        CREATE INDEX IF NOT EXISTS ix_gepa_human_feedback_variant_id ON gepa_human_feedback(variant_id);
        CREATE INDEX IF NOT EXISTS ix_gepa_feedback_job_variant ON gepa_human_feedback(job_id, variant_id);
        CREATE INDEX IF NOT EXISTS ix_gepa_feedback_unincorporated ON gepa_human_feedback(job_id, incorporated);
    """)


def downgrade() -> None:
    # Drop table
    op.drop_table('gepa_human_feedback')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS feedback_rating')
    op.execute('DROP TYPE IF EXISTS feedback_type')
