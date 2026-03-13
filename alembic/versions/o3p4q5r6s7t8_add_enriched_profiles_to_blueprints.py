"""Add source_pdl_person_ids to career_blueprints

Revision ID: o3p4q5r6s7t8
Revises: n2o3p4q5r6s7
Create Date: 2024-12-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'o3p4q5r6s7t8'
down_revision: Union[str, None] = 'n2o3p4q5r6s7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["talent"]


def upgrade() -> None:
    """Add source_pdl_person_ids column to career_blueprints table.
    
    This stores references to pdl_persons.id records rather than duplicating
    the full profile data. The enriched profile data is already cached in
    the pdl_persons table.
    
    NOTE: This migration is conditional - it only runs if the career_blueprints
    table exists. The table may not exist in all deployments.
    """
    conn = op.get_bind()
    
    # First check if the career_blueprints table exists at all
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='career_blueprints'"
    ))
    if not result.fetchone():
        # Table doesn't exist, skip this migration
        print("career_blueprints table does not exist, skipping migration")
        return
    
    # Check if old column exists and drop it
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='career_blueprints' AND column_name='source_enriched_profiles'"
    ))
    if result.fetchone():
        op.drop_column('career_blueprints', 'source_enriched_profiles')
    
    # Check if new column already exists before adding
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='career_blueprints' AND column_name='source_pdl_person_ids'"
    ))
    if not result.fetchone():
        op.add_column(
            'career_blueprints',
            sa.Column('source_pdl_person_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
        )


def downgrade() -> None:
    """Remove source_pdl_person_ids column from career_blueprints table."""
    conn = op.get_bind()
    
    # Check if table exists before trying to drop column
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='career_blueprints'"
    ))
    if result.fetchone():
        op.drop_column('career_blueprints', 'source_pdl_person_ids')

