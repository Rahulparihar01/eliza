"""
Custom CrewAI Tool for Fathom meeting search and transcript retrieval.

Resolves the user's encrypted Fathom API key, queries the Fathom REST API
for meetings (with optional filters), and can fetch transcripts/summaries
for individual recordings.
"""

import json
import logging
from typing import Type, Optional

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from src.services.langfuse_service import get_langfuse_service
from src.services.retrieval.connection_resolver import get_source_credentials
from src.services.retrieval.tool_response_models import ToolResponse

logger = logging.getLogger(__name__)

FATHOM_API_BASE = "https://api.fathom.ai/external/v1"


class FathomToolInput(BaseModel):
    """Input schema exposed to the LLM agent."""

    action: str = Field(
        ...,
        description=(
            "Action to perform. One of: "
            "'list_meetings' – list/filter meetings, "
            "'get_transcript' – fetch transcript for a recording_id, "
            "'get_summary' – fetch summary for a recording_id."
        ),
    )
    recording_id: Optional[int] = Field(
        None,
        description="The recording ID (required for get_transcript and get_summary).",
    )
    search_query: Optional[str] = Field(
        None,
        description="Free-text query to filter meetings by title or content.",
    )
    created_after: Optional[str] = Field(
        None,
        description="ISO-8601 datetime. Only return meetings created after this date.",
    )
    created_before: Optional[str] = Field(
        None,
        description="ISO-8601 datetime. Only return meetings created before this date.",
    )
    limit: int = Field(
        10,
        description="Max meetings to return (1-50). Default 10.",
    )
    include_transcript: bool = Field(
        False,
        description="If true and action is list_meetings, include transcripts inline.",
    )
    include_summary: bool = Field(
        True,
        description="If true and action is list_meetings, include summaries inline.",
    )


