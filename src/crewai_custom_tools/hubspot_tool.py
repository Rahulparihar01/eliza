"""
Custom CrewAI Tool for HubSpot CRM Search.

Resolves the user's encrypted access token, builds a validated HubSpot
Search API request via the schema, calls the HubSpot CRM Search endpoint,
and returns formatted results.
"""

import json
import logging
from typing import Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.services.langfuse_service import get_langfuse_service
from src.services.retrieval.connection_resolver import get_source_credentials
from src.services.retrieval.tool_response_models import ToolResponse
from src.services.retrieval.hubspot_query_schema import (
    HubSpotSearchRequest,
    HUBSPOT_PROPERTIES,
)

logger = logging.getLogger(__name__)

HUBSPOT_SEARCH_URL = "https://api.hubapi.com/crm/v3/objects/{object_type}/search"


class HubSpotToolInput(BaseModel):
    """Input schema exposed to the LLM agent."""

    search_request_json: str = Field(
        ...,
        description=(
            "A JSON string representing a HubSpotSearchRequest with fields: "
            "object_type (contacts|companies|deals), query (optional text), "
            "filterGroups, sorts, properties, limit. "
            "Example: {\"object_type\":\"contacts\",\"query\":\"acme\",\"properties\":[\"email\",\"firstname\"],\"limit\":10}"
        ),
    )


class HubSpotTool(BaseTool):
    """Searches HubSpot CRM objects (contacts, companies, deals)."""

    name: str = "hubspot_crm_search"
    description: str = (
        "Search HubSpot CRM for contacts, companies, or deals. "
        "Accepts a JSON search request and returns matching records."
    )
    args_schema: Type[BaseModel] = HubSpotToolInput

    # Runtime context (not exposed to the LLM)
    user_id: int = Field(..., description="Current user ID")
    customer_id: str = Field(..., description="Current customer/tenant ID")

    def _resolve_token(self) -> str:
        """Fetch and decrypt the tenant HubSpot access token."""
        langfuse_service = get_langfuse_service()
        trace_metadata = {
            "component": "agentmesh",
            "flow": "retrieval",
            "stage": "tool_auth",
            "tool": self.name,
            "source_type": "hubspot",
            "customer_id": self.customer_id,
            "user_id": self.user_id,
        }

        with langfuse_service.span_scope(
            name="retrieval.tool.hubspot.resolve_token",
            input_data={"source_type": "hubspot"},
            metadata=trace_metadata,
        ) as auth_span:
            observation = auth_span.get("observation")
            creds = get_source_credentials(customer_id=self.customer_id, source_type="hubspot")
            if not creds:
                if observation is not None:
                    try:
                        observation.update(
                            output={"status": "missing_connection"},
                            level="ERROR",
                            status_message="No connected HubSpot source for tenant",
                        )
                    except Exception:
                        pass
                raise ValueError("No connected HubSpot data source found for this tenant.")

            token_key = next(
                (candidate for candidate in ("access_token", "api_key", "token") if creds.get(candidate)),
                None,
            )
            token = creds.get(token_key) if token_key else None
            if not token:
                if observation is not None:
                    try:
                        observation.update(
                            output={
                                "status": "missing_token",
                                "credential_keys": sorted(creds.keys())[:20],
                            },
                            level="ERROR",
                            status_message="HubSpot credentials missing token field",
                        )
                    except Exception:
                        pass
                raise ValueError("HubSpot connection is missing credentials.")

            if observation is not None:
                try:
                    observation.update(
                        output={
                            "status": "resolved",
                            "token_field": token_key,
                            "credential_keys": sorted(creds.keys())[:20],
                        }
                    )
                except Exception:
                    pass
            return str(token)

    def _run(self, search_request_json: str) -> str:
        """Execute the HubSpot CRM Search API call."""
        settings = get_settings()
        action = "search"

        # Parse and validate the LLM-produced payload
        try:
            raw = json.loads(search_request_json)
        except json.JSONDecodeError as exc:
            return ToolResponse.failure(
                source="hubspot",
                action=action,
                message=f"Invalid JSON: {exc}",
                code="validation_error",
            ).to_json()

        try:
            req = HubSpotSearchRequest(**raw)
        except Exception as exc:
            return ToolResponse.failure(
                source="hubspot",
                action=action,
                message=f"Schema validation failed: {exc}",
                code="validation_error",
            ).to_json()

        # Clamp to configured caps
        req.clamp(
            max_groups=settings.hubspot_filter_group_limit,
            max_filters_total=settings.hubspot_filter_total_limit,
            max_filters_per_group=settings.hubspot_filters_per_group,
        )

        # Default properties if the LLM didn't specify any
        if not req.properties:
            req.properties = HUBSPOT_PROPERTIES.get(req.object_type, [])

        # Resolve access token
        try:
            token = self._resolve_token()
        except ValueError as exc:
            return ToolResponse.failure(
                source="hubspot",
                action=action,
                message=str(exc),
                code="auth_required",
                retryable=False,
                details={"auth_required": True},
            ).to_json()

        # Build the HubSpot API payload (omit object_type – it's in the URL)
        payload = req.model_dump(exclude={"object_type", "after"}, exclude_none=True)
        if req.after:
            payload["after"] = req.after

        url = HUBSPOT_SEARCH_URL.format(object_type=req.object_type)

        try:
            resp = httpx.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return ToolResponse.success(
                source="hubspot",
                action=action,
                payload={
                    "object_type": req.object_type,
                    "total": data.get("total", 0),
                    "results": data.get("results", []),
                },
            ).to_json()
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot API error: %s %s", exc.response.status_code, exc.response.text)
            status_code = exc.response.status_code
            return ToolResponse.failure(
                source="hubspot",
                action=action,
                message=f"HubSpot API {status_code}: {exc.response.text}",
                status_code=status_code,
                url=str(exc.request.url),
                retryable=status_code >= 500 or status_code == 429,
                code="http_error",
            ).to_json()
        except Exception as exc:
            logger.error("HubSpot tool error: %s", exc)
            error_message = str(exc).strip() or type(exc).__name__
            return ToolResponse.failure(
                source="hubspot",
                action=action,
                message=error_message,
                code="tool_error",
            ).to_json()
