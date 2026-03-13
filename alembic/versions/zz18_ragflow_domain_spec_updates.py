"""Update RAGFlow domains: add icon/color, update status enum to match spec

Revision ID: zz18_ragflow_domain_spec_updates
Revises: zz17_add_ragflow_tables
Create Date: 2026-01-22

Per spec: RAG Domains should have icon, color fields and status values:
pending | indexing | ready | failed (replacing active/inactive/syncing/error)
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'zz18_ragflow_domain_spec_updates'
down_revision = 'zz17_add_ragflow_tables'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    # Add icon column with default
    op.execute("""
        ALTER TABLE ragflow_domains 
        ADD COLUMN IF NOT EXISTS icon VARCHAR(50) NOT NULL DEFAULT 'folder';
    """)
    
    # Add color column with default
    op.execute("""
        ALTER TABLE ragflow_domains 
        ADD COLUMN IF NOT EXISTS color VARCHAR(50) NOT NULL DEFAULT 'violet';
    """)
    
    # Add last_error column
    op.execute("""
        ALTER TABLE ragflow_domains 
        ADD COLUMN IF NOT EXISTS last_error TEXT;
    """)
    
    # PostgreSQL requires enum values to be committed before use.
    # Since we're adding new values AND using them in the same migration,
    # we need to create a new enum type and migrate.
    
    # Create new enum type with all values
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE ragflow_domain_status_new AS ENUM (
                'pending', 'indexing', 'ready', 'failed',
                'active', 'inactive', 'syncing', 'error'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Alter the column to use text temporarily
    op.execute("""
        ALTER TABLE ragflow_domains 
        ALTER COLUMN status TYPE VARCHAR(20) USING status::VARCHAR;
    """)
    
    # Migrate existing data from old status values to new
    # active -> ready (domain was working, so it's ready)
    # inactive -> pending (domain was not active, treat as pending)
    # syncing -> indexing (documents being processed)
    # error -> failed (error occurred)
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'ready' 
        WHERE status = 'active';
    """)
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'pending' 
        WHERE status = 'inactive';
    """)
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'indexing' 
        WHERE status = 'syncing';
    """)
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'failed' 
        WHERE status = 'error';
    """)
    
    # Drop the old enum type with CASCADE to remove default dependency
    op.execute("DROP TYPE IF EXISTS ragflow_domain_status CASCADE;")
    op.execute("ALTER TYPE ragflow_domain_status_new RENAME TO ragflow_domain_status;")
    
    # Convert back to enum and set new default
    op.execute("""
        ALTER TABLE ragflow_domains 
        ALTER COLUMN status TYPE ragflow_domain_status 
        USING status::ragflow_domain_status;
    """)
    
    # Re-add default value for new domains
    op.execute("""
        ALTER TABLE ragflow_domains 
        ALTER COLUMN status SET DEFAULT 'pending';
    """)


def downgrade() -> None:
    # Migrate back to old status values
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'active' 
        WHERE status = 'ready';
    """)
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'inactive' 
        WHERE status = 'pending';
    """)
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'syncing' 
        WHERE status = 'indexing';
    """)
    op.execute("""
        UPDATE ragflow_domains 
        SET status = 'error' 
        WHERE status = 'failed';
    """)
    
    # Drop new columns
    op.execute("ALTER TABLE ragflow_domains DROP COLUMN IF EXISTS icon;")
    op.execute("ALTER TABLE ragflow_domains DROP COLUMN IF EXISTS color;")
    op.execute("ALTER TABLE ragflow_domains DROP COLUMN IF EXISTS last_error;")
    
    # Note: Cannot remove enum values in PostgreSQL, but data is migrated back
