"""Add adoption sync config table and sync run provenance columns.

Revision ID: zz27_adoption_sync_cfg
Revises: zz26_flatten_baseline_merge
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "zz27_adoption_sync_cfg"
down_revision = "zz26_flatten_baseline_merge"
branch_labels = None
depends_on = None
tags = ["adoption", "ops"]


def upgrade() -> None:
    # Per-tenant adoption sync settings.
    op.create_table(
        "adoption_sync_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("initial_sync_start_date", sa.Date(), nullable=False),
        sa.Column(
            "schedule_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("schedule_cron", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", name="uq_adoption_sync_configs_customer"),
    )
    op.create_index(
        "ix_adoption_sync_configs_customer_id",
        "adoption_sync_configs",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        "ix_adoption_sync_configs_initial_sync_start_date",
        "adoption_sync_configs",
        ["initial_sync_start_date"],
        unique=False,
    )

    # Run-level provenance for targeted rollback.
    op.add_column(
        "adoption_daily_metrics",
        sa.Column("sync_run_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_adoption_daily_metrics_sync_run_id",
        "adoption_daily_metrics",
        ["sync_run_id"],
        unique=False,
    )

    op.add_column(
        "adoption_conversations",
        sa.Column("sync_run_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_adoption_conversations_sync_run_id",
        "adoption_conversations",
        ["sync_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_adoption_conversations_sync_run_id", table_name="adoption_conversations")
    op.drop_column("adoption_conversations", "sync_run_id")

    op.drop_index("ix_adoption_daily_metrics_sync_run_id", table_name="adoption_daily_metrics")
    op.drop_column("adoption_daily_metrics", "sync_run_id")

    op.drop_index("ix_adoption_sync_configs_initial_sync_start_date", table_name="adoption_sync_configs")
    op.drop_index("ix_adoption_sync_configs_customer_id", table_name="adoption_sync_configs")
    op.drop_table("adoption_sync_configs")
