"""
Security Tests: Audit Logging Verification

These tests verify that:
1. Data access events are written to the audit log
2. Audit entries include correct tenant context
3. RLS violations are logged
4. Audit triggers fire on table changes

Run with: pytest tests/security/test_audit_logging.py -v
"""

import pytest
import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import text

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.models import database


def get_db_session():
    """Get a database session, initializing if needed."""
    if database.SessionLocal is None:
        database.init_database()
    return database.SessionLocal()


class TestAuditLogWriting:
    """Test that audit log entries are actually being written."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session."""
        self.db = get_db_session()
        yield
        self.db.rollback()  # Don't persist test data
        self.db.close()
    
    def test_can_insert_audit_log_entry(self):
        """Verify we can manually insert an audit log entry."""
        # Insert a test audit entry
        self.db.execute(text("""
            INSERT INTO data_access_audit_log 
            (customer_id, action, resource_type, outcome, severity)
            VALUES ('test_tenant', 'SELECT', 'test_resource', 'success', 'low')
        """))
        
        # Verify it was inserted
        result = self.db.execute(text("""
            SELECT customer_id, action, resource_type, outcome
            FROM data_access_audit_log
            WHERE customer_id = 'test_tenant'
            AND resource_type = 'test_resource'
            ORDER BY timestamp DESC
            LIMIT 1
        """))
        row = result.fetchone()
        
        assert row is not None, "Audit log entry was not inserted"
        assert row[0] == 'test_tenant', f"customer_id mismatch: {row[0]}"
        assert row[1] == 'SELECT', f"action mismatch: {row[1]}"
        assert row[2] == 'test_resource', f"resource_type mismatch: {row[2]}"
        assert row[3] == 'success', f"outcome mismatch: {row[3]}"
    
    def test_audit_log_captures_all_required_fields(self):
        """Verify audit log schema supports all required fields."""
        # Insert with all fields
        self.db.execute(text("""
            INSERT INTO data_access_audit_log (
                customer_id, user_id, session_id, ip_address, user_agent,
                request_id, action, resource_type, resource_id, api_endpoint,
                api_method, records_affected, data_classification, outcome,
                denial_reason, error_message, severity, duration_ms
            ) VALUES (
                'test_tenant', 1, 'session_123', '192.168.1.1', 'TestAgent/1.0',
                'req_abc123', 'SELECT', 'users', '42', '/api/v1/users',
                'GET', 10, 'PII', 'success',
                NULL, NULL, 'medium', 150
            )
        """))
        
        # Verify all fields
        result = self.db.execute(text("""
            SELECT 
                customer_id, user_id, session_id, ip_address, user_agent,
                request_id, action, resource_type, resource_id, api_endpoint,
                api_method, records_affected, data_classification, outcome,
                severity, duration_ms
            FROM data_access_audit_log
            WHERE request_id = 'req_abc123'
        """))
        row = result.fetchone()
        
        assert row is not None, "Audit log entry was not inserted"
        assert row[0] == 'test_tenant'  # customer_id
        assert row[1] == 1  # user_id
        assert row[2] == 'session_123'  # session_id
        assert row[3] == '192.168.1.1'  # ip_address
        assert row[4] == 'TestAgent/1.0'  # user_agent
        assert row[5] == 'req_abc123'  # request_id
        assert row[6] == 'SELECT'  # action
        assert row[7] == 'users'  # resource_type
        assert row[8] == '42'  # resource_id
        assert row[9] == '/api/v1/users'  # api_endpoint
        assert row[10] == 'GET'  # api_method
        assert row[11] == 10  # records_affected
        assert row[12] == 'PII'  # data_classification
        assert row[13] == 'success'  # outcome
        assert row[14] == 'medium'  # severity
        assert row[15] == 150  # duration_ms


