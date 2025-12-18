"""Streaming utilities for memory-efficient query result processing.

Provides generator-based streaming for large result sets without loading
everything into memory at once.
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from knowgraph.domain.models.node import Node

T = TypeVar("T")


@dataclass
class StreamChunk:
    """A chunk of streaming data.
    
    Attributes
    ----------
        data: The actual data (node, result, etc.)
        index: Position in the stream
        total: Total number of items (if known)
        is_last: Whether this is the last chunk
    """
    
    data: Node | dict | str
    index: int
    total: int | None = None
    is_last: bool = False


@dataclass
class PaginationState:
    """State for pagination tracking.
    
    Attributes
    ----------
        page: Current page number (1-indexed)
        page_size: Items per page
        total_items: Total number of items
        has_next: Whether there are more pages
        has_previous: Whether there are previous pages
    """
    
    page: int
    page_size: int
    total_items: int
    
    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page * self.page_size < self.total_items
    
    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1
    
    @property
    def total_pages(self) -> int:
        """Calculate total number of pages."""
        return (self.total_items + self.page_size - 1) // self.page_size
    
    @property
    def start_index(self) -> int:
        """Calculate start index for current page."""
        return (self.page - 1) * self.page_size
    
    @property
    def end_index(self) -> int:
        """Calculate end index for current page."""
        return min(self.page * self.page_size, self.total_items)


def stream_nodes(nodes: list[Node], chunk_size: int = 10) -> Iterator[StreamChunk]:
    """Stream nodes in chunks to avoid memory overflow.
    
    Args:
    ----
        nodes: List of nodes to stream
        chunk_size: Number of nodes per chunk
        
    Yields:
    ------
        StreamChunk containing a batch of nodes
        
    Example:
    -------
        >>> for chunk in stream_nodes(all_nodes, chunk_size=5):
        ...     process_chunk(chunk.data)
        ...     print(f"Processed {chunk.index + 1}/{chunk.total}")
    """
    total = len(nodes)
    
    for i in range(0, total, chunk_size):
        chunk_nodes = nodes[i:i + chunk_size]
        yield StreamChunk(
            data=chunk_nodes,
            index=i // chunk_size,
            total=(total + chunk_size - 1) // chunk_size,
            is_last=(i + chunk_size >= total),
        )


async def stream_nodes_async(
    nodes: list[Node], chunk_size: int = 10
) -> AsyncIterator[StreamChunk]:
    """Async version of stream_nodes for concurrent processing.
    
    Args:
    ----
        nodes: List of nodes to stream
        chunk_size: Number of nodes per chunk
        
    Yields:
    ------
        StreamChunk containing a batch of nodes
        
    Example:
    -------
        >>> async for chunk in stream_nodes_async(all_nodes, chunk_size=5):
        ...     await process_chunk_async(chunk.data)
        ...     print(f"Processed {chunk.index + 1}/{chunk.total}")
    """
    total = len(nodes)
    
    for i in range(0, total, chunk_size):
        chunk_nodes = nodes[i:i + chunk_size]
        yield StreamChunk(
            data=chunk_nodes,
            index=i // chunk_size,
            total=(total + chunk_size - 1) // chunk_size,
            is_last=(i + chunk_size >= total),
        )
        # Allow other tasks to run
        await asyncio.sleep(0)


def paginate_nodes(
    nodes: list[Node], page: int = 1, page_size: int = 20
) -> tuple[list[Node], PaginationState]:
    """Paginate a list of nodes.
    
    Args:
    ----
        nodes: All nodes to paginate
        page: Page number (1-indexed)
        page_size: Number of items per page
        
    Returns:
    -------
        Tuple of (page_nodes, pagination_state)
        
    Example:
    -------
        >>> page_nodes, state = paginate_nodes(all_nodes, page=2, page_size=10)
        >>> print(f"Page {state.page} of {state.total_pages}")
        >>> print(f"Has next: {state.has_next}")
    """
    total = len(nodes)
    state = PaginationState(page=page, page_size=page_size, total_items=total)
    
    start = state.start_index
    end = state.end_index
    
    page_nodes = nodes[start:end]
    
    return page_nodes, state


async def stream_load_nodes_async(
    node_ids: list[UUID],
    graph_store_path,
    chunk_size: int = 50,
) -> AsyncIterator[StreamChunk]:
    """Stream-load nodes from disk without loading all at once.
    
    This is memory-efficient for large result sets as it only loads
    chunk_size nodes into memory at a time.
    
    Args:
    ----
        node_ids: List of node IDs to load
        graph_store_path: Path to graph storage
        chunk_size: Number of nodes to load per chunk
        
    Yields:
    ------
        StreamChunk containing loaded nodes
        
    Example:
    -------
        >>> async for chunk in stream_load_nodes_async(node_ids, path):
        ...     for node in chunk.data:
        ...         process_node(node)
    """
    from knowgraph.infrastructure.storage.filesystem import read_node_json
    
    total = len(node_ids)
    
    for i in range(0, total, chunk_size):
        chunk_ids = node_ids[i:i + chunk_size]
        
        # Load nodes concurrently within chunk
        async def load_node(node_id: UUID) -> Node | None:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, read_node_json, node_id, graph_store_path
            )
        
        tasks = [load_node(nid) for nid in chunk_ids]
        loaded_nodes = await asyncio.gather(*tasks)
        
        # Filter out None values
        valid_nodes = [n for n in loaded_nodes if n is not None]
        
        yield StreamChunk(
            data=valid_nodes,
            index=i // chunk_size,
            total=(total + chunk_size - 1) // chunk_size,
            is_last=(i + chunk_size >= total),
        )
