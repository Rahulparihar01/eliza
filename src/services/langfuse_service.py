"""
Langfuse service wrapper.

Provides a safe, optional integration layer for Langfuse tracing.
When disabled or unavailable, methods become no-ops.
"""

from __future__ import annotations

import base64
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
import inspect
import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__, component="langfuse.service")


class LangfuseService:
    """Singleton-style Langfuse wrapper used by RAG, evals, and optimization flows."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._enabled = bool(self.settings.langfuse_enabled)
        self._client: Any = None
        self._initialized = False
        self._trace_id_var: ContextVar[Optional[str]] = ContextVar(
            "langfuse_trace_id", default=None
        )
        self._trace_session_id_var: ContextVar[Optional[str]] = ContextVar(
            "langfuse_trace_session_id", default=None
        )
        self._trace_user_id_var: ContextVar[Optional[str]] = ContextVar(
            "langfuse_trace_user_id", default=None
        )
        self.initialize()

    @staticmethod
    def _clean_env_value(value: Optional[str]) -> str:
        if not value:
            return ""
        cleaned = value.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (
            cleaned.startswith("'") and cleaned.endswith("'")
        ):
            cleaned = cleaned[1:-1]
        return cleaned.strip()

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    @property
    def client(self) -> Any:
        return self._client

    @property
    def host(self) -> str:
        # Support either LANGFUSE_HOST or LANGFUSE_BASE_URL.
        # LANGFUSE_HOST remains the primary setting in this codebase.
        configured_host = (
            os.getenv("LANGFUSE_HOST")
            or os.getenv("LANGFUSE_BASE_URL")
            or self.settings.langfuse_base_url
            or self.settings.langfuse_host
            or ""
        )
        return self._clean_env_value(configured_host).rstrip("/")

    @property
    def public_url(self) -> str:
        configured_public_url = (
            os.getenv("LANGFUSE_PUBLIC_URL")
            or self.settings.langfuse_public_url
            or os.getenv("LANGFUSE_BASE_URL")
            or self.settings.langfuse_base_url
            or self.host
            or ""
        )
        return self._clean_env_value(configured_public_url).rstrip("/")

    @property
    def project_id(self) -> Optional[str]:
        return self.settings.langfuse_project_id

    @property
    def embed_url(self) -> str:
        return self.settings.langfuse_embed_url or self.public_url

    @property
    def current_trace_id(self) -> Optional[str]:
        """Active trace id from the current execution context."""
        return self._trace_id_var.get()

    @staticmethod
    def _filter_none_values(values: Dict[str, Any]) -> Dict[str, Any]:
        return {key: value for key, value in values.items() if value is not None}

    def _call_with_fallback_kwargs(
        self,
        method: Any,
        kwargs: Dict[str, Any],
        optional_keys: List[str],
    ) -> Any:
        """
        Invoke SDK methods while gracefully dropping unsupported kwargs.

        Langfuse SDK signatures can vary between versions. We optimistically call
        with rich kwargs first, then progressively remove optional keys on TypeError.
        """
        payload = self._filter_none_values(dict(kwargs))
        try:
            return method(**payload)
        except TypeError as original_error:
            current_payload = dict(payload)
            for key in optional_keys:
                if key not in current_payload:
                    continue
                current_payload.pop(key, None)
                try:
                    return method(**current_payload)
                except TypeError:
                    continue
            raise original_error

    @staticmethod
    def _safe_update_observation(observation: Any, **kwargs: Any) -> None:
        """Best-effort observation update without raising."""
        if not observation or not hasattr(observation, "update"):
            return
        try:
            observation.update(**kwargs)
        except Exception:
            pass

    @contextmanager
    def trace_scope(
        self,
        *,
        name: str,
        input_data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """
        Start a root Langfuse trace/span and propagate context for nested spans.

        Yields:
            Dict with `trace_id` and `observation` (root span when available).
        """
        resolved_trace_id = trace_id or self.current_trace_id or uuid.uuid4().hex
        resolved_session_id = session_id or self._trace_session_id_var.get()
        resolved_user_id = user_id or self._trace_user_id_var.get()
        resolved_metadata: Dict[str, Any] = dict(metadata or {})
        resolved_metadata.setdefault("trace_id", resolved_trace_id)

        if not self.enabled:
            yield {
                "trace_id": resolved_trace_id,
                "observation": None,
                "session_id": resolved_session_id,
                "user_id": resolved_user_id,
            }
            return

        span_kwargs = {
            "name": name,
            "input": input_data,
            "metadata": resolved_metadata,
            "trace_id": resolved_trace_id,
            "session_id": resolved_session_id,
            "user_id": resolved_user_id,
        }

        optional_keys = ["trace_id", "session_id", "user_id", "input", "metadata"]
        observation_context = self._call_with_fallback_kwargs(
            self._client.start_as_current_span,
            span_kwargs,
            optional_keys,
        )

        trace_token = self._trace_id_var.set(resolved_trace_id)
        session_token = self._trace_session_id_var.set(resolved_session_id)
        user_token = self._trace_user_id_var.set(resolved_user_id)
        observation: Any = None
        try:
            with observation_context as active_observation:
                observation = active_observation
                try:
                    if hasattr(active_observation, "update_trace"):
                        active_observation.update_trace(
                            name=name,
                            user_id=resolved_user_id,
                            session_id=resolved_session_id,
                            metadata=resolved_metadata,
                            input=input_data,
                        )
                except Exception:
                    pass

                yield {
                    "trace_id": resolved_trace_id,
                    "observation": active_observation,
                    "session_id": resolved_session_id,
                    "user_id": resolved_user_id,
                }
        finally:
            self._trace_id_var.reset(trace_token)
            self._trace_session_id_var.reset(session_token)
            self._trace_user_id_var.reset(user_token)
            if observation is not None:
                self._safe_update_observation(observation, metadata=resolved_metadata)

    @contextmanager
    def span_scope(
        self,
        *,
        name: str,
        input_data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ):
        """Start a nested span under the active trace context."""
        active_trace_id = trace_id or self.current_trace_id
        resolved_metadata: Dict[str, Any] = dict(metadata or {})
        if active_trace_id:
            resolved_metadata.setdefault("trace_id", active_trace_id)

        if not self.enabled:
            yield {"trace_id": active_trace_id, "observation": None}
            return

        span_kwargs = {
            "name": name,
            "input": input_data,
            "metadata": resolved_metadata,
            "trace_id": active_trace_id,
            "session_id": self._trace_session_id_var.get(),
            "user_id": self._trace_user_id_var.get(),
        }
        optional_keys = ["trace_id", "session_id", "user_id", "input", "metadata"]
        try:
            observation_context = self._call_with_fallback_kwargs(
                self._client.start_as_current_span,
                span_kwargs,
                optional_keys,
            )
        except Exception as exc:
            logger.warning("langfuse_span_scope_start_failed", error=str(exc), name=name)
            yield {"trace_id": active_trace_id, "observation": None}
            return

        with observation_context as observation:
            yield {"trace_id": active_trace_id, "observation": observation}

    def begin_trace_scope(
        self,
        *,
        name: str,
        input_data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Manually enter a trace scope and return a handle.

        Useful for lifecycles controlled by callbacks/signals (e.g., Celery).
        """
        try:
            context_manager = self.trace_scope(
                name=name,
                input_data=input_data,
                metadata=metadata,
                trace_id=trace_id,
                session_id=session_id,
                user_id=user_id,
            )
            state = context_manager.__enter__()
            return {"context_manager": context_manager, "state": state}
        except Exception as exc:
            logger.warning("langfuse_begin_trace_scope_failed", error=str(exc), name=name)
            return {"context_manager": None, "state": {"trace_id": trace_id, "observation": None}}

    def end_trace_scope(
        self,
        handle: Optional[Dict[str, Any]],
        *,
        output_data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """Close a handle created by `begin_trace_scope`."""
        if not handle:
            return

        state = handle.get("state") or {}
        observation = state.get("observation")
        resolved_metadata = dict(metadata or {})
        if error is not None:
            resolved_metadata["error"] = str(error)
            resolved_metadata["error_type"] = type(error).__name__
        if output_data is not None:
            self._safe_update_observation(
                observation,
                output=output_data,
                metadata=resolved_metadata if resolved_metadata else None,
            )
        elif resolved_metadata:
            self._safe_update_observation(observation, metadata=resolved_metadata)

        context_manager = handle.get("context_manager")
        if context_manager is None:
            return
        try:
            context_manager.__exit__(None, None, None)
        except Exception as exc:
            logger.warning("langfuse_end_trace_scope_failed", error=str(exc))
        try:
            if self.enabled and hasattr(self._client, "flush"):
                self._client.flush()
        except Exception as exc:
            logger.warning("langfuse_trace_flush_failed", error=str(exc))

    def trace_event(
        self,
        *,
        name: str,
        input_data: Any = None,
        output_data: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a lightweight event span under the current trace context."""
        if not self.enabled:
            return
        try:
            with self.span_scope(name=name, input_data=input_data, metadata=metadata) as span_info:
                observation = span_info.get("observation")
                if output_data is not None:
                    self._safe_update_observation(observation, output=output_data)
        except Exception as exc:
            logger.warning("langfuse_trace_event_failed", error=str(exc))

    def initialize(self) -> None:
        """Initialize Langfuse client when enabled."""
        if self._initialized:
            return
        self._initialized = True

        if not self._enabled:
            logger.info("langfuse_disabled")
            return

        public_key = self._clean_env_value(self.settings.langfuse_public_key)
        secret_key = self._clean_env_value(self.settings.langfuse_secret_key)
        if not public_key or not secret_key:
            logger.warning("langfuse_missing_keys_disabling")
            self._enabled = False
            return

        try:
            from langfuse import Langfuse

            # Keep keys available for LiteLLM callback integrations.
            os.environ.setdefault("LANGFUSE_PUBLIC_KEY", public_key)
            os.environ.setdefault("LANGFUSE_SECRET_KEY", secret_key)
            if self.host:
                os.environ["LANGFUSE_HOST"] = self.host

            self._client = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=self.host,
            )
            self._configure_litellm_callbacks()
            logger.info("langfuse_initialized", host=self.host)
        except Exception as exc:
            self._enabled = False
            self._client = None
            logger.warning("langfuse_init_failed", error=str(exc))

    def _configure_litellm_callbacks(self) -> None:
        """Disable incompatible LiteLLM Langfuse callbacks; use manual tracing only."""
        try:
            import litellm
            from langfuse import Langfuse

            # LiteLLM's Langfuse integration currently forwards `sdk_integration=...`.
            # Older Langfuse SDK constructors in this environment do not accept it,
            # which causes runtime task failures on every LLM call.
            init_signature = inspect.signature(Langfuse.__init__)
            if "sdk_integration" not in init_signature.parameters:
                logger.warning(
                    "langfuse_litellm_callbacks_skipped_incompatible_sdk",
                    metadata={"reason": "missing_sdk_integration_constructor_arg"},
                )
                return

            success_callbacks = list(getattr(litellm, "success_callback", []) or [])
            failure_callbacks = list(getattr(litellm, "failure_callback", []) or [])

            cleaned_success = [cb for cb in success_callbacks if cb != "langfuse"]
            cleaned_failure = [cb for cb in failure_callbacks if cb != "langfuse"]

            litellm.success_callback = cleaned_success
            litellm.failure_callback = cleaned_failure
            logger.info(
                "langfuse_litellm_callbacks_disabled_manual_tracing",
                removed_success_callbacks=max(0, len(success_callbacks) - len(cleaned_success)),
                removed_failure_callbacks=max(0, len(failure_callbacks) - len(cleaned_failure)),
            )
        except Exception as exc:
            logger.warning("langfuse_litellm_callback_setup_failed", error=str(exc))

    def shutdown(self) -> None:
        """Flush/close Langfuse client when supported by SDK version."""
        if not self.enabled:
            return

        try:
            if hasattr(self._client, "flush"):
                self._client.flush()
            if hasattr(self._client, "shutdown"):
                self._client.shutdown()
        except Exception as exc:
            logger.warning("langfuse_shutdown_failed", error=str(exc))

    @staticmethod
    def _coerce_metadata(raw_metadata: Any) -> Dict[str, Any]:
        if isinstance(raw_metadata, dict):
            return raw_metadata
        if isinstance(raw_metadata, str):
            try:
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                return {}
        return {}

    def _public_api_base(self) -> str:
        host = self.host
        if not host:
            return ""
        if host.endswith("/api/public"):
            return host
        return f"{host}/api/public"

    def _public_api_auth_header(self) -> Optional[str]:
        public_key = self._clean_env_value(self.settings.langfuse_public_key)
        secret_key = self._clean_env_value(self.settings.langfuse_secret_key)
        if not public_key or not secret_key:
            return None
        credentials = f"{public_key}:{secret_key}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        return f"Basic {encoded}"

    def _build_trace_url(self, trace_id: str) -> Optional[str]:
        public_url = self.public_url
        if not public_url:
            return None
        if self.project_id:
            return f"{public_url}/project/{self.project_id}/traces/{trace_id}"
        return f"{public_url}/traces/{trace_id}"

    def _build_trace_url_from_payload(self, trace: Dict[str, Any], trace_id: str) -> Optional[str]:
        html_path = trace.get("htmlPath")
        if isinstance(html_path, str) and html_path:
            if html_path.startswith("http://") or html_path.startswith("https://"):
                return html_path
            public_url = self.public_url
            if public_url and html_path.startswith("/"):
                return f"{public_url}{html_path}"
        return self._build_trace_url(trace_id)

    async def fetch_workspace_traces(
        self,
        *,
        workspace_id: int,
        customer_id: Optional[str] = None,
        limit: int = 25,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch recent Langfuse traces and filter to workspace metadata.

        Returns (traces, error). The error is None on success.
        """
        if not self.settings.langfuse_enabled:
            return [], None

        api_base = self._public_api_base()
        auth_header = self._public_api_auth_header()
        if not api_base:
            return [], "Langfuse host is not configured"
        if not auth_header:
            return [], "Langfuse API keys are not configured"

        traces_url = f"{api_base}/traces"
        params = {"limit": max(1, min(limit, 100))}
        headers = {"Authorization": auth_header}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(traces_url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            error = f"Langfuse API returned {exc.response.status_code}"
            logger.warning("langfuse_trace_fetch_http_error", error=error)
            return [], error
        except Exception as exc:
            logger.warning("langfuse_trace_fetch_failed", error=str(exc))
            return [], str(exc)

        try:
            payload = response.json()
        except Exception as exc:
            logger.warning("langfuse_trace_fetch_invalid_json", error=str(exc))
            return [], "Langfuse response was not valid JSON"

        raw_traces = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(raw_traces, list):
            return [], "Langfuse response did not include a trace list"

        filtered_traces: List[Dict[str, Any]] = []
        for trace in raw_traces:
            if not isinstance(trace, dict):
                continue
            metadata = self._coerce_metadata(trace.get("metadata"))
            metadata_workspace_id = metadata.get("workspace_id")
            metadata_customer_id = metadata.get("customer_id")

            if metadata_workspace_id is None or str(metadata_workspace_id) != str(workspace_id):
                continue
            if customer_id and metadata_customer_id and str(metadata_customer_id) != str(customer_id):
                continue

            trace_id = trace.get("id") or trace.get("traceId")
            if not trace_id:
                continue

            filtered_traces.append(
                {
                    "trace_id": str(trace_id),
                    "name": trace.get("name"),
                    "timestamp": trace.get("timestamp") or trace.get("createdAt"),
                    "session_id": trace.get("sessionId") or metadata.get("session_id"),
                    "user_id": trace.get("userId"),
                    "metadata": metadata,
                    "input": trace.get("input"),
                    "output": trace.get("output"),
                    "url": self._build_trace_url_from_payload(trace, str(trace_id)),
                }
            )

        return filtered_traces, None

    @staticmethod
    def _workspace_metadata(
        *,
        workspace_id: Optional[int],
        domain: Optional[str],
        customer_id: Optional[str],
        prompt_version: Optional[int],
        gepa_variant_id: Optional[int],
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {}
        if workspace_id is not None:
            metadata["workspace_id"] = workspace_id
        if domain:
            metadata["domain"] = domain
        if customer_id:
            metadata["customer_id"] = customer_id
        if prompt_version is not None:
            metadata["prompt_version"] = prompt_version
        if gepa_variant_id is not None:
            metadata["gepa_variant_id"] = gepa_variant_id
        if extra:
            metadata.update(extra)
        return metadata

    @staticmethod
    def _format_chunks_for_trace(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format retrieved chunks into a readable structure for Langfuse display."""
        formatted = []
        for i, chunk in enumerate(chunks[:10]):
            meta = chunk.get("metadata") or {}
            entry: Dict[str, Any] = {
                "rank": i + 1,
                "document": chunk.get("document_title") or meta.get("document_title") or chunk.get("document_name") or meta.get("filename", "Unknown"),
                "score": round(chunk.get("score", 0), 4),
            }
            page = chunk.get("page_number") or meta.get("page_number")
            if page:
                entry["page"] = page
            page_range = chunk.get("page_range") or meta.get("page_range")
            if page_range:
                entry["page_range"] = page_range
            section = chunk.get("section_title") or meta.get("section_title")
            if section:
                entry["section"] = section
            hierarchy = chunk.get("section_hierarchy") or meta.get("section_hierarchy")
            if hierarchy:
                entry["section_path"] = " > ".join(hierarchy)
            chunk_type = chunk.get("chunk_type") or meta.get("chunk_type")
            if chunk_type:
                entry["type"] = chunk_type
            kb_name = chunk.get("knowledge_base_name") or meta.get("knowledge_base_name")
            if kb_name:
                entry["knowledge_base"] = kb_name
            summary = chunk.get("chunk_summary") or meta.get("chunk_summary")
            if summary:
                entry["summary"] = summary
            entities = chunk.get("key_entities") or meta.get("key_entities")
            if entities:
                entry["entities"] = entities
            doc_type = meta.get("document_type")
            if doc_type:
                entry["document_type"] = doc_type

            text = chunk.get("text", "")
            entry["text_preview"] = text[:300] + ("..." if len(text) > 300 else "")
            entry["text_length"] = len(text)
            formatted.append(entry)
        return formatted

    def trace_retrieval(
        self,
        *,
        query: str,
        chunks: list[Dict[str, Any]],
        workspace_id: Optional[int] = None,
        domain: Optional[str] = None,
        customer_id: Optional[str] = None,
        prompt_version: Optional[int] = None,
        gepa_variant_id: Optional[int] = None,
        session_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Trace retrieval step as a span with formatted chunk details."""
        if not self.enabled:
            return

        active_trace_id = self.current_trace_id
        metadata = self._workspace_metadata(
            workspace_id=workspace_id,
            domain=domain,
            customer_id=customer_id,
            prompt_version=prompt_version,
            gepa_variant_id=gepa_variant_id,
            extra=extra_metadata,
        )
        if session_id:
            metadata["session_id"] = session_id
        if active_trace_id:
            metadata.setdefault("trace_id", active_trace_id)

        formatted_chunks = self._format_chunks_for_trace(chunks)

        try:
            span_kwargs = {
                "name": "rag-retrieval",
                "input": {"query": query},
                "output": {
                    "chunks_retrieved": len(chunks),
                    "chunks": formatted_chunks,
                },
                "metadata": metadata,
                "trace_id": active_trace_id,
            }
            optional_keys = ["trace_id", "input", "output", "metadata"]
            span_context = self._call_with_fallback_kwargs(
                self._client.start_as_current_span,
                span_kwargs,
                optional_keys,
            )
            with span_context as span:
                if hasattr(span, "update"):
                    span.update(output={
                        "chunks_retrieved": len(chunks),
                        "chunks": formatted_chunks,
                    })
        except Exception as exc:
            logger.warning("langfuse_trace_retrieval_failed", error=str(exc))

    def trace_generation(
        self,
        *,
        name: str,
        model: str,
        input_data: Any,
        output_data: Any,
        usage_details: Optional[Dict[str, int]] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        workspace_id: Optional[int] = None,
        domain: Optional[str] = None,
        customer_id: Optional[str] = None,
        prompt_version: Optional[int] = None,
        gepa_variant_id: Optional[int] = None,
        session_id: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Trace model generation as a generation observation."""
        if not self.enabled:
            return

        active_trace_id = self.current_trace_id
        resolved_session_id = session_id or self._trace_session_id_var.get()
        resolved_user_id = self._trace_user_id_var.get()
        metadata = self._workspace_metadata(
            workspace_id=workspace_id,
            domain=domain,
            customer_id=customer_id,
            prompt_version=prompt_version,
            gepa_variant_id=gepa_variant_id,
            extra=extra_metadata,
        )
        if resolved_session_id:
            metadata["session_id"] = resolved_session_id
        if active_trace_id:
            metadata.setdefault("trace_id", active_trace_id)

        traced = False
        try:
            generation_kwargs = {
                "name": name,
                "model": model,
                "input": input_data,
                "metadata": metadata,
                "model_parameters": model_parameters,
                "usage_details": usage_details,
                "trace_id": active_trace_id,
                "session_id": resolved_session_id,
                "user_id": resolved_user_id,
            }
            generation = self._call_with_fallback_kwargs(
                self._client.start_generation,
                generation_kwargs,
                [
                    "trace_id",
                    "session_id",
                    "user_id",
                    "model_parameters",
                    "usage_details",
                    "metadata",
                    "input",
                ],
            )
            if hasattr(generation, "update"):
                generation.update(
                    output=output_data,
                    usage_details=usage_details,
                    metadata=metadata,
                )
            if hasattr(generation, "end"):
                generation.end()
            traced = True
        except Exception:
            # Fallback for SDK variants where start_generation differs
            try:
                span_kwargs = {
                    "name": name,
                    "input": input_data,
                    "output": output_data,
                    "metadata": metadata,
                    "trace_id": active_trace_id,
                    "session_id": resolved_session_id,
                    "user_id": resolved_user_id,
                }
                span_context = self._call_with_fallback_kwargs(
                    self._client.start_as_current_span,
                    span_kwargs,
                    ["trace_id", "session_id", "user_id", "output", "metadata", "input"],
                )
                with span_context as span:
                    if hasattr(span, "start_as_current_generation"):
                        nested_generation_kwargs = {
                            "name": f"{name}.generation",
                            "model": model,
                            "input": input_data,
                            "model_parameters": model_parameters,
                            "usage_details": usage_details,
                            "metadata": metadata,
                            "trace_id": active_trace_id,
                            "session_id": resolved_session_id,
                            "user_id": resolved_user_id,
                        }
                        nested_generation_context = self._call_with_fallback_kwargs(
                            span.start_as_current_generation,
                            nested_generation_kwargs,
                            [
                                "trace_id",
                                "session_id",
                                "user_id",
                                "model_parameters",
                                "usage_details",
                                "metadata",
                                "input",
                            ],
                        )
                        with nested_generation_context as generation:
                            if hasattr(generation, "update"):
                                generation.update(output=output_data, usage_details=usage_details)
                traced = True
            except Exception as exc:
                logger.warning("langfuse_trace_generation_failed", error=str(exc))

        if traced:
            try:
                if hasattr(self._client, "flush"):
                    self._client.flush()
            except Exception as exc:
                logger.warning("langfuse_trace_flush_failed", error=str(exc))

    def trace_workspace_chat(
        self,
        *,
        model: str,
        input_data: Any,
        output_data: Any,
        usage_details: Optional[Dict[str, int]] = None,
        workspace_id: Optional[int] = None,
        domain: Optional[str] = None,
        customer_id: Optional[str] = None,
        prompt_version: Optional[int] = None,
        gepa_variant_id: Optional[int] = None,
        session_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Trace end-to-end workspace chat interaction."""
        metadata = dict(extra_metadata or {})
        if latency_ms is not None:
            metadata["latency_ms"] = latency_ms

        self.trace_generation(
            name="workspace-chat",
            model=model,
            input_data=input_data,
            output_data=output_data,
            usage_details=usage_details,
            workspace_id=workspace_id,
            domain=domain,
            customer_id=customer_id,
            prompt_version=prompt_version,
            gepa_variant_id=gepa_variant_id,
            session_id=session_id,
            extra_metadata=metadata,
        )

    def trace_eval_question(
        self,
        *,
        run_id: str,
        question_id: str,
        question: str,
        expected_answer: str,
        model_response: str,
        metrics: Dict[str, Any],
        verdict: Optional[str],
        customer_id: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> None:
        """Trace a single eval question verdict/metrics."""
        self.trace_generation(
            name="rag-eval-question",
            model="eval-judge",
            input_data={
                "run_id": run_id,
                "question_id": question_id,
                "question": question,
                "expected_answer": expected_answer,
            },
            output_data={
                "response": model_response,
                "verdict": verdict,
                "metrics": metrics,
            },
            customer_id=customer_id,
            domain=domain,
            extra_metadata={
                "eval_run_id": run_id,
                "eval_question_id": question_id,
            },
        )

    def trace_gepa_step(
        self,
        *,
        job_id: str,
        step_name: str,
        model: str,
        input_data: Any,
        output_data: Any,
        strategy: Optional[str] = None,
        customer_id: Optional[str] = None,
        domain: Optional[str] = None,
        variant_id: Optional[int] = None,
    ) -> None:
        """Trace a GEPA optimization step."""
        self.trace_generation(
            name=f"gepa-{step_name}",
            model=model,
            input_data=input_data,
            output_data=output_data,
            customer_id=customer_id,
            domain=domain,
            gepa_variant_id=variant_id,
            extra_metadata={
                "gepa_job_id": job_id,
                "optimization_strategy": strategy,
            },
        )


@lru_cache()
def get_langfuse_service() -> LangfuseService:
    """Get cached Langfuse service."""
    return LangfuseService()
