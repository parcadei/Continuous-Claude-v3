from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GitResetParams(BaseModel):
    """Parameters for git_reset"""
    repo_path: str

async def git_reset(params: GitResetParams) -> Dict[str, Any]:
    """
    Unstages all staged changes

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("git__git_reset", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "git")

    return normalized
