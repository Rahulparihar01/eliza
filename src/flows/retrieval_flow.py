"""
Retrieval Flow – Planner → ReAct Execute → Synthesize.

Architecture:
  1. **Planner** (LLM call) – analyses the query and available tools,
     produces a concrete plan of tool calls with parameters.
  2. **Executor** (Python loop) – executes each planned tool call,
     collects all raw results.
  3. **Evaluator** (LLM call) – inspects gathered data, decides if
     follow-up queries are needed.  If yes, produces more tool calls
     and we loop back to the executor.  Max 3 iterations.
  4. **Synthesizer** (LLM call) – takes ALL gathered data and the
     original query, produces a human-readable markdown answer with
     executive summary, key findings, and details.

No CrewAI dependency – uses PydanticAI (with LiteLLM fallback) for
typed planning/evaluation/synthesis and direct Python tool execution
for full control over the loop and output.
"""

import inspect
import json
import logging
import re
from typing import Any, Callable

import litellm
from pydantic import BaseModel, Field

from src.crewai_custom_tools.hubspot_tool import HubSpotTool
from src.crewai_custom_tools.fathom_tool import FathomTool
from src.core.config import get_settings
from src.services.langfuse_service import get_langfuse_service
from src.services.retrieval.connection_resolver import list_connected_sources
from src.services.retrieval.tool_response_models import ToolResponse

logger = logging.getLogger(__name__)

# Max evaluate→execute iterations to prevent runaway loops
MAX_REACT_ITERATIONS = 3
TRACE_PREVIEW_LIMIT = 4000

ProgressEventCallback = Callable[[dict[str, Any]], None]


class ToolCallPlanStep(BaseModel):
    """Normalized tool call shape used by planner/evaluator stages."""

    tool: str = Field(..., description="Registered tool name to execute.")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool input params.",
    )


class PlannerOutput(BaseModel):
    """Structured planner output."""

    calls: list[ToolCallPlanStep] = Field(default_factory=list)


class EvaluatorOutput(BaseModel):
    """Structured evaluator output."""

    done: bool = True
    reason: str | None = None
    follow_up: list[ToolCallPlanStep] = Field(default_factory=list)


class SynthesizerOutput(BaseModel):
    """Structured synthesizer output."""

    answer: str = ""


class FollowUpsOutput(BaseModel):
    """Structured follow-up output."""

    questions: list[str] = Field(default_factory=list)


def _connected_sources(customer_id: str) -> set[str]:
    """Return retrieval sources with an enabled tenant connector."""
    return list_connected_sources(customer_id=customer_id)


