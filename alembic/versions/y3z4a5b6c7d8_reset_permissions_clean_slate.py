"""Reset permissions - clean slate for feature-based permissions

Revision ID: y3z4a5b6c7d8
Revises: x2y3z4a5b6c7
Create Date: 2025-12-25 12:00:00.000000

This migration resets the permissions table to a clean slate.
We keep ONLY platform:admin as the super permission.
All other permissions will be added incrementally per feature set.

The platform_admin role retains platform:admin, so super admins still work.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'y3z4a5b6c7d8'
down_revision = 'x2y3z4a5b6c7'
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


def upgrade() -> None:
    # Step 1: Clear all role_permissions EXCEPT platform_admin -> platform:admin
    op.execute("""
        DELETE FROM role_permissions 
        WHERE NOT (
            role_id IN (SELECT id FROM roles WHERE name = 'platform_admin')
            AND permission_id IN (SELECT id FROM permissions WHERE name = 'platform:admin')
        )
    """)
    
    # Step 2: Clear all permissions EXCEPT platform:admin
    op.execute("""
        DELETE FROM permissions 
        WHERE name != 'platform:admin'
    """)
    
    # Step 3: Ensure platform:admin exists and is properly configured
    # Permissions table columns: name, resource, action, description, scope, conditions, created_at
    op.execute("""
        INSERT INTO permissions (name, resource, action, description, scope, created_at)
        VALUES ('platform:admin', 'platform', 'admin', 'Full platform administration with all permissions. All actions are logged.', 'all', now())
        ON CONFLICT (name) DO UPDATE SET 
            description = 'Full platform administration with all permissions. All actions are logged.'
    """)
    
    # Step 4: Ensure platform_admin role has platform:admin
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'platform_admin' AND p.name = 'platform:admin'
        ON CONFLICT DO NOTHING
    """)
    
    # Log what we did
    print("=" * 60)
    print("PERMISSIONS RESET TO CLEAN SLATE")
    print("=" * 60)
    print("Kept: platform:admin")
    print("Removed: All other permissions")
    print("")
    print("Next steps:")
    print("  1. Add AI Assistant permissions")
    print("  2. Add AI Recruiter permissions")
    print("  3. Add Administration permissions")
    print("  4. Add other feature permissions")
    print("=" * 60)


def downgrade() -> None:
    # Can't easily restore old permissions - would need to re-run the original migration
    # This is intentionally a one-way migration
    print("WARNING: Cannot restore old permissions. Re-run w1x2y3z4a5b6 if needed.")
