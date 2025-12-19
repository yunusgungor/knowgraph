"""CLI command for incremental graph updates.

Note: This now delegates to run_index() for better performance.
"""

import asyncio
import sys
from pathlib import Path

import click

from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.shared.security import validate_path


async def run_update(
    input_path: str,
    graph_store: str,
    gc: bool = False,
    verbose: bool = False,
    provider: IntelligenceProvider | None = None,
    exclude_patterns: list[str] | None = None,
) -> None:
    """Incrementally update graph with changes (AI-Driven).

    Note: This now uses run_index() which has efficient manifest-level
    hash checking and only processes changed files.
    """
    # Import run_index here to avoid circular imports
    from knowgraph.adapters.cli.index_command import run_index

    # Validate path first
    input_path_obj = validate_path(input_path, must_exist=True, must_be_file=False)
    graph_store_path = Path(graph_store)

    # Check if graph exists
    manifest_path = graph_store_path / "metadata" / "manifest.json"
    if not manifest_path.exists():
        click.echo(
            f"Error: No existing graph found at {graph_store_path}. "
            "Run 'knowgraph index' first.",
            err=True,
        )
        sys.exit(2)

    if verbose:
        click.echo(f"Updating graph from {input_path}...")
        click.echo("Note: Using efficient manifest-level hash checking.")

    # Use run_index which has efficient hash checking
    # It will automatically skip unchanged files at manifest level
    await run_index(
        input_path=str(input_path_obj),
        output_path=graph_store,
        verbose=verbose,
        provider=provider,
        exclude_patterns=exclude_patterns or [],
    )

    if verbose:
        click.echo("✓ Update completed using manifest-level incremental indexing.")


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
