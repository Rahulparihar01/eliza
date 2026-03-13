"""Add business intelligence schema

Revision ID: 014_bi_schema
Revises: 013_add_hr_summary_views
Create Date: 2025-10-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '014_bi_schema'
down_revision = '013_add_hr_summary_views'
branch_labels = None
depends_on = None
tags = ["bi"]


def upgrade() -> None:
    """Create business intelligence tables for Q&A system."""
    
    # Create enum types if they don't exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE question_status AS ENUM (
                'pending',
                'enriching',
                'analyzing',
                'completed',
                'failed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;

        DO $$ BEGIN
            CREATE TYPE agent_status AS ENUM (
                'pending',
                'running',
                'completed',
                'failed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;

        DO $$ BEGIN
            CREATE TYPE telemetry_event_type AS ENUM (
                'agent_started',
                'agent_completed',
                'agent_failed',
                'tool_called',
                'tool_completed',
                'tool_failed',
                'stage_started',
                'stage_completed',
                'stage_failed',
                'progress_update'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # 1. Business Intelligence Questions
    op.create_table(
        'bi_questions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=100), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('original_question', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'enriching', 'analyzing', 'completed', 'failed', name='question_status', create_type=False), nullable=False),
        sa.Column('enriched_prompt_id', sa.Integer(), nullable=True),
        sa.Column('analysis_session_id', sa.Integer(), nullable=True),
        sa.Column('result_id', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('question_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('question_id', name='uq_question_id')
    )
    op.create_index('idx_bi_questions_user', 'bi_questions', ['user_id'])
    op.create_index('idx_bi_questions_customer', 'bi_questions', ['customer_id'])
    op.create_index('idx_bi_questions_status', 'bi_questions', ['status'])
    op.create_index('idx_bi_questions_session', 'bi_questions', ['session_id'])
    op.create_index('idx_bi_questions_created', 'bi_questions', ['created_at'])
    
    # 2. Enriched Prompts (from Task Enrichment Flow)
    op.create_table(
        'bi_enriched_prompts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prompt_id', sa.String(length=100), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('original_input', sa.Text(), nullable=False),
        sa.Column('enriched_prompt', sa.Text(), nullable=False),
        sa.Column('intent_type', sa.String(length=100), nullable=True),
        sa.Column('complexity', sa.String(length=50), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('processing_instructions', sa.JSON(), nullable=True),
        sa.Column('expected_output_format', sa.JSON(), nullable=True),
        sa.Column('validation_criteria', sa.JSON(), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('user_context', sa.JSON(), nullable=True),
        sa.Column('rag_context', sa.JSON(), nullable=True),
        sa.Column('enrichment_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['bi_questions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prompt_id', name='uq_prompt_id')
    )
    op.create_index('idx_bi_enriched_prompts_question', 'bi_enriched_prompts', ['question_id'])
    op.create_index('idx_bi_enriched_prompts_intent', 'bi_enriched_prompts', ['intent_type'])
    op.create_index('idx_bi_enriched_prompts_created', 'bi_enriched_prompts', ['created_at'])
    
    # 3. Analysis Sessions (tracks the data retrieval & analysis flow)
    op.create_table(
        'bi_analysis_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=100), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('enriched_prompt_id', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'completed', 'failed', name='agent_status', create_type=False), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('agents_executed', sa.JSON(), nullable=True),
        sa.Column('tools_used', sa.JSON(), nullable=True),
        sa.Column('data_sources_queried', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('session_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['bi_questions.id']),
        sa.ForeignKeyConstraint(['enriched_prompt_id'], ['bi_enriched_prompts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', name='uq_session_id')
    )
    op.create_index('idx_bi_analysis_sessions_question', 'bi_analysis_sessions', ['question_id'])
    op.create_index('idx_bi_analysis_sessions_status', 'bi_analysis_sessions', ['status'])
    op.create_index('idx_bi_analysis_sessions_created', 'bi_analysis_sessions', ['created_at'])
    
    # 4. Agent Telemetry (real-time agent execution tracking)
    op.create_table(
        'bi_agent_telemetry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telemetry_id', sa.String(length=100), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', postgresql.ENUM('agent_started', 'agent_completed', 'agent_failed', 'tool_called', 'tool_completed', 'tool_failed', 'stage_started', 'stage_completed', 'stage_failed', 'progress_update', name='telemetry_event_type', create_type=False), nullable=False),
        sa.Column('agent_name', sa.String(length=255), nullable=True),
        sa.Column('tool_name', sa.String(length=255), nullable=True),
        sa.Column('stage_name', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['bi_analysis_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telemetry_id', name='uq_telemetry_id')
    )
    op.create_index('idx_bi_agent_telemetry_session', 'bi_agent_telemetry', ['session_id'])
    op.create_index('idx_bi_agent_telemetry_event_type', 'bi_agent_telemetry', ['event_type'])
    op.create_index('idx_bi_agent_telemetry_timestamp', 'bi_agent_telemetry', ['timestamp'])
    
    # 5. Analysis Results (final output from analysis flow)
    op.create_table(
        'bi_analysis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('result_id', sa.String(length=100), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('analysis_text', sa.Text(), nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=True),
        sa.Column('key_findings', sa.JSON(), nullable=True),
        sa.Column('data_sources_used', sa.JSON(), nullable=True),
        sa.Column('hr_data_queried', sa.JSON(), nullable=True),
        sa.Column('documents_referenced', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('recommendations', sa.JSON(), nullable=True),
        sa.Column('visualizations', sa.JSON(), nullable=True),
        sa.Column('result_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['question_id'], ['bi_questions.id']),
        sa.ForeignKeyConstraint(['session_id'], ['bi_analysis_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('result_id', name='uq_result_id')
    )
    op.create_index('idx_bi_analysis_results_question', 'bi_analysis_results', ['question_id'])
    op.create_index('idx_bi_analysis_results_session', 'bi_analysis_results', ['session_id'])
    op.create_index('idx_bi_analysis_results_created', 'bi_analysis_results', ['created_at'])
    
    # Add foreign key constraints back to bi_questions
    op.create_foreign_key(
        'fk_bi_questions_enriched_prompt',
        'bi_questions', 'bi_enriched_prompts',
        ['enriched_prompt_id'], ['id']
    )
    op.create_foreign_key(
        'fk_bi_questions_analysis_session',
        'bi_questions', 'bi_analysis_sessions',
        ['analysis_session_id'], ['id']
    )
    op.create_foreign_key(
        'fk_bi_questions_result',
        'bi_questions', 'bi_analysis_results',
        ['result_id'], ['id']
    )


def downgrade() -> None:
    """Drop business intelligence tables."""
    # Drop tables in reverse order
    op.drop_table('bi_analysis_results')
    op.drop_table('bi_agent_telemetry')
    op.drop_table('bi_analysis_sessions')
    op.drop_table('bi_enriched_prompts')
    op.drop_table('bi_questions')
    
    # Drop enum types
    op.execute("""
        DROP TYPE IF EXISTS telemetry_event_type;
        DROP TYPE IF EXISTS agent_status;
        DROP TYPE IF EXISTS question_status;
    """)

