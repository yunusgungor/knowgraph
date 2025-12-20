"""Main CLI entry point for KnowGraph commands."""

import warnings

import click
from dotenv import load_dotenv

# Suppress invalid escape sequence warnings from dependencies
warnings.filterwarnings("ignore", category=SyntaxWarning, message="invalid escape sequence")

from knowgraph import __version__  # noqa: E402
from knowgraph.adapters.cli.discover_conversations_command import (  # noqa: E402  # noqa: E402
    discover_and_index_conversations,
    list_conversations,
)
from knowgraph.adapters.cli.index_command import index_command  # noqa: E402
from knowgraph.adapters.cli.query_command import query_command  # noqa: E402
from knowgraph.adapters.cli.update_command import update_command  # noqa: E402
from knowgraph.adapters.cli.version_command import version_commands  # noqa: E402

# Load environment variables
load_dotenv()


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """KnowGraph - Knowledge Graph-Powered RAG System.

    A production-grade library for converting Git repositories into queryable
    knowledge graphs with explainable reasoning paths.
    """


# Register commands
cli.add_command(index_command, name="index")
cli.add_command(query_command, name="query")
cli.add_command(update_command, name="update")
cli.add_command(discover_and_index_conversations, name="discover-conversations")
cli.add_command(list_conversations, name="list-conversations")

cli.add_command(version_commands, name="version")


@cli.command(name="serve")
def serve_command() -> None:
    """Start the KnowGraph MCP server."""
    import asyncio

    from knowgraph.adapters.mcp.server import main

    asyncio.run(main())


if __name__ == "__main__":
    cli()
