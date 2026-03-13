#!/usr/bin/env python3
"""
Create HR users with hr_user role and TALENT section permissions.

This script:
1. Creates talent-related permissions if they don't exist
2. Creates the hr_user role with those permissions
3. Creates three HR users and assigns them the hr_user role
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from src.models.database import get_db, init_database
from src.models.auth import Role, Permission, User
from src.models.customer import Customer


def create_talent_permissions(db: Session) -> dict:
    """Create all TALENT section permissions and return a mapping."""
    permissions_data = [
        # Talent Intelligence permissions
        ("talent:read", "talent", "read", "View talent analyses and results"),
        ("talent:analyze", "talent", "analyze", "Run talent intelligence analyses"),
        ("talent:manage", "talent", "manage", "Manage talent data and configurations"),
        ("talent:history", "talent", "history", "View analysis history"),
        
        # Data Connectors permissions
        ("connectors:read", "connectors", "read", "View data connector configurations"),
        ("connectors:configure", "connectors", "configure", "Create and configure data connectors"),
        ("connectors:sync", "connectors", "sync", "Trigger and manage data syncs"),
        
        # Candidate Outreach permissions
        ("outreach:read", "outreach", "read", "View candidate outreach and engagement"),
        ("outreach:manage", "outreach", "manage", "Create and manage outreach campaigns"),
        ("outreach:templates", "outreach", "templates", "Create and edit email templates"),
        
        # Wildcard for hr_user role
        ("talent:*", "talent", "*", "All talent intelligence permissions"),
        ("connectors:*", "connectors", "*", "All data connector permissions"),
        ("outreach:*", "outreach", "*", "All candidate outreach permissions"),
    ]
    
    permissions = {}
    for name, resource, action, description in permissions_data:
        # Check if permission already exists
        existing = db.query(Permission).filter(Permission.name == name).first()
        if existing:
            permissions[name] = existing
            print(f"  ✓ Permission '{name}' already exists")
            continue
            
        permission = Permission(
            name=name,
            resource=resource,
            action=action,
            description=description
        )
        db.add(permission)
        permissions[name] = permission
        print(f"  + Created permission '{name}'")
    
    db.commit()
    return permissions


def create_hr_user_role(db: Session, permissions: dict) -> Role:
    """Create hr_user role with TALENT section permissions."""
    role_name = "hr_user"
    
    # Check if role already exists
    existing_role = db.query(Role).filter(Role.name == role_name).first()
    if existing_role:
        print(f"  ✓ Role '{role_name}' already exists")
        return existing_role
    
    # Create the hr_user role
    role = Role(
        name=role_name,
        display_name="HR User",
        description="Access to all Talent Intelligence features including Data Connections, Talent Intelligence, Analysis History, Candidate Outreach, and Email Templates",
        hierarchy_level=2,  # Similar to analyst level
        is_active=True
    )
    
    # Add all talent-related permissions (using wildcards for full access)
    permission_names = [
        "talent:*",
        "connectors:*",
        "outreach:*"
    ]
    
    role_permissions = []
    for perm_name in permission_names:
        if perm_name in permissions:
            role_permissions.append(permissions[perm_name])
            print(f"    - Added permission: {perm_name}")
    
    role.permissions = role_permissions
    db.add(role)
    db.commit()
    db.refresh(role)
    
    print(f"  + Created role '{role.display_name}' with {len(role_permissions)} permissions")
    return role


def create_hr_user(db: Session, email: str, role: Role, customer_id: str = "caylent") -> User:
    """Create a single HR user with the hr_user role."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        print(f"  ⚠️  User '{email}' already exists")
        # Check if they have the role
        if role not in existing_user.roles:
            existing_user.roles.append(role)
            db.commit()
            print(f"    + Added hr_user role to existing user")
        return existing_user
    
    # Extract name from email
    name_part = email.split('@')[0]
    first_name = name_part.split('.')[0].capitalize()
    last_name = name_part.split('.')[1].capitalize() if '.' in name_part else ""
    full_name = f"{first_name} {last_name}".strip()
    username = name_part.replace('.', '_')
    
    # Create the user
    user = User(
        email=email,
        username=username,
        full_name=full_name,
        customer_id=customer_id,
        is_active=True,
        is_superuser=False
    )
    
    # Set password
    user.set_password("admin123")
    
    # Assign role
    user.roles = [role]
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    print(f"  + Created user '{email}' ({full_name})")
    return user


def main():
    """Create hr_user role and HR users."""
    print("🚀 Creating HR users with TALENT section access...\n")
    
    # Initialize database
    init_database()
    
    with next(get_db()) as db:
        # Ensure customer exists
        print("🏢 Checking customer...")
        customer = db.query(Customer).filter(Customer.customer_id == "caylent").first()
        if not customer:
            print("  ❌ Customer 'caylent' not found. Please create it first.")
            sys.exit(1)
        print(f"  ✓ Customer 'caylent' exists\n")
        
        # Create permissions
        print("📝 Creating TALENT section permissions...")
        permissions = create_talent_permissions(db)
        print(f"  ✓ Processed {len(permissions)} permissions\n")
        
        # Create hr_user role
        print("👥 Creating hr_user role...")
        hr_role = create_hr_user_role(db, permissions)
        print()
        
        # Create the three HR users
        print("👤 Creating HR users...")
        hr_emails = [
            "laura.sullivan@caylent.com",
            "lisa.cohrs@caylent.com",
            "sofia.ferrari@caylent.com"
        ]
        
        created_users = []
        for email in hr_emails:
            user = create_hr_user(db, email, hr_role, customer_id="caylent")
            created_users.append(user)
        
        print("\n🎉 HR users created successfully!\n")
        print("📋 Summary:")
        print(f"  • Role: {hr_role.display_name} ({hr_role.name})")
        print(f"  • Permissions: {len(hr_role.get_permissions())}")
        print(f"  • Users created: {len(created_users)}")
        print("\n👥 User Accounts:")
        for user in created_users:
            print(f"  • {user.email} ({user.full_name})")
        
        print("\n🔐 Login Credentials:")
        print("  Password (all users): admin123")
        print("\n📱 TALENT Section Access:")
        print("  ✓ Data Connections")
        print("  ✓ Talent Intelligence")
        print("  ✓ Analysis History")
        print("  ✓ Candidate Outreach")
        print("  ✓ Email Templates")
        print("\n⚠️  Users can login at: https://caylent-hr-intel.lhr.rocks/login")


if __name__ == "__main__":
    main()

