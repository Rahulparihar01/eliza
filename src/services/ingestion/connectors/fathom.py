"""
Fathom meetings connector.

Supports credential validation and lightweight meeting pulls for
tenant-level Fathom connections used by retrieval workflows.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Tuple

import httpx

from src.services.ingestion.connectors.base import BaseConnector

FATHOM_API_BASE = "https://api.fathom.ai/external/v1"


class FathomConnector(BaseConnector):
    """Connector for Fathom meetings data."""

    def _resolve_api_key(self) -> str:
        api_key = (
            self.credentials.get("api_key")
            or self.credentials.get("access_token")
            or self.credentials.get("token")
        )
        if not api_key:
            raise ValueError("Fathom API key is required")
        return str(api_key).strip()

    def check(self) -> Dict[str, Any]:
        """Validate Fathom credentials."""
        token = self._resolve_api_key()
        try:
            resp = httpx.get(
                f"{FATHOM_API_BASE}/meetings",
                params={"limit": 1},
                headers={"X-Api-Key": token},
                timeout=10.0,
            )
            if resp.status_code == 200:
                payload = resp.json()
                return {
                    "status": "healthy",
                    "message": "Connected to Fathom successfully",
                    "metadata": {"meeting_count_preview": len(payload.get("items", []))},
                }
            return {
                "status": "unhealthy",
                "message": f"Fathom authentication failed: {resp.text}",
                "metadata": {},
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "message": f"Fathom authentication failed: {exc}",
                "metadata": {},
            }

    def discover(self) -> Dict[str, Any]:
        """Return supported Fathom stream."""
        return {
            "streams": [
                {
                    "name": "meetings",
                    "supported_sync_modes": ["full", "incremental"],
                    "json_schema": {"type": "object"},
                }
            ]
        }

    def read_stream(
        self,
        sync_mode: str,
        sync_params: Dict[str, Any],
    ) -> Iterator[List[Dict[str, Any]]]:
        """
        List meetings and return a single batch.

        This connector is primarily used for connection lifecycle and retrieval
        enablement, not full ingestion pipelines.
        """
        del sync_mode  # currently unused for this connector
        token = self._resolve_api_key()
        limit = int(sync_params.get("max_records") or self.config.get("limit") or 20)
        params: Dict[str, Any] = {"limit": max(1, min(limit, 50))}

        for key in ("query", "created_after", "created_before"):
            value = self.config.get(key)
            if value:
                params[key] = value

        resp = httpx.get(
            f"{FATHOM_API_BASE}/meetings",
            params=params,
            headers={"X-Api-Key": token},
            timeout=20.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        yield payload.get("items", [])

    def validate_config(self) -> Tuple[bool, str]:
        """Validate optional Fathom sync config."""
        limit = self.config.get("limit")
        if limit is None:
            return True, ""
        try:
            parsed = int(limit)
        except (TypeError, ValueError):
            return False, "limit must be an integer between 1 and 50"
        if parsed < 1 or parsed > 50:
            return False, "limit must be between 1 and 50"
        return True, ""
