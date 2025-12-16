"""Smart Graph Builder using Intelligence Provider."""

import asyncio
from dataclasses import replace
from typing import Any
from uuid import UUID

from knowgraph.application.indexing.graph_builder import (
    create_nodes_from_chunks,
    create_semantic_edges,
)
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.parsing.chunker import Chunk


class SmartGraphBuilder:
    """Graph builder that uses Intelligence Provider for semantic analysis."""

    def __init__(self, provider: IntelligenceProvider):
        """Initialize builder with provider."""
        self.provider = provider

    async def build(
        self, chunks: list[Chunk], file_path: str, file_hash: str
    ) -> tuple[list[Node], list[Edge]]:
        """Build graph nodes and edges from chunks using AI analysis.

        This method:
        1. Creates base nodes from chunks.
        2. Uses AI to extract entities from each node.
        3. Creates semantic edges based on shared AI-extracted entities.
        """
        # 1. Create Nodes (Initial)
        initial_nodes = create_nodes_from_chunks(chunks, file_path)

        # 2. Extract Entities per Node (Parallel with Limits)
        # We limit concurrency preventing Rate Limits (e.g. OpenRouter)
        semaphore = asyncio.Semaphore(1)  # Conservative limit for Free Tier (e.g. 20 RPM)

        async def extract_with_retry(content: str) -> Any:
            async with semaphore:
                for attempt in range(5):
                    try:
                        return await self.provider.extract_entities(content)
                    except Exception:
                        if attempt == 4:  # Last attempt
                            # print(f"Failed to extract entities after retries: {e}")
                            return []
                        # Exponential backoff: 1s, 2s, 4s, 8s
                        wait_time = 2**attempt
                        # print(f"Rate limit hit, retrying in {wait_time}s... ({str(e)})")
                        await asyncio.sleep(wait_time)
                return []

        tasks = [extract_with_retry(node.content) for node in initial_nodes]

        # Execute all extractions
        results = await asyncio.gather(*tasks)

        final_nodes = []
        node_entities: dict[UUID, set[str]] = {}
        for node, entities in zip(initial_nodes, results):
            # Store lowercased entity names for matching
            entity_names = {e.name.lower() for e in entities}
            node_entities[node.id] = entity_names

            # Persist in metadata
            # We must recreate the node because it is frozen
            new_node = replace(node, metadata={"entities": [e._asdict() for e in entities]})
            final_nodes.append(new_node)

        # 4. Create Semantic Edges (Smart)
        # Assuming final_nodes have metadata populated
        semantic_edges = create_semantic_edges(final_nodes)

        all_edges = semantic_edges

        return final_nodes, all_edges
