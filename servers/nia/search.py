from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class SearchParams(BaseModel):
    """Parameters for search"""
    query: str
    """Natural language query"""
    repositories: Optional[Dict[str, Any]] = None
    """owner/repo list (auto-detected if omitted)"""
    data_sources: Optional[Dict[str, Any]] = None
    """Documentation/research paper sources (auto-detected if omitted). Accepts flexible identifiers:
- UUID (data source ID)
- display_name
- URL (docs site URL)
- Research papers: paper data-source UUID OR arXiv abs/pdf URL
You may pass a single string, a list of strings, or objects like {"source_id":"..."} (legacy) or {"identifier":"..."} (flexible)."""
    search_mode: Optional[Literal["unified", "repositories", "sources"]] = None
    """Search scope"""
    include_sources: Optional[bool] = None
    """Include snippets"""

async def search(params: SearchParams) -> Dict[str, Any]:
    """
    Search repos/docs. Omit sources for universal hybrid search.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__search", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
