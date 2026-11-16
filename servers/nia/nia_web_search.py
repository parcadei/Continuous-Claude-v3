from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class NiaWebSearchParams(BaseModel):
    """Parameters for nia_web_search"""
    query: str
    """Search query"""
    num_results: Optional[int] = None
    """Max 10"""
    category: Optional[Dict[str, Any]] = None
    """Category filter"""
    days_back: Optional[Dict[str, Any]] = None
    """Recency filter"""
    find_similar_to: Optional[Dict[str, Any]] = None
    """URL for similar content"""

async def nia_web_search(params: NiaWebSearchParams) -> Dict[str, Any]:
    """
    Web search for repos/docs/tech content.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__nia_web_search", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
