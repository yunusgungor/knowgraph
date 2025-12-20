"""CLI command for auto-discovering and indexing conversations from AI editors."""

import asyncio

import click

from knowgraph.adapters.cli.index_command import run_index
from knowgraph.infrastructure.detection.conversation_discovery import (
    discover_all_conversations,
    get_conversation_count_by_editor,
)


@click.command()
@click.option(
    "--output",
    "-o",
    default="./graphstore",
    help="Output directory for graph storage",
)
@click.option(
    "--editor",
    "-e",
    type=click.Choice(["all", "antigravity", "cursor", "github_copilot"], case_sensitive=False),
    default="all",
    help="Which editor's conversations to index",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be indexed without actually indexing"
)
def discover_and_index_conversations(
    output: str, editor: str, verbose: bool, dry_run: bool
) -> None:
    """Auto-discover and index conversations from AI code editors.

    Automatically finds conversation histories from:
    - Antigravity (Gemini)
    - Cursor
    - GitHub Copilot (VSCode)

    No manual export required!
    """
    click.echo("🔍 Auto-discovering conversations from AI editors...\n")

    # Discover all conversations
    discovered = discover_all_conversations()

    if not discovered:
        click.echo("❌ No conversations found from any editor.")
        click.echo("\nMake sure you have one of these editors installed:")
        click.echo("  - Antigravity (Gemini)")
        click.echo("  - Cursor")
        click.echo("  - VSCode with GitHub Copilot")
        return

    # Filter by editor if specified
    if editor != "all":
        discovered = {k: v for k, v in discovered.items() if k == editor}

    # Show summary
    total_files = sum(len(files) for files in discovered.values())
    click.echo(f"✅ Found {total_files} conversations across {len(discovered)} editors:\n")

    for editor_name, files in discovered.items():
        click.echo(f"  📝 {editor_name.upper()}: {len(files)} conversations")

    if dry_run:
        click.echo("\n🔍 Dry run - showing files that would be indexed:\n")
        for editor_name, files in discovered.items():
            click.echo(f"\n{editor_name.upper()}:")
            for file_path in files[:5]:  # Show first 5
                click.echo(f"  - {file_path}")
            if len(files) > 5:
                click.echo(f"  ... and {len(files) - 5} more")
        return

    # Index all discovered conversations
    click.echo(f"\n📥 Indexing conversations to {output}...\n")

    indexed_count = 0
    failed_count = 0

    for editor_name, files in discovered.items():
        click.echo(f"\n📂 Indexing {editor_name} conversations...")

        for file_path in files:
            try:
                if verbose:
                    click.echo(f"  Indexing: {file_path.name}")

                asyncio.run(
                    run_index(
                        input_path=str(file_path),
                        output_path=output,
                        verbose=False,  # Suppress individual file verbosity
                    )
                )
                indexed_count += 1

            except Exception as e:
                failed_count += 1
                if verbose:
                    click.echo(f"  ❌ Failed: {e}")

    click.echo("\n✅ Indexing complete!")
    click.echo(f"  Indexed: {indexed_count} conversations")
    if failed_count > 0:
        click.echo(f"  Failed: {failed_count} conversations")
    click.echo(f"\n📊 Graph stored in: {output}")


@click.command()
def list_conversations() -> None:
    """List all discovered conversations from AI editors."""
    click.echo("🔍 Discovering conversations...\n")

    counts = get_conversation_count_by_editor()

    if not counts:
        click.echo("❌ No conversations found.")
        return

    total = sum(counts.values())
    click.echo(f"✅ Found {total} conversations:\n")

    for editor, count in counts.items():
        click.echo(f"  📝 {editor.upper()}: {count} conversations")


if __name__ == "__main__":
    discover_and_index_conversations()
