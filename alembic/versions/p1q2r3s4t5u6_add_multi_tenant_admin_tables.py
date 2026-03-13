"""Add multi-tenant admin management tables

Revision ID: p1q2r3s4t5u6
Revises: o3p4q5r6s7t8
Create Date: 2025-12-23 15:00:00.000000

This migration adds the complete multi-tenant admin management system:
- platform_features: Master list of all platform features
- feature_permissions: Permissions available within each feature
- tenant_feature_allocations: Features allocated to each tenant
- tenant_roles: Roles defined within a tenant
- tenant_role_permissions: Permissions assigned to a role
- tenant_user_roles: Users assigned to roles
- user_invites: Invites for new users
- platform_admins: Platform-level administrators (Eliza team)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'p1q2r3s4t5u6'
down_revision = 'o3p4q5r6s7t8'
branch_labels = None
depends_on = None
tags = ["tenancy", "auth"]


def upgrade() -> None:
    """Create multi-tenant admin management tables."""
    
    # =========================================================================
    # PLATFORM FEATURES - Master list of all platform features
    # =========================================================================
    op.create_table(
        'platform_features',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feature_key', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('feature_key', name='uq_platform_feature_key')
    )
    
    op.create_index('ix_platform_features_feature_key', 'platform_features', ['feature_key'])
    op.create_index('ix_platform_features_category', 'platform_features', ['category'])
    
    # =========================================================================
    # FEATURE PERMISSIONS - Permissions available within each feature
    # =========================================================================
    op.create_table(
        'feature_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('feature_id', sa.Integer(), nullable=False),
        sa.Column('permission_key', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['feature_id'], ['platform_features.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('feature_id', 'permission_key', name='uq_feature_permission')
    )
    
    op.create_index('ix_feature_permissions_feature_id', 'feature_permissions', ['feature_id'])
    op.create_index('ix_feature_permissions_permission_key', 'feature_permissions', ['permission_key'])
    
    # =========================================================================
    # TENANT FEATURE ALLOCATIONS - Features allocated to each tenant
    # =========================================================================
    op.create_table(
        'tenant_feature_allocations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('feature_id', sa.Integer(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('allocated_by', sa.Integer(), nullable=True),
        sa.Column('allocated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('usage_limit', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['feature_id'], ['platform_features.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['allocated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'feature_id', name='uq_tenant_feature_allocation')
    )
    
    op.create_index('ix_tenant_feature_allocations_customer_id', 'tenant_feature_allocations', ['customer_id'])
    op.create_index('ix_tenant_feature_allocations_feature_id', 'tenant_feature_allocations', ['feature_id'])
    
    # =========================================================================
    # TENANT ROLES - Roles defined within a tenant
    # =========================================================================
    op.create_table(
        'tenant_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('role_name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'role_name', name='uq_tenant_role_name')
    )
    
    op.create_index('ix_tenant_roles_customer_id', 'tenant_roles', ['customer_id'])
    op.create_index('ix_tenant_roles_role_name', 'tenant_roles', ['role_name'])
    
    # =========================================================================
    # TENANT ROLE PERMISSIONS - Permissions assigned to a role
    # =========================================================================
    op.create_table(
        'tenant_role_permissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['tenant_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['feature_permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission')
    )
    
    op.create_index('ix_tenant_role_permissions_role_id', 'tenant_role_permissions', ['role_id'])
    op.create_index('ix_tenant_role_permissions_permission_id', 'tenant_role_permissions', ['permission_id'])
    
    # =========================================================================
    # TENANT USER ROLES - Users assigned to roles within a tenant
    # =========================================================================
    op.create_table(
        'tenant_user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['tenant_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role')
    )
    
    op.create_index('ix_tenant_user_roles_user_id', 'tenant_user_roles', ['user_id'])
    op.create_index('ix_tenant_user_roles_role_id', 'tenant_user_roles', ['role_id'])
    
    # =========================================================================
    # USER INVITES - Invites for new users created by tenant admins
    # =========================================================================
    op.create_table(
        'user_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('invite_token', sa.String(length=255), nullable=False),
        sa.Column('role_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_by_user_id', sa.Integer(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['accepted_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('invite_token', name='uq_invite_token')
    )
    
    op.create_index('ix_user_invites_customer_id', 'user_invites', ['customer_id'])
    op.create_index('ix_user_invites_email', 'user_invites', ['email'])
    op.create_index('ix_user_invites_invite_token', 'user_invites', ['invite_token'])
    op.create_index('ix_user_invites_status', 'user_invites', ['status'])
    
    # =========================================================================
    # PLATFORM ADMINS - Platform-level administrators (Eliza team)
    # =========================================================================
    op.create_table(
        'platform_admins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('admin_level', sa.String(length=50), nullable=False, server_default='admin'),
        sa.Column('can_create_tenants', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_allocate_features', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('can_manage_platform_admins', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('can_impersonate', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_platform_admin_user')
    )
    
    op.create_index('ix_platform_admins_user_id', 'platform_admins', ['user_id'])
    op.create_index('ix_platform_admins_admin_level', 'platform_admins', ['admin_level'])
    
    # =========================================================================
    # SEED INITIAL PLATFORM FEATURES (Idempotent - uses ON CONFLICT DO NOTHING)
    # =========================================================================
    # This ensures that:
    # 1. Features are only inserted if they don't exist (by feature_key)
    # 2. Existing features are NOT modified
    # 3. Future migrations can add new features safely
    op.execute("""
        INSERT INTO platform_features (feature_key, display_name, description, category, icon, sort_order) VALUES
        ('documents', 'Documents & RAG', 'Document management and RAG query system', 'data', 'DocumentText', 1),
        ('connectors', 'Data Connectors', 'External data source integrations', 'data', 'Plug', 2),
        ('ai_providers', 'AI Providers', 'AI model provider configuration', 'config', 'Brain', 3),
        ('business_intelligence', 'Business Intelligence', 'AI-powered business analytics', 'intelligence', 'BarChart', 4),
        ('talent_intelligence', 'Talent Intelligence', 'AI-powered talent analysis', 'intelligence', 'Users', 5),
        ('hr_intelligence', 'HR Intelligence', 'HR data analysis and insights', 'intelligence', 'Building', 6),
        ('operations_intelligence', 'Operations Intelligence', 'Operational analytics', 'intelligence', 'Settings', 7),
        ('users_roles', 'Users & Roles', 'User and role management', 'admin', 'UserCog', 8),
        ('settings', 'Settings', 'Tenant settings and configuration', 'admin', 'Cog', 9),
        ('audit', 'Audit & Logging', 'Audit trail and activity logging', 'admin', 'ClipboardList', 10)
        ON CONFLICT (feature_key) DO NOTHING
    """)
    
    # =========================================================================
    # SEED INITIAL FEATURE PERMISSIONS (Idempotent - uses ON CONFLICT DO NOTHING)
    # =========================================================================
    # This ensures that:
    # 1. Permissions are only inserted if they don't exist (by feature_id + permission_key)
    # 2. Existing permissions are NOT modified
    # 3. Future migrations can add new permissions safely
    
    # Documents permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'documents:create', 'Create Documents', 'Upload and create new documents', 1 
        FROM platform_features WHERE feature_key = 'documents'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'documents:read', 'Read Documents', 'View documents and metadata', 2 
        FROM platform_features WHERE feature_key = 'documents'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'documents:update', 'Update Documents', 'Edit document metadata', 3 
        FROM platform_features WHERE feature_key = 'documents'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'documents:delete', 'Delete Documents', 'Remove documents', 4 
        FROM platform_features WHERE feature_key = 'documents'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'documents:rag_query', 'RAG Query', 'Query documents using RAG', 5 
        FROM platform_features WHERE feature_key = 'documents'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # Connectors permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'connectors:create', 'Create Connectors', 'Create new data connectors', 1 
        FROM platform_features WHERE feature_key = 'connectors'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'connectors:read', 'Read Connectors', 'View connector configurations', 2 
        FROM platform_features WHERE feature_key = 'connectors'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'connectors:update', 'Update Connectors', 'Modify connector settings', 3 
        FROM platform_features WHERE feature_key = 'connectors'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'connectors:delete', 'Delete Connectors', 'Remove connectors', 4 
        FROM platform_features WHERE feature_key = 'connectors'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'connectors:run_sync', 'Run Sync', 'Trigger data synchronization', 5 
        FROM platform_features WHERE feature_key = 'connectors'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'connectors:view_telemetry', 'View Telemetry', 'View sync logs and telemetry', 6 
        FROM platform_features WHERE feature_key = 'connectors'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # AI Providers permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ai_providers:create', 'Create Providers', 'Add new AI provider configurations', 1 
        FROM platform_features WHERE feature_key = 'ai_providers'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ai_providers:read', 'Read Providers', 'View AI provider settings', 2 
        FROM platform_features WHERE feature_key = 'ai_providers'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ai_providers:update', 'Update Providers', 'Modify AI provider settings', 3 
        FROM platform_features WHERE feature_key = 'ai_providers'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ai_providers:delete', 'Delete Providers', 'Remove AI providers', 4 
        FROM platform_features WHERE feature_key = 'ai_providers'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ai_providers:test_keys', 'Test API Keys', 'Test API key validity', 5 
        FROM platform_features WHERE feature_key = 'ai_providers'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # Business Intelligence permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'bi:read', 'Read', 'View business intelligence data', 1 
        FROM platform_features WHERE feature_key = 'business_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'bi:write', 'Write', 'Create and modify BI content', 2 
        FROM platform_features WHERE feature_key = 'business_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'bi:run_queries', 'Run Queries', 'Execute BI queries', 3 
        FROM platform_features WHERE feature_key = 'business_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'bi:export_reports', 'Export Reports', 'Export BI reports', 4 
        FROM platform_features WHERE feature_key = 'business_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # Talent Intelligence permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'talent:read', 'Read', 'View talent data and analyses', 1 
        FROM platform_features WHERE feature_key = 'talent_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'talent:write', 'Write', 'Create and modify talent data', 2 
        FROM platform_features WHERE feature_key = 'talent_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'talent:run_analysis', 'Run Analysis', 'Execute talent analyses', 3 
        FROM platform_features WHERE feature_key = 'talent_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'talent:manage_configs', 'Manage Configurations', 'Manage talent configurations', 4 
        FROM platform_features WHERE feature_key = 'talent_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # HR Intelligence permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'hr:read', 'Read', 'View HR intelligence data', 1 
        FROM platform_features WHERE feature_key = 'hr_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'hr:write', 'Write', 'Create and modify HR data', 2 
        FROM platform_features WHERE feature_key = 'hr_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'hr:company_access', 'Company Access', 'Access company-level HR data', 3 
        FROM platform_features WHERE feature_key = 'hr_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'hr:run_reports', 'Run Reports', 'Generate HR reports', 4 
        FROM platform_features WHERE feature_key = 'hr_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # Operations Intelligence permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ops:read', 'Read', 'View operations data', 1 
        FROM platform_features WHERE feature_key = 'operations_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ops:write', 'Write', 'Create and modify operations data', 2 
        FROM platform_features WHERE feature_key = 'operations_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'ops:run_analysis', 'Run Analysis', 'Execute operations analyses', 3 
        FROM platform_features WHERE feature_key = 'operations_intelligence'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # Users & Roles permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'users:create', 'Create Users', 'Create new users', 1 
        FROM platform_features WHERE feature_key = 'users_roles'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'users:read', 'Read Users', 'View user information', 2 
        FROM platform_features WHERE feature_key = 'users_roles'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'users:update', 'Update Users', 'Modify user settings', 3 
        FROM platform_features WHERE feature_key = 'users_roles'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'users:delete', 'Delete Users', 'Deactivate users', 4 
        FROM platform_features WHERE feature_key = 'users_roles'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'roles:manage', 'Manage Roles', 'Create and manage roles', 5 
        FROM platform_features WHERE feature_key = 'users_roles'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # Settings permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'settings:read', 'Read Settings', 'View tenant settings', 1 
        FROM platform_features WHERE feature_key = 'settings'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'settings:write', 'Write Settings', 'Modify tenant settings', 2 
        FROM platform_features WHERE feature_key = 'settings'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    
    # Audit permissions
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'audit:read', 'Read Audit Logs', 'View audit trail', 1 
        FROM platform_features WHERE feature_key = 'audit'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)
    op.execute("""
        INSERT INTO feature_permissions (feature_id, permission_key, display_name, description, sort_order)
        SELECT id, 'audit:export', 'Export Audit Logs', 'Export audit data', 2 
        FROM platform_features WHERE feature_key = 'audit'
        ON CONFLICT (feature_id, permission_key) DO NOTHING
    """)


def downgrade() -> None:
    """Drop multi-tenant admin management tables."""
    
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('platform_admins')
    op.drop_table('user_invites')
    op.drop_table('tenant_user_roles')
    op.drop_table('tenant_role_permissions')
    op.drop_table('tenant_roles')
    op.drop_table('tenant_feature_allocations')
    op.drop_table('feature_permissions')
    op.drop_table('platform_features')

