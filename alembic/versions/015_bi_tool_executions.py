"""Add BI tool executions and agent responses tracking

Revision ID: 015_bi_tool_executions
Revises: 014_bi_schema
Create Date: 2025-10-06 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015_bi_tool_executions'
down_revision = '8e1e22f1d4ab'
branch_labels = None
depends_on = None
tags = ["bi"]


def upgrade() -> None:
    """Add tables for detailed tool executions and agent responses."""
    
    # 1. Tool Executions Table - Captures every tool call with inputs/outputs
    op.create_table(
        'bi_tool_executions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.String(length=100), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.String(length=255), nullable=True),
        sa.Column('tool_name', sa.String(length=255), nullable=False),
        sa.Column('tool_input', sa.JSON(), nullable=True),  # Input parameters passed to tool
        sa.Column('tool_output', sa.JSON(), nullable=True),  # Results returned by tool
        sa.Column('status', sa.String(length=50), nullable=False),  # success, failed, timeout
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('results_count', sa.Integer(), nullable=True),  # Number of results returned
        sa.Column('execution_metadata', sa.JSON(), nullable=True),  # Additional context
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['bi_analysis_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('execution_id', name='uq_execution_id')
    )
    op.create_index('idx_bi_tool_executions_session', 'bi_tool_executions', ['session_id'])
    op.create_index('idx_bi_tool_executions_tool_name', 'bi_tool_executions', ['tool_name'])
    op.create_index('idx_bi_tool_executions_started', 'bi_tool_executions', ['started_at'])
    
    # 2. Agent Responses Table - Captures agent reasoning and outputs at each stage
    op.create_table(
        'bi_agent_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('response_id', sa.String(length=100), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('enriched_prompt_id', sa.Integer(), nullable=True),
        sa.Column('agent_name', sa.String(length=255), nullable=False),
        sa.Column('stage_name', sa.String(length=255), nullable=True),  # enrichment, retrieval, analysis
        sa.Column('input_prompt', sa.Text(), nullable=True),  # Prompt given to agent
        sa.Column('response_text', sa.Text(), nullable=False),  # Agent's response
        sa.Column('reasoning', sa.Text(), nullable=True),  # Agent's reasoning process
        sa.Column('tool_calls', sa.JSON(), nullable=True),  # List of tools called during this response
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('response_metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['bi_analysis_sessions.id']),
        sa.ForeignKeyConstraint(['enriched_prompt_id'], ['bi_enriched_prompts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('response_id', name='uq_response_id')
    )
    op.create_index('idx_bi_agent_responses_session', 'bi_agent_responses', ['session_id'])
    op.create_index('idx_bi_agent_responses_agent', 'bi_agent_responses', ['agent_name'])
    op.create_index('idx_bi_agent_responses_stage', 'bi_agent_responses', ['stage_name'])
    op.create_index('idx_bi_agent_responses_created', 'bi_agent_responses', ['created_at'])
    
    # 3. Add columns to bi_enriched_prompts for better tracking
    op.add_column('bi_enriched_prompts', sa.Column('agent_response_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_bi_enriched_prompts_agent_response',
        'bi_enriched_prompts', 'bi_agent_responses',
        ['agent_response_id'], ['id']
    )


def downgrade() -> None:
    """Remove tool executions and agent responses tables."""
    
    # Drop foreign key and column from bi_enriched_prompts
    op.drop_constraint('fk_bi_enriched_prompts_agent_response', 'bi_enriched_prompts', type_='foreignkey')
    op.drop_column('bi_enriched_prompts', 'agent_response_id')
    
    # Drop indices and tables
    op.drop_index('idx_bi_agent_responses_created', table_name='bi_agent_responses')
    op.drop_index('idx_bi_agent_responses_stage', table_name='bi_agent_responses')
    op.drop_index('idx_bi_agent_responses_agent', table_name='bi_agent_responses')
    op.drop_index('idx_bi_agent_responses_session', table_name='bi_agent_responses')
    op.drop_table('bi_agent_responses')
    
    op.drop_index('idx_bi_tool_executions_started', table_name='bi_tool_executions')
    op.drop_index('idx_bi_tool_executions_tool_name', table_name='bi_tool_executions')
    op.drop_index('idx_bi_tool_executions_session', table_name='bi_tool_executions')
    op.drop_table('bi_tool_executions')

