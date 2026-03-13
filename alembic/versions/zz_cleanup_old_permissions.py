"""Remove old-style permissions from database

Revision ID: zz_cleanup_old_perms
Revises: z4a5b6c7d8e9
Create Date: 2025-12-30

This migration removes the old permission scheme that has been replaced
by the comprehensive permissions system. The old permissions are no longer
used in the codebase.

Old permissions being removed:
- data_analyst:read, data_analyst:write
- bi:read, bi:write, bi:admin
- settings:read, settings:write
- talent:read, talent:write
- system:admin
- agents:write
- hr:read, hr:write
- connectors:read, connectors:write (replaced by connections:*)
- users:create (replaced by users:invite)
- users:manage (replaced by users:update)
"""
from alembic import op
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'zz_cleanup_old_permissions'
down_revision = 'aa1bb2cc3dd5'
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


# Old permissions to remove
OLD_PERMISSIONS = [
    # Data Analyst (now assistant:questions:*)
    'data_analyst:read',
    'data_analyst:write',
    
    # Business Intelligence (now assistant:questions:*)
    'bi:read',
    'bi:write',
    'bi:admin',
    
    # Settings (now admin:settings:*)
    'settings:read',
    'settings:write',
    
    # Talent (now recruiter:*)
    'talent:read',
    'talent:write',
    
    # System admin (now labs:* or admin:*)
    'system:admin',
    
    # Agents (now labs:agents:*)
    'agents:write',
    'agents:read',
    
    # HR (TBD - mapped to assistant:access for now)
    'hr:read',
    'hr:write',
    
    # Connectors (now connections:*)
    'connectors:read',
    'connectors:write',
    'connectors:create',
    'connectors:update',
    'connectors:delete',
    'connectors:test',
    'connectors:sync',
    
    # Users (renamed)
    'users:create',  # now users:invite
    'users:manage',  # now users:update
    
    # Permissions (renamed)
    'permissions:read',
    'permissions:create',
]


def upgrade() -> None:
    """Remove old permissions and their role assignments."""
    conn = op.get_bind()
    
    print("=" * 60)
    print("CLEANING UP OLD PERMISSIONS")
    print("=" * 60)
    
    # Step 1: Remove old permissions from role_permissions
    print("\n[Step 1/2] Removing old permission assignments from roles...")
    for perm_name in OLD_PERMISSIONS:
        result = conn.execute(text("""
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE name = :perm_name
            )
        """), {'perm_name': perm_name})
        if result.rowcount > 0:
            print(f"  ✓ Removed {result.rowcount} role assignments for: {perm_name}")
    
    # Step 2: Remove old permissions from permissions table
    print("\n[Step 2/2] Removing old permissions from database...")
    for perm_name in OLD_PERMISSIONS:
        result = conn.execute(text("""
            DELETE FROM permissions WHERE name = :perm_name
        """), {'perm_name': perm_name})
        if result.rowcount > 0:
            print(f"  ✓ Deleted permission: {perm_name}")
    
    # Summary
    remaining = conn.execute(text("SELECT COUNT(*) FROM permissions")).scalar()
    print("\n" + "=" * 60)
    print(f"CLEANUP COMPLETE - {remaining} permissions remain in database")
    print("=" * 60)


def downgrade() -> None:
    """Restore old permissions (not recommended)."""
    conn = op.get_bind()
    
    print("WARNING: Restoring old permissions is not fully supported.")
    print("The old permission scheme should not be used.")
    
    # Re-create old permissions (basic restore)
    OLD_PERMISSION_DEFINITIONS = [
        ('data_analyst:read', 'data_analyst', 'read', 'Read data analyst'),
        ('data_analyst:write', 'data_analyst', 'write', 'Write data analyst'),
        ('bi:read', 'bi', 'read', 'Read BI'),
        ('bi:write', 'bi', 'write', 'Write BI'),
        ('bi:admin', 'bi', 'admin', 'Admin BI'),
        ('settings:read', 'settings', 'read', 'Read settings'),
        ('settings:write', 'settings', 'write', 'Write settings'),
        ('talent:read', 'talent', 'read', 'Read talent'),
        ('talent:write', 'talent', 'write', 'Write talent'),
        ('system:admin', 'system', 'admin', 'System admin'),
        ('agents:write', 'agents', 'write', 'Write agents'),
        ('agents:read', 'agents', 'read', 'Read agents'),
        ('hr:read', 'hr', 'read', 'Read HR'),
        ('hr:write', 'hr', 'write', 'Write HR'),
        ('connectors:read', 'connectors', 'read', 'Read connectors'),
        ('connectors:write', 'connectors', 'write', 'Write connectors'),
        ('users:create', 'users', 'create', 'Create users'),
        ('users:manage', 'users', 'manage', 'Manage users'),
    ]
    
    for name, resource, action, description in OLD_PERMISSION_DEFINITIONS:
        conn.execute(text("""
            INSERT INTO permissions (name, resource, action, description, created_at, updated_at)
            VALUES (:name, :resource, :action, :description, NOW(), NOW())
            ON CONFLICT (name) DO NOTHING
        """), {'name': name, 'resource': resource, 'action': action, 'description': description})
    
    print("Old permissions restored (role assignments NOT restored)")