class FathomTool(BaseTool):
    """Search Fathom meetings, retrieve transcripts and summaries."""

    name: str = "fathom_meetings"
    description: str = (
        "Search and retrieve Fathom meeting data. "
        "Can list/filter meetings, get transcripts, and get summaries. "
        "Use action='list_meetings' to search, 'get_transcript' or "
        "'get_summary' with a recording_id for details."
    )
    args_schema: Type[BaseModel] = FathomToolInput

    # Runtime context (not exposed to LLM)
    user_id: int = Field(..., description="Current user ID")
    customer_id: str = Field(..., description="Current customer/tenant ID")

    def _resolve_token(self) -> str:
        """Fetch and decrypt the tenant Fathom API key."""
        langfuse_service = get_langfuse_service()
        trace_metadata = {
            "component": "agentmesh",
            "flow": "retrieval",
            "stage": "tool_auth",
            "tool": self.name,
            "source_type": "fathom",
            "customer_id": self.customer_id,
            "user_id": self.user_id,
        }

        with langfuse_service.span_scope(
            name="retrieval.tool.fathom.resolve_token",
            input_data={"source_type": "fathom"},
            metadata=trace_metadata,
        ) as auth_span:
            observation = auth_span.get("observation")
            creds = get_source_credentials(customer_id=self.customer_id, source_type="fathom")
            if not creds:
                if observation is not None:
                    try:
                        observation.update(
                            output={"status": "missing_connection"},
                            level="ERROR",
                            status_message="No connected Fathom source for tenant",
                        )
                    except Exception:
                        pass
                raise ValueError("No connected Fathom data source found for this tenant.")

            token_key = next(
                (candidate for candidate in ("api_key", "access_token", "token") if creds.get(candidate)),
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
                            status_message="Fathom credentials missing token field",
                        )
                    except Exception:
                        pass
                raise ValueError("Fathom connection is missing credentials.")

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

    def _headers(self, token: str) -> dict:
        return {"X-Api-Key": token, "Content-Type": "application/json"}

    def _run(
        self,
        action: str,
        recording_id: Optional[int] = None,
        search_query: Optional[str] = None,
        created_after: Optional[str] = None,
        created_before: Optional[str] = None,
        limit: int = 10,
        include_transcript: bool = False,
        include_summary: bool = True,
    ) -> str:
        """Execute the Fathom API call."""
        try:
            token = self._resolve_token()
        except ValueError as exc:
            return ToolResponse.failure(
                source="fathom",
                action=action,
                message=str(exc),
                code="auth_required",
                retryable=False,
                details={"auth_required": True},
            ).to_json()

        headers = self._headers(token)

        try:
            if action == "list_meetings":
                return self._list_meetings(
                    headers, search_query, created_after, created_before,
                    limit, include_transcript, include_summary,
                )
            elif action == "get_transcript":
                if not recording_id:
                    return ToolResponse.failure(
                        source="fathom",
                        action=action,
                        message="recording_id is required for get_transcript",
                        code="validation_error",
                    ).to_json()
                return self._get_transcript(headers, recording_id)
            elif action == "get_summary":
                if not recording_id:
                    return ToolResponse.failure(
                        source="fathom",
                        action=action,
                        message="recording_id is required for get_summary",
                        code="validation_error",
                    ).to_json()
                return self._get_summary(headers, recording_id)
            else:
                return ToolResponse.failure(
                    source="fathom",
                    action=action,
                    message=(
                        f"Unknown action: {action}. Use list_meetings, "
                        "get_transcript, or get_summary."
                    ),
                    code="validation_error",
                ).to_json()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            body_text = exc.response.text
            return ToolResponse.failure(
                source="fathom",
                action=action,
                message=f"Fathom API {status_code}: {body_text}",
                status_code=status_code,
                url=str(exc.request.url),
                retryable=status_code >= 500 or status_code == 429,
                code="http_error",
            ).to_json()
        except Exception as exc:
            logger.error("Fathom tool error: %s", exc)
            error_message = str(exc).strip() or type(exc).__name__
            return ToolResponse.failure(
                source="fathom",
                action=action,
                message=error_message,
                code="tool_error",
                retryable=False,
            ).to_json()

    def _list_meetings(
        self, headers: dict, search_query, created_after, created_before,
        limit, include_transcript, include_summary,
    ) -> str:
        params: dict = {"limit": min(max(limit, 1), 50)}
        if search_query:
            params["query"] = search_query
        if created_after:
            params["created_after"] = created_after
        if created_before:
            params["created_before"] = created_before
        if include_transcript:
            params["include_transcript"] = "true"
        if include_summary:
            params["include_summary"] = "true"

        resp = httpx.get(
            f"{FATHOM_API_BASE}/meetings",
            params=params,
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        meetings = []
        for item in data.get("items", []):
            meeting = {
                "title": item.get("title") or item.get("meeting_title"),
                "recording_id": item.get("recording_id"),
                "url": item.get("url"),
                "date": item.get("meeting_start_time") or item.get("recording_start_time"),
                "duration_minutes": item.get("duration_minutes"),
                "meeting_type": item.get("meeting_type"),
            }
            if include_summary and "summary" in item:
                meeting["summary"] = item["summary"]
            if include_transcript and "transcript" in item:
                meeting["transcript"] = item["transcript"]
            meetings.append(meeting)

        return ToolResponse.success(
            source="fathom",
            action="list_meetings",
            payload={
                "total": len(meetings),
                "meetings": meetings,
            },
        ).to_json()

    def _get_transcript(self, headers: dict, recording_id: int) -> str:
        resp = httpx.get(
            f"{FATHOM_API_BASE}/recordings/{recording_id}/transcript",
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        return ToolResponse.success(
            source="fathom",
            action="get_transcript",
            payload={
                "recording_id": recording_id,
                "transcript": resp.json().get("transcript", []),
            },
        ).to_json()

    def _get_summary(self, headers: dict, recording_id: int) -> str:
        resp = httpx.get(
            f"{FATHOM_API_BASE}/recordings/{recording_id}/summary",
            headers=headers,
            timeout=15.0,
        )
        resp.raise_for_status()
        return ToolResponse.success(
            source="fathom",
            action="get_summary",
            payload={
                "recording_id": recording_id,
                "summary": resp.json(),
            },
        ).to_json()
