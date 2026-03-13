from src.models.bedrock_config import BedrockModelInfo
from src.services.bedrock_model_utils import normalize_bedrock_models


def test_normalize_bedrock_models_accepts_string_entries():
    raw_models = [
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "  meta.llama3-1-70b-instruct-v1:0  ",
    ]

    normalized = normalize_bedrock_models(raw_models)

    assert len(normalized) == 2
    assert normalized[0]["model_id"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert normalized[0]["model_name"] == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert normalized[0]["provider"] == "anthropic"
    assert normalized[0]["is_enabled"] is True

    assert normalized[1]["model_id"] == "meta.llama3-1-70b-instruct-v1:0"
    assert normalized[1]["provider"] == "meta"


def test_normalize_bedrock_models_accepts_dict_entries():
    raw_models = [
        {
            "model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
            "model_name": "Claude 3.5 Haiku",
            "provider": "anthropic",
            "is_enabled": "false",
            "max_tokens": "8192",
            "supports_streaming": "true",
        }
    ]

    normalized = normalize_bedrock_models(raw_models)

    assert len(normalized) == 1
    assert normalized[0]["model_id"] == "anthropic.claude-3-5-haiku-20241022-v1:0"
    assert normalized[0]["model_name"] == "Claude 3.5 Haiku"
    assert normalized[0]["provider"] == "anthropic"
    assert normalized[0]["is_enabled"] is False
    assert normalized[0]["max_tokens"] == 8192
    assert normalized[0]["supports_streaming"] is True


def test_normalize_bedrock_models_accepts_pydantic_entries():
    model = BedrockModelInfo(
        model_id="amazon.titan-text-lite-v1",
        model_name="Titan Text Lite",
        provider="amazon",
        is_enabled=True,
        max_tokens=4096,
        supports_streaming=True,
    )

    normalized = normalize_bedrock_models([model])

    assert len(normalized) == 1
    assert normalized[0]["model_id"] == "amazon.titan-text-lite-v1"
    assert normalized[0]["model_name"] == "Titan Text Lite"
    assert normalized[0]["provider"] == "amazon"


def test_normalize_bedrock_models_skips_invalid_entries():
    raw_models = [None, "", {}, {"model_id": "   "}, 123]

    normalized = normalize_bedrock_models(raw_models)

    assert normalized == []