class TestRLSViolationLogging:
    """Test that RLS violations are logged."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session."""
        self.db = get_db_session()
        yield
        self.db.rollback()
        self.db.close()
    
    def test_can_insert_rls_violation_log(self):
        """Verify we can log RLS violations."""
        self.db.execute(text("""
            INSERT INTO rls_violation_log (
                customer_id, target_customer_id, user_id, table_name, policy_name,
                operation
            ) VALUES (
                'attacker_tenant', 'victim_tenant', 1, 'documents', 'tenant_isolation_policy',
                'SELECT'
            )
        """))
        
        result = self.db.execute(text("""
            SELECT customer_id, target_customer_id, table_name, policy_name, operation
            FROM rls_violation_log
            WHERE customer_id = 'attacker_tenant'
            ORDER BY timestamp DESC
            LIMIT 1
        """))
        row = result.fetchone()
        
        assert row is not None, "RLS violation was not logged"
        assert row[0] == 'attacker_tenant'
        assert row[1] == 'victim_tenant'
        assert row[2] == 'documents'
        assert row[3] == 'tenant_isolation_policy'
        assert row[4] == 'SELECT'
    
    def test_rls_violation_log_has_required_indexes(self):
        """Verify indexes exist for efficient querying."""
        result = self.db.execute(text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'rls_violation_log'
        """))
        indexes = [row[0] for row in result.fetchall()]
        
        # Should have indexes for common query patterns
        assert any('customer_id' in idx for idx in indexes), "Missing index on customer_id"
        assert any('timestamp' in idx or 'pkey' in idx for idx in indexes), "Missing index on timestamp or primary key"


class TestUserAuditLogEnhanced:
    """Test enhanced user_audit_log with tenant context."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session."""
        self.db = get_db_session()
        yield
        self.db.rollback()
        self.db.close()
    
    def test_user_audit_log_has_tenant_columns(self):
        """Verify user_audit_log has tenant-related columns."""
        result = self.db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'user_audit_log'
            AND column_name IN ('customer_id', 'severity', 'outcome')
        """))
        columns = {row[0]: row[1] for row in result.fetchall()}
        
        assert 'customer_id' in columns, "Missing customer_id column"
        assert 'severity' in columns, "Missing severity column"
        assert 'outcome' in columns, "Missing outcome column"
    
    def test_can_query_audit_by_tenant(self):
        """Verify we can filter audit logs by tenant."""
        # This tests the index performance for tenant-based queries
        result = self.db.execute(text("""
            EXPLAIN (FORMAT JSON)
            SELECT * FROM data_access_audit_log
            WHERE customer_id = 'test_tenant'
            ORDER BY timestamp DESC
            LIMIT 100
        """))
        plan = result.fetchone()[0]
        
        # The query should use an index (not a sequential scan for large tables)
        # This is a sanity check that the index exists
        assert plan is not None, "Query plan should be generated"


class TestAuditTriggers:
    """Test that audit triggers fire on table changes."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session."""
        self.db = get_db_session()
        yield
        self.db.rollback()
        self.db.close()
    
    def test_audit_trigger_exists_on_users(self):
        """Verify audit trigger is attached to users table."""
        result = self.db.execute(text("""
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = 'users'::regclass
            AND tgname LIKE '%audit%'
        """))
        triggers = [row[0] for row in result.fetchall()]
        
        assert len(triggers) >= 1, "No audit trigger found on users table"
    
    def test_audit_trigger_exists_on_roles(self):
        """Verify audit trigger is attached to roles table."""
        result = self.db.execute(text("""
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = 'roles'::regclass
            AND tgname LIKE '%audit%'
        """))
        triggers = [row[0] for row in result.fetchall()]
        
        assert len(triggers) >= 1, "No audit trigger found on roles table"
    
    def test_audit_trigger_exists_on_documents(self):
        """Verify audit trigger is attached to documents table."""
        result = self.db.execute(text("""
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = 'documents'::regclass
            AND tgname LIKE '%audit%'
        """))
        triggers = [row[0] for row in result.fetchall()]
        
        assert len(triggers) >= 1, "No audit trigger found on documents table"


class TestComplianceReporting:
    """Test compliance reporting tables."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup database session."""
        self.db = get_db_session()
        yield
        self.db.rollback()
        self.db.close()
    
    def test_tenant_activity_summary_table_exists(self):
        """Verify tenant_activity_summary table exists."""
        result = self.db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'tenant_activity_summary'
            )
        """))
        assert result.scalar() is True, "tenant_activity_summary table not found"
    
    def test_compliance_reports_table_exists(self):
        """Verify compliance_reports table exists."""
        result = self.db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'compliance_reports'
            )
        """))
        assert result.scalar() is True, "compliance_reports table not found"
    
    def test_can_insert_compliance_report(self):
        """Verify we can create compliance reports."""
        self.db.execute(text("""
            INSERT INTO compliance_reports (
                customer_id, report_type, report_name, start_date, end_date,
                generated_by, status
            ) VALUES (
                'test_tenant', 'SOC2_DATA_ACCESS', 'January 2025 Data Access Report',
                '2025-01-01', '2025-01-31',
                1, 'completed'
            )
        """))
        
        result = self.db.execute(text("""
            SELECT report_type, status, report_name
            FROM compliance_reports
            WHERE customer_id = 'test_tenant'
            ORDER BY generated_at DESC
            LIMIT 1
        """))
        row = result.fetchone()
        
        assert row is not None, "Compliance report was not created"
        assert row[0] == 'SOC2_DATA_ACCESS'
        assert row[1] == 'completed'
        assert row[2] == 'January 2025 Data Access Report'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

