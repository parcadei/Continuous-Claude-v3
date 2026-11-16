from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class PerplexitySearchParams(BaseModel):
    """Parameters for perplexity_search"""
    query: str
    """Search query string"""
    max_results: Optional[float] = None
    """Maximum number of results to return (1-20, default: 10)"""
    max_tokens_per_page: Optional[float] = None
    """Maximum tokens to extract per webpage (default: 1024)"""
    country: Optional[str] = None
    """ISO 3166-1 alpha-2 country code for regional results (e.g., 'US', 'GB')"""

async def perplexity_search(params: PerplexitySearchParams) -> Dict[str, Any]:
    """
    Performs web search using the Perplexity Search API. Returns ranked search results with titles, URLs, snippets, and metadata. Perfect for finding up-to-date facts, news, or specific information.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("perplexity__perplexity_search", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "perplexity")

    return normalized
