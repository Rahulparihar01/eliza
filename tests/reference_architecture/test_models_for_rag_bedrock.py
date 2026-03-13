from types import SimpleNamespace

import pytest

from src.api.routes.models import list_models_for_rag
from src.models.customer import CustomerAIProvider


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def query(self, model):
        assert model is CustomerAIProvider
        return _FakeQuery(self._rows)


class _FakeModelService:
    def __init__(self, providers, customer_id="test-customer"):
        self._providers = providers
        self.customer_config = SimpleNamespace(customer_id=customer_id)

    async def get_providers_status(self):
        return self._providers


def _provider(name: str, model_ids: list[str]):
    return SimpleNamespace(
        name=name,
        models=[SimpleNamespace(id=m, name=m) for m in model_ids],
    )


@pytest.mark.asyncio
async def test_for_rag_includes_bedrock_models_when_available_models_are_strings():
    bedrock_config_row = SimpleNamespace(
        id=42,
        config_data={
            "available_models": [
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "meta.llama3-1-70b-instruct-v1:0",
            ]
        },
    )
    service = _FakeModelService(providers=[_provider("openai_1", ["gpt-4o-mini"])])
    response = await list_models_for_rag(model_service=service, db=_FakeDB([bedrock_config_row]))

    models_by_id = {m.id: m for m in response.models}
    assert "gpt-4o-mini" in models_by_id
    assert "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0" in models_by_id
    assert "bedrock/meta.llama3-1-70b-instruct-v1:0" in models_by_id
    assert models_by_id["bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"].provider == "bedrock"


@pytest.mark.asyncio
async def test_for_rag_skips_disabled_bedrock_models_from_db_config():
    bedrock_config_row = SimpleNamespace(
        id=43,
        config_data={
            "available_models": [
                {"model_id": "anthropic.claude-3-opus-20240229-v1:0", "is_enabled": False},
                {"model_id": "amazon.titan-text-lite-v1", "is_enabled": True},
            ]
        },
    )
    service = _FakeModelService(providers=[])
    response = await list_models_for_rag(model_service=service, db=_FakeDB([bedrock_config_row]))

    ids = [m.id for m in response.models]
    assert "bedrock/amazon.titan-text-lite-v1" in ids
    assert "bedrock/anthropic.claude-3-opus-20240229-v1:0" not in ids
