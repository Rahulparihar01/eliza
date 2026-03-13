"""Add domain prompt feedback table

Revision ID: zz15_pm_feedback
Revises: zz14_gepa_promo_rb
Create Date: 2026-01-19

"""

from alembic import op
import sqlalchemy as sa


revision = "zz15_pm_feedback"
down_revision = "zz14_gepa_promo_rb"
branch_labels = None
depends_on = None
tags = ["ai_console", "evals"]


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS domain_prompt_feedback (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            customer_id VARCHAR(100) NOT NULL,
            domain VARCHAR(100) NOT NULL,
            environment VARCHAR(20) NOT NULL DEFAULT 'prod',

            rating_numeric INTEGER NOT NULL DEFAULT -1,
            comment TEXT NOT NULL,
            tags JSON NULL,
            improvement_suggestions TEXT NULL,
            target_components JSON NULL,

            prompt_snapshot JSON NOT NULL,

            created_by_user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_domain_prompt_feedback_customer_domain_env
        ON domain_prompt_feedback (customer_id, domain, environment);
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS domain_prompt_feedback;")

