"""
Unit tests for Bedrock configuration (optional base_url for VPC endpoint).

No AWS or DB required; tests Pydantic models and that base_url is accepted.
"""

import pytest
from src.models.bedrock_config import (
    BedrockConfigurationCreate,
    BedrockConfigurationUpdate,
    BedrockAuthMethod,
)


class TestBedrockConfigurationCreate:
    """Test create model accepts optional base_url."""

    def test_base_url_optional(self):
        payload = {
            "auth_method": BedrockAuthMethod.IAM_ROLE,
            "aws_region": "us-east-1",
        }
        config = BedrockConfigurationCreate(**payload)
        assert config.base_url is None

    def test_base_url_can_be_set(self):
        config = BedrockConfigurationCreate(
            auth_method=BedrockAuthMethod.IAM_ROLE,
            aws_region="us-east-1",
            base_url="https://vpce-xxx.bedrock-runtime.us-east-1.vpce.amazonaws.com/openai/v1",
        )
        assert "vpce" in (config.base_url or "")


class TestBedrockConfigurationUpdate:
    """Test update model accepts optional base_url."""

    def test_base_url_optional(self):
        config = BedrockConfigurationUpdate(aws_region="us-west-2")
        assert config.base_url is None

    def test_base_url_can_be_set(self):
        config = BedrockConfigurationUpdate(
            base_url="https://custom.endpoint.com/openai/v1",
        )
        assert config.base_url == "https://custom.endpoint.com/openai/v1"
