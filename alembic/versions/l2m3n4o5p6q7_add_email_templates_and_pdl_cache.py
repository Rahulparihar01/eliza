"""Add email templates, PDL cache, and customer settings tables

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6_add_talent_feedback_table
Create Date: 2024-12-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'l2m3n4o5p6q7'
down_revision = '53dc30500e78'  # Updated to match current DB state
branch_labels = None
depends_on = None
tags = ["content", "connectors"]


def upgrade() -> None:
    # Create email_templates table
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('customer_id', sa.String(100), sa.ForeignKey('customers.customer_id'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=False, server_default='custom'),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('subject_is_ai_generated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('subject_ai_prompt', sa.Text(), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_email_template_customer', 'email_templates', ['customer_id'])
    op.create_index('ix_email_template_category', 'email_templates', ['customer_id', 'category'])
    op.create_index('ix_email_template_active', 'email_templates', ['customer_id', 'is_active'])

    # Create email_template_sections table
    op.create_table(
        'email_template_sections',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('email_templates.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('section_type', sa.String(50), nullable=False, server_default='static'),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('ai_prompt', sa.Text(), nullable=True),
        sa.Column('ai_context_fields', postgresql.JSON(), nullable=True),
        sa.Column('ai_tone', sa.String(50), nullable=True, server_default='professional'),
        sa.Column('ai_max_length', sa.Integer(), nullable=True, server_default='200'),
        sa.Column('section_name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_template_section_order', 'email_template_sections', ['template_id', 'order'])

    # Create generated_emails table
    op.create_table(
        'generated_emails',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('customer_id', sa.String(100), sa.ForeignKey('customers.customer_id'), nullable=False, index=True),
        sa.Column('template_id', sa.Integer(), sa.ForeignKey('email_templates.id'), nullable=True),
        sa.Column('candidate_id', sa.String(255), nullable=False, index=True),
        sa.Column('talent_analysis_id', sa.String(100), sa.ForeignKey('talent_analyses.analysis_id'), nullable=True),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('is_edited', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('original_subject', sa.Text(), nullable=True),
        sa.Column('original_body', sa.Text(), nullable=True),
        sa.Column('generation_context', postgresql.JSON(), nullable=True),
        sa.Column('generation_model', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_generated_email_candidate', 'generated_emails', ['customer_id', 'candidate_id'])
    op.create_index('ix_generated_email_analysis', 'generated_emails', ['talent_analysis_id'])

    # Create pdl_query_cache table
    op.create_table(
        'pdl_query_cache',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('customer_id', sa.String(100), sa.ForeignKey('customers.customer_id'), nullable=False, index=True),
        sa.Column('query_hash', sa.String(64), nullable=False, index=True),
        sa.Column('query_params', postgresql.JSON(), nullable=False),
        sa.Column('query_type', sa.String(50), nullable=False),
        sa.Column('result_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('result_pdl_ids', postgresql.JSON(), nullable=True),
        sa.Column('cache_hit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_hit_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index('ix_pdl_cache_query', 'pdl_query_cache', ['customer_id', 'query_hash'])
    op.create_index('ix_pdl_cache_expires', 'pdl_query_cache', ['expires_at'])

    # Create customer_settings table
    op.create_table(
        'customer_settings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('customer_id', sa.String(100), sa.ForeignKey('customers.customer_id'), nullable=False, unique=True, index=True),
        sa.Column('greenhouse_maildrop_address', sa.String(255), nullable=True),
        sa.Column('greenhouse_connector_id', sa.String(100), nullable=True),
        sa.Column('pdl_cache_ttl_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('pdl_max_results_per_query', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('default_email_template_id', sa.Integer(), sa.ForeignKey('email_templates.id'), nullable=True),
        sa.Column('email_signature', sa.Text(), nullable=True),
        sa.Column('sender_name', sa.String(255), nullable=True),
        sa.Column('sender_title', sa.String(255), nullable=True),
        sa.Column('ai_email_generation_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ai_model_preference', sa.String(100), nullable=False, server_default='gpt-4'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # Ensure the 'eliza' customer exists before inserting settings
    # Use a connection to check if customer exists first (more reliable than ON CONFLICT)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT customer_id FROM customers WHERE customer_id = 'eliza'"
    ))
    if not result.fetchone():
        conn.execute(sa.text("""
            INSERT INTO customers (customer_id, name, is_active, subscription_tier, 
                                   max_users, max_documents, max_api_calls_per_month,
                                   current_users, current_documents, api_calls_this_month,
                                   created_at, updated_at)
            VALUES ('eliza', 'Eliza Platform', true, 'enterprise',
                    100, 10000, 100000,
                    0, 0, 0,
                    NOW(), NOW())
        """))
    
    # Insert default settings for Eliza (only if not exists)
    result = conn.execute(sa.text(
        "SELECT customer_id FROM customer_settings WHERE customer_id = 'eliza'"
    ))
    if not result.fetchone():
        conn.execute(sa.text("""
            INSERT INTO customer_settings (customer_id, greenhouse_maildrop_address, pdl_cache_ttl_days)
            VALUES ('eliza', 'maildrop@lily.greenhouse.io', 30)
        """))


def downgrade() -> None:
    op.drop_table('customer_settings')
    op.drop_table('pdl_query_cache')
    op.drop_table('generated_emails')
    op.drop_table('email_template_sections')
    op.drop_table('email_templates')

