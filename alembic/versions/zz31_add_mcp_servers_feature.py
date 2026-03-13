"""Add MCP Servers platform feature for feature allocation.

Revision ID: zz31_mcp_servers_feature
Revises: zz30_mcp_phase1_schema
Create Date: 2026-03-05
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "zz31_mcp_servers_feature"
down_revision: Union[str, Sequence[str], None] = "zz30_mcp_phase1_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
tags: Sequence[str] = ["core"]


def upgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(text(
        "SELECT id FROM platform_features WHERE feature_key = 'mcp_servers'"
    )).fetchone()

    if not result:
        conn.execute(text("""
            INSERT INTO platform_features (
                feature_key, display_name, description, category, icon, sort_order, is_active, created_at, updated_at
            ) VALUES (
                'mcp_servers',
                'MCP Servers',
                'Allow tenant admins to configure Model Context Protocol (MCP) servers for AI agent access to workspaces and tools',
                'config',
                'ServerStackIcon',
                60,
                true,
                now(),
                now()
            )
        """))

        feature_id = conn.execute(text(
            "SELECT id FROM platform_features WHERE feature_key = 'mcp_servers'"
        )).fetchone()[0]

        conn.execute(text("""
            INSERT INTO feature_permissions (
                feature_id, permission_key, display_name, description, sort_order, created_at, updated_at
            ) VALUES
                (:fid, 'mcp:read', 'View MCP Configs', 'View MCP server configurations', 1, now(), now()),
                (:fid, 'mcp:write', 'Manage MCP Configs', 'Create, edit, and delete MCP server configurations', 2, now(), now())
        """), {"fid": feature_id})


def downgrade() -> None:
    conn = op.get_bind()

    result = conn.execute(text(
        "SELECT id FROM platform_features WHERE feature_key = 'mcp_servers'"
    )).fetchone()

    if result:
        feature_id = result[0]
        conn.execute(text(
            "DELETE FROM feature_permissions WHERE feature_id = :fid"
        ), {"fid": feature_id})
        conn.execute(text(
            "DELETE FROM tenant_feature_allocations WHERE feature_id = :fid"
        ), {"fid": feature_id})
        conn.execute(text(
            "DELETE FROM platform_features WHERE id = :fid"
        ), {"fid": feature_id})
