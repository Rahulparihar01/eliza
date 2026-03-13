"""
HubSpot CRM connector.

Supports credential validation and lightweight object search pulls for
tenant-level HubSpot connections used by retrieval workflows.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Tuple

import httpx

from src.services.ingestion.connectors.base import BaseConnector

HUBSPOT_CONTACTS_URL = "https://api.hubapi.com/crm/v3/objects/contacts?limit=1"
HUBSPOT_SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/{object_type}/search"


class HubSpotConnector(BaseConnector):
    """Connector for HubSpot CRM."""

    def _resolve_token(self) -> str:
        token = (
            self.credentials.get("access_token")
            or self.credentials.get("api_key")
            or self.credentials.get("token")
        )
        if not token:
            raise ValueError("HubSpot token is required")
        return str(token).strip()

    def check(self) -> Dict[str, Any]:
        """Validate HubSpot credentials."""
        token = self._resolve_token()
        last_error = ""

        # Method 1: Bearer token (OAuth/private app tokens)
        try:
            resp = httpx.get(
                HUBSPOT_CONTACTS_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            if resp.status_code in (200, 403):
                return {
                    "status": "healthy",
                    "message": "Connected to HubSpot successfully",
                    "metadata": {"auth_method": "bearer"},
                }
            last_error = resp.text
        except Exception as exc:
            last_error = str(exc)

        # Method 2: hapikey-style token
        try:
            resp = httpx.get(
                f"{HUBSPOT_CONTACTS_URL}&hapikey={token}",
                timeout=10.0,
            )
            if resp.status_code in (200, 403):
                return {
                    "status": "healthy",
                    "message": "Connected to HubSpot successfully",
                    "metadata": {"auth_method": "api_key"},
                }
            last_error = resp.text
        except Exception as exc:
            last_error = str(exc)

        return {
            "status": "unhealthy",
            "message": f"HubSpot authentication failed: {last_error}",
            "metadata": {"auth_method": "unknown"},
        }

    def discover(self) -> Dict[str, Any]:
        """Return supported HubSpot object streams."""
        return {
            "streams": [
                {
                    "name": "contacts",
                    "supported_sync_modes": ["full", "incremental"],
                    "json_schema": {"type": "object"},
                },
                {
                    "name": "companies",
                    "supported_sync_modes": ["full", "incremental"],
                    "json_schema": {"type": "object"},
                },
                {
                    "name": "deals",
                    "supported_sync_modes": ["full", "incremental"],
                    "json_schema": {"type": "object"},
                },
            ]
        }

    def read_stream(
        self,
        sync_mode: str,
        sync_params: Dict[str, Any],
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        Run a lightweight HubSpot search and yield one batch.

        This connector is primarily used for connection lifecycle and retrieval
        enablement, not full ingestion pipelines.
        """
        del sync_mode  # currently unused for this connector

        object_type = str(self.config.get("object_type") or "contacts")
        search_query = self.config.get("search_query") or {}
        if not isinstance(search_query, dict):
            search_query = {}
        limit = int(sync_params.get("max_records") or search_query.get("limit") or 20)
        search_query["limit"] = max(1, min(limit, 100))

        token = self._resolve_token()
        resp = httpx.post(
            HUBSPOT_SEARCH_URL.format(object_type=object_type),
            json=search_query,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        yield payload.get("results", [])

    def validate_config(self) -> Tuple[bool, str]:
        """Validate optional stream config."""
        object_type = self.config.get("object_type")
        if object_type and object_type not in {"contacts", "companies", "deals"}:
            return False, "object_type must be one of: contacts, companies, deals"
        return True, ""
