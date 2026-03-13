"""Cleanup scott@eliza.com platform admin status

Revision ID: zz2_cleanup_scott_platform_admin
Revises: zz1_fix_role_perm_assignments
Create Date: 2025-12-30 16:00:00.000000

This migration ensures scott@eliza.com is set up as a tenant admin for Caylent,
NOT as a platform admin. Platform admin privileges should only be held by
admin@eliza.com (or other designated platform admins).

Changes:
1. Remove scott@eliza.com from platform_admins table (if present)
2. Set is_superuser=false for scott@eliza.com
3. Ensure scott@eliza.com has the 'admin' role for 'caylent' tenant
4. Ensure scott@eliza.com's customer_id is 'caylent' (not 'platform')
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'zz2_scott_tenant_admin'
down_revision = 'zz1_fix_role_perms'
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


TENANT_USER_EMAIL = 'scott@eliza.com'
TENANT_CUSTOMER_ID = 'caylent'


def upgrade() -> None:
    """Clean up scott@eliza.com to be a tenant admin, not platform admin."""
    conn = op.get_bind()
    
    print("=" * 60)
    print(f"CLEANING UP {TENANT_USER_EMAIL} PLATFORM ADMIN STATUS")
    print("=" * 60)
    
    # Check if user exists
    user = conn.execute(text("""
        SELECT id, email, customer_id, is_superuser 
        FROM users 
        WHERE email = :email
    """), {'email': TENANT_USER_EMAIL}).fetchone()
    
    if not user:
        print(f"⚠️  User {TENANT_USER_EMAIL} not found. Skipping cleanup.")
        return
    
    user_id = user[0]
    current_customer_id = user[2]
    is_superuser = user[3]
    
    print(f"Found user: ID={user_id}, customer_id={current_customer_id}, is_superuser={is_superuser}")
    
    # Step 1: Remove from platform_admins table
    print(f"\n[Step 1/4] Removing {TENANT_USER_EMAIL} from platform_admins...")
    result = conn.execute(text("""
        DELETE FROM platform_admins WHERE user_id = :user_id
    """), {'user_id': user_id})
    if result.rowcount > 0:
        print(f"  ✓ Removed from platform_admins table")
    else:
        print(f"  ℹ️  Not in platform_admins table (already clean)")
    
    # Step 2: Set is_superuser=false
    print(f"\n[Step 2/4] Setting is_superuser=false...")
    conn.execute(text("""
        UPDATE users 
        SET is_superuser = false, updated_at = NOW()
        WHERE id = :user_id AND is_superuser = true
    """), {'user_id': user_id})
    print(f"  ✓ Set is_superuser=false")
    
    # Step 3: Ensure customer_id is correct tenant (not 'platform')
    print(f"\n[Step 3/4] Ensuring customer_id is '{TENANT_CUSTOMER_ID}'...")
    if current_customer_id != TENANT_CUSTOMER_ID:
        conn.execute(text("""
            UPDATE users 
            SET customer_id = :customer_id, updated_at = NOW()
            WHERE id = :user_id
        """), {'user_id': user_id, 'customer_id': TENANT_CUSTOMER_ID})
        print(f"  ✓ Changed customer_id from '{current_customer_id}' to '{TENANT_CUSTOMER_ID}'")
    else:
        print(f"  ℹ️  customer_id already set to '{TENANT_CUSTOMER_ID}'")
    
    # Step 4: Ensure user has 'admin' role for the tenant
    print(f"\n[Step 4/4] Ensuring user has 'admin' role for '{TENANT_CUSTOMER_ID}'...")
    
    # Get the admin role for this tenant
    admin_role = conn.execute(text("""
        SELECT id FROM roles 
        WHERE name = 'admin' AND customer_id = :customer_id
    """), {'customer_id': TENANT_CUSTOMER_ID}).fetchone()
    
    if admin_role:
        admin_role_id = admin_role[0]
        # Assign role if not already assigned
        conn.execute(text("""
            INSERT INTO user_roles (user_id, role_id, assigned_at, active)
            VALUES (:user_id, :role_id, NOW(), true)
            ON CONFLICT (user_id, role_id) DO UPDATE SET active = true
        """), {'user_id': user_id, 'role_id': admin_role_id})
        print(f"  ✓ Assigned 'admin' role (ID: {admin_role_id}) for '{TENANT_CUSTOMER_ID}'")
    else:
        print(f"  ⚠️  'admin' role not found for '{TENANT_CUSTOMER_ID}'. Role will be created when tenant is set up.")
    
    # Remove any platform_admin role assignment
    print(f"\n[Cleanup] Removing any platform_admin role assignments...")
    result = conn.execute(text("""
        DELETE FROM user_roles 
        WHERE user_id = :user_id 
        AND role_id IN (SELECT id FROM roles WHERE name = 'platform_admin')
    """), {'user_id': user_id})
    if result.rowcount > 0:
        print(f"  ✓ Removed platform_admin role assignment")
    else:
        print(f"  ℹ️  No platform_admin role to remove")
    
    # Verify final state
    final_user = conn.execute(text("""
        SELECT u.id, u.email, u.customer_id, u.is_superuser,
               EXISTS(SELECT 1 FROM platform_admins pa WHERE pa.user_id = u.id) as is_platform_admin,
               ARRAY_AGG(r.name) as roles
        FROM users u
        LEFT JOIN user_roles ur ON u.id = ur.user_id AND ur.active = true
        LEFT JOIN roles r ON ur.role_id = r.id
        WHERE u.email = :email
        GROUP BY u.id
    """), {'email': TENANT_USER_EMAIL}).fetchone()
    
    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE")
    print("=" * 60)
    print(f"""
Final state for {TENANT_USER_EMAIL}:
  - customer_id: {final_user[2]}
  - is_superuser: {final_user[3]}
  - in platform_admins: {final_user[4]}
  - roles: {final_user[5]}

{TENANT_USER_EMAIL} is now a TENANT ADMIN for '{TENANT_CUSTOMER_ID}' only.
They can manage users, connections, settings within Caylent.
They CANNOT access platform admin features.
""")


def downgrade() -> None:
    """Restore scott@eliza.com platform admin status (not recommended)."""
    print("WARNING: Restoring platform admin status is not recommended.")
    print("If you need to make scott@eliza.com a platform admin, do it manually.")
    pass

