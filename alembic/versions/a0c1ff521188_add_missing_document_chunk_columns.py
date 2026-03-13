"""add_missing_document_chunk_columns

Revision ID: a0c1ff521188
Revises: cad767c6f516
Create Date: 2025-10-01 16:56:18.666562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a0c1ff521188'
down_revision: Union[str, Sequence[str], None] = 'cad767c6f516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core"]


def upgrade() -> None:
    """Upgrade schema - Add missing columns to document_chunks table.
    
    This migration adds columns that are required by the DocumentChunk model
    but are missing from the database schema. Uses ADD COLUMN IF NOT EXISTS
    to safely handle cases where columns might already exist.
    """
    
    # Add quality_score column if it doesn't exist
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS quality_score DOUBLE PRECISION;
    """)
    
    # Add section_title column if it doesn't exist
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS section_title VARCHAR(500);
    """)
    
    # Add section_level column if it doesn't exist
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS section_level INTEGER;
    """)
    
    # Add parent_chunk_id column with index if it doesn't exist
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS parent_chunk_id VARCHAR(100);
    """)
    
    # Create index on parent_chunk_id if it doesn't exist
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_document_chunks_parent_chunk_id 
        ON document_chunks (parent_chunk_id);
    """)
    
    # Add qa_questions column if it doesn't exist
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS qa_questions JSON;
    """)
    
    # Add qa_answers column if it doesn't exist
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS qa_answers JSON;
    """)
    
    # Add qa_quality_score column if it doesn't exist
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS qa_quality_score DOUBLE PRECISION;
    """)


def downgrade() -> None:
    """Downgrade schema - Remove added columns.
    
    This will only drop columns if they exist, to safely handle
    partial migrations or rollbacks.
    """
    
    # Drop columns in reverse order
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS qa_quality_score;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS qa_answers;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS qa_questions;")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_parent_chunk_id;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS parent_chunk_id;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS section_level;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS section_title;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS quality_score;")

