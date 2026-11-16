from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ChatSendParams(BaseModel):
    """Parameters for chat_send"""
    chat_id: Optional[str] = None
    """Chat ID to continue a specific chat (optional)"""
    chat_name: Optional[str] = None
    """Set or update the chat session name"""
    include_diffs: Optional[bool] = None
    """Include edit diffs in the reply (default: true). Pass false to omit."""
    message: Optional[str] = None
    """Your message to send (ignored if use_tab_prompt is true)"""
    mode: Optional[Literal["chat", "plan", "edit"]] = None
    """Operation mode"""
    model: Optional[str] = None
    """Model preset ID or name. Call `list_models` first to see available presets."""
    new_chat: bool
    """Start a new chat session"""
    selected_paths: Optional[List[str]] = None
    """File paths for context (overrides current selection)"""
    use_tab_prompt: Optional[bool] = None
    """When true, use the active compose tab's prompt instead of message parameter"""

async def chat_send(params: ChatSendParams) -> Dict[str, Any]:
    """
    Start a new chat or continue an existing conversation. Modes: `chat` | `plan` | `edit`.

**Recommended pair‑program loop**
1) **Plan** (`mode="plan"`): ask for architecture/steps or request a review.
2) **Apply**: use `apply_edits` (or `chat_send` with `mode="edit"`) to make the changes.
3) **Review** (`mode="chat"` or `plan`): get a second opinion; refine.
4) **Repeat** in the **same chat**.

**Critical context hygiene**
- Run `manage_selection` op=`get` (view="files") to confirm context and tokens.
- Prefer `set` (or `add`/`remove`) so all **related files** are included.
- For a full snapshot (prompt, selection, code, tokens; optionally file text/tree), call `workspace_context`.
- Bias toward **more context over too little**; avoid selecting only one file that references others.

**Session management**
- `new_chat`: true to start; else continues the most recent (or pass `chat_id`)
- `selected_paths`: replace the selection for this message
- `chat_name`: optional but **highly recommended** — short, descriptive (e.g., "Fix login crash – auth flow")
- `model`: preset id/name; call `list_models` first

**Limitations**
- No commands/tests; only sees **selected files** + conversation history
- For a **snapshot of context** (prompt, selection, codemaps, optional file contents/tree), call `workspace_context`
	(add `"files"` in `include` to embed file text). For targeted slices, use `read_file` or `file_search`.
- The chat does not track diff history; it sees current file state only

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__chat_send", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
