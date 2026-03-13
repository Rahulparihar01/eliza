"""add_greenhouse_profile_url_to_candidates

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2025-11-10 15:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None
tags = ["talent"]


def upgrade() -> None:
    # Add Greenhouse integration fields to talent_analysis_candidates table
    op.add_column(
        'talent_analysis_candidates',
        sa.Column('greenhouse_candidate_id', sa.Integer(), nullable=True, comment='Greenhouse candidate ID if candidate exists in Greenhouse')
    )
    op.add_column(
        'talent_analysis_candidates',
        sa.Column('greenhouse_profile_url', sa.String(length=500), nullable=True, comment='Direct link to candidate profile in Greenhouse')
    )
    
    # Create index for faster lookups by Greenhouse candidate ID
    op.create_index(
        'ix_talent_analysis_candidates_greenhouse_id',
        'talent_analysis_candidates',
        ['greenhouse_candidate_id'],
        unique=False
    )


def downgrade() -> None:
    # Remove index
    op.drop_index('ix_talent_analysis_candidates_greenhouse_id', table_name='talent_analysis_candidates')
    
    # Remove columns
    op.drop_column('talent_analysis_candidates', 'greenhouse_profile_url')
    op.drop_column('talent_analysis_candidates', 'greenhouse_candidate_id')


