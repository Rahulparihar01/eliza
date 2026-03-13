"""Unify role system - add customer_id to roles table

This migration unifies the permission system by:
1. Adding customer_id to roles table for tenant scoping
2. Creating platform_admin role with all permissions
3. Cleaning up duplicate tenant role tables (they remain but are deprecated)

Revision ID: w1x2y3z4a5b6
Revises: v0w1x2y3z4a5
Create Date: 2025-12-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'w1x2y3z4a5b6'
down_revision = 'v0w1x2y3z4a5'
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


def upgrade():
    """
    Add customer_id to roles table and set up platform_admin role.
    """
    conn = op.get_bind()
    
    # 1. Add customer_id column to roles table (nullable for platform-level roles)
    # Use raw SQL with IF NOT EXISTS logic for idempotency
    conn.execute(text("""
        DO $$ BEGIN
            ALTER TABLE roles ADD COLUMN customer_id VARCHAR(100) REFERENCES customers(customer_id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """))
    
    # Create index if not exists
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_roles_customer_id ON roles(customer_id);
    """))
    
    # 2. Add is_system_role column to identify default roles
    conn.execute(text("""
        DO $$ BEGIN
            ALTER TABLE roles ADD COLUMN is_system_role BOOLEAN NOT NULL DEFAULT false;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """))
    
    # 3. Clear existing user_roles (will be reassigned via admin UI)
    conn.execute(text("DELETE FROM user_roles"))
    
    # 4. Clear existing role_permissions (will be redefined)
    conn.execute(text("DELETE FROM role_permissions"))
    
    # 5. Clear existing roles (will be recreated)
    conn.execute(text("DELETE FROM roles"))
    
    # 6. Clear existing permissions (will be recreated based on features)
    conn.execute(text("DELETE FROM permissions"))
    
    # 7. Create platform_admin role (null customer_id = platform level)
    conn.execute(text("""
        INSERT INTO roles (id, name, display_name, description, is_active, hierarchy_level, is_system_role, created_at, updated_at)
        VALUES (1, 'platform_admin', 'Platform Administrator', 'Full platform access - can manage all tenants and features', true, 100, true, NOW(), NOW())
    """))
    
    # 8. Create base permissions for all platform features
    # Format: feature_key:action
    permissions = [
        # Documents & RAG
        ('documents:read', 'documents', 'read', 'View documents and search'),
        ('documents:create', 'documents', 'create', 'Upload new documents'),
        ('documents:update', 'documents', 'update', 'Edit document metadata'),
        ('documents:delete', 'documents', 'delete', 'Delete documents'),
        
        # Data Connectors
        ('connectors:read', 'connectors', 'read', 'View data connectors'),
        ('connectors:create', 'connectors', 'create', 'Create data connectors'),
        ('connectors:update', 'connectors', 'update', 'Configure connectors'),
        ('connectors:delete', 'connectors', 'delete', 'Delete connectors'),
        ('connectors:sync', 'connectors', 'sync', 'Trigger data syncs'),
        
        # AI Providers
        ('ai_providers:read', 'ai_providers', 'read', 'View AI provider configs'),
        ('ai_providers:create', 'ai_providers', 'create', 'Add AI providers'),
        ('ai_providers:update', 'ai_providers', 'update', 'Configure AI providers'),
        ('ai_providers:delete', 'ai_providers', 'delete', 'Remove AI providers'),
        
        # Business Intelligence
        ('business_intelligence:read', 'business_intelligence', 'read', 'View BI reports'),
        ('business_intelligence:create', 'business_intelligence', 'create', 'Create BI sessions'),
        ('business_intelligence:ask', 'business_intelligence', 'ask', 'Ask BI questions'),
        
        # Talent Intelligence  
        ('talent_intelligence:read', 'talent_intelligence', 'read', 'View talent analyses'),
        ('talent_intelligence:create', 'talent_intelligence', 'create', 'Run talent analyses'),
        ('talent_intelligence:update', 'talent_intelligence', 'update', 'Edit analysis configs'),
        ('talent_intelligence:delete', 'talent_intelligence', 'delete', 'Delete analyses'),
        
        # HR Intelligence
        ('hr_intelligence:read', 'hr_intelligence', 'read', 'View HR data'),
        ('hr_intelligence:create', 'hr_intelligence', 'create', 'Create HR records'),
        ('hr_intelligence:update', 'hr_intelligence', 'update', 'Update HR data'),
        
        # Users & Roles (Tenant Admin)
        ('users:read', 'users', 'read', 'View users in tenant'),
        ('users:create', 'users', 'create', 'Invite users to tenant'),
        ('users:update', 'users', 'update', 'Edit user details'),
        ('users:delete', 'users', 'delete', 'Remove users from tenant'),
        ('roles:read', 'roles', 'read', 'View roles'),
        ('roles:create', 'roles', 'create', 'Create custom roles'),
        ('roles:update', 'roles', 'update', 'Edit role permissions'),
        ('roles:delete', 'roles', 'delete', 'Delete custom roles'),
        
        # Settings
        ('settings:read', 'settings', 'read', 'View settings'),
        ('settings:update', 'settings', 'update', 'Modify settings'),
        
        # Audit & Logging
        ('audit:read', 'audit', 'read', 'View audit logs'),
        
        # Platform Admin only
        ('platform:admin', 'platform', 'admin', 'Full platform administration'),
        ('tenants:read', 'tenants', 'read', 'View all tenants'),
        ('tenants:create', 'tenants', 'create', 'Create new tenants'),
        ('tenants:update', 'tenants', 'update', 'Modify tenant settings'),
        ('tenants:delete', 'tenants', 'delete', 'Deactivate tenants'),
        ('features:allocate', 'features', 'allocate', 'Allocate features to tenants'),
    ]
    
    for i, (name, resource, action, description) in enumerate(permissions, start=1):
        conn.execute(text("""
            INSERT INTO permissions (id, name, resource, action, description, scope, created_at)
            VALUES (:id, :name, :resource, :action, :description, 'all', NOW())
        """), {"id": i, "name": name, "resource": resource, "action": action, "description": description})
    
    # 9. Assign ALL permissions to platform_admin role
    permission_count = len(permissions)
    for i in range(1, permission_count + 1):
        conn.execute(text("""
            INSERT INTO role_permissions (role_id, permission_id, granted_at)
            VALUES (1, :perm_id, NOW())
        """), {"perm_id": i})
    
    # 10. Assign platform_admin role to scott@eliza.com
    conn.execute(text("""
        INSERT INTO user_roles (user_id, role_id, assigned_at, active)
        SELECT id, 1, NOW(), true FROM users WHERE email = 'scott@eliza.com'
    """))
    
    # 11. Create default tenant roles template (these will be copied when creating new tenants)
    # Note: These have customer_id = NULL as templates, actual tenant roles will have customer_id set
    conn.execute(text("""
        INSERT INTO roles (id, name, display_name, description, is_active, hierarchy_level, is_system_role, created_at, updated_at, customer_id)
        VALUES 
            (2, 'tenant_admin', 'Tenant Administrator', 'Full access within tenant', true, 90, true, NOW(), NOW(), NULL),
            (3, 'tenant_viewer', 'Viewer', 'Read-only access', true, 10, true, NOW(), NOW(), NULL)
    """))
    
    # Reset sequence for roles table
    conn.execute(text("SELECT setval('roles_id_seq', (SELECT MAX(id) FROM roles))"))
    conn.execute(text("SELECT setval('permissions_id_seq', (SELECT MAX(id) FROM permissions))"))


def downgrade():
    """
    Remove customer_id from roles table and restore original state.
    """
    conn = op.get_bind()
    
    # Clear the unified tables
    conn.execute(text("DELETE FROM user_roles"))
    conn.execute(text("DELETE FROM role_permissions"))
    conn.execute(text("DELETE FROM roles"))
    conn.execute(text("DELETE FROM permissions"))
    
    # Remove added columns
    op.drop_column('roles', 'is_system_role')
    op.drop_column('roles', 'customer_id')

