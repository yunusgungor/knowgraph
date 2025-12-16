"""CLI command for incremental graph updates."""

import asyncio
import sys
import time
from dataclasses import replace
from pathlib import Path

import click

from knowgraph.application.evolution.incremental_update import (
    apply_incremental_update,
    detect_delta,
)
from knowgraph.application.indexing.graph_builder import normalize_markdown_content
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider
from knowgraph.infrastructure.parsing.hasher import hash_content
from knowgraph.infrastructure.storage.manifest import (
    read_manifest as load_manifest,
)
from knowgraph.shared.security import validate_path


async def run_update(
    input_path: str,
    graph_store: str,
    gc: bool = False,
    verbose: bool = False,
    provider: IntelligenceProvider | None = None,
) -> None:
    """Incrementally update graph with changes (AI-Driven)."""
    start_time = time.time()

    # Validate and resolve paths
    # Allow directory or file input for update
    input_path_obj = validate_path(input_path, must_exist=True, must_be_file=False)
    graph_store_path = Path(graph_store)

    # Load manifest
    manifest = load_manifest(graph_store_path)
    if not manifest:
        click.echo(
            f"Error: No existing graph found at {graph_store_path}. "
            "Run 'knowgraph index' first.",
            err=True,
        )
        sys.exit(2)

    files_to_process = []
    if input_path_obj.is_dir():
        import glob

        files_to_process = sorted(
            [Path(p) for p in glob.glob(str(input_path_obj / "**/*.md"), recursive=True)]
        )
    else:
        files_to_process = [input_path_obj]

    if not files_to_process:
        if verbose:
            click.echo("No files to update.")
        return

    if verbose:
        click.echo(f"Updating graph from {input_path_obj} ({len(files_to_process)} files)...")

    # Initialize stats
    total_added = 0
    total_modified = 0
    total_deleted = 0

    # Smart/AI Mode (Default)
    if not provider:
        provider = OpenAIProvider()

    for input_file in files_to_process:
        try:
            # Load new content
            with open(input_file, encoding="utf-8") as file:
                new_content = file.read()

            normalized_content = normalize_markdown_content(new_content)
            file_hash = hash_content(normalized_content)

            # Detect changes
            delta = detect_delta(manifest, new_content, str(input_file), graph_store_path)

            if not delta.added_nodes and not delta.deleted_node_ids and not delta.modified_nodes:
                continue

            if verbose:
                click.echo(
                    f"✓ {input_file.name}: "
                    f"{len(delta.added_nodes)} added, "
                    f"{len(delta.deleted_node_ids)} deleted"
                )

            # Process added nodes with AI
            if delta.added_nodes:
                tasks = []
                for node in delta.added_nodes:
                    tasks.append(provider.extract_entities(node.content))

                results = await asyncio.gather(*tasks)

                enriched_nodes = []
                for node, entities in zip(delta.added_nodes, results):
                    new_node = replace(node, metadata={"entities": [e._asdict() for e in entities]})
                    enriched_nodes.append(new_node)

                delta.added_nodes = enriched_nodes
                # For now assume modified = added logic
                delta.modified_nodes = enriched_nodes

            # Apply update with Smart support
            manifest = apply_incremental_update(
                delta, manifest, file_hash, str(input_file), graph_store_path, gc
            )

            total_added += len(delta.added_nodes)
            total_deleted += len(delta.deleted_node_ids)
            # track total_modified if needed

        except Exception as e:
            click.echo(f"Error updating file {input_file}: {e}", err=True)
            if verbose:
                import traceback

                traceback.print_exc()
            continue

    elapsed = time.time() - start_time
    click.echo(f"\nUpdate completed in {elapsed:.1f}s")
    click.echo(f"Total: {total_added} added, {total_deleted} deleted nodes")


@click.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "--graph-store",
    "-g",
    default=DEFAULT_GRAPH_STORE_PATH,
    help="Graph storage directory",
)
@click.option("--gc", is_flag=True, help="Garbage collect deleted nodes")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def update_command(input_path: str, graph_store: str, gc: bool, verbose: bool) -> None:
    """Incrementally update graph with changes.

    INPUT_PATH: Path to updated markdown file
    """
    try:
        asyncio.run(run_update(input_path, graph_store, gc, verbose))
    except Exception as error:
        click.echo(f"Error: {error}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    update_command()
