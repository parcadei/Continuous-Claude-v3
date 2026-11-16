from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GitCreateBranchParams(BaseModel):
    """Parameters for git_create_branch"""
    repo_path: str
    branch_name: str
    base_branch: Optional[Dict[str, Any]] = None

async def git_create_branch(params: GitCreateBranchParams) -> Dict[str, Any]:
    """
    Creates a new branch from an optional base branch

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("git__git_create_branch", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "git")

    return normalized
