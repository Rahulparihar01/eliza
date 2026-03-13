"""Add GEPA Optimizer tables

Revision ID: zz10_gepa_optimizer
Revises: zz9_validate_citations
Create Date: 2026-01-16 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'zz10_gepa_optimizer'
down_revision: Union[str, None] = 'zz9_validate_citations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["ai_console", "evals"]


def upgrade() -> None:
    # Create enum types
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE optimizer_job_status AS ENUM ('pending', 'running', 'paused', 'completed', 'failed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE variant_status AS ENUM ('pending', 'evaluating', 'evaluated', 'failed', 'promoted');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE mutation_type AS ENUM (
                'rephrase', 'expand', 'compress', 'restructure', 
                'add_constraint', 'remove_constraint', 'crossover', 
                'reflection_guided', 'error_targeted'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create gepa_optimizer_jobs table
    op.create_table(
        'gepa_optimizer_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('agent_config_id', sa.Integer(), nullable=True),
        sa.Column('eval_suite_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('target_components', postgresql.JSON(), nullable=False),
        sa.Column('baseline_components', postgresql.JSON(), nullable=False),
        sa.Column('population_size', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_iterations', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('eval_budget', sa.Integer(), nullable=False, server_default='500'),
        sa.Column('mutation_rate', sa.Float(), nullable=False, server_default='0.3'),
        sa.Column('crossover_rate', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('elite_count', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('objective_weights', postgresql.JSON(), nullable=True),
        sa.Column('objectives', postgresql.JSON(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'running', 'paused', 'completed', 'failed', 'cancelled', name='optimizer_job_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('current_iteration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_evals_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('best_variant_id', sa.Integer(), nullable=True),
        sa.Column('best_quality_score', sa.Float(), nullable=True),
        sa.Column('celery_task_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['agent_config_id'], ['agent_configurations.id'], ondelete='SET NULL'),
    )
    
    op.create_index('ix_gepa_jobs_job_id', 'gepa_optimizer_jobs', ['job_id'], unique=True)
    op.create_index('ix_gepa_jobs_customer_id', 'gepa_optimizer_jobs', ['customer_id'])
    op.create_index('ix_gepa_jobs_user_id', 'gepa_optimizer_jobs', ['user_id'])
    op.create_index('ix_gepa_jobs_customer_status', 'gepa_optimizer_jobs', ['customer_id', 'status'])
    
    # Create gepa_candidate_variants table
    op.create_table(
        'gepa_candidate_variants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.String(100), nullable=False),
        sa.Column('generation', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_variant_ids', postgresql.JSON(), nullable=True),
        sa.Column('mutation_type', postgresql.ENUM('rephrase', 'expand', 'compress', 'restructure', 'add_constraint', 'remove_constraint', 'crossover', 'reflection_guided', 'error_targeted', name='mutation_type', create_type=False), nullable=True),
        sa.Column('component_values', postgresql.JSON(), nullable=False),
        sa.Column('component_diffs', postgresql.JSON(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'evaluating', 'evaluated', 'failed', 'promoted', name='variant_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('groundedness_score', sa.Float(), nullable=True),
        sa.Column('citation_accuracy', sa.Float(), nullable=True),
        sa.Column('avg_latency_ms', sa.Float(), nullable=True),
        sa.Column('avg_cost', sa.Float(), nullable=True),
        sa.Column('pareto_rank', sa.Integer(), nullable=True),
        sa.Column('crowding_distance', sa.Float(), nullable=True),
        sa.Column('is_baseline', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_promoted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('promoted_at', sa.DateTime(), nullable=True),
        sa.Column('promoted_to', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['gepa_optimizer_jobs.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('job_id', 'variant_id', name='uq_job_variant'),
    )
    
    op.create_index('ix_gepa_variants_job_id', 'gepa_candidate_variants', ['job_id'])
    op.create_index('ix_gepa_variants_job_generation', 'gepa_candidate_variants', ['job_id', 'generation'])
    op.create_index('ix_gepa_variants_pareto_rank', 'gepa_candidate_variants', ['job_id', 'pareto_rank'])
    
    # Add foreign key from jobs to best_variant (after variants table exists)
    op.create_foreign_key(
        'fk_gepa_jobs_best_variant',
        'gepa_optimizer_jobs', 'gepa_candidate_variants',
        ['best_variant_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Create gepa_evaluation_results table
    op.create_table(
        'gepa_evaluation_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('eval_case_id', sa.String(100), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('expected_answer', sa.Text(), nullable=True),
        sa.Column('model_response', sa.Text(), nullable=True),
        sa.Column('factual_correctness', sa.Float(), nullable=True),
        sa.Column('faithfulness', sa.Float(), nullable=True),
        sa.Column('context_precision', sa.Float(), nullable=True),
        sa.Column('context_recall', sa.Float(), nullable=True),
        sa.Column('citation_compliance', sa.Float(), nullable=True),
        sa.Column('answer_relevance', sa.Float(), nullable=True),
        sa.Column('verdict', sa.String(20), nullable=True),
        sa.Column('verdict_reason', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('tool_calls', postgresql.JSON(), nullable=True),
        sa.Column('retrieved_docs', postgresql.JSON(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['variant_id'], ['gepa_candidate_variants.id'], ondelete='CASCADE'),
    )
    
    op.create_index('ix_gepa_eval_results_variant', 'gepa_evaluation_results', ['variant_id'])
    
    # Create gepa_trace_artifacts table
    op.create_table(
        'gepa_trace_artifacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('trace_id', sa.String(100), nullable=False),
        sa.Column('eval_case_id', sa.String(100), nullable=True),
        sa.Column('trace_type', sa.String(50), nullable=False),
        sa.Column('trace_data', postgresql.JSON(), nullable=False),
        sa.Column('total_latency_ms', sa.Float(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=True),
        sa.Column('step_count', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('reflection_insights', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['variant_id'], ['gepa_candidate_variants.id'], ondelete='CASCADE'),
    )
    
    op.create_index('ix_gepa_traces_variant_type', 'gepa_trace_artifacts', ['variant_id', 'trace_type'])
    
    # Create gepa_pareto_snapshots table
    op.create_table(
        'gepa_pareto_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('iteration', sa.Integer(), nullable=False),
        sa.Column('frontier_variant_ids', postgresql.JSON(), nullable=False),
        sa.Column('frontier_count', sa.Integer(), nullable=False),
        sa.Column('frontier_stats', postgresql.JSON(), nullable=False),
        sa.Column('hypervolume', sa.Float(), nullable=True),
        sa.Column('diversity_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['gepa_optimizer_jobs.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('job_id', 'iteration', name='uq_job_iteration'),
    )
    
    op.create_index('ix_gepa_pareto_job_iteration', 'gepa_pareto_snapshots', ['job_id', 'iteration'])
    
    # Create gepa_telemetry_events table
    op.create_table(
        'gepa_telemetry_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('stage_name', sa.String(100), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('data', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['job_id'], ['gepa_optimizer_jobs.id'], ondelete='CASCADE'),
    )
    
    op.create_index('ix_gepa_telemetry_job_id', 'gepa_telemetry_events', ['job_id'])
    
    # Create gepa_promoted_variant_history table
    op.create_table(
        'gepa_promoted_variant_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('variant_snapshot', postgresql.JSON(), nullable=False),
        sa.Column('environment', sa.String(50), nullable=False),
        sa.Column('promoted_by_user_id', sa.Integer(), nullable=False),
        sa.Column('agent_config_id', sa.Integer(), nullable=True),
        sa.Column('previous_values', postgresql.JSON(), nullable=True),
        sa.Column('scores_at_promotion', postgresql.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_rolled_back', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('rolled_back_at', sa.DateTime(), nullable=True),
        sa.Column('rolled_back_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['variant_id'], ['gepa_candidate_variants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['gepa_optimizer_jobs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['promoted_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['agent_config_id'], ['agent_configurations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rolled_back_by_user_id'], ['users.id']),
    )
    
    op.create_index('ix_gepa_promoted_env_time', 'gepa_promoted_variant_history', ['environment', 'created_at'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('gepa_promoted_variant_history')
    op.drop_table('gepa_telemetry_events')
    op.drop_table('gepa_pareto_snapshots')
    op.drop_table('gepa_trace_artifacts')
    op.drop_table('gepa_evaluation_results')
    
    # Drop foreign key before dropping variants table
    op.drop_constraint('fk_gepa_jobs_best_variant', 'gepa_optimizer_jobs', type_='foreignkey')
    
    op.drop_table('gepa_candidate_variants')
    op.drop_table('gepa_optimizer_jobs')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS mutation_type')
    op.execute('DROP TYPE IF EXISTS variant_status')
    op.execute('DROP TYPE IF EXISTS optimizer_job_status')
