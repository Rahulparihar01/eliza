#!/usr/bin/env python3
"""
Platform & Tenant Initialization Script

This script initializes a fresh installation with:
1. Platform tenant (special tenant for platform-level resources)
2. Platform admin user (belongs to platform tenant, manages all tenants)
3. Optionally creates an additional customer tenant

The platform tenant is a special reserved tenant that:
- Owns platform-level resources (AI providers, features, etc.)
- The platform admin user belongs to this tenant
- Is always created with customer_id = "platform"

Usage:
    python scripts/init_tenant.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection URL (required)
    ADMIN_EMAIL: Platform admin email (REQUIRED)
    ADMIN_PASSWORD: Platform admin password (REQUIRED)
    CUSTOMER_ID: Optional additional customer tenant to create (e.g., 'caylent')
    CUSTOMER_NAME: Display name for additional customer tenant

Configuration Priority:
    1. Environment variables (highest priority)
    2. Settings class (src/core/config.py)
    3. Hardcoded defaults (lowest priority)

The script is idempotent - safe to run multiple times.
"""

import os
import sys
from datetime import datetime

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Platform tenant constants
PLATFORM_TENANT_ID = "platform"
PLATFORM_TENANT_NAME = "Eliza Platform"


def get_database_url():
    """Get DATABASE_URL from environment or settings."""
    # First try direct environment variable
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url
    
    # Try loading from settings
    try:
        from src.core.config import get_settings
        settings = get_settings()
        return settings.database_url
    except Exception as e:
        print(f"⚠️  Could not load settings: {e}")
        return None


def create_tenant(db, text, customer_id: str, customer_name: str, subscription_tier: str = "enterprise"):
    """Create a tenant/customer if it doesn't exist."""
    db.execute(text("""
        INSERT INTO customers (customer_id, name, display_name, is_active, subscription_tier, created_at, updated_at)
        VALUES (:customer_id, :name, :display_name, true, :subscription_tier, NOW(), NOW())
        ON CONFLICT (customer_id) DO UPDATE SET
            name = EXCLUDED.name,
            display_name = EXCLUDED.display_name,
            is_active = true
    """), {
        "customer_id": customer_id, 
        "name": customer_name, 
        "display_name": customer_name,
        "subscription_tier": subscription_tier
    })
    db.commit()


def ensure_platform_admin_role(db, text, customer_id: str):
    """Ensure platform_admin role exists for a tenant."""
    role_check = db.execute(text("""
        SELECT id, name FROM roles WHERE customer_id = :customer_id
    """), {"customer_id": customer_id}).fetchall()
    
    if not role_check:
        print(f"  ⚠️  No roles found for tenant '{customer_id}', creating fallback platform_admin role...")
        
        # Create minimal platform_admin role as fallback
        db.execute(text("""
            INSERT INTO roles (name, display_name, description, is_system_role, is_active, customer_id, created_at, updated_at)
            VALUES ('platform_admin', 'Platform Administrator', 'Full system access', true, true, :customer_id, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """), {"customer_id": customer_id})
        
        # Assign platform:admin permission if it exists
        db.execute(text("""
            INSERT INTO role_permissions (role_id, permission_id, granted_at)
            SELECT r.id, p.id, NOW()
            FROM roles r, permissions p
            WHERE r.name = 'platform_admin' AND r.customer_id = :customer_id AND p.name = 'platform:admin'
            ON CONFLICT DO NOTHING
        """), {"customer_id": customer_id})
        db.commit()
        return True
    else:
        role_names = [r[1] for r in role_check]
        print(f"  ✓ Found {len(role_check)} roles: {', '.join(role_names)}")
        return False


