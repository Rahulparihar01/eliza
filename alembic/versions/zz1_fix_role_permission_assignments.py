"""Fix role permission assignments - assign to admin/editor/viewer roles

Revision ID: zz1_fix_role_perm_assignments
Revises: zz_cleanup_old_permissions
Create Date: 2025-12-30 15:00:00.000000

This migration fixes a bug where permissions were being assigned to non-existent
roles named 'tenant_admin', 'tenant_editor', 'tenant_viewer' instead of the
actual role names 'admin', 'editor', 'viewer'.

This migration assigns the correct permissions to all existing admin/editor/viewer
roles across all tenants.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'zz1_fix_role_perms'
down_revision = 'zz_cleanup_old_permissions'
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


# =============================================================================
# PERMISSION LISTS (same as in z4a5b6c7d8e9)
# =============================================================================

TENANT_ADMIN_PERMISSIONS = [
    # AI Assistant
    'assistant:access', 'assistant:documents:read', 'assistant:documents:upload', 'assistant:documents:delete',
    'assistant:questions:read', 'assistant:questions:ask', 'assistant:questions:delete',
    'assistant:chat:access', 'assistant:domains:onboard', 'assistant:domains:configure',
    'assistant:domains:publish', 'assistant:domains:delete', 'assistant:domains:insurance_analytics:access',
    
    # AI Recruiter
    'recruiter:access', 'recruiter:config:read', 'recruiter:config:create', 'recruiter:config:update', 'recruiter:config:delete',
    'recruiter:results:read', 'recruiter:results:email', 'recruiter:results:feedback',
    'recruiter:email_templates:read', 'recruiter:email_templates:create', 'recruiter:email_templates:update',
    'recruiter:email_templates:delete', 'recruiter:email_templates:set_default',
    'recruiter:blueprints:read', 'recruiter:blueprints:create', 'recruiter:blueprints:update', 'recruiter:blueprints:delete',
    'recruiter:dna:read', 'recruiter:dna:update',
    'recruiter:history:read', 'recruiter:history:delete',
    'recruiter:section_library:read', 'recruiter:section_library:create', 'recruiter:section_library:update', 'recruiter:section_library:delete',
    
    # Administration
    'admin:settings:read', 'admin:settings:update', 'admin:settings:providers:manage',
    'admin:email:read', 'admin:email:configure', 'admin:email:disconnect',
    
    # Data Connections
    'connections:read', 'connections:create', 'connections:update', 'connections:delete', 'connections:test', 'connections:sync',
    
    # Users & Roles
    'users:read', 'users:invite', 'users:update', 'users:deactivate', 'users:delete',
    'roles:read', 'roles:create', 'roles:update', 'roles:delete', 'roles:assign',
    'invites:read', 'invites:create', 'invites:resend', 'invites:revoke',
    
    # Audit
    'audit:read', 'audit:filter',
]

TENANT_EDITOR_PERMISSIONS = [
    # AI Assistant
    'assistant:access', 'assistant:documents:read', 'assistant:documents:upload',
    'assistant:questions:read', 'assistant:questions:ask',
    'assistant:chat:access', 'assistant:domains:insurance_analytics:access',
    
    # AI Recruiter
    'recruiter:access', 'recruiter:config:read', 'recruiter:config:create', 'recruiter:config:update',
    'recruiter:results:read', 'recruiter:results:email', 'recruiter:results:feedback',
    'recruiter:email_templates:read', 'recruiter:email_templates:create', 'recruiter:email_templates:update',
    'recruiter:blueprints:read', 'recruiter:blueprints:create', 'recruiter:blueprints:update',
    'recruiter:dna:read', 'recruiter:dna:update',
    'recruiter:history:read',
    'recruiter:section_library:read', 'recruiter:section_library:create', 'recruiter:section_library:update',
]

TENANT_VIEWER_PERMISSIONS = [
    # AI Assistant
    'assistant:access', 'assistant:documents:read', 'assistant:questions:read',
    'assistant:chat:access', 'assistant:domains:insurance_analytics:access',
    
    # AI Recruiter
    'recruiter:access', 'recruiter:config:read', 'recruiter:results:read',
    'recruiter:email_templates:read',
    'recruiter:blueprints:read', 'recruiter:dna:read',
    'recruiter:history:read',
    'recruiter:section_library:read',
]


def upgrade() -> None:
    conn = op.get_bind()
    
    print("=" * 70)
    print("FIXING ROLE PERMISSION ASSIGNMENTS")
    print("=" * 70)
    print("\nThis migration fixes the bug where permissions were assigned to")
    print("'tenant_admin', 'tenant_editor', 'tenant_viewer' instead of")
    print("'admin', 'editor', 'viewer'.")
    
    # Helper function to assign permissions to a role
    def assign_permissions_to_role(role_name: str, permission_names: list) -> int:
        """Assign permissions to ALL roles with this name across all tenants."""
        count = 0
        for perm_name in permission_names:
            result = conn.execute(text("""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r
                CROSS JOIN permissions p
                WHERE r.name = :role_name 
                  AND p.name = :perm_name
                  AND NOT EXISTS (
                      SELECT 1 FROM role_permissions rp2
                      WHERE rp2.role_id = r.id AND rp2.permission_id = p.id
                  )
            """), {'role_name': role_name, 'perm_name': perm_name})
            if result.rowcount > 0:
                count += result.rowcount
        return count
    
    # Get count of roles by name
    admin_count = conn.execute(text(
        "SELECT COUNT(*) FROM roles WHERE name = 'admin'"
    )).scalar()
    editor_count = conn.execute(text(
        "SELECT COUNT(*) FROM roles WHERE name = 'editor'"
    )).scalar()
    viewer_count = conn.execute(text(
        "SELECT COUNT(*) FROM roles WHERE name = 'viewer'"
    )).scalar()
    
    print(f"\nFound roles to update:")
    print(f"  - admin roles: {admin_count}")
    print(f"  - editor roles: {editor_count}")
    print(f"  - viewer roles: {viewer_count}")
    
    # Assign permissions to admin roles
    print(f"\n[1/3] Assigning {len(TENANT_ADMIN_PERMISSIONS)} permissions to 'admin' roles...")
    admin_assigned = assign_permissions_to_role('admin', TENANT_ADMIN_PERMISSIONS)
    print(f"  ✓ Assigned {admin_assigned} new permission-role pairs")
    
    # Assign permissions to editor roles
    print(f"\n[2/3] Assigning {len(TENANT_EDITOR_PERMISSIONS)} permissions to 'editor' roles...")
    editor_assigned = assign_permissions_to_role('editor', TENANT_EDITOR_PERMISSIONS)
    print(f"  ✓ Assigned {editor_assigned} new permission-role pairs")
    
    # Assign permissions to viewer roles
    print(f"\n[3/3] Assigning {len(TENANT_VIEWER_PERMISSIONS)} permissions to 'viewer' roles...")
    viewer_assigned = assign_permissions_to_role('viewer', TENANT_VIEWER_PERMISSIONS)
    print(f"  ✓ Assigned {viewer_assigned} new permission-role pairs")
    
    # Verify
    print("\nVerifying final permission counts...")
    for role_name in ['admin', 'editor', 'viewer']:
        count = conn.execute(text("""
            SELECT COUNT(DISTINCT rp.permission_id)
            FROM role_permissions rp
            JOIN roles r ON rp.role_id = r.id
            WHERE r.name = :role_name
        """), {'role_name': role_name}).scalar()
        print(f"  - {role_name}: {count} permissions assigned")
    
    print("\n" + "=" * 70)
    print("ROLE PERMISSION ASSIGNMENTS FIXED SUCCESSFULLY")
    print("=" * 70)


def downgrade() -> None:
    # This migration only adds missing assignments, so downgrade is a no-op
    # (we don't want to remove permissions that might have been added manually)
    print("Downgrade for 'zz1_fix_role_perm_assignments' is a no-op.")
    print("Role permission assignments remain unchanged.")
    pass

