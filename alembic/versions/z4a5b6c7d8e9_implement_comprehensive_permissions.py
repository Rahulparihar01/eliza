"""Implement comprehensive permissions system and update feature allocation

Revision ID: z4a5b6c7d8e9
Revises: y3z4a5b6c7d8
Create Date: 2025-12-25 18:00:00.000000

This migration implements the full permissions system as defined in
docs/specs/permissions-comprehensive.md

Creates/Updates:
- 71 permissions across 8 categories
- 4 default roles: platform_admin, tenant_admin, tenant_editor, tenant_viewer
- Role-permission assignments per the spec
- Updates platform_features to match new naming (AI Assistant, AI Recruiter, etc.)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = 'z4a5b6c7d8e9'
down_revision = 'y3z4a5b6c7d8'
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


# =============================================================================
# PERMISSION DEFINITIONS
# Columns: name, resource, action, description
# =============================================================================

PERMISSIONS = [
    # ---------- 1. Platform (1 permission) ----------
    # platform:admin already exists from previous migration
    
    # ---------- 2. AI Assistant (13 permissions) ----------
    ('assistant:access', 'assistant', 'access', 'Can open AI Assistant section'),
    ('assistant:documents:read', 'assistant', 'documents:read', 'View uploaded documents'),
    ('assistant:documents:upload', 'assistant', 'documents:upload', 'Upload new documents'),
    ('assistant:documents:delete', 'assistant', 'documents:delete', 'Remove documents'),
    ('assistant:questions:read', 'assistant', 'questions:read', 'View question history'),
    ('assistant:questions:ask', 'assistant', 'questions:ask', 'Submit new questions'),
    ('assistant:questions:delete', 'assistant', 'questions:delete', 'Delete question history'),
    ('assistant:chat:access', 'assistant', 'chat:access', 'Use the Chat interface'),
    ('assistant:domains:onboard', 'assistant', 'domains:onboard', 'Create new analytics domains'),
    ('assistant:domains:configure', 'assistant', 'domains:configure', 'Edit domain configuration'),
    ('assistant:domains:publish', 'assistant', 'domains:publish', 'Publish domains for use'),
    ('assistant:domains:delete', 'assistant', 'domains:delete', 'Remove analytics domains'),
    ('assistant:domains:insurance_analytics:access', 'assistant', 'domains:insurance_analytics:access', 'Query Insurance Analytics domain'),
    
    # ---------- 3. AI Recruiter (22 permissions) ----------
    ('recruiter:access', 'recruiter', 'access', 'Can open AI Recruiter section'),
    ('recruiter:config:read', 'recruiter', 'config:read', 'View search/scoring templates'),
    ('recruiter:config:create', 'recruiter', 'config:create', 'Create new templates'),
    ('recruiter:config:update', 'recruiter', 'config:update', 'Edit templates'),
    ('recruiter:config:delete', 'recruiter', 'config:delete', 'Delete templates'),
    ('recruiter:results:read', 'recruiter', 'results:read', 'View scored candidates & metrics'),
    ('recruiter:results:email', 'recruiter', 'results:email', 'Generate/send emails'),
    ('recruiter:results:feedback', 'recruiter', 'results:feedback', 'Provide score feedback'),
    ('recruiter:email_templates:read', 'recruiter', 'email_templates:read', 'View email templates'),
    ('recruiter:email_templates:create', 'recruiter', 'email_templates:create', 'Create email templates'),
    ('recruiter:email_templates:update', 'recruiter', 'email_templates:update', 'Edit email templates'),
    ('recruiter:email_templates:delete', 'recruiter', 'email_templates:delete', 'Delete email templates'),
    ('recruiter:email_templates:set_default', 'recruiter', 'email_templates:set_default', 'Set default template per candidate type'),
    ('recruiter:blueprints:read', 'recruiter', 'blueprints:read', 'View career blueprints'),
    ('recruiter:blueprints:create', 'recruiter', 'blueprints:create', 'Create blueprints'),
    ('recruiter:blueprints:update', 'recruiter', 'blueprints:update', 'Edit blueprints'),
    ('recruiter:blueprints:delete', 'recruiter', 'blueprints:delete', 'Delete blueprints'),
    ('recruiter:dna:read', 'recruiter', 'dna:read', 'View company DNA'),
    ('recruiter:dna:update', 'recruiter', 'dna:update', 'Edit company DNA'),
    ('recruiter:history:read', 'recruiter', 'history:read', 'View talent search run history'),
    ('recruiter:history:delete', 'recruiter', 'history:delete', 'Delete search history'),
    ('recruiter:reference_checks:access', 'recruiter', 'reference_checks:access', 'Access Reference Checks feature'),
    # NOTE: section_library permissions are added in migration d7e8f9g0h1i2
    
    # ---------- 4. Administration (6 permissions) ----------
    ('admin:settings:read', 'admin', 'settings:read', 'View system settings'),
    ('admin:settings:update', 'admin', 'settings:update', 'Modify system settings'),
    ('admin:settings:providers:manage', 'admin', 'settings:providers:manage', 'Manage AI provider configurations'),
    ('admin:email:read', 'admin', 'email:read', 'View Google email integration status'),
    ('admin:email:configure', 'admin', 'email:configure', 'Configure Google OAuth credentials'),
    ('admin:email:disconnect', 'admin', 'email:disconnect', 'Disconnect Google email account'),
    
    # ---------- 5. Data Connections (6 permissions) ----------
    ('connections:read', 'connections', 'read', 'View configured data connections'),
    ('connections:create', 'connections', 'create', 'Add new connections from library'),
    ('connections:update', 'connections', 'update', 'Edit connection configuration'),
    ('connections:delete', 'connections', 'delete', 'Remove data connections'),
    ('connections:test', 'connections', 'test', 'Test connection health/connectivity'),
    ('connections:sync', 'connections', 'sync', 'Trigger manual data synchronization'),
    
    # ---------- 6. Users & Roles (14 permissions) ----------
    ('users:read', 'users', 'read', 'View users in tenant'),
    ('users:invite', 'users', 'invite', 'Send user invitations'),
    ('users:update', 'users', 'update', 'Edit user details and role assignments'),
    ('users:deactivate', 'users', 'deactivate', 'Deactivate/suspend user accounts'),
    ('users:delete', 'users', 'delete', 'Permanently delete user accounts'),
    ('roles:read', 'roles', 'read', 'View available roles and permissions'),
    ('roles:create', 'roles', 'create', 'Create new custom roles'),
    ('roles:update', 'roles', 'update', 'Edit role permissions'),
    ('roles:delete', 'roles', 'delete', 'Delete custom roles'),
    ('roles:assign', 'roles', 'assign', 'Assign roles to users'),
    ('invites:read', 'invites', 'read', 'View pending invitations'),
    ('invites:create', 'invites', 'create', 'Create new user invitations'),
    ('invites:resend', 'invites', 'resend', 'Resend invitation emails'),
    ('invites:revoke', 'invites', 'revoke', 'Cancel pending invitations'),
    
    # ---------- 7. Audit (3 permissions) ----------
    ('audit:read', 'audit', 'read', 'View audit logs'),
    ('audit:export', 'audit', 'export', 'Export audit data to file'),
    ('audit:filter', 'audit', 'filter', 'Filter audit logs by user/action'),
    
    # ---------- 8. Coming Soon / Labs (6 permissions) ----------
    ('labs:agents:access', 'labs', 'agents:access', 'Access Agent Configuration page'),
    ('labs:agents:configure', 'labs', 'agents:configure', 'Configure AI agent parameters'),
    ('labs:agents:test', 'labs', 'agents:test', 'Test agent configurations'),
    ('labs:resume_parsing:access', 'labs', 'resume_parsing:access', 'Access Resume Parsing Test page'),
    ('labs:resume_parsing:upload', 'labs', 'resume_parsing:upload', 'Upload test resumes'),
    ('labs:resume_parsing:analyze', 'labs', 'resume_parsing:analyze', 'Run parsing analysis'),
]

# =============================================================================
# ROLE DEFINITIONS
# Columns: name, display_name, description, is_system_role
# =============================================================================

ROLES = [
    ('platform_admin', 'Platform Administrator', 'Full system access with all permissions granted. All actions are logged.', True),
    ('admin', 'Admin', 'Full administrative access within this organization', False),
    ('editor', 'Editor', 'Can create and modify content', False),
    ('viewer', 'Viewer', 'Read-only access to view content', False),
]

# =============================================================================
# ROLE-PERMISSION MAPPINGS
# =============================================================================

# platform_admin gets platform:admin only (bypasses all checks)
PLATFORM_ADMIN_PERMISSIONS = ['platform:admin']

# tenant_admin gets full access to everything except platform:admin and labs:*
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
    # NOTE: section_library permissions are assigned in migration d7e8f9g0h1i2
    'recruiter:blueprints:read', 'recruiter:blueprints:create', 'recruiter:blueprints:update', 'recruiter:blueprints:delete',
    'recruiter:dna:read', 'recruiter:dna:update',
    'recruiter:history:read', 'recruiter:history:delete',
    
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

# tenant_editor can create/modify content but not manage users or settings
TENANT_EDITOR_PERMISSIONS = [
    # AI Assistant
    'assistant:access', 'assistant:documents:read', 'assistant:documents:upload',
    'assistant:questions:read', 'assistant:questions:ask',
    'assistant:chat:access', 'assistant:domains:insurance_analytics:access',
    
    # AI Recruiter
    'recruiter:access', 'recruiter:config:read', 'recruiter:config:create', 'recruiter:config:update',
    'recruiter:results:read', 'recruiter:results:email', 'recruiter:results:feedback',
    'recruiter:email_templates:read', 'recruiter:email_templates:create', 'recruiter:email_templates:update',
    # NOTE: section_library permissions are assigned in migration d7e8f9g0h1i2
    'recruiter:blueprints:read', 'recruiter:blueprints:create', 'recruiter:blueprints:update',
    'recruiter:dna:read', 'recruiter:dna:update',
    'recruiter:history:read',
]

# tenant_viewer is read-only
TENANT_VIEWER_PERMISSIONS = [
    # AI Assistant
    'assistant:access', 'assistant:documents:read', 'assistant:questions:read',
    'assistant:chat:access', 'assistant:domains:insurance_analytics:access',
    
    # AI Recruiter
    'recruiter:access', 'recruiter:config:read', 'recruiter:results:read',
    'recruiter:email_templates:read',
    # NOTE: section_library:read is assigned in migration d7e8f9g0h1i2
    'recruiter:blueprints:read', 'recruiter:dna:read',
    'recruiter:history:read',
]


def upgrade() -> None:
    conn = op.get_bind()
    
    print("=" * 70)
    print("IMPLEMENTING COMPREHENSIVE PERMISSIONS SYSTEM")
    print("=" * 70)
    
    # -------------------------------------------------------------------------
    # STEP 0: Update platform_features to match new naming
    # -------------------------------------------------------------------------
    print("\n[Step 0/5] Updating platform feature names...")
    
    # Update existing features with new names
    feature_updates = [
        # (old_key, new_display_name, new_description, new_category)
        ('documents', 'AI Assistant - Documents', 'Document management and RAG query system', 'assistant'),
        ('business_intelligence', 'AI Assistant - Question Log', 'AI-powered question answering and history', 'assistant'),
        ('talent_intelligence', 'AI Recruiter', 'AI-powered talent search and analysis', 'recruiter'),
        ('connectors', 'Data Connections', 'Database and API integrations', 'admin'),
        ('ai_providers', 'Labs - Agent Configuration', 'AI agent and model configuration (Coming Soon)', 'labs'),
        ('settings', 'Admin Settings', 'System settings and configuration', 'admin'),
        ('users_roles', 'Users & Roles', 'User and role management', 'admin'),
        ('audit', 'Audit & Logging', 'Audit trail and activity logging', 'admin'),
    ]
    
    for feature_key, display_name, description, category in feature_updates:
        conn.execute(text("""
            UPDATE platform_features 
            SET display_name = :display_name, 
                description = :description, 
                category = :category,
                updated_at = now()
            WHERE feature_key = :feature_key
        """), {
            'feature_key': feature_key,
            'display_name': display_name,
            'description': description,
            'category': category,
        })
    
    # Deactivate deprecated features (keep data, just hide from UI)
    conn.execute(text("""
        UPDATE platform_features 
        SET is_active = false, updated_at = now()
        WHERE feature_key IN ('hr_intelligence', 'operations_intelligence')
    """))
    
    # Add new features that don't exist yet
    new_features = [
        ('assistant_chat', 'AI Assistant - Chat', 'Natural language data analytics chat', 'assistant', 'Chat', 3),
        ('recruiter_email_templates', 'AI Recruiter - Email Templates', 'Email template management for outreach', 'recruiter', 'Mail', 6),
        ('recruiter_blueprints', 'AI Recruiter - Blueprints & DNA', 'Career blueprints and company DNA configuration', 'recruiter', 'Blueprint', 7),
        ('recruiter_reference_checks', 'AI Recruiter - Reference Checks', 'Automated reference check system (Coming Soon)', 'recruiter', 'Phone', 8),
        ('invites', 'User Invites', 'User invitation management', 'admin', 'UserPlus', 11),
        ('labs_resume_parsing', 'Labs - Resume Parsing', 'Resume parsing test tool (Coming Soon)', 'labs', 'Document', 12),
    ]
    
    for feature_key, display_name, description, category, icon, sort_order in new_features:
        conn.execute(text("""
            INSERT INTO platform_features (feature_key, display_name, description, category, icon, sort_order, is_active)
            VALUES (:feature_key, :display_name, :description, :category, :icon, :sort_order, true)
            ON CONFLICT (feature_key) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                icon = EXCLUDED.icon,
                sort_order = EXCLUDED.sort_order,
                is_active = true,
                updated_at = now()
        """), {
            'feature_key': feature_key,
            'display_name': display_name,
            'description': description,
            'category': category,
            'icon': icon,
            'sort_order': sort_order,
        })
    
    print("  ✓ Updated feature display names to match new naming convention")
    print("  ✓ Deactivated deprecated features (hr_intelligence, operations_intelligence)")
    print("  ✓ Added new features (Chat, Email Templates, Blueprints, Invites, Labs)")
    
    # -------------------------------------------------------------------------
    # STEP 1: Create all permissions
    # Columns: name, resource, action, description, scope
    # -------------------------------------------------------------------------
    print("\n[Step 1/5] Creating permissions...")
    
    permission_count = 0
    for perm_name, resource, action, description in PERMISSIONS:
        conn.execute(text("""
            INSERT INTO permissions (name, resource, action, description, scope, created_at)
            VALUES (:name, :resource, :action, :description, 'all', now())
            ON CONFLICT (name) DO UPDATE SET 
                resource = EXCLUDED.resource,
                action = EXCLUDED.action,
                description = EXCLUDED.description
        """), {
            'name': perm_name,
            'resource': resource,
            'action': action,
            'description': description,
        })
        permission_count += 1
    
    print(f"  ✓ Created/updated {permission_count} permissions")
    
    # -------------------------------------------------------------------------
    # STEP 2: Ensure all roles exist
    # Columns: name, display_name, description, is_system_role
    # -------------------------------------------------------------------------
    print("\n[Step 2/5] Creating/updating roles...")
    
    # First, fix the roles constraint - drop old name-only constraint, add (customer_id, name)
    # This must happen before we try to create tenant-scoped roles with the same names
    print("  Fixing role constraints...")
    conn.execute(text("DROP INDEX IF EXISTS ix_roles_name"))
    conn.execute(text("ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_name_key"))
    
    # Add new composite unique constraint if it doesn't exist
    result = conn.execute(text("""
        SELECT 1 FROM pg_constraint WHERE conname = 'roles_customer_name_unique'
    """))
    if result.fetchone() is None:
        conn.execute(text("""
            ALTER TABLE roles 
            ADD CONSTRAINT roles_customer_name_unique UNIQUE (customer_id, name)
        """))
        print("  ✓ Added unique constraint: (customer_id, name)")
    else:
        print("  ✓ Unique constraint already exists")
    
    # Get the CUSTOMER_ID from environment - required, no default
    import os
    CUSTOMER_ID = os.environ.get('CUSTOMER_ID')
    if not CUSTOMER_ID:
        raise ValueError("CUSTOMER_ID environment variable is required for migration")
    
    for role_name, display_name, description, is_system_role in ROLES:
        # Check if role exists for this customer
        existing = conn.execute(text("""
            SELECT id FROM roles WHERE customer_id = :customer_id AND name = :name
        """), {'customer_id': CUSTOMER_ID, 'name': role_name}).fetchone()
        
        if existing:
            # Update existing role
            conn.execute(text("""
                UPDATE roles SET 
                    display_name = :display_name,
                    description = :description,
                    is_system_role = :is_system_role,
                    is_active = true,
                    updated_at = now()
                WHERE customer_id = :customer_id AND name = :name
            """), {
                'name': role_name,
                'display_name': display_name,
                'description': description,
                'is_system_role': is_system_role,
                'customer_id': CUSTOMER_ID,
            })
        else:
            # Insert new role
            conn.execute(text("""
                INSERT INTO roles (name, display_name, description, is_system_role, is_active, customer_id, created_at, updated_at)
                VALUES (:name, :display_name, :description, :is_system_role, true, :customer_id, now(), now())
            """), {
                'name': role_name,
                'display_name': display_name,
                'description': description,
                'is_system_role': is_system_role,
                'customer_id': CUSTOMER_ID,
            })
        print(f"  ✓ {role_name}")
    
    # -------------------------------------------------------------------------
    # STEP 3: Clear existing role_permissions (except platform_admin -> platform:admin)
    # -------------------------------------------------------------------------
    print("\n[Step 3/5] Clearing old role-permission assignments...")
    conn.execute(text("""
        DELETE FROM role_permissions 
        WHERE NOT (
            role_id IN (SELECT id FROM roles WHERE name = 'platform_admin')
            AND permission_id IN (SELECT id FROM permissions WHERE name = 'platform:admin')
        )
    """))
    print("  ✓ Cleared old assignments (preserved platform_admin -> platform:admin)")
    
    # -------------------------------------------------------------------------
    # STEP 4: Assign permissions to roles
    # -------------------------------------------------------------------------
    print("\n[Step 4/5] Assigning permissions to roles...")
    
    def assign_permissions_to_role(role_name: str, permission_names: list):
        """Helper to assign a list of permissions to a role."""
        count = 0
        for perm_name in permission_names:
            conn.execute(text("""
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT r.id, p.id
                FROM roles r, permissions p
                WHERE r.name = :role_name AND p.name = :perm_name
                ON CONFLICT DO NOTHING
            """), {'role_name': role_name, 'perm_name': perm_name})
            count += 1
        return count
    
    # Platform Admin gets ALL permissions
    conn.execute(text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.name = 'platform_admin'
        ON CONFLICT DO NOTHING
    """))
    platform_admin_count = conn.execute(text("""
        SELECT COUNT(*) FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id
        WHERE r.name = 'platform_admin'
    """)).scalar()
    print(f"  ✓ platform_admin: {platform_admin_count} permissions (full access)")
    
    # Tenant Admin (role name is 'admin' per-tenant)
    count = assign_permissions_to_role('admin', TENANT_ADMIN_PERMISSIONS)
    print(f"  ✓ admin: {count} permissions")
    
    # Tenant Editor (role name is 'editor' per-tenant)
    count = assign_permissions_to_role('editor', TENANT_EDITOR_PERMISSIONS)
    print(f"  ✓ editor: {count} permissions")
    
    # Tenant Viewer (role name is 'viewer' per-tenant)
    count = assign_permissions_to_role('viewer', TENANT_VIEWER_PERMISSIONS)
    print(f"  ✓ viewer: {count} permissions")
    
    # -------------------------------------------------------------------------
    # SUMMARY
    # -------------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PERMISSIONS SYSTEM IMPLEMENTED SUCCESSFULLY")
    print("=" * 70)
    print(f"""
Summary:
  - Platform Features: Updated to match new naming convention
    • AI Assistant (Documents, Question Log, Chat)
    • AI Recruiter (Talent Search, Email Templates, Blueprints, Reference Checks)
    • Administration (Data Connections, Users & Roles, Invites, Settings, Audit)
    • Labs (Agent Configuration, Resume Parsing)
    
  - Total permissions: 71 (including platform:admin)
  - Roles configured: 4
    • platform_admin: Full access (all 71 permissions)
    • admin: Full tenant access ({len(TENANT_ADMIN_PERMISSIONS)} permissions)
    • editor: Create/edit content ({len(TENANT_EDITOR_PERMISSIONS)} permissions)
    • viewer: Read-only access ({len(TENANT_VIEWER_PERMISSIONS)} permissions)

Permission Categories:
  - Platform: 1
  - AI Assistant: 13
  - AI Recruiter: 22
  - Administration: 6
  - Data Connections: 6
  - Users & Roles: 14
  - Audit: 3
  - Labs (Coming Soon): 6
""")
    print("=" * 70)


