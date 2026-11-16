from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ManageResourceParams(BaseModel):
    """Parameters for manage_resource"""
    action: Literal["list", "status", "rename", "delete"]
    """Action"""
    resource_type: Optional[Dict[str, Any]] = None
    """Required for status/rename/delete"""
    identifier: Optional[Dict[str, Any]] = None
    """owner/repo or UUID/name/URL"""
    new_name: Optional[Dict[str, Any]] = None
    """For rename (1-100 chars)"""
    query: Optional[Dict[str, Any]] = None
    """Optional text filter (matches repo/display_name/url/title/id). Use this to avoid listing everything."""
    limit: Optional[int] = None
    """Max items to return (per section)."""
    offset: Optional[int] = None
    """Pagination offset (per section)."""
    view: Optional[Literal["auto", "summary", "compact", "detailed"]] = None
    """How much to show. 'auto' uses summary when output would be large."""
    show_all: Optional[bool] = None
    """Ignore limit/offset and show all matches (can be large)."""

async def manage_resource(params: ManageResourceParams) -> Dict[str, Any]:
    """
    Manage indexed resources (list/status/rename/delete).

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__manage_resource", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
