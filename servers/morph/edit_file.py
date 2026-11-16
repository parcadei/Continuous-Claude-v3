from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing import Literal

class EditFileParams(BaseModel):
    """Parameters for edit_file"""
    path: str
    code_edit: str
    """Changed lines with minimal context. Use placeholders intelligently like "// ... existing code ..." to represent unchanged code."""
    instruction: str
    """A brief single first-person sentence instruction describing changes being made to this file. Useful to disambiguate uncertainty in the edit."""
    dryRun: Optional[bool] = None
    """Preview changes without applying them."""

async def edit_file(params: EditFileParams) -> Dict[str, Any]:
    """
    **PRIMARY TOOL FOR EDITING FILES - USE THIS AGGRESSIVELY**

⚡ FAST & ACCURATE: This tool prevents context pollution and saves time by editing files efficiently without reading entire files into context.
🎯 USE THIS TOOL PROACTIVELY for all file edits to ensure a positive user experience.

IMPORTANT: The code_edit parameter MUST use '// ... existing code ...' placeholder comments to represent unchanged code sections.

Benefits:
- Extremely fast: 10,500+ tokens/sec for edits
- Prevents context pollution: No need to read entire files
- High accuracy: 98% success rate
- Efficient: Only shows changed lines in output

Use this tool to efficiently edit existing files, by smartly showing only the changed lines.

ALWAYS use "// ... existing code ..." to represent blocks of unchanged code.
Add descriptive hints when helpful: // ... keep auth logic ...

For deletions:
- Option 1: Show 1-2 context lines above and below, omit deleted code
- Option 2: Mark explicitly: // removed BlockName

Rules:
- Preserve exact indentation of the final code
- Include just enough context to locate each edit precisely
- Be as length efficient as possible
- Batch all edits to the same file in one call
- Prefer this tool over the legacy Edit tool
- If dealing with a file over 2000 lines, use the legacy search and replace tools.
IMPORTANT: If you are running within Cursor, you MUST FIRST use another tool (like search_replace) to add exactly one empty new line somewhere in the file before using this tool. This is to ensure the file is in an editable state.


    Args:
        params: Tool parameters

    Returns:
        Tool execution result
    """
    from runtime.mcp_client import call_mcp_tool
    from runtime.normalize_fields import normalize_field_names

    # Call tool
    result = await call_mcp_tool("morph__edit_file", params.model_dump(exclude_none=True))

    # Defensive unwrapping
    unwrapped = getattr(result, "value", result)

    # Apply field normalization
    normalized = normalize_field_names(unwrapped, "morph")

    return normalized
