"""Add workspace prompt snapshots and GEPA optimization strategy.

Revision ID: zz23_workspace_prompt_cfg
Revises: zz22_workspace_templates_kb
Create Date: 2026-02-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "zz23_workspace_prompt_cfg"
down_revision = "zz22_workspace_templates_kb"
branch_labels = None
depends_on = None
tags = ["core", "ai_console", "evals"]


def upgrade() -> None:
    # Workspace-level prompt template snapshot
    op.add_column(
        "ragflow_domains",
        sa.Column("prompt_config_json", postgresql.JSON(astext_type=sa.Text()), nullable=True),
    )

    # Eval reproducibility snapshot
    op.add_column(
        "rag_eval_runs",
        sa.Column(
            "prompt_template_snapshot",
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # GEPA strategy selector (legacy + DSPy-backed modes)
    op.add_column(
        "gepa_optimizer_jobs",
        sa.Column(
            "optimization_strategy",
            sa.String(length=50),
            nullable=False,
            server_default="genetic",
        ),
    )


def downgrade() -> None:
    op.drop_column("gepa_optimizer_jobs", "optimization_strategy")
    op.drop_column("rag_eval_runs", "prompt_template_snapshot")
    op.drop_column("ragflow_domains", "prompt_config_json")
