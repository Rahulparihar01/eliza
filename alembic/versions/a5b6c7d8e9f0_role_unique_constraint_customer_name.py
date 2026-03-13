"""Role unique constraint on (customer_id, name)

Revision ID: a5b6c7d8e9f0
Revises: z4a5b6c7d8e9
Create Date: 2025-12-25

Roles are unique within a tenant, not globally.
Each tenant can have their own 'admin', 'editor', 'viewer' roles.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'a5b6c7d8e9f0'
down_revision = 'b6c7d8e9f0a1'  # Depends on RLS migration (linear chain)
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


def upgrade() -> None:
    conn = op.get_bind()
    
    print("Updating role unique constraint to (customer_id, name)...")
    
    # Drop old unique constraints on name alone
    conn.execute(text("DROP INDEX IF EXISTS ix_roles_name"))
    conn.execute(text("ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_name_key"))
    
    # Check if constraint already exists before creating
    result = conn.execute(text("""
        SELECT 1 FROM pg_constraint WHERE conname = 'roles_customer_name_unique'
    """))
    if result.fetchone() is None:
        conn.execute(text("""
            ALTER TABLE roles 
            ADD CONSTRAINT roles_customer_name_unique UNIQUE (customer_id, name)
        """))
        print("  ✓ Added unique constraint: (customer_id, name)")
    else:
        print("  ✓ Unique constraint already exists")
    
    # Rename tenant roles to simple names (idempotent - only updates if old names exist)
    conn.execute(text("UPDATE roles SET name = 'admin' WHERE name = 'tenant_admin'"))
    conn.execute(text("UPDATE roles SET name = 'editor' WHERE name = 'tenant_editor'"))
    conn.execute(text("UPDATE roles SET name = 'viewer' WHERE name = 'tenant_viewer'"))
    
    print("  ✓ Role names simplified: admin, editor, viewer")


def downgrade() -> None:
    conn = op.get_bind()
    
    # Rename back to tenant_ prefixed names
    conn.execute(text("UPDATE roles SET name = 'tenant_admin' WHERE name = 'admin'"))
    conn.execute(text("UPDATE roles SET name = 'tenant_editor' WHERE name = 'editor'"))
    conn.execute(text("UPDATE roles SET name = 'tenant_viewer' WHERE name = 'viewer'"))
    
    # Drop the composite unique constraint
    conn.execute(text("ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_customer_name_unique"))
    
    # Recreate the old unique constraint on name alone
    conn.execute(text("CREATE UNIQUE INDEX ix_roles_name ON roles(name)"))

