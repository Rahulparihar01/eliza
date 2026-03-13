"""Add agent configurations table and provider name column

Revision ID: 016_add_agent_configurations
Revises: 015_bi_tool_executions
Create Date: 2025-01-08 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '016_add_agent_configurations'
down_revision = '015_bi_tool_executions'
branch_labels = None
depends_on = None
tags = ["core"]


def upgrade() -> None:
    """Add agent configurations table and provider name column."""
    
    # Add missing columns to customer_ai_providers
    # Check if columns exist before adding (for idempotency)
    from sqlalchemy import inspect
    from sqlalchemy import create_engine
    
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_columns = [c['name'] for c in inspector.get_columns('customer_ai_providers')]
    
    # Add name column
    if 'name' not in existing_columns:
        op.add_column('customer_ai_providers', 
            sa.Column('name', sa.String(length=255), nullable=True)
        )
    
    # Add is_enabled column (rename from is_active for consistency)
    if 'is_enabled' not in existing_columns and 'is_active' in existing_columns:
        # Rename is_active to is_enabled
        op.alter_column('customer_ai_providers', 'is_active', new_column_name='is_enabled')
    elif 'is_enabled' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true')
        )
    
    # Add priority column
    if 'priority' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('priority', sa.Integer(), nullable=False, server_default='1')
        )
    
    # Add max_requests_per_minute column
    if 'max_requests_per_minute' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('max_requests_per_minute', sa.Integer(), nullable=False, server_default='60')
        )
    
    # Add max_tokens_per_request column
    if 'max_tokens_per_request' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('max_tokens_per_request', sa.Integer(), nullable=False, server_default='4000')
        )
    
    # Add is_healthy column
    if 'is_healthy' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('is_healthy', sa.Boolean(), nullable=False, server_default='true')
        )
    
    # Add last_health_check column
    if 'last_health_check' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True)
        )
    
    # Add error_count column
    if 'error_count' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('error_count', sa.Integer(), nullable=False, server_default='0')
        )
    
    # Add last_error column
    if 'last_error' not in existing_columns:
        op.add_column('customer_ai_providers',
            sa.Column('last_error', sa.Text(), nullable=True)
        )
    
    # Populate name column with default values for existing records
    # Format: "{provider_name} Config {id}"
    op.execute("""
        UPDATE customer_ai_providers
        SET name = CONCAT(INITCAP(provider_name), ' Config ', id::text)
        WHERE name IS NULL
    """)
    
    # Create agent_configurations table
    op.create_table(
        'agent_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.String(length=255), nullable=False),
        sa.Column('flow_identifier', sa.String(length=255), nullable=False),
        sa.Column('agent_identifier', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('backstory', sa.Text(), nullable=True),
        sa.Column('model_id', sa.String(length=255), nullable=True),
        sa.Column('provider_config_id', sa.Integer(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('enabled_tools', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tool_configs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('updated_by', sa.String(length=50), nullable=True),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['provider_config_id'], ['customer_ai_providers.id'], ),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ),
        sa.UniqueConstraint('customer_id', 'flow_identifier', 'agent_identifier', 
                          name='uq_agent_config_customer_flow_agent')
    )
    
    # Create indexes
    op.create_index(
        'ix_agent_configurations_customer_id', 
        'agent_configurations', 
        ['customer_id']
    )
    op.create_index(
        'ix_agent_configurations_lookup', 
        'agent_configurations', 
        ['customer_id', 'flow_identifier', 'agent_identifier']
    )
    op.create_index(
        'ix_agent_configurations_provider',
        'agent_configurations',
        ['provider_config_id']
    )


def downgrade() -> None:
    """Remove agent configurations table and provider name column."""
    
    # Drop indexes
    op.drop_index('ix_agent_configurations_provider', table_name='agent_configurations')
    op.drop_index('ix_agent_configurations_lookup', table_name='agent_configurations')
    op.drop_index('ix_agent_configurations_customer_id', table_name='agent_configurations')
    
    # Drop table
    op.drop_table('agent_configurations')
    
    # Drop name column from customer_ai_providers
    op.drop_column('customer_ai_providers', 'name')

