from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ChatsParams(BaseModel):
    """Parameters for chats"""
    action: Optional[Literal["list", "log"]] = None
    """list or log"""
    chat_id: Optional[str] = None
    """Chat ID (alias of id)"""
    diffs: Optional[bool] = None
    """Include diff summaries (alias: include_diffs)"""
    id: Optional[str] = None
    """Chat ID (alias: chat_id) for log"""
    limit: Optional[int] = None
    """Max items to return - for 'list': max sessions (default 10), for 'log': max messages (default 3)"""

async def chats(params: ChatsParams) -> Dict[str, Any]:
    """
    List chats or view a chat's history. Actions: list | log

`list`: recent chats (ID, name, selected files, last activity) — use the ID with `chat_send`
`log`: full conversation history (optionally include diffs)

Notes:
- Each chat maintains its own selection and context; continuing restores state
- `chat_send` without `chat_id` resumes the most recent by default
- You can **rename** a session anytime by passing `chat_name` in `chat_send`
Related: chat_send, workspace_context

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__chats", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
