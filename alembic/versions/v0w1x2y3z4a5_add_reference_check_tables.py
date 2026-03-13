"""add reference check tables

Revision ID: v0w1x2y3z4a5
Revises: u9v0w1x2y3z4
Create Date: 2025-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'v0w1x2y3z4a5'
down_revision = 'p1q2r3s4t5u6'
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade() -> None:
    # Get connection for direct SQL execution
    conn = op.get_bind()
    
    # Create enum types (idempotent - skip if already exists)
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE reference_request_status AS ENUM (
                'pending', 'references_requested', 'in_progress', 'completed', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE reference_status AS ENUM (
                'pending', 'scheduled', 'in_progress', 'completed', 'failed', 'declined', 'voicemail', 'callback_pending'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE relationship_type AS ENUM (
                'direct_manager', 'colleague', 'direct_report', 'client', 'other'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE question_type AS ENUM ('verbatim', 'concept');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE question_priority AS ENUM ('required', 'optional');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE call_status AS ENUM (
                'initiated', 'ringing', 'in_progress', 'completed', 'busy', 'no_answer', 'failed', 'voicemail'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE call_type AS ENUM ('outbound', 'inbound_callback', 'test', 'sandbox');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE scheduled_call_status AS ENUM (
                'scheduled', 'in_progress', 'completed', 'voicemail', 'callback_pending', 'cancelled'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """))
    
    # Create all tables using raw SQL with IF NOT EXISTS
    # This makes the migration completely idempotent
    
    # reference_check_requests table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_check_requests (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
            candidate_id INTEGER REFERENCES candidates(id),
            candidate_name VARCHAR(255) NOT NULL,
            candidate_email VARCHAR(255) NOT NULL,
            candidate_phone VARCHAR(50),
            job_id VARCHAR(255),
            job_title VARCHAR(255),
            greenhouse_candidate_id BIGINT,
            greenhouse_application_id BIGINT,
            status reference_request_status DEFAULT 'pending' NOT NULL,
            max_references INTEGER DEFAULT 10 NOT NULL,
            verification_token VARCHAR(255) UNIQUE,
            verification_expires_at TIMESTAMPTZ,
            verified_at TIMESTAMPTZ,
            created_by_user_id INTEGER REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcr_customer_id ON reference_check_requests(customer_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcr_candidate_id ON reference_check_requests(candidate_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcr_status ON reference_check_requests(status)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcr_verification_token ON reference_check_requests(verification_token)"))
    
    # candidate_references table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS candidate_references (
            id SERIAL PRIMARY KEY,
            request_id INTEGER NOT NULL REFERENCES reference_check_requests(id) ON DELETE CASCADE,
            full_name VARCHAR(255) NOT NULL,
            relationship_type relationship_type,
            company VARCHAR(255),
            title VARCHAR(255),
            phone_number VARCHAR(50) NOT NULL,
            email VARCHAR(255),
            preferred_contact_time VARCHAR(100),
            notes TEXT,
            status reference_status DEFAULT 'pending' NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cr_request_id ON candidate_references(request_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cr_phone_number ON candidate_references(phone_number)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cr_status ON candidate_references(status)"))
    
    # reference_call_templates table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_call_templates (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            is_default BOOLEAN DEFAULT FALSE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_by_user_id INTEGER REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rct_customer_id ON reference_call_templates(customer_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rct_is_default ON reference_call_templates(is_default)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rct_is_active ON reference_call_templates(is_active)"))
    
    # reference_template_questions table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_template_questions (
            id SERIAL PRIMARY KEY,
            template_id INTEGER NOT NULL REFERENCES reference_call_templates(id) ON DELETE CASCADE,
            question_text TEXT NOT NULL,
            question_type question_type DEFAULT 'concept' NOT NULL,
            priority question_priority DEFAULT 'required' NOT NULL,
            order_index INTEGER NOT NULL,
            follow_up_enabled BOOLEAN DEFAULT TRUE NOT NULL,
            max_follow_ups INTEGER DEFAULT 2 NOT NULL,
            expected_answer_type VARCHAR(50),
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rtq_template_id ON reference_template_questions(template_id)"))
    
    # reference_voice_personas table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_voice_personas (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
            name VARCHAR(255) NOT NULL,
            description TEXT,
            voice_model VARCHAR(100) DEFAULT 'alloy' NOT NULL,
            speaking_rate FLOAT DEFAULT 1.0 NOT NULL,
            tone VARCHAR(50) DEFAULT 'professional' NOT NULL,
            personality_traits JSONB,
            introduction_script TEXT,
            closing_script TEXT,
            is_default BOOLEAN DEFAULT FALSE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rvp_customer_id ON reference_voice_personas(customer_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rvp_is_default ON reference_voice_personas(is_default)"))
    
    # reference_consent_templates table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_consent_templates (
            id SERIAL PRIMARY KEY,
            jurisdiction VARCHAR(100) NOT NULL UNIQUE,
            consent_script TEXT NOT NULL,
            requires_explicit_consent BOOLEAN DEFAULT TRUE NOT NULL,
            legal_notes TEXT,
            is_active BOOLEAN DEFAULT TRUE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rconst_jurisdiction ON reference_consent_templates(jurisdiction)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rconst_is_active ON reference_consent_templates(is_active)"))
    
    # reference_scheduled_calls table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_scheduled_calls (
            id SERIAL PRIMARY KEY,
            reference_id INTEGER NOT NULL REFERENCES candidate_references(id) ON DELETE CASCADE,
            template_id INTEGER REFERENCES reference_call_templates(id),
            persona_id INTEGER REFERENCES reference_voice_personas(id),
            consent_template_id INTEGER REFERENCES reference_consent_templates(id),
            scheduled_at TIMESTAMPTZ NOT NULL,
            reminder_intervals JSONB DEFAULT '[86400, 7200, 900]' NOT NULL,
            reminder_24h_sent BOOLEAN DEFAULT FALSE NOT NULL,
            reminder_2h_sent BOOLEAN DEFAULT FALSE NOT NULL,
            reminder_15m_sent BOOLEAN DEFAULT FALSE NOT NULL,
            caller_id VARCHAR(50),
            status scheduled_call_status DEFAULT 'scheduled' NOT NULL,
            created_by_user_id INTEGER REFERENCES users(id),
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rsc_reference_id ON reference_scheduled_calls(reference_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rsc_scheduled_at ON reference_scheduled_calls(scheduled_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rsc_status ON reference_scheduled_calls(status)"))
    
    # reference_calls table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_calls (
            id SERIAL PRIMARY KEY,
            scheduled_call_id INTEGER REFERENCES reference_scheduled_calls(id),
            reference_id INTEGER REFERENCES candidate_references(id),
            twilio_call_sid VARCHAR(100) UNIQUE,
            call_type call_type DEFAULT 'outbound' NOT NULL,
            call_status call_status,
            consent_obtained BOOLEAN DEFAULT FALSE NOT NULL,
            consent_timestamp TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            duration_seconds INTEGER,
            recording_url TEXT,
            recording_duration_seconds INTEGER,
            recording_sid VARCHAR(100),
            is_complete BOOLEAN DEFAULT FALSE NOT NULL,
            incomplete_reason VARCHAR(100),
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rc_scheduled_call_id ON reference_calls(scheduled_call_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rc_reference_id ON reference_calls(reference_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rc_twilio_call_sid ON reference_calls(twilio_call_sid)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rc_call_type ON reference_calls(call_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rc_call_status ON reference_calls(call_status)"))
    
    # reference_call_transcripts table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_call_transcripts (
            id SERIAL PRIMARY KEY,
            call_id INTEGER NOT NULL REFERENCES reference_calls(id) ON DELETE CASCADE,
            full_transcript TEXT NOT NULL,
            transcript_segments JSONB NOT NULL,
            word_timestamps JSONB,
            language VARCHAR(10) DEFAULT 'en' NOT NULL,
            confidence_score FLOAT,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rctrans_call_id ON reference_call_transcripts(call_id)"))
    
    # reference_question_responses table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_question_responses (
            id SERIAL PRIMARY KEY,
            call_id INTEGER NOT NULL REFERENCES reference_calls(id) ON DELETE CASCADE,
            template_question_id INTEGER REFERENCES reference_template_questions(id),
            question_asked TEXT NOT NULL,
            response_text TEXT NOT NULL,
            response_sentiment VARCHAR(50),
            response_confidence FLOAT,
            transcript_start_time FLOAT,
            transcript_end_time FLOAT,
            follow_up_questions JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rqr_call_id ON reference_question_responses(call_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rqr_template_question_id ON reference_question_responses(template_question_id)"))
    
    # reference_call_summaries table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_call_summaries (
            id SERIAL PRIMARY KEY,
            call_id INTEGER NOT NULL REFERENCES reference_calls(id) ON DELETE CASCADE,
            executive_summary TEXT NOT NULL,
            key_strengths JSONB,
            areas_of_concern JSONB,
            notable_quotes JSONB,
            overall_sentiment VARCHAR(50),
            recommendation_score INTEGER,
            recommendation_notes TEXT,
            generated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcs_call_id ON reference_call_summaries(call_id)"))
    
    # reference_check_audit_log table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS reference_check_audit_log (
            id SERIAL PRIMARY KEY,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER NOT NULL,
            action VARCHAR(50) NOT NULL,
            user_id INTEGER REFERENCES users(id),
            user_role VARCHAR(50),
            ip_address VARCHAR(50),
            changes JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcal_entity_type ON reference_check_audit_log(entity_type)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcal_entity_id ON reference_check_audit_log(entity_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcal_user_id ON reference_check_audit_log(user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcal_action ON reference_check_audit_log(action)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_rcal_created_at ON reference_check_audit_log(created_at)"))
    
    # customer_caller_ids table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS customer_caller_ids (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL REFERENCES customers(customer_id),
            twilio_phone_number VARCHAR(50) NOT NULL,
            display_name VARCHAR(100),
            is_verified BOOLEAN DEFAULT FALSE NOT NULL,
            verification_sid VARCHAR(100),
            is_default BOOLEAN DEFAULT FALSE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            CONSTRAINT uq_customer_caller_id UNIQUE (customer_id, twilio_phone_number)
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cci_customer_id ON customer_caller_ids(customer_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_cci_is_default ON customer_caller_ids(is_default)"))
    
    # customer_call_settings table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS customer_call_settings (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR(100) NOT NULL UNIQUE REFERENCES customers(customer_id),
            max_call_duration_seconds INTEGER DEFAULT 1800 NOT NULL,
            hard_limit_seconds INTEGER DEFAULT 3600 NOT NULL,
            max_references_per_candidate INTEGER DEFAULT 10 NOT NULL,
            default_reminder_intervals JSONB DEFAULT '[86400, 7200, 900]' NOT NULL,
            default_persona_id INTEGER REFERENCES reference_voice_personas(id),
            default_template_id INTEGER REFERENCES reference_call_templates(id),
            default_consent_template VARCHAR(100) DEFAULT 'strict_compliance' NOT NULL,
            incomplete_call_action VARCHAR(50) DEFAULT 'save_partial' NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_ccs_customer_id ON customer_call_settings(customer_id)"))
    
    # Insert default consent templates (only if not already present)
    conn.execute(sa.text("""
        INSERT INTO reference_consent_templates (jurisdiction, consent_script, requires_explicit_consent, legal_notes, is_active)
        VALUES 
        ('us_one_party', 
         'Hi {reference_name}, this is {agent_name} calling on behalf of {company_name} regarding a professional reference for {candidate_name}. Before we begin, I want to let you know this call may be recorded for quality and documentation purposes. Is now still a good time to speak?',
         false,
         'Notification provided but explicit consent not legally required for one-party consent states',
         true),
        ('us_two_party',
         'Hi {reference_name}, this is {agent_name} calling on behalf of {company_name} regarding a professional reference for {candidate_name}. This call will be recorded for documentation purposes. Do I have your consent to record this conversation?',
         true,
         'Explicit verbal consent required before proceeding',
         true),
        ('california',
         'Hi {reference_name}, this is {agent_name} calling on behalf of {company_name} regarding a professional reference for {candidate_name}. Under California law, I am required to inform you that this call will be recorded. Do you consent to being recorded?',
         true,
         'California Penal Code Section 632 - explicit consent required',
         true),
        ('illinois',
         'Hi {reference_name}, this is {agent_name} calling on behalf of {company_name} regarding a professional reference for {candidate_name}. Illinois law requires me to inform you that this conversation will be recorded. Do I have your permission to proceed with the recording?',
         true,
         '720 ILCS 5/14-2 - explicit consent required',
         true),
        ('florida',
         'Hi {reference_name}, this is {agent_name} calling on behalf of {company_name} regarding a professional reference for {candidate_name}. Florida law requires all parties to consent to recording. Do I have your consent to record this call?',
         true,
         'Florida Statutes Section 934.03 - all-party consent required',
         true),
        ('strict_compliance',
         'Hi {reference_name}, this is {agent_name} calling on behalf of {company_name} regarding a professional reference for {candidate_name}. I want to be transparent that this call will be recorded for documentation and quality purposes. The recording helps us accurately capture your feedback. Do I have your explicit consent to record this conversation? You can say yes to consent or no to decline.',
         true,
         'Maximum compliance template - recommended default for all jurisdictions',
         true)
        ON CONFLICT (jurisdiction) DO NOTHING
    """))


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('ix_ccs_customer_id', table_name='customer_call_settings')
    op.drop_table('customer_call_settings')
    
    op.drop_index('ix_cci_is_default', table_name='customer_caller_ids')
    op.drop_index('ix_cci_customer_id', table_name='customer_caller_ids')
    op.drop_table('customer_caller_ids')
    
    op.drop_index('ix_rcal_created_at', table_name='reference_check_audit_log')
    op.drop_index('ix_rcal_action', table_name='reference_check_audit_log')
    op.drop_index('ix_rcal_user_id', table_name='reference_check_audit_log')
    op.drop_index('ix_rcal_entity_id', table_name='reference_check_audit_log')
    op.drop_index('ix_rcal_entity_type', table_name='reference_check_audit_log')
    op.drop_table('reference_check_audit_log')
    
    op.drop_index('ix_rcs_call_id', table_name='reference_call_summaries')
    op.drop_table('reference_call_summaries')
    
    op.drop_index('ix_rqr_template_question_id', table_name='reference_question_responses')
    op.drop_index('ix_rqr_call_id', table_name='reference_question_responses')
    op.drop_table('reference_question_responses')
    
    op.drop_index('ix_rctrans_call_id', table_name='reference_call_transcripts')
    op.drop_table('reference_call_transcripts')
    
    op.drop_index('ix_rc_call_status', table_name='reference_calls')
    op.drop_index('ix_rc_call_type', table_name='reference_calls')
    op.drop_index('ix_rc_twilio_call_sid', table_name='reference_calls')
    op.drop_index('ix_rc_reference_id', table_name='reference_calls')
    op.drop_index('ix_rc_scheduled_call_id', table_name='reference_calls')
    op.drop_table('reference_calls')
    
    op.drop_index('ix_rsc_status', table_name='reference_scheduled_calls')
    op.drop_index('ix_rsc_scheduled_at', table_name='reference_scheduled_calls')
    op.drop_index('ix_rsc_reference_id', table_name='reference_scheduled_calls')
    op.drop_table('reference_scheduled_calls')
    
    op.drop_index('ix_rconst_is_active', table_name='reference_consent_templates')
    op.drop_index('ix_rconst_jurisdiction', table_name='reference_consent_templates')
    op.drop_table('reference_consent_templates')
    
    op.drop_index('ix_rvp_is_default', table_name='reference_voice_personas')
    op.drop_index('ix_rvp_customer_id', table_name='reference_voice_personas')
    op.drop_table('reference_voice_personas')
    
    op.drop_index('ix_rtq_template_id', table_name='reference_template_questions')
    op.drop_table('reference_template_questions')
    
    op.drop_index('ix_rct_is_active', table_name='reference_call_templates')
    op.drop_index('ix_rct_is_default', table_name='reference_call_templates')
    op.drop_index('ix_rct_customer_id', table_name='reference_call_templates')
    op.drop_table('reference_call_templates')
    
    op.drop_index('ix_cr_status', table_name='candidate_references')
    op.drop_index('ix_cr_phone_number', table_name='candidate_references')
    op.drop_index('ix_cr_request_id', table_name='candidate_references')
    op.drop_table('candidate_references')
    
    op.drop_index('ix_rcr_verification_token', table_name='reference_check_requests')
    op.drop_index('ix_rcr_status', table_name='reference_check_requests')
    op.drop_index('ix_rcr_candidate_id', table_name='reference_check_requests')
    op.drop_index('ix_rcr_customer_id', table_name='reference_check_requests')
    op.drop_table('reference_check_requests')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS scheduled_call_status")
    op.execute("DROP TYPE IF EXISTS call_type")
    op.execute("DROP TYPE IF EXISTS call_status")
    op.execute("DROP TYPE IF EXISTS question_priority")
    op.execute("DROP TYPE IF EXISTS question_type")
    op.execute("DROP TYPE IF EXISTS relationship_type")
    op.execute("DROP TYPE IF EXISTS reference_status")
    op.execute("DROP TYPE IF EXISTS reference_request_status")