def ensure_default_assignable_roles(db, text, customer_id: str):
    """Ensure baseline tenant roles exist for invites/admin UX."""
    default_roles = [
        ("admin", "Admin", "Full administrative access within this organization"),
        ("editor", "Editor", "Can create and modify content"),
        ("viewer", "Viewer", "Read-only access to view content"),
    ]

    created_count = 0
    for role_name, display_name, description in default_roles:
        existing = db.execute(
            text(
                """
                SELECT id
                FROM roles
                WHERE customer_id = :customer_id
                  AND LOWER(name) = LOWER(:role_name)
                LIMIT 1
                """
            ),
            {"customer_id": customer_id, "role_name": role_name},
        ).fetchone()

        if existing:
            continue

        db.execute(
            text(
                """
                INSERT INTO roles (
                    name, display_name, description, is_system_role, is_active,
                    customer_id, created_at, updated_at
                )
                VALUES (
                    :role_name, :display_name, :description, true, true,
                    :customer_id, NOW(), NOW()
                )
                """
            ),
            {
                "role_name": role_name,
                "display_name": display_name,
                "description": description,
                "customer_id": customer_id,
            },
        )
        created_count += 1

    if created_count > 0:
        db.commit()
        print(f"  ✓ Created {created_count} default assignable roles (admin/editor/viewer)")
    else:
        print("  ✓ Default assignable roles already present")


