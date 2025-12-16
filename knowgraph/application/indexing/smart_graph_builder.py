"""Smart Graph Builder using Intelligence Provider."""

import asyncio
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID

from knowgraph.application.indexing.graph_builder import (
    create_nodes_from_chunks,
    create_semantic_edges,
)
from knowgraph.config import BATCH_SIZE, MAX_CONCURRENT_REQUESTS
from knowgraph.domain.intelligence.code_analyzer import ASTAnalyzer
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.cache.cache_manager import CacheManager
from knowgraph.infrastructure.parsing.chunker import Chunk


class SmartGraphBuilder:
    """Graph builder that uses Intelligence Provider for semantic analysis."""

    def __init__(self, provider: IntelligenceProvider):
        """Initialize builder with provider."""
        self.provider = provider
        # CacheManager will be initialized in build() when path is known
        self.cache_manager: CacheManager | None = None
        self.ast_analyzer = ASTAnalyzer()

    async def build(
        self, chunks: list[Chunk], file_path: str, file_hash: str, graph_path: str
    ) -> tuple[list[Node], list[Edge]]:
        """Build graph nodes and edges from chunks using AI analysis."""
        # 1. Create Nodes (Initial)
        initial_nodes = create_nodes_from_chunks(chunks, file_path)

        # Initialize Cache Manager in the output directory
        cache_dir = Path(graph_path) / ".cache"
        self.cache_manager = CacheManager(cache_dir=str(cache_dir))

        # 2. Extract Entities (Hybrid Strategy: Cache -> AST -> LLM)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        # Prepare lists
        final_nodes_map: dict[UUID, Node] = {}
        nodes_needing_llm: list[Node] = []

        # Phase 1: Cache & AST Check
        for node in initial_nodes:
            # Check Cache
            cached_entities = self.cache_manager.get_entities(node.hash)
            if cached_entities is not None:
                final_nodes_map[node.id] = replace(
                    node, metadata={"entities": [e._asdict() for e in cached_entities]}
                )
                continue

            # Check AST (if code)
            # Simple heuristic: ASTAnalyzer handles syntax errors gracefully
            ast_entities = self.ast_analyzer.extract_entities(node.content)
            if ast_entities:
                self.cache_manager.save_entities(node.hash, ast_entities)
                final_nodes_map[node.id] = replace(
                    node, metadata={"entities": [e._asdict() for e in ast_entities]}
                )
                continue

            # If Cache Miss & AST Miss -> Queue for LLM
            nodes_needing_llm.append(node)

        # Phase 2: LLM Batch Processing
        if nodes_needing_llm:

            async def process_batch(batch_nodes: list[Node]) -> list[tuple[Node, list[Any]]]:
                """Process a batch of nodes and return (node, entities) pairs."""
                texts = [node.content for node in batch_nodes]
                async with semaphore:
                    for attempt in range(5):
                        try:
                            batch_entities = await self.provider.extract_entities_batch(texts)
                            return list(zip(batch_nodes, batch_entities))
                        except Exception:
                            if attempt == 4:
                                return [(n, []) for n in batch_nodes]
                            await asyncio.sleep(2**attempt)
                    return [(n, []) for n in batch_nodes]

            tasks = []
            for i in range(0, len(nodes_needing_llm), BATCH_SIZE):
                batch = nodes_needing_llm[i : i + BATCH_SIZE]
                tasks.append(process_batch(batch))

            batch_results = await asyncio.gather(*tasks)

            # Process LLM Results
            for batch_res in batch_results:
                for node, entities in batch_res:
                    # Save to Cache (even if empty, to avoid re-asking next time)
                    self.cache_manager.save_entities(node.hash, entities)
                    final_nodes_map[node.id] = replace(
                        node, metadata={"entities": [e._asdict() for e in entities]}
                    )

        # Reassemble final nodes in original order
        final_nodes = [final_nodes_map[node.id] for node in initial_nodes]

        # 4. Create Semantic Edges
        semantic_edges = create_semantic_edges(final_nodes)
        return final_nodes, semantic_edges
