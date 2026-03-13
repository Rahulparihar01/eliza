"""Add adoption dashboard feature and permissions

Revision ID: ee5ff6gg7hh8
Revises: dd4ee5ff6gg7
Create Date: 2025-12-28

This migration adds:
- adoption_dashboard feature to platform_features
- Adoption-related permissions to the permissions table
- adoption_analyst and adoption_admin roles
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


revision = 'ee5ff6gg7hh8'
down_revision = 'dd4ee5ff6gg7'
branch_labels = None
depends_on = None
tags = ["adoption"]


def upgrade() -> None:
    conn = op.get_bind()
    
    # =========================================================================
    # 1. Add adoption_dashboard feature to platform_features
    # =========================================================================
    
    # Check if feature already exists
    result = conn.execute(text(
        "SELECT id FROM platform_features WHERE feature_key = 'adoption_dashboard'"
    )).fetchone()
    
    if not result:
        conn.execute(text("""
            INSERT INTO platform_features (
                feature_key, display_name, description, category, icon, sort_order, is_active, created_at, updated_at
            ) VALUES (
                'adoption_dashboard',
                'Adoption Dashboard',
                'Track ChatGPT Enterprise and LLM adoption metrics across companies',
                'analytics',
                'ChartBarIcon',
                50,
                true,
                now(),
                now()
            )
        """))
    
    # =========================================================================
    # 2. Add adoption permissions
    # =========================================================================
    
    adoption_permissions = [
        ('adoption:view_dashboard', 'adoption', 'view_dashboard', 'Access the adoption dashboard UI'),
        ('adoption:read:company:*', 'adoption', 'read', 'View adoption metrics for ALL companies (wildcard)'),
        ('adoption:admin:company:*', 'adoption', 'admin', 'Configure adoption data sources for ALL companies'),
        ('adoption:manage_sharing', 'adoption', 'manage_sharing', 'Share own tenant adoption data with other tenants'),
        ('adoption:manage_sync', 'adoption', 'manage_sync', 'Trigger manual adoption data syncs'),
    ]
    
    for name, resource, action, description in adoption_permissions:
        # Check if permission already exists
        result = conn.execute(text(
            "SELECT id FROM permissions WHERE name = :name"
        ), {"name": name}).fetchone()
        
        if not result:
            conn.execute(text("""
                INSERT INTO permissions (name, resource, action, description, scope, created_at)
                VALUES (:name, :resource, :action, :description, 'all', now())
            """), {
                "name": name,
                "resource": resource,
                "action": action,
                "description": description
            })
    
    # =========================================================================
    # 3. Add adoption roles
    # =========================================================================
    
    adoption_roles = [
        ('adoption_analyst', 'Adoption Analyst', 'View adoption metrics for granted companies', 6),
        ('adoption_admin', 'Adoption Administrator', 'Configure adoption data sources and sharing', 7),
    ]
    
    for name, display_name, description, hierarchy_level in adoption_roles:
        # Check if role already exists (system roles have NULL customer_id)
        result = conn.execute(text(
            "SELECT id FROM roles WHERE name = :name AND customer_id IS NULL"
        ), {"name": name}).fetchone()
        
        if not result:
            conn.execute(text("""
                INSERT INTO roles (name, display_name, description, hierarchy_level, is_active, 
                                   is_system_role, customer_id, created_at, updated_at)
                VALUES (:name, :display_name, :description, :hierarchy_level, true, 
                        true, NULL, now(), now())
            """), {
                "name": name,
                "display_name": display_name,
                "description": description,
                "hierarchy_level": hierarchy_level
            })
    
    # =========================================================================
    # 4. Assign permissions to roles
    # =========================================================================
    
    # adoption_analyst gets adoption:view_dashboard
    conn.execute(text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'adoption_analyst'
        AND p.name = 'adoption:view_dashboard'
        AND NOT EXISTS (
            SELECT 1 FROM role_permissions rp
            WHERE rp.role_id = r.id AND rp.permission_id = p.id
        )
    """))
    
    # adoption_admin gets multiple permissions
    adoption_admin_permissions = [
        'adoption:view_dashboard',
        'adoption:manage_sharing',
        'adoption:manage_sync',
    ]
    
    for perm_name in adoption_admin_permissions:
        conn.execute(text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles r, permissions p
            WHERE r.name = 'adoption_admin'
            AND p.name = :perm_name
            AND NOT EXISTS (
                SELECT 1 FROM role_permissions rp
                WHERE rp.role_id = r.id AND rp.permission_id = p.id
            )
        """), {"perm_name": perm_name})
    
    # super_admin and admin get all adoption permissions
    all_adoption_permissions = [
        'adoption:view_dashboard',
        'adoption:read:company:*',
        'adoption:admin:company:*',
        'adoption:manage_sharing',
        'adoption:manage_sync',
    ]
    
    for role_name in ['super_admin', 'admin']:
        for perm_name in all_adoption_permissions:
            conn.execute(text("""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r, permissions p
                WHERE r.name = :role_name
                AND p.name = :perm_name
                AND NOT EXISTS (
                    SELECT 1 FROM role_permissions rp
                    WHERE rp.role_id = r.id AND rp.permission_id = p.id
                )
            """), {"role_name": role_name, "perm_name": perm_name})


def downgrade() -> None:
    conn = op.get_bind()
    
    # Remove role permissions
    conn.execute(text("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions WHERE name LIKE 'adoption:%'
        )
    """))
    
    # Remove adoption roles (system roles have NULL customer_id)
    conn.execute(text("""
        DELETE FROM roles WHERE name IN ('adoption_analyst', 'adoption_admin') AND customer_id IS NULL
    """))
    
    # Remove adoption permissions
    conn.execute(text("""
        DELETE FROM permissions WHERE name LIKE 'adoption:%'
    """))
    
    # Remove adoption_dashboard feature
    conn.execute(text("""
        DELETE FROM platform_features WHERE feature_key = 'adoption_dashboard'
    """))

