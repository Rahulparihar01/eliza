"""
RAGFlow background tasks.

Includes best-effort conversation title generation using the tenant's
configured AI provider.  Every failure path is a silent no-op — the
conversation title stays as "New conversation" and the user can always
rename manually.
"""
import re
import litellm
from src.celery_app import celery_app
from src.core.logging import get_logger

logger = get_logger(__name__)

# Preferred models per provider (smallest / cheapest first)
_PREFERRED_MODELS = {
    "openai": ["gpt-5-nano", "gpt-4.1-nano", "gpt-5-mini", "gpt-4.1-mini", "gpt-4o-mini"],
    "anthropic": ["claude-haiku-4", "claude-sonnet-4", "claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022"],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
    "bedrock": [],  # Use first available
    "together": [],
    "azure_openai": ["gpt-4o-mini"],
}

_TITLE_PROMPT = (
    "Generate a very short title (4-6 words) "
    "summarizing this chat message. Return only the title text, nothing else."
)


def _pick_model(provider) -> str | None:
    """Select the smallest available model for a provider.

    Returns the model name string, or None if nothing is available.
    """
    provider_name = (provider.provider_name or "").lower()
    config_data = provider.config_data or {}
    available = (
        config_data.get("available_models")
        or config_data.get("models")
        or []
    )

    # Walk the preference list; return the first one that is available
    for model in _PREFERRED_MODELS.get(provider_name, []):
        if model in available:
            return model

    # Fallback: first model in available_models
    if available:
        return available[0]

    return None


def _sanitize_title(raw: str) -> str | None:
    """Clean up and validate an LLM-generated title.

    Returns the cleaned title, or None if it should be rejected.
    """
    # Strip whitespace, surrounding quotes, and trailing punctuation
    title = raw.strip().strip("\"'""''").rstrip(".!?").strip()

    if not title:
        return None

    # Reject if it's just punctuation / special chars
    if not re.search(r"[a-zA-Z0-9]", title):
        return None

    # Enforce a 6-word limit; let the sidebar CSS handle text-overflow
    words = title.split()
    if len(words) > 6:
        title = " ".join(words[:6])

    # Hard cap at 50 chars as a safety net; truncate at word boundary
    max_len = 50
    if len(title) > max_len:
        truncated = title[:max_len].rsplit(" ", 1)
        if len(truncated) > 1 and len(truncated[0]) >= 8:
            title = truncated[0]
        else:
            title = title[:max_len]

    return title


@celery_app.task(
    bind=True,
    name="ragflow.generate_conversation_title",
    max_retries=0,
    ignore_result=True,
    autoretry_for=(),       # Override global autoretry — never retry
    time_limit=30,          # Hard kill after 30 s
    soft_time_limit=15,     # Raise SoftTimeLimitExceeded after 15 s
)
def generate_conversation_title(
    self,
    conversation_id: int,
    customer_id: str,
    user_message: str,
):
    """Best-effort title generation.  Never raises, never retries."""
    try:
        _generate_title_inner(conversation_id, customer_id, user_message)
    except Exception as e:
        logger.warning(
            "auto_title_generation_failed",
            metadata={
                "conversation_id": conversation_id,
                "customer_id": customer_id,
                "error": str(e),
            },
        )
        # Swallow — title stays as-is.


def _generate_title_inner(
    conversation_id: int,
    customer_id: str,
    user_message: str,
):
    """Core logic, separated so the outer task can catch everything."""
    from src.models import database
    from src.models.ragflow_domain import RAGFlowConversation
    from src.models.customer import CustomerAIProvider
    from src.utils.encryption import decrypt_value
    import json

    # ---- 1. DB session --------------------------------------------------
    if database.SessionLocal is None:
        database.init_database()
    db = database.SessionLocal()

    try:
        # ---- 2. Pick provider -------------------------------------------
        providers = (
            db.query(CustomerAIProvider)
            .filter(
                CustomerAIProvider.customer_id == customer_id,
                CustomerAIProvider.is_enabled == True,
            )
            .order_by(CustomerAIProvider.priority.asc())
            .all()
        )
        if not providers:
            logger.debug(f"No AI providers for {customer_id}, skipping auto-title")
            return

        # Try providers in priority order until we find one with a usable model
        model = None
        chosen_provider = None
        for provider in providers:
            model = _pick_model(provider)
            if model:
                chosen_provider = provider
                break

        if not model or not chosen_provider:
            logger.debug(f"No usable model for {customer_id}, skipping auto-title")
            return

        # ---- 3. Decrypt credentials ------------------------------------
        api_key = None
        base_url = None
        if chosen_provider.api_key_encrypted:
            try:
                creds = json.loads(decrypt_value(chosen_provider.api_key_encrypted))
                api_key = creds.get("api_key")
            except Exception:
                logger.warning(f"Failed to decrypt credentials for provider {chosen_provider.id}")
                return

        config_data = chosen_provider.config_data or {}
        base_url = config_data.get("base_url")

        # ---- 4. Call LLM -----------------------------------------------
        truncated_msg = user_message[:150]
        litellm.drop_params = True  # Silently drop unsupported params (e.g. temperature for gpt-5)

        raw_title = None
        # Try the chosen model first, then fall back through remaining providers
        all_attempts = [(chosen_provider, model)]
        for p in providers:
            if p.id == chosen_provider.id:
                continue
            m = _pick_model(p)
            if m:
                all_attempts.append((p, m))

        for attempt_provider, attempt_model in all_attempts:
            try:
                # Resolve credentials for this attempt
                attempt_api_key = api_key
                attempt_base_url = base_url
                if attempt_provider.id != chosen_provider.id:
                    if attempt_provider.api_key_encrypted:
                        try:
                            creds = json.loads(decrypt_value(attempt_provider.api_key_encrypted))
                            attempt_api_key = creds.get("api_key")
                        except Exception:
                            continue
                    attempt_base_url = (attempt_provider.config_data or {}).get("base_url")

                response = litellm.completion(
                    model=attempt_model,
                    messages=[
                        {"role": "system", "content": _TITLE_PROMPT},
                        {"role": "user", "content": truncated_msg},
                    ],
                    api_key=attempt_api_key,
                    base_url=attempt_base_url,
                    max_tokens=30,
                    temperature=0.3,
                    timeout=10,
                )
                raw_title = (response.choices[0].message.content or "").strip()
                model = attempt_model  # Track which model actually succeeded
                break
            except Exception as llm_err:
                logger.debug(
                    f"LLM call failed with model {attempt_model}: {llm_err}, trying next"
                )
                continue

        if not raw_title:
            logger.debug(f"All LLM attempts failed for {customer_id}, skipping auto-title")
            return

        # ---- 5. Validate -----------------------------------------------
        title = _sanitize_title(raw_title)
        if not title:
            logger.debug(f"LLM returned unusable title '{raw_title}', skipping")
            return

        # ---- 6. Write to DB (only if still default) --------------------
        conversation = db.query(RAGFlowConversation).get(conversation_id)
        if not conversation:
            return
        if conversation.title != "New conversation":
            # User already renamed — respect their choice.
            return

        conversation.title = title
        db.commit()

        logger.info(
            "auto_title_generated",
            metadata={
                "conversation_id": conversation_id,
                "title": title,
                "model": model,
                "provider": chosen_provider.provider_name,
            },
        )
    finally:
        db.close()
