from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GetGithubFileTreeParams(BaseModel):
    """Parameters for get_github_file_tree"""
    repository: str
    """owner/repo"""
    branch: Optional[Dict[str, Any]] = None
    """Branch"""
    include_paths: Optional[Dict[str, Any]] = None
    """Path filters"""
    exclude_paths: Optional[Dict[str, Any]] = None
    """Path exclusions"""
    file_extensions: Optional[Dict[str, Any]] = None
    """Extension filters"""
    exclude_extensions: Optional[Dict[str, Any]] = None
    """Extension exclusions"""
    show_full_paths: Optional[bool] = None
    """Full paths vs tree"""

async def get_github_file_tree(params: GetGithubFileTreeParams) -> Dict[str, Any]:
    """
    Get repo file tree from GitHub API (no indexing needed).

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("nia__get_github_file_tree", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "nia")

    return normalized
