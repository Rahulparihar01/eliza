"""
Connection resolution helpers for retrieval sources.

This module resolves HubSpot/Fathom credentials from the platform-level
ConnectorConfiguration model (tenant-scoped connections).
"""

from __future__ import annotations

import json
from typing import Dict, Optional, Set

from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.models import database
from src.models.connector import ConnectorConfiguration
from src.services.langfuse_service import get_langfuse_service
from src.utils.encryption import decrypt_value

RETRIEVAL_SOURCES: tuple[str, ...] = ("hubspot", "fathom")
logger = get_logger(__name__, component="retrieval.connection_resolver")


def _get_db() -> Session:
    if database.SessionLocal is None:
        database.init_database()
    return database.SessionLocal()


def get_connector_configuration(
    *,
    customer_id: str,
    source_type: str,
    db: Optional[Session] = None,
) -> Optional[ConnectorConfiguration]:
    """
    Resolve enabled connector config for a retrieval source.

    Returns the most recently updated matching connector.
    """
    if source_type not in RETRIEVAL_SOURCES:
        return None

    close_db = False
    if db is None:
        db = _get_db()
        close_db = True

    try:
        return (
            db.query(ConnectorConfiguration)
            .filter(
                ConnectorConfiguration.customer_id == customer_id,
                ConnectorConfiguration.connector_type == source_type,
                ConnectorConfiguration.is_enabled == True,
                ConnectorConfiguration.credentials_encrypted.isnot(None),
            )
            .order_by(ConnectorConfiguration.updated_at.desc(), ConnectorConfiguration.created_at.desc())
            .first()
        )
    finally:
        if close_db:
            db.close()


def get_source_credentials(
    *,
    customer_id: str,
    source_type: str,
    db: Optional[Session] = None,
) -> Optional[Dict]:
    """Return decrypted credentials for a retrieval source, or None."""
    langfuse_service = get_langfuse_service()
    trace_metadata = {
        "component": "agentmesh",
        "flow": "retrieval",
        "stage": "resolve_source_credentials",
        "source_type": source_type,
        "customer_id": customer_id,
    }

    with langfuse_service.span_scope(
        name=f"retrieval.credentials.resolve.{source_type}",
        input_data={"source_type": source_type},
        metadata=trace_metadata,
    ) as resolver_span:
        observation = resolver_span.get("observation")

        config = get_connector_configuration(customer_id=customer_id, source_type=source_type, db=db)
        if config is None:
            if observation is not None:
                try:
                    observation.update(
                        output={"status": "missing_connector", "source_type": source_type},
                        level="ERROR",
                        status_message="No enabled connector found for retrieval source",
                    )
                except Exception:
                    pass
            return None

        if not config.credentials_encrypted:
            if observation is not None:
                try:
                    observation.update(
                        output={
                            "status": "missing_credentials",
                            "source_type": source_type,
                            "connector_id": config.connector_id,
                        },
                        level="ERROR",
                        status_message="Connector has no encrypted credentials",
                    )
                except Exception:
                    pass
            return None

        try:
            decrypted = decrypt_value(config.credentials_encrypted)
            parsed = json.loads(decrypted)
        except Exception as exc:
            logger.warning(
                "retrieval_credential_resolution_failed",
                source_type=source_type,
                connector_id=config.connector_id,
                error=str(exc),
            )
            if observation is not None:
                try:
                    observation.update(
                        output={
                            "status": "credential_resolution_failed",
                            "source_type": source_type,
                            "connector_id": config.connector_id,
                            "error": str(exc),
                            "error_type": type(exc).__name__,
                        },
                        level="ERROR",
                        status_message="Failed to decrypt or parse connector credentials",
                    )
                except Exception:
                    pass
            raise

        if isinstance(parsed, dict):
            if observation is not None:
                try:
                    observation.update(
                        output={
                            "status": "resolved",
                            "source_type": source_type,
                            "connector_id": config.connector_id,
                            "credential_keys": sorted(parsed.keys())[:20],
                        }
                    )
                except Exception:
                    pass
            return parsed

        if observation is not None:
            try:
                observation.update(
                    output={
                        "status": "invalid_credential_payload",
                        "source_type": source_type,
                        "connector_id": config.connector_id,
                        "payload_type": type(parsed).__name__,
                    },
                    level="ERROR",
                    status_message="Credentials payload is not a JSON object",
                )
            except Exception:
                pass
        return None


def list_connected_sources(*, customer_id: str, db: Optional[Session] = None) -> Set[str]:
    """Return retrieval sources with an enabled connector in the tenant."""
    close_db = False
    if db is None:
        db = _get_db()
        close_db = True

    try:
        rows = (
            db.query(ConnectorConfiguration.connector_type)
            .filter(
                ConnectorConfiguration.customer_id == customer_id,
                ConnectorConfiguration.connector_type.in_(RETRIEVAL_SOURCES),
                ConnectorConfiguration.is_enabled == True,
                ConnectorConfiguration.credentials_encrypted.isnot(None),
            )
            .all()
        )
        return {row[0] for row in rows}
    finally:
        if close_db:
            db.close()
