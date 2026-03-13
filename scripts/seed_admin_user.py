"""
Seed Admin User Script

Creates the initial admin user, customer, and super_admin role with full permissions.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import select, insert
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import init_async_database
import src.models
from src.models.auth import User, Role, Permission, user_roles, role_permissions
from src.models.customer import Customer
import bcrypt

# Admin user details
ADMIN_EMAIL = "scott@eliza.com"
ADMIN_USERNAME = "scott"
ADMIN_PASSWORD = "admin123"  # Change this after first login!
CUSTOMER_ID = "eliza"
CUSTOMER_NAME = "Eliza"

# All permissions for super_admin
ALL_PERMISSIONS = [
    # User Management
    {"name": "users:read", "description": "View users", "resource": "users", "action": "read"},
    {"name": "users:create", "description": "Create users", "resource": "users", "action": "create"},
    {"name": "users:update", "description": "Update users", "resource": "users", "action": "update"},
    {"name": "users:delete", "description": "Delete users", "resource": "users", "action": "delete"},
    
    # Role Management
    {"name": "roles:read", "description": "View roles", "resource": "roles", "action": "read"},
    {"name": "roles:create", "description": "Create roles", "resource": "roles", "action": "create"},
    {"name": "roles:update", "description": "Update roles", "resource": "roles", "action": "update"},
    {"name": "roles:delete", "description": "Delete roles", "resource": "roles", "action": "delete"},
    
    # Document Management
    {"name": "documents:read", "description": "View documents", "resource": "documents", "action": "read"},
    {"name": "documents:create", "description": "Upload documents", "resource": "documents", "action": "create"},
    {"name": "documents:update", "description": "Update documents", "resource": "documents", "action": "update"},
    {"name": "documents:delete", "description": "Delete documents", "resource": "documents", "action": "delete"},
    {"name": "documents:process", "description": "Process documents", "resource": "documents", "action": "process"},
    
    # HR Management
    {"name": "hr:read", "description": "View HR data", "resource": "hr", "action": "read"},
    {"name": "hr:create", "description": "Create HR records", "resource": "hr", "action": "create"},
    {"name": "hr:update", "description": "Update HR records", "resource": "hr", "action": "update"},
    {"name": "hr:delete", "description": "Delete HR records", "resource": "hr", "action": "delete"},
    
    # Customer Management
    {"name": "customers:read", "description": "View customers", "resource": "customers", "action": "read"},
    {"name": "customers:create", "description": "Create customers", "resource": "customers", "action": "create"},
    {"name": "customers:update", "description": "Update customers", "resource": "customers", "action": "update"},
    {"name": "customers:delete", "description": "Delete customers", "resource": "customers", "action": "delete"},
    
    # System Administration
    {"name": "system:admin", "description": "Full system administration", "resource": "system", "action": "admin"},
    {"name": "audit:read", "description": "View audit logs", "resource": "audit", "action": "read"},
    
    # Platform Administration
    {"name": "platform:admin", "description": "Platform administration access", "resource": "platform", "action": "admin"},
    
    # AI Assistant Access (required for SOW, HR Assistant, etc.)
    {"name": "assistant:access", "description": "Access AI Assistant features", "resource": "assistant", "action": "access"},
    
    # Workspace Management
    # TODO: Add workspaces:read for granular read vs write control
    {"name": "workspaces:write", "description": "Create and modify workspaces", "resource": "workspaces", "action": "write"},

    # Content Writer
    {"name": "content_writer:read", "description": "View content writer runs and drafts", "resource": "content_writer", "action": "read"},
    {"name": "content_writer:write", "description": "Create and edit content", "resource": "content_writer", "action": "write"},
]


async def create_admin_user():
    """Create admin user, customer, and super_admin role."""

    print("🔧 Starting admin user setup...")
    print(f"   Email: {ADMIN_EMAIL}")
    print(f"   Username: {ADMIN_USERNAME}")
    print(f"   Customer: {CUSTOMER_NAME} ({CUSTOMER_ID})")
    print()

    try:
        # Initialize async database
        init_async_database()
        AsyncSessionLocal = src.models.AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            # 1. Create Customer
            print("📦 Creating customer...")

            result = await session.execute(
                select(Customer).where(Customer.customer_id == CUSTOMER_ID)
            )
            customer = result.scalar_one_or_none()

            if customer:
                print(f"ℹ️  Customer '{CUSTOMER_ID}' already exists, skipping creation")
            else:
                customer = Customer(
                    customer_id=CUSTOMER_ID,
                    name=CUSTOMER_NAME,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                session.add(customer)
                await session.flush()
                print(f"✅ Created customer: {CUSTOMER_NAME}")

            
            # 2. Create Permissions
            print("\n🔐 Creating permissions...")
            permission_objects = []
            for perm_data in ALL_PERMISSIONS:
                # Check if permission already exists
                result = await session.execute(
                    select(Permission).where(Permission.name == perm_data["name"])
                )
                existing_perm = result.scalar_one_or_none()
                
                if existing_perm:
                    permission_objects.append(existing_perm)
                else:
                    perm = Permission(**perm_data)
                    session.add(perm)
                    permission_objects.append(perm)
            
            await session.flush()
            print(f"✅ Created/verified {len(permission_objects)} permissions")
            
            # 3. Create super_admin Role
            print("\n👑 Creating super_admin role...")
            result = await session.execute(
                select(Role).where(Role.name == "super_admin")
            )
            super_admin_role = result.scalar_one_or_none()
            
            if not super_admin_role:
                super_admin_role = Role(
                    name="super_admin",
                    display_name="Super Administrator",
                    description="Super Administrator with full system access",
                    is_active=True
                )
                session.add(super_admin_role)
                await session.flush()
            print(f"✅ Created super_admin role")
            
            # 4. Assign all permissions to super_admin role
            print("\n🔗 Assigning permissions to super_admin role...")
            for perm in permission_objects:
                # Check if role-permission already exists
                result = await session.execute(
                    select(role_permissions).where(
                        role_permissions.c.role_id == super_admin_role.id,
                        role_permissions.c.permission_id == perm.id
                    )
                )
                existing_rp = result.first()

                if not existing_rp:
                    await session.execute(
                        insert(role_permissions).values(
                            role_id=super_admin_role.id,
                            permission_id=perm.id
                        )
                    )

            await session.flush()
            print(f"✅ Assigned {len(permission_objects)} permissions to super_admin")
            
            # 5. Create Admin User
            print("\n👤 Creating admin user...")
            result = await session.execute(
                select(User).where(User.email == ADMIN_EMAIL)
            )
            admin_user = result.scalar_one_or_none()
            
            if admin_user:
                print(f"⚠️  User {ADMIN_EMAIL} already exists, skipping creation")
            else:
                # Hash password using bcrypt
                password_bytes = ADMIN_PASSWORD.encode('utf-8')
                salt = bcrypt.gensalt()
                hashed_password = bcrypt.hashpw(password_bytes, salt).decode('utf-8')

                admin_user = User(
                    email=ADMIN_EMAIL,
                    username=ADMIN_USERNAME,
                    hashed_password=hashed_password,
                    customer_id=CUSTOMER_ID,
                    is_active=True,
                    is_superuser=True
                )
                session.add(admin_user)
                await session.flush()
                print(f"✅ Created admin user: {ADMIN_USERNAME}")
            
            # 6. Assign super_admin role to user
            print("\n🎭 Assigning super_admin role to user...")
            result = await session.execute(
                select(user_roles).where(
                    user_roles.c.user_id == admin_user.id,
                    user_roles.c.role_id == super_admin_role.id
                )
            )
            existing_ur = result.first()

            if not existing_ur:
                await session.execute(
                    insert(user_roles).values(
                        user_id=admin_user.id,
                        role_id=super_admin_role.id
                    )
                )
            print(f"✅ Assigned super_admin role to {ADMIN_USERNAME}")
            
            # Commit all changes
            await session.commit()
            
            print("\n" + "="*60)
            print("✅ Admin user setup completed successfully!")
            print("="*60)
            print(f"\n📧 Email: {ADMIN_EMAIL}")
            print(f"👤 Username: {ADMIN_USERNAME}")
            print(f"🔑 Password: {ADMIN_PASSWORD}")
            print(f"🏢 Customer: {CUSTOMER_NAME} ({CUSTOMER_ID})")
            print(f"👑 Role: super_admin")
            print(f"🔐 Permissions: {len(permission_objects)} (full access)")
            print("\n⚠️  IMPORTANT: Change the default password after first login!")
            print()
            
    except Exception as e:
        print(f"\n❌ Error creating admin user: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(create_admin_user())

