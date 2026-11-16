from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class PerplexityResearchParams(BaseModel):
    """Parameters for perplexity_research"""
    messages: List[Dict[str, Any]]
    """Array of conversation messages"""
    strip_thinking: Optional[bool] = None
    """If true, removes <think>...</think> tags and their content from the response to save context tokens. Default is false."""

async def perplexity_research(params: PerplexityResearchParams) -> Dict[str, Any]:
    """
    Performs deep research using the Perplexity API. Accepts an array of messages (each with a role and content) and returns a comprehensive research response with citations.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("perplexity__perplexity_research", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "perplexity")

    return normalized
