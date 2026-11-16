from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ManageSelectionParams(BaseModel):
    """Parameters for manage_selection"""
    mode: Optional[Literal["full", "slices", "codemap_only"]] = None
    """How to represent files in selection: 'full' (complete content), 'slices' (line ranges), or 'codemap_only' (signatures only). With op=set, mode changes semantics (see 'op=set semantics' above)."""
    op: Optional[Literal["get", "add", "remove", "set", "clear", "preview", "promote", "demote"]] = None
    """Operation"""
    path_display: Optional[Literal["full", "relative"]] = None
    """Path display for blocks"""
    paths: Optional[List[str]] = None
    """File or folder paths (required for add/remove/set)"""
    slices: Optional[List[Dict[str, Any]]] = None
    """Selection slices to apply (path + line ranges)"""
    strict: Optional[bool] = None
    """Throw when no paths resolve (mutations)"""
    view: Optional[Literal["summary", "files", "content", "codemaps"]] = None
    """Amount of detail to return"""

async def manage_selection(params: ManageSelectionParams) -> Dict[str, Any]:
    """
    Manage the current selection used by all tools.

Ops: get | add | remove | set | clear | preview | promote | demote
Options:
• view="summary"|"files"|"content" (default "summary")
• path_display="relative"|"full" (default "relative")
• strict=true|false (default false) — if a mutation resolves no paths, return a helpful error; set false for no‑op
• mode="full"|"slices"|"codemap_only" (default "full"):
  - "full": Complete file content
  - "slices": Specific line ranges only
  - "codemap_only": Efficient API structure (function/type signatures) for token savings
  - Files without an available codemap are skipped and reported as "codemap unavailable" when targeting folders or paths in codemap_only mode.

Automatic Codemap Management:
• When selecting files with mode="full" or "slices" (via op=add or op=set), auto-adds codemaps for related/dependency files
• Check complete selection (including auto-codemaps) with op="get" view="files"
• Manual codemap operations (mode="codemap_only", promote, demote) disable auto-management until you clear
• Prefer auto-management; only manually manage when you need precise control

op=set semantics (mode controls behavior):
• mode="full": Clears selection, replaces with provided paths/slices (complete reset)
• mode="slices": File-scoped - adds any paths without clearing, replaces slice definitions only for specified files
• mode="codemap_only": Replaces codemap-only files, disables auto-management

Path Handling:
• Paths can be files or directories (directories are expanded to all files within, recursively)
• Paths can be relative (to workspace root) or absolute
• For single-root workspaces: "src/main.swift" or "Root/src/main.swift" both work
• For multi-root workspaces: prefix with root name (e.g., "ProjectA/src/main.swift")
• Fuzzy matching enabled by default - close matches will be resolved

Guidance:
• Read files with read_file before slicing to identify relevant sections
• Use ranges with descriptions for clarity (aliases: description/desc/label)
• Preview with op="preview" view="files" to see the complete selection (including auto-codemaps) and token counts before committing

Examples:
• Add full file: {"op":"add","paths":["Root/src/main.swift"]}
• Add codemap: {"op":"add","paths":["Root/src/utils/helper.swift"],"mode":"codemap_only"}
• Set slices (file-scoped): {"op":"set","mode":"slices","slices":[{"path":"Root/src/file.swift","ranges":[{"start_line":45,"end_line":120,"description":"UserAuth flow"}]}]}
• Add/merge slices: {"op":"add","slices":[{"path":"Root/src/file.swift","ranges":[{"start_line":200,"end_line":250}]}]}
• Promote codemap→full: {"op":"promote","paths":["Root/src/utils/helper.swift"]}
• Demote full→codemap: {"op":"demote","paths":["Root/src/utils/helper.swift"]}

Related:
• Discover candidates: get_file_tree, file_search
• Preview structure fast: get_code_structure
• Snapshot everything: workspace_context
• Apply changes: apply_edits
• Chat: chat_send (list/log with chats)

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__manage_selection", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
