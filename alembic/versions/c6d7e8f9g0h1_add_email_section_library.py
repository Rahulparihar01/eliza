"""Add email section library table

Revision ID: c6d7e8f9g0h1
Revises: a5b6c7d8e9f0
Create Date: 2025-12-26

This migration adds the email_section_library table for storing
reusable email template sections that can be shared across templates.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c6d7e8f9g0h1'
down_revision = 'a5b6c7d8e9f0'
branch_labels = None
depends_on = None
tags = ["content"]


def upgrade() -> None:
    """Create email_section_library table."""
    
    # Check if table already exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'email_section_library'
        )
    """)).scalar()
    
    if result:
        print("Table 'email_section_library' already exists, skipping creation")
        return
    
    op.create_table(
        'email_section_library',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        
        # Identity
        sa.Column('customer_id', sa.String(100), nullable=False),
        
        # Section metadata
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        # Section type
        sa.Column('section_type', sa.String(50), nullable=False, default='static'),
        
        # For static sections
        sa.Column('content', sa.Text(), nullable=True),
        
        # For AI-generated sections
        sa.Column('ai_prompt', sa.Text(), nullable=True),
        sa.Column('ai_context_fields', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ai_tone', sa.String(50), nullable=True, default='professional'),
        sa.Column('ai_max_length', sa.Integer(), nullable=True, default=200),
        
        # Usage tracking
        sa.Column('use_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        
        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('is_shared', sa.Boolean(), nullable=False, default=False),
        
        # Creator tracking
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        
        # Primary key
        sa.PrimaryKeyConstraint('id'),
        
        # Foreign keys
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
    )
    
    # Create indexes
    op.create_index('ix_section_library_customer', 'email_section_library', ['customer_id'])
    op.create_index('ix_section_library_category', 'email_section_library', ['customer_id', 'category'])
    op.create_index('ix_section_library_active', 'email_section_library', ['customer_id', 'is_active'])
    
    print("✓ Created 'email_section_library' table")


def downgrade() -> None:
    """Drop email_section_library table."""
    
    # Drop indexes first
    op.drop_index('ix_section_library_active', table_name='email_section_library')
    op.drop_index('ix_section_library_category', table_name='email_section_library')
    op.drop_index('ix_section_library_customer', table_name='email_section_library')
    
    # Drop table
    op.drop_table('email_section_library')
    
    print("✓ Dropped 'email_section_library' table")

