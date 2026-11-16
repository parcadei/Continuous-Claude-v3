from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ManageWorkspacesParams(BaseModel):
    """Parameters for manage_workspaces"""
    action: str
    """Action to perform: 'list', 'switch', 'create', 'delete', 'add_folder', 'remove_folder', 'list_tabs', or 'select_tab'"""
    focus: Optional[bool] = None
    """For 'select_tab': if true, also switches the UI to show the selected tab"""
    folder_path: Optional[str] = None
    """Absolute folder path (required for 'add_folder', 'remove_folder')"""
    name: Optional[str] = None
    """Name for new workspace (required for 'create')"""
    tab: Optional[str] = None
    """Compose tab UUID or name (required for 'select_tab')"""
    window_id: Optional[int] = None
    """Optional window ID; defaults to selected or only window"""
    workspace: Optional[str] = None
    """Workspace UUID or name (required for 'switch', 'delete', 'add_folder', 'remove_folder')"""

async def manage_workspaces(params: ManageWorkspacesParams) -> Dict[str, Any]:
    """
    Manage workspaces across RepoPrompt windows.

Actions:
• list    – Return all known workspaces (id, name, repoPaths, showing window IDs)
• switch  – Switch a window to a specified workspace
• create  – Create a new workspace (requires user approval)
• delete  – Delete a workspace (requires user approval)
• add_folder – Add a folder to a workspace (requires user approval)
• remove_folder – Remove a folder from a workspace (requires user approval)
• list_tabs  – List compose tabs for the active workspace in a window
• select_tab – Bind this MCP connection to a specific compose tab

Parameters:
- action: "list" | "switch" | "create" | "delete" | "add_folder" | "remove_folder" | "list_tabs" | "select_tab" (required)
- workspace: string                             (required for 'switch', 'delete', 'add_folder', 'remove_folder'; UUID or name)
- name: string                                  (required for 'create'; the new workspace name)
- folder_path: string                           (required for 'add_folder', 'remove_folder'; absolute path)
- tab: string                                   (required for 'select_tab'; UUID or name)
- window_id: integer                            (optional; target window, defaults to selected or only window)
- focus: boolean                                (optional for 'select_tab'; default false)

For 'switch', provide a single 'workspace' value. If it parses as a UUID, that workspace is selected by ID; otherwise it is treated as a name and the first match is used.

After selecting a window (via select_window), use list_tabs and select_tab to pin your connection to a specific compose tab. This ensures your tools operate on consistent context even if the user changes the active tab in the UI.

Tab binding behavior:
• If no tab is bound, tools use the user's currently active tab. This can cause inconsistent results if the user switches tabs during your operations.
• Use select_tab to explicitly bind to a specific tab for predictable, stable context across multiple tool calls.
• Alternatively, pass the hidden '_tabID' parameter with any tool call to bind on-the-fly.

Output flags:
• [active] = The tab currently visible in the UI for that window
• [bound] = The tab this MCP connection is pinned to; your tool calls use this tab even if the user switches the visible tab

IMPORTANT: The 'focus' parameter switches the visible tab in the UI, which can be disruptive to the user's workflow. Only set focus=true when the user explicitly requests to see or switch to a specific tab. For background operations, omit focus or set it to false.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__manage_workspaces", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
