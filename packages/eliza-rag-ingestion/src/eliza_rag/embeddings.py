"""
Embedding Service - Generate vector embeddings for text.

Supports:
- OpenAI embeddings (text-embedding-3-small, text-embedding-3-large, ada-002)
- Local embeddings via sentence-transformers
- AWS Bedrock Titan embeddings (v1: 1536d, v2: 1024d)
"""

import json
import logging
import asyncio
import os
import time
from typing import List, Optional, Union
from enum import Enum

logger = logging.getLogger(__name__)

_BEDROCK_THROTTLE_BASE_DELAY = 0.5
_BEDROCK_THROTTLE_MAX_RETRIES = 8


class EmbeddingProvider(str, Enum):
    """Embedding model providers."""
    OPENAI = "openai"
    LOCAL = "local"  # sentence-transformers
    BEDROCK = "bedrock"  # AWS Bedrock Titan


class EmbeddingService:
    """
    Generate embeddings using OpenAI, local, or AWS Bedrock models.

    Default: OpenAI text-embedding-3-small (1536 dimensions)
    Local: sentence-transformers all-MiniLM-L6-v2 (384 dimensions)
    Bedrock: amazon.titan-embed-text-v2:0 (1024 dimensions)
    """

    MODEL_DIMENSIONS = {
        # OpenAI
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
        # Local models
        "all-MiniLM-L6-v2": 384,
        "all-mpnet-base-v2": 768,
        "multi-qa-mpnet-base-dot-v1": 768,
        # AWS Bedrock Titan
        "amazon.titan-embed-text-v1": 1536,
        "amazon.titan-embed-text-v1:0": 1536,
        "amazon.titan-embed-text-v2:0": 1024,
    }

    def __init__(
        self,
        provider: EmbeddingProvider = EmbeddingProvider.OPENAI,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        batch_size: int = 100,
        aws_region: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.batch_size = batch_size
        self._local_model = None
        self._openai_client = None
        self._bedrock_client = None

        self._aws_region = aws_region or os.environ.get(
            "BEDROCK_EMBEDDING_REGION",
            os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        )
        self._aws_access_key_id = aws_access_key_id or os.environ.get("AWS_ACCESS_KEY_ID")
        self._aws_secret_access_key = aws_secret_access_key or os.environ.get("AWS_SECRET_ACCESS_KEY")
        self._aws_session_token = aws_session_token or os.environ.get("AWS_SESSION_TOKEN")

    # Public aliases so callers that used dev's attribute names still work
    @property
    def aws_region(self) -> str:
        return self._aws_region

    @property
    def aws_access_key_id(self) -> Optional[str]:
        return self._aws_access_key_id

    @property
    def aws_secret_access_key(self) -> Optional[str]:
        return self._aws_secret_access_key

    @property
    def aws_session_token(self) -> Optional[str]:
        return self._aws_session_token

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions for current model."""
        return self.MODEL_DIMENSIONS.get(self.model, 1536)
    
    def _get_openai_client(self):
        """Lazy-load OpenAI client."""
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI(api_key=self.api_key)
        return self._openai_client
    
    def _get_bedrock_client(self):
        """Lazy-load Bedrock Runtime client via boto3."""
        if self._bedrock_client is None:
            import boto3

            kwargs = {"region_name": self._aws_region}
            if self._aws_access_key_id and self._aws_secret_access_key:
                kwargs["aws_access_key_id"] = self._aws_access_key_id
                kwargs["aws_secret_access_key"] = self._aws_secret_access_key
                if self._aws_session_token:
                    kwargs["aws_session_token"] = self._aws_session_token
                self._bedrock_client = boto3.client("bedrock-runtime", **kwargs)
                logger.debug("Created Bedrock client using explicit credentials")
            else:
                self._bedrock_client = boto3.client("bedrock-runtime", **kwargs)
                logger.debug(
                    "Created Bedrock client using default credential chain (IAM/env)"
                )
        return self._bedrock_client
    
    def _get_local_model(self):
        """Lazy-load sentence-transformers model."""
        if self._local_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer(self.model)
                logger.info(f"Loaded local embedding model: {self.model}")
            except ImportError:
                raise RuntimeError("sentence-transformers not installed")
        return self._local_model
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector as list of floats
        """
        embeddings = await self.embed_texts([text])
        return embeddings[0]
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Clean texts
        texts = [t.replace("\n", " ").strip() for t in texts]
        texts = [t if t else " " for t in texts]  # Handle empty strings
        
        if self.provider == EmbeddingProvider.OPENAI:
            return await self._embed_openai(texts)
        elif self.provider == EmbeddingProvider.BEDROCK:
            return await self._embed_bedrock(texts)
        else:
            return await self._embed_local(texts)
    
    async def _embed_openai(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        client = self._get_openai_client()
        all_embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            try:
                response = await client.embeddings.create(
                    model=self.model,
                    input=batch
                )
                
                # Sort by index to maintain order
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [item.embedding for item in sorted_data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"OpenAI embedding error: {e}")
                raise
        
        return all_embeddings
    
    async def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local sentence-transformers."""
        model = self._get_local_model()
        
        # sentence-transformers is synchronous, run in thread pool
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        )
        
        return [emb.tolist() for emb in embeddings]

    def _invoke_bedrock_embedding(self, text: str) -> List[float]:
        """Synchronous single-text Bedrock Titan embedding call with retry."""
        client = self._get_bedrock_client()
        body: dict = {"inputText": text}
        if "v2" in self.model:
            body["dimensions"] = self.MODEL_DIMENSIONS.get(self.model, 1024)
            body["normalize"] = True

        import botocore.exceptions

        for attempt in range(_BEDROCK_THROTTLE_MAX_RETRIES):
            try:
                resp = client.invoke_model(
                    modelId=self.model,
                    contentType="application/json",
                    accept="application/json",
                    body=json.dumps(body),
                )
                result = json.loads(resp["body"].read())
                return result["embedding"]
            except botocore.exceptions.ClientError as exc:
                if exc.response["Error"]["Code"] == "ThrottlingException":
                    delay = _BEDROCK_THROTTLE_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        f"Bedrock throttled (attempt {attempt + 1}), backing off {delay:.1f}s"
                    )
                    time.sleep(delay)
                    continue
                raise
        raise RuntimeError(f"Bedrock throttled after {_BEDROCK_THROTTLE_MAX_RETRIES} retries")

    async def _embed_bedrock(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings via AWS Bedrock Titan (run in thread pool)."""
        loop = asyncio.get_event_loop()
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            futures = [
                loop.run_in_executor(None, self._invoke_bedrock_embedding, t)
                for t in batch
            ]
            batch_results = await asyncio.gather(*futures)
            all_embeddings.extend(batch_results)

        return all_embeddings

    async def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a search query.
        
        Some models have different encode modes for queries vs documents.
        Bedrock Titan uses the same encoding for query and documents.
        """
        if self.provider == EmbeddingProvider.LOCAL:
            model = self._get_local_model()
            # Check if model supports query encoding
            if hasattr(model, 'encode_queries'):
                loop = asyncio.get_event_loop()
                embedding = await loop.run_in_executor(
                    None,
                    lambda: model.encode_queries([query])[0]
                )
                return embedding.tolist()
        # OPENAI and BEDROCK: same as document encoding
        return await self.embed_text(query)
    
    def get_model_info(self) -> dict:
        """Get information about the current embedding model."""
        return {
            "provider": self.provider.value,
            "model": self.model,
            "dimensions": self.dimensions,
            "batch_size": self.batch_size
        }
