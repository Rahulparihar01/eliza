"""Add section library permissions

Revision ID: d7e8f9g0h1i2
Revises: c6d7e8f9g0h1
Create Date: 2025-12-26

This migration adds the section library permissions that were missing
from the comprehensive permissions migration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = 'd7e8f9g0h1i2'
down_revision = 'c6d7e8f9g0h1'
branch_labels = None
depends_on = None
tags = ["content", "auth"]

# Section library permissions to add
SECTION_LIBRARY_PERMISSIONS = [
    ('recruiter:section_library:read', 'recruiter', 'section_library:read', 'View email section library'),
    ('recruiter:section_library:create', 'recruiter', 'section_library:create', 'Save sections to library'),
    ('recruiter:section_library:update', 'recruiter', 'section_library:update', 'Edit library sections'),
    ('recruiter:section_library:delete', 'recruiter', 'section_library:delete', 'Delete library sections'),
]


def upgrade() -> None:
    """Add section library permissions and assign to roles."""
    conn = op.get_bind()
    
    # 1. Insert the new permissions (if they don't already exist)
    for name, resource, action, description in SECTION_LIBRARY_PERMISSIONS:
        result = conn.execute(text(
            "SELECT id FROM permissions WHERE name = :name"
        ), {"name": name}).fetchone()
        
        if not result:
            conn.execute(text("""
                INSERT INTO permissions (name, resource, action, description)
                VALUES (:name, :resource, :action, :description)
            """), {
                "name": name,
                "resource": resource,
                "action": action,
                "description": description
            })
            print(f"✓ Created permission: {name}")
        else:
            print(f"⏭ Permission already exists: {name}")
    
    # 2. Assign permissions to roles
    # Get permission IDs
    perm_ids = {}
    for name, _, _, _ in SECTION_LIBRARY_PERMISSIONS:
        result = conn.execute(text(
            "SELECT id FROM permissions WHERE name = :name"
        ), {"name": name}).fetchone()
        if result:
            perm_ids[name] = result[0]
    
    # Get role IDs
    roles = {}
    for role_name in ['admin', 'editor', 'viewer']:
        result = conn.execute(text(
            "SELECT id FROM roles WHERE name = :name"
        ), {"name": role_name}).fetchall()
        roles[role_name] = [r[0] for r in result]
    
    # Role permission mappings
    # Admin gets all section library permissions
    admin_perms = [
        'recruiter:section_library:read',
        'recruiter:section_library:create',
        'recruiter:section_library:update',
        'recruiter:section_library:delete',
    ]
    
    # Editor gets read, create, update (no delete)
    editor_perms = [
        'recruiter:section_library:read',
        'recruiter:section_library:create',
        'recruiter:section_library:update',
    ]
    
    # Viewer gets read only
    viewer_perms = [
        'recruiter:section_library:read',
    ]
    
    # Assign to admin roles
    for role_id in roles.get('admin', []):
        for perm_name in admin_perms:
            if perm_name in perm_ids:
                # Check if already exists
                exists = conn.execute(text("""
                    SELECT 1 FROM role_permissions 
                    WHERE role_id = :role_id AND permission_id = :perm_id
                """), {"role_id": role_id, "perm_id": perm_ids[perm_name]}).fetchone()
                
                if not exists:
                    conn.execute(text("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (:role_id, :perm_id)
                    """), {"role_id": role_id, "perm_id": perm_ids[perm_name]})
    
    # Assign to editor roles
    for role_id in roles.get('editor', []):
        for perm_name in editor_perms:
            if perm_name in perm_ids:
                exists = conn.execute(text("""
                    SELECT 1 FROM role_permissions 
                    WHERE role_id = :role_id AND permission_id = :perm_id
                """), {"role_id": role_id, "perm_id": perm_ids[perm_name]}).fetchone()
                
                if not exists:
                    conn.execute(text("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (:role_id, :perm_id)
                    """), {"role_id": role_id, "perm_id": perm_ids[perm_name]})
    
    # Assign to viewer roles
    for role_id in roles.get('viewer', []):
        for perm_name in viewer_perms:
            if perm_name in perm_ids:
                exists = conn.execute(text("""
                    SELECT 1 FROM role_permissions 
                    WHERE role_id = :role_id AND permission_id = :perm_id
                """), {"role_id": role_id, "perm_id": perm_ids[perm_name]}).fetchone()
                
                if not exists:
                    conn.execute(text("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (:role_id, :perm_id)
                    """), {"role_id": role_id, "perm_id": perm_ids[perm_name]})
    
    print("✓ Section library permissions added and assigned to roles")


def downgrade() -> None:
    """Remove section library permissions."""
    conn = op.get_bind()
    
    # Get permission IDs
    for name, _, _, _ in SECTION_LIBRARY_PERMISSIONS:
        result = conn.execute(text(
            "SELECT id FROM permissions WHERE name = :name"
        ), {"name": name}).fetchone()
        
        if result:
            perm_id = result[0]
            # Remove from role_permissions first
            conn.execute(text(
                "DELETE FROM role_permissions WHERE permission_id = :perm_id"
            ), {"perm_id": perm_id})
            # Remove the permission
            conn.execute(text(
                "DELETE FROM permissions WHERE id = :perm_id"
            ), {"perm_id": perm_id})
            print(f"✓ Removed permission: {name}")

