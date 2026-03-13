"""Drop deprecated tenant role tables

The role system has been unified. These tables are no longer needed:
- tenant_roles -> use roles (with customer_id)
- tenant_role_permissions -> use role_permissions  
- tenant_user_roles -> use user_roles

Revision ID: x2y3z4a5b6c7
Revises: w1x2y3z4a5b6
Create Date: 2025-12-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = 'x2y3z4a5b6c7'
down_revision = 'w1x2y3z4a5b6'
branch_labels = None
depends_on = None
tags = ["auth", "tenancy"]


def upgrade():
    """Drop deprecated tenant role tables."""
    conn = op.get_bind()
    
    # Drop in order of dependencies
    conn.execute(text("DROP TABLE IF EXISTS tenant_user_roles CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS tenant_role_permissions CASCADE"))
    conn.execute(text("DROP TABLE IF EXISTS tenant_roles CASCADE"))


def downgrade():
    """Recreate the deprecated tables (for rollback purposes only)."""
    # tenant_roles
    op.create_table(
        'tenant_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('customer_id', sa.String(100), nullable=False),
        sa.Column('role_name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.customer_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'role_name', name='uq_tenant_role_name')
    )
    op.create_index('ix_tenant_roles_customer_id', 'tenant_roles', ['customer_id'])
    
    # tenant_role_permissions
    op.create_table(
        'tenant_role_permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('permission_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['tenant_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['permission_id'], ['feature_permissions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_tenant_role_permission')
    )
    
    # tenant_user_roles
    op.create_table(
        'tenant_user_roles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['tenant_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', name='uq_tenant_user_role')
    )

