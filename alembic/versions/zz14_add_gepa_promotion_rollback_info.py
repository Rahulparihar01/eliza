"""Add rollback_info to GEPA promotion history

Revision ID: zz14_gepa_promo_rb
Revises: zz13_gepa_job_domain
Create Date: 2026-01-19

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
# IMPORTANT: alembic_version.version_num is varchar(32) in this DB.
revision = "zz14_gepa_promo_rb"
down_revision = "zz13_gepa_job_domain"
branch_labels = None
depends_on = None
tags = ["ai_console", "evals"]


def upgrade():
    op.add_column(
        "gepa_promoted_variant_history",
        sa.Column("rollback_info", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("gepa_promoted_variant_history", "rollback_info")

