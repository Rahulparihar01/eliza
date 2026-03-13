"""Add missing timestamp columns to tenant tables

Revision ID: aa1bb2cc3dd5
Revises: cc3dd4ee5ff6
Create Date: 2025-12-27 11:00:00.000000

This migration adds missing created_at and updated_at columns to tables
that were created without them or where the columns weren't properly added.

The migration is idempotent - it checks if columns exist before adding them.

Tables affected:
- tenant_feature_allocations
- tenant_roles
- tenant_role_permissions
- tenant_user_roles
- platform_features
- feature_permissions
- platform_admins
- user_invites

Note: This migration was created to fix schema issues discovered in the
Caylent production environment where these tables were missing the
timestamp columns expected by SQLAlchemy models inheriting from BaseModel.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'aa1bb2cc3dd5'
down_revision = 'cc3dd4ee5ff6'
branch_labels = None
depends_on = None
tags = ["tenancy", "core"]


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    result = conn.execute(text(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public'
            AND table_name = :table_name
        )
    """), {"table_name": table_name})
    return result.scalar()


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    conn = op.get_bind()
    result = conn.execute(text("""
        SELECT EXISTS (
            SELECT FROM information_schema.columns 
            WHERE table_schema = 'public'
            AND table_name = :table_name
            AND column_name = :column_name
        )
    """), {"table_name": table_name, "column_name": column_name})
    return result.scalar()


def upgrade() -> None:
    """Add missing timestamp columns to tenant tables."""
    
    # Tables that inherit from BaseModel and need created_at/updated_at
    tables_to_check = [
        'tenant_feature_allocations',
        'tenant_roles', 
        'tenant_role_permissions',
        'tenant_user_roles',
        'platform_features',
        'feature_permissions',
        'platform_admins',
        'user_invites',
    ]
    
    for table_name in tables_to_check:
        # Skip if table doesn't exist
        if not table_exists(table_name):
            print(f"Table {table_name} does not exist, skipping")
            continue
            
        # Add created_at if missing
        if not column_exists(table_name, 'created_at'):
            op.add_column(
                table_name,
                sa.Column('created_at', sa.DateTime(timezone=True), 
                          server_default=sa.text('now()'), nullable=False)
            )
            print(f"Added created_at to {table_name}")
        else:
            print(f"Column created_at already exists in {table_name}")
        
        # Add updated_at if missing
        if not column_exists(table_name, 'updated_at'):
            op.add_column(
                table_name,
                sa.Column('updated_at', sa.DateTime(timezone=True),
                          server_default=sa.text('now()'), nullable=False)
            )
            print(f"Added updated_at to {table_name}")
        else:
            print(f"Column updated_at already exists in {table_name}")


def downgrade() -> None:
    """Remove added timestamp columns.
    
    Note: We intentionally do NOT remove columns on downgrade because:
    1. It would cause data loss
    2. The columns are expected by the ORM models
    3. Having extra columns doesn't break anything
    
    If you really need to remove them, do it manually with:
    ALTER TABLE table_name DROP COLUMN created_at;
    ALTER TABLE table_name DROP COLUMN updated_at;
    """
    pass
