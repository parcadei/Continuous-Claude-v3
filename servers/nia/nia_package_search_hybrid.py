from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class NiaPackageSearchHybridParams(BaseModel):
    """Parameters for nia_package_search_hybrid"""
    registry: Literal["crates_io", "golang_proxy", "npm", "py_pi", "ruby_gems"]
    """Registry"""
    package_name: str
    """Package name (Go: org/repo)"""
    semantic_queries: List[str]
    """1-5 questions"""
    version: Optional[Dict[str, Any]] = None
    """Version"""
    filename_sha256: Optional[Dict[str, Any]] = None
    """File SHA256"""
    pattern: Optional[Dict[str, Any]] = None
    """Regex filter"""
    language: Optional[Dict[str, Any]] = None
    """Language filter"""

async def nia_package_search_hybrid(params: NiaPackageSearchHybridParams) -> Dict[str, Any]:
    """
    Semantic search in package source with optional regex.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__nia_package_search_hybrid", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
