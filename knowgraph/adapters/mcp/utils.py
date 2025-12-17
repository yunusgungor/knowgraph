import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.server import Server

from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.intelligence.mcp_sampling_provider import MCPSamplingProvider
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider


def resolve_graph_path(path_arg: str | None, root_dir: Path) -> Path:
    """Resolve the graph path relative to the root directory if it's not absolute.
    Defaults to resolving relative to the provided root_dir.

    Args:
    ----
        path_arg: Graph path argument (can be relative, absolute, or None)
        root_dir: Root directory for resolving relative paths

    Returns:
    -------
        Resolved absolute path
    """
    # Handle None - use default
    if path_arg is None:
        from knowgraph.config import DEFAULT_GRAPH_STORE_PATH

        path_arg = DEFAULT_GRAPH_STORE_PATH

    # Ensure root_dir is not root directory
    if root_dir == root_dir.parent:  # root_dir is /
        root_dir = Path.home()

    path_obj = Path(path_arg)
    if not path_obj.is_absolute():
        return (root_dir / path_obj).resolve()
    return path_obj.resolve()


def get_llm_provider(server: Server) -> IntelligenceProvider:
    """Factory function to create an LLM provider based on environment variables.
    Prioritizes OpenAI/OpenRouter via env vars, falls back to MCP Sampling.
    """
    load_dotenv()

    api_key = os.getenv("KNOWGRAPH_API_KEY")
    api_base = os.getenv("KNOWGRAPH_API_BASE")
    llm_model = os.getenv("KNOWGRAPH_LLM_MODEL", "amazon/nova-2-lite-v1:free")

    if api_key:
        return OpenAIProvider(api_key=api_key, api_base=api_base, model=llm_model)
    else:
        provider = MCPSamplingProvider(server=server)
        # Hack: Inject request context if available (mcp >= 1.0)
        if hasattr(server, "request_context"):
            provider.request_context = server.request_context
        return provider
