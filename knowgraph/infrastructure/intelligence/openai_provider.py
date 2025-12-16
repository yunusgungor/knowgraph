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
    ENTITY_EXTRACTION_PROMPT,
    RELATIONSHIP_EXTRACTION_PROMPT,
)


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

    async def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return response.choices[0].message.content or ""

    async def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text."""
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0,
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
            temperature=0,
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
