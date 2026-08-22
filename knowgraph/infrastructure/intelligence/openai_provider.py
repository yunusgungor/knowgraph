"""OpenAI Intelligence Provider."""

import asyncio
import json
import os
from typing import Any

from openai import AsyncOpenAI

from knowgraph.config import (
    KNOWGRAPH_LLM_MODEL,
    LLM_MAX_INPUT_TOKENS,
    LLM_MAX_TOKENS,
    LLM_RETRY_BASE_DELAY,
    LLM_RETRY_COUNT,
)
from knowgraph.domain.intelligence.provider import (
    Entity,
    IntelligenceProvider,
    Relationship,
)
from knowgraph.infrastructure.intelligence.prompts import (
    ENTITY_EXTRACTION_BATCH_PROMPT,
    ENTITY_EXTRACTION_PROMPT,
    RELATIONSHIP_EXTRACTION_PROMPT,
)
from knowgraph.infrastructure.intelligence.rate_limiter import RateLimiter
from knowgraph.shared.circuit_breaker import CircuitBreakerError, get_circuit_breaker


class OpenAIProvider(IntelligenceProvider):
    """Intelligence provider using OpenAI API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = KNOWGRAPH_LLM_MODEL,
        api_base: str | None = None,
    ):
        """Initialize OpenAI provider."""
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("KNOWGRAPH_API_KEY"),
            base_url=api_base or os.getenv("KNOWGRAPH_API_BASE_URL"),
        )
        self.model = model
        self.rate_limiter = RateLimiter()
        # Shared circuit breaker: a persistently failing API opens the circuit
        # so callers fail fast instead of hammering a down service.
        self.circuit_breaker = get_circuit_breaker("openai_llm")

    async def _raw_completion(self, messages: list[dict], kwargs: dict) -> Any:
        """Issue the actual OpenAI chat completion (unwrapped)."""
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )

    async def _chat_completion(self, messages: list[dict], **kwargs: Any) -> Any:
        """Rate-limited, retried, circuit-broken chat completion.

        Every LLM call is throttled by the dynamic rate limiter, syncs its
        budgets from the API's rate-limit headers, retries transient failures
        (429 gets faster backoff), and is protected by a circuit breaker.
        Output is capped at LLM_MAX_TOKENS so a completion can't blow up cost
        or context.
        """
        kwargs.setdefault("max_tokens", LLM_MAX_TOKENS)
        await self.rate_limiter.acquire()

        for attempt in range(LLM_RETRY_COUNT):
            try:
                response = await self.circuit_breaker.call(
                    self._raw_completion, messages, kwargs
                )
            except CircuitBreakerError:
                # Service is down; don't keep hammering. Surface the error.
                raise
            except Exception as e:
                await self.rate_limiter.trigger_backoff()
                if attempt >= LLM_RETRY_COUNT - 1:
                    raise
                # Rate limits back off faster (3^n); generic errors 2^n.
                exponent = 3 if "429" in str(e).lower() or "rate limit" in str(e).lower() else 2
                await asyncio.sleep(LLM_RETRY_BASE_DELAY * (exponent**attempt))
                continue

            # Sync budgets from response headers (OpenAI/OpenRouter send
            # x-ratelimit-remaining-*); harmless if absent.
            headers = getattr(response, "headers", None)
            if headers is not None:
                await self.rate_limiter.update(headers)
            return response

        raise RuntimeError("LLM retry budget exhausted")

    async def extract_entities_batch(self, texts: list[str]) -> list[list[Entity]]:
        """Extract entities from multiple texts in a single batch request."""
        # Prepare batched prompt, dropping the tail segments that would blow
        # the input-token budget (approx 4 chars/token). Keeps the prompt under
        # the model context and avoids silently truncated JSON.
        segments = []
        budget = max(1, LLM_MAX_INPUT_TOKENS) * 4  # chars
        used = 0
        for i, text in enumerate(texts):
            seg = f"--- SEGMENT {i} ---\n{text}\n"
            if used + len(seg) > budget:
                break  # drop the rest; batch_output defaults to [] for them
            segments.append(seg)
            used += len(seg)

        combined_text = "\n".join(segments)
        prompt = ENTITY_EXTRACTION_BATCH_PROMPT.format(text=combined_text)

        response = await self._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            return [[] for _ in texts]

        try:
            data = json.loads(content)
            results = data.get("results", [])

            # Map back to original order
            batch_output = [[] for _ in texts]
            for item in results:
                # Parse segment ID safely
                try:
                    seg_id = int(item.get("segment_id", -1))
                    if 0 <= seg_id < len(texts):
                        entities = [Entity(**e) for e in item.get("entities", [])]
                        batch_output[seg_id] = entities
                except (ValueError, TypeError):
                    continue

            return batch_output
        except Exception:
            return [[] for _ in texts]

    async def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt."""
        response = await self._chat_completion([{"role": "user", "content": prompt}])
        return response.choices[0].message.content or ""

    async def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text."""
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        response = await self._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            return []

        try:
            # Expecting {"entities": [...]} or just [...] depending on model behavior,
            # but usually json mode requires explicit schema prompting or careful parsing.
            # For this simple implementation, we'll assume the prompt guides it enough
            # or we parse whatever list is there.
            # Let's refine the prompt instructions in a real scenario, but here:
            data = json.loads(content)
            if isinstance(data, list):
                return [Entity(**item) for item in data]
            if "entities" in data:
                return [Entity(**item) for item in data["entities"]]
            return []
        except Exception:
            return []

    async def extract_relationships(self, text: str, entities: list[Entity]) -> list[Relationship]:
        """Extract relationships from text."""
        entity_names = [e.name for e in entities]
        prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(text=text, entities=json.dumps(entity_names))
        response = await self._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            return []

        try:
            data = json.loads(content)
            if isinstance(data, list):
                return [Relationship(**item) for item in data]
            if "relationships" in data:
                return [Relationship(**item) for item in data["relationships"]]
            return []
        except Exception:
            return []
