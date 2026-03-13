"""Switch adoption scheduling to dispatcher-driven tenant cron.

Revision ID: zz28_adoption_daily_default
Revises: zz27_adoption_sync_cfg
Create Date: 2026-03-02
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "zz28_adoption_daily_default"
down_revision = "zz27_adoption_sync_cfg"
branch_labels = None
depends_on = None
tags = ["adoption", "ops"]


def upgrade() -> None:
    # Dispatcher runs frequently and reads tenant schedules from adoption_sync_configs.
    op.execute(
        """
        UPDATE scheduled_job_configs
        SET task_name = 'adoption.daily_sync',
            schedule_type = 'interval',
            schedule_value = '60',
            description = 'Dispatches tenant adoption sync runs based on tenant-defined schedules in Adoption Settings.'
        WHERE job_name = 'adoption-daily-sync'
        """
    )

    # New tenant defaults: disabled until schedule is explicitly configured.
    op.alter_column(
        "adoption_sync_configs",
        "schedule_enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.execute(
        """
        UPDATE adoption_sync_configs
        SET schedule_enabled = false
        WHERE schedule_cron IS NULL OR btrim(schedule_cron) = ''
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE scheduled_job_configs
        SET task_name = 'adoption.daily_sync',
            schedule_type = 'interval',
            schedule_value = '21600',
            description = 'Syncs ChatGPT Enterprise adoption metrics from OpenAI Compliance API. Runs automatically every 6 hours.'
        WHERE job_name = 'adoption-daily-sync'
        """
    )

    op.alter_column(
        "adoption_sync_configs",
        "schedule_enabled",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )
