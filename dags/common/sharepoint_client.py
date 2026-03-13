"""Microsoft Graph API wrapper for SharePoint document sync.

Credentials are expected in environment variables:
  SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, SHAREPOINT_CLIENT_SECRET,
  SHAREPOINT_SITE_ID
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SharePointFile:
    id: str
    name: str
    path: str
    size: int
    content_type: str
    last_modified: str
    download_url: str
    drive_id: str
    etag: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class SharePointClient:
    """Thin wrapper around Microsoft Graph API for SharePoint drive items."""

    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        site_id: str | None = None,
    ):
        self.tenant_id = tenant_id or os.environ.get("SHAREPOINT_TENANT_ID", "")
        self.client_id = client_id or os.environ.get("SHAREPOINT_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("SHAREPOINT_CLIENT_SECRET", "")
        self.site_id = site_id or os.environ.get("SHAREPOINT_SITE_ID", "")
        self._token: str | None = None
        self._token_expiry: float = 0.0

        if not all([self.tenant_id, self.client_id, self.client_secret, self.site_id]):
            logger.warning(
                "SharePoint credentials not fully configured — "
                "set SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID, "
                "SHAREPOINT_CLIENT_SECRET, SHAREPOINT_SITE_ID"
            )

    def _ensure_token(self) -> str:
        # Refresh if missing or within 60s of expiry
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        import requests

        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        resp = requests.post(url, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3599)
        logger.debug("SharePoint OAuth token refreshed, expires in %ds", data.get("expires_in", 3599))
        return self._token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._ensure_token()}"}

    def list_drives(self) -> list[dict[str, Any]]:
        import requests

        url = f"{self.GRAPH_BASE}/sites/{self.site_id}/drives"
        resp = requests.get(url, headers=self._headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])

    def delta(self, drive_id: str, delta_link: str | None = None) -> tuple[list[SharePointFile], str | None]:
        """Fetch changed files via delta query. Returns (files, next_delta_link)."""
        import requests

        if delta_link:
            url = delta_link
        else:
            url = f"{self.GRAPH_BASE}/drives/{drive_id}/root/delta"

        files: list[SharePointFile] = []
        next_link: str | None = None

        while url:
            resp = requests.get(url, headers=self._headers(), timeout=60)
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("value", []):
                if item.get("file") is None:
                    continue
                parent = item.get("parentReference", {})
                path_parts = (parent.get("path", "") or "").split(":")
                folder = path_parts[-1].lstrip("/") if len(path_parts) > 1 else ""
                full_path = f"{folder}/{item['name']}".lstrip("/")

                files.append(SharePointFile(
                    id=item["id"],
                    name=item["name"],
                    path=full_path,
                    size=item.get("size", 0),
                    content_type=item.get("file", {}).get("mimeType", "application/octet-stream"),
                    last_modified=item.get("lastModifiedDateTime", ""),
                    download_url=item.get("@microsoft.graph.downloadUrl", ""),
                    drive_id=drive_id,
                    etag=item.get("eTag"),
                ))

            url = data.get("@odata.nextLink")
            if not url:
                next_link = data.get("@odata.deltaLink")
                break

        return files, next_link

    def download_file(self, download_url: str) -> bytes:
        import requests

        resp = requests.get(download_url, headers=self._headers(), timeout=300)
        resp.raise_for_status()
        return resp.content
