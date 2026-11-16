from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class ContextBuilderParams(BaseModel):
    """Parameters for context_builder"""
    instructions: Optional[str] = None
    """Task description for the agent (what context to build)"""
    response_type: Optional[Literal["plan", "question", "clarify"]] = None
    """Optional: 'plan' to generate implementation plan, 'question' to ask a question. Omit or 'clarify' to just return context."""

async def context_builder(params: ContextBuilderParams) -> Dict[str, Any]:
    """
    Start a task by intelligently exploring the codebase and building optimal file context.

Ideal as the **first step** for complex tasks: the agent maps out relevant code, selects files
within a token budget, and can generate an implementation plan in one shot. The resulting
chat thread is perfect for follow-up questions, mid-task clarifications, or getting a second
opinion as you work.

**Tips:**
- Use response_type="plan" to get an implementation plan alongside the context, or generate one later via chat_send
- Continue the conversation via chat_send with the returned chat_id
- Add files to the selection with manage_selection as new areas become relevant
- Run context_builder again anytime to explore a different area of the codebase

Parameters:
- instructions: Describe what you want to accomplish
- response_type: "plan" generates an implementation plan; "question" answers about the codebase; omit for context-only

Returns file selection, prompt, and status. With response_type="plan" or "question", also returns
the response and a chat_id for seamless follow-up conversation.

Note: Thorough exploration takes 30s-5min depending on codebase size and task complexity.

    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("repoprompt__context_builder", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "repoprompt")

    return normalized
