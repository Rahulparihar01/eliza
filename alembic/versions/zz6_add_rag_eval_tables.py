"""Add RAG evaluation tables

Revision ID: zz6_add_rag_eval_tables
Revises: zz3_merge_heads
Create Date: 2026-01-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'zz6_add_rag_eval_tables'
down_revision: Union[str, None] = 'zz3_merge_heads'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["evals"]


def upgrade() -> None:
    # Create enum types using raw SQL with IF NOT EXISTS (PostgreSQL 9.1+)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE evalrunstatus AS ENUM ('pending', 'running', 'completed', 'failed', 'cancelled');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE evalverdict AS ENUM ('pass', 'fail', 'error');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Create rag_eval_runs table
    op.create_table(
        'rag_eval_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        
        # Configuration
        sa.Column('domain', sa.String(50), nullable=False, server_default='fasb'),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('difficulty_counts', sa.JSON(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=True, server_default='42'),
        sa.Column('concurrency', sa.Integer(), nullable=True, server_default='3'),
        
        # Model configuration snapshot
        sa.Column('chat_model', sa.String(100), nullable=True),
        sa.Column('embed_model', sa.String(100), nullable=True),
        sa.Column('judge_model', sa.String(100), nullable=True),
        sa.Column('knn_k', sa.Integer(), nullable=True),
        sa.Column('retrieve_size', sa.Integer(), nullable=True),
        sa.Column('rerank_keep', sa.Integer(), nullable=True),
        
        # Status and timing
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        
        # MLflow integration
        sa.Column('mlflow_run_id', sa.String(100), nullable=True),
        sa.Column('mlflow_experiment_name', sa.String(255), nullable=True),
        
        # Aggregate metrics
        sa.Column('total_questions', sa.Integer(), nullable=True),
        sa.Column('pass_count', sa.Integer(), nullable=True),
        sa.Column('fail_count', sa.Integer(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=True),
        sa.Column('pass_rate', sa.Float(), nullable=True),
        
        # RAGAS metrics means
        sa.Column('factual_correctness_mean', sa.Float(), nullable=True),
        sa.Column('faithfulness_mean', sa.Float(), nullable=True),
        sa.Column('context_precision_mean', sa.Float(), nullable=True),
        sa.Column('context_recall_mean', sa.Float(), nullable=True),
        sa.Column('citation_compliance_mean', sa.Float(), nullable=True),
        
        # Metrics by difficulty
        sa.Column('metrics_by_difficulty', sa.JSON(), nullable=True),
        
        # Artifact paths
        sa.Column('results_file_path', sa.String(500), nullable=True),
        sa.Column('failures_file_path', sa.String(500), nullable=True),
        sa.Column('summary_file_path', sa.String(500), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes
    op.create_index('ix_rag_eval_runs_run_id', 'rag_eval_runs', ['run_id'], unique=True)
    op.create_index('ix_rag_eval_runs_customer_id', 'rag_eval_runs', ['customer_id'])
    op.create_index('ix_rag_eval_runs_user_id', 'rag_eval_runs', ['user_id'])
    op.create_index('ix_rag_eval_runs_mlflow_run_id', 'rag_eval_runs', ['mlflow_run_id'])
    
    # Create rag_eval_results table
    op.create_table(
        'rag_eval_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('eval_run_id', sa.Integer(), nullable=False),
        
        # Question identification
        sa.Column('eval_id', sa.String(100), nullable=False),
        sa.Column('question_index', sa.Integer(), nullable=False),
        
        # Question content
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('expected_answer', sa.Text(), nullable=False),
        sa.Column('difficulty', sa.String(50), nullable=True),
        
        # Model response
        sa.Column('model_response', sa.Text(), nullable=True),
        
        # Verdict
        sa.Column('verdict', sa.String(20), nullable=True),
        sa.Column('verdict_reason', sa.Text(), nullable=True),
        
        # Citations
        sa.Column('citations', sa.JSON(), nullable=True),
        sa.Column('citation_compliance', sa.Integer(), nullable=True),
        
        # Contexts
        sa.Column('contexts_count', sa.Integer(), nullable=True),
        
        # RAGAS metrics
        sa.Column('factual_correctness', sa.Float(), nullable=True),
        sa.Column('faithfulness', sa.Float(), nullable=True),
        sa.Column('context_precision', sa.Float(), nullable=True),
        sa.Column('context_recall', sa.Float(), nullable=True),
        
        # MLflow trace
        sa.Column('mlflow_trace_id', sa.String(100), nullable=True),
        
        # Timing
        sa.Column('processing_time_ms', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['eval_run_id'], ['rag_eval_runs.id'], ondelete='CASCADE'),
    )
    
    # Create indexes
    op.create_index('ix_rag_eval_results_eval_run_id', 'rag_eval_results', ['eval_run_id'])
    
    # Create rag_eval_telemetry_events table
    op.create_table(
        'rag_eval_telemetry_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('eval_run_id', sa.Integer(), nullable=False),
        
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('stage_name', sa.String(100), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['eval_run_id'], ['rag_eval_runs.id'], ondelete='CASCADE'),
    )
    
    # Create index
    op.create_index('ix_rag_eval_telemetry_events_eval_run_id', 'rag_eval_telemetry_events', ['eval_run_id'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('rag_eval_telemetry_events')
    op.drop_table('rag_eval_results')
    op.drop_table('rag_eval_runs')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS evalverdict')
    op.execute('DROP TYPE IF EXISTS evalrunstatus')

