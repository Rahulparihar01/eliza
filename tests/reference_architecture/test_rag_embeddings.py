"""
Unit tests for RAG embeddings (EmbeddingProvider, dimensions, Bedrock model names).

No AWS required for these tests; they cover enum, model dimensions, and service init.
"""

import pytest
from src.services.rag.embeddings import EmbeddingService, EmbeddingProvider


class TestEmbeddingProvider:
    """Test EmbeddingProvider enum includes Bedrock."""

    def test_bedrock_provider_exists(self):
        assert hasattr(EmbeddingProvider, "BEDROCK")
        assert EmbeddingProvider.BEDROCK.value == "bedrock"

    def test_all_providers(self):
        assert EmbeddingProvider.OPENAI.value == "openai"
        assert EmbeddingProvider.LOCAL.value == "local"
        assert EmbeddingProvider.BEDROCK.value == "bedrock"


class TestBedrockModelDimensions:
    """Test Titan model names have correct dimensions."""

    def test_titan_v1_dimensions(self):
        assert EmbeddingService.MODEL_DIMENSIONS.get("amazon.titan-embed-text-v1") == 1024
        assert EmbeddingService.MODEL_DIMENSIONS.get("amazon.titan-embed-text-v1:0") == 1024

    def test_titan_v2_dimensions(self):
        assert EmbeddingService.MODEL_DIMENSIONS.get("amazon.titan-embed-text-v2:0") == 1024


class TestEmbeddingServiceBedrockInit:
    """Test EmbeddingService with provider=BEDROCK (no network calls)."""

    def test_bedrock_dimensions_from_model(self):
        svc = EmbeddingService(
            provider=EmbeddingProvider.BEDROCK,
            model="amazon.titan-embed-text-v1",
            aws_region="us-east-1",
        )
        assert svc.dimensions == 1024

    def test_bedrock_default_region(self):
        svc = EmbeddingService(provider=EmbeddingProvider.BEDROCK, model="amazon.titan-embed-text-v1")
        assert svc.aws_region == "us-east-1"

    def test_bedrock_explicit_region(self):
        svc = EmbeddingService(
            provider=EmbeddingProvider.BEDROCK,
            model="amazon.titan-embed-text-v2:0",
            aws_region="us-west-2",
        )
        assert svc.aws_region == "us-west-2"
        assert svc.dimensions == 1024

    def test_get_model_info_bedrock(self):
        svc = EmbeddingService(
            provider=EmbeddingProvider.BEDROCK,
            model="amazon.titan-embed-text-v1",
            aws_region="us-east-1",
        )
        info = svc.get_model_info()
        assert info["provider"] == "bedrock"
        assert info["model"] == "amazon.titan-embed-text-v1"
        assert info["dimensions"] == 1024
