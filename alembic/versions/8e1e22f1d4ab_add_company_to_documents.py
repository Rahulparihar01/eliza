"""add company to documents

Revision ID: 8e1e22f1d4ab
Revises: 7d0d11d0c3fc
Create Date: 2025-10-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8e1e22f1d4ab'
down_revision = '7d0d11d0c3fc'
branch_labels = None
depends_on = None
tags = ["core", "tenancy"]


def upgrade() -> None:
    """Upgrade schema."""
    # Add company_hr_dataset to documents table
    op.add_column(
        'documents',
        sa.Column('company_hr_dataset', sa.String(100), nullable=True)
    )
    
    # Backfill: Set company_hr_dataset to customer_id for existing documents
    # (maintains current behavior - documents associated with uploader's org)
    op.execute("""
        UPDATE documents 
        SET company_hr_dataset = customer_id 
        WHERE company_hr_dataset IS NULL
    """)
    
    # Add index for performance
    op.create_index(
        'idx_documents_company_hr_dataset',
        'documents',
        ['company_hr_dataset']
    )
    
    # Update document_chunks if it needs company reference
    # (chunks inherit from parent document, but we add for query performance)
    op.add_column(
        'document_chunks',
        sa.Column('company_hr_dataset', sa.String(100), nullable=True)
    )
    
    # Backfill chunks from their parent documents
    op.execute("""
        UPDATE document_chunks dc
        SET company_hr_dataset = d.company_hr_dataset
        FROM documents d
        WHERE dc.document_id = d.id
    """)
    
    # Add index on chunks
    op.create_index(
        'idx_document_chunks_company_hr_dataset',
        'document_chunks',
        ['company_hr_dataset']
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_document_chunks_company_hr_dataset', table_name='document_chunks')
    op.drop_index('idx_documents_company_hr_dataset', table_name='documents')
    
    # Drop columns
    op.drop_column('document_chunks', 'company_hr_dataset')
    op.drop_column('documents', 'company_hr_dataset')

