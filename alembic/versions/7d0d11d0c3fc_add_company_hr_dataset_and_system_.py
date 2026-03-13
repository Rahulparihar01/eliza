"""add_company_hr_dataset_and_system_settings

Revision ID: 7d0d11d0c3fc
Revises: 014_bi_schema
Create Date: 2025-10-06 17:48:34.286262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7d0d11d0c3fc'
down_revision: Union[str, Sequence[str], None] = '014_bi_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core", "tenancy"]


def upgrade() -> None:
    """Upgrade schema."""
    # Create system_settings table for admin configuration
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('setting_key', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('setting_value', sa.Text(), nullable=True),
        sa.Column('setting_type', sa.String(50), nullable=False, default='string'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Add company_hr_dataset column to bi_questions
    op.add_column(
        'bi_questions',
        sa.Column('company_hr_dataset', sa.String(100), nullable=True)
    )
    
    # Backfill: Set company_hr_dataset to customer_id for existing records
    # (maintains current behavior - users query their own org's data)
    op.execute("""
        UPDATE bi_questions 
        SET company_hr_dataset = customer_id 
        WHERE company_hr_dataset IS NULL
    """)
    
    # Add index for performance
    op.create_index(
        'idx_bi_questions_company_hr_dataset',
        'bi_questions',
        ['company_hr_dataset']
    )
    
    # Insert default system setting (using 'caylent' as default)
    op.execute("""
        INSERT INTO system_settings (setting_key, setting_value, setting_type, description, is_public)
        VALUES (
            'default_company_hr_dataset',
            'caylent',
            'string',
            'Default company for HR data queries when not explicitly specified',
            false
        )
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove index
    op.drop_index('idx_bi_questions_company_hr_dataset', 'bi_questions')
    
    # Remove column from bi_questions
    op.drop_column('bi_questions', 'company_hr_dataset')
    
    # Drop system_settings table
    op.drop_table('system_settings')
