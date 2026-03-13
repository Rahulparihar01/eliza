"""
OAuth service for external data source authorization flows.

Currently supports HubSpot OAuth 2.0. Generates HMAC-signed state
tokens to prevent CSRF, and builds the authorize URL.
"""

import hmac
import time
import secrets
import hashlib
import logging
from urllib.parse import quote

from src.core.config import get_settings

logger = logging.getLogger(__name__)

HUBSPOT_SCOPES = [
    "crm.objects.contacts.read",
    "crm.objects.companies.read",
    "crm.objects.deals.read",
]


class OAuthService:
    """Handle OAuth authorization flows for external data sources."""

    def __init__(self):
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # State token helpers
    # ------------------------------------------------------------------

    def generate_state(self, user_id: int, customer_id: str, source_type: str) -> str:
        """Generate an HMAC-signed state parameter for OAuth redirect."""
        secret = self._settings.oauth_state_secret
        if not secret:
            raise ValueError("OAUTH_STATE_SECRET is not configured")
        ts = str(int(time.time()))
        nonce = secrets.token_hex(16)
        payload = f"{user_id}:{customer_id}:{source_type}:{ts}:{nonce}"
        sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return f"{payload}:{sig}"

    def verify_state(self, state: str, max_age: int = 600) -> dict:
        """
        Verify an HMAC-signed state string.  Returns parsed fields or
        raises ValueError on tampered / expired tokens.
        """
        secret = self._settings.oauth_state_secret
        parts = state.rsplit(":", 1)
        if len(parts) != 2:
            raise ValueError("Malformed state token")
        payload, sig = parts
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("State signature mismatch")

        fields = payload.split(":")
        if len(fields) != 5:
            raise ValueError("Malformed state payload")

        user_id, customer_id, source_type, ts, _nonce = fields
        if int(time.time()) - int(ts) > max_age:
            raise ValueError("State token expired")

        return {
            "user_id": int(user_id),
            "customer_id": customer_id,
            "source_type": source_type,
        }

    # ------------------------------------------------------------------
    # HubSpot OAuth
    # ------------------------------------------------------------------

    def hubspot_authorize_url(self, state: str) -> str:
        """Return the HubSpot OAuth authorization URL."""
        client_id = self._settings.hubspot_client_id
        redirect_uri = quote(self._settings.hubspot_redirect_uri, safe="")
        scope = quote(" ".join(HUBSPOT_SCOPES), safe="")
        return (
            "https://app.hubspot.com/oauth/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&scope={scope}"
            f"&state={state}"
        )
