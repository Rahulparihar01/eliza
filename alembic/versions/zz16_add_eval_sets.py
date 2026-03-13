"""Add eval sets table and eval source tracking

Revision ID: zz16_add_eval_sets
Revises: zz15_pm_feedback
Create Date: 2026-01-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'zz16_add_eval_sets'
down_revision = 'zz15_pm_feedback'
branch_labels = None
depends_on = None
tags = ["evals"]


def upgrade() -> None:
    # Create eval_set_type enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eval_set_type AS ENUM ('static', 'uploaded');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create eval_set_category enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eval_set_category AS ENUM (
                'general', 'retrieval', 'synthesis', 'grounding', 
                'multi_hop', 'edge_cases', 'regression', 'custom'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create eval_source enum (if not exists)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE eval_source AS ENUM ('random_sampling', 'eval_set');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create eval_sets table (if not exists)
    op.execute("""
        CREATE TABLE IF NOT EXISTS eval_sets (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            customer_id VARCHAR(100),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            domain VARCHAR(50) NOT NULL DEFAULT 'fasb',
            set_type eval_set_type NOT NULL DEFAULT 'uploaded',
            category eval_set_category NOT NULL DEFAULT 'general',
            questions JSONB NOT NULL DEFAULT '[]',
            example_count INTEGER NOT NULL DEFAULT 0,
            difficulty_distribution JSONB,
            tags JSONB,
            is_built_in BOOLEAN NOT NULL DEFAULT false,
            created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
        );
    """)
    
    # Create indexes (if not exist)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_eval_sets_customer_domain ON eval_sets (customer_id, domain);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_eval_sets_type ON eval_sets (set_type);
    """)
    
    # Create eval_set_usages table (if not exists)
    op.execute("""
        CREATE TABLE IF NOT EXISTS eval_set_usages (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            eval_set_id INTEGER NOT NULL REFERENCES eval_sets(id) ON DELETE CASCADE,
            eval_run_id INTEGER NOT NULL REFERENCES rag_eval_runs(id) ON DELETE CASCADE,
            example_count_at_run INTEGER NOT NULL
        );
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_eval_set_usages_set_run ON eval_set_usages (eval_set_id, eval_run_id);
    """)
    
    # Add eval_source column to rag_eval_runs (if not exists)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE rag_eval_runs ADD COLUMN eval_source eval_source DEFAULT 'random_sampling';
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE rag_eval_runs ADD COLUMN eval_set_id INTEGER;
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE rag_eval_runs ADD COLUMN eval_set_name VARCHAR(255);
        EXCEPTION
            WHEN duplicate_column THEN null;
        END $$;
    """)
    
    # Add FK constraint (if not exists)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE rag_eval_runs 
            ADD CONSTRAINT fk_rag_eval_runs_eval_set_id 
            FOREIGN KEY (eval_set_id) REFERENCES eval_sets(id) ON DELETE SET NULL;
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create index on eval_set_id (if not exists)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_rag_eval_runs_eval_set_id ON rag_eval_runs (eval_set_id);
    """)


def downgrade() -> None:
    # Drop FK and columns from rag_eval_runs
    op.execute("DROP INDEX IF EXISTS ix_rag_eval_runs_eval_set_id")
    op.execute("ALTER TABLE rag_eval_runs DROP CONSTRAINT IF EXISTS fk_rag_eval_runs_eval_set_id")
    op.execute("ALTER TABLE rag_eval_runs DROP COLUMN IF EXISTS eval_set_name")
    op.execute("ALTER TABLE rag_eval_runs DROP COLUMN IF EXISTS eval_set_id")
    op.execute("ALTER TABLE rag_eval_runs DROP COLUMN IF EXISTS eval_source")
    
    # Drop eval_set_usages
    op.execute("DROP INDEX IF EXISTS ix_eval_set_usages_set_run")
    op.execute("DROP TABLE IF EXISTS eval_set_usages")
    
    # Drop eval_sets
    op.execute("DROP INDEX IF EXISTS ix_eval_sets_type")
    op.execute("DROP INDEX IF EXISTS ix_eval_sets_customer_domain")
    op.execute("DROP TABLE IF EXISTS eval_sets")
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS eval_source")
    op.execute("DROP TYPE IF EXISTS eval_set_category")
    op.execute("DROP TYPE IF EXISTS eval_set_type")
