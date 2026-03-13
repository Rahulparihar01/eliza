"""Add prompt management tables

Revision ID: zz12_prompt_management
Revises: zz11_gepa_human_feedback
Create Date: 2026-01-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'zz12_prompt_management'
down_revision = 'zz11_gepa_human_feedback'
branch_labels = None
depends_on = None
tags = ["ai_console", "evals"]


def upgrade():
    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE prompt_type AS ENUM ('system', 'query_rewrite', 'retrieval', 'synthesis', 'evaluation', 'custom');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE prompt_status AS ENUM ('draft', 'active', 'archived', 'testing');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create prompt_templates table
    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            
            customer_id VARCHAR(100) NOT NULL,
            domain VARCHAR(100) NOT NULL,
            prompt_type prompt_type NOT NULL,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            
            content TEXT NOT NULL,
            variables JSON,
            
            version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT false,
            parent_version_id INTEGER REFERENCES prompt_templates(id),
            
            status prompt_status NOT NULL DEFAULT 'draft',
            
            created_by_user_id INTEGER REFERENCES users(id),
            last_modified_by_user_id INTEGER REFERENCES users(id),
            
            gepa_variant_id INTEGER REFERENCES gepa_candidate_variants(id) ON DELETE SET NULL,
            gepa_job_id INTEGER REFERENCES gepa_optimizer_jobs(id) ON DELETE SET NULL,
            
            avg_quality_score INTEGER,
            usage_count INTEGER NOT NULL DEFAULT 0,
            
            CONSTRAINT uq_prompt_version UNIQUE (customer_id, domain, prompt_type, version)
        );
    """)
    
    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_prompt_templates_customer_id ON prompt_templates(customer_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prompt_templates_domain ON prompt_templates(domain);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_prompt_templates_active ON prompt_templates(customer_id, domain, prompt_type, is_active) WHERE is_active = true;")
    
    # Create prompt_change_logs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_change_logs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            
            prompt_template_id INTEGER NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
            
            action VARCHAR(50) NOT NULL,
            previous_content TEXT,
            new_content TEXT,
            change_summary TEXT,
            
            user_id INTEGER REFERENCES users(id),
            
            source VARCHAR(50) NOT NULL DEFAULT 'manual',
            source_reference VARCHAR(255)
        );
    """)
    
    op.execute("CREATE INDEX IF NOT EXISTS ix_prompt_change_logs_template ON prompt_change_logs(prompt_template_id);")
    
    # Create domain_prompt_configs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS domain_prompt_configs (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            
            customer_id VARCHAR(100) NOT NULL,
            domain VARCHAR(100) NOT NULL,
            
            display_name VARCHAR(255) NOT NULL,
            description TEXT,
            
            use_query_rewrite BOOLEAN NOT NULL DEFAULT true,
            use_custom_system_prompt BOOLEAN NOT NULL DEFAULT true,
            
            default_model VARCHAR(100),
            temperature INTEGER,
            max_tokens INTEGER,
            
            retrieval_top_k INTEGER DEFAULT 10,
            similarity_threshold INTEGER DEFAULT 70,
            
            is_active BOOLEAN NOT NULL DEFAULT true,
            
            CONSTRAINT uq_domain_config UNIQUE (customer_id, domain)
        );
    """)
    
    op.execute("CREATE INDEX IF NOT EXISTS ix_domain_configs_customer ON domain_prompt_configs(customer_id);")


def downgrade():
    op.execute("DROP TABLE IF EXISTS prompt_change_logs CASCADE;")
    op.execute("DROP TABLE IF EXISTS domain_prompt_configs CASCADE;")
    op.execute("DROP TABLE IF EXISTS prompt_templates CASCADE;")
    op.execute("DROP TYPE IF EXISTS prompt_type CASCADE;")
    op.execute("DROP TYPE IF EXISTS prompt_status CASCADE;")
