"""add_connector_ingestion_tables

Revision ID: a1b2c3d4e5f6
Revises: 016_add_agent_configurations
Create Date: 2025-10-08 14:00:00.000000

Adds tables for data connector ingestion system:
- connector_configurations: Connector instances with queries
- connector_sync_runs: Sync execution tracking
- ingested_data: Raw data staging
- connector_telemetry: Real-time progress events
- pdl_persons: Normalized People Data Labs person records
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '016_add_agent_configurations'
branch_labels = None
depends_on = None
tags = ["connectors"]


def upgrade():
    # ConnectorConfiguration table
    op.create_table(
        'connector_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('connector_id', sa.String(100), nullable=False),
        sa.Column('connector_type', sa.String(50), nullable=False),
        sa.Column('connector_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('use_shared_credentials', sa.Boolean(), default=True),
        sa.Column('credentials_encrypted', sa.Text(), nullable=True),
        sa.Column('sync_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('sync_config_version', sa.Integer(), default=1),
        sa.Column('sync_config_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('max_records_per_sync', sa.Integer(), nullable=True),
        sa.Column('estimated_cost_per_sync', sa.Float(), nullable=True),
        sa.Column('total_cost_to_date', sa.Float(), default=0.0),
        sa.Column('sync_schedule', sa.String(100), nullable=True),
        sa.Column('sync_mode', sa.String(20), default='incremental'),
        sa.Column('is_enabled', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_healthy', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_check_message', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_connector_configurations_connector_id', 'connector_configurations', ['connector_id'], unique=True)
    op.create_index('ix_connector_configurations_customer_id', 'connector_configurations', ['customer_id'])
    op.create_index('ix_connector_customer_type', 'connector_configurations', ['customer_id', 'connector_type'])
    op.create_index('ix_connector_enabled', 'connector_configurations', ['is_enabled', 'customer_id'])
    
    # ConnectorSyncRun table
    op.create_table(
        'connector_sync_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_id', sa.String(100), nullable=False),
        sa.Column('connector_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('celery_task_id', sa.String(100), nullable=True),
        sa.Column('sync_mode', sa.String(20), nullable=False),
        sa.Column('triggered_by', sa.String(50), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('records_extracted', sa.Integer(), default=0),
        sa.Column('records_loaded', sa.Integer(), default=0),
        sa.Column('records_skipped', sa.Integer(), default=0),
        sa.Column('records_failed', sa.Integer(), default=0),
        sa.Column('checkpoint_before', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('checkpoint_after', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('api_calls_made', sa.Integer(), default=0),
        sa.Column('bytes_transferred', sa.Integer(), default=0),
        sa.Column('cost_incurred', sa.Float(), default=0.0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_configurations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_connector_sync_runs_sync_id', 'connector_sync_runs', ['sync_id'], unique=True)
    op.create_index('ix_connector_sync_runs_customer_id', 'connector_sync_runs', ['customer_id'])
    op.create_index('ix_connector_sync_runs_celery_task_id', 'connector_sync_runs', ['celery_task_id'])
    op.create_index('ix_connector_sync_runs_status', 'connector_sync_runs', ['status'])
    op.create_index('ix_sync_run_customer_status', 'connector_sync_runs', ['customer_id', 'status'])
    op.create_index('ix_sync_run_connector_created', 'connector_sync_runs', ['connector_id', 'created_at'])
    op.create_index('ix_sync_run_dates', 'connector_sync_runs', ['started_at', 'completed_at'])
    
    # IngestedData table
    op.create_table(
        'ingested_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('connector_id', sa.Integer(), nullable=False),
        sa.Column('sync_id', sa.String(100), nullable=False),
        sa.Column('source_record_id', sa.String(255), nullable=True),
        sa.Column('source_record_type', sa.String(50), nullable=True),
        sa.Column('company_dataset', sa.String(255), nullable=True),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(50), default='pending'),
        sa.Column('transformed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('transformed_record_type', sa.String(50), nullable=True),
        sa.Column('transformed_record_id', sa.Integer(), nullable=True),
        sa.Column('ingestion_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['connector_id'], ['connector_configurations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['sync_id'], ['connector_sync_runs.sync_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_ingested_data_customer_id', 'ingested_data', ['customer_id'])
    op.create_index('ix_ingested_data_sync_id', 'ingested_data', ['sync_id'])
    op.create_index('ix_ingested_data_source_record_id', 'ingested_data', ['source_record_id'])
    op.create_index('ix_ingested_data_company_dataset', 'ingested_data', ['company_dataset'])
    op.create_index('ix_ingested_data_status', 'ingested_data', ['status'])
    op.create_index('ix_ingested_customer_company', 'ingested_data', ['customer_id', 'company_dataset'])
    op.create_index('ix_ingested_status', 'ingested_data', ['customer_id', 'status'])
    op.create_index('ix_ingested_sync_status', 'ingested_data', ['sync_id', 'status'])
    op.create_index('ix_ingested_source_id', 'ingested_data', ['customer_id', 'source_record_id'])
    
    # ConnectorTelemetry table
    op.create_table(
        'connector_telemetry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sync_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('progress_percentage', sa.Float(), nullable=True),
        sa.Column('current_stage', sa.String(100), nullable=True),
        sa.Column('records_processed', sa.Integer(), default=0),
        sa.Column('api_calls_made', sa.Integer(), default=0),
        sa.Column('cost_so_far', sa.Float(), default=0.0),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('telemetry_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['sync_id'], ['connector_sync_runs.sync_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_connector_telemetry_sync_id', 'connector_telemetry', ['sync_id'])
    op.create_index('ix_telemetry_sync_timestamp', 'connector_telemetry', ['sync_id', 'event_timestamp'])
    
    # PDLPerson table
    op.create_table(
        'pdl_persons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pdl_id', sa.String(100), nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('middle_name', sa.String(100), nullable=True),
        sa.Column('job_title', sa.String(255), nullable=True),
        sa.Column('job_title_role', sa.String(100), nullable=True),
        sa.Column('job_title_sub_role', sa.String(100), nullable=True),
        sa.Column('job_title_levels', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('job_company_name', sa.String(255), nullable=True),
        sa.Column('job_company_id', sa.String(100), nullable=True),
        sa.Column('job_company_size', sa.String(50), nullable=True),
        sa.Column('job_company_industry', sa.String(100), nullable=True),
        sa.Column('job_company_location_name', sa.String(255), nullable=True),
        sa.Column('job_start_date', sa.String(50), nullable=True),
        sa.Column('primary_email', sa.String(255), nullable=True),
        sa.Column('emails', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('primary_phone', sa.String(50), nullable=True),
        sa.Column('phone_numbers', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('linkedin_username', sa.String(255), nullable=True),
        sa.Column('twitter_url', sa.String(500), nullable=True),
        sa.Column('github_url', sa.String(500), nullable=True),
        sa.Column('location_name', sa.String(255), nullable=True),
        sa.Column('location_locality', sa.String(100), nullable=True),
        sa.Column('location_metro', sa.String(100), nullable=True),
        sa.Column('location_region', sa.String(100), nullable=True),
        sa.Column('location_country', sa.String(100), nullable=True),
        sa.Column('location_continent', sa.String(50), nullable=True),
        sa.Column('skills', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('inferred_years_experience', sa.Integer(), nullable=True),
        sa.Column('education_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('work_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('pdl_likelihood', sa.Integer(), nullable=True),
        sa.Column('pdl_last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_seen_sync_id', sa.String(100), nullable=True),
        sa.Column('last_updated_sync_id', sa.String(100), nullable=True),
        sa.Column('sync_count', sa.Integer(), default=1),
        sa.Column('ingested_data_id', sa.Integer(), nullable=True),
        sa.Column('raw_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id']),
        sa.ForeignKeyConstraint(['ingested_data_id'], ['ingested_data.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_pdl_persons_pdl_id', 'pdl_persons', ['pdl_id'])
    op.create_index('ix_pdl_persons_customer_id', 'pdl_persons', ['customer_id'])
    op.create_index('ix_pdl_persons_full_name', 'pdl_persons', ['full_name'])
    op.create_index('ix_pdl_persons_job_title', 'pdl_persons', ['job_title'])
    op.create_index('ix_pdl_persons_job_title_role', 'pdl_persons', ['job_title_role'])
    op.create_index('ix_pdl_persons_job_company_name', 'pdl_persons', ['job_company_name'])
    op.create_index('ix_pdl_persons_linkedin_url', 'pdl_persons', ['linkedin_url'])
    op.create_index('ix_pdl_persons_location_country', 'pdl_persons', ['location_country'])
    op.create_index('ix_pdl_persons_primary_email', 'pdl_persons', ['primary_email'])
    op.create_index('ix_pdl_person_unique', 'pdl_persons', ['pdl_id', 'customer_id'], unique=True)
    op.create_index('ix_pdl_person_name', 'pdl_persons', ['first_name', 'last_name'])
    op.create_index('ix_pdl_person_company_role', 'pdl_persons', ['job_company_name', 'job_title_role'])
    op.create_index('ix_pdl_person_location', 'pdl_persons', ['location_country', 'location_region'])
    op.create_index('ix_pdl_person_email', 'pdl_persons', ['primary_email'])


def downgrade():
    op.drop_table('pdl_persons')
    op.drop_table('connector_telemetry')
    op.drop_table('ingested_data')
    op.drop_table('connector_sync_runs')
    op.drop_table('connector_configurations')

