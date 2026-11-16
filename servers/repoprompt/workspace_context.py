from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class WorkspaceContextParams(BaseModel):
    """Parameters for workspace_context"""
    include: Optional[List[Literal["prompt", "selection", "code", "files", "tree", "tokens"]]] = None
    """What to include (defaults to prompt, selection, code, tokens)"""
    path_display: Optional[Literal["full", "relative"]] = None
    """Path display for blocks"""

async def workspace_context(params: WorkspaceContextParams) -> Dict[str, Any]:
    """
    Snapshot of this window's workspace: prompt, selection, code structure (codemaps). Larger parts are opt-in.
Defaults include: prompt, selection, code, tokens.
include: ["prompt","selection","code","files","tree","tokens"]
path_display: "relative"|"full"

Related: manage_selection (curate selection), prompt (edit instructions), get_file_tree, file_search, get_code_structure, apply_edits, chat_send, chats.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__workspace_context", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
