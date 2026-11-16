from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GitLogParams(BaseModel):
    """Parameters for git_log"""
    repo_path: str
    max_count: Optional[int] = None
    start_timestamp: Optional[Dict[str, Any]] = None
    """Start timestamp for filtering commits. Accepts: ISO 8601 format (e.g., '2024-01-15T14:30:25'), relative dates (e.g., '2 weeks ago', 'yesterday'), or absolute dates (e.g., '2024-01-15', 'Jan 15 2024')"""
    end_timestamp: Optional[Dict[str, Any]] = None
    """End timestamp for filtering commits. Accepts: ISO 8601 format (e.g., '2024-01-15T14:30:25'), relative dates (e.g., '2 weeks ago', 'yesterday'), or absolute dates (e.g., '2024-01-15', 'Jan 15 2024')"""

async def git_log(params: GitLogParams) -> Dict[str, Any]:
    """
    Shows the commit logs

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("git__git_log", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "git")

    return normalized
