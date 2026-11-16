from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ContextParams(BaseModel):
    """Parameters for context"""
    action: Literal["save", "list", "retrieve", "search", "semantic-search", "keyword-search", "update", "delete"]
    """Action"""
    title: Optional[Dict[str, Any]] = None
    """Title"""
    summary: Optional[Dict[str, Any]] = None
    """Summary (10-1000 chars)"""
    content: Optional[Dict[str, Any]] = None
    """Content (min 50 chars)"""
    agent_source: Optional[Dict[str, Any]] = None
    """Agent e.g. 'cursor'"""
    tags: Optional[Dict[str, Any]] = None
    """Tags"""
    metadata: Optional[Dict[str, Any]] = None
    """Extra metadata"""
    nia_references: Optional[Dict[str, Any]] = None
    """NIA resources used"""
    edited_files: Optional[Dict[str, Any]] = None
    """Modified files"""
    workspace_override: Optional[Dict[str, Any]] = None
    """Override workspace"""
    limit: Optional[int] = None
    """Results limit"""
    offset: Optional[int] = None
    """Pagination offset"""
    scope: Optional[Dict[str, Any]] = None
    """Filter scope"""
    workspace: Optional[Dict[str, Any]] = None
    """Workspace filter"""
    directory: Optional[Dict[str, Any]] = None
    """Directory filter"""
    file_overlap: Optional[Dict[str, Any]] = None
    """Overlapping files"""
    context_id: Optional[Dict[str, Any]] = None
    """Context ID"""
    query: Optional[Dict[str, Any]] = None
    """Search query"""

async def context(params: ContextParams) -> Dict[str, Any]:
    """
    Cross-agent context sharing (save/list/retrieve/search/update/delete).

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__context", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
