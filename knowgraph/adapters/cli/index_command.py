"""CLI command for indexing markdown files, repositories, and code directories into knowledge graph."""

import sys
import time
from collections.abc import Awaitable, Callable

import click

from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.parsing.repo_ingestor import RepositoryIngestorError
from knowgraph.shared.security import validate_path

LANGUAGE_MAP = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "jsx": "javascript",
    "tsx": "typescript",
    "rs": "rust",
    "rb": "ruby",
    "md": "markdown",
    "java": "java",
    "go": "go",
    "php": "php",
    "html": "html",
    "css": "css",
    "txt": "text",
    "sql": "sql",
    "json": "json",
    "yml": "yaml",
    "yaml": "yaml",
    "xml": "xml",
    "csv": "csv",
    "tsv": "tsv",
    "ini": "ini",
    "conf": "conf",
    "cfg": "cfg",
    "properties": "properties",
    "toml": "toml",
    "cpp": "cpp",
    "cxx": "cpp",
    "cc": "cpp",
    "c": "c",
    "h": "c",
    "hpp": "cpp",
    "cs": "csharp",
    "kt": "kotlin",
    "swift": "swift",
    "m": "objectivec",
    "dart": "dart",
    "scala": "scala",
    "erl": "erlang",
    "ex": "elixir",
    "lua": "lua",
    "sh": "shell",
    "bash": "shell",
}

# Derived maps for easier access
EXT_MAP = {f".{ext}": lang for ext, lang in LANGUAGE_MAP.items()}


