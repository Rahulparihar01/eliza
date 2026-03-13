"""Add Agent Mesh workspace template and migrate retrieval connections.

Revision ID: zzd_agent_mesh_retrieval
Revises: zz25_kb_source_storage_settings, zzc_retrieval_conversations
Create Date: 2026-02-20 00:00:00.000000
"""
from __future__ import annotations

import json
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "zzd_agent_mesh_retrieval"
down_revision: Union[str, Sequence[str], None] = (
    "zz25_kb_source_storage_settings",
    "zzc_retrieval_conversations",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["retrieval", "core"]


def _table_exists(inspector: sa.Inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _load_crypto_helpers() -> tuple[object | None, object | None]:
    """Load credential crypto helpers lazily to keep Alembic import-time dependencies minimal."""
    try:
        from src.services.retrieval.tenant_encryption_service import TenantEncryptionService
        from src.utils.encryption import encrypt_value
    except Exception:
        return None, None
    return TenantEncryptionService, encrypt_value


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tenant_encryption_service, encrypt_value = _load_crypto_helpers()

    # 1) Seed Agent Mesh as a workflow template.
    if _table_exists(inspector, "workspace_templates"):
        conn.execute(
            sa.text(
                """
                INSERT INTO workspace_templates (
                    name, display_name, description, icon, is_available, config_schema, default_config
                )
                VALUES (
                    :name, :display_name, :description, :icon, true, CAST(:config_schema AS jsonb), CAST(:default_config AS jsonb)
                )
                ON CONFLICT (name) DO UPDATE
                SET
                    display_name = EXCLUDED.display_name,
                    description = EXCLUDED.description,
                    icon = EXCLUDED.icon,
                    is_available = true,
                    config_schema = EXCLUDED.config_schema,
                    default_config = EXCLUDED.default_config
                """
            ),
            {
                "name": "agent_mesh_retrieval",
                "display_name": "Agent Mesh Retrieval",
                "description": "Multi-source retrieval workflow template for CRM and meeting intelligence search.",
                "icon": "sparkles",
                "config_schema": json.dumps(
                    {
                        "type": "object",
                        "properties": {
                            "sources": {
                                "type": "object",
                                "properties": {
                                    "hubspot": {"type": "boolean"},
                                    "fathom": {"type": "boolean"},
                                },
                            },
                            "planner": {"type": "object"},
                            "synthesizer": {"type": "object"},
                        },
                    }
                ),
                "default_config": json.dumps(
                    {
                        "sources": {"hubspot": True, "fathom": True},
                        "planner": {"max_iterations": 3},
                        "synthesizer": {"follow_ups": True},
                    }
                ),
            },
        )

    inspector = sa.inspect(conn)

    # 2) Add workspace binding to retrieval conversations.
    if _table_exists(inspector, "retrieval_conversations") and not _column_exists(
        inspector, "retrieval_conversations", "workspace_id"
    ):
        op.add_column(
            "retrieval_conversations",
            sa.Column("workspace_id", sa.Integer(), nullable=True),
        )

    inspector = sa.inspect(conn)
    if _table_exists(inspector, "retrieval_conversations") and _column_exists(
        inspector, "retrieval_conversations", "workspace_id"
    ):
        foreign_keys = inspector.get_foreign_keys("retrieval_conversations")
        if not any(fk["name"] == "fk_retrieval_conversations_workspace_id" for fk in foreign_keys):
            op.create_foreign_key(
                "fk_retrieval_conversations_workspace_id",
                "retrieval_conversations",
                "ragflow_domains",
                ["workspace_id"],
                ["id"],
                ondelete="SET NULL",
            )

        indexes = {idx["name"] for idx in inspector.get_indexes("retrieval_conversations")}
        if "idx_retrieval_conv_workspace" not in indexes:
            op.create_index(
                "idx_retrieval_conv_workspace",
                "retrieval_conversations",
                ["workspace_id"],
            )

    # 3) Backfill workspace_id for existing retrieval conversations.
    template_id = conn.execute(
        sa.text("SELECT id FROM workspace_templates WHERE name = 'agent_mesh_retrieval' LIMIT 1")
    ).scalar()

    if template_id is not None and _table_exists(inspector, "retrieval_conversations"):
        customer_rows = conn.execute(
            sa.text(
                """
                SELECT DISTINCT customer_id
                FROM retrieval_conversations
                WHERE workspace_id IS NULL
                """
            )
        ).fetchall()

        for row in customer_rows:
            customer_id = row[0]
            workspace_id = conn.execute(
                sa.text(
                    """
                    SELECT rd.id
                    FROM ragflow_domains rd
                    JOIN workspace_templates wt ON wt.id = rd.template_id
                    WHERE rd.customer_id = :customer_id
                      AND rd.is_active = true
                      AND wt.name = 'agent_mesh_retrieval'
                    ORDER BY rd.created_at ASC
                    LIMIT 1
                    """
                ),
                {"customer_id": customer_id},
            ).scalar()

            if workspace_id is None:
                base_name = "agent_mesh"
                workspace_name = base_name
                suffix = 1
                while conn.execute(
                    sa.text(
                        """
                        SELECT 1
                        FROM ragflow_domains
                        WHERE customer_id = :customer_id AND name = :name
                        LIMIT 1
                        """
                    ),
                    {"customer_id": customer_id, "name": workspace_name},
                ).scalar():
                    suffix += 1
                    workspace_name = f"{base_name}_{suffix}"

                workspace_id = conn.execute(
                    sa.text(
                        """
                        INSERT INTO ragflow_domains (
                            customer_id, name, display_name, description, template_id, is_active
                        )
                        VALUES (
                            :customer_id, :name, :display_name, :description, :template_id, true
                        )
                        RETURNING id
                        """
                    ),
                    {
                        "customer_id": customer_id,
                        "name": workspace_name,
                        "display_name": "Agent Mesh",
                        "description": "Auto-created Agent Mesh retrieval workspace",
                        "template_id": template_id,
                    },
                ).scalar()

            conn.execute(
                sa.text(
                    """
                    UPDATE retrieval_conversations
                    SET workspace_id = :workspace_id
                    WHERE customer_id = :customer_id
                      AND workspace_id IS NULL
                    """
                ),
                {"workspace_id": workspace_id, "customer_id": customer_id},
            )

    # 4) Migrate hubspot/fathom credentials into connector_configurations.
    inspector = sa.inspect(conn)
    if (
        tenant_encryption_service is not None
        and encrypt_value is not None
        and _table_exists(inspector, "user_data_source_connections")
        and _table_exists(
        inspector, "connector_configurations"
    )):
        rows = conn.execute(
            sa.text(
                """
                SELECT DISTINCT ON (customer_id, source_type)
                    id,
                    customer_id,
                    user_id,
                    source_type,
                    auth_method,
                    access_token_encrypted,
                    refresh_token_encrypted,
                    token_expires_at
                FROM user_data_source_connections
                WHERE source_type IN ('hubspot', 'fathom')
                  AND status = 'connected'
                  AND access_token_encrypted IS NOT NULL
                ORDER BY customer_id, source_type, connected_at DESC, id DESC
                """
            )
        ).fetchall()

        for row in rows:
            customer_id = row.customer_id
            source_type = row.source_type

            exists = conn.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM connector_configurations
                    WHERE customer_id = :customer_id
                      AND connector_type = :connector_type
                    LIMIT 1
                    """
                ),
                {"customer_id": customer_id, "connector_type": source_type},
            ).scalar()
            if exists:
                continue

            try:
                primary_token = tenant_encryption_service.decrypt(customer_id, row.access_token_encrypted)
            except Exception:
                # If old tenant-encrypted credentials cannot be decrypted, skip and
                # require reconnect from Data Connections.
                continue

            refresh_token = None
            if row.refresh_token_encrypted:
                try:
                    refresh_token = tenant_encryption_service.decrypt(customer_id, row.refresh_token_encrypted)
                except Exception:
                    refresh_token = None

            if source_type == "hubspot":
                if (row.auth_method or "").lower() == "oauth":
                    credentials_payload = {
                        "access_token": primary_token,
                        "refresh_token": refresh_token,
                        "auth_method": "oauth",
                    }
                else:
                    credentials_payload = {
                        "api_key": primary_token,
                        "auth_method": row.auth_method or "api_key",
                    }
                connector_name = "HubSpot (Migrated)"
            else:
                credentials_payload = {
                    "api_key": primary_token,
                    "auth_method": "api_key",
                }
                connector_name = "Fathom (Migrated)"

            if row.token_expires_at is not None:
                credentials_payload["token_expires_at"] = row.token_expires_at.isoformat()

            try:
                encrypted_credentials = encrypt_value(json.dumps(credentials_payload))
            except Exception:
                # ENCRYPTION_KEY may be unset in some environments; skip legacy
                # credential copy and require reconnect through Data Connections.
                continue
            conn.execute(
                sa.text(
                    """
                    INSERT INTO connector_configurations (
                        connector_id,
                        connector_type,
                        connector_name,
                        description,
                        customer_id,
                        use_shared_credentials,
                        credentials_encrypted,
                        sync_config,
                        sync_config_version,
                        sync_config_history,
                        sync_mode,
                        is_enabled,
                        is_healthy,
                        health_check_message,
                        created_by_user_id
                    )
                    VALUES (
                        :connector_id,
                        :connector_type,
                        :connector_name,
                        :description,
                        :customer_id,
                        false,
                        :credentials_encrypted,
                        CAST(:sync_config AS jsonb),
                        1,
                        CAST(:sync_config_history AS jsonb),
                        'incremental',
                        true,
                        true,
                        :health_check_message,
                        :created_by_user_id
                    )
                    """
                ),
                {
                    "connector_id": f"{source_type}_{customer_id}_{uuid4().hex[:8]}",
                    "connector_type": source_type,
                    "connector_name": connector_name,
                    "description": "Auto-migrated from retrieval user data source connections",
                    "customer_id": customer_id,
                    "credentials_encrypted": encrypted_credentials,
                    "sync_config": json.dumps({"migrated_from": "user_data_source_connections"}),
                    "sync_config_history": "[]",
                    "health_check_message": "Migrated legacy retrieval credentials",
                    "created_by_user_id": row.user_id,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _table_exists(inspector, "retrieval_conversations") and _column_exists(
        inspector, "retrieval_conversations", "workspace_id"
    ):
        indexes = {idx["name"] for idx in inspector.get_indexes("retrieval_conversations")}
        if "idx_retrieval_conv_workspace" in indexes:
            op.drop_index("idx_retrieval_conv_workspace", table_name="retrieval_conversations")

        foreign_keys = inspector.get_foreign_keys("retrieval_conversations")
        if any(fk["name"] == "fk_retrieval_conversations_workspace_id" for fk in foreign_keys):
            op.drop_constraint(
                "fk_retrieval_conversations_workspace_id",
                "retrieval_conversations",
                type_="foreignkey",
            )

        op.drop_column("retrieval_conversations", "workspace_id")

    # Keep seeded template and migrated connector rows intact to avoid data loss.
    conn.execute(sa.text("SELECT 1"))
