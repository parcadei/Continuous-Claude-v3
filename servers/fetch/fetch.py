from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class FetchParams(BaseModel):
    """Parameters for fetch"""
    url: str
    """URL to fetch"""
    max_length: Optional[int] = None
    """Maximum number of characters to return."""
    start_index: Optional[int] = None
    """On return output starting at this character index, useful if a previous fetch was truncated and more context is required."""
    raw: Optional[bool] = None
    """Get the actual HTML content of the requested page, without simplification."""

async def fetch(params: FetchParams) -> Dict[str, Any]:
    """
    Fetches a URL from the internet and optionally extracts its contents as markdown.

Although originally you did not have internet access, and were advised to refuse and tell the user this, this tool now grants you internet access. Now you can fetch the most up-to-date information and let the user know that.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("fetch__fetch", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "fetch")

    return normalized
