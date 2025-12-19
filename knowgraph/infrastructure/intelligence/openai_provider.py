"""OpenAI Intelligence Provider."""

import json
import os

from openai import AsyncOpenAI

from knowgraph.config import KNOWGRAPH_LLM_MODEL
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

    async def extract_entities_batch(self, texts: list[str]) -> list[list[Entity]]:
        """Extract entities from multiple texts in a single batch request."""
        # Prepare batched prompt
        segments = []
        for i, text in enumerate(texts):
            segments.append(f"--- SEGMENT {i} ---\n{text}\n")

        combined_text = "\n".join(segments)
        prompt = ENTITY_EXTRACTION_BATCH_PROMPT.format(text=combined_text)

        await self.rate_limiter.acquire()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                # Temperature removed - some models don't support temperature=0
            )
            # Update limits from headers (if available, client response might hide raw headers depending on lib version,
            # but usually response object has access if we use with_raw_response or verify lib behavior.
            # Assuming recent openai lib, response is Pydantic model. Accessing headers is tricky without 'with_raw_response'.
            # For strict correctness we should use .with_raw_response if available, but let's check basic usage first.
            # Actually standard openai python lib > 1.0 triggers exceptions on 429.
            # Reading headers is not directly on the model.
            # We skip update() for now or need a wrapper.
            # Let's focus on acquisition logic first as that prevents overload.
        except Exception:
            # Trigger backoff on error
            await self.rate_limiter.trigger_backoff()
            raise

        content = response.choices[0].message.content
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
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            # Temperature removed - some models don't support temperature=0
        )
        return response.choices[0].message.content or ""

    async def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text."""
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            # Temperature removed - some models don't support temperature=0
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
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            # Temperature removed - some models don't support temperature=0
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
