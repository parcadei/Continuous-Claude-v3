from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class NiaPackageSearchGrepParams(BaseModel):
    """Parameters for nia_package_search_grep"""
    registry: Literal["crates_io", "golang_proxy", "npm", "py_pi", "ruby_gems"]
    """Registry"""
    package_name: str
    """Package name (Go: org/repo)"""
    pattern: str
    """Regex pattern"""
    version: Optional[Dict[str, Any]] = None
    """Version"""
    language: Optional[Dict[str, Any]] = None
    """Language filter"""
    filename_sha256: Optional[Dict[str, Any]] = None
    """File SHA256"""
    a: Optional[Dict[str, Any]] = None
    """Lines after"""
    b: Optional[Dict[str, Any]] = None
    """Lines before"""
    c: Optional[Dict[str, Any]] = None
    """Context lines"""
    head_limit: Optional[Dict[str, Any]] = None
    """Max results"""
    output_mode: Optional[Literal["content", "files_with_matches", "count"]] = None
    """Output mode"""

async def nia_package_search_grep(params: NiaPackageSearchGrepParams) -> Dict[str, Any]:
    """
    Regex search in public package source.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__nia_package_search_grep", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
