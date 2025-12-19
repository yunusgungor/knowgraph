"""CLI command for auto-tagging bookmarks."""

import click
from pathlib import Path

from knowgraph.config import DEFAULT_GRAPH_STORE_PATH


@click.command()
@click.option(
    "--graphstore",
    "-g",
    default=str(DEFAULT_GRAPH_STORE_PATH),
    help="Path to graph storage directory",
)
@click.option(
    "--min-confidence",
    "-c",
    default=0.3,
    type=float,
    help="Minimum confidence threshold for auto-suggestions (0.0-1.0)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def auto_tag_bookmarks(graphstore: str, min_confidence: float, verbose: bool) -> None:
    """Apply AI auto-tagging to existing bookmarks.

    Scans all tagged_snippet nodes and adds AI-generated tag suggestions
    with confidence scores and topic categorization.
    """
    import asyncio

    async def run():
        try:
            from knowgraph.application.indexing.post_index_hooks import auto_tag_bookmarks

            if verbose:
                click.echo(f"🏷️  Auto-tagging bookmarks in {graphstore}...")
                click.echo(f"Minimum confidence: {min_confidence:.0%}\n")

            stats = await auto_tag_bookmarks(Path(graphstore), min_confidence=min_confidence)

            # Display results
            click.echo("=" * 60)
            click.echo("AUTO-TAGGING RESULTS")
            click.echo("=" * 60)
            click.echo(f"\nBookmarks found: {stats['bookmarks_found']}")
            click.echo(f"Bookmarks enhanced: {stats['bookmarks_enhanced']}")
            click.echo(f"Suggestions added: {stats['suggestions_added']}")

            if stats["errors"] > 0:
                click.echo(f"\n⚠️  Errors: {stats['errors']}")

            if stats["bookmarks_enhanced"] > 0:
                avg_suggestions = stats["suggestions_added"] / stats["bookmarks_enhanced"]
                click.echo(f"\n📊 Avg suggestions per bookmark: {avg_suggestions:.1f}")

            click.echo("\n✅ Auto-tagging complete!")

        except Exception as e:
            click.echo(f"❌ Error: {e}", err=True)
            if verbose:
                import traceback

                traceback.print_exc()
            raise click.Abort()

    asyncio.run(run())


if __name__ == "__main__":
    auto_tag_bookmarks()
