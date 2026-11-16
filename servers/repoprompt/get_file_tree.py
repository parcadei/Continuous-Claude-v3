from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class GetFileTreeParams(BaseModel):
    """Parameters for get_file_tree"""
    max_depth: Optional[int] = None
    """Maximum depth (root = 0)"""
    mode: Optional[Literal["auto", "full", "folders", "selected"]] = None
    """Filter mode (for 'files' type only)"""
    path: Optional[str] = None
    """Optional starting folder (absolute or relative) when type='files'. When provided, the tree is generated from this folder and 'mode' and 'max_depth' apply from that subtree."""
    type: Literal["files", "roots"]
    """Tree type to generate"""

async def get_file_tree(params: GetFileTreeParams) -> Dict[str, Any]:
    """
    ASCII directory tree of the project.

Types:
- `files` — modes:
	- `auto` (default): tries full tree, then trims depth to fit ~10k tokens
	- `full`: all files/folders (can be very large)
	- `folders`: directories only
	- `selected`: only selected files and their parents
	Optional: `path` to start from a specific folder; `max_depth` to limit (root=0).
- `roots` — list root folders.

Files with a codemap are marked `+` in the standard tree.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__get_file_tree", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