async def run_index(
    input_path: str,
    output_path: str,
    verbose: bool = False,
    provider: IntelligenceProvider | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    access_token: str | None = None,
    link_conversations: bool = False,
    incremental: bool = False,
    progress_callback: Callable[[str, int, int, str], Awaitable[None]] | None = None,
) -> None:
    """Execute indexing process (AI-Driven).

    Refactored to use helper functions for better maintainability.
    Complexity reduced from 94 to <8.

    Args:
    ----
        input_path: Path to input (markdown, code, or repo URL)
        output_path: Path for graph storage
        verbose: Enable verbose logging
        provider: Intelligence provider (defaults to OpenAI)
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude
        access_token: GitHub token for private repos
        link_conversations: Auto-discover and link conversations
        incremental: Only index new/modified files
        progress_callback: Optional callback for progress updates (stage, current, total, message)
    """
    from knowgraph.adapters.cli.index_helpers import (
        build_knowledge_graph,
        chunk_files,
        cleanup_temp_files,
        create_and_save_manifest,
        detect_and_prepare_source,
        load_existing_manifest,
        log_completion,
        prepare_files_and_hashes,
        run_post_index_hooks,
        should_skip_indexing,
        write_graph_to_storage,
    )

    start_time = time.time()

    try:
        # Step 1: Detect and prepare source
        if progress_callback:
            await progress_callback("source_detection", 1, 9, "Detecting and preparing source...")

        source_type, base_path, files_to_process = await detect_and_prepare_source(
            input_path, verbose, exclude_patterns, access_token
        )

        if not files_to_process:
            return

        # Step 2: Prepare files and compute hashes
        if progress_callback:
            await progress_callback("file_preparation", 2, 9, f"Preparing {len(files_to_process)} files...")

        graph_store_path = validate_path(output_path, must_exist=False, must_be_file=False)
        existing_manifest = load_existing_manifest(output_path, verbose)

        file_hashes, files_ready, cached_files, cache, file_hash_map = await prepare_files_and_hashes(
            files_to_process, base_path, verbose
        )

        # Step 3: Check if indexing can be skipped
        if progress_callback:
            await progress_callback("validation", 3, 9, "Checking if indexing needed...")

        if should_skip_indexing(existing_manifest, file_hashes, verbose):
            if progress_callback:
                await progress_callback("complete", 9, 9, "No changes detected, skipping indexing")
            return

        # Step 4: Chunk files
        if progress_callback:
            await progress_callback("chunking", 4, 9, f"Chunking {len(files_ready)} files...")

        all_chunks = await chunk_files(files_ready, verbose)

        # Load nodes from cache for cached files
        cached_nodes = []
        if cached_files and cache:
            from knowgraph.domain.models.node import Node
            for cached_file in cached_files:
                cached_result = cache.get_cached_result(cached_file)
                if cached_result and "nodes" in cached_result:
                    for node_dict in cached_result["nodes"]:
                        try:
                            cached_nodes.append(Node.from_dict(node_dict))
                        except Exception as e:
                            if verbose:
                                click.echo(f"Warning: Could not load cached node: {e}")

            if cached_nodes:
                click.echo(f"✓ Loaded {len(cached_nodes)} nodes from cache")

        # Step 5: Build knowledge graph
        if progress_callback:
            await progress_callback("graph_building", 5, 9, f"Building graph from {len(all_chunks)} chunks...")

        nodes, edges, _ = await build_knowledge_graph(
            all_chunks, input_path, graph_store_path, provider, verbose, base_path, file_hash_map
        )

        # Merge cached nodes with newly created nodes
        all_nodes = cached_nodes + nodes

        # Step 6: Write to storage
        if progress_callback:
            await progress_callback("writing", 6, 9, f"Writing {len(all_nodes)} nodes and {len(edges)} edges...")

        await write_graph_to_storage(all_nodes, edges, existing_manifest, graph_store_path, verbose)

        # Step 7: Create and save manifest
        if progress_callback:
            await progress_callback("manifest", 7, 9, "Creating and saving manifest...")

        await create_and_save_manifest(all_nodes, edges, file_hashes, graph_store_path, verbose)

        # Step 8: Run post-index hooks
        if progress_callback:
            await progress_callback("post_hooks", 8, 9, "Running post-index hooks...")

        await run_post_index_hooks(
            link_conversations, input_path, source_type, graph_store_path, verbose
        )

        # Step 9: Log completion
        if progress_callback:
            await progress_callback("complete", 9, 9, "Indexing completed successfully!")

        await write_graph_to_storage(all_nodes, edges, existing_manifest, graph_store_path, verbose)

        # Step 7: Create and save manifest
        await create_and_save_manifest(all_nodes, edges, file_hashes, graph_store_path, verbose)

        # Step 8: Run post-index hooks
        await run_post_index_hooks(
            link_conversations, input_path, source_type, graph_store_path, verbose
        )

        # Step 9: Log completion
        log_completion(start_time, graph_store_path, verbose)

    except RepositoryIngestorError as e:
        click.echo(f"Repository ingestion error: {e}", err=True)
        raise

    finally:
        # Cleanup temporary files
        cleanup_temp_files()


@click.command()
@click.argument("input_path", type=str)
@click.option(
    "--output",
    "-o",
    default=str(DEFAULT_GRAPH_STORE_PATH),
    help="Output path for the graph store",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option(
    "--link-conversations",
    is_flag=True,
    help="Auto-discover and link conversations to code after indexing",
)
@click.option(
    "--incremental",
    is_flag=True,
    help="Only index new/modified files (uses checkpoint for faster re-indexing)",
)
def index_command(
    input_path: str,
    output: str,
    verbose: bool,
    link_conversations: bool,
    incremental: bool,
) -> None:
    """Index markdown files, code, or repositories into a knowledge graph.

    Enhanced with:
    - Auto conversation discovery and linking (--link-conversations)
    - Incremental indexing for faster updates (--incremental)
    """
    import asyncio

    try:
        asyncio.run(
            run_index(
                input_path,
                output,
                verbose,
                link_conversations=link_conversations,
                incremental=incremental,
            )
        )
    except Exception as error:
        click.echo(f"Error: {error}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    index_command()
