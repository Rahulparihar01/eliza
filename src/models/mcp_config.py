"""MCP server configuration models.

Stores per-tenant MCP server settings: which workspaces and tools are
exposed, rate limits, white-label branding, and enable/disable state.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from src.models.database import BaseModel


class MCPServerConfig(BaseModel):
    """Per-tenant configuration for an MCP server instance (Chat or Applet)."""

    __tablename__ = "mcp_server_configs"

    customer_id = Column(String(100), ForeignKey("customers.customer_id"), nullable=False, index=True)

    server_type = Column(String(20), nullable=False, default="chat")
    server_name = Column(String(100), nullable=False, default="eliza-chat")
    display_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)

    is_enabled = Column(Boolean, nullable=False, default=False)

    allowed_workspace_ids = Column(JSONB, nullable=True, default=list)
    allowed_tool_names = Column(JSONB, nullable=True, default=list)
    enabled_widgets = Column(JSONB, nullable=True, default=list)

    rate_limit_rpm = Column(Integer, nullable=False, default=30)
    rate_limit_rph = Column(Integer, nullable=False, default=500)
    max_concurrent_sessions = Column(Integer, nullable=False, default=50)
    max_async_operations = Column(Integer, nullable=False, default=5)

    oauth_client_id = Column(String(255), nullable=True)
    oauth_redirect_uris = Column(JSONB, nullable=True, default=list)

    def __repr__(self) -> str:
        return f"<MCPServerConfig {self.server_name} tenant={self.customer_id} enabled={self.is_enabled}>"
