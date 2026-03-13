"""Add domain to GEPA optimizer jobs

Revision ID: zz13_gepa_job_domain
Revises: zz12_prompt_management
Create Date: 2026-01-19

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "zz13_gepa_job_domain"
down_revision = "zz12_prompt_management"
branch_labels = None
depends_on = None
tags = ["ai_console", "evals"]


def upgrade():
    op.add_column(
        "gepa_optimizer_jobs",
        sa.Column("domain", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_gepa_jobs_customer_domain",
        "gepa_optimizer_jobs",
        ["customer_id", "domain"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_gepa_jobs_customer_domain", table_name="gepa_optimizer_jobs")
    op.drop_column("gepa_optimizer_jobs", "domain")

