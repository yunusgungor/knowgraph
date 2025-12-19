import asyncio
import contextlib
import sys
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path

import mcp.types as types

from knowgraph.adapters.cli.index_command import run_index
from knowgraph.application.evolution.incremental_update import (
    apply_incremental_update,
    detect_delta,
)
from knowgraph.application.indexing.graph_builder import normalize_markdown_content
from knowgraph.application.querying.impact_analyzer import analyze_impact_by_path
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.parsing.hasher import hash_content
from knowgraph.infrastructure.storage.filesystem import (
    list_all_nodes,
    read_all_edges,
    read_node_json,
)
from knowgraph.infrastructure.storage.manifest import read_manifest
from knowgraph.shared.security import validate_path


async def index_graph(
    input_path: str,
    graph_path: Path,
    provider: IntelligenceProvider,
    resume_mode: bool,
    gc: bool,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    access_token: str | None = None,
    progress_callback: Callable[[str, int, int, str], Awaitable[None]] | None = None,
) -> list[types.TextContent]:
    """Handles the indexing process for markdown files, repositories, and code directories.

    Supports:
    - Local markdown files and directories
    - Git repository URLs (GitHub, GitLab, Bitbucket)
    - Code directories (with automatic conversion to markdown)
    - Resume mode and incremental updates

    Args:
        progress_callback: Optional callback for progress updates (stage, current, total, message)
    """
    from knowgraph.infrastructure.parsing.repo_ingestor import detect_source_type

    # Detect source type first
    source_type = detect_source_type(input_path)

    # For repositories and remote code directories, skip path validation
    if source_type == "repository":
        # No path validation needed for URLs
        pass
    else:
        # Validate local paths
        try:
            input_path_obj = validate_path(input_path, must_exist=True, must_be_file=False)
            input_path = str(input_path_obj)
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: Invalid input path: {e}")]

    # Redirect stdout to stderr to prevent polluting the MCP JSON-RPC stream
    with contextlib.redirect_stdout(sys.stderr):
        try:
            graph_path / "metadata" / "manifest.json"

            if resume_mode and source_type != "repository":
                # Resume mode only works for local files/directories
                manifest = read_manifest(graph_path)
                if not manifest:
                    return [
                        types.TextContent(
                            type="text", text="Error: Cannot resume, no manifest found."
                        )
                    ]

                # Only perform single-file delta optimization if input is a file
                if Path(input_path).is_file():
                    with open(input_path, encoding="utf-8") as file:
                        new_content = file.read()

                    delta = detect_delta(manifest, new_content, str(input_path), graph_path)

                    if delta.added_nodes:
                        # Enrich nodes with AI
                        tasks = []
                        for node in delta.added_nodes:
                            tasks.append(provider.extract_entities(node.content))

                        results = await asyncio.gather(*tasks)
                        enriched_nodes = []
                        for node, entities in zip(delta.added_nodes, results):
                            new_node = replace(
                                node, metadata={"entities": [e._asdict() for e in entities]}
                            )
                            enriched_nodes.append(new_node)

                        delta.added_nodes = enriched_nodes
                        delta.modified_nodes = enriched_nodes

                    normalized_content = normalize_markdown_content(new_content)
                    file_hash = hash_content(normalized_content)

                    apply_incremental_update(
                        delta, manifest, file_hash, str(input_path), graph_path, gc_orphans=True
                    )

                    return [
                        types.TextContent(
                            type="text",
                            text=f"Successfully resumed/updated indexing for {input_path}.",
                        )
                    ]

            # Use run_index for all cases - it has efficient hash checking
            # and only processes changed files at manifest level
            await run_index(
                input_path=input_path,
                output_path=str(graph_path),
                progress_callback=progress_callback,
                provider=provider,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                access_token=access_token,
            )

            source_desc = (
                "repository"
                if source_type == "repository"
                else (
                    "code directory"
                    if source_type == "directory"
                    else (
                        "conversation history"
                        if source_type == "conversation"
                        else "markdown files"
                    )
                )
            )

            return [
                types.TextContent(
                    type="text",
                    text=f"Successfully indexed/updated {source_desc}: {input_path}.",
                ),
            ]

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            return [
                types.TextContent(type="text", text=f"Error indexing: {e!s}\n\n{error_details}")
            ]


def analyze_path_impact_report(
    element: str, graph_path: Path, max_hops: int
) -> list[types.TextContent]:
    """Performs impact analysis based on file paths."""
    with contextlib.redirect_stdout(sys.stderr):
        all_node_ids = list_all_nodes(graph_path)
        all_nodes = []
        for node_id in all_node_ids:
            node = read_node_json(node_id, graph_path)
            if node:
                all_nodes.append(node)

        all_edges = read_all_edges(graph_path)

        results = analyze_impact_by_path(element, all_nodes, all_edges, max_depth=max_hops)
        if not results:
            return [
                types.TextContent(
                    type="text", text=f"No nodes found matching path pattern: {element}"
                )
            ]

        # Format output
        output = f"Impact Analysis for Path Pattern: {element}\n" + "─" * 40 + "\n"
        for res in results:
            output += f"\n{res.get_summary()}"
            if res.dependent_nodes:
                output += "Dependent Files:\n"
                seen = set()
                for n in res.dependent_nodes[:20]:
                    if n.path not in seen:
                        output += f"  - {n.path}\n"
                        seen.add(n.path)
                if len(res.dependent_nodes) > 20:
                    output += f"  ... and {len(res.dependent_nodes)-20} more\n"
            else:
                output += "No dependencies found.\n"

        return [types.TextContent(type="text", text=output)]
