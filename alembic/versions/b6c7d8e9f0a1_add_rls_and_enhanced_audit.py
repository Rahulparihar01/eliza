"""Add Row Level Security and Enhanced Audit Logging for SOC2 Compliance

Revision ID: b6c7d8e9f0a1
Revises: z4a5b6c7d8e9
Create Date: 2024-12-25

This migration implements:
1. Enhanced audit tables for compliance (DataAccessAuditLog, RLSViolationLog, etc.)
2. Add customer_id to existing UserAuditLog table
3. Row Level Security (RLS) policies for all tenant-scoped tables
4. Database function for setting tenant context
"""

from typing import Sequence, Union, Optional
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b6c7d8e9f0a1'
down_revision: Optional[str] = 'z4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["auth", "tenancy", "core"]


# Tables that need RLS (all tables with customer_id)
TENANT_TABLES = [
    'users',
    'roles',
    'user_invites',
    'tenant_feature_allocations',
    'documents',
    'document_chunks',
    'reference_check_requests',
    'candidate_references',
    'reference_call_templates',
    'reference_voice_personas',
    'reference_scheduled_calls',
    'reference_calls',
    'customer_caller_ids',
    'customer_call_settings',
    'candidates',
    'candidate_score_feedback',
    'analysis_configs',
    'career_blueprints',
    'company_dna_profiles',
    'outreach_emails',
    'email_templates',
    'generated_emails',
    'pdl_query_cache',
    'customer_settings',
    'talent_feedback',
    'data_analyst_conversations',
    'data_analyst_messages',
    'career_fingerprints',
    'connector_configurations',
    'connector_sync_runs',
    'pdl_persons',
    'customer_ai_providers',
]


