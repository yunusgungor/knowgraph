from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from knowgraph.application.indexing.smart_graph_builder import SmartGraphBuilder
from knowgraph.domain.intelligence.provider import Entity, IntelligenceProvider
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.parsing.chunker import Chunk


@pytest.mark.asyncio
async def test_smart_graph_builder_workflow():
    provider = AsyncMock(spec=IntelligenceProvider)
    # Return entities for node 1, empty for node 2
    # Return entities for node 1, empty for node 2
    # Batch processing expects a list of lists
    provider.extract_entities_batch.side_effect = [
        [[Entity(name="Apple", type="Fruit", description="A fruit")], []],
    ]

    chunks = [
        Chunk(
            content="c1",
            header="h",
            header_depth=1,
            header_path="p",
            line_start=1,
            line_end=2,
            token_count=1,
            has_code=False,
        ),
        Chunk(
            content="c2",
            header="h",
            header_depth=1,
            header_path="p",
            line_start=3,
            line_end=5,
            token_count=1,
            has_code=False,
        ),
    ]

    builder = SmartGraphBuilder(provider)

    # Mock helpers
    mock_nodes = [
        MagicMock(content="c1", id=uuid4(), metadata={}),
        MagicMock(content="c2", id=uuid4(), metadata={}),
    ]
    # Necessary to support replace()
    # Or rely on real nodes? Real nodes are safer.
    from knowgraph.domain.models.node import Node

    mock_nodes = [
        Node(
            id=uuid4(),
            hash="a" * 40,
            title="t1",
            content="c1",
            path="p",
            type="text",
            token_count=1,
            created_at=1,
        ),
        Node(
            id=uuid4(),
            hash="b" * 40,
            title="t2",
            content="c2",
            path="p",
            type="text",
            token_count=1,
            created_at=1,
        ),
    ]

    with (
        patch(
            "knowgraph.application.indexing.smart_graph_builder.create_nodes_from_chunks",
            return_value=mock_nodes,
        ),
        patch(
            "knowgraph.application.indexing.smart_graph_builder.create_semantic_edges",
            return_value=[],
        ) as mock_edges,
        patch(
            "knowgraph.application.indexing.smart_graph_builder.CacheManager"
        ) as MockCacheManager,
    ):
        # Configure mock cache
        mock_cache = MockCacheManager.return_value
        mock_cache.get_entities.return_value = None  # Force cache miss
        mock_cache.get_cache_for_chunk = MagicMock(return_value=None)

        nodes, edges = await builder.build(chunks, "file.md", "hash", graph_path=Path("."))

        assert len(nodes) == 2
        # Check metadata update
        assert nodes[0].metadata["entities"][0]["name"] == "Apple"
        assert nodes[0].metadata["entities"][0]["name"] == "Apple"
        # Only called once because of batching
        assert provider.extract_entities_batch.call_count == 1
        mock_edges.assert_called_once()


@pytest.mark.asyncio
async def test_retry_logic():
    provider = AsyncMock(spec=IntelligenceProvider)
    # Fail 2 times then succeed
    # Fail 2 times then succeed
    provider.extract_entities_batch.side_effect = [
        Exception("Rate Limit"),
        Exception("Rate Limit"),
        [[Entity(name="Apple", type="Fruit", description="desc")]],
    ]

    builder = SmartGraphBuilder(provider)
    chunk = Chunk(
        content="c",
        header="h",
        header_depth=1,
        header_path="p",
        line_start=1,
        line_end=2,
        token_count=1,
        has_code=False,
    )

    mock_node = Node(
        id=uuid4(),
        hash="a" * 40,
        title="t",
        content="c",
        path="p",
        type="text",
        token_count=1,
        created_at=1,
    )

    with (
        patch(
            "knowgraph.application.indexing.smart_graph_builder.create_nodes_from_chunks",
            return_value=[mock_node],
        ),
        patch(
            "knowgraph.application.indexing.smart_graph_builder.create_semantic_edges",
            return_value=[],
        ),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        patch(
            "knowgraph.application.indexing.smart_graph_builder.CacheManager"
        ) as MockCacheManager,
    ):
        mock_cache = MockCacheManager.return_value
        mock_cache.get_entities.return_value = None

        nodes, _ = await builder.build([chunk], "f", "h", graph_path=Path("."))

        # Should have slept twice
        assert provider.extract_entities_batch.call_count == 3
        # Should have slept twice
        assert mock_sleep.call_count == 2
        assert nodes[0].metadata["entities"][0]["name"] == "Apple"


@pytest.mark.asyncio
async def test_retry_failure():
    provider = AsyncMock(spec=IntelligenceProvider)
    # Fail 5 times (all attempts)
    # Fail 5 times (all attempts)
    provider.extract_entities_batch.side_effect = Exception("Fail")

    builder = SmartGraphBuilder(provider)
    chunk = Chunk(
        content="c",
        header="h",
        header_depth=1,
        header_path="p",
        line_start=1,
        line_end=2,
        token_count=1,
        has_code=False,
    )
    mock_node = Node(
        id=uuid4(),
        hash="a" * 40,
        title="t",
        content="c",
        path="p",
        type="text",
        token_count=1,
        created_at=1,
    )

    with (
        patch(
            "knowgraph.application.indexing.smart_graph_builder.create_nodes_from_chunks",
            return_value=[mock_node],
        ),
        patch(
            "knowgraph.application.indexing.smart_graph_builder.create_semantic_edges",
            return_value=[],
        ),
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch(
            "knowgraph.application.indexing.smart_graph_builder.CacheManager"
        ) as MockCacheManager,
    ):
        mock_cache = MockCacheManager.return_value
        mock_cache.get_entities.return_value = None

        nodes, _ = await builder.build([chunk], "f", "h", graph_path=Path("."))

        # Should return empty entities
        assert nodes[0].metadata["entities"] == []
