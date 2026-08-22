"""MCP Sampling Intelligence Provider."""

import json
from typing import Any

import mcp.types as types

from knowgraph.domain.intelligence.provider import (
    Entity,
    IntelligenceProvider,
    Relationship,
)
from knowgraph.infrastructure.intelligence.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    RELATIONSHIP_EXTRACTION_PROMPT,
)


class MCPSamplingProvider(IntelligenceProvider):
    """Intelligence provider using MCP Sampling (delegation to Agent)."""

    def __init__(self) -> None:
        """Initialize MCP Sampling provider.

        The live ServerSession is obtained from ``mcp.request_context()`` at
        call time (FastMCP public API), so no server handle needs to be wired
        through construction.
        """
        self.request_context: Any = None

    async def _sample(self, prompt: str) -> str:
        """Send a sampling request to the connected client."""
        # Construct a message for the agent
        messages = [
            types.SamplingMessage(
                role="user",
                content=types.TextContent(type="text", text=prompt),
            )
        ]

        # The public FastMCP API exposes the current request's session.
        try:
            import mcp

            session = mcp.request_context().session
        except Exception:
            # Back-compat fallback for callers that inject a request context.
            if self.request_context is not None:
                session = self.request_context.session
            else:
                raise RuntimeError("No request context available for sampling.") from None

        result = await session.create_message(
            messages=messages,
            max_tokens=2000,
            system_prompt="You are a helpful coding assistant analyzing code for a Knowledge Graph.",
        )

        # Parse result
        # result is likely a CreateMessageResult
        content = result.content
        if isinstance(content, types.TextContent):
            return content.text
        if isinstance(content, list):
            return "".join([c.text for c in content if c.type == "text"])
        return ""

    async def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt."""
        return await self._sample(prompt)

    async def extract_entities_batch(self, texts: list[str]) -> list[list[Entity]]:
        """Extract entities from multiple texts in a batch (serialized for MCP)."""
        # For MCP sampling, we currently process sequentially or would need parallel requests.
        # Simple sequential implementation for now to satisfy interface.
        results = []
        for text in texts:
            results.append(await self.extract_entities(text))
        return results

    async def extract_entities(self, text: str) -> list[Entity]:
        """Extract entities from text."""
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        prompt += "\n\nIMPORTANT: Return ONLY the JSON."

        # Strict delegation: No fallback. If this fails, we fail.
        response_text = await self._sample(prompt)

        try:
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)

            if isinstance(data, list):
                return [Entity(**item) for item in data]
            if "entities" in data:
                return [Entity(**item) for item in data["entities"]]
            return []
        except Exception:
            # We return empty list on parsing error, but we do NOT use heuristic fallback
            return []

    async def extract_relationships(self, text: str, entities: list[Entity]) -> list[Relationship]:
        """Extract relationships from text."""
        entity_names = [e.name for e in entities]
        prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(text=text, entities=json.dumps(entity_names))
        prompt += "\n\nIMPORTANT: Return ONLY the JSON."

        # Strict delegation
        response_text = await self._sample(prompt)

        try:
            clean_text = response_text.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_text)

            if isinstance(data, list):
                return [Relationship(**item) for item in data]
            if "relationships" in data:
                return [Relationship(**item) for item in data["relationships"]]
            return []
        except Exception:
            return []
