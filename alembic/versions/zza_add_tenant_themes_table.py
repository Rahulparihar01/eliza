"""Add tenant_themes table and theme:write permission

Revision ID: zza_tenant_themes
Revises: zz9_validate_citations
Create Date: 2026-01-23 12:00:00.000000

This migration adds:
- tenant_themes table for storing tenant-specific branding/theme settings
- theme:write permission for managing theme settings
- Adds theme:write to tenant_admin role
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision: str = 'zza_tenant_themes'
down_revision: Union[str, None] = 'zz9_validate_citations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["tenancy", "core"]


def upgrade() -> None:
    # Create tenant_themes table
    op.create_table(
        'tenant_themes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('primary_color', sa.String(7), nullable=False, server_default='#c9506b'),
        sa.Column('primary_light_color', sa.String(7), nullable=False, server_default='#e8a598'),
        sa.Column('accent_color', sa.String(7), nullable=False, server_default='#f5c4a1'),
        sa.Column('text_color', sa.String(7), nullable=False, server_default='#5c4a5a'),
        sa.Column('preset_name', sa.String(50), server_default='eliza-forge'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.UniqueConstraint('customer_id')
    )
    
    # Create index on customer_id
    op.create_index('idx_tenant_themes_customer', 'tenant_themes', ['customer_id'])
    
    # Add theme:write permission
    conn = op.get_bind()
    
    # Insert the permission (permissions table uses created_at only, no updated_at)
    conn.execute(text("""
        INSERT INTO permissions (name, resource, action, description, scope, created_at)
        VALUES ('theme:write', 'theme', 'write', 'Manage tenant theme and branding settings', 'all', NOW())
        ON CONFLICT (name) DO NOTHING
    """))
    
    # Get the permission ID
    result = conn.execute(text("SELECT id FROM permissions WHERE name = 'theme:write'"))
    row = result.fetchone()
    if row:
        permission_id = row[0]
        
        # Assign to admin role (tenant admin) for each customer
        # Get all admin roles that are not system roles
        conn.execute(text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, :permission_id
            FROM roles r
            WHERE r.name = 'admin' AND r.is_system_role = FALSE
            ON CONFLICT DO NOTHING
        """), {"permission_id": permission_id})
        
        # Also assign to platform_admin role
        conn.execute(text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, :permission_id
            FROM roles r
            WHERE r.name = 'platform_admin' AND r.is_system_role = TRUE
            ON CONFLICT DO NOTHING
        """), {"permission_id": permission_id})


def downgrade() -> None:
    # Remove permission from roles first
    conn = op.get_bind()
    
    # Get permission ID
    result = conn.execute(text("SELECT id FROM permissions WHERE name = 'theme:write'"))
    row = result.fetchone()
    if row:
        permission_id = row[0]
        conn.execute(text("DELETE FROM role_permissions WHERE permission_id = :permission_id"), {"permission_id": permission_id})
    
    # Delete permission
    conn.execute(text("DELETE FROM permissions WHERE name = 'theme:write'"))
    
    # Drop table
    op.drop_index('idx_tenant_themes_customer', 'tenant_themes')
    op.drop_table('tenant_themes')
