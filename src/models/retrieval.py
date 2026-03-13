"""
Retrieval subsystem models.

Tables:
  - user_data_source_connections: per-user/tenant OAuth and private-app tokens
  - retrieval_runs: individual search runs (status, results, provenance)
  - retrieval_conversations: persistent chat conversations
  - retrieval_messages: messages within a conversation
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func

from src.models.database import Base, BaseModel


class UserDataSourceConnection(BaseModel):
    """Stores encrypted access credentials for external data sources."""

    __tablename__ = "user_data_source_connections"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    customer_id = Column(String(255), index=True, nullable=False)
    source_type = Column(String(50), nullable=False)          # e.g. "hubspot"
    auth_method = Column(String(30), nullable=False)           # "oauth" | "private_app"

    access_token_encrypted = Column(Text, nullable=True)
    refresh_token_encrypted = Column(Text, nullable=True)
    token_expires_at = Column(DateTime, nullable=True)

    status = Column(String(20), nullable=False, default="connected")
    connected_at = Column(DateTime, server_default=func.now())


class RetrievalRun(Base):
    """Tracks a single retrieval search run (status + results)."""

    __tablename__ = "retrieval_runs"

    run_id = Column(String(36), primary_key=True)
    customer_id = Column(String(255), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(String(36), ForeignKey("retrieval_conversations.id"), nullable=True)
    query_text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)

    results_json = Column(JSON, nullable=True)
    sources_used = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)


class RetrievalConversation(Base):
    """A persistent chat conversation for data search."""

    __tablename__ = "retrieval_conversations"

    id = Column(String(36), primary_key=True)
    customer_id = Column(String(255), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    workspace_id = Column(Integer, ForeignKey("ragflow_domains.id"), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RetrievalMessage(Base):
    """A single message in a retrieval conversation."""

    __tablename__ = "retrieval_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("retrieval_conversations.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)          # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)
    follow_ups = Column(JSON, nullable=True)
    run_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
