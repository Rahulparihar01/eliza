"""
OAuth callback routes for external data source authorization.

GET /oauth/callback/hubspot – HubSpot OAuth 2.0 code exchange
GET /oauth/authorize/hubspot – Initiate HubSpot OAuth flow
"""

import logging
import json
from uuid import uuid4
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.models import get_db
from src.models.connector import ConnectorConfiguration
from src.services.retrieval.oauth_service import OAuthService
from src.middleware.authorization import AuthorizationMiddleware
from src.core.auth_context import CurrentUserContext
from src.core.config import get_settings
from src.utils.encryption import encrypt_value

logger = logging.getLogger(__name__)
auth_middleware = AuthorizationMiddleware()

router = APIRouter(prefix="/oauth", tags=["OAuth"])

SUCCESS_HTML = """
<html>
<head><title>Connected!</title></head>
<body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#f9fafb">
  <div style="text-align:center">
    <h1 style="color:#059669">Connected!</h1>
    <p>Your HubSpot account has been connected. You can close this window.</p>
    <script>window.opener && window.opener.postMessage({type:'oauth_complete',source:'hubspot'},window.location.origin);setTimeout(()=>window.close(),3000)</script>
  </div>
</body>
</html>
"""

ERROR_HTML = """
<html>
<head><title>Connection Failed</title></head>
<body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#fef2f2">
  <div style="text-align:center">
    <h1 style="color:#dc2626">Connection Failed</h1>
    <p>{error}</p>
  </div>
</body>
</html>
"""


@router.get(
    "/authorize/hubspot",
    summary="Initiate HubSpot OAuth flow",
)
async def hubspot_authorize(
    current_user: CurrentUserContext = Depends(
        auth_middleware.require_any_permission(["connections:create", "platform:admin"])
    ),
):
    """Return the HubSpot OAuth authorize URL for the current user."""
    oauth = OAuthService()
    state = oauth.generate_state(
        user_id=current_user.user_id,
        customer_id=current_user.customer_id,
        source_type="hubspot",
    )
    url = oauth.hubspot_authorize_url(state)
    return {"authorize_url": url}


@router.get(
    "/callback/hubspot",
    response_class=HTMLResponse,
    summary="HubSpot OAuth callback (code exchange)",
)
async def hubspot_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Exchange the authorization code for access + refresh tokens, encrypt
    them, and store in connector_configurations.
    """
    oauth = OAuthService()
    settings = get_settings()

    # Verify state token
    try:
        parsed = oauth.verify_state(state)
    except ValueError as exc:
        logger.warning("OAuth state verification failed: %s", exc)
        return HTMLResponse(ERROR_HTML.format(error=str(exc)), status_code=400)

    user_id = parsed["user_id"]
    customer_id = parsed["customer_id"]

    # Exchange code for tokens
    try:
        resp = httpx.post(
            "https://api.hubapi.com/oauth/v1/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.hubspot_client_id,
                "client_secret": settings.hubspot_client_secret,
                "redirect_uri": settings.hubspot_redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except Exception as exc:
        logger.error("HubSpot token exchange failed: %s", exc)
        return HTMLResponse(ERROR_HTML.format(error="Token exchange failed"), status_code=502)

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")

    credentials_payload = {
        "access_token": access_token,
        "refresh_token": refresh_token or None,
        "auth_method": "oauth",
    }
    encrypted_credentials = encrypt_value(json.dumps(credentials_payload))

    existing = (
        db.query(ConnectorConfiguration)
        .filter(
            ConnectorConfiguration.customer_id == customer_id,
            ConnectorConfiguration.connector_type == "hubspot",
        )
        .order_by(ConnectorConfiguration.updated_at.desc(), ConnectorConfiguration.created_at.desc())
        .first()
    )

    if existing:
        existing.credentials_encrypted = encrypted_credentials
        existing.is_enabled = True
        existing.is_healthy = True
        existing.health_check_message = "Connected via OAuth"
        sync_config = existing.sync_config or {}
        sync_config["oauth_connected"] = True
        existing.sync_config = sync_config
    else:
        conn = ConnectorConfiguration(
            connector_id=f"hubspot_{customer_id}_{uuid4().hex[:8]}",
            customer_id=customer_id,
            connector_type="hubspot",
            connector_name="HubSpot (OAuth)",
            description="HubSpot CRM connection",
            use_shared_credentials=False,
            credentials_encrypted=encrypted_credentials,
            sync_config={"oauth_connected": True},
            sync_config_version=1,
            sync_config_history=[],
            sync_mode="incremental",
            is_enabled=True,
            is_healthy=True,
            health_check_message="Connected via OAuth",
            created_by_user_id=user_id,
        )
        db.add(conn)

    db.commit()
    logger.info("HubSpot OAuth connected for user %s / customer %s", user_id, customer_id)

    return HTMLResponse(SUCCESS_HTML)