def upgrade() -> None:
    """
    Upgrade: Add enhanced audit logging and RLS.
    """
    conn = op.get_bind()
    
    print("\n" + "="*70)
    print("MIGRATION: Add Row Level Security and Enhanced Audit Logging")
    print("="*70)
    
    # =========================================================================
    # STEP 1: Add customer_id to existing user_audit_log table
    # =========================================================================
    print("\n[Step 1/6] Adding customer_id to user_audit_log...")
    
    # Check if column already exists
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'user_audit_log' AND column_name = 'customer_id'
    """))
    if result.fetchone() is None:
        op.add_column('user_audit_log', sa.Column('customer_id', sa.String(100), nullable=True))
        print("  ✓ Added customer_id column to user_audit_log")
    else:
        print("  ✓ customer_id column already exists")
    
    # Check if index already exists
    result = conn.execute(sa.text("""
        SELECT indexname FROM pg_indexes 
        WHERE indexname = 'ix_user_audit_log_customer_id'
    """))
    if result.fetchone() is None:
        op.create_index('ix_user_audit_log_customer_id', 'user_audit_log', ['customer_id'])
        print("  ✓ Created index on customer_id")
    else:
        print("  ✓ Index already exists")
    
    # Add severity column if it doesn't exist
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'user_audit_log' AND column_name = 'severity'
    """))
    if result.fetchone() is None:
        op.add_column('user_audit_log', sa.Column('severity', sa.String(20), nullable=True, default='low'))
        print("  ✓ Added severity column to user_audit_log")
    
    # Add outcome column if it doesn't exist
    result = conn.execute(sa.text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'user_audit_log' AND column_name = 'outcome'
    """))
    if result.fetchone() is None:
        op.add_column('user_audit_log', sa.Column('outcome', sa.String(20), nullable=True, default='success'))
        print("  ✓ Added outcome column to user_audit_log")

    # =========================================================================
    # STEP 2: Create data_access_audit_log table
    # =========================================================================
    print("\n[Step 2/6] Creating data_access_audit_log table...")
    
    result = conn.execute(sa.text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = 'data_access_audit_log'
    """))
    if result.fetchone() is None:
        op.create_table(
            'data_access_audit_log',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('customer_id', sa.String(100), nullable=False),
            sa.Column('session_id', sa.String(255), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('request_id', sa.String(100), nullable=True),
            sa.Column('action', sa.String(50), nullable=False),
            sa.Column('resource_type', sa.String(100), nullable=False),
            sa.Column('resource_id', sa.String(255), nullable=True),
            sa.Column('resource_ids', postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column('api_endpoint', sa.String(255), nullable=True),
            sa.Column('api_method', sa.String(10), nullable=True),
            sa.Column('records_affected', sa.Integer(), nullable=True),
            sa.Column('data_classification', sa.String(50), nullable=True),
            sa.Column('fields_accessed', postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column('query_hash', sa.String(64), nullable=True),
            sa.Column('query_params_hash', sa.String(64), nullable=True),
            sa.Column('outcome', sa.String(20), nullable=False, server_default='success'),
            sa.Column('denial_reason', sa.String(255), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('severity', sa.String(20), nullable=False, server_default='low'),
            sa.Column('duration_ms', sa.Integer(), nullable=True),
            sa.Column('additional_context', postgresql.JSONB(), nullable=True),
        )
        
        # Create indexes for common query patterns
        op.create_index('ix_data_access_audit_log_timestamp', 'data_access_audit_log', ['timestamp'])
        op.create_index('ix_data_access_audit_log_customer_id', 'data_access_audit_log', ['customer_id'])
        op.create_index('ix_data_access_audit_log_user_id', 'data_access_audit_log', ['user_id'])
        op.create_index('ix_data_access_audit_log_resource_type', 'data_access_audit_log', ['resource_type'])
        op.create_index('ix_data_access_audit_log_action', 'data_access_audit_log', ['action'])
        op.create_index('ix_data_access_audit_log_request_id', 'data_access_audit_log', ['request_id'])
        op.create_index('ix_data_access_customer_timestamp', 'data_access_audit_log', ['customer_id', 'timestamp'])
        op.create_index('ix_data_access_user_timestamp', 'data_access_audit_log', ['user_id', 'timestamp'])
        print("  ✓ Created data_access_audit_log table with indexes")
    else:
        print("  ✓ data_access_audit_log table already exists")
    
    # =========================================================================
    # STEP 3: Create rls_violation_log table
    # =========================================================================
    print("\n[Step 3/6] Creating rls_violation_log table...")
    
    result = conn.execute(sa.text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = 'rls_violation_log'
    """))
    if result.fetchone() is None:
        op.create_table(
            'rls_violation_log',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('customer_id', sa.String(100), nullable=False),
            sa.Column('target_customer_id', sa.String(100), nullable=False),
            sa.Column('table_name', sa.String(100), nullable=False),
            sa.Column('operation', sa.String(20), nullable=False),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('request_id', sa.String(100), nullable=True),
            sa.Column('api_endpoint', sa.String(255), nullable=True),
            sa.Column('query_hash', sa.String(64), nullable=True),
            sa.Column('policy_name', sa.String(100), nullable=True),
            sa.Column('blocked_by', sa.String(50), nullable=False, server_default='rls'),
            sa.Column('severity', sa.String(20), nullable=False, server_default='high'),
            sa.Column('investigated', sa.Boolean(), server_default='false'),
            sa.Column('investigated_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('investigated_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('investigation_notes', sa.Text(), nullable=True),
            sa.Column('additional_context', postgresql.JSONB(), nullable=True),
        )
        
        op.create_index('ix_rls_violation_log_timestamp', 'rls_violation_log', ['timestamp'])
        op.create_index('ix_rls_violation_log_customer_id', 'rls_violation_log', ['customer_id'])
        op.create_index('ix_rls_violation_log_target_customer_id', 'rls_violation_log', ['target_customer_id'])
        op.create_index('ix_rls_violation_customer_timestamp', 'rls_violation_log', ['customer_id', 'timestamp'])
        print("  ✓ Created rls_violation_log table with indexes")
    else:
        print("  ✓ rls_violation_log table already exists")
    
    # =========================================================================
    # STEP 4: Create tenant_activity_summary table
    # =========================================================================
    print("\n[Step 4/6] Creating tenant_activity_summary table...")
    
    result = conn.execute(sa.text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = 'tenant_activity_summary'
    """))
    if result.fetchone() is None:
        op.create_table(
            'tenant_activity_summary',
            sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column('period_start', sa.DateTime(timezone=True), nullable=False),
            sa.Column('period_end', sa.DateTime(timezone=True), nullable=False),
            sa.Column('period_type', sa.String(20), nullable=False),
            sa.Column('customer_id', sa.String(100), nullable=False),
            sa.Column('total_requests', sa.Integer(), server_default='0'),
            sa.Column('total_reads', sa.Integer(), server_default='0'),
            sa.Column('total_writes', sa.Integer(), server_default='0'),
            sa.Column('total_deletes', sa.Integer(), server_default='0'),
            sa.Column('unique_users', sa.Integer(), server_default='0'),
            sa.Column('login_count', sa.Integer(), server_default='0'),
            sa.Column('failed_login_count', sa.Integer(), server_default='0'),
            sa.Column('permission_denied_count', sa.Integer(), server_default='0'),
            sa.Column('rls_violation_count', sa.Integer(), server_default='0'),
            sa.Column('pii_access_count', sa.Integer(), server_default='0'),
            sa.Column('sensitive_data_access_count', sa.Integer(), server_default='0'),
            sa.Column('resource_access_counts', postgresql.JSONB(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        
        op.create_index('ix_tenant_activity_summary_period_start', 'tenant_activity_summary', ['period_start'])
        op.create_index('ix_tenant_activity_summary_customer_id', 'tenant_activity_summary', ['customer_id'])
        op.create_index('ix_tenant_activity_customer_period', 'tenant_activity_summary', ['customer_id', 'period_start'])
        print("  ✓ Created tenant_activity_summary table with indexes")
    else:
        print("  ✓ tenant_activity_summary table already exists")
    
    # =========================================================================
    # STEP 5: Create compliance_reports table
    # =========================================================================
    print("\n[Step 5/6] Creating compliance_reports table...")
    
    result = conn.execute(sa.text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name = 'compliance_reports'
    """))
    if result.fetchone() is None:
        op.create_table(
            'compliance_reports',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('report_type', sa.String(50), nullable=False),
            sa.Column('report_name', sa.String(255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('customer_id', sa.String(100), nullable=True),
            sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
            sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
            sa.Column('parameters', postgresql.JSONB(), nullable=True),
            sa.Column('report_data', postgresql.JSONB(), nullable=True),
            sa.Column('file_path', sa.String(500), nullable=True),
            sa.Column('generated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('generation_duration_ms', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('access_count', sa.Integer(), server_default='0'),
        )
        
        op.create_index('ix_compliance_reports_customer_id', 'compliance_reports', ['customer_id'])
        op.create_index('ix_compliance_reports_report_type', 'compliance_reports', ['report_type'])
        print("  ✓ Created compliance_reports table with indexes")
    else:
        print("  ✓ compliance_reports table already exists")
    
    # =========================================================================
    # STEP 6: Enable Row Level Security (RLS) on tenant tables
    # =========================================================================
    print("\n[Step 6/6] Enabling Row Level Security on tenant tables...")
    
    # Create the function to get current tenant from session
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS text AS $$
        BEGIN
            RETURN current_setting('app.customer_id', true);
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))
    print("  ✓ Created current_tenant_id() function")
    
    # Create function to check if cross-tenant access is allowed
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION is_cross_tenant_access_allowed() RETURNS boolean AS $$
        BEGIN
            -- Cross-tenant access requires BOTH flags to be explicitly set to 'true'
            RETURN (
                current_setting('app.is_platform_admin', true) = 'true'
                AND current_setting('app.cross_tenant_access', true) = 'true'
            );
        END;
        $$ LANGUAGE plpgsql STABLE;
    """))
    print("  ✓ Created is_cross_tenant_access_allowed() function")
    
    # Create function to log RLS violations (called when policy blocks access)
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION log_rls_violation(
            p_user_id integer,
            p_customer_id text,
            p_target_customer_id text,
            p_table_name text,
            p_operation text
        ) RETURNS void AS $$
        BEGIN
            INSERT INTO rls_violation_log (
                user_id, customer_id, target_customer_id, table_name, operation
            ) VALUES (
                p_user_id, p_customer_id, p_target_customer_id, p_table_name, p_operation
            );
        END;
        $$ LANGUAGE plpgsql;
    """))
    print("  ✓ Created log_rls_violation() function")
    
    # Enable RLS on each tenant table
    enabled_count = 0
    skipped_count = 0
    
    for table in TENANT_TABLES:
        # Check if table exists
        result = conn.execute(sa.text(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name = :table_name AND table_schema = 'public'
        """), {'table_name': table})
        
        if result.fetchone() is None:
            print(f"  ⚠ Skipping {table} (table does not exist)")
            skipped_count += 1
            continue
        
        # Check if customer_id column exists
        result = conn.execute(sa.text(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = :table_name AND column_name = 'customer_id'
        """), {'table_name': table})
        
        if result.fetchone() is None:
            print(f"  ⚠ Skipping {table} (no customer_id column)")
            skipped_count += 1
            continue
        
        try:
            # Enable RLS on the table
            conn.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            
            # Drop existing policy if any
            conn.execute(sa.text(f'DROP POLICY IF EXISTS tenant_isolation_policy ON "{table}"'))
            
            # Create the tenant isolation policy
            # This policy ensures users can only see rows where customer_id matches their tenant
            # Platform admins can access cross-tenant data ONLY with explicit flags set
            # NO implicit NULL bypass - every request must have explicit tenant context
            conn.execute(sa.text(f"""
                CREATE POLICY tenant_isolation_policy ON "{table}"
                FOR ALL
                USING (
                    -- Normal case: user can only see their own tenant's data
                    customer_id = current_tenant_id()
                    -- Platform admin cross-tenant access: requires EXPLICIT flags
                    OR is_cross_tenant_access_allowed()
                )
                WITH CHECK (
                    -- Writes MUST specify the correct tenant (no cross-tenant writes)
                    customer_id = current_tenant_id()
                )
            """))
            
            # Force RLS for table owner too (important for security)
            conn.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
            
            print(f"  ✓ Enabled RLS on {table}")
            enabled_count += 1
            
        except Exception as e:
            print(f"  ✗ Failed to enable RLS on {table}: {str(e)}")
            skipped_count += 1
    
    print(f"\n  Summary: Enabled RLS on {enabled_count} tables, skipped {skipped_count}")
    
    # =========================================================================
    # STEP 7: Create audit trigger function for automatic logging
    # =========================================================================
    print("\n[Bonus] Creating audit trigger function...")
    
    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION audit_trigger_func() RETURNS trigger AS $$
        DECLARE
            v_old_data JSONB;
            v_new_data JSONB;
            v_action TEXT;
        BEGIN
            v_action := TG_OP;
            
            IF (TG_OP = 'UPDATE') THEN
                v_old_data := to_jsonb(OLD);
                v_new_data := to_jsonb(NEW);
                INSERT INTO data_access_audit_log (
                    customer_id, action, resource_type, resource_id,
                    additional_context, severity
                ) VALUES (
                    COALESCE(current_tenant_id(), NEW.customer_id, 'system'),
                    'UPDATE',
                    TG_TABLE_NAME,
                    NEW.id::text,
                    jsonb_build_object('old', v_old_data, 'new', v_new_data),
                    'low'
                );
                RETURN NEW;
            ELSIF (TG_OP = 'DELETE') THEN
                v_old_data := to_jsonb(OLD);
                INSERT INTO data_access_audit_log (
                    customer_id, action, resource_type, resource_id,
                    additional_context, severity
                ) VALUES (
                    COALESCE(current_tenant_id(), OLD.customer_id, 'system'),
                    'DELETE',
                    TG_TABLE_NAME,
                    OLD.id::text,
                    jsonb_build_object('deleted', v_old_data),
                    'medium'
                );
                RETURN OLD;
            ELSIF (TG_OP = 'INSERT') THEN
                v_new_data := to_jsonb(NEW);
                INSERT INTO data_access_audit_log (
                    customer_id, action, resource_type, resource_id,
                    additional_context, severity
                ) VALUES (
                    COALESCE(current_tenant_id(), NEW.customer_id, 'system'),
                    'INSERT',
                    TG_TABLE_NAME,
                    NEW.id::text,
                    jsonb_build_object('new', v_new_data),
                    'low'
                );
                RETURN NEW;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """))
    print("  ✓ Created audit_trigger_func()")
    
    # Add triggers to critical tables (users, roles, documents)
    critical_tables = ['users', 'roles', 'documents', 'user_invites']
    for table in critical_tables:
        result = conn.execute(sa.text(f"""
            SELECT table_name FROM information_schema.tables 
            WHERE table_name = :table_name AND table_schema = 'public'
        """), {'table_name': table})
        
        if result.fetchone():
            conn.execute(sa.text(f'DROP TRIGGER IF EXISTS audit_trigger ON "{table}"'))
            conn.execute(sa.text(f"""
                CREATE TRIGGER audit_trigger
                AFTER INSERT OR UPDATE OR DELETE ON "{table}"
                FOR EACH ROW EXECUTE FUNCTION audit_trigger_func()
            """))
            print(f"  ✓ Added audit trigger to {table}")
    
    print("\n" + "="*70)
    print("MIGRATION COMPLETE: RLS and Enhanced Audit Logging enabled")
    print("="*70)
    print("\nIMPORTANT: Application must SET app.customer_id before queries!")
    print("Example: SET app.customer_id = 'tenant_123';")
    print("="*70 + "\n")


def downgrade() -> None:
    """
    Downgrade: Remove RLS and enhanced audit logging.
    """
    conn = op.get_bind()
    
    print("\n[Downgrade] Removing RLS and enhanced audit...")
    
    # Disable RLS on all tables
    for table in TENANT_TABLES:
        try:
            conn.execute(sa.text(f'DROP POLICY IF EXISTS tenant_isolation_policy ON "{table}"'))
            conn.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
        except:
            pass
    
    # Remove triggers
    critical_tables = ['users', 'roles', 'documents', 'user_invites']
    for table in critical_tables:
        try:
            conn.execute(sa.text(f'DROP TRIGGER IF EXISTS audit_trigger ON "{table}"'))
        except:
            pass
    
    # Drop functions
    conn.execute(sa.text('DROP FUNCTION IF EXISTS audit_trigger_func() CASCADE'))
    conn.execute(sa.text('DROP FUNCTION IF EXISTS log_rls_violation(integer, text, text, text, text) CASCADE'))
    conn.execute(sa.text('DROP FUNCTION IF EXISTS is_cross_tenant_access_allowed() CASCADE'))
    conn.execute(sa.text('DROP FUNCTION IF EXISTS current_tenant_id() CASCADE'))
    
    # Drop new tables
    op.drop_table('compliance_reports')
    op.drop_table('tenant_activity_summary')
    op.drop_table('rls_violation_log')
    op.drop_table('data_access_audit_log')
    
    # Remove columns from user_audit_log
    op.drop_column('user_audit_log', 'outcome')
    op.drop_column('user_audit_log', 'severity')
    op.drop_index('ix_user_audit_log_customer_id', 'user_audit_log')
    op.drop_column('user_audit_log', 'customer_id')
    
    print("  ✓ Downgrade complete")

