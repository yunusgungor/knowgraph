import os
from typing import Any

from dotenv import load_dotenv

from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.intelligence.mcp_sampling_provider import MCPSamplingProvider
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider


def get_llm_provider(_server: Any = None) -> IntelligenceProvider:
    """Factory function to create an LLM provider based on environment variables.
    Prioritizes OpenAI/OpenRouter via env vars, falls back to MCP Sampling.

    Args:
        _server: Ignored. Kept for call-site compatibility; MCP Sampling reads
            the live session from ``mcp.request_context()`` at call time.
    """
    load_dotenv()

    api_key = os.getenv("KNOWGRAPH_API_KEY")
    api_base = os.getenv("KNOWGRAPH_API_BASE")
    llm_model = os.getenv("KNOWGRAPH_LLM_MODEL", "amazon/nova-2-lite-v1:free")

    if api_key:
        return OpenAIProvider(api_key=api_key, api_base=api_base, model=llm_model)
    else:
        return MCPSamplingProvider()
