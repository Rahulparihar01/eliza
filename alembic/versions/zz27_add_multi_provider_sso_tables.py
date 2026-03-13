"""Add tenant SSO providers/domains tables with backfill.

Revision ID: zz27_multi_provider_sso
Revises: zz26_tenant_sso_settings
Create Date: 2026-02-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "zz27_multi_provider_sso"
down_revision: Union[str, Sequence[str], None] = "zz26_tenant_sso_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags = ["tenancy", "auth"]


def upgrade() -> None:
    op.create_table(
        "tenant_sso_providers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("config_data", sa.JSON(), nullable=True),
        sa.Column("secret_data_encrypted", sa.JSON(), nullable=True),
        sa.Column(
            "jit_provisioning_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "jit_default_role",
            sa.String(length=100),
            nullable=False,
            server_default=sa.text("'viewer'"),
        ),
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
        sa.UniqueConstraint(
            "customer_id",
            "provider_type",
            "protocol",
            name="uq_tenant_sso_providers_customer_provider_protocol",
        ),
    )
    op.create_index(
        "ix_tenant_sso_providers_customer_id",
        "tenant_sso_providers",
        ["customer_id"],
    )
    op.create_index(
        "ix_tenant_sso_providers_provider_type",
        "tenant_sso_providers",
        ["provider_type"],
    )
    op.create_index(
        "ix_tenant_sso_providers_protocol",
        "tenant_sso_providers",
        ["protocol"],
    )
    op.create_index(
        "ix_tenant_sso_providers_is_enabled",
        "tenant_sso_providers",
        ["is_enabled"],
    )
    op.create_index(
        "ix_tenant_sso_providers_updated_by_user_id",
        "tenant_sso_providers",
        ["updated_by_user_id"],
    )

    op.create_table(
        "tenant_sso_domains",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("verification_token", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_error", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status in ('pending', 'verified', 'failed')",
            name="ck_tenant_sso_domains_status",
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id",
            "domain",
            name="uq_tenant_sso_domains_customer_domain",
        ),
    )
    op.create_index(
        "ix_tenant_sso_domains_customer_id",
        "tenant_sso_domains",
        ["customer_id"],
    )
    op.create_index(
        "ix_tenant_sso_domains_domain",
        "tenant_sso_domains",
        ["domain"],
    )
    op.create_index(
        "ix_tenant_sso_domains_status",
        "tenant_sso_domains",
        ["status"],
    )

    # Backfill existing single-provider tenant configs into provider rows.
    op.execute(
        """
        INSERT INTO tenant_sso_providers (
            customer_id,
            provider_type,
            protocol,
            display_name,
            is_enabled,
            config_data,
            secret_data_encrypted,
            jit_provisioning_enabled,
            jit_default_role,
            last_tested_at,
            last_test_status,
            last_test_error,
            updated_by_user_id,
            created_at,
            updated_at
        )
        SELECT
            customer_id,
            provider_type,
            protocol,
            provider_display_name,
            is_enabled,
            config_data,
            secret_data_encrypted,
            jit_provisioning_enabled,
            jit_default_role,
            last_tested_at,
            last_test_status,
            last_test_error,
            updated_by_user_id,
            created_at,
            updated_at
        FROM tenant_sso_configs
        WHERE provider_type IS NOT NULL
          AND protocol IS NOT NULL
        ON CONFLICT (customer_id, provider_type, protocol) DO UPDATE
        SET
            display_name = EXCLUDED.display_name,
            is_enabled = EXCLUDED.is_enabled,
            config_data = EXCLUDED.config_data,
            secret_data_encrypted = EXCLUDED.secret_data_encrypted,
            jit_provisioning_enabled = EXCLUDED.jit_provisioning_enabled,
            jit_default_role = EXCLUDED.jit_default_role,
            last_tested_at = EXCLUDED.last_tested_at,
            last_test_status = EXCLUDED.last_test_status,
            last_test_error = EXCLUDED.last_test_error,
            updated_by_user_id = EXCLUDED.updated_by_user_id,
            updated_at = EXCLUDED.updated_at
        """
    )

    # Backfill legacy domain allowlist values as verified domains.
    op.execute(
        """
        INSERT INTO tenant_sso_domains (
            customer_id,
            domain,
            verification_token,
            status,
            verified_at,
            last_checked_at,
            last_check_error,
            created_at,
            updated_at
        )
        SELECT
            c.customer_id,
            lower(trim(d.domain)) AS domain,
            concat('legacy-', md5(c.customer_id || ':' || lower(trim(d.domain)))) AS verification_token,
            'verified' AS status,
            COALESCE(c.updated_at, now()) AS verified_at,
            COALESCE(c.updated_at, now()) AS last_checked_at,
            NULL AS last_check_error,
            COALESCE(c.created_at, now()) AS created_at,
            COALESCE(c.updated_at, now()) AS updated_at
        FROM tenant_sso_configs c
        CROSS JOIN LATERAL jsonb_array_elements_text(
            COALESCE(c.domain_allowlist::jsonb, '[]'::jsonb)
        ) AS d(domain)
        WHERE trim(d.domain) <> ''
        ON CONFLICT (customer_id, domain) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tenant_sso_domains_status", table_name="tenant_sso_domains")
    op.drop_index("ix_tenant_sso_domains_domain", table_name="tenant_sso_domains")
    op.drop_index("ix_tenant_sso_domains_customer_id", table_name="tenant_sso_domains")
    op.drop_table("tenant_sso_domains")

    op.drop_index(
        "ix_tenant_sso_providers_updated_by_user_id",
        table_name="tenant_sso_providers",
    )
    op.drop_index("ix_tenant_sso_providers_is_enabled", table_name="tenant_sso_providers")
    op.drop_index("ix_tenant_sso_providers_protocol", table_name="tenant_sso_providers")
    op.drop_index(
        "ix_tenant_sso_providers_provider_type",
        table_name="tenant_sso_providers",
    )
    op.drop_index("ix_tenant_sso_providers_customer_id", table_name="tenant_sso_providers")
    op.drop_table("tenant_sso_providers")
