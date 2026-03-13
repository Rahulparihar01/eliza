"""add greenhouse connector support

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2025-10-23 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'e5f6g7h8i9j0'  # Fixed: points to actual previous migration
branch_labels = None
depends_on = None
tags = ["connectors"]


def upgrade():
    """Add Greenhouse connector support.
    
    connector_type is a VARCHAR(50), not an enum, so no schema changes needed.
    Greenhouse is already supported as a valid connector_type value.
    """
    # No changes needed - connector_type is VARCHAR, accepts any string
    pass


def downgrade():
    """
    Cannot remove enum values in PostgreSQL without recreating the type.
    This is a forward-only migration.
    """
    pass

