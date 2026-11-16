from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class NiaPackageSearchReadFileParams(BaseModel):
    """Parameters for nia_package_search_read_file"""
    registry: Literal["crates_io", "golang_proxy", "npm", "py_pi", "ruby_gems"]
    """Registry"""
    package_name: str
    """Package name (Go: org/repo)"""
    filename_sha256: str
    """File SHA256"""
    start_line: int
    """Start line (1-based)"""
    end_line: int
    """End line (max 200)"""
    version: Optional[Dict[str, Any]] = None
    """Version"""

async def nia_package_search_read_file(params: NiaPackageSearchReadFileParams) -> Dict[str, Any]:
    """
    Read lines from package source file.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__nia_package_search_read_file", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
