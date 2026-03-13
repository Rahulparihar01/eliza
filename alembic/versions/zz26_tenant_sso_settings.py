"""Add tenant SSO settings table and SSO feature seed.

Revision ID: zz26_tenant_sso_settings
Revises: zz25_kb_source_storage_settings
Create Date: 2026-02-18
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "zz26_tenant_sso_settings"
down_revision: Union[str, Sequence[str], None] = "zz25_kb_source_storage_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags = ["tenancy", "auth"]


def upgrade() -> None:
    op.create_table(
        "tenant_sso_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "login_mode",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'password_only'"),
        ),
        sa.Column("provider_type", sa.String(length=64), nullable=True),
        sa.Column("protocol", sa.String(length=16), nullable=True),
        sa.Column("provider_display_name", sa.String(length=255), nullable=True),
        sa.Column("domain_allowlist", sa.JSON(), nullable=True),
        sa.Column("domain_verification_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("jit_provisioning_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "jit_default_role",
            sa.String(length=100),
            nullable=False,
            server_default=sa.text("'viewer'"),
        ),
        sa.Column("config_data", sa.JSON(), nullable=True),
        sa.Column("secret_data_encrypted", sa.JSON(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(length=32), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("customer_id", name="uq_tenant_sso_configs_customer_id"),
    )

    op.create_index(
        "ix_tenant_sso_configs_customer_id",
        "tenant_sso_configs",
        ["customer_id"],
        unique=True,
    )
    op.create_index(
        "ix_tenant_sso_configs_provider_type",
        "tenant_sso_configs",
        ["provider_type"],
    )
    op.create_index(
        "ix_tenant_sso_configs_protocol",
        "tenant_sso_configs",
        ["protocol"],
    )
    op.create_index(
        "ix_tenant_sso_configs_login_mode",
        "tenant_sso_configs",
        ["login_mode"],
    )
    op.create_index(
        "ix_tenant_sso_configs_updated_by_user_id",
        "tenant_sso_configs",
        ["updated_by_user_id"],
    )

    op.create_table(
        "user_sso_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("external_subject", sa.String(length=512), nullable=False),
        sa.Column("external_email", sa.String(length=255), nullable=True),
        sa.Column("claims_snapshot", sa.JSON(), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id",
            "provider_type",
            "protocol",
            "external_subject",
            name="uq_user_sso_identity_subject",
        ),
        sa.UniqueConstraint(
            "user_id",
            "customer_id",
            "provider_type",
            "protocol",
            name="uq_user_sso_identity_user_provider",
        ),
    )

    op.create_index("ix_user_sso_identities_user_id", "user_sso_identities", ["user_id"])
    op.create_index(
        "ix_user_sso_identities_customer_id", "user_sso_identities", ["customer_id"]
    )
    op.create_index(
        "ix_user_sso_identities_provider_type", "user_sso_identities", ["provider_type"]
    )
    op.create_index("ix_user_sso_identities_protocol", "user_sso_identities", ["protocol"])
    op.create_index(
        "ix_user_sso_identities_external_email", "user_sso_identities", ["external_email"]
    )

    # Seed platform feature for tenant SSO allocation control.
    op.execute(
        """
        INSERT INTO platform_features (
            feature_key, display_name, description, category, icon, sort_order, is_active, created_at, updated_at
        ) VALUES (
            'sso_authentication',
            'SSO Authentication',
            'Tenant-configurable SSO (OIDC/SAML) and login mode policy',
            'admin',
            'ShieldCheckIcon',
            14,
            true,
            now(),
            now()
        )
        ON CONFLICT (feature_key) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            description = EXCLUDED.description,
            category = EXCLUDED.category,
            icon = EXCLUDED.icon,
            is_active = true,
            updated_at = now()
        """
    )


def downgrade() -> None:
    # Keep platform_features seed intact on downgrade to avoid tenant feature mapping regressions.
    op.drop_index("ix_user_sso_identities_external_email", table_name="user_sso_identities")
    op.drop_index("ix_user_sso_identities_protocol", table_name="user_sso_identities")
    op.drop_index("ix_user_sso_identities_provider_type", table_name="user_sso_identities")
    op.drop_index("ix_user_sso_identities_customer_id", table_name="user_sso_identities")
    op.drop_index("ix_user_sso_identities_user_id", table_name="user_sso_identities")
    op.drop_table("user_sso_identities")

    op.drop_index("ix_tenant_sso_configs_updated_by_user_id", table_name="tenant_sso_configs")
    op.drop_index("ix_tenant_sso_configs_login_mode", table_name="tenant_sso_configs")
    op.drop_index("ix_tenant_sso_configs_protocol", table_name="tenant_sso_configs")
    op.drop_index("ix_tenant_sso_configs_provider_type", table_name="tenant_sso_configs")
    op.drop_index("ix_tenant_sso_configs_customer_id", table_name="tenant_sso_configs")
    op.drop_table("tenant_sso_configs")