def main():
    """Main initialization function."""
    print("=" * 60)
    print("Eliza Platform - Platform & Tenant Initialization")
    print("=" * 60)
    print()
    
    # Get database URL
    database_url = get_database_url()
    if not database_url:
        print("✗ DATABASE_URL not found in environment or settings")
        print("  Set DATABASE_URL environment variable and try again")
        sys.exit(1)
    
    # Mask password in URL for display
    display_url = database_url
    if '@' in database_url:
        parts = database_url.split('@')
        display_url = parts[0].rsplit(':', 1)[0] + ':****@' + parts[1]
    print(f"Database: {display_url}")
    
    # Import SQLAlchemy components
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        print("✗ SQLAlchemy not installed")
        sys.exit(1)
    
    # Create engine and session
    try:
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()
        
        # Test connection
        db.execute(text("SELECT 1"))
        print("✓ Database connection successful")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Configuration - load from Settings for consistency, with env var overrides
    try:
        from src.core.config import get_settings
        settings = get_settings()
        additional_customer_id = os.environ.get("CUSTOMER_ID") or settings.customer_id
        additional_customer_name = os.environ.get("CUSTOMER_NAME") or settings.customer_name
        admin_email = os.environ.get("ADMIN_EMAIL") or getattr(settings, 'admin_email', None)
        admin_password = os.environ.get("ADMIN_PASSWORD") or getattr(settings, 'admin_password', None)
    except Exception as e:
        print(f"⚠️  Could not load settings, using env vars: {e}")
        additional_customer_id = os.environ.get("CUSTOMER_ID")
        additional_customer_name = os.environ.get("CUSTOMER_NAME")
        admin_email = os.environ.get("ADMIN_EMAIL")
        admin_password = os.environ.get("ADMIN_PASSWORD")
    
    # Validate required fields
    if not admin_email:
        print("✗ ADMIN_EMAIL environment variable is required")
        print("  Set ADMIN_EMAIL to the platform admin's email address")
        sys.exit(1)
    
    if not admin_password:
        print("✗ ADMIN_PASSWORD environment variable is required")
        print("  Set ADMIN_PASSWORD to a secure password for the platform admin")
        sys.exit(1)
    
    print()
    print("Configuration:")
    print(f"  Platform Tenant: {PLATFORM_TENANT_ID} ({PLATFORM_TENANT_NAME})")
    print(f"  Platform Admin Email: {admin_email}")
    print(f"  Platform Admin Password: {'*' * len(admin_password)}")
    if additional_customer_id and additional_customer_id != PLATFORM_TENANT_ID:
        print(f"  Additional Tenant: {additional_customer_id} ({additional_customer_name or additional_customer_id})")
    print()
    
    try:
        # ============================================================
        # STEP 1: Create Platform Tenant (always)
        # ============================================================
        print("STEP 1: Creating Platform Tenant...")
        create_tenant(db, text, PLATFORM_TENANT_ID, PLATFORM_TENANT_NAME, "platform")
        print(f"  ✓ Platform tenant '{PLATFORM_TENANT_ID}' ready")
        
        # Ensure roles exist for platform tenant
        print("  Checking platform tenant roles...")
        ensure_platform_admin_role(db, text, PLATFORM_TENANT_ID)
        ensure_default_assignable_roles(db, text, PLATFORM_TENANT_ID)
        
        # ============================================================
        # STEP 2: Create Platform Admin User (under platform tenant)
        # ============================================================
        print()
        print("STEP 2: Creating Platform Admin User...")
        import bcrypt
        password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        username = admin_email.split('@')[0]
        
        db.execute(text("""
            INSERT INTO users (
                email, username, full_name, hashed_password, 
                is_active, is_superuser, customer_id, 
                failed_login_attempts, locked_until,
                created_at, updated_at
            )
            VALUES (
                :email, :username, :full_name, :hashed_password,
                true, true, :customer_id,
                0, NULL,
                NOW(), NOW()
            )
            ON CONFLICT (email) DO UPDATE SET
                hashed_password = EXCLUDED.hashed_password,
                is_active = true,
                is_superuser = true,
                customer_id = :customer_id,
                failed_login_attempts = 0,
                locked_until = NULL,
                updated_at = NOW()
        """), {
            "email": admin_email,
            "username": username,
            "full_name": "Platform Admin",
            "hashed_password": password_hash,
            "customer_id": PLATFORM_TENANT_ID,  # Platform admin belongs to platform tenant
        })
        db.commit()
        print(f"  ✓ Platform admin user '{admin_email}' created (tenant: {PLATFORM_TENANT_ID})")
        
        # ============================================================
        # STEP 3: Assign platform_admin role
        # ============================================================
        print()
        print("STEP 3: Assigning Platform Admin Role...")
        db.execute(text("""
            INSERT INTO user_roles (user_id, role_id, assigned_at, active)
            SELECT u.id, r.id, NOW(), true
            FROM users u, roles r
            WHERE u.email = :email AND r.name = 'platform_admin' AND r.customer_id = :customer_id
            ON CONFLICT DO NOTHING
        """), {"email": admin_email, "customer_id": PLATFORM_TENANT_ID})
        db.commit()
        print("  ✓ Platform admin role assigned")
        
        # ============================================================
        # STEP 4: Create tenant membership for platform tenant
        # ============================================================
        print()
        print("STEP 4: Creating Platform Tenant Membership...")
        db.execute(text("""
            INSERT INTO user_tenant_memberships (user_id, customer_id, is_default, first_login_completed, created_at)
            SELECT u.id, :customer_id, true, true, NOW()
            FROM users u
            WHERE u.email = :email
            ON CONFLICT (user_id, customer_id) DO NOTHING
        """), {"email": admin_email, "customer_id": PLATFORM_TENANT_ID})
        db.commit()
        print(f"  ✓ Platform tenant membership created")
        
        # ============================================================
        # STEP 5: Add to platform_admins table
        # ============================================================
        print()
        print("STEP 5: Adding to Platform Admins Table...")
        db.execute(text("""
            INSERT INTO platform_admins (
                user_id, admin_level, 
                can_create_tenants, can_allocate_features, 
                can_manage_platform_admins, can_impersonate, 
                is_active, created_at, updated_at
            )
            SELECT u.id, 'super_admin', true, true, true, true, true, NOW(), NOW()
            FROM users u
            WHERE u.email = :email
            ON CONFLICT (user_id) DO UPDATE SET
                admin_level = 'super_admin',
                can_create_tenants = true,
                can_allocate_features = true,
                can_manage_platform_admins = true,
                can_impersonate = true,
                is_active = true,
                updated_at = NOW()
        """), {"email": admin_email})
        db.commit()
        print("  ✓ Platform admin record created with super_admin privileges")
        
        # ============================================================
        # STEP 6: Create Additional Customer Tenant (if specified)
        # ============================================================
        if additional_customer_id and additional_customer_id != PLATFORM_TENANT_ID and additional_customer_id != "default":
            print()
            print(f"STEP 6: Creating Additional Customer Tenant '{additional_customer_id}'...")
            tenant_name = additional_customer_name or additional_customer_id.title()
            create_tenant(db, text, additional_customer_id, tenant_name, "enterprise")
            print(f"  ✓ Customer tenant '{additional_customer_id}' ready")
            
            # Ensure roles exist
            print(f"  Checking tenant roles...")
            ensure_platform_admin_role(db, text, additional_customer_id)
            ensure_default_assignable_roles(db, text, additional_customer_id)
            
            # Also give platform admin access to this tenant
            print(f"  Adding platform admin membership to '{additional_customer_id}'...")
            db.execute(text("""
                INSERT INTO user_tenant_memberships (user_id, customer_id, is_default, first_login_completed, created_at)
                SELECT u.id, :customer_id, false, true, NOW()
                FROM users u
                WHERE u.email = :email
                ON CONFLICT (user_id, customer_id) DO NOTHING
            """), {"email": admin_email, "customer_id": additional_customer_id})
            db.commit()
            print(f"  ✓ Platform admin can now access tenant '{additional_customer_id}'")
        
        # ============================================================
        # VERIFICATION
        # ============================================================
        print()
        print("=" * 60)
        print("Verifying Setup...")
        print("=" * 60)
        
        result = db.execute(text("""
            SELECT u.id, u.email, u.is_active, u.is_superuser, u.customer_id, c.name as customer_name
            FROM users u
            JOIN customers c ON u.customer_id = c.customer_id
            WHERE u.email = :email
        """), {"email": admin_email}).fetchone()
        
        # Check platform_admins entry
        pa_result = db.execute(text("""
            SELECT pa.admin_level, pa.is_active
            FROM platform_admins pa
            JOIN users u ON pa.user_id = u.id
            WHERE u.email = :email
        """), {"email": admin_email}).fetchone()
        
        # Check tenant memberships
        memberships = db.execute(text("""
            SELECT utm.customer_id, utm.is_default
            FROM user_tenant_memberships utm
            JOIN users u ON utm.user_id = u.id
            WHERE u.email = :email
        """), {"email": admin_email}).fetchall()
        
        if result:
            print()
            print("✅ Platform Admin User:")
            print(f"   ID: {result[0]}")
            print(f"   Email: {result[1]}")
            print(f"   Active: {result[2]}")
            print(f"   Superuser: {result[3]}")
            print(f"   Home Tenant: {result[4]} ({result[5]})")
            
            if pa_result:
                print()
                print("✅ Platform Admin Privileges:")
                print(f"   Admin Level: {pa_result[0]}")
                print(f"   Active: {pa_result[1]}")
            
            if memberships:
                print()
                print("✅ Tenant Memberships:")
                for m in memberships:
                    default_marker = " (default)" if m[1] else ""
                    print(f"   - {m[0]}{default_marker}")
            
            print()
            print("=" * 60)
            print("🎉 INITIALIZATION COMPLETE!")
            print("=" * 60)
            print()
            print("You can now log in with:")
            print(f"  Email: {admin_email}")
            print(f"  Password: {admin_password}")
            print()
            print("⚠️  IMPORTANT: Change the admin password after first login!")
            print()
            print("The platform admin can:")
            print("  - Manage all tenants from the Platform Admin panel")
            print("  - Create and configure AI providers (owned by 'platform' tenant)")
            print("  - Allocate features to customer tenants")
            print("  - Create additional tenant admins")
            print()
        else:
            print("⚠️  User created but verification failed")
        
    except Exception as e:
        print(f"✗ Error during initialization: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
