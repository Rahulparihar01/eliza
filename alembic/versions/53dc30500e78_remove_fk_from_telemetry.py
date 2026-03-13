"""remove_fk_from_telemetry

Revision ID: 53dc30500e78
Revises: 7e60333efb2e
Create Date: 2025-11-20 06:35:58.891793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53dc30500e78'
down_revision: Union[str, Sequence[str], None] = '7e60333efb2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["bi"]


def upgrade() -> None:
    """
    Remove Foreign Key constraint from data_analyst_telemetry.message_id
    
    Telemetry is observability data and should be independent of message lifecycle.
    Keeping message_id as indexed string for filtering, but no referential integrity.
    """
    # Drop the FK constraint
    op.drop_constraint(
        'fk_data_analyst_telemetry_message_id_data_analyst_messages',
        'data_analyst_telemetry',
        type_='foreignkey'
    )


def downgrade() -> None:
    """Re-add FK constraint (not recommended)."""
    op.create_foreign_key(
        'fk_data_analyst_telemetry_message_id_data_analyst_messages',
        'data_analyst_telemetry',
        'data_analyst_messages',
        ['message_id'],
        ['message_id'],
        ondelete='CASCADE'
    )
