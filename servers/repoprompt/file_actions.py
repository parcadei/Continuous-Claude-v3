from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class FileActionsParams(BaseModel):
    """Parameters for file_actions"""
    action: Literal["create", "delete", "move"]
    """Operation to perform"""
    content: Optional[str] = None
    """File content (for create)"""
    if_exists: Optional[Literal["error", "overwrite"]] = None
    """Behavior if the file already exists (for create)"""
    new_path: Optional[str] = None
    """New path (for move)"""
    path: str
    """File path"""

async def file_actions(params: FileActionsParams) -> Dict[str, Any]:
    """
    Create, delete, or move files.

Actions:
- `create`: Create a new file with `content`. Use `if_exists="overwrite"` to replace an existing file. New files are added to the selection.
- `delete`: Delete a file (absolute path required for safety).
- `move`: Move/rename to `new_path` (fails if destination exists).

Paths: Relative or absolute (`delete` requires absolute). When multiple roots are loaded, you must provide an absolute path when creating files; relative paths are rejected to avoid ambiguity.
Options: `if_exists` (create): "error" (default) or "overwrite".

Note: Multi-root file creation is supported. Missing intermediate folders are automatically created.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__file_actions", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