def _truncate_text(value: Any, limit: int = TRACE_PREVIEW_LIMIT) -> str:
    """Convert arbitrary values into bounded strings for trace payloads."""
    text = str(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...[truncated]"


def _emit_progress_event(
    callback: ProgressEventCallback | None,
    event_type: str,
    message: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Safely emit a progress event without breaking flow execution."""
    if callback is None:
        return
    payload = {
        "event_type": event_type,
        "message": message,
        "metadata": metadata or {},
    }
    try:
        callback(payload)
    except Exception as exc:
        logger.debug("agent_mesh_progress_emit_failed: %s", exc)


def _tool_source_label(tool_name: str) -> str:
    """Map internal tool names to user-facing source labels."""
    mapping = {
        "hubspot_crm_search": "HubSpot",
        "fathom_meetings": "Fathom",
    }
    return mapping.get(tool_name, tool_name.replace("_", " ").title())


def _summarize_tool_params(params: dict[str, Any]) -> str:
    """Create concise parameter preview for progress UI."""
    details: list[str] = []
    action = str(params.get("action") or "").strip()
    if action:
        details.append(f"action={action}")
    search_query = params.get("search_query")
    if isinstance(search_query, str) and search_query.strip():
        details.append(f"query={_truncate_text(search_query.strip(), limit=80)}")
    recording_id = params.get("recording_id")
    if isinstance(recording_id, int):
        details.append(f"recording_id={recording_id}")
    return " | ".join(details)


def _safe_json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _extract_llm_usage(resp: Any) -> dict[str, Any]:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    extracted = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = getattr(usage, key, None)
        if value is not None:
            extracted[key] = value
    return extracted


def _extract_pydantic_usage(result: Any) -> dict[str, Any]:
    """Best-effort usage extraction across pydantic-ai versions."""
    try:
        usage = result.usage() if callable(getattr(result, "usage", None)) else None
        if usage is None:
            return {}
        return {
            "prompt_tokens": int(
                getattr(usage, "request_tokens", None)
                or getattr(usage, "prompt_tokens", None)
                or getattr(usage, "input_tokens", None)
                or 0
            ),
            "completion_tokens": int(
                getattr(usage, "response_tokens", None)
                or getattr(usage, "completion_tokens", None)
                or getattr(usage, "output_tokens", None)
                or 0
            ),
        }
    except Exception:
        return {}


def _resolve_pydantic_model(model_name: str) -> Any:
    """Resolve a pydantic-ai model object across provider versions."""
    try:
        from pydantic_ai.providers.litellm import LiteLLMProvider

        provider = LiteLLMProvider()
        try:
            from pydantic_ai.models.openai import OpenAIChatModel

            return OpenAIChatModel(model_name, provider=provider)
        except Exception:
            from pydantic_ai.models.openai import OpenAIModel

            return OpenAIModel(model_name, provider=provider)
    except Exception:
        pass

    try:
        from pydantic_ai.models.litellm import LiteLLMModel

        return LiteLLMModel(model_name)
    except Exception:
        return model_name


def _build_pydantic_agent(
    model: str,
    system_prompt: str,
    output_model: type[BaseModel],
) -> Any | None:
    """Build a pydantic-ai agent while handling API signature differences."""
    try:
        from pydantic_ai import Agent
    except Exception:
        return None

    model_candidates: list[Any] = []
    if isinstance(model, str) and ":" not in model:
        model_candidates.append(f"openai:{model}")
    model_candidates.append(model)
    resolved_model = _resolve_pydantic_model(model)
    if resolved_model not in model_candidates:
        model_candidates.append(resolved_model)

    last_error: Exception | None = None
    for model_candidate in model_candidates:
        for kwargs in (
            {
                "model": model_candidate,
                "output_type": output_model,
                "instructions": system_prompt,
            },
            {
                "model": model_candidate,
                "output_type": output_model,
                "system_prompt": system_prompt,
            },
        ):
            try:
                return Agent(**kwargs)
            except Exception as exc:
                last_error = exc
                continue
    if last_error is not None:
        logger.warning("pydantic_agent_build_failed: %s", last_error)
    return None


def _run_agent_sync(agent: Any, prompt: str) -> Any:
    """Run agent in sync context, supporting async-only versions."""
    run_sync = getattr(agent, "run_sync", None)
    if callable(run_sync):
        return run_sync(prompt)

    run_fn = getattr(agent, "run", None)
    if not callable(run_fn):
        raise RuntimeError("Pydantic agent does not expose run/run_sync")
    result = run_fn(prompt)
    if inspect.isawaitable(result):
        import asyncio

        return asyncio.run(result)
    return result


def _pydantic_structured_call(
    output_model: type[BaseModel],
    system: str,
    user: str,
    model: str,
    *,
    span_name: str,
    span_metadata: dict[str, Any] | None = None,
) -> tuple[BaseModel | None, str]:
    """
    Run a structured pydantic-ai stage.

    Returns:
        (parsed_output, status) where status is one of:
        - "success": pydantic-ai call succeeded
        - "unavailable": pydantic-ai is not available/buildable
        - "failed": pydantic-ai call failed at runtime
    """
    agent = _build_pydantic_agent(model, system, output_model)
    if agent is None:
        return None, "unavailable"

    langfuse_service = get_langfuse_service()
    metadata = dict(span_metadata or {})
    metadata.setdefault("component", "agentmesh")
    metadata.setdefault("flow", "retrieval")
    metadata["llm_backend"] = "pydantic_ai"

    with langfuse_service.span_scope(
        name=span_name,
        input_data={
            "model": model,
            "system_prompt": _truncate_text(system),
            "user_prompt": _truncate_text(user),
            "structured_output": output_model.__name__,
        },
        metadata=metadata,
    ) as span_info:
        observation = span_info.get("observation")
        try:
            raw_result = _run_agent_sync(agent, user)
            raw_output = (
                getattr(raw_result, "output", None)
                or getattr(raw_result, "data", None)
                or raw_result
            )
            if isinstance(raw_output, str):
                parsed_json = _safe_json_loads(raw_output)
                if parsed_json is not None:
                    raw_output = parsed_json
            parsed_output = (
                raw_output
                if isinstance(raw_output, output_model)
                else output_model.model_validate(raw_output)
            )
            if observation is not None:
                try:
                    observation.update(
                        output={
                            "llm_backend": "pydantic_ai",
                            "response_preview": _truncate_text(
                                parsed_output.model_dump_json(exclude_none=True)
                            ),
                            "usage": _extract_pydantic_usage(raw_result),
                        }
                    )
                except Exception:
                    pass
            return parsed_output, "success"
        except Exception as exc:
            error_message = str(exc).strip() or type(exc).__name__
            logger.warning(
                "pydantic_stage_failed span=%s output_model=%s error=%s",
                span_name,
                output_model.__name__,
                error_message,
            )
            if observation is not None:
                try:
                    observation.update(
                        output={
                            "llm_backend": "pydantic_ai",
                            "error": error_message,
                        },
                        level="ERROR",
                        status_message=f"PydanticAI stage failed: {error_message}",
                    )
                except Exception:
                    pass
            return None, "failed"


def _strip_markdown_fences(raw: str) -> str:
    """Strip markdown fences from raw model output if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")]
    return cleaned.strip()


def _extract_json_objects_from_text(raw: str) -> list[dict[str, Any]]:
    """Extract top-level JSON objects from mixed prose + fenced output."""
    extracted: list[dict[str, Any]] = []

    # Prefer explicit fenced JSON/code blocks first.
    for block in re.findall(r"```(?:json)?\s*([\s\S]*?)```", raw, flags=re.IGNORECASE):
        parsed = _safe_json_loads(block.strip())
        if isinstance(parsed, dict):
            extracted.append(parsed)
        elif isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    extracted.append(item)

    if extracted:
        return extracted

    # Fallback: scan for balanced top-level JSON objects.
    depth = 0
    start_index: int | None = None
    in_string = False
    escape_next = False
    for idx, char in enumerate(raw):
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start_index = idx
            depth += 1
            continue
        if char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start_index is not None:
                candidate = raw[start_index : idx + 1]
                parsed = _safe_json_loads(candidate)
                if isinstance(parsed, dict):
                    extracted.append(parsed)
                start_index = None

    return extracted


def _extract_tool_failure(raw_output: str) -> tuple[bool, str | None]:
    """Return (failed, message) for tool output payloads."""
    parsed = _safe_json_loads(raw_output)
    if not isinstance(parsed, dict):
        return False, None

    if parsed.get("ok") is False:
        error_payload = parsed.get("error")
        if isinstance(error_payload, dict):
            message = (
                str(error_payload.get("message") or "").strip()
                or str(error_payload.get("code") or "").strip()
                or "Tool call failed"
            )
            return True, message
        if isinstance(error_payload, str):
            message = error_payload.strip() or "Tool call failed"
            return True, message
        return True, "Tool call failed"

    direct_error = parsed.get("error")
    if isinstance(direct_error, str) and direct_error.strip():
        return True, direct_error.strip()
    return False, None


def _collect_failed_tool_messages(results: list[dict[str, Any]]) -> list[str]:
    """Collect tool failure messages from execution results."""
    failures: list[str] = []
    for result in results:
        output = result.get("output")
        if not isinstance(output, str):
            continue
        failed, message = _extract_tool_failure(output)
        if not failed:
            continue
        tool_name = str(result.get("tool") or "unknown_tool")
        failures.append(f"{tool_name}: {message or 'Tool call failed'}")
    return failures


def _build_tool_call_trace(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Build a compact execution trace for UI consumption.

    Each entry describes one tool invocation with status and a short summary.
    """
    trace: list[dict[str, Any]] = []
    for idx, result in enumerate(results, start=1):
        tool_name = str(result.get("tool") or "unknown_tool")
        params = result.get("params") if isinstance(result.get("params"), dict) else {}
        action = str(params.get("action") or "").strip() or None

        raw_output = result.get("output")
        output_text = raw_output if isinstance(raw_output, str) else json.dumps(raw_output)
        failed, failure_message = _extract_tool_failure(output_text)

        parsed_output = _safe_json_loads(output_text)
        payload = parsed_output.get("payload") if isinstance(parsed_output, dict) else None

        detail_parts: list[str] = []
        if action:
            detail_parts.append(f"action={action}")
        if isinstance(params.get("recording_id"), int):
            detail_parts.append(f"recording_id={params['recording_id']}")
        if isinstance(params.get("search_query"), str) and params.get("search_query"):
            detail_parts.append(f"query={_truncate_text(params['search_query'], limit=80)}")

        if isinstance(payload, dict):
            for key in ("meetings", "results", "contacts", "companies", "deals"):
                value = payload.get(key)
                if isinstance(value, list):
                    detail_parts.append(f"{len(value)} {key}")
                    break
            if isinstance(payload.get("total"), int):
                detail_parts.append(f"total={payload['total']}")

        description = (
            failure_message
            if failed
            else (" | ".join(detail_parts) if detail_parts else "Tool call completed")
        )

        phase = str(result.get("phase") or "initial")
        step_index = int(result.get("step_index") or idx)
        iteration = int(result.get("iteration") or 0)

        trace.append(
            {
                "id": f"{tool_name}-{phase}-{iteration}-{step_index}",
                "tool": tool_name,
                "action": action,
                "label": f"{tool_name}{'.' + action if action else ''}",
                "status": "failed" if failed else "completed",
                "description": _truncate_text(description, limit=220),
                "phase": phase,
                "iteration": iteration,
                "step_index": step_index,
            }
        )

    return trace


def _summarize_tool_output(raw_output: str) -> dict[str, Any]:
    """Create a compact output summary for tool spans."""
    summary: dict[str, Any] = {
        "output_preview": _truncate_text(raw_output),
    }
    parsed = _safe_json_loads(raw_output)
    if isinstance(parsed, dict):
        summary["output_type"] = "dict"
        summary["keys"] = list(parsed.keys())[:25]
        if isinstance(parsed.get("ok"), bool):
            summary["ok"] = parsed["ok"]
            if not parsed["ok"]:
                error_payload = parsed.get("error")
                if isinstance(error_payload, dict):
                    summary["error_message"] = _truncate_text(
                        error_payload.get("message", "")
                    )
                    summary["error_code"] = error_payload.get("code")
                    summary["status_code"] = error_payload.get("status_code")
        for key in ("results", "meetings", "contacts", "companies", "deals"):
            value = parsed.get(key)
            if isinstance(value, list):
                summary[f"{key}_count"] = len(value)
        if "error" in parsed:
            if isinstance(parsed["error"], str):
                summary["error"] = _truncate_text(parsed["error"])
    elif isinstance(parsed, list):
        summary["output_type"] = "list"
        summary["item_count"] = len(parsed)
    else:
        summary["output_type"] = "text"
    return summary


def _find_first_recording_id(payload: Any) -> str | None:
    """Recursively locate a usable recording_id value."""
    if isinstance(payload, dict):
        recording_id = payload.get("recording_id")
        if recording_id is not None:
            recording_id_str = str(recording_id).strip()
            if recording_id_str and recording_id_str != "__RECORDING_ID__":
                return recording_id_str

        # Prefer common collection keys before scanning all values.
        for key in ("meetings", "recordings", "items", "results", "data"):
            if key in payload:
                found = _find_first_recording_id(payload.get(key))
                if found:
                    return found

        for value in payload.values():
            found = _find_first_recording_id(value)
            if found:
                return found
        return None

    if isinstance(payload, list):
        for item in payload:
            found = _find_first_recording_id(item)
            if found:
                return found
        return None

    return None


def _resolve_recording_placeholder_from_results(results: list[dict]) -> str | None:
    """Find a recording ID from prior/current tool outputs for placeholder replacement."""
    for result in reversed(results):
        output = result.get("output")
        if not isinstance(output, str):
            continue
        parsed = _safe_json_loads(output)
        if parsed is None:
            continue
        found = _find_first_recording_id(parsed)
        if found:
            return found
    return None


# ------------------------------------------------------------------ #
#  Tool registry                                                      #
# ------------------------------------------------------------------ #

def _build_tool_registry(
    user_id: int, customer_id: str, active_sources: list[str]
) -> dict[str, Any]:
    """Instantiate tools and return a name→instance mapping."""
    registry: dict[str, Any] = {}
    if "hubspot" in active_sources:
        registry["hubspot_crm_search"] = HubSpotTool(
            user_id=user_id, customer_id=customer_id
        )
    if "fathom" in active_sources:
        registry["fathom_meetings"] = FathomTool(
            user_id=user_id, customer_id=customer_id
        )
    return registry


def _tool_descriptions(active_sources: list[str]) -> str:
    """Human-readable tool descriptions for LLM prompts."""
    descs = []
    if "hubspot" in active_sources:
        descs.append(
            "Tool: hubspot_crm_search\n"
            "  Description: Search HubSpot CRM for contacts, companies, or deals.\n"
            "  Parameters (JSON string in 'search_request_json'):\n"
            "    - object_type: 'contacts' | 'companies' | 'deals'\n"
            "    - query: optional free-text search\n"
            "    - filterGroups: optional HubSpot filter groups\n"
            "    - properties: list of property names to return\n"
            "    - limit: max results (1-100)\n"
            "  Example: {\"tool\": \"hubspot_crm_search\", \"params\": {\"search_request_json\": \"{\\\"object_type\\\":\\\"contacts\\\",\\\"query\\\":\\\"acme\\\",\\\"limit\\\":10}\"}}"
        )
    if "fathom" in active_sources:
        descs.append(
            "Tool: fathom_meetings\n"
            "  Description: Search Fathom meetings, get transcripts & summaries.\n"
            "  Parameters:\n"
            "    - action: 'list_meetings' | 'get_transcript' | 'get_summary'\n"
            "    - recording_id: integer (required for get_transcript/get_summary)\n"
            "    - search_query: optional text filter for list_meetings\n"
            "    - created_after: ISO-8601 date filter\n"
            "    - created_before: ISO-8601 date filter\n"
            "    - limit: 1-50 (default 10)\n"
            "    - include_summary: true/false (default true)\n"
            "    - include_transcript: true/false (default false)\n"
            "  Examples:\n"
            '    {\"tool\": \"fathom_meetings\", \"params\": {\"action\": \"list_meetings\", \"limit\": 10, \"include_summary\": true}}\n'
            '    {\"tool\": \"fathom_meetings\", \"params\": {\"action\": \"get_summary\", \"recording_id\": 12345}}'
        )
    return "\n\n".join(descs)


# ------------------------------------------------------------------ #
#  Execute a single tool call                                         #
# ------------------------------------------------------------------ #

def _execute_tool(registry: dict[str, Any], tool_name: str, params: dict) -> str:
    """Run a tool and return its string output."""
    tool = registry.get(tool_name)
    if tool is None:
        return ToolResponse.failure(
            source="agentmesh",
            action="dispatch",
            message=f"Unknown tool: {tool_name}",
            code="unknown_tool",
        ).to_json()
    try:
        if tool_name == "hubspot_crm_search":
            return tool._run(search_request_json=params.get("search_request_json", "{}"))
        elif tool_name == "fathom_meetings":
            fathom_params = dict(params or {})
            action = str(fathom_params.get("action") or "").strip().lower()
            if not action:
                action = "get_summary" if fathom_params.get("recording_id") else "list_meetings"
                logger.warning(
                    "Fathom call missing action. Defaulting to '%s' (params keys: %s)",
                    action,
                    sorted(fathom_params.keys()),
                )
            fathom_params["action"] = action

            if action in {"get_summary", "get_transcript"}:
                recording_id = fathom_params.get("recording_id")
                recording_id_str = str(recording_id).strip() if recording_id is not None else ""
                if recording_id_str.isdigit():
                    fathom_params["recording_id"] = int(recording_id_str)
                else:
                    logger.warning(
                        "Fathom action '%s' missing/invalid recording_id (%s). Falling back to list_meetings.",
                        action,
                        recording_id,
                    )
                    fathom_params.pop("recording_id", None)
                    fathom_params["action"] = "list_meetings"
                    fathom_params.setdefault("include_summary", True)
                    if action == "get_transcript":
                        fathom_params.setdefault("include_transcript", True)
                    fathom_params.setdefault("limit", 10)
            return tool._run(**fathom_params)
        else:
            return ToolResponse.failure(
                source="agentmesh",
                action="dispatch",
                message=f"No executor for tool: {tool_name}",
                code="executor_missing",
            ).to_json()
    except Exception as exc:
        logger.error("Tool %s failed: %s", tool_name, exc, exc_info=True)
        error_message = str(exc).strip() or type(exc).__name__
        return ToolResponse.failure(
            source="agentmesh",
            action="dispatch",
            message=error_message,
            code="executor_exception",
            retryable=False,
        ).to_json()


# ------------------------------------------------------------------ #
#  LLM helpers                                                        #
# ------------------------------------------------------------------ #

def _llm_call(
    system: str,
    user: str,
    model: str,
    *,
    span_name: str,
    span_metadata: dict[str, Any] | None = None,
) -> str:
    """litellm completion wrapper with explicit Langfuse span tracing."""
    langfuse_service = get_langfuse_service()
    metadata = dict(span_metadata or {})
    metadata.setdefault("component", "agentmesh")
    metadata.setdefault("flow", "retrieval")
    metadata["llm_backend"] = "litellm"

    with langfuse_service.span_scope(
        name=span_name,
        input_data={
            "model": model,
            "system_prompt": _truncate_text(system),
            "user_prompt": _truncate_text(user),
        },
        metadata=metadata,
    ) as span_info:
        resp = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        content = resp.choices[0].message.content.strip()
        usage = _extract_llm_usage(resp)
        finish_reason = getattr(resp.choices[0], "finish_reason", None)

        observation = span_info.get("observation")
        if observation is not None:
            try:
                observation.update(
                    output={
                        "response_preview": _truncate_text(content),
                        "llm_backend": "litellm",
                        "usage": usage,
                        "finish_reason": finish_reason,
                    }
                )
            except Exception:
                pass

        return content


# ------------------------------------------------------------------ #
#  Step 1: Planner                                                    #
# ------------------------------------------------------------------ #

PLANNER_SYSTEM = """\
You are a query planner. Given a user question and a set of available tools,
produce a sequence of tool calls that should be executed to answer the question.

Rules:
- For simple listing queries, one tool call is enough.
- For deeper questions (e.g., "summarize my last meeting"), plan multiple steps:
  first list meetings, then get_summary for the most relevant one.
  In that case, use a placeholder like "__RECORDING_ID__" for values
  that depend on earlier results – the executor will resolve them.
- Include appropriate parameters for each tool call.
"""


def _normalize_tool_steps(raw_steps: list[Any]) -> list[dict]:
    """Normalize arbitrary step payloads into executor-ready call objects."""
    normalized: list[dict] = []
    for step in raw_steps:
        tool_name = ""
        params: dict[str, Any] = {}
        if isinstance(step, ToolCallPlanStep):
            tool_name = step.tool.strip()
            params = step.params or {}
        elif isinstance(step, dict):
            tool_name = str(step.get("tool", "")).strip()
            params_value = step.get("params", {})
            if isinstance(params_value, dict):
                params = params_value
        if "." in tool_name:
            base_tool, action_name = tool_name.split(".", 1)
            if base_tool in {"fathom_meetings", "hubspot_crm_search"}:
                tool_name = base_tool
                if (
                    base_tool == "fathom_meetings"
                    and action_name in {"list_meetings", "get_summary", "get_transcript"}
                    and "action" not in params
                ):
                    params = {**params, "action": action_name}
        if tool_name == "fathom_meetings" and "action" not in params:
            default_action = "get_summary" if params.get("recording_id") else "list_meetings"
            params = {**params, "action": default_action}
        if tool_name:
            normalized.append({"tool": tool_name, "params": params})
    return normalized


def _plan(
    query: str,
    tool_descs: str,
    model: str,
    *,
    trace_context: dict[str, Any] | None = None,
) -> list[dict]:
    """Ask the LLM to produce a plan of tool calls."""
    user_msg = (
        f"User question: {query}\n\n"
        f"Available tools:\n{tool_descs}\n\n"
        "Produce the tool-call plan."
    )
    parsed_plan, call_status = _pydantic_structured_call(
        PlannerOutput,
        PLANNER_SYSTEM,
        user_msg,
        model,
        span_name="retrieval.plan.llm",
        span_metadata={
            **(trace_context or {}),
            "stage": "planner",
        },
    )
    if parsed_plan is not None:
        return _normalize_tool_steps(parsed_plan.calls)

    fallback_span_name = (
        "retrieval.plan.llm"
        if call_status == "unavailable"
        else "retrieval.plan.llm.fallback"
    )
    raw = _llm_call(
        PLANNER_SYSTEM,
        user_msg,
        model,
        span_name=fallback_span_name,
        span_metadata={
            **(trace_context or {}),
            "stage": "planner",
            "llm_backend": "litellm_fallback",
        },
    )
    raw = _strip_markdown_fences(raw)
    try:
        plan = json.loads(raw)
        if isinstance(plan, dict) and isinstance(plan.get("calls"), list):
            parsed = PlannerOutput.model_validate(plan)
            return _normalize_tool_steps(parsed.calls)
        if isinstance(plan, dict):
            plan = [plan]
        if not isinstance(plan, list):
            logger.error("Planner returned non-array JSON: %s", raw)
            return []
        return _normalize_tool_steps(plan)
    except json.JSONDecodeError:
        extracted_objects = _extract_json_objects_from_text(raw)
        if extracted_objects:
            normalized = _normalize_tool_steps(extracted_objects)
            if normalized:
                logger.warning("Planner fallback extracted %d JSON object(s)", len(normalized))
                return normalized
        logger.error("Planner returned invalid JSON: %s", raw)
        return []
    except Exception as exc:
        logger.error("Planner fallback parse failed: %s", exc)
        return []


# ------------------------------------------------------------------ #
#  Step 2: Execute plan                                               #
# ------------------------------------------------------------------ #

def _execute_plan(
    plan: list[dict],
    registry: dict[str, Any],
    prior_results: list[dict],
    *,
    trace_context: dict[str, Any] | None = None,
    phase: str = "initial",
    iteration: int = 0,
    event_callback: ProgressEventCallback | None = None,
) -> list[dict]:
    """Execute each tool call in the plan, resolving placeholders."""
    langfuse_service = get_langfuse_service()
    results = []
    for index, step in enumerate(plan, start=1):
        tool_name = step.get("tool", "")
        params = step.get("params", {})
        placeholder_resolved = False
        placeholder_error: str | None = None

        # Resolve placeholders from already executed results (same plan) and prior runs.
        params_str = json.dumps(params)
        if "__RECORDING_ID__" in params_str:
            available_results = prior_results + results
            resolved_recording_id = _resolve_recording_placeholder_from_results(available_results)
            if resolved_recording_id:
                params_str = params_str.replace("__RECORDING_ID__", resolved_recording_id)
                placeholder_resolved = True
            else:
                unresolved_message = (
                    "Planner placeholder __RECORDING_ID__ could not be resolved "
                    "from prior tool outputs."
                )
                # For Fathom, continue execution so _execute_tool can gracefully
                # downgrade to list_meetings instead of failing hard.
                if tool_name == "fathom_meetings":
                    logger.warning(
                        "unresolved_recording_placeholder_fathom_fallback",
                        extra={
                            "tool": tool_name,
                            "phase": phase,
                            "iteration": iteration,
                            "step_index": index,
                        },
                    )
                else:
                    placeholder_error = unresolved_message
                    logger.warning(
                        "unresolved_recording_placeholder",
                        extra={
                            "tool": tool_name,
                            "phase": phase,
                            "iteration": iteration,
                            "step_index": index,
                        },
                    )

        if "__RECORDING_ID__" not in params_str:
            params = json.loads(params_str)
            if (
                isinstance(params, dict)
                and isinstance(params.get("recording_id"), str)
                and params["recording_id"].isdigit()
            ):
                params["recording_id"] = int(params["recording_id"])

        source_label = _tool_source_label(tool_name)
        param_summary = _summarize_tool_params(params if isinstance(params, dict) else {})
        start_description = f"{source_label}.{params.get('action')}" if isinstance(params, dict) and params.get("action") else source_label
        if param_summary:
            start_description = f"{start_description} | {param_summary}"
        _emit_progress_event(
            event_callback,
            "tool_started",
            f"Querying {source_label}",
            metadata={
                "tool": tool_name,
                "source": source_label,
                "phase": phase,
                "iteration": iteration,
                "step_index": index,
                "description": start_description,
                "params": params if isinstance(params, dict) else {},
            },
        )

        logger.info("Executing tool=%s params=%s", tool_name, params)
        span_name = f"retrieval.execute.tool.{tool_name or 'unknown'}"
        span_metadata = {
            **(trace_context or {}),
            "stage": "executor",
            "phase": phase,
            "iteration": iteration,
            "tool": tool_name,
            "step_index": index,
            "plan_size": len(plan),
            "placeholder_resolved": placeholder_resolved,
            "placeholder_error": placeholder_error,
        }
        with langfuse_service.span_scope(
            name=span_name,
            input_data={"tool": tool_name, "params": params},
            metadata=span_metadata,
        ) as span_info:
            if placeholder_error:
                output = ToolResponse.failure(
                    source="agentmesh",
                    action="resolve_placeholder",
                    message=placeholder_error,
                    code="planner_placeholder_unresolved",
                ).to_json()
            else:
                output = _execute_tool(registry, tool_name, params)
            observation = span_info.get("observation")
            if observation is not None:
                try:
                    summary = _summarize_tool_output(output)
                    failed, failure_message = _extract_tool_failure(output)
                    if failed:
                        observation.update(
                            output=summary,
                            level="ERROR",
                            status_message=failure_message or "Tool call failed",
                        )
                    else:
                        observation.update(output=summary)
                except Exception:
                    pass

        failed, failure_message = _extract_tool_failure(output)
        if failed:
            _emit_progress_event(
                event_callback,
                "tool_failed",
                f"{source_label} query failed",
                metadata={
                    "tool": tool_name,
                    "source": source_label,
                    "phase": phase,
                    "iteration": iteration,
                    "step_index": index,
                    "description": failure_message or "Tool call failed",
                    "params": params if isinstance(params, dict) else {},
                },
            )
        else:
            _emit_progress_event(
                event_callback,
                "tool_completed",
                f"{source_label} query completed",
                metadata={
                    "tool": tool_name,
                    "source": source_label,
                    "phase": phase,
                    "iteration": iteration,
                    "step_index": index,
                    "description": start_description if start_description else "Tool call completed",
                    "params": params if isinstance(params, dict) else {},
                },
            )

        results.append({
            "tool": tool_name,
            "params": params,
            "output": output,
            "phase": phase,
            "iteration": iteration,
            "step_index": index,
        })
    return results


# ------------------------------------------------------------------ #
#  Step 3: Evaluator (ReAct reasoning)                                #
# ------------------------------------------------------------------ #

EVALUATOR_SYSTEM = """\
You are an evaluator. Given the user's original question and the data
retrieved so far, decide if we have ENOUGH information to answer fully.

Rules:
- If we listed meetings but the user asked about content/details,
  request get_summary or get_transcript for the most relevant recording_id(s).
- If we got contacts but the user asked about related deals, request a deals search.
- Use ACTUAL recording_ids/values from the data, not placeholders.
- Request at most 3 follow-up calls.
"""


def _normalize_evaluator_response(
    done: bool,
    reason: str | None,
    follow_up_steps: list[Any],
) -> dict[str, Any]:
    """Normalize evaluator payload into the flow contract."""
    follow_up = _normalize_tool_steps(follow_up_steps)[:3]
    return {
        "done": bool(done),
        "reason": str(reason).strip() if reason else None,
        "follow_up": follow_up,
    }


def _evaluate(
    query: str,
    results_so_far: list[dict],
    tool_descs: str,
    model: str,
    *,
    trace_context: dict[str, Any] | None = None,
    iteration: int = 1,
) -> dict:
    """Evaluate if we have enough data or need follow-up queries."""
    results_summary = []
    for r in results_so_far:
        results_summary.append(
            f"Tool: {r['tool']}\nParams: {json.dumps(r['params'])}\n"
            f"Output:\n{r['output'][:3000]}"
        )
    results_text = "\n\n---\n\n".join(results_summary)

    user_msg = (
        f"User question: {query}\n\n"
        f"Data retrieved so far:\n{results_text}\n\n"
        f"Available tools:\n{tool_descs}\n\n"
        "Decide whether data is sufficient and provide follow-up tool calls if needed."
    )
    parsed_eval, call_status = _pydantic_structured_call(
        EvaluatorOutput,
        EVALUATOR_SYSTEM,
        user_msg,
        model,
        span_name="retrieval.evaluate.llm",
        span_metadata={
            **(trace_context or {}),
            "stage": "evaluator",
            "iteration": iteration,
            "result_count": len(results_so_far),
        },
    )
    if parsed_eval is not None:
        return _normalize_evaluator_response(
            parsed_eval.done,
            parsed_eval.reason,
            parsed_eval.follow_up,
        )

    fallback_span_name = (
        "retrieval.evaluate.llm"
        if call_status == "unavailable"
        else "retrieval.evaluate.llm.fallback"
    )
    raw = _llm_call(
        EVALUATOR_SYSTEM,
        user_msg,
        model,
        span_name=fallback_span_name,
        span_metadata={
            **(trace_context or {}),
            "stage": "evaluator",
            "iteration": iteration,
            "result_count": len(results_so_far),
            "llm_backend": "litellm_fallback",
        },
    )
    raw = _strip_markdown_fences(raw)
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return _normalize_evaluator_response(
                bool(parsed.get("done", True)),
                parsed.get("reason"),
                parsed.get("follow_up", []),
            )
        logger.error("Evaluator returned non-object JSON: %s", raw)
        return {"done": True}
    except json.JSONDecodeError:
        logger.error("Evaluator returned invalid JSON: %s", raw)
        return {"done": True}


# ------------------------------------------------------------------ #
#  Step 4: Synthesizer                                                #
# ------------------------------------------------------------------ #

SYNTHESIZER_SYSTEM = """\
You are a senior business analyst. Given raw data from various business tools
and the user's original question, write a clear, comprehensive answer.

Format your answer in markdown:
1. **Executive Summary** – 1-3 sentences directly answering the question.
2. **Key Findings** – Bullet points with the most important facts,
   including specific names, numbers, dates, and links.
3. **Details** (if the data warrants it) – Use tables, numbered lists,
   or sub-sections for richer breakdown.

Rules:
- ALWAYS include specific data from the results (names, dates, numbers, URLs).
- Use markdown formatting (bold, bullets, tables, links).
- If a meeting has a Fathom URL, include it as a clickable link.
- Do NOT include raw JSON.
- Be concise but complete – don't drop information the user would want.
- If no results were found, say so clearly and suggest alternatives.
"""


def _synthesize(
    query: str,
    all_results: list[dict],
    model: str,
    *,
    trace_context: dict[str, Any] | None = None,
) -> str:
    """Produce the final human-readable answer."""
    results_summary = []
    for r in all_results:
        results_summary.append(
            f"Source tool: {r['tool']}\n"
            f"Parameters: {json.dumps(r['params'])}\n"
            f"Data:\n{r['output']}"
        )
    results_text = "\n\n---\n\n".join(results_summary)

    user_msg = (
        f"User question: {query}\n\n"
        f"Retrieved data:\n\n{results_text}\n\n"
        "Write the final answer for the user."
    )
    parsed_answer, call_status = _pydantic_structured_call(
        SynthesizerOutput,
        SYNTHESIZER_SYSTEM,
        user_msg,
        model,
        span_name="retrieval.synthesize.llm",
        span_metadata={
            **(trace_context or {}),
            "stage": "synthesizer",
            "result_count": len(all_results),
        },
    )
    if parsed_answer is not None and parsed_answer.answer:
        return parsed_answer.answer.strip()

    fallback_span_name = (
        "retrieval.synthesize.llm"
        if call_status == "unavailable"
        else "retrieval.synthesize.llm.fallback"
    )
    return _llm_call(
        SYNTHESIZER_SYSTEM,
        user_msg,
        model,
        span_name=fallback_span_name,
        span_metadata={
            **(trace_context or {}),
            "stage": "synthesizer",
            "result_count": len(all_results),
            "llm_backend": "litellm_fallback",
        },
    )


# ------------------------------------------------------------------ #
#  Step 5: Follow-up question generator                               #
# ------------------------------------------------------------------ #

FOLLOWUP_SYSTEM = """\
You generate follow-up questions a user might want to ask next.

Given the user's original question, the answer they received, and
the available data-source capabilities, produce exactly 3 follow-up
questions.

Rules:
- Each question must be hyper-specific – reference actual names, dates,
  companies, or meetings from the answer.
- Questions should go DEEPER or ADJACENT:
  • Deeper: drill into a specific item (e.g. "What was discussed in the
    Cengage meeting on Feb 6?")
  • Adjacent: explore related data (e.g. "Show me all deals associated
    with Heartland Vet")
- Make questions that sound natural, as if a human typed them.
- Keep each question under 80 characters.
- Never repeat the original question.
"""


def _normalize_follow_up_questions(raw_questions: list[Any]) -> list[str]:
    """Normalize follow-up question payload to max 3 non-empty strings."""
    cleaned: list[str] = []
    for question in raw_questions:
        text = str(question).strip()
        if text:
            cleaned.append(text)
        if len(cleaned) == 3:
            break
    return cleaned


def _fallback_follow_up_questions(
    query: str,
    active_sources: list[str],
) -> list[str]:
    """
    Deterministic fallback follow-up prompts when LLM follow-up generation fails.

    Keeps UX consistent by always returning 3 safe, actionable prompts.
    """
    source_label = ", ".join(active_sources[:2]) if active_sources else "your connected sources"
    prompt = query.strip().rstrip("?")
    if prompt:
        prompt = _truncate_text(prompt, limit=58)
    else:
        prompt = "this topic"

    return [
        f"Can you break down {prompt} by timeline?",
        f"What evidence supports that answer from {source_label}?",
        f"What should I ask next to validate this conclusion?",
    ]


def _generate_follow_ups(
    query: str,
    answer: str,
    active_sources: list[str],
    tool_descs: str,
    model: str,
    *,
    trace_context: dict[str, Any] | None = None,
) -> list[str]:
    """Generate 3 hyper-specific follow-up questions."""
    user_msg = (
        f"Original question: {query}\n\n"
        f"Answer provided:\n{answer[:3000]}\n\n"
        f"Connected sources: {', '.join(active_sources)}\n"
        f"Available capabilities:\n{tool_descs}\n\n"
        "Generate 3 follow-up questions."
    )
    parsed_follow_ups, call_status = _pydantic_structured_call(
        FollowUpsOutput,
        FOLLOWUP_SYSTEM,
        user_msg,
        model,
        span_name="retrieval.followups.llm",
        span_metadata={
            **(trace_context or {}),
            "stage": "followups",
            "active_source_count": len(active_sources),
        },
    )
    if parsed_follow_ups is not None:
        normalized = _normalize_follow_up_questions(parsed_follow_ups.questions)
        if normalized:
            return normalized

    fallback_span_name = (
        "retrieval.followups.llm"
        if call_status == "unavailable"
        else "retrieval.followups.llm.fallback"
    )
    raw = _llm_call(
        FOLLOWUP_SYSTEM,
        user_msg,
        model,
        span_name=fallback_span_name,
        span_metadata={
            **(trace_context or {}),
            "stage": "followups",
            "active_source_count": len(active_sources),
            "llm_backend": "litellm_fallback",
        },
    )
    raw = _strip_markdown_fences(raw)
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            normalized = _normalize_follow_up_questions(result)
            if normalized:
                return normalized
        if isinstance(result, dict):
            questions = result.get("questions", [])
            if isinstance(questions, list):
                normalized = _normalize_follow_up_questions(questions)
                if normalized:
                    return normalized
    except json.JSONDecodeError:
        logger.error("Follow-up generator returned invalid JSON: %s", raw)
    return _fallback_follow_up_questions(query, active_sources)


# ------------------------------------------------------------------ #
#  Main Flow                                                          #
# ------------------------------------------------------------------ #

class RetrievalFlow:
    """
    Planner → Execute → Evaluate (loop) → Synthesize.

    Fully controlled pipeline without CrewAI overhead.
    """

    def run(
        self,
        query: str,
        user_id: int,
        customer_id: str,
        run_id: str | None = None,
        conversation_id: str | None = None,
        workspace_id: int | None = None,
        event_callback: ProgressEventCallback | None = None,
    ) -> dict:
        settings = get_settings()
        model = settings.default_llm_model
        langfuse_service = get_langfuse_service()

        trace_context: dict[str, Any] = {
            "component": "agentmesh",
            "flow": "retrieval",
            "customer_id": customer_id,
            "user_id": user_id,
        }
        if run_id:
            trace_context["run_id"] = run_id
        if conversation_id:
            trace_context["conversation_id"] = conversation_id
        if workspace_id is not None:
            trace_context["workspace_id"] = workspace_id

        _emit_progress_event(
            event_callback,
            "run_started",
            "Agent Mesh received your question",
            metadata={
                "query": _truncate_text(query, limit=200),
                "customer_id": customer_id,
                "workspace_id": workspace_id,
                "conversation_id": conversation_id,
            },
        )

        root_input = query

        if langfuse_service.current_trace_id:
            root_scope = langfuse_service.span_scope(
                name="retrieval.flow",
                input_data=root_input,
                metadata=trace_context,
            )
        else:
            root_scope = langfuse_service.trace_scope(
                name="agentmesh",
                input_data=root_input,
                metadata=trace_context,
                session_id=conversation_id or run_id,
                user_id=str(user_id),
            )

        with root_scope as flow_span_info:
            # Determine connected sources
            with langfuse_service.span_scope(
                name="retrieval.connected_sources",
                input_data={"customer_id": customer_id, "user_id": user_id},
                metadata={**trace_context, "stage": "connected_sources"},
            ) as source_span:
                sources = _connected_sources(customer_id)
                active_sources = sorted(sources)
                source_observation = source_span.get("observation")
                if source_observation is not None:
                    try:
                        source_observation.update(
                            output={
                                "active_sources": active_sources,
                                "active_source_count": len(active_sources),
                            }
                        )
                    except Exception:
                        pass

            _emit_progress_event(
                event_callback,
                "sources_connected",
                (
                    f"Connected sources: {', '.join(active_sources)}"
                    if active_sources
                    else "No connected data sources found"
                ),
                metadata={
                    "active_sources": active_sources,
                    "active_source_count": len(active_sources),
                },
            )

            if not active_sources:
                response = {
                    "error": "No connected data sources. Please connect HubSpot or Fathom first.",
                    "sources": [],
                }
                root_observation = flow_span_info.get("observation")
                if root_observation is not None:
                    try:
                        root_observation.update(
                            output=response,
                            level="ERROR",
                            status_message="No connected data sources",
                        )
                    except Exception:
                        pass
                _emit_progress_event(
                    event_callback,
                    "failed",
                    "No connected data sources found",
                    metadata={"reason": "no_connected_sources"},
                )
                return response

            # Build tool registry and descriptions
            with langfuse_service.span_scope(
                name="retrieval.build_registry",
                input_data={"active_sources": active_sources},
                metadata={**trace_context, "stage": "build_registry"},
            ) as registry_span:
                registry = _build_tool_registry(user_id, customer_id, active_sources)
                tool_descs = _tool_descriptions(active_sources)
                registry_observation = registry_span.get("observation")
                if registry_observation is not None:
                    try:
                        registry_observation.update(
                            output={
                                "registered_tools": sorted(list(registry.keys())),
                                "registered_tool_count": len(registry),
                            }
                        )
                    except Exception:
                        pass

            # --- Step 1: Plan ---
            logger.info("[Planner] Creating plan for query: %s", query)
            _emit_progress_event(
                event_callback,
                "planning_started",
                "Planning which connected knowledge sources to query",
                metadata={
                    "stage": "planning",
                    "active_sources": active_sources,
                },
            )
            with langfuse_service.span_scope(
                name="retrieval.plan",
                input_data={"query": query},
                metadata={**trace_context, "stage": "planning"},
            ) as planning_span:
                plan = _plan(query, tool_descs, model, trace_context=trace_context)
                logger.info("[Planner] Plan: %s", json.dumps(plan, indent=2))
                planning_observation = planning_span.get("observation")
                if planning_observation is not None:
                    try:
                        planning_output = {
                            "plan_step_count": len(plan),
                            "plan_preview": _truncate_text(json.dumps(plan)),
                        }
                        if plan:
                            planning_observation.update(output=planning_output)
                        else:
                            planning_observation.update(
                                output=planning_output,
                                level="ERROR",
                                status_message="Planner returned no executable tool calls",
                            )
                    except Exception:
                        pass

            _emit_progress_event(
                event_callback,
                "planning_completed",
                f"Planned {len(plan)} internal tool call(s)",
                metadata={
                    "stage": "planning",
                    "plan_step_count": len(plan),
                    "plan": plan,
                },
            )

            if not plan:
                response = {
                    "raw": "I wasn't able to create a search plan for your query. Please try rephrasing.",
                    "sources": active_sources,
                }
                root_observation = flow_span_info.get("observation")
                if root_observation is not None:
                    try:
                        root_observation.update(
                            output=response,
                            level="ERROR",
                            status_message="Planner produced empty plan",
                        )
                    except Exception:
                        pass
                _emit_progress_event(
                    event_callback,
                    "failed",
                    "Planner returned no executable tool calls",
                    metadata={"reason": "empty_plan"},
                )
                return response

            # --- Step 2: Execute initial plan ---
            logger.info("[Executor] Executing %d planned tool call(s)", len(plan))
            _emit_progress_event(
                event_callback,
                "execution_started",
                f"Executing {len(plan)} planned tool call(s)",
                metadata={
                    "stage": "execution",
                    "phase": "initial",
                    "plan_step_count": len(plan),
                },
            )
            with langfuse_service.span_scope(
                name="retrieval.execute_initial",
                input_data={"plan_step_count": len(plan)},
                metadata={**trace_context, "stage": "execute_initial_plan"},
            ) as execute_span:
                all_results = _execute_plan(
                    plan,
                    registry,
                    [],
                    trace_context=trace_context,
                    phase="initial",
                    iteration=0,
                    event_callback=event_callback,
                )
                logger.info("[Executor] Got %d result(s)", len(all_results))
                initial_failures = _collect_failed_tool_messages(all_results)
                execute_observation = execute_span.get("observation")
                if execute_observation is not None:
                    try:
                        execute_output = {
                            "result_count": len(all_results),
                            "failed_tool_count": len(initial_failures),
                            "failed_tools": initial_failures[:10],
                        }
                        if initial_failures:
                            execute_observation.update(
                                output=execute_output,
                                level="ERROR",
                                status_message=(
                                    f"{len(initial_failures)} tool call(s) failed in initial execution"
                                ),
                            )
                        else:
                            execute_observation.update(output=execute_output)
                    except Exception:
                        pass

            # --- Step 3: Evaluate → follow-up loop ---
            for iteration in range(MAX_REACT_ITERATIONS):
                logger.info("[Evaluator] Iteration %d – checking if data is sufficient", iteration + 1)
                _emit_progress_event(
                    event_callback,
                    "evaluation_started",
                    f"Evaluating retrieved context (pass {iteration + 1})",
                    metadata={
                        "stage": "evaluation",
                        "iteration": iteration + 1,
                        "results_so_far": len(all_results),
                    },
                )
                with langfuse_service.span_scope(
                    name="retrieval.evaluate",
                    input_data={
                        "iteration": iteration + 1,
                        "results_so_far": len(all_results),
                    },
                    metadata={
                        **trace_context,
                        "stage": "evaluator_iteration",
                        "iteration": iteration + 1,
                    },
                ) as evaluator_span:
                    evaluation = _evaluate(
                        query,
                        all_results,
                        tool_descs,
                        model,
                        trace_context=trace_context,
                        iteration=iteration + 1,
                    )
                    logger.info("[Evaluator] Result: %s", json.dumps(evaluation))
                    follow_up_calls = evaluation.get("follow_up", []) if isinstance(evaluation, dict) else []
                    evaluator_observation = evaluator_span.get("observation")
                    if evaluator_observation is not None:
                        try:
                            evaluator_observation.update(
                                output={
                                    "done": bool(evaluation.get("done", True)),
                                    "follow_up_count": len(follow_up_calls),
                                    "reason": evaluation.get("reason"),
                                }
                            )
                        except Exception:
                            pass

                _emit_progress_event(
                    event_callback,
                    "evaluation_completed",
                    (
                        "Current data is sufficient to answer"
                        if evaluation.get("done", True)
                        else "Need additional targeted tool calls"
                    ),
                    metadata={
                        "stage": "evaluation",
                        "iteration": iteration + 1,
                        "done": bool(evaluation.get("done", True)),
                        "reason": evaluation.get("reason"),
                        "follow_up_count": len(follow_up_calls),
                    },
                )

                if evaluation.get("done", True):
                    logger.info("[Evaluator] Data is sufficient, proceeding to synthesis")
                    break

                if not follow_up_calls:
                    logger.info("[Evaluator] No follow-ups suggested, proceeding to synthesis")
                    break

                logger.info(
                    "[Executor] Running %d follow-up call(s): %s",
                    len(follow_up_calls),
                    evaluation.get("reason", ""),
                )
                _emit_progress_event(
                    event_callback,
                    "execution_started",
                    f"Executing {len(follow_up_calls)} follow-up tool call(s)",
                    metadata={
                        "stage": "execution",
                        "phase": "follow_up",
                        "iteration": iteration + 1,
                        "follow_up_count": len(follow_up_calls),
                    },
                )
                with langfuse_service.span_scope(
                    name="retrieval.execute_followups",
                    input_data={
                        "iteration": iteration + 1,
                        "follow_up_count": len(follow_up_calls),
                    },
                    metadata={
                        **trace_context,
                        "stage": "execute_followups",
                        "iteration": iteration + 1,
                    },
                ) as followup_execute_span:
                    new_results = _execute_plan(
                        follow_up_calls,
                        registry,
                        all_results,
                        trace_context=trace_context,
                        phase="follow_up",
                        iteration=iteration + 1,
                        event_callback=event_callback,
                    )
                    all_results.extend(new_results)
                    followup_failures = _collect_failed_tool_messages(new_results)
                    followup_execute_observation = followup_execute_span.get("observation")
                    if followup_execute_observation is not None:
                        try:
                            followup_output = {
                                "new_result_count": len(new_results),
                                "total_result_count": len(all_results),
                                "failed_tool_count": len(followup_failures),
                                "failed_tools": followup_failures[:10],
                            }
                            if followup_failures:
                                followup_execute_observation.update(
                                    output=followup_output,
                                    level="ERROR",
                                    status_message=(
                                        f"{len(followup_failures)} follow-up tool call(s) failed"
                                    ),
                                )
                            else:
                                followup_execute_observation.update(output=followup_output)
                        except Exception:
                            pass

            # --- Step 4: Synthesize ---
            logger.info("[Synthesizer] Producing final answer from %d total result(s)", len(all_results))
            _emit_progress_event(
                event_callback,
                "synthesis_started",
                "Synthesizing final answer from retrieved evidence",
                metadata={
                    "stage": "synthesis",
                    "result_count": len(all_results),
                },
            )
            with langfuse_service.span_scope(
                name="retrieval.synthesize",
                input_data={"result_count": len(all_results)},
                metadata={**trace_context, "stage": "synthesize_answer"},
            ) as synthesis_span:
                answer = _synthesize(
                    query,
                    all_results,
                    model,
                    trace_context=trace_context,
                )
                logger.info("[Synthesizer] Answer length: %d chars", len(answer))
                synthesis_observation = synthesis_span.get("observation")
                if synthesis_observation is not None:
                    try:
                        synthesis_observation.update(
                            output={
                                "answer_preview": _truncate_text(answer),
                                "answer_length": len(answer),
                            }
                        )
                    except Exception:
                        pass
            _emit_progress_event(
                event_callback,
                "synthesis_completed",
                "Answer draft complete",
                metadata={
                    "stage": "synthesis",
                    "answer_length": len(answer),
                },
            )

            # --- Step 5: Generate follow-up questions ---
            logger.info("[FollowUps] Generating follow-up questions")
            _emit_progress_event(
                event_callback,
                "followups_started",
                "Generating recommended follow-up questions",
                metadata={
                    "stage": "followups",
                },
            )
            with langfuse_service.span_scope(
                name="retrieval.followups",
                input_data={"answer_length": len(answer)},
                metadata={**trace_context, "stage": "generate_followups"},
            ) as followups_span:
                follow_ups = _generate_follow_ups(
                    query,
                    answer,
                    active_sources,
                    tool_descs,
                    model,
                    trace_context=trace_context,
                )
                logger.info("[FollowUps] Generated %d follow-ups", len(follow_ups))
                followups_observation = followups_span.get("observation")
                if followups_observation is not None:
                    try:
                        followups_observation.update(
                            output={
                                "follow_up_count": len(follow_ups),
                                "follow_ups": follow_ups,
                            }
                        )
                    except Exception:
                        pass
            _emit_progress_event(
                event_callback,
                "followups_completed",
                f"Generated {len(follow_ups)} follow-up question(s)",
                metadata={
                    "stage": "followups",
                    "follow_up_count": len(follow_ups),
                    "follow_ups": follow_ups,
                },
            )

            all_failures = _collect_failed_tool_messages(all_results)
            tool_calls = _build_tool_call_trace(all_results)
            response = {
                "raw": answer,
                "sources": active_sources,
                "follow_ups": follow_ups,
                "tool_calls": tool_calls,
                "failed_tool_count": len(all_failures),
                "failed_tools": all_failures[:10],
            }

            root_observation = flow_span_info.get("observation")
            if root_observation is not None:
                try:
                    root_output = {
                        "status": "completed",
                        "sources": active_sources,
                        "result_count": len(all_results),
                        "tool_call_count": len(tool_calls),
                        "follow_up_count": len(follow_ups),
                        "answer_preview": _truncate_text(answer),
                        "failed_tool_count": len(all_failures),
                        "failed_tools": all_failures[:10],
                    }
                    if all_failures:
                        root_observation.update(
                            output=root_output,
                            level="ERROR",
                            status_message=f"{len(all_failures)} tool call(s) failed during run",
                        )
                    else:
                        root_observation.update(output=root_output)
                except Exception:
                    pass

            _emit_progress_event(
                event_callback,
                "completed",
                "Agent Mesh run complete",
                metadata={
                    "sources": active_sources,
                    "tool_call_count": len(tool_calls),
                    "follow_up_count": len(follow_ups),
                    "failed_tool_count": len(all_failures),
                },
            )
            return response
