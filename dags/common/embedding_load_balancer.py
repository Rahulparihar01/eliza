"""Bedrock embedding rate-limit manager with token-bucket throttling and fan-out.

Usable both from Airflow tasks and directly from EmbeddingService.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class RateLimiterConfig:
    requests_per_minute: int = 100
    tokens_per_minute: int = 300_000
    max_concurrent: int = 10
    retry_max: int = 8
    base_delay: float = 0.5


class TokenBucketRateLimiter:
    """Simple token-bucket that refills per-minute."""

    def __init__(self, rpm: int, tpm: int):
        self._rpm = rpm
        self._tpm = tpm
        self._request_tokens = float(rpm)
        self._token_tokens = float(tpm)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, estimated_tokens: int = 500) -> None:
        async with self._lock:
            self._refill()
            while self._request_tokens < 1.0 or self._token_tokens < estimated_tokens:
                await asyncio.sleep(0.05)
                self._refill()
            self._request_tokens -= 1.0
            self._token_tokens -= estimated_tokens

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._request_tokens = min(self._rpm, self._request_tokens + (self._rpm * elapsed / 60.0))
        self._token_tokens = min(self._tpm, self._token_tokens + (self._tpm * elapsed / 60.0))
        self._last_refill = now


class EmbeddingLoadBalancer:
    """Fan-out embedding requests through a rate limiter.

    Wraps any callable with signature ``(texts: list[str]) -> list[list[float]]``
    (e.g. ``EmbeddingService.embed_texts``).
    """

    def __init__(self, config: RateLimiterConfig | None = None):
        self.config = config or RateLimiterConfig()
        self._limiter = TokenBucketRateLimiter(
            rpm=self.config.requests_per_minute,
            tpm=self.config.tokens_per_minute,
        )
        self._semaphore: asyncio.Semaphore | None = None

    async def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        return self._semaphore

    async def embed_batched(
        self,
        texts: List[str],
        embed_fn,
        batch_size: int = 25,
    ) -> List[List[float]]:
        """Split *texts* into batches and call *embed_fn* with rate limiting."""
        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
        results: List[List[float]] = [[] for _ in batches]

        async def _process(idx: int, batch: List[str]) -> None:
            avg_tokens = max(1, sum(len(t.split()) for t in batch) // len(batch))
            await self._limiter.acquire(estimated_tokens=avg_tokens * len(batch))
            semaphore = await self._get_semaphore()
            async with semaphore:
                results[idx] = await embed_fn(batch)

        tasks = [_process(i, b) for i, b in enumerate(batches)]
        await asyncio.gather(*tasks)

        flat: List[List[float]] = []
        for r in results:
            flat.extend(r)
        return flat
