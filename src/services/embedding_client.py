"""
OpenAI embedding client with model selection based on target dimension.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np
import openai
from openai import AsyncOpenAI

from src.core.config import get_settings

logger = logging.getLogger(__name__)

_OPENAI_EMBEDDING_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

_DIMENSION_ADJUSTABLE_MODELS = {
    "text-embedding-3-small",
    "text-embedding-3-large",
}


def select_openai_embedding_model(
    target_dimension: int,
    preferred_model: Optional[str] = None,
) -> str:
    """Pick the OpenAI embedding model closest to the target dimension."""
    if preferred_model in _OPENAI_EMBEDDING_DIMENSIONS:
        return preferred_model

    return min(
        _OPENAI_EMBEDDING_DIMENSIONS,
        key=lambda model: abs(_OPENAI_EMBEDDING_DIMENSIONS[model] - target_dimension),
    )


class OpenAIEmbeddingClient:
    """Async OpenAI embedding client with dimension-aware model selection."""

    def __init__(
        self,
        target_dimension: Optional[int] = None,
        model_name: Optional[str] = None,
    ):
        self.settings = get_settings()
        if not self.settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")

        self.target_dimension = target_dimension or self.settings.embedding_dimension
        self.model_name = select_openai_embedding_model(
            self.target_dimension,
            preferred_model=model_name or self.settings.embedding_model,
        )
        self.model_dimension = _OPENAI_EMBEDDING_DIMENSIONS[self.model_name]

        self.dimensions = None
        if (
            self.model_name in _DIMENSION_ADJUSTABLE_MODELS
            and self.target_dimension
            and self.target_dimension <= self.model_dimension
        ):
            self.dimensions = self.target_dimension

        self.output_dimension = self.dimensions or self.model_dimension

        self.client = AsyncOpenAI(
            api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_api_base_url,
        )

        logger.info(
            "OpenAI embedding client initialized",
            extra={
                "model": self.model_name,
                "target_dimension": self.target_dimension,
                "output_dimension": self.output_dimension,
            },
        )

    async def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for a list of texts."""
        if not texts:
            return np.empty((0, self.output_dimension), dtype=np.float32)

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._embed_batch(batch)
            all_embeddings.append(np.array(batch_embeddings, dtype=np.float32))

        return np.vstack(all_embeddings)

    async def _embed_batch(self, batch: List[str]) -> List[List[float]]:
        """Embed a single batch of texts."""
        request = {
            "model": self.model_name,
            "input": batch,
            "encoding_format": "float",
        }
        if self.dimensions is not None:
            request["dimensions"] = self.dimensions

        try:
            response = await self.client.embeddings.create(**request)
        except openai.BadRequestError as exc:
            logger.error(
                "OpenAI embedding request failed",
                extra={"model": self.model_name, "dimensions": self.dimensions},
            )
            raise exc

        return [item.embedding for item in response.data]
