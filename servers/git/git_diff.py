from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GitDiffParams(BaseModel):
    """Parameters for git_diff"""
    repo_path: str
    target: str
    context_lines: Optional[int] = None

async def git_diff(params: GitDiffParams) -> Dict[str, Any]:
    """
    Shows differences between branches or commits

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("git__git_diff", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "git")

    return normalized
