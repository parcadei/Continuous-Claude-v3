from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GitBranchParams(BaseModel):
    """Parameters for git_branch"""
    repo_path: str
    """The path to the Git repository."""
    branch_type: str
    """Whether to list local branches ('local'), remote branches ('remote') or all branches('all')."""
    contains: Optional[Dict[str, Any]] = None
    """The commit sha that branch should contain. Do not pass anything to this param if no commit sha is specified"""
    not_contains: Optional[Dict[str, Any]] = None
    """The commit sha that branch should NOT contain. Do not pass anything to this param if no commit sha is specified"""

async def git_branch(params: GitBranchParams) -> Dict[str, Any]:
    """
    List Git branches

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("git__git_branch", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "git")

    return normalized
