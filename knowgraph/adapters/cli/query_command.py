"""CLI command for querying knowledge graph."""

import sys

import click

from knowgraph.application.querying.impact_analyzer import analyze_impact_by_path
from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.config import (
    DEFAULT_GRAPH_STORE_PATH,
    MAX_HOPS,
    MAX_TOKENS,
    MS_TO_SECONDS,
    TOP_K,
)
from knowgraph.domain.algorithms.graph_validator import validate_graph_consistency
from knowgraph.infrastructure.storage.filesystem import (
    list_all_nodes,
    read_all_edges,
    read_node_json,
)


@click.command()
@click.argument("query_text")
@click.option(
    "--graph-store",
    "-g",
    default=DEFAULT_GRAPH_STORE_PATH,
    help="Path to graph storage directory",
)
@click.option("--top-k", default=TOP_K, help="Number of seed nodes")
@click.option("--max-hops", default=MAX_HOPS, help="Graph traversal depth")
@click.option("--max-tokens", default=MAX_TOKENS, help="Maximum context tokens")
@click.option("--explain", "-e", is_flag=True, help="Show explainability report")
@click.option("--expand-query", is_flag=True, help="Expand query with AI-generated synonyms")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option(
    "--mode",
    default="query",
    type=click.Choice(["query", "impact"]),
    help="Mode: query (default) or impact analysis",
)
def query_command(
    query_text: str,
    graph_store: str,
    top_k: int,
    max_hops: int,
    max_tokens: int,
    explain: bool,
    expand_query: bool,
    verbose: bool,
    mode: str,
) -> None:
    """Query knowledge graph with natural language.

    QUERY_TEXT: Natural language query string
    """
    from knowgraph.shared.security import (
        sanitize_query_input,
        validate_graph_store_path,
        validate_path,
    )

    try:
        # Validate and sanitize inputs
        query_text = sanitize_query_input(query_text, max_length=10000)
        graph_store_path = validate_path(graph_store, must_exist=True, must_be_file=False)
        validate_graph_store_path(graph_store_path)

        if verbose:
            click.echo(f"Loading graph from {graph_store_path}...")

        # Pre-flight validation (FR-058)
        validation_result = validate_graph_consistency(graph_store_path)
        if not validation_result.valid:
            click.echo(f"Error: {validation_result.get_error_summary()}", err=True)
            sys.exit(1)

        if verbose:
            click.echo("✓ Graph validation passed")

        # Mode: Impact Analysis
        if mode == "impact":
            # Load all nodes and edges
            all_node_ids = list_all_nodes(graph_store_path)
            all_nodes = []
            for node_id in all_node_ids:
                node = read_node_json(node_id, graph_store_path)
                if node:
                    all_nodes.append(node)

            all_edges = read_all_edges(graph_store_path)

            if verbose:
                click.echo(f"Analyzing impact for: {query_text}")

            # Perform impact analysis
            results = analyze_impact_by_path(query_text, all_nodes, all_edges, max_depth=max_hops)

            if not results:
                click.echo(f"No nodes found matching pattern: {query_text}")
                return

            # Output impact analysis
            click.echo(f"\nImpact Analysis for: {query_text}")
            click.echo("─" * 60)

            for result in results:
                click.echo(f"\n{result.get_summary()}")

                if result.dependent_nodes:
                    click.echo("Dependent Files:")
                    seen_paths = set()
                    for node in result.dependent_nodes[:20]:  # Limit to 20
                        if node.path not in seen_paths:
                            click.echo(f"  - {node.path}")
                            seen_paths.add(node.path)

                    if len(result.dependent_nodes) > 20:
                        click.echo(f"  ... and {len(result.dependent_nodes) - 20} more")
                else:
                    click.echo("No dependencies found (isolated node)")

            click.echo("\n" + "─" * 60)
            return

        # Mode: Standard Query
        # Initialize engine
        engine = QueryEngine(graph_store_path)

        # Query expansion if requested
        if expand_query:
            try:
                import os

                from knowgraph.application.querying.query_expansion import QueryExpander

                if verbose:
                    click.echo("Expanding query with AI...")

                if os.getenv("KNOWGRAPH_API_KEY"):
                    llm_model = os.getenv("KNOWGRAPH_LLM_MODEL", "amazon/nova-2-lite-v1:free")
                    expander = QueryExpander(provider="openai", model=llm_model)
                    expansion_terms = expander.expand_query(query_text)
                    if expansion_terms:
                        original_query = query_text
                        query_text = f"{query_text} {' '.join(expansion_terms)}"
                        if verbose:
                            click.echo(f"Expanded: {original_query} → {query_text}")
            except Exception as e:
                if verbose:
                    click.echo(f"Query expansion failed: {e}")

        if verbose:
            click.echo(f"Querying: {query_text}")

        # Execute query
        query_result = engine.query(
            query_text, top_k, max_hops, max_tokens, with_explanation=explain
        )

        # Output result
        click.echo(f"\nQuery: {query_result.query}")
        click.echo("─" * 60)
        click.echo(f"\n{query_result.answer}\n")
        click.echo("─" * 60)

        # Performance metrics
        click.echo(
            f"Retrieved {query_result.active_subgraph_size} nodes in "
            f"{query_result.sparse_search_time + query_result.graph_expansion_time:.0f}ms"
        )

        if explain:
            click.echo("\n## Performance Breakdown")
            click.echo(f"- Sparse search: {query_result.sparse_search_time * MS_TO_SECONDS:.0f}ms")
            click.echo(
                f"- Graph expansion: {query_result.graph_expansion_time * MS_TO_SECONDS:.0f}ms"
            )
            click.echo(
                f"- Centrality calculation: {query_result.centrality_time * MS_TO_SECONDS:.0f}ms"
            )
            click.echo(f"- Total time: {query_result.execution_time:.1f}s")

            click.echo("\n## Seed Nodes")
            click.echo(f"Top-{len(query_result.seed_nodes)} nodes from sparse search:")
            for i, node_id in enumerate(query_result.seed_nodes[:5], 1):
                click.echo(f"  {i}. {node_id}")

            # Display explanation
            if query_result.explanation:
                exp = query_result.explanation
                click.echo("\n## Reasoning Paths")
                for i, path in enumerate(exp.reasoning_paths[:3], 1):
                    click.echo(f"  {i}. {path.narrative} (score: {path.total_score:.2f})")

                click.echo("\n## Node Contributions (top 5)")
                sorted_contribs = sorted(
                    exp.node_contributions,
                    key=lambda c: c.importance_score,
                    reverse=True,
                )
                for contrib in sorted_contribs[:5]:
                    marker = "🌱" if contrib.is_seed else "  "
                    click.echo(
                        f"  {marker} Node {str(contrib.node_id)[:8]}... "
                        f"(importance: {contrib.importance_score:.2f})"
                    )

                if exp.citation_validation:
                    click.echo("\n## Citations")
                    click.echo(f"Validated {len(exp.citation_validation)} citations from context")

    except Exception as error:
        click.echo(f"Error: {error}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    query_command()
