#!/usr/bin/env python3
"""
Initialize RBAC system with default roles and permissions.

This script creates the default roles and permissions as defined in the
SINGLE_TENANT_RBAC_SPECIFICATION.md document.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.models.database import get_db, init_database
from src.models.auth import Role, Permission, User
from src.services.auth_service import auth_service
import asyncio
from src.models.customer import Customer


def create_permissions(db: Session) -> dict:
    """Create all permissions and return a mapping of name to Permission object."""
    permissions_data = [
        # Document permissions
        ("documents:read", "documents", "read", "View documents and metadata"),
        ("documents:upload", "documents", "upload", "Upload new documents"),
        ("documents:edit", "documents", "edit", "Modify document metadata and content"),
        ("documents:delete", "documents", "delete", "Remove documents from system"),
        ("documents:share", "documents", "share", "Share documents with other users"),
        
        # Search permissions
        ("search:execute", "search", "execute", "Perform basic document searches"),
        ("search:advanced", "search", "advanced", "Use advanced search features and filters"),
        ("search:export", "search", "export", "Export search results and reports"),
        
        # User management permissions
        ("users:read", "users", "read", "View user profiles and lists"),
        ("users:create", "users", "create", "Create new user accounts"),
        ("users:edit", "users", "edit", "Modify user profiles and roles"),
        ("users:delete", "users", "delete", "Remove user accounts"),
        ("users:invite", "users", "invite", "Send user invitations"),
        
        # AI model permissions
        ("models:read", "models", "read", "View AI model configurations and status"),
        ("models:configure", "models", "configure", "Modify AI model settings"),
        ("models:test", "models", "test", "Execute model tests and validations"),
        
        # System permissions
        ("system:admin", "system", "admin", "Access system administration features"),
        ("system:logs", "system", "logs", "View system logs and audit trails"),
        ("system:health", "system", "health", "Monitor system health and performance"),
        ("system:backup", "system", "backup", "Manage system backups and recovery"),
        
        # Wildcard permissions for super admin
        ("documents:*", "documents", "*", "All document permissions"),
        ("search:*", "search", "*", "All search permissions"),
        ("users:*", "users", "*", "All user management permissions"),
        ("models:*", "models", "*", "All AI model permissions"),
        ("system:*", "system", "*", "All system permissions"),
    ]
    
    permissions = {}
    for name, resource, action, description in permissions_data:
        # Check if permission already exists
        existing = db.query(Permission).filter(Permission.name == name).first()
        if existing:
            permissions[name] = existing
            continue
            
        permission = Permission(
            name=name,
            resource=resource,
            action=action,
            description=description
        )
        db.add(permission)
        permissions[name] = permission
    
    db.commit()
    return permissions


def create_roles(db: Session, permissions: dict) -> dict:
    """Create all roles with their permissions."""
    roles_data = [
        ("viewer", "Viewer", "Read-only access to documents and reports", 1, [
            "documents:read",
            "search:execute"
        ]),
        ("analyst", "Analyst", "Document analysis and AI model usage", 2, [
            "documents:read",
            "documents:upload",
            "documents:edit",  # Own documents only (handled in business logic)
            "search:execute",
            "search:advanced",
            "search:export",
            "models:read"
        ]),
        ("manager", "Manager", "Team oversight and advanced document management", 3, [
            "documents:read",
            "documents:upload",
            "documents:edit",
            "documents:delete",
            "search:execute",
            "search:advanced",
            "search:export",
            "users:read",
            "models:read",
            "models:test",
            "system:health"
        ]),
        ("admin", "Admin", "System configuration and user management", 4, [
            "documents:read",
            "documents:upload",
            "documents:edit",
            "documents:delete",
            "search:execute",
            "search:advanced",
            "search:export",
            "users:read",
            "users:create",
            "users:edit",
            "users:delete",
            "models:read",
            "models:configure",
            "models:test",
            "system:logs",
            "system:health"
        ]),
        ("super_admin", "Super Admin", "Full system access and user management", 5, [
            "documents:*",
            "search:*",
            "users:*",
            "models:*",
            "system:*"
        ])
    ]
    
    roles = {}
    for name, display_name, description, level, permission_names in roles_data:
        # Check if role already exists
        existing = db.query(Role).filter(Role.name == name).first()
        if existing:
            roles[name] = existing
            continue
            
        role = Role(
            name=name,
            display_name=display_name,
            description=description,
            hierarchy_level=level
        )
        
        # Add permissions to role
        role_permissions = []
        for perm_name in permission_names:
            if perm_name in permissions:
                role_permissions.append(permissions[perm_name])
        
        role.permissions = role_permissions
        db.add(role)
        roles[name] = role
    
    db.commit()
    return roles


async def create_default_admin_user(db: Session, roles: dict):
    """Create default admin user if none exists."""
    # Check if any admin users exist
    admin_role = roles.get("super_admin")
    if not admin_role:
        print("❌ Super admin role not found")
        return
    
    existing_admin = db.query(User).join(User.roles).filter(Role.name == "super_admin").first()
    if existing_admin:
        print(f"✅ Super admin user already exists: {existing_admin.email}")
        return
    
    # Create default admin user
    try:
        admin_user = User(
            email="admin@ai-enablement.local",
            username="system_admin",
            full_name="System Administrator",
            customer_id="eliza",
            is_superuser=True,
            is_active=True,
        )
        admin_user.set_password("admin123")
        admin_user.roles = [admin_role]
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"✅ Created default super admin user: {admin_user.email}")
        print("⚠️  Default password is 'admin123' - please change on first login")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to create default admin user: {e}")


def main():
    """Initialize RBAC system."""
    print("🚀 Initializing RBAC system...")
    
    # Initialize database
    init_database()
    
    with next(get_db()) as db:
        # Ensure default customer exists
        print("🏢 Ensuring default customer exists...")
        customer = db.query(Customer).filter(Customer.customer_id == "eliza").first()
        if not customer:
            customer = Customer(
                customer_id="eliza",
                name="Eliza Platform",
                display_name="Eliza Platform",
                contact_email="admin@ai-enablement.local",
                subscription_tier="enterprise",
                is_active=True
            )
            db.add(customer)
            db.commit()
            db.refresh(customer)
            print("✅ Created default customer 'eliza'")
        else:
            print("✅ Default customer 'eliza' already exists")
        
        print("📝 Creating permissions...")
        permissions = create_permissions(db)
        print(f"✅ Created {len(permissions)} permissions")
        
        print("👥 Creating roles...")
        roles = create_roles(db, permissions)
        print(f"✅ Created {len(roles)} roles")
        
        print("👤 Creating default admin user...")
        asyncio.run(create_default_admin_user(db, roles))
        
        print("\n🎉 RBAC system initialized successfully!")
        print("\n📋 Created Roles:")
        for role_name, role in roles.items():
            perm_count = len(role.get_permissions())
            print(f"  • {role.display_name} ({role_name}): {perm_count} permissions")
        
        print("\n🔐 Default Login Credentials:")
        print("  Email: admin@ai-enablement.local")
        print("  Password: admin123")
        print("  ⚠️  Please change the password on first login!")


if __name__ == "__main__":
    main()
