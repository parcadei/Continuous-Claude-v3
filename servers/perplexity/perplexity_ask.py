from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class PerplexityAskParams(BaseModel):
    """Parameters for perplexity_ask"""
    messages: List[Dict[str, Any]]
    """Array of conversation messages"""

async def perplexity_ask(params: PerplexityAskParams) -> Dict[str, Any]:
    """
    Engages in a conversation using the Sonar API. Accepts an array of messages (each with a role and content) and returns a chat completion response from the Perplexity model.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("perplexity__perplexity_ask", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "perplexity")

    return normalized
