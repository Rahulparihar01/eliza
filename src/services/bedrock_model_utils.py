"""
Utilities for normalizing Bedrock model configuration payloads.

Bedrock model lists are stored in different shapes across the codebase:
- list[str] from generic provider configuration UI
- list[dict] from Bedrock-specific model discovery/add flows

This module provides a single normalization path so read-time consumers can
safely handle both.
"""

from __future__ import annotations

import logging
from typing import Any


def _infer_provider(model_id: str) -> str:
    """Infer provider name from Bedrock model identifier prefix."""
    if "." in model_id:
        return model_id.split(".", 1)[0].strip().lower() or "bedrock"
    return "bedrock"


def _coerce_bool(value: Any, default: bool = True) -> bool:
    """Coerce permissive bool-like values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _coerce_int_or_none(value: Any) -> int | None:
    """Best-effort int conversion for optional numeric model fields."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_dict(value: Any) -> dict[str, Any] | None:
    """Return dict-like data from common payload/object forms."""
    if isinstance(value, dict):
        return value
    # Pydantic v2 model
    if hasattr(value, "model_dump") and callable(value.model_dump):
        dumped = value.model_dump()
        return dumped if isinstance(dumped, dict) else None
    # Pydantic v1 model
    if hasattr(value, "dict") and callable(value.dict):
        dumped = value.dict()
        return dumped if isinstance(dumped, dict) else None
    return None


def _log_skip(
    logger: logging.Logger | None,
    *,
    context: str,
    reason: str,
    value: Any,
) -> None:
    """Emit a standard warning for skipped model entries."""
    if logger is None:
        return
    logger.warning(
        "bedrock_model_normalization_skip context=%s reason=%s value_type=%s value=%r",
        context or "-",
        reason,
        type(value).__name__,
        value,
    )


def normalize_bedrock_models(
    raw_models: Any,
    *,
    logger: logging.Logger | None = None,
    context: str = "",
) -> list[dict[str, Any]]:
    """
    Normalize Bedrock model payload into list[dict] with stable keys.

    Returned model dict shape:
    - model_id: str
    - model_name: str
    - provider: str
    - is_enabled: bool
    - max_tokens: Optional[int]
    - supports_streaming: bool
    """
    if raw_models is None:
        return []
    if not isinstance(raw_models, list):
        _log_skip(
            logger,
            context=context,
            reason="raw_models_not_list",
            value=raw_models,
        )
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw_models:
        if isinstance(item, str):
            model_id = item.strip()
            if not model_id:
                _log_skip(
                    logger,
                    context=context,
                    reason="empty_string_model_id",
                    value=item,
                )
                continue
            normalized.append(
                {
                    "model_id": model_id,
                    "model_name": model_id,
                    "provider": _infer_provider(model_id),
                    "is_enabled": True,
                    "max_tokens": None,
                    "supports_streaming": True,
                }
            )
            continue

        item_dict = _to_dict(item)
        if item_dict is None:
            _log_skip(
                logger,
                context=context,
                reason="unsupported_model_entry_type",
                value=item,
            )
            continue

        model_id_raw = (
            item_dict.get("model_id")
            or item_dict.get("id")
            or item_dict.get("model_name")
            or item_dict.get("name")
        )
        model_id = str(model_id_raw).strip() if model_id_raw is not None else ""
        if not model_id:
            _log_skip(
                logger,
                context=context,
                reason="missing_model_id",
                value=item_dict,
            )
            continue

        model_name_raw = item_dict.get("model_name") or item_dict.get("name") or model_id
        model_name = str(model_name_raw).strip() or model_id
        provider_raw = item_dict.get("provider")
        provider = str(provider_raw).strip().lower() if provider_raw is not None else ""
        if not provider:
            provider = _infer_provider(model_id)

        normalized.append(
            {
                "model_id": model_id,
                "model_name": model_name,
                "provider": provider,
                "is_enabled": _coerce_bool(item_dict.get("is_enabled"), default=True),
                "max_tokens": _coerce_int_or_none(item_dict.get("max_tokens")),
                "supports_streaming": _coerce_bool(
                    item_dict.get("supports_streaming"),
                    default=True,
                ),
            }
        )

    return normalized
