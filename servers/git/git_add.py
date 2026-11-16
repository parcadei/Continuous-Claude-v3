from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GitAddParams(BaseModel):
    """Parameters for git_add"""
    repo_path: str
    files: List[str]

async def git_add(params: GitAddParams) -> Dict[str, Any]:
    """
    Adds file contents to the staging area

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("git__git_add", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "git")

    return normalized
