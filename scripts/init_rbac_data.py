#!/usr/bin/env python3
"""
Initialize RBAC system with default roles, permissions, and admin user
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.core.config import get_settings
from src.models.auth import User, Role, Permission, user_roles, role_permissions
from src.services.auth_service import AuthService

async def init_rbac_system():
    """Initialize the RBAC system with default data"""
    settings = get_settings()
    
    # Create database engine
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    auth_service = AuthService()
    
    try:
        print("🚀 Initializing RBAC system...")
        
        # Create default permissions
        permissions_data = [
            # AI Assistant permissions
            ("assistant:access", "assistant", "access", "Access AI Assistant features"),
            
            # Document permissions
            ("documents:create", "documents", "create", "Create new documents"),
            ("documents:read", "documents", "read", "View documents"),
            ("documents:edit", "documents", "edit", "Edit documents"),
            ("documents:delete", "documents", "delete", "Delete documents"),
            ("documents:upload", "documents", "upload", "Upload documents"),
            
            # Search permissions
            ("search:execute", "search", "execute", "Execute searches"),
            ("search:advanced", "search", "advanced", "Use advanced search features"),
            
            # Model permissions
            ("models:read", "models", "read", "View AI models"),
            ("models:configure", "models", "configure", "Configure AI models"),
            ("models:manage", "models", "manage", "Manage AI models"),
            
            # User permissions
            ("users:read", "users", "read", "View users"),
            ("users:create", "users", "create", "Create users"),
            ("users:edit", "users", "edit", "Edit users"),
            ("users:delete", "users", "delete", "Delete users"),
            ("users:manage_roles", "users", "manage_roles", "Manage user roles"),
            
            # System permissions
            ("system:health", "system", "health", "View system health"),
            ("system:logs", "system", "logs", "View system logs"),
            ("system:config", "system", "config", "Configure system settings"),
            ("system:admin", "system", "admin", "Full system administration"),
            
            # Analytics permissions
            ("analytics:read", "analytics", "read", "View analytics"),
            ("analytics:export", "analytics", "export", "Export analytics data"),
            
            # Business Intelligence permissions
            ("bi:read", "business_intelligence", "read", "View BI questions and answers"),
            ("bi:write", "business_intelligence", "write", "Submit BI questions"),
            ("bi:admin", "business_intelligence", "admin", "Manage BI system"),
            
            # HR Data Access permissions (company-scoped)
            ("hr:read:company:*", "hr_data", "read", "Read HR data from ALL companies (wildcard)"),
            ("hr:read:company:caylent", "hr_data", "read", "Read HR data from Caylent"),
            ("hr:read:company:eliza", "hr_data", "read", "Read HR data from Eliza"),
            
            # Settings permissions
            ("settings:read", "settings", "read", "View system settings"),
            ("settings:write", "settings", "write", "Modify system settings"),

            # Tenant theme permissions
            ("theme:write", "theme", "write", "Update tenant theme/branding settings"),
            
            # Data Analyst permissions
            ("data_analyst:read", "data_analyst", "read", "View data analyst questions and results"),
            ("data_analyst:write", "data_analyst", "write", "Submit data analyst questions"),
            ("data_analyst:admin", "data_analyst", "admin", "Manage data analyst system"),
            
            # Content Writer permissions
            ("content_writer:read", "content_writer", "read", "View content writer projects and content"),
            ("content_writer:write", "content_writer", "write", "Create and edit content writer projects"),
            
            # Adoption Dashboard permissions
            ("adoption:view_dashboard", "adoption", "view_dashboard", "Access the adoption dashboard UI"),
            ("adoption:read:company:*", "adoption", "read", "View adoption metrics for ALL companies (wildcard)"),
            ("adoption:admin:company:*", "adoption", "admin", "Configure adoption data sources for ALL companies"),
            ("adoption:manage_sharing", "adoption", "manage_sharing", "Share my tenant's adoption data with other tenants"),
            ("adoption:manage_sync", "adoption", "manage_sync", "Trigger manual adoption data syncs and configure sync settings"),
            ("adoption:manage_jobs", "adoption", "manage_jobs", "View, trigger, and edit scheduled jobs from the Job Scheduler"),
            
            # Workspace permissions
            # TODO: Add workspaces:read for granular read vs write control
            ("workspaces:write", "workspaces", "write", "Create and modify workspaces"),
        ]
        
        print("📋 Creating permissions...")
        permissions = {}
        for name, resource, action, description in permissions_data:
            permission = db.query(Permission).filter(Permission.name == name).first()
            if not permission:
                permission = Permission(
                    name=name,
                    resource=resource,
                    action=action,
                    description=description
                )
                db.add(permission)
                db.flush()
                print(f"  ✅ Created permission: {name}")
            else:
                print(f"  ⏭️  Permission already exists: {name}")
            permissions[name] = permission
        
        # Create default roles
        roles_data = [
            ("super_admin", "Super Administrator", "Full system access with all permissions", None, 1),
            ("admin", "Administrator", "Administrative access to most system functions", None, 2),
            ("manager", "Manager", "Management access to documents and users", None, 3),
            ("analyst", "Analyst", "Analysis and search capabilities with document access", None, 4),
            ("viewer", "Viewer", "Read-only access to documents and search", None, 5),
            # Adoption Dashboard roles
            ("adoption_analyst", "Adoption Analyst", "View adoption metrics for granted companies", None, 6),
            ("adoption_admin", "Adoption Administrator", "Configure adoption data sources and sharing", None, 7),
        ]
        
        print("👥 Creating roles...")
        roles = {}
        for name, display_name, description, parent_role_id, hierarchy_level in roles_data:
            role = db.query(Role).filter(Role.name == name).first()
            if not role:
                role = Role(
                    name=name,
                    display_name=display_name,
                    description=description,
                    parent_role_id=parent_role_id,
                    hierarchy_level=hierarchy_level,
                    is_active=True
                )
                db.add(role)
                db.flush()
                print(f"  ✅ Created role: {display_name}")
            else:
                print(f"  ⏭️  Role already exists: {display_name}")
            roles[name] = role
        
        # Define role-permission mappings
        role_permission_mappings = {
            "super_admin": list(permissions.keys()),  # All permissions including wildcards
            "admin": [
                "assistant:access",  # AI Assistant access
                "documents:create", "documents:read", "documents:edit", "documents:delete", "documents:upload",
                "search:execute", "search:advanced",
                "models:read", "models:configure", "models:manage",
                "users:read", "users:create", "users:edit", "users:manage_roles",
                "system:health", "system:logs", "system:config",
                "analytics:read", "analytics:export",
                "bi:read", "bi:write", "bi:admin",
                "hr:read:company:*",  # Admins can access all company HR data
                "settings:read", "settings:write",
                "theme:write",
                "data_analyst:read", "data_analyst:write", "data_analyst:admin",
                "content_writer:read", "content_writer:write",
                # Adoption Dashboard - admins get full access
                "adoption:view_dashboard", "adoption:read:company:*", "adoption:admin:company:*",
                "adoption:manage_sharing", "adoption:manage_sync", "adoption:manage_jobs",
                # Workspaces
                "workspaces:write"
            ],
            "manager": [
                "assistant:access",  # AI Assistant access
                "documents:create", "documents:read", "documents:edit", "documents:upload",
                "search:execute", "search:advanced",
                "models:read", "models:configure",
                "users:read", "users:create", "users:edit",
                "system:health",
                "analytics:read",
                "bi:read", "bi:write",
                "hr:read:company:caylent",  # Managers can access their own company
                "settings:read",
                "data_analyst:read", "data_analyst:write",
                "content_writer:read", "content_writer:write"
            ],
            "analyst": [
                "assistant:access",  # AI Assistant access
                "documents:create", "documents:read", "documents:edit", "documents:upload",
                "search:execute", "search:advanced",
                "models:read",
                "users:read",
                "analytics:read",
                "bi:read", "bi:write",
                "hr:read:company:caylent",  # Analysts can access their own company
                "data_analyst:read", "data_analyst:write",
                "content_writer:read", "content_writer:write"
            ],
            "viewer": [
                "assistant:access",  # AI Assistant access (read-only)
                "documents:read",
                "search:execute",
                "models:read",
                "users:read",
                "bi:read",  # Viewers can only read BI, not write
                "data_analyst:read",  # Viewers can only read data analyst results
                "content_writer:read"  # Viewers can only read content writer results
            ],
            # Adoption Dashboard roles
            "adoption_analyst": [
                "adoption:view_dashboard",
                # Note: adoption:read:company:X permissions are granted separately per company
            ],
            "adoption_admin": [
                "adoption:view_dashboard",
                "adoption:manage_sharing",
                "adoption:manage_sync",
                "adoption:manage_jobs",
                # Note: adoption:read:company:X and adoption:admin:company:X are granted separately
            ]
        }
        
        print("🔗 Assigning permissions to roles...")
        for role_name, permission_names in role_permission_mappings.items():
            role = roles[role_name]
            for permission_name in permission_names:
                permission = permissions[permission_name]
                
                # Check if role-permission already exists
                from sqlalchemy import select
                existing = db.execute(
                    select(role_permissions).where(
                        (role_permissions.c.role_id == role.id) &
                        (role_permissions.c.permission_id == permission.id)
                    )
                ).first()
                
                if not existing:
                    db.execute(role_permissions.insert().values(role_id=role.id, permission_id=permission.id))
            
            print(f"  ✅ Assigned {len(permission_names)} permissions to {role.display_name}")
        
        # Create default admin user if it doesn't exist
        admin_email = "admin@eliza.com"
        admin_user = db.query(User).filter(User.email == admin_email).first()
        
        if not admin_user:
            print("👤 Creating default admin user...")
            admin_user = User(
                email=admin_email,
                username="admin",
                full_name="System Administrator",
                hashed_password=auth_service.get_password_hash("admin123!"),
                is_active=True,
                is_superuser=True,
                customer_id="default",
                preferred_language="en",
                timezone="UTC",
                password_changed_at=datetime.utcnow()
            )
            db.add(admin_user)
            db.flush()
            
            # Assign super_admin role to admin user
            user_role = UserRole(
                user_id=admin_user.id,
                role_id=roles["super_admin"].id,
                active=True
            )
            db.add(user_role)
            
            print(f"  ✅ Created admin user: {admin_email} (password: admin123!)")
        else:
            print(f"  ⏭️  Admin user already exists: {admin_email}")
        
        # Commit all changes
        db.commit()
        
        print("\n🎉 RBAC system initialization complete!")
        print(f"📊 Created {len(permissions)} permissions")
        print(f"👥 Created {len(roles)} roles")
        print(f"👤 Admin user: {admin_email}")
        print("🔐 Default admin password: admin123!")
        print("\n⚠️  Please change the default admin password after first login!")
        
    except Exception as e:
        print(f"❌ Error initializing RBAC system: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(init_rbac_system())