def downgrade() -> None:
    conn = op.get_bind()
    
    print("Rolling back comprehensive permissions and feature updates...")
    
    # Clear all role_permissions except platform_admin -> platform:admin
    conn.execute(text("""
        DELETE FROM role_permissions 
        WHERE NOT (
            role_id IN (SELECT id FROM roles WHERE name = 'platform_admin')
            AND permission_id IN (SELECT id FROM permissions WHERE name = 'platform:admin')
        )
    """))
    
    # Delete all permissions except platform:admin
    conn.execute(text("""
        DELETE FROM permissions 
        WHERE name != 'platform:admin'
    """))
    
    # Delete newly added features
    conn.execute(text("""
        DELETE FROM platform_features 
        WHERE feature_key IN (
            'assistant_chat', 'recruiter_email_templates', 'recruiter_blueprints',
            'recruiter_reference_checks', 'invites', 'labs_resume_parsing'
        )
    """))
    
    # Re-activate deprecated features
    conn.execute(text("""
        UPDATE platform_features 
        SET is_active = true, updated_at = now()
        WHERE feature_key IN ('hr_intelligence', 'operations_intelligence')
    """))
    
    # Restore original feature names (best effort)
    original_names = [
        ('documents', 'Documents & RAG', 'Document management and RAG query system', 'data'),
        ('business_intelligence', 'Business Intelligence', 'AI-powered business analytics', 'intelligence'),
        ('talent_intelligence', 'Talent Intelligence', 'AI-powered talent analysis', 'intelligence'),
        ('connectors', 'Data Connectors', 'External data source integrations', 'data'),
        ('ai_providers', 'AI Providers', 'AI model provider configuration', 'config'),
        ('settings', 'Settings', 'Tenant settings and configuration', 'admin'),
        ('users_roles', 'Users & Roles', 'User and role management', 'admin'),
        ('audit', 'Audit & Logging', 'Audit trail and activity logging', 'admin'),
    ]
    
    for feature_key, display_name, description, category in original_names:
        conn.execute(text("""
            UPDATE platform_features 
            SET display_name = :display_name,
                description = :description,
                category = :category,
                updated_at = now()
            WHERE feature_key = :feature_key
        """), {
            'feature_key': feature_key,
            'display_name': display_name,
            'description': description,
            'category': category,
        })
    
    # Note: We don't delete the roles as they might have user assignments
    print("  ✓ Rolled back to clean slate (platform:admin only)")
    print("  ✓ Restored original feature names")
