"""CLI command for indexing markdown files, repositories, and code directories into knowledge graph."""

import asyncio
import glob
import sys
import time
from pathlib import Path

import click

from knowgraph.application.indexing.graph_builder import (
    normalize_markdown_content,
)
from knowgraph.application.indexing.smart_graph_builder import SmartGraphBuilder
from knowgraph.config import (
    DEFAULT_GRAPH_STORE_PATH,
    EDGES_FILENAME,
)
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider
from knowgraph.infrastructure.parsing.chunker import chunk_markdown
from knowgraph.infrastructure.parsing.hasher import hash_content
from knowgraph.infrastructure.parsing.repo_ingestor import (
    RepositoryIngestorError,
    detect_source_type,
    ingest_source,
)
from knowgraph.infrastructure.search.sparse_index import SparseIndex
from knowgraph.infrastructure.storage.filesystem import write_all_edges, write_node_json
from knowgraph.infrastructure.storage.manifest import Manifest, write_manifest
from knowgraph.shared.security import validate_path


async def run_index(
    input_path: str,
    output_path: str,
    verbose: bool = False,
    provider: IntelligenceProvider | None = None,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    access_token: str | None = None,
) -> None:
    """Execute indexing process (AI-Driven).

    Supports markdown files, directories, Git repositories, and code directories.
    """
    start_time = time.time()

    # Detect source type
    source_type = detect_source_type(input_path)

    if verbose:
        click.echo(f"Detected source type: {source_type}")
        click.echo(f"Indexing {input_path} (AI Mode)...")

    # Step 1: Process source based on type
    temp_files_to_cleanup = []

    try:
        if source_type == "repository" or (
            source_type == "directory" and not Path(input_path).exists()
        ):
            # It's a repository URL or remote directory - use gitingest
            if verbose:
                click.echo("Processing repository with gitingest...")

            markdown_content, temp_path, _ = await ingest_source(
                input_path=input_path,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                access_token=access_token,
            )
            temp_files_to_cleanup.append(temp_path)

            # Treat the generated markdown as a single file
            files_to_process = [temp_path]

        else:
            # Local path - validate and collect files
            input_path_obj = validate_path(input_path, must_exist=True, must_be_file=False)

            # Step 1: Collect files
            files_to_process = []
            if input_path_obj.is_dir():
                # Glob all .md files
                files_to_process = sorted(
                    [Path(p) for p in glob.glob(str(input_path_obj / "**/*.md"), recursive=True)]
                )
            else:
                files_to_process = [input_path_obj]

            if not files_to_process:
                if verbose:
                    click.echo("No markdown files found to index.")
                return

        graph_store_path = validate_path(output_path, must_exist=False, must_be_file=False)

        all_chunks = []
        file_hashes = {}

        # Step 2: Load, normalize, and chunk each file
        for file_path in files_to_process:
            with open(file_path, encoding="utf-8") as file:
                markdown_content = file.read()

            normalized_content = normalize_markdown_content(markdown_content)
            file_hash = hash_content(normalized_content)
            file_hashes[str(file_path)] = file_hash

            if verbose:
                click.echo(f"✓ Loaded {file_path.name} ({len(normalized_content)} chars)")

            # Chunk markdown
            chunks = chunk_markdown(normalized_content, str(file_path))
            all_chunks.extend(chunks)

        if verbose:
            click.echo(f"✓ Created {len(all_chunks)} chunks from {len(files_to_process)} files")

        # Step 3: Build Nodes and Edges (AI Only)
        if not provider:
            # Default to OpenAI if not provided (e.g. CLI usage)
            provider = OpenAIProvider()

        builder = SmartGraphBuilder(provider)
        nodes, all_edges = await builder.build(
            all_chunks, str(input_path), "", str(graph_store_path)
        )

        # We still need sparse embeddings for retrieval index
        sparse_embedder = SparseEmbedder()
        sparse_embeddings = {node.id: sparse_embedder.embed_text(node.content) for node in nodes}

        if verbose:
            click.echo(f"✓ Created {len(nodes)} nodes")
            click.echo(f"✓ Created {len(all_edges)} edges")

        # Step 4: Build Sparse Index
        if verbose:
            click.echo("Building Sparse Index...")

        index = SparseIndex()
        for node in nodes:
            if node.id in sparse_embeddings:
                index.add(node.id, sparse_embeddings[node.id])
        index.build()
        index.save(graph_store_path / "index")

        # Step 5: Write to storage
        for node in nodes:
            write_node_json(node, graph_store_path)

        write_all_edges(all_edges, graph_store_path)

        # Step 6: Create Manifest
        semantic_count = len(all_edges)

        manifest = Manifest.create_new(
            edges_filename=EDGES_FILENAME,
            sparse_index_filename="index",
        )
        manifest.node_count = len(nodes)
        manifest.edge_count = len(all_edges)
        manifest.file_hashes = file_hashes
        manifest.semantic_edge_count = semantic_count
        manifest.finalized = True

        write_manifest(manifest, graph_store_path)

        if verbose:
            click.echo(f"✓ Saved manifest (v{manifest.version})")

        elapsed = time.time() - start_time
        if verbose:
            click.echo(f"\nGraph stored in: {graph_store_path}")
            click.echo(f"Indexing completed in {elapsed:.1f}s")

    except RepositoryIngestorError as e:
        click.echo(f"Repository ingestion error: {e}", err=True)
        raise

    finally:
        # Cleanup temporary files
        for temp_file in temp_files_to_cleanup:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors


@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    default=DEFAULT_GRAPH_STORE_PATH,
    help="Output directory for graph storage",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def index_command(input_path: str, output: str, verbose: bool) -> None:
    """Index markdown files into knowledge graph.

    INPUT_PATH: Path to markdown file or directory
    """
    try:
        asyncio.run(run_index(input_path, output, verbose))
    except Exception as error:
        click.echo(f"Error: {error}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    index_command()
